#!/usr/bin/env python3
"""Build a bounded proposal subgraph and an auditable sidecar receipt."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from metawingman_core.topic_proposal_subgraph import (
    TopicProposalSubgraphError,
    build_topic_proposal_subgraph,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("landscape", type=Path)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--maximum-publications", type=int, default=240)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--created-at-utc")
    args = parser.parse_args()
    try:
        landscape = json.loads(args.landscape.read_text(encoding="utf-8"))
        result = build_topic_proposal_subgraph(
            landscape,
            seed=args.seed,
            maximum_publications=args.maximum_publications,
            created_at_utc=args.created_at_utc or datetime.now(timezone.utc).isoformat(),
        )
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result["landscape"], indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
        args.receipt.write_text(json.dumps(result["audit"], indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError, TopicProposalSubgraphError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}))
        return 1
    print(json.dumps({"status": "completed", "out": str(args.out), "audit": result["audit"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
