#!/usr/bin/env python3
"""Evaluate frozen question-synthesis run records against sealed references."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from metawingman_core.question_synthesis_evaluator import aggregate_question_benchmark, evaluate_question_portfolio, validate_family_isolation
from metawingman_core.state_store import atomic_write_json


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    args = parser.parse_args()
    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    cases = [json.loads(Path(path).read_text(encoding="utf-8")) for path in plan["cases"]]
    runs = [json.loads(Path(path).read_text(encoding="utf-8")) for path in plan["runs"]]
    validate_family_isolation(cases)
    case_index = {item["case_id"]: item for item in cases}
    reports = [evaluate_question_portfolio(case_index[item["case_id"]], item) for item in runs]
    result = {"reports": reports, "aggregate": aggregate_question_benchmark(reports)}
    output = Path(plan["output"])
    atomic_write_json(output, result)
    print(json.dumps({"runs": len(reports), "output": str(output), **result["aggregate"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
