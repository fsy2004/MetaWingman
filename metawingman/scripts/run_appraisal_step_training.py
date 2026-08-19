"""Train the appraisal-step verifier component (R6, trained version).

Task: classify an appraisal-role passage into one of six risk-of-bias
domains (selection / performance / detection / attrition / reporting /
other). Weak-supervised candidates come from
`build_appraisal_step_candidates.py`; labels are deterministic rules, so
the acceptance ceiling is rule-consistency (see the component
preregistration doc). Class-imbalanced cross-entropy uses inverse
frequency weights.

Usage (server):
  python metawingman/scripts/run_appraisal_step_training.py \
    --candidates validation-output/training-corpus/appraisal-step-candidates.jsonl \
    --out-dir validation-output/training-runs/appraisal-step \
    --model-repository microsoft/BiomedNLP-BiomedBERT-base-uncased-abstract-fulltext \
    --model-revision e1354b7a3a09615f6aba48dfad4b7a613eef7062
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Any, Sequence

DOMAIN_LABELS = ("selection_bias", "performance_bias", "detection_bias", "attrition_bias", "reporting_bias", "other")
LABEL_TO_ID = {label: index for index, label in enumerate(DOMAIN_LABELS)}
ID_TO_LABEL = {index: label for label, index in LABEL_TO_ID.items()}


def load_candidates(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def split_records(candidates: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    train = [item for item in candidates if item.get("split") == "train"]
    dev = [item for item in candidates if item.get("split") == "development"]
    return train, dev


def records_to_pairs(records: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    pairs = []
    for item in records:
        label = item.get("weak_label")
        if label not in LABEL_TO_ID:
            continue
        pairs.append({"text": item["text"], "label": LABEL_TO_ID[label]})
    return pairs


def _hash_tree(root: Path) -> dict[str, str]:
    hashes = {}
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        hashes[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return hashes


def _inverse_frequency_weights(labels: Sequence[int], num_classes: int) -> list[float]:
    """Per-CLASS inverse-frequency weights (length == num_classes).

    torch.nn.functional.cross_entropy expects one weight per class, not per
    example. Classes absent from the training split get weight 0.0 so they
    contribute no gradient.
    """
    counts: dict[int, int] = {}
    for label in labels:
        counts[label] = counts.get(label, 0) + 1
    total = len(labels)
    return [
        total / (num_classes * counts[label]) if counts.get(label, 0) > 0 else 0.0
        for label in range(num_classes)
    ]


def train(
    candidates: list[dict[str, Any]],
    *,
    out_dir: Path,
    repository: str,
    revision: str,
    epochs: int,
    batch_size: int,
    gradient_accumulation_steps: int,
    learning_rate: float,
    weight_decay: float,
    warmup_ratio: float,
    precision: str,
    seed: int,
    device: str,
    max_length: int,
) -> dict[str, Any]:
    import numpy as np
    import torch
    from datasets import Dataset
    from sklearn.metrics import f1_score
    from transformers import AutoModelForSequenceClassification, AutoTokenizer, Trainer, TrainingArguments

    if device != "cuda" and not torch.cuda.is_available():
        device = "cpu"

    tokenizer = AutoTokenizer.from_pretrained(repository, revision=revision)
    model = AutoModelForSequenceClassification.from_pretrained(
        repository, revision=revision, num_labels=len(DOMAIN_LABELS),
        id2label=ID_TO_LABEL, label2id=LABEL_TO_ID,
    )
    train_records, dev_records = split_records(candidates)
    datasets = {}
    for split, records in (("train", train_records), ("development", dev_records)):
        pairs = records_to_pairs(records)
        dataset = Dataset.from_list(pairs)
        datasets[split] = dataset.map(
            lambda batch: tokenizer(batch["text"], padding="max_length", truncation=True, max_length=max_length),
            batched=True,
        )

    weights = _inverse_frequency_weights(
        [item["label"] for item in records_to_pairs(train_records)], num_classes=len(DOMAIN_LABELS)
    )
    weights_tensor = torch.tensor(weights, dtype=torch.float32, device=device)

    class WeightedTrainer(Trainer):
        def compute_loss(self, model, inputs, return_outputs=False, **kwargs):
            labels = inputs.pop("labels")
            outputs = model(**inputs)
            loss = torch.nn.functional.cross_entropy(outputs.logits, labels, weight=weights_tensor)
            return (loss, outputs) if return_outputs else loss

    def compute_metrics(eval_pred):
        predictions = np.argmax(eval_pred.predictions, axis=-1)
        return {"macro_f1": float(f1_score(eval_pred.label_ids, predictions, average="macro"))}

    total_steps = (len(datasets["train"]) // (batch_size * gradient_accumulation_steps)) * epochs
    warmup_steps = max(1, int(total_steps * warmup_ratio))
    arguments = TrainingArguments(
        output_dir=str(out_dir), num_train_epochs=epochs,
        per_device_train_batch_size=batch_size, per_device_eval_batch_size=batch_size,
        gradient_accumulation_steps=gradient_accumulation_steps,
        learning_rate=learning_rate, weight_decay=weight_decay,
        warmup_steps=warmup_steps, eval_strategy="epoch", save_strategy="epoch",
        load_best_model_at_end=True, metric_for_best_model="macro_f1", greater_is_better=True,
        seed=seed, data_seed=seed,
        fp16=precision == "fp16", bf16=precision == "bf16", report_to=[],
        logging_steps=200, save_total_limit=2,
    )
    trainer = WeightedTrainer(
        model=model, args=arguments,
        train_dataset=datasets["train"], eval_dataset=datasets["development"],
        compute_metrics=compute_metrics,
    )
    trainer.train()
    metrics = trainer.evaluate()
    final = out_dir / "final"
    final.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(final, safe_serialization=True)
    tokenizer.save_pretrained(final)
    return {
        "train_count": len(datasets["train"]),
        "development_count": len(datasets["development"]),
        "eval_macro_f1": round(float(metrics.get("eval_macro_f1", 0.0)), 6),
        "eval_loss": round(float(metrics.get("eval_loss", 0.0)), 6),
        "torch_version": torch.__version__,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--model-repository", required=True)
    parser.add_argument("--model-revision", required=True)
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--gradient-accumulation-steps", type=int, default=2)
    parser.add_argument("--learning-rate", type=float, default=2e-5)
    parser.add_argument("--weight-decay", type=float, default=0.01)
    parser.add_argument("--warmup-ratio", type=float, default=0.1)
    parser.add_argument("--precision", choices=["fp16", "bf16"], default="bf16")
    parser.add_argument("--seed", type=int, default=20260815)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--max-length", type=int, default=512)
    args = parser.parse_args()
    try:
        candidates = load_candidates(args.candidates)
        if not candidates:
            raise ValueError("candidate stream is empty")
        args.out_dir.mkdir(parents=True, exist_ok=True)
        started = time.monotonic()
        metrics = train(
            candidates, out_dir=args.out_dir, repository=args.model_repository,
            revision=args.model_revision, epochs=args.epochs, batch_size=args.batch_size,
            gradient_accumulation_steps=args.gradient_accumulation_steps,
            learning_rate=args.learning_rate, weight_decay=args.weight_decay,
            warmup_ratio=args.warmup_ratio, precision=args.precision, seed=args.seed,
            device=args.device, max_length=args.max_length,
        )
        receipt = {
            "schema_version": "1.0",
            "component": "appraisal_step_classification",
            "execution_state": "completed",
            "elapsed_seconds": time.monotonic() - started,
            "metrics": metrics,
            "checkpoint_hashes": _hash_tree(args.out_dir),
        }
        (args.out_dir / "execution-receipt.json").write_text(
            json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        print(json.dumps(receipt, indent=2, ensure_ascii=False))
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"execution_state": "failed", "error": str(exc)}, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
