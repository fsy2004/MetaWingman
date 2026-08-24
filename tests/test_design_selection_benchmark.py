from __future__ import annotations

import unittest
from pathlib import Path

from metawingman.benchmark.cli import _run
from metawingman.benchmark.gold_loader import load_gold, gold_to_eval_rows
from metawingman.benchmark.landscape_builder import (
    build_gold_signals,
    records_from_corpus,
    signal_from_records,
)

REPO = Path(__file__).resolve().parents[1]
GOLD = REPO / "research" / "design-selection-gold-v1.json"
RECORDS = REPO / "research" / "records-by-family-demo.json"


class TestGoldLoader(unittest.TestCase):
    def test_loads_11_cases_and_8_strata(self):
        gold = load_gold(GOLD)
        self.assertEqual(len(gold), 11)
        profiles = {g.gold_profile for g in gold}
        self.assertIn("intervention_network", profiles)
        self.assertIn("diagnostic_accuracy", profiles)
        self.assertIn("prevalence_incidence", profiles)
        self.assertIn("public_health_exposure", profiles)
        self.assertIn("prognostic_prediction", profiles)
        self.assertIn("intervention_pairwise", profiles)

    def test_eval_rows_carry_identity(self):
        rows = gold_to_eval_rows(load_gold(GOLD))
        self.assertEqual(len(rows), 11)
        self.assertTrue(all("case_id" in r and "profile" in r and "living" in r for r in rows))


class TestLandscapeBuilder(unittest.TestCase):
    def test_exposure_design_injected_from_record(self):
        signal = signal_from_records(
            {"type": "exposure", "is_public_health_exposure": True},
            [{"review_family_id": "f", "exposure_outcome_design": "observational",
              "outcome_unit": "rate", "node_coverage_checked": True}],
            family_id="f",
        )
        self.assertEqual(signal["exposure_outcome_design"], "observational")
        self.assertEqual(signal["outcome_unit"], "rate")

    def test_fallback_signal_from_question_shape(self):
        signal = signal_from_records({"type": "diagnostic", "has_index_test_reference": True}, [])
        self.assertTrue(signal["has_reference_standard"])

    def test_records_from_corpus_normalises_fields(self):
        raw = [{"review_family_id": "x", "intervention_count": 4, "comparator_count": 8,
                "outcome_unit": "binary", "is_update": True, "node_coverage_checked": True}]
        rows = records_from_corpus(raw)
        self.assertEqual(rows[0]["intervention_count"], 4)
        self.assertEqual(rows[0]["comparator_count"], 8)
        self.assertTrue(rows[0]["node_coverage_checked"])

    def test_build_gold_signals_falls_back_to_landscape(self):
        gold = load_gold(GOLD)
        signals = build_gold_signals(gold)
        # curated path: signal == gold landscape
        self.assertEqual(signals["nature-psychological-wellbeing"], gold[1].landscape)


class TestBenchmarkCli(unittest.TestCase):
    def test_curated_and_records_paths_both_match(self):
        curated = _run(GOLD)
        rec = _run(GOLD, records_path=RECORDS)
        for report in (curated, rec):
            self.assertEqual(report["skill"]["profile_match_accuracy"], 1.0)
            self.assertEqual(report["skill"]["living_flag_accuracy"], 1.0)
            self.assertEqual(report["skill"]["abstain_rate"], 0.0)
            self.assertEqual(report["skill"]["false_opportunity_rate"], 0.0)
        self.assertEqual(curated["source_of_signals"], "gold.landscape")
        self.assertEqual(rec["source_of_signals"], "records")

    def test_fixed_pairwise_baseline_underperforms_skill(self):
        report = _run(GOLD, baselines=["intervention_pairwise"])
        skill_match = report["skill"]["profile_match_accuracy"]
        baseline = report["baselines"]["unconditional intervention_pairwise"]["profile_match_accuracy"]
        self.assertEqual(skill_match, 1.0)
        self.assertEqual(baseline, 1.0 / len(load_gold(GOLD)))  # exactly 1/11
        self.assertGreater(skill_match, baseline)

    def test_extra_baselines_are_reported(self):
        report = _run(GOLD, baselines=["intervention_pairwise", "intervention_network"])
        self.assertTrue(any("intervention_network" in k for k in report["baselines"]))
        self.assertLess(report["baselines"]["unconditional intervention_network"]["profile_match_accuracy"], 1.0)


if __name__ == "__main__":
    unittest.main()
