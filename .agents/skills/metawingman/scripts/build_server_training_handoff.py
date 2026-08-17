#!/usr/bin/env python3
"""Materialize a metadata-only local-to-server training handoff."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from metawingman_core.server_handoff import build_server_commands, materialize_server_handoff
from metawingman_core.schema_guard import validate_document
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
        plan = json.loads((root / args.plan).read_text(encoding="utf-8"))
        validate_document(plan, "training_corpus_plan")
        jobs = [json.loads((root / path).read_text(encoding="utf-8")) for path in args.job]
        for job in jobs:
            validate_document(job, "component_training_job")
        reports = [json.loads((root / path).read_text(encoding="utf-8")) for path in args.preflight]
        allowed_report_keys = {
            "manifest_valid", "ready", "training_started", "reason_codes",
            "scientific_blockers", "server_checks_pending",
        }
        if any(set(report) != allowed_report_keys for report in reports):
            raise TrainingCorpusError("preflight report has unexpected or missing fields")
        blockers = sorted({code for report in reports for code in report.get("scientific_blockers", [])})
        pending = sorted({code for report in reports for code in report.get("server_checks_pending", [])})
        job_paths = dict(zip((job["component"] for job in jobs), args.job))
        evidence_job = job_paths.get("evidence_retrieval")
        if not evidence_job:
            raise TrainingCorpusError("evidence_retrieval job is required for server handoff commands")
        commands = build_server_commands(args.plan, evidence_job)
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
