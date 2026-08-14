#!/usr/bin/env python3
"""Aggregate scored AI-only repeated-run benchmark JSONL records."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from metawingman_core.ai_only_evaluator import AIOnlyEvaluationError, aggregate_ai_only_runs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("runs", type=Path, help="JSONL file of ai_only_run_record objects")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    try:
        plan = json.loads(args.plan.read_text(encoding="utf-8"))
        records = [
            json.loads(line) for line in args.runs.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        result = aggregate_ai_only_runs(plan, records)
    except (OSError, json.JSONDecodeError, AIOnlyEvaluationError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        return 1
    text = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
