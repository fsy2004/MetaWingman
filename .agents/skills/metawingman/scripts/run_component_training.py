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
from metawingman_core.training_corpus import TrainingCorpusError, preflight_component_training, _retrieval_query


def _warmup_steps(train_count: int, batch_size: int, epochs: int, warmup_ratio: float) -> int:
    """Materialize a frozen warmup ratio into explicit steps.

    transformers >= 5 dropped TrainingArguments.warmup_ratio; computing the
    equivalent warmup_steps keeps the frozen optimization semantics across
    runtime versions.
    """
    steps_per_epoch = math.ceil(train_count / batch_size)
    return max(0, int(round(steps_per_epoch * epochs * warmup_ratio)))


def _pad_id_lists(id_lists: list[list[int]], pad_id: int) -> tuple[list[list[int]], list[list[int]]]:
    """Pad token id lists to the batch maximum with attention masks."""
    if not id_lists:
        return [], []
    longest = max(len(ids) for ids in id_lists)
    padded = [ids + [pad_id] * (longest - len(ids)) for ids in id_lists]
    masks = [[1] * len(ids) + [0] * (longest - len(ids)) for ids in id_lists]
    return padded, masks


def _accumulation_steps(job: dict[str, Any]) -> int:
    """Read the optional gradient-accumulation step count, defaulting to 1.

    ``optimization.gradient_accumulation_steps`` is optional in the job schema and
    defaults to 1, which reproduces the historical per-micro-batch update exactly.
    """
    steps = int(job["optimization"].get("gradient_accumulation_steps", 1))
    if steps < 1:
        raise ValueError("optimization.gradient_accumulation_steps must be >= 1")
    return steps


def _accumulation_windows(batch_count: int, accumulation_steps: int) -> list[tuple[int, int]]:
    """Split one epoch's micro-batches into gradient-accumulation windows.

    Returns ``(start, length)`` slices: each window is one optimizer step and one
    effective batch. Full windows hold ``accumulation_steps`` micro-batches and a
    trailing partial window keeps its remainder so no gradient is dropped. With
    ``accumulation_steps == 1`` every window is a single micro-batch and the
    original per-batch update is reproduced exactly.
    """
    return [
        (start, min(accumulation_steps, batch_count - start))
        for start in range(0, batch_count, accumulation_steps)
    ]


def _accumulate_losses(step_losses: list[float], accumulation_steps: int) -> list[float]:
    """Reduce per-micro-batch losses into per-effective-batch means.

    ``step_losses[i]`` is the unscaled cross-entropy of micro-batch ``i`` (the value
    divided by the window size before backward). The result has one entry per
    optimizer step: the mean of the micro-batch losses in that accumulation window,
    i.e. the cross-entropy of the effective batch. This preserves the reporting
    scale of the non-accumulated run (per-optimizer-step mean cross-entropy).
    """
    return [
        sum(step_losses[start:start + length]) / length
        for start, length in _accumulation_windows(len(step_losses), accumulation_steps)
    ]


