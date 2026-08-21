#!/usr/bin/env python3
"""Validate or train one frozen bounded question-synthesis component."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pickle
import random
import time
from pathlib import Path
from typing import Any

from metawingman_core.schema_guard import validate_document
from metawingman_core.state_store import atomic_write_json
from metawingman_core.training_corpus import TrainingCorpusError


COMPONENTS = {"question_method_ranker", "source_support_verifier", "risk_cost_router"}


def _peak_rss_kib() -> int:
    try:
        import resource

        return int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    except ImportError:
        return 0


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _resolve(root: Path, relative: str) -> Path:
    resolved_root = root.resolve()
    path = (resolved_root / relative).resolve()
    try:
        path.relative_to(resolved_root)
    except ValueError as exc:
        raise TrainingCorpusError("job path escapes root") from exc
    return path


def _rows(path: Path) -> list[dict[str, Any]]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    for row in rows:
        validate_document(row, "question_synthesis_training_example")
    return rows


def validate_question_synthesis_job(job: dict[str, Any], root: Path) -> dict[str, Any]:
    component = job.get("component")
    if component not in COMPONENTS:
        raise TrainingCorpusError("unsupported question-synthesis component")
    if job.get("status") != "ready_for_server_preflight":
        raise TrainingCorpusError("job is not ready_for_server_preflight")
    dataset = job.get("dataset") or {}
    path = _resolve(root, str(dataset.get("examples_path") or ""))
    if not path.is_file():
        raise TrainingCorpusError("examples file is missing")
    expected = str(dataset.get("examples_sha256") or "")
    if _sha(path) != expected:
        raise TrainingCorpusError("examples hash drift")
    rows = [item for item in _rows(path) if item["component_type"] == component]
    if not rows:
        raise TrainingCorpusError("component has no examples")
    by_family: dict[str, set[str]] = {}
    for row in rows:
        by_family.setdefault(row["family_id"], set()).add(row["split"])
    conflicts = {family: splits for family, splits in by_family.items() if len(splits) > 1}
    if conflicts:
        raise TrainingCorpusError(f"family split contamination: {sorted(conflicts)}")
    counts = {split: sum(item["split"] == split for item in rows) for split in ("train", "calibration", "held_out")}
    if counts["train"] < 1 or counts["calibration"] < 1:
        raise TrainingCorpusError("train and calibration examples are required")
    if counts["held_out"]:
        raise TrainingCorpusError("held-out examples are disabled during component training")
    return {"manifest_valid": True, "ready": True, "component": component, "examples": len(rows), "split_counts": counts, "examples_sha256": expected}


def _text(row: dict[str, Any]) -> str:
    return json.dumps(row["input"], ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _train_router(rows: list[dict[str, Any]], output: Path, seed: int) -> dict[str, float]:
    from sklearn.feature_extraction import DictVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import accuracy_score, log_loss

    def flatten(row: dict[str, Any]) -> dict[str, float]:
        features: dict[str, float] = {}
        for key, value in row["input"].items():
            if isinstance(value, bool):
                features[key] = float(value)
            elif isinstance(value, (int, float)):
                features[key] = float(value)
            elif isinstance(value, str):
                features[f"{key}={value}"] = 1.0
        return features

    train = [item for item in rows if item["split"] == "train"]
    development = [item for item in rows if item["split"] == "calibration"]
    vectorizer = DictVectorizer(sparse=True)
    x_train = vectorizer.fit_transform([flatten(item) for item in train])
    y_train = [item["target"]["label"] for item in train]
    model = LogisticRegression(random_state=seed, max_iter=1000, class_weight="balanced")
    model.fit(x_train, y_train)
    x_dev = vectorizer.transform([flatten(item) for item in development])
    y_dev = [item["target"]["label"] for item in development]
    prediction = model.predict(x_dev)
    probabilities = model.predict_proba(x_dev)
    with (output / "router.pkl").open("wb") as handle:
        pickle.dump({"model": model, "vectorizer": vectorizer}, handle)
    return {"development_accuracy": float(accuracy_score(y_dev, prediction)), "development_log_loss": float(log_loss(y_dev, probabilities, labels=[0, 1]))}


def _train_encoder(job: dict[str, Any], rows: list[dict[str, Any]], output: Path) -> tuple[dict[str, float], int]:
    import torch
    from sklearn.metrics import accuracy_score, f1_score
    from torch.utils.data import DataLoader, TensorDataset
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if device.type != "cuda":
        raise TrainingCorpusError("CUDA is required for encoder training")
    tokenizer = AutoTokenizer.from_pretrained(job["model"]["repository_id"], revision=job["model"]["tokenizer_revision"])
    model = AutoModelForSequenceClassification.from_pretrained(job["model"]["repository_id"], revision=job["model"]["revision"], num_labels=2).to(device)

    def loader(split: str, shuffle: bool) -> DataLoader:
        selected = [item for item in rows if item["split"] == split]
        encoded = tokenizer([_text(item) for item in selected], padding=True, truncation=True, max_length=512, return_tensors="pt")
        labels = torch.tensor([item["target"]["label"] for item in selected], dtype=torch.long)
        dataset = TensorDataset(encoded["input_ids"], encoded["attention_mask"], labels)
        return DataLoader(dataset, batch_size=int(job["optimization"]["batch_size"]), shuffle=shuffle)

    train_loader = loader("train", True)
    development_loader = loader("calibration", False)
    optimizer = torch.optim.AdamW(model.parameters(), lr=float(job["optimization"]["learning_rate"]), weight_decay=float(job["optimization"]["weight_decay"]))
    use_bf16 = job["optimization"]["precision"] == "bf16"
    torch.cuda.reset_peak_memory_stats()
    model.train()
    for _ in range(int(job["optimization"]["epochs"])):
        for input_ids, attention_mask, labels in train_loader:
            optimizer.zero_grad(set_to_none=True)
            with torch.autocast(device_type="cuda", dtype=torch.bfloat16, enabled=use_bf16):
                loss = model(input_ids=input_ids.to(device), attention_mask=attention_mask.to(device), labels=labels.to(device)).loss
            loss.backward()
            optimizer.step()
    model.eval()
    truth: list[int] = []
    predicted: list[int] = []
    with torch.no_grad():
        for input_ids, attention_mask, labels in development_loader:
            logits = model(input_ids=input_ids.to(device), attention_mask=attention_mask.to(device)).logits
            predicted.extend(logits.argmax(dim=-1).cpu().tolist())
            truth.extend(labels.tolist())
    final = output / "final"
    final.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(final, safe_serialization=True)
    tokenizer.save_pretrained(final)
    peak = int(torch.cuda.max_memory_allocated())
    return {"development_accuracy": float(accuracy_score(truth, predicted)), "development_f1": float(f1_score(truth, predicted, zero_division=0))}, peak


def _hash_tree(root: Path) -> dict[str, str]:
    return {path.relative_to(root).as_posix(): _sha(path) for path in sorted(root.rglob("*")) if path.is_file()}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("job", type=Path)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    try:
        job = json.loads(args.job.read_text(encoding="utf-8"))
        validate_document(job, "component_training_job")
        report = validate_question_synthesis_job(job, args.root)
        if args.validate_only:
            print(json.dumps(report, indent=2))
            return 0
        seed = int(job["seed"])
        random.seed(seed)
        os.environ["PYTHONHASHSEED"] = str(seed)
        examples_path = _resolve(args.root, job["dataset"]["examples_path"])
        rows = [item for item in _rows(examples_path) if item["component_type"] == job["component"]]
        output = _resolve(args.root, job["output"]["root"])
        output.mkdir(parents=True, exist_ok=False)
        started = time.monotonic()
        if job["component"] == "risk_cost_router":
            metrics = _train_router(rows, output, seed)
            peak_gpu = 0
        else:
            metrics, peak_gpu = _train_encoder(job, rows, output)
        elapsed = time.monotonic() - started
        receipt = {
            "schema_version": "1.0",
            "job_id": job["job_id"],
            "component": job["component"],
            "execution_state": "completed",
            "elapsed_seconds": elapsed,
            "examples_per_second": len(rows) / elapsed if elapsed else 0.0,
            "peak_gpu_memory_bytes": peak_gpu,
            "peak_host_rss_kib": _peak_rss_kib(),
            "metrics": metrics,
            "input_examples_sha256": job["dataset"]["examples_sha256"],
            "checkpoint_hashes": _hash_tree(output),
        }
        atomic_write_json(output / "execution-receipt.json", receipt)
        print(json.dumps(receipt, indent=2))
        return 0
    except (OSError, ValueError, json.JSONDecodeError, TrainingCorpusError) as exc:
        print(json.dumps({"execution_state": "failed_before_training", "error": str(exc)}, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
