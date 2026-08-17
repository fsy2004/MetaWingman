#!/usr/bin/env python3
"""Evaluate a compiled pipeline on isolated source-grounded cases."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from metawingman_core.pipeline_evaluator import PipelineEvaluationError, evaluate_pipeline


def _jsonl(path: Path) -> list[dict[str, object]]:
    output = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"{path}:{line_number} is not a JSON object")
        output.append(value)
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("spec", type=Path)
    parser.add_argument("cases", type=Path)
    parser.add_argument("--reliability", type=Path, required=True)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    try:
        spec = json.loads(args.spec.read_text(encoding="utf-8"))
        report = evaluate_pipeline(spec, _jsonl(args.cases), _jsonl(args.reliability))
    except (OSError, json.JSONDecodeError, ValueError, PipelineEvaluationError) as exc:
        print(json.dumps({"release_ready": False, "error": str(exc)}, indent=2))
        return 1
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["release_ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
