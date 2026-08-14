#!/usr/bin/env python3
"""Evaluate a single-change protocol stress test and intervention replay."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from metawingman_core.causal_replay import CausalReplayError, evaluate_causal_replay


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    try:
        case = json.loads(args.case.read_text(encoding="utf-8"))
        report = evaluate_causal_replay(case)
    except (OSError, json.JSONDecodeError, CausalReplayError) as exc:
        print(json.dumps({"valid_case": False, "error": str(exc)}, indent=2))
        return 1
    payload = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")
    if not report["valid_case"]:
        return 1
    return 0 if report["protocol_adherence_status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
