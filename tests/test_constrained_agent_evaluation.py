from __future__ import annotations

import unittest

from metawingman.scripts.evaluate_constrained_agent_actions import classification_metrics, derive_action_contract


class ConstrainedAgentEvaluationTests(unittest.TestCase):
    def test_metrics_separate_record_and_family_performance(self) -> None:
        rows = [
            {"family_id": "large", "true": "include", "predicted": "include"},
            {"family_id": "large", "true": "exclude", "predicted": "exclude"},
            {"family_id": "small", "true": "include", "predicted": "exclude"},
        ]
        metrics = classification_metrics(rows, ["exclude", "include"])
        self.assertAlmostEqual(metrics["record_accuracy"], 2 / 3)
        self.assertAlmostEqual(metrics["family_macro_accuracy"], 0.5)
        self.assertAlmostEqual(metrics["balanced_accuracy"], 0.75)

    def test_contract_uses_frozen_dataset_targets_without_inventing_actions(self) -> None:
        rows = [
            {"target_action": {"type": "effect_decreased", "source_section": "result_extraction"}, "target_decision": {"status": "effect_decreased"}},
            {"target_action": {"type": "effect_increased", "source_section": "result_extraction"}, "target_decision": {"status": "effect_increased"}},
        ]
        contract = derive_action_contract(rows)
        self.assertEqual(list(contract), ["effect_decreased", "effect_increased"])
        self.assertEqual(contract["effect_decreased"]["target_action"]["source_section"], "result_extraction")


if __name__ == "__main__":
    unittest.main()
