#!/usr/bin/env python3
"""Export family/time-safe question-synthesis examples and immutable component jobs."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from metawingman_core.question_synthesis_training import COMPONENT_TASKS, export_question_synthesis_examples
from metawingman_core.schema_guard import validate_document
from metawingman_core.state_store import atomic_write_json, canonical_json


ROOT = Path(__file__).resolve().parents[2]
MODEL_ID = "microsoft/BiomedNLP-BiomedBERT-base-uncased-abstract-fulltext"
MODEL_REVISION = "e1354b7a3a09615f6aba48dfad4b7a613eef7062"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _relative(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _job(component: str, examples: list[dict[str, Any]], examples_path: Path, jobs_root: Path, root: Path, created_at_utc: str) -> dict[str, Any]:
    rows = [item for item in examples if item["component_type"] == component]
    train = sum(item["split"] == "train" for item in rows)
    development = sum(item["split"] == "calibration" for item in rows)
    lock = ROOT / "metawingman" / "references" / "dependencies" / "python-training.lock.txt"
    model = {
        "repository_id": MODEL_ID if component != "risk_cost_router" else "scikit-learn/logistic-regression",
        "revision": MODEL_REVISION if component != "risk_cost_router" else "1.9.0",
        "tokenizer_revision": MODEL_REVISION if component != "risk_cost_router" else "1.9.0",
        "model_card_url": "https://huggingface.co/" + MODEL_ID if component != "risk_cost_router" else "https://scikit-learn.org/stable/modules/linear_model.html",
        "declared_license": "MIT" if component != "risk_cost_router" else "BSD-3-Clause",
        "release_intent": "internal_research_only",
    }
    path_string = _relative(examples_path, root)
    sha = _sha(examples_path)
    job = {
        "schema_version": "1.0",
        "job_id": f"question-synthesis-{component}",
        "created_at_utc": created_at_utc,
        "component": component,
        "status": "ready_for_server_preflight" if train and development else "blocked",
        "reason_codes": [] if train and development else ["train_or_calibration_split_missing"],
        "model": model,
        "dataset": {
            "run_plan_path": path_string,
            "run_plan_sha256": sha,
            "examples_path": path_string,
            "examples_sha256": sha,
            "pairs_path": path_string,
            "pairs_sha256": sha,
            "train_examples": train,
            "development_examples": development,
            "train_pairs": train,
            "development_pairs": development,
            "family_isolation": True,
            "label_policy": "weak_candidates_not_gold",
            "release_status": "raw_text_redistribution_forbidden_weights_pending_license_review"
        },
        "optimization": {
            "epochs": 2,
            "batch_size": 8,
            "gradient_accumulation_steps": 1,
            "learning_rate": 2e-5 if component != "risk_cost_router" else 0.001,
            "weight_decay": 0.01,
            "warmup_ratio": 0.1,
            "precision": "bf16" if component != "risk_cost_router" else "fp32",
            "selection_metric": {"question_method_ranker": "pairwise_accuracy", "source_support_verifier": "verifier_f1", "risk_cost_router": "bounded_loss"}[component]
        },
        "resources": {"cpu_cores": 8, "ram_gib": 32, "gpu_count": 0 if component == "risk_cost_router" else 1, "gpu_memory_gib_each": 0 if component == "risk_cost_router" else 24, "storage_gib": 20, "network_required": component != "risk_cost_router"},
        "output": {"root": f"validation-output/question-synthesis-training/{component}", "checkpoint_every_steps": 100, "maximum_checkpoints": 2, "resume_checkpoint_hashes": []},
        "runtime": {"lock_path": _relative(lock, root), "lock_sha256": _sha(lock), "python": "3.12", "cuda_required": component != "risk_cost_router"},
        "seed": 20260820,
        "command_argv": ["python", "metawingman/scripts/train_question_synthesis_component.py", _relative(jobs_root / f"{component}.json", root), "--root", "."]
    }
    validate_document(job, "component_training_job")
    return job


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", action="append", type=Path, required=True)
    parser.add_argument("--trajectories", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--jobs-out", type=Path, required=True)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--created-at-utc")
    args = parser.parse_args()
    timestamp = args.created_at_utc or datetime.now(timezone.utc).isoformat()
    cases = [json.loads(path.read_text(encoding="utf-8")) for path in args.case]
    trajectories = [] if args.trajectories is None else json.loads(args.trajectories.read_text(encoding="utf-8"))
    manifest = export_question_synthesis_examples(cases, trajectories, created_at_utc=timestamp)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(b"".join(canonical_json(item) + b"\n" for item in manifest["examples"]))
    manifest_path = args.out.with_suffix(".manifest.json")
    atomic_write_json(manifest_path, {key: value for key, value in manifest.items() if key != "examples"} | {"examples_path": _relative(args.out, args.root)})
    args.jobs_out.mkdir(parents=True, exist_ok=True)
    jobs = [_job(component, manifest["examples"], args.out, args.jobs_out, args.root, timestamp) for component in COMPONENT_TASKS]
    for job in jobs:
        atomic_write_json(args.jobs_out / f"{job['component']}.json", job, "component_training_job")
    print(json.dumps({"examples": len(manifest["examples"]), "examples_sha256": _sha(args.out), "jobs": [{"job_id": item["job_id"], "status": item["status"]} for item in jobs]}, indent=2))
    return 0 if all(item["status"] == "ready_for_server_preflight" for item in jobs) else 2


if __name__ == "__main__":
    raise SystemExit(main())
