#!/usr/bin/env python3
"""Apply a frozen target-independent MeSH construct mapping to topic records."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from metawingman_core.topic_construct_annotation import (  # noqa: E402
    TopicConstructAnnotationError,
    annotate_topic_construct_records,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("records", type=Path)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--created-at-utc")
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    receipt = annotate_topic_construct_records(
        args.records, manifest, output_path=args.out, receipt_path=args.receipt,
        created_at_utc=args.created_at_utc,
    )
    print(json.dumps(receipt, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (TopicConstructAnnotationError, OSError, json.JSONDecodeError) as exc:
        raise SystemExit(str(exc)) from None
