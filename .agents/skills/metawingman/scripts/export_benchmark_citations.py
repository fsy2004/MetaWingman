#!/usr/bin/env python3
"""Export benchmark discovery identities for the citation verification CLI."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("catalog", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    catalog = json.loads(args.catalog.read_text(encoding="utf-8"))
    rows = [
        {
            "candidate_id": item["candidate_id"],
            "title": item["title"],
            "doi": item["publication"]["doi"],
            "pmid": "",
        }
        for item in catalog["candidates"]
    ]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=["candidate_id", "title", "doi", "pmid"]
        )
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps({"exported": len(rows), "output": str(args.output)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
