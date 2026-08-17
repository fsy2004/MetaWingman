#!/usr/bin/env python3
"""Run a frozen bounded-component job only after an exact server preflight."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import random
import time
from pathlib import Path
from typing import Any

from metawingman_core.state_store import atomic_write_json
from metawingman_core.training_corpus import TrainingCorpusError, preflight_component_training


def _warmup_steps(train_count: int, batch_size: int, epochs: int, warmup_ratio: float) -> int:
    """Materialize a frozen warmup ratio into explicit steps.

    transformers >= 5 dropped TrainingArguments.warmup_ratio; computing the
    equivalent warmup_steps keeps the frozen optimization semantics across
    runtime versions.
    """
    steps_per_epoch = math.ceil(train_count / batch_size)
    return max(0, int(round(steps_per_epoch * epochs * warmup_ratio)))


def validate_training_job(job: dict[str, Any], root: Path) -> dict[str, Any]:
    """Validation-only boundary that never imports Torch or Transformers."""
    return preflight_component_training(job, root, inspect_server=False)


def _hash_tree(root: Path) -> dict[str, str]:
    hashes = {}
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        hashes[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return hashes


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _run_section_role(job: dict[str, Any], root: Path, output: Path) -> dict[str, Any]:
    import numpy as np
    import torch
    from datasets import Dataset
    from sklearn.metrics import f1_score
    from transformers import AutoModelForSequenceClassification, AutoTokenizer, Trainer, TrainingArguments

    examples = _load_jsonl((root / job["dataset"]["examples_path"]).resolve())
    examples = [item for item in examples if item["task"] == "section_role_classification"]
    labels = sorted({item["target"]["section_role"] for item in examples})
    label_to_id = {label: index for index, label in enumerate(labels)}
    tokenizer = AutoTokenizer.from_pretrained(job["model"]["repository_id"], revision=job["model"]["tokenizer_revision"])
    model = AutoModelForSequenceClassification.from_pretrained(
        job["model"]["repository_id"], revision=job["model"]["revision"], num_labels=len(labels),
        id2label={index: label for label, index in label_to_id.items()}, label2id=label_to_id,
    )
    datasets = {}
    for split in ("train", "development"):
        records = [{"text": item["input_text"], "label": label_to_id[item["target"]["section_role"]]} for item in examples if item["split"] == split]
        dataset = Dataset.from_list(records)
        datasets[split] = dataset.map(lambda batch: tokenizer(batch["text"], truncation=True, max_length=512), batched=True)
    precision = job["optimization"]["precision"]
    warmup_steps = _warmup_steps(
        len(datasets["train"]),
        job["optimization"]["batch_size"],
        job["optimization"]["epochs"],
        job["optimization"]["warmup_ratio"],
    )
    arguments = TrainingArguments(
        output_dir=str(output), num_train_epochs=job["optimization"]["epochs"],
        per_device_train_batch_size=job["optimization"]["batch_size"],
        per_device_eval_batch_size=job["optimization"]["batch_size"],
        learning_rate=job["optimization"]["learning_rate"], weight_decay=job["optimization"]["weight_decay"],
        warmup_steps=warmup_steps, eval_strategy="steps", save_strategy="steps",
        save_steps=job["output"]["checkpoint_every_steps"], save_total_limit=job["output"]["maximum_checkpoints"],
        load_best_model_at_end=True, metric_for_best_model="macro_f1", seed=job["seed"], data_seed=job["seed"],
        fp16=precision == "fp16", bf16=precision == "bf16", report_to=[],
    )
    def metrics(prediction: Any) -> dict[str, float]:
        predicted = np.argmax(prediction.predictions, axis=-1)
        return {"macro_f1": float(f1_score(prediction.label_ids, predicted, average="macro"))}
    trainer = Trainer(model=model, args=arguments, train_dataset=datasets["train"], eval_dataset=datasets["development"], processing_class=tokenizer, compute_metrics=metrics)
    trainer.train()
    metrics_out = trainer.evaluate()
    trainer.save_model(str(output / "final"))
    tokenizer.save_pretrained(str(output / "final"))
    return {key: float(value) for key, value in metrics_out.items() if isinstance(value, (int, float))}


def _run_retrieval(job: dict[str, Any], root: Path, output: Path) -> dict[str, Any]:
    import torch
    import torch.nn.functional as functional
    from torch.utils.data import DataLoader
    from transformers import AutoModel, AutoTokenizer

    pairs = _load_jsonl((root / job["dataset"]["pairs_path"]).resolve())
    tokenizer = AutoTokenizer.from_pretrained(job["model"]["repository_id"], revision=job["model"]["tokenizer_revision"])
    model = AutoModel.from_pretrained(job["model"]["repository_id"], revision=job["model"]["revision"])
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)
    train_pairs = [item for item in pairs if item["query_split"] == "train" and item["label"] == 1]
    loader = DataLoader(train_pairs, batch_size=job["optimization"]["batch_size"], shuffle=True, generator=torch.Generator().manual_seed(job["seed"]), collate_fn=lambda items: items)
    optimizer = torch.optim.AdamW(model.parameters(), lr=job["optimization"]["learning_rate"], weight_decay=job["optimization"]["weight_decay"])
    model.train()
    losses = []
    for _ in range(job["optimization"]["epochs"]):
        for batch in loader:
            queries = tokenizer([item["query_text"] for item in batch], padding=True, truncation=True, max_length=256, return_tensors="pt").to(device)
            documents = tokenizer([item["document_text"] for item in batch], padding=True, truncation=True, max_length=512, return_tensors="pt").to(device)
            query_vectors = functional.normalize(model(**queries).last_hidden_state[:, 0], dim=-1)
            document_vectors = functional.normalize(model(**documents).last_hidden_state[:, 0], dim=-1)
            logits = query_vectors @ document_vectors.T
            labels = torch.arange(logits.shape[0], device=device)
            loss = functional.cross_entropy(logits, labels)
            optimizer.zero_grad(); loss.backward(); optimizer.step()
            losses.append(float(loss.detach().cpu()))
    model.eval()
    grouped: dict[str, list[tuple[float, int]]] = {}
    with torch.no_grad():
        for item in (item for item in pairs if item["query_split"] == "development"):
            query = tokenizer([item["query_text"]], padding=True, truncation=True, max_length=256, return_tensors="pt").to(device)
            document = tokenizer([item["document_text"]], padding=True, truncation=True, max_length=512, return_tensors="pt").to(device)
            query_vector = functional.normalize(model(**query).last_hidden_state[:, 0], dim=-1)
            document_vector = functional.normalize(model(**document).last_hidden_state[:, 0], dim=-1)
            grouped.setdefault(item["query_example_id"], []).append((float((query_vector * document_vector).sum().cpu()), item["label"]))
    recall = sum(any(label == 1 for _, label in sorted(items, reverse=True)[:10]) for items in grouped.values()) / max(1, len(grouped))
    final = output / "final"; final.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(final, safe_serialization=True); tokenizer.save_pretrained(final)
    return {"train_mean_loss": sum(losses) / len(losses), "development_recall_at_10": recall}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("job", type=Path)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    try:
        job = json.loads(args.job.read_text(encoding="utf-8"))
        if args.validate_only:
            validation = validate_training_job(job, args.root)
            print(json.dumps(validation, indent=2))
            return 0 if validation["manifest_valid"] else 2
        report = preflight_component_training(job, args.root, inspect_server=True)
        if not report["ready"]:
            print(json.dumps(report, indent=2)); return 2
        random.seed(job["seed"]); os.environ["PYTHONHASHSEED"] = str(job["seed"])
        import numpy as np
        import torch
        np.random.seed(job["seed"]); torch.manual_seed(job["seed"]); torch.cuda.manual_seed_all(job["seed"])
        output = (args.root.resolve() / job["output"]["root"]).resolve(); output.relative_to(args.root.resolve()); output.mkdir(parents=True, exist_ok=True)
        started = time.monotonic()
        metrics = _run_section_role(job, args.root, output) if job["component"] == "section_role_classification" else _run_retrieval(job, args.root, output)
        receipt = {"schema_version": "1.0", "job_id": job["job_id"], "execution_state": "completed", "elapsed_seconds": time.monotonic() - started, "metrics": metrics, "checkpoint_hashes": _hash_tree(output), "torch_version": torch.__version__}
        atomic_write_json(output / "execution-receipt.json", receipt)
        print(json.dumps(receipt, indent=2)); return 0
    except (OSError, ValueError, json.JSONDecodeError, TrainingCorpusError) as exc:
        print(json.dumps({"execution_state": "failed_before_training", "error": str(exc)}, indent=2)); return 1


if __name__ == "__main__":
    raise SystemExit(main())
