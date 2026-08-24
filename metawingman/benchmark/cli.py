#!/usr/bin/env python3
"""Benchmark CLI: evidence-landscape -> design-selection against frozen gold.

Runs the design-selection skill against a gold case set (and optional baselines)
and writes a deterministic JSON report plus a console summary. This is the local
/ server-shared entry point for producing the reported numbers; it does not call
any model and is fully reproducible from the same inputs.

Examples
--------
  # curated-signal path (gold carries landscape signals directly)
  python -m metawingman.benchmark.cli --gold research/design-selection-gold-v1.json

  # real-landscape path (signals are built from family-tagged records)
  python -m metawingman.benchmark.cli --gold research/design-selection-gold-v1.json \
      --records research/records-by-family.json

  # add an extra fixed-profile baseline
  python -m metawingman.benchmark.cli --gold research/design-selection-gold-v1.json \
      --baselines intervention_pairwise intervention_network diagnostic_accuracy
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from metawingman.benchmark.gold_loader import load_gold, gold_to_eval_rows
from metawingman.benchmark.landscape_builder import build_gold_signals
from metawingman.scripts.metawingman_core.design_selection import (
    PROFILE_STRATA, derive_review_design)
from metawingman.scripts.metawingman_core.design_selection_eval import (
    evaluate_design_selection, unconditional_baseline)


def _run(
    gold_path: str | Path,
    *,
    records_path: str | Path | None = None,
    baselines: list[str] | None = None,
) -> dict[str, Any]:
    gold = load_gold(gold_path)
    gold_rows = gold_to_eval_rows(gold)

    records_by_family: dict[str, list[dict[str, Any]]] | None = None
    if records_path:
        records_by_family = json.loads(Path(records_path).read_text(encoding="utf-8"))

    signals = build_gold_signals(gold, records_by_family)

    predictions: list[dict[str, Any]] = []
    for case in gold:
        decision = derive_review_design(case.question, signals[case.case_id])
        row = decision.to_dict()
        row["case_id"] = case.case_id
        row["gold_profile"] = case.gold_profile
        row["gold_living"] = case.gold_living
        predictions.append(row)

    # Baselines: default to unconditional fixed-pairwise; allow extras.
    baseline_specs: dict[str, list[dict[str, Any]]] = {
        f"unconditional {p}": unconditional_baseline(p, gold_rows)
        for p in (baselines or ["intervention_pairwise"])
    }
    metrics = evaluate_design_selection(predictions, gold_rows, baselines=baseline_specs)

    return {
        "gold_path": str(gold_path),
        "records_path": str(records_path) if records_path else None,
        "cases": len(gold),
        "source_of_signals": "records" if records_by_family else "gold.landscape",
        "strata_covered": sorted({g.gold_profile for g in gold}),
        "skill": {
            "profile_match_accuracy": metrics["profile_match_accuracy"],
            "macro_over_strata": metrics["macro_over_strata"],
            "living_flag_accuracy": metrics["living_flag_accuracy"],
            "abstain_rate": metrics["abstain_rate"],
            "false_opportunity_rate": metrics["false_opportunity_rate"],
        },
        "baselines": metrics.get("baselines", {}),
        "per_case": [
            {
                "case_id": p["case_id"],
                "gold_profile": p["gold_profile"],
                "predicted_profile": p["profile"] or "abstain",
                "correct": p["profile"] == p["gold_profile"],
                "gold_living": p["gold_living"],
                "predicted_living": p["living"],
                "confidence": p["confidence"],
            }
            for p in predictions
        ],
    }


def _print_summary(report: dict[str, Any]) -> None:
    s = report["skill"]
    b = report["baselines"]
    print(f"design-selection benchmark: {report['cases']} gold cases "
          f"({len(report['strata_covered'])} strata; signals from {report['source_of_signals']})")
    print(f"  skill : profile_match={s['profile_match_accuracy']:.3f}  "
          f"macro={s['macro_over_strata']:.3f}  living={s['living_flag_accuracy']:.3f}  "
          f"abstain={s['abstain_rate']:.3f}  false_opportunity={s['false_opportunity_rate']:.3f}")
    for name, m in b.items():
        print(f"  base  : {name:<32} profile_match={m['profile_match_accuracy']:.3f}  "
              f"abstain={m['abstain_rate']:.3f}")
    worst = [c for c in report["per_case"] if not c["correct"]]
    if worst:
        print(f"  misses ({len(worst)}): " + "; ".join(f"{c['case_id']}: gold={c['gold_profile']} "
              f"pred={c['predicted_profile']}" for c in worst))
    else:
        print("  misses: none")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--gold", required=True, help="path to gold fixture JSON (design-selection-gold-v*.json)")
    parser.add_argument("--records", default=None, help="optional JSON {family_id: [records]} for the real-landscape path")
    parser.add_argument("--baselines", nargs="+", default=["intervention_pairwise"],
                        help="fixed-profile baselines to compare against")
    parser.add_argument("--out", default=None, help="override output report path")
    parser.add_argument("--quiet", action="store_true", help="suppress console summary")
    args = parser.parse_args(argv)

    report = _run(args.gold, records_path=args.records, baselines=args.baselines)
    out_path = Path(args.out) if args.out else (
        Path(args.gold).with_name("design-selection-benchmark-v1.json"))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if not args.quiet:
        _print_summary(report)
    print(f"wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
