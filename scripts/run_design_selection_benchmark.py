#!/usr/bin/env python3
"""Run a minimal 8-strata design-selection comparison (full skill vs fixed-pairwise baseline).

This is a local, deterministic first number: given the representative-case gold
review profile (question -> evidence-structure -> true profile), how often does
the design-selection skill pick the right meta-type compared to a baseline that
always assumes pairwise? 8-strata gold derived from research/direct-evidence-case-registry-v1.json.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from metawingman.scripts.metawingman_core.design_selection import derive_review_design
from metawingman.scripts.metawingman_core.design_selection_eval import (
    evaluate_design_selection,
    unconditional_baseline,
)

# Gold cases: question shape + evidence-structure summary + true review profile.
# Mirrors the representative-case registry (8 strata, 11 cases), each with verified identity+cutoff.
GOLD_CASES = [
    ("bmj-covid-therapies-living-nma", {"type": "intervention", "intervention_count": 8, "is_living_or_update": True},
     {"arms_per_study": 3, "comparator_count": 8, "outcome_unit": "binary", "is_update": True, "n_nodes_assessed": True},
     "intervention_network", True),
    ("nature-psychological-wellbeing", {"type": "intervention", "intervention_count": 2},
     {"arms_per_study": 2, "comparator_count": 1, "outcome_unit": "continuous", "n_nodes_assessed": True},
     "intervention_pairwise", False),
    ("bmj-exercise-depression-nma", {"type": "intervention", "intervention_count": 5, "is_living_or_update": True},
     {"arms_per_study": 2, "comparator_count": 6, "outcome_unit": "continuous", "is_update": True, "n_nodes_assessed": True},
     "intervention_network", True),
    ("nature-obesity-pharmacotherapy-nma", {"type": "intervention", "intervention_count": 6},
     {"arms_per_study": 3, "comparator_count": 8, "outcome_unit": "continuous", "n_nodes_assessed": True},
     "intervention_network", False),
    ("nature-heat-maternal-neonatal", {"type": "exposure", "is_public_health_exposure": True},
     {"exposure_outcome_design": "observational", "has_geographic_dose_heterogeneity": True, "outcome_unit": "rate"},
     "public_health_exposure", False),
    ("lancet-antidepressants-mdd-nma", {"type": "intervention", "intervention_count": 21},
     {"arms_per_study": 3, "comparator_count": 21, "outcome_unit": "binary", "n_nodes_assessed": True},
     "intervention_network", False),
    ("jama-portable-screen-sleep", {"type": "exposure", "is_public_health_exposure": True},
     {"exposure_outcome_design": "observational", "outcome_unit": "continuous"},
     "public_health_exposure", False),
    ("ag-rdt-living-dta", {"type": "diagnostic", "has_index_test_reference": True, "is_living_or_update": True},
     {"has_reference_standard": True, "is_update": True, "outcome_unit": "binary", "n_nodes_assessed": True},
     "diagnostic_accuracy", True),
    ("covid-suicide-self-harm-living", {"type": "exposure", "is_public_health_exposure": True, "is_living_or_update": True},
     {"exposure_outcome_design": "observational", "is_update": True},
     "public_health_exposure", True),
    ("bmj-type2-diabetes-risk-models", {"type": "prediction", "has_prediction_model": True},
     {"has_prediction_model": True, "outcome_unit": "rate", "n_nodes_assessed": True},
     "prognostic_prediction", False),
    ("jama-global-child-obesity-prevalence", {"type": "prevalence"},
     {"outcome_unit": "proportion", "n_nodes_assessed": True},
     "prevalence_incidence", False),
]


def main() -> int:
    predictions = []
    for case_id, question, landscape, gold_profile, gold_living in GOLD_CASES:
        decision = derive_review_design(question, landscape)
        predictions.append({
            "case_id": case_id, "profile": decision.profile,
            "living": decision.living, "abstain": decision.abstain,
            "abstain_reason": decision.abstain_reason,
        })
    gold = [{"case_id": c[0], "profile": c[3], "living": c[4]} for c in GOLD_CASES]

    full_metrics = evaluate_design_selection(predictions, gold)
    pairwise_metrics = evaluate_design_selection(
        unconditional_baseline("intervention_pairwise", gold), gold)

    report = {
        "scope": "minimal 8-strata design-selection comparison (local deterministic)",
        "cases": len(GOLD_CASES),
        "strata_covered": sorted({g["profile"] for g in gold}),
        "full_skill": {k: full_metrics[k] for k in (
            "profile_match_accuracy", "macro_over_strata", "living_flag_accuracy",
            "abstain_rate", "false_opportunity_rate")},
        "fixed_pairwise_baseline": {k: pairwise_metrics[k] for k in (
            "profile_match_accuracy", "macro_over_strata", "living_flag_accuracy",
            "abstain_rate", "false_opportunity_rate")},
        "per_case": {},
    }
    for case_id, question, landscape, gold_profile, gold_living in GOLD_CASES:
        decision = derive_review_design(question, landscape)
        report["per_case"][case_id] = {
            "gold": gold_profile, "predicted": decision.profile or "abstain",
            "correct": decision.profile == gold_profile,
            "living_gold": gold_living, "living_pred": decision.living,
        }
    out = Path(__file__).resolve().parents[1] / "research" / "design-selection-benchmark-v1.json"
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False)[:2400])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
