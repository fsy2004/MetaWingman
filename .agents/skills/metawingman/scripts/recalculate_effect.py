#!/usr/bin/env python3
"""Recompute one effect estimate from accepted extraction-candidate JSONL."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from metawingman_core.effect_recalculator import EffectCalculationError, calculate_effect


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("candidates", type=Path)
    parser.add_argument("--effect-id", required=True)
    parser.add_argument("--result-id", required=True)
    parser.add_argument("--measure", choices=("log_risk_ratio", "log_odds_ratio", "risk_difference", "mean_difference", "standardized_mean_difference", "fisher_z", "logit_proportion"), required=True)
    parser.add_argument("--direction", choices=("higher_favors_intervention", "lower_favors_intervention", "higher_is_harm", "lower_is_harm", "descriptive", "other"), required=True)
    parser.add_argument("--confidence-level", type=float, default=0.95)
    parser.add_argument("--continuity-correction", type=float)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    try:
        candidates = [json.loads(line) for line in args.candidates.read_text(encoding="utf-8").splitlines() if line.strip()]
        output = calculate_effect(
            candidates,
            effect_id=args.effect_id,
            result_id=args.result_id,
            measure=args.measure,
            direction=args.direction,
            confidence_level=args.confidence_level,
            continuity_correction=args.continuity_correction,
        )
    except (OSError, json.JSONDecodeError, EffectCalculationError) as exc:
        print(json.dumps({"calculated": False, "error": str(exc)}, indent=2))
        return 1
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(output, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