def _rank_metrics(similarities: list[list[float]], families: list[str]) -> dict[str, float]:
    """Full-corpus dev ranking metrics; each query's positive is its own document.

    Documents from the same review family as the query are masked before
    ranking (family isolation). Returns recall@10, MRR, and precision@1.
    """
    queries = len(similarities)
    if queries == 0:
        return {"recall_at_10": 0.0, "mrr": 0.0, "precision_at_1": 0.0}
    recall = 0.0
    mrr = 0.0
    precision_at_1 = 0
    for index, row in enumerate(similarities):
        masked = [
            -float("inf") if j != index and families[j] == families[index] else score
            for j, score in enumerate(row)
        ]
        ranked = sorted(range(queries), key=lambda j: masked[j], reverse=True)
        position = ranked.index(index) + 1
        mrr += 1.0 / position
        recall += 1.0 if position <= 10 else 0.0
        precision_at_1 += 1 if position == 1 else 0
    return {
        "recall_at_10": recall / queries,
        "mrr": mrr / queries,
        "precision_at_1": precision_at_1 / queries,
    }


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
        eval_steps=job["output"]["checkpoint_every_steps"],
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
    from transformers import AutoModel, AutoTokenizer
    pairs = _load_jsonl((root / job["dataset"]["pairs_path"]).resolve())
    examples = _load_jsonl((root / job["dataset"]["examples_path"]).resolve())
    tokenizer = AutoTokenizer.from_pretrained(job["model"]["repository_id"], revision=job["model"]["tokenizer_revision"])
    model = AutoModel.from_pretrained(job["model"]["repository_id"], revision=job["model"]["revision"])
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)
    positives_by_query = {
        item["query_example_id"]: item
        for item in pairs
        if item["query_split"] == "train" and item["label"] == 1
    }
    negatives_by_query: dict[str, list[dict]] = {}
    for item in pairs:
        if item["query_split"] == "train" and item["label"] == 0:
            negatives_by_query.setdefault(item["query_example_id"], []).append(item)
    batch_size = job["optimization"]["batch_size"]
    accumulation_steps = _accumulation_steps(job)
    query_ids = sorted(positives_by_query)
    batches = [query_ids[i:i + batch_size] for i in range(0, len(query_ids), batch_size)]
    pad_id = tokenizer.pad_token_id if tokenizer.pad_token_id is not None else 0

    # Pre-tokenize every distinct text once (batched); the loop then pads ids.
    def _tokenize_texts(texts: list[str], max_length: int) -> list[list[int]]:
        output: list[list[int]] = []
        for start in range(0, len(texts), 256):
            output.extend(
                tokenizer(texts[start:start + 256], padding=False, truncation=True, max_length=max_length)["input_ids"]
            )
        return output

    query_texts = [positives_by_query[query_id]["query_text"] for query_id in query_ids]
    query_cache = dict(zip(query_ids, _tokenize_texts(query_texts, 256)))
    document_texts_by_id: dict[str, str] = {}
    for query_id in query_ids:
        positive = positives_by_query[query_id]
        document_texts_by_id[positive["document_example_id"]] = positive["document_text"]
        for negative in negatives_by_query.get(query_id, []):
            document_texts_by_id[negative["document_example_id"]] = negative["document_text"]
    document_ids = sorted(document_texts_by_id)
    document_cache = dict(zip(
        document_ids, _tokenize_texts([document_texts_by_id[identifier] for identifier in document_ids], 512)
    ))

    optimizer = torch.optim.AdamW(model.parameters(), lr=job["optimization"]["learning_rate"], weight_decay=job["optimization"]["weight_decay"])
    model.train()
    losses = []
    for _ in range(job["optimization"]["epochs"]):
        step_losses: list[float] = []
        for window_start, window_size in _accumulation_windows(len(batches), accumulation_steps):
            for query_batch in batches[window_start:window_start + window_size]:
                positives = [positives_by_query[query_id] for query_id in query_batch]
                hard_negatives: list[dict] = []
                for query_id in query_batch:
                    hard_negatives.extend(
                        sorted(negatives_by_query.get(query_id, []), key=lambda item: item["pair_id"])[:3]
                    )
                query_id_lists = [query_cache[query_id] for query_id in query_batch]
                document_id_lists = (
                    [document_cache[item["document_example_id"]] for item in positives]
                    + [document_cache[item["document_example_id"]] for item in hard_negatives]
                )
                padded_queries, query_masks = _pad_id_lists(query_id_lists, pad_id)
                padded_documents, document_masks = _pad_id_lists(document_id_lists, pad_id)
                query_tensors = {
                    "input_ids": torch.tensor(padded_queries, device=device),
                    "attention_mask": torch.tensor(query_masks, device=device),
                }
                document_tensors = {
                    "input_ids": torch.tensor(padded_documents, device=device),
                    "attention_mask": torch.tensor(document_masks, device=device),
                }
                query_vectors = functional.normalize(model(**query_tensors).last_hidden_state[:, 0], dim=-1)
                document_vectors = functional.normalize(model(**document_tensors).last_hidden_state[:, 0], dim=-1)
                logits = query_vectors @ document_vectors.T
                labels = torch.arange(len(positives), device=device)
                loss = functional.cross_entropy(logits, labels)
                # Average the gradient over the effective batch: divide this
                # micro-batch loss by the window size before backward so the summed
                # grads equal the gradient of the window's mean cross-entropy.
                (loss / window_size).backward()
                step_losses.append(float(loss.detach().cpu()))
            optimizer.step()
            optimizer.zero_grad()
        # Report one value per optimizer step: the mean of the window's micro-batch
        # cross-entropies (the effective-batch cross-entropy), keeping
        # train_mean_loss on the same scale as a non-accumulated run.
        losses.extend(_accumulate_losses(step_losses, accumulation_steps))
    model.eval()

    def _encode(texts: list[str], max_length: int) -> torch.Tensor:
        vectors = []
        for start in range(0, len(texts), 32):
            batch = tokenizer(texts[start:start + 32], padding=True, truncation=True, max_length=max_length, return_tensors="pt").to(device)
            with torch.no_grad():
                vectors.append(functional.normalize(model(**batch).last_hidden_state[:, 0], dim=-1))
        return torch.cat(vectors)

    # (a) hard-negative candidate-set ranking (positive vs its own negatives)
    grouped: dict[str, list[tuple[float, int]]] = {}
    with torch.no_grad():
        for item in (item for item in pairs if item["query_split"] == "development"):
            query_vector = _encode([item["query_text"]], 256)
            document_vector = _encode([item["document_text"]], 512)
            grouped.setdefault(item["query_example_id"], []).append((float((query_vector * document_vector).sum().cpu()), item["label"]))
    candidate_mrr = 0.0
    candidate_p1 = 0
    for items in grouped.values():
        ordered = sorted(items, key=lambda pair: pair[0], reverse=True)
        rank = next(index + 1 for index, (_, label) in enumerate(ordered) if label == 1)
        candidate_mrr += 1.0 / rank
        candidate_p1 += 1 if rank == 1 else 0
    candidate_mrr /= max(1, len(grouped))
    candidate_p1 /= max(1, len(grouped))

    # (b) full development-corpus ranking: each query's positive is its own document
    dev_examples = [item for item in examples if item["task"] == "evidence_retrieval" and item["split"] == "development"]
    query_vectors = _encode([_retrieval_query(item) for item in dev_examples], 256)
    document_vectors = _encode([item["input_text"] for item in dev_examples], 512)
    with torch.no_grad():
        similarities = (query_vectors @ document_vectors.T).cpu().tolist()
    families = [item["family_id"] for item in dev_examples]
    corpus_metrics = _rank_metrics(similarities, families)
    final = output / "final"; final.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(final, safe_serialization=True); tokenizer.save_pretrained(final)
    return {
        "train_mean_loss": sum(losses) / len(losses),
        "development_recall_at_10": corpus_metrics["recall_at_10"],
        "development_mrr": corpus_metrics["mrr"],
        "development_precision_at_1": corpus_metrics["precision_at_1"],
        "development_queries": len(dev_examples),
        "hard_negative_mrr": candidate_mrr,
        "hard_negative_precision_at_1": candidate_p1,
    }


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
