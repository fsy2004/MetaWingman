#!/usr/bin/env python3
"""Materialize a metadata-only local-to-server training handoff."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from metawingman_core.server_handoff import materialize_server_handoff
from metawingman_core.training_corpus import TrainingCorpusError


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, default=Path.cwd())
    parser.add_argument("--plan", required=True)
    parser.add_argument("--job", action="append", required=True)
    parser.add_argument("--preflight", action="append", required=True)
    parser.add_argument("--lock", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--handoff-id", default="metawingman-biomedical-training-v2")
    parser.add_argument("--storage-estimate-gib", type=int, default=500)
    parser.add_argument("--created-at-utc")
    args = parser.parse_args()
    try:
        root = args.source_root.resolve()
        members = [args.plan, args.lock, *args.job, *args.preflight]
        members.extend([
            "metawingman/schemas/training_corpus_plan.schema.json",
            "metawingman/schemas/training_pair.schema.json",
            "metawingman/schemas/training_run_plan.schema.json",
            "metawingman/schemas/component_training_job.schema.json",
            "metawingman/schemas/server_training_handoff.schema.json",
        ])
        jobs = [json.loads((root / path).read_text(encoding="utf-8")) for path in args.job]
        reports = [json.loads((root / path).read_text(encoding="utf-8")) for path in args.preflight]
        blockers = sorted({code for report in reports for code in report.get("scientific_blockers", [])})
        pending = sorted({code for report in reports for code in report.get("server_checks_pending", [])})
        commands = {
            "download": ["metawingman/scripts/fetch_training_corpus.py", "training-corpus-plan-biomedical-v2.json", "--out", "documents"],
            "freeze": ["metawingman/scripts/freeze_training_dataset.py", "documents/training-document-manifest.json", "--artifact-root", "documents"],
            "audit": ["metawingman/scripts/audit_training_dataset.py", "--plan", "training-corpus-plan-biomedical-v2.json"],
            "export": ["metawingman/scripts/export_training_splits.py", "training-examples.jsonl", "--training-plan", "training-corpus-plan-biomedical-v2.json"],
            "preflight": ["metawingman/scripts/preflight_component_training.py", "jobs/evidence-retrieval.json", "--root", ".", "--inspect-server"],
            "train": ["metawingman/scripts/run_component_training.py", "jobs/evidence-retrieval.json", "--root", "."],
            "benchmark": ["metawingman/scripts/evaluate_pipeline.py", "--help"],
        }
        now = args.created_at_utc or datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        manifest = materialize_server_handoff(
            root,
            args.out,
            members,
            {
                "handoff_id": args.handoff_id,
                "created_at_utc": now,
                "component_job_ids": [job["job_id"] for job in jobs],
                "preflight": {"scientific_blockers": blockers, "server_checks_pending": pending},
                "storage_estimate_gib": args.storage_estimate_gib,
                "commands": commands,
            },
        )
    except (OSError, json.JSONDecodeError, TrainingCorpusError, ValueError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2)); return 1
    print(json.dumps({"ok": True, "out": str(args.out), "status": manifest["status"], "members": len(manifest["members"]), "server_only_pending": manifest["server_only_pending"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
