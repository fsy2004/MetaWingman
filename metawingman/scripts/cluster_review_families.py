#!/usr/bin/env python3
"""Generate a conservative review-family candidate registry from a corpus intake."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from metawingman_core.review_family import ReviewFamilyError, build_review_family_registry


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("corpus", type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    try:
        corpus = json.loads(args.corpus.read_text(encoding="utf-8"))
        registry = build_review_family_registry(corpus, source_path=args.corpus.as_posix())
    except (OSError, json.JSONDecodeError, ReviewFamilyError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, indent=2))
        return 1
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(registry, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(registry["summary"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
