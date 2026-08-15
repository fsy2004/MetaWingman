#!/usr/bin/env python3
"""Freeze an explicit bounded-component training job without contacting a model hub."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from metawingman_core.state_store import atomic_write_json
from metawingman_core.training_corpus import (
    TrainingCorpusError,
    build_component_training_job,
    sha256_file,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_plan", type=Path)
    parser.add_argument("--component", choices=("section_role_classification", "evidence_retrieval"), required=True)
    parser.add_argument("--model-repository", required=True)
    parser.add_argument("--model-revision", required=True)
    parser.add_argument("--tokenizer-revision", required=True)
    parser.add_argument("--model-card-url", required=True)
    parser.add_argument("--model-license", required=True)
    parser.add_argument("--runtime-lock", type=Path, required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--learning-rate", type=float, default=2e-5)
    parser.add_argument("--weight-decay", type=float, default=0.01)
    parser.add_argument("--warmup-ratio", type=float, default=0.1)
    parser.add_argument("--precision", choices=("fp32", "fp16", "bf16"), default="bf16")
    parser.add_argument("--checkpoint-every-steps", type=int, default=250)
    parser.add_argument("--maximum-checkpoints", type=int, default=3)
    parser.add_argument("--cpu-cores", type=int, default=16)
    parser.add_argument("--ram-gib", type=int, default=64)
    parser.add_argument("--gpu-count", type=int, default=1)
    parser.add_argument("--gpu-memory-gib-each", type=int, default=24)
    parser.add_argument("--storage-gib", type=int, default=500)
    parser.add_argument("--seed", type=int, default=20260815)
    parser.add_argument("--created-at-utc")
    args = parser.parse_args()
    try:
        run_plan = json.loads(args.run_plan.read_text(encoding="utf-8"))
        now = args.created_at_utc or datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        selection_metric = "macro_f1" if args.component == "section_role_classification" else "retrieval_recall_at_10"
        job = build_component_training_job(
            run_plan,
            args.component,
            {
                "repository_id": args.model_repository,
                "revision": args.model_revision,
                "tokenizer_revision": args.tokenizer_revision,
                "model_card_url": args.model_card_url,
                "declared_license": args.model_license,
                "release_intent": "internal_research_only",
            },
            {
                "epochs": args.epochs,
                "batch_size": args.batch_size,
                "learning_rate": args.learning_rate,
                "weight_decay": args.weight_decay,
                "warmup_ratio": args.warmup_ratio,
                "precision": args.precision,
                "selection_metric": selection_metric,
                "checkpoint_every_steps": args.checkpoint_every_steps,
                "maximum_checkpoints": args.maximum_checkpoints,
            },
            {
                "cpu_cores": args.cpu_cores,
                "ram_gib": args.ram_gib,
                "gpu_count": args.gpu_count,
                "gpu_memory_gib_each": args.gpu_memory_gib_each,
                "storage_gib": args.storage_gib,
                "network_required": True,
            },
            now,
            run_plan_path=args.run_plan.as_posix(),
            run_plan_sha256=sha256_file(args.run_plan),
            job_path=args.out.as_posix(),
            output_root=args.output_root,
            runtime_lock_path=args.runtime_lock.as_posix(),
            runtime_lock_sha256=sha256_file(args.runtime_lock),
            seed=args.seed,
        )
        atomic_write_json(args.out, job, "component_training_job")
    except (OSError, json.JSONDecodeError, TrainingCorpusError, ValueError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        return 1
    print(json.dumps({"ok": True, "out": str(args.out), "status": job["status"], "reason_codes": job["reason_codes"]}, indent=2))
    return 0 if job["status"] == "ready_for_server_preflight" else 2


if __name__ == "__main__":
    raise SystemExit(main())
