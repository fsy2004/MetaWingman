#!/usr/bin/env python3
"""Build bounded target-independent proposal scaffolds from a frozen landscape."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from metawingman_core.topic_proposal_scaffolds import (
    build_exhaustive_topic_proposal_shards,
    build_topic_proposal_scaffolds,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("landscape", type=Path)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--maximum-scaffolds", type=int, default=4)
    parser.add_argument("--maximum-publications", type=int, default=60)
    parser.add_argument("--exhaustive", action="store_true")
    parser.add_argument("--maximum-shards", type=int, default=100)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--created-at-utc")
    args = parser.parse_args()
    landscape = json.loads(args.landscape.read_text(encoding="utf-8"))
    timestamp = args.created_at_utc or datetime.now(timezone.utc).isoformat()
    if args.exhaustive:
        result = build_exhaustive_topic_proposal_shards(
            landscape, seed=args.seed, maximum_publications=args.maximum_publications,
            maximum_shards=args.maximum_shards, created_at_utc=timestamp,
        )
    else:
        result = build_topic_proposal_scaffolds(
            landscape, seed=args.seed, maximum_scaffolds=args.maximum_scaffolds,
            maximum_publications=args.maximum_publications, created_at_utc=timestamp,
        )
    args.out_dir.mkdir(parents=True, exist_ok=True)
    files = []
    for item in result["scaffolds"]:
        path = args.out_dir / f"{item['scaffold_id']}.json"
        path.write_text(json.dumps(item["landscape"], indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
        receipt = args.out_dir / f"{item['scaffold_id']}.receipt.json"
        receipt.write_text(json.dumps(item["audit"], indent=2, sort_keys=True) + "\n", encoding="utf-8")
        files.append(str(path))
    print(json.dumps({"status": "completed", "scaffolds": len(files), "files": files}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
