"""Audit log + meta-update loop: record execution lessons, propose
versioned skill updates with sources, and apply them through the human
review window (lifelong-upgrades mechanism; ICLR 2026 lifelong agents).

Usage:
  python metawingman/scripts/record_audit_log.py \
    --log audit.jsonl --stage appraisal --event-type failure \
    --description "unanchored RoB signal" --evidence-source "file:line" \
    --target-file references/socratic-checklists/appraisal.json \
    --section "items/1" --new-text "..." --rationale "..." --source "..."

  # list open proposals and mark one applied:
  python metawingman/scripts/record_audit_log.py --log audit.jsonl --list-open
  python metawingman/scripts/record_audit_log.py --log audit.jsonl --apply <entry_id> --commit abc123
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from metawingman_core.schema_guard import SchemaValidationError, validate_document

SCHEMA = "audit_log_entry"


def build_entry(
    *,
    stage: str,
    event_type: str,
    description: str,
    evidence_source: str | None,
    proposed_update: dict[str, str],
) -> dict[str, Any]:
    fingerprint = hashlib.sha256(
        json.dumps(
            [stage, event_type, description, proposed_update], sort_keys=True, ensure_ascii=False
        ).encode("utf-8")
    ).hexdigest()
    entry: dict[str, Any] = {
        "schema_version": "1.0",
        "entry_id": f"audit:{fingerprint}",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "stage": stage,
        "event_type": event_type,
        "description": description,
        "evidence_source": evidence_source,
        "proposed_update": proposed_update,
        "applied": False,
        "applied_at_utc": None,
        "applied_commit": None,
    }
    validate_document(entry, SCHEMA)
    return entry


def append_entry(path: Path, entry: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


def load_entries(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    entries: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        validate_document(item, SCHEMA)
        entries.append(item)
    return entries


def list_open(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [entry for entry in entries if not entry["applied"]]


def apply_entry(path: Path, entry_id: str, commit: str) -> dict[str, Any]:
    entries = load_entries(path)
    for entry in entries:
        if entry["entry_id"] == entry_id:
            if entry["applied"]:
                raise ValueError(f"entry {entry_id} already applied")
            entry["applied"] = True
            entry["applied_at_utc"] = datetime.now(timezone.utc).isoformat()
            entry["applied_commit"] = commit
            with path.open("w", encoding="utf-8") as handle:
                for item in entries:
                    handle.write(json.dumps(item, ensure_ascii=False) + "\n")
            return entry
    raise ValueError(f"entry {entry_id} not found")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--log", type=Path, default=Path("validation-output/audit-log.jsonl"))
    parser.add_argument("--stage", choices=["topic", "protocol", "search", "screening", "extraction", "appraisal", "analysis", "writing", "review", "update", "meta"])
    parser.add_argument("--event-type", choices=["deviation", "failure", "fix", "reflection", "question_answer", "certificate_update"])
    parser.add_argument("--description")
    parser.add_argument("--evidence-source", default=None)
    parser.add_argument("--target-file", default="")
    parser.add_argument("--section", default="")
    parser.add_argument("--new-text", default="")
    parser.add_argument("--rationale", default="")
    parser.add_argument("--source", default="")
    parser.add_argument("--list-open", action="store_true")
    parser.add_argument("--apply")
    parser.add_argument("--commit", default="")
    args = parser.parse_args()
    try:
        if args.list_open:
            open_entries = list_open(load_entries(args.log))
            print(json.dumps({"open": len(open_entries), "entries": open_entries}, indent=2, ensure_ascii=False))
            return 0
        if args.apply:
            applied = apply_entry(args.log, args.apply, args.commit)
            print(json.dumps(applied, indent=2, ensure_ascii=False))
            return 0
        proposed = {
            "target_file": args.target_file,
            "section": args.section,
            "new_text": args.new_text,
            "rationale": args.rationale,
            "source": args.source,
        }
        entry = build_entry(
            stage=args.stage, event_type=args.event_type, description=args.description,
            evidence_source=args.evidence_source, proposed_update=proposed,
        )
        append_entry(args.log, entry)
        print(json.dumps(entry, indent=2, ensure_ascii=False))
        return 0
    except (OSError, ValueError, json.JSONDecodeError, SchemaValidationError) as exc:
        print(json.dumps({"error": str(exc)}, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
