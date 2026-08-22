from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from metawingman.scripts.evaluate_fulltext_acquisition_loop import evaluate_fulltext_loops


class FullTextAcquisitionLoopEvaluationTests(unittest.TestCase):
    def test_real_loop_executes_high_impact_false_exclusion_first(self) -> None:
        abstract = [
            {"example_id": "critical", "family_id": "F", "true": "include", "predicted": "exclude", "action_probabilities": {"exclude": 0.55, "include": 0.45}},
            {"example_id": "safe", "family_id": "F", "true": "exclude", "predicted": "exclude", "action_probabilities": {"exclude": 0.9, "include": 0.1}},
        ]
        full = [
            {"example_id": "critical", "family_id": "F", "true": "include", "predicted": "include", "action_probabilities": {"exclude": 0.1, "include": 0.9}},
            {"example_id": "safe", "family_id": "F", "true": "exclude", "predicted": "exclude", "action_probabilities": {"exclude": 0.95, "include": 0.05}},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            result = evaluate_fulltext_loops(
                abstract,
                full,
                artifact_root=Path(tmp),
                budget_fraction=0.5,
                created_at_utc="2026-08-22T00:00:00Z",
            )
        loop = result["family_loops"]["F"]
        self.assertEqual(loop["selected_example_ids"], ["critical"])
        self.assertTrue(loop["controller_result"]["full_risk_impact_controller_instantiated"])
        self.assertEqual(len(loop["controller_result"]["action_receipts"]), 1)
        self.assertEqual(result["metrics"]["include_recall"], 1.0)

    def test_legacy_log_likelihoods_are_supported(self) -> None:
        abstract = [{"example_id": "a", "family_id": "F", "true": "include", "predicted": "exclude", "action_log_likelihoods": {"exclude": -0.2, "include": -0.3}}]
        full = [{"example_id": "a", "family_id": "F", "true": "include", "predicted": "include", "action_log_likelihoods": {"exclude": -2.0, "include": -0.1}}]
        with tempfile.TemporaryDirectory() as tmp:
            result = evaluate_fulltext_loops(abstract, full, artifact_root=Path(tmp), budget_fraction=1.0, created_at_utc="2026-08-22T00:00:00Z")
        self.assertEqual(result["metrics"]["record_accuracy"], 1.0)


if __name__ == "__main__":
    unittest.main()
