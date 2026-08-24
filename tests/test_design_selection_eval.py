from __future__ import annotations

import unittest

from metawingman.scripts.metawingman_core.design_selection import derive_review_design
from metawingman.scripts.metawingman_core.design_selection_eval import (
    evaluate_design_selection,
    unconditional_baseline,
)
from metawingman.scripts.metawingman_core.evidence_landscape import build_evidence_landscape


def _record(start: int, **overrides):
    row = {
        "review_family_id": "fam-a", "historical_cutoff": "2023-01-01",
        "intervention_count": 2, "comparator_count": 1,
        "has_reference_standard": False, "has_prediction_model": False,
        "outcome_unit": "binary", "is_update": False,
        "node_coverage_checked": True, "record_id": f"r{start}",
    }
    row.update(overrides)
    return row


class EvidenceLandscapeTests(unittest.TestCase):
    def test_build_landscape_aggregates_family_signals(self) -> None:
        records = [
            _record(1, review_family_id="fam-a", intervention_count=6, comparator_count=8, is_update=True,
                    outcome_unit="continuous"),
            _record(2, review_family_id="fam-b", has_reference_standard=True, outcome_unit="binary"),
            _record(3, review_family_id="fam-c", has_prediction_model=True, outcome_unit="rate"),
        ]
        landscape = build_evidence_landscape(records)
        self.assertEqual(landscape.families, 3)
        self.assertEqual(landscape.comparator_nodes["fam-a"], 8)
        self.assertIn("fam-b", landscape.reference_standard_families)
        self.assertIn("fam-c", landscape.prediction_model_families)
        summary = landscape.summary("fam-a")
        self.assertTrue(summary["is_update"])
        self.assertEqual(summary["comparator_count"], 8)
        self.assertEqual(summary["outcome_unit"], "continuous")

    def test_landscape_feeds_design_selection_end_to_end(self) -> None:
        records = [_record(1, intervention_count=6, comparator_count=8, is_update=True, outcome_unit="continuous")]
        landscape = build_evidence_landscape(records)
        summary = landscape.summary("fam-a")
        decision = derive_review_design(
            {"type": "intervention", "intervention_count": 6, "is_living_or_update": True},
            summary,
        )
        self.assertEqual(decision.profile, "intervention_network")
        self.assertTrue(decision.living)


class DesignSelectionEvalTests(unittest.TestCase):
    def _gold(self):
        return [
            {"case_id": "c1", "profile": "diagnostic_accuracy", "living": False},
            {"case_id": "c2", "profile": "intervention_network", "living": True},
            {"case_id": "c3", "profile": "prevalence_incidence", "living": False},
        ]

    def test_evaluate_reports_predeclared_metrics(self) -> None:
        gold = self._gold()
        preds = [
            {"case_id": "c1", "profile": "diagnostic_accuracy", "living": False},
            {"case_id": "c2", "profile": "intervention_network", "living": True},
            {"case_id": "c3", "profile": "public_health_exposure", "living": False, "abstain": False},
        ]
        metrics = evaluate_design_selection(preds, gold)
        self.assertAlmostEqual(metrics["profile_match_accuracy"], 2 / 3)
        self.assertAlmostEqual(metrics["living_flag_accuracy"], 1.0)
        self.assertAlmostEqual(metrics["false_opportunity_rate"], 1 / 3)
        self.assertIn("diagnostic_accuracy", metrics["confusion"])

    def test_evaluate_counts_abstention_separately(self) -> None:
        gold = self._gold()
        preds = [
            {"case_id": "c1", "profile": "", "abstain": True},
            {"case_id": "c2", "profile": "intervention_network", "living": True},
            {"case_id": "c3", "profile": "prevalence_incidence", "living": False},
        ]
        metrics = evaluate_design_selection(preds, gold)
        self.assertAlmostEqual(metrics["abstain_rate"], 1 / 3)
        self.assertAlmostEqual(metrics["profile_match_accuracy"], 2 / 3)

    def test_unconditional_baseline_never_abstains(self) -> None:
        rows = unconditional_baseline("intervention_pairwise", [{"case_id": "x"}])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["profile"], "intervention_pairwise")
        self.assertFalse(rows[0]["abstain"])


if __name__ == "__main__":
    unittest.main()
