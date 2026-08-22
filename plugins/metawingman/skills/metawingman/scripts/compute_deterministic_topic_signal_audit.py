#!/usr/bin/env python3
"""Compute replayable heuristic topic signals from an external-search receipt."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from metawingman_core.deterministic_topic_signal_audit import (
    DeterministicTopicAuditError,
    build_deterministic_topic_signal_audit,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("proposal_batch", type=Path)
    parser.add_argument("landscape", type=Path)
    parser.add_argument("external_search_receipt", type=Path)
    parser.add_argument("--proposal-id", required=True)
    parser.add_argument("--auditor-id", default="ncbi-pubmed-deterministic-topic-audit-v1")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    try:
        batch = json.loads(args.proposal_batch.read_text(encoding="utf-8"))
        matches = [item for item in batch["proposals"] if item.get("proposal_id") == args.proposal_id]
        if len(matches) != 1:
            raise DeterministicTopicAuditError(
                f"proposal_id must match exactly one proposal; found {len(matches)}"
            )
        audit = build_deterministic_topic_signal_audit(
            matches[0],
            json.loads(args.landscape.read_text(encoding="utf-8")),
            json.loads(args.external_search_receipt.read_text(encoding="utf-8")),
            proposal_provider_id=str(batch["model_provenance"]["model"]),
            auditor_id=args.auditor_id,
        )
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(
            json.dumps(audit, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError, DeterministicTopicAuditError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}))
        return 1
    print(json.dumps({"status": "completed", "proposal_id": args.proposal_id, "out": str(args.out)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
