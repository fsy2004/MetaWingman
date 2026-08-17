#!/usr/bin/env python3
"""Apply frozen MetaWingman criteria to one structured record."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from metawingman_core.screening_engine import ScreeningError, screen_record


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("criteria", type=Path)
    parser.add_argument("record", type=Path)
    parser.add_argument("--stage", choices=("title_abstract", "full_text"), required=True)
    parser.add_argument("--confidence-floor", type=float, default=0.8)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    try:
        assessment = screen_record(
            json.loads(args.criteria.read_text(encoding="utf-8")),
            json.loads(args.record.read_text(encoding="utf-8")),
            stage=args.stage,
            confidence_floor=args.confidence_floor,
        )
    except (OSError, json.JSONDecodeError, ScreeningError) as exc:
        print(json.dumps({"screened": False, "error": str(exc)}, indent=2))
        return 1
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(assessment, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(assessment, indent=2, ensure_ascii=False))
    return 0 if assessment["policy_decision"]["recommendation"] != "abstain" else 2


if __name__ == "__main__":
    raise SystemExit(main())
