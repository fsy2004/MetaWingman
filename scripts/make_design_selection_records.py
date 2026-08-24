#!/usr/bin/env python3
"""Build a small demo records.json (family-tagged records) from the gold fixture.

This lets the CLI's real-landscape path (--records) run on the same 11 cases by
constructing one record per case whose fields reproduce the gold landscape
signals. It is a *demonstration* corpus — a real corpus would come from an
extraction pipeline. Run it to regenerate research/records-by-family-demo.json.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from metawingman.benchmark.gold_loader import load_gold

REPO = Path(__file__).resolve().parents[1]
GOLD = REPO / "research" / "design-selection-gold-v1.json"
OUT = REPO / "research" / "records-by-family-demo.json"


def main() -> int:
    gold = load_gold(GOLD)
    records_by_family: dict[str, list[dict]] = {}
    for case in gold:
        frame = case.question
        land = case.landscape
        record: dict = {"review_family_id": case.case_id}
        if frame.get("intervention_count"):
            record["intervention_count"] = int(frame["intervention_count"])
        if land.get("comparator_count"):
            record["comparator_count"] = int(land["comparator_count"])
        if land.get("has_reference_standard"):
            record["has_reference_standard"] = True
        if land.get("has_prediction_model"):
            record["has_prediction_model"] = True
        if land.get("outcome_unit"):
            record["outcome_unit"] = land["outcome_unit"]
        if land.get("is_update") or frame.get("is_living_or_update"):
            record["is_update"] = True
        if land.get("exposure_outcome_design"):
            record["exposure_outcome_design"] = land["exposure_outcome_design"]
        if land.get("n_nodes_assessed"):
            record["node_coverage_checked"] = True
        records_by_family[case.case_id] = [record]
    OUT.write_text(json.dumps(records_by_family, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT} ({len(records_by_family)} families)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
