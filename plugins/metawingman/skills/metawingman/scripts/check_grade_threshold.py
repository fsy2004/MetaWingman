#!/usr/bin/env python3
"""Locate a confidence interval against a prespecified decision threshold."""

from __future__ import annotations

import argparse
import json

from metawingman_core.judgment_workbench import JudgmentWorkbenchError, locate_interval_against_threshold


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--estimate", type=float, required=True)
    parser.add_argument("--ci-lower", type=float, required=True)
    parser.add_argument("--ci-upper", type=float, required=True)
    parser.add_argument("--threshold", type=float, required=True)
    args = parser.parse_args()
    try:
        output = locate_interval_against_threshold(args.estimate, args.ci_lower, args.ci_upper, args.threshold)
    except JudgmentWorkbenchError as exc:
        print(json.dumps({"checked": False, "error": str(exc)}, indent=2))
        return 1
    print(json.dumps(output, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
