#!/usr/bin/env python3
"""Build a non-final estimand alignment and poolability matrix."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from metawingman_core.poolability import PoolabilityError, build_poolability_matrix


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    try:
        output = build_poolability_matrix(json.loads(args.candidate.read_text(encoding="utf-8")))
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    except (OSError, json.JSONDecodeError, PoolabilityError) as exc:
        print(json.dumps({"built": False, "error": str(exc)}, indent=2))
        return 1
    print(json.dumps({"built": True, "status": output["status"], "out": str(args.out)}, indent=2))
    return 0 if output["status"] == "ready_for_adjudication" else 2


if __name__ == "__main__":
    raise SystemExit(main())
