#!/usr/bin/env python3
"""Add explicit biomedical context to a readable legacy review project."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from init_review import draft_biomedical_context
from metawingman_core.state_store import EventLedger, atomic_write_json


CONTEXT_RELATIVE_PATH = Path("01_protocol/biomedical_context.json")
PROFILE_RELATIVE_PATH = Path("01_protocol/review_profile.json")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_existing_project(project: Path) -> tuple[bool, str]:
    completed = subprocess.run(
        [sys.executable, str(Path(__file__).with_name("validate_project.py")), str(project)],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode == 0:
        return True, ""
    try:
        report = json.loads(completed.stdout)
        detail = "; ".join(report.get("issues", []))
    except json.JSONDecodeError:
        detail = completed.stderr.strip() or completed.stdout.strip()
    return False, detail or "project validation failed"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path)
    parser.add_argument(
        "--specialty",
        action="append",
        help="Declared specialty ID; repeat for secondary specialties",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--created-at-utc", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if not args.specialty:
        parser.error("--specialty is required")

    project = args.project.expanduser().resolve()
    context_path = project / CONTEXT_RELATIVE_PATH
    if context_path.exists():
        print(
            f"Refusing to overwrite existing biomedical context: {context_path}",
            file=sys.stderr,
        )
        return 2
    valid, validation_error = validate_existing_project(project)
    if not valid:
        print(f"Existing project is not valid: {validation_error}", file=sys.stderr)
        return 1

    profile_path = project / PROFILE_RELATIVE_PATH
    try:
        profile = json.loads(profile_path.read_text(encoding="utf-8"))
        now = args.created_at_utc or datetime.now(timezone.utc).isoformat()
        context = draft_biomedical_context(
            f"{profile['profile_id']}-biomedical-context",
            profile["review_family"],
            args.specialty,
            now,
            specialty_was_declared=True,
        )
    except (OSError, KeyError, ValueError) as exc:
        print(f"Cannot prepare biomedical migration: {exc}", file=sys.stderr)
        return 2

    if args.dry_run:
        print(json.dumps(context, indent=2, ensure_ascii=False))
        return 0

    profile_hash = sha256_file(profile_path)
    try:
        atomic_write_json(context_path, context, "biomedical_context")
        context_hash = sha256_file(context_path)
        event = {
            "schema_version": "1.0",
            "event_id": f"biomedical-context-migration:{context_hash[:16]}",
            "idempotency_key": f"biomedical-context-migration:{profile_hash}:{context_hash}",
            "timestamp_utc": now,
            "action_type": "biomedical_context_migrated",
            "actor": {"type": "tool", "id": "migrate_biomedical_context", "version": "1.0"},
            "status": "completed",
            "input": {
                "sha256": profile_hash,
                "media_type": "application/json",
                "reference": PROFILE_RELATIVE_PATH.as_posix(),
            },
            "output": {
                "sha256": context_hash,
                "media_type": "application/json",
                "reference": CONTEXT_RELATIVE_PATH.as_posix(),
            },
            "execution": {
                "prompt_sha256": None,
                "retry_count": 0,
                "retry_budget": 0,
                "latency_ms": 0,
                "cost_usd": 0,
            },
            "evidence_anchor_ids": [],
            "reason_codes": ["explicit_specialty_declaration"],
            "previous_event_hash": None,
            "event_hash": "0" * 64,
        }
        append_result = EventLedger(project / "00_admin/event_ledger.jsonl").append(event)
        if not append_result.appended:
            raise ValueError("migration event idempotency key already exists")
    except Exception as exc:
        context_path.unlink(missing_ok=True)
        print(f"Biomedical migration failed: {exc}", file=sys.stderr)
        return 1

    print(
        json.dumps(
            {
                "status": "migrated",
                "context": str(context_path),
                "profile_sha256": profile_hash,
                "context_sha256": context_hash,
                "event_id": append_result.event["event_id"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
