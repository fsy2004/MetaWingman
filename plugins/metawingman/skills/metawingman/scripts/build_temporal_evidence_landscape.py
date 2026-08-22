#!/usr/bin/env python3
"""Build a target-free historical topic landscape from a frozen JSONL corpus."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

try:
    from metawingman_core.landscape_builder import LandscapeBuildError, build_broad_temporal_landscape
except ModuleNotFoundError:  # package import during tests
    from .metawingman_core.landscape_builder import LandscapeBuildError, build_broad_temporal_landscape


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    """Read physical JSONL records without treating U+2028/U+2029 as delimiters."""
    return [json.loads(line) for line in path.read_text(encoding="utf-8").split("\n") if line.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("records", type=Path)
    parser.add_argument("spec", type=Path)
    parser.add_argument("forbidden_identity_patterns", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--created-at-utc")
    args = parser.parse_args()
    try:
        records = _read_jsonl(args.records)
        spec = json.loads(args.spec.read_text(encoding="utf-8"))
        forbidden = json.loads(args.forbidden_identity_patterns.read_text(encoding="utf-8"))
        result = build_broad_temporal_landscape(
            records, spec, forbidden["patterns"],
            created_at_utc=args.created_at_utc or datetime.now(timezone.utc).isoformat(),
        )
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError, LandscapeBuildError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}))
        return 1
    print(json.dumps({"status": "completed", "out": str(args.out), "audit": result["build_audit"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
