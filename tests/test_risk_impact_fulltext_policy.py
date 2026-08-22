from __future__ import annotations

import unittest

from metawingman.scripts.evaluate_risk_impact_fulltext_policy import evaluate_policies


class RiskImpactFullTextPolicyTests(unittest.TestCase):
    def test_full_policy_prioritizes_asymmetric_false_exclusion_risk(self) -> None:
        abstract = [
            {"example_id": "critical", "family_id": "F", "true": "include", "predicted": "exclude", "action_probabilities": {"exclude": 0.55, "include": 0.45}},
            {"example_id": "safe", "family_id": "F", "true": "exclude", "predicted": "exclude", "action_probabilities": {"exclude": 0.8, "include": 0.2}},
        ]
        full = [
            {"example_id": "critical", "family_id": "F", "true": "include", "predicted": "include", "action_probabilities": {"exclude": 0.1, "include": 0.9}},
            {"example_id": "safe", "family_id": "F", "true": "exclude", "predicted": "exclude", "action_probabilities": {"exclude": 0.9, "include": 0.1}},
        ]
        result = evaluate_policies(abstract, full, budget_fraction=0.5, false_exclusion_harm=4.0)
        selected = result["arms"]["risk_impact_asymmetric"]["action_trace"][0]["example_id"]
        self.assertEqual(selected, "critical")
        self.assertEqual(result["arms"]["risk_impact_asymmetric"]["metrics"]["include_recall"], 1.0)
        self.assertEqual(result["matched_fulltext_actions_per_family"], {"F": 1})

    def test_mismatched_score_rows_fail_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "same examples"):
            evaluate_policies(
                [{"example_id": "a", "family_id": "F", "true": "include", "predicted": "exclude", "action_probabilities": {"exclude": 0.6, "include": 0.4}}],
                [{"example_id": "b", "family_id": "F", "true": "include", "predicted": "include", "action_probabilities": {"exclude": 0.1, "include": 0.9}}],
                budget_fraction=0.5,
                false_exclusion_harm=4.0,
            )

    def test_legacy_log_likelihood_rows_are_normalized(self) -> None:
        abstract = [
            {"example_id": "critical", "family_id": "F", "true": "include", "predicted": "exclude", "action_log_likelihoods": {"exclude": -0.2, "include": -0.3}},
            {"example_id": "safe", "family_id": "F", "true": "exclude", "predicted": "exclude", "action_log_likelihoods": {"exclude": -0.1, "include": -2.0}},
        ]
        full = [
            {"example_id": "critical", "family_id": "F", "true": "include", "predicted": "include", "action_log_likelihoods": {"exclude": -2.0, "include": -0.1}},
            {"example_id": "safe", "family_id": "F", "true": "exclude", "predicted": "exclude", "action_log_likelihoods": {"exclude": -0.1, "include": -2.0}},
        ]
        result = evaluate_policies(abstract, full, budget_fraction=0.5, false_exclusion_harm=4.0)
        self.assertEqual(
            result["arms"]["risk_impact_asymmetric"]["action_trace"][0]["example_id"],
            "critical",
        )


if __name__ == "__main__":
    unittest.main()
