#!/usr/bin/env python3
"""Promote a topic proposal after an independently produced signal audit."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from metawingman_core.topic_signal_audit import (
    TopicSignalAuditError,
    landscape_node_ids,
    promote_proposal_after_independent_audit,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("proposal_batch", type=Path)
    parser.add_argument("audit", type=Path)
    parser.add_argument("landscape", type=Path)
    parser.add_argument("--proposal-id", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--created-at-utc")
    args = parser.parse_args()
    try:
        batch = json.loads(args.proposal_batch.read_text(encoding="utf-8"))
        matches = [
            item for item in batch["proposals"] if item.get("proposal_id") == args.proposal_id
        ]
        if len(matches) != 1:
            raise TopicSignalAuditError(
                f"proposal_id must match exactly one proposal; found {len(matches)}"
            )
        proposal = matches[0]
        proposal_provider_id = str(batch["model_provenance"]["model"])
        audit = json.loads(args.audit.read_text(encoding="utf-8"))
        landscape = json.loads(args.landscape.read_text(encoding="utf-8"))
        node_ids = landscape_node_ids(landscape)
        candidate = promote_proposal_after_independent_audit(
            proposal,
            audit,
            proposal_provider_id=proposal_provider_id,
            landscape_id=str(landscape["landscape_id"]),
            landscape_node_ids=node_ids,
            created_at_utc=args.created_at_utc or datetime.now(timezone.utc).isoformat(),
        )
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(
            json.dumps(candidate, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError, TopicSignalAuditError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}))
        return 1
    print(json.dumps({"status": "completed", "out": str(args.out), "candidate_id": candidate["candidate_id"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
