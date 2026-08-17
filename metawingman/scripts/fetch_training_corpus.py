#!/usr/bin/env python3
"""Fetch licensed OA PDF/XML training documents and record immutable provenance."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from metawingman_core.training_corpus import TrainingCorpusError, fetch_training_plan


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--manifest-id", default="top-journal-oa-documents-v1")
    parser.add_argument("--maximum-records", type=int)
    parser.add_argument("--max-file-bytes", type=int, default=40 * 1024 * 1024)
    parser.add_argument("--max-total-bytes", type=int, default=500 * 1024 * 1024)
    parser.add_argument("--delay-seconds", type=float, default=0.2)
    parser.add_argument("--created-at-utc")
    parser.add_argument("--refresh", action="store_true", help="Ignore verified local artifacts and recheck remote sources.")
    parser.add_argument("--skip-pdf", action="store_true", help="XML-only acquisition; skip OA PDF downloads (training uses JATS XML).")
    parser.add_argument("--request-deadline-seconds", type=float, default=120.0, help="Wall-clock deadline per source request; guards slow-drip endpoints.")
    args = parser.parse_args()
    try:
        plan = json.loads(args.plan.read_text(encoding="utf-8"))
        manifest = fetch_training_plan(
            plan, args.out, manifest_id=args.manifest_id, maximum_records=args.maximum_records,
            max_file_bytes=args.max_file_bytes, max_total_bytes=args.max_total_bytes,
            delay_seconds=args.delay_seconds, created_at_utc=args.created_at_utc,
            reuse_existing=not args.refresh, skip_pdf=args.skip_pdf,
            request_deadline_seconds=args.request_deadline_seconds,
        )
    except (OSError, json.JSONDecodeError, TrainingCorpusError, ValueError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        return 1
    print(json.dumps({"ok": True, "manifest": str(args.out / "training-document-manifest.json"), "summary": manifest["summary"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
