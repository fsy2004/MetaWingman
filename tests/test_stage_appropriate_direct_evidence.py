from __future__ import annotations

import copy
import unittest

from metawingman.scripts.metawingman_core.stage_appropriate_evaluation import (
    StagePlanError,
    validate_stage_plan,
)


class StageAppropriateEvaluationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.plan = {
            "schema_version": "1.1",
            "plan_id": "stage-appropriate-r4",
            "frozen_at_utc": "2026-08-22T02:00:00Z",
            "case_registry_sha256": "a" * 64,
            "repeats": [20260823, 20260824, 20260825],
            "topic_rediscovery": {
                "input_condition": "broad_non_target_historical_landscape",
                "target_identity_sealed": True,
                "published_answers_sealed": True,
                "independent_signal_audit_required": True,
                "arms": [
                    "bibliometric_count", "semantic_gap", "graph_only", "llm_proposal_order",
                    "decision_aware_full", "no_overlap_opposition", "no_decision_relevance",
                    "no_portfolio_diversity",
                ],
            },
            "fixed_question_reconstruction": {
                "input_condition": "frozen_question_and_operational_corpus",
                "published_answers_sealed": True,
                "arms": ["generic_fixed_acquisition", "conclusion_directed_acquisition"],
                "protocol_schema_repairs": 1,
                "synthesis_schema_repairs": 1,
            },
        }

    def test_two_scientific_stages_are_validated_separately(self) -> None:
        result = validate_stage_plan(self.plan)
        self.assertEqual(result["topic_slots_per_case"], 24)
        self.assertEqual(result["fixed_question_slots_per_case"], 6)

    def test_target_conditioned_topic_input_fails_closed(self) -> None:
        plan = copy.deepcopy(self.plan)
        plan["topic_rediscovery"]["input_condition"] = "target_conditioned_corpus"
        with self.assertRaisesRegex(StagePlanError, "broad non-target"):
            validate_stage_plan(plan)

    def test_fixed_question_stage_cannot_contain_a_topic_flag(self) -> None:
        plan = copy.deepcopy(self.plan)
        plan["fixed_question_reconstruction"]["topic_opportunity_control"] = True
        with self.assertRaisesRegex(StagePlanError, "topic mechanism"):
            validate_stage_plan(plan)

    def test_exact_control_and_ablation_arms_are_required(self) -> None:
        plan = copy.deepcopy(self.plan)
        plan["topic_rediscovery"]["arms"].remove("no_decision_relevance")
        with self.assertRaisesRegex(StagePlanError, "exact frozen arms"):
            validate_stage_plan(plan)

    def test_both_schema_repairs_are_bounded_to_one(self) -> None:
        plan = copy.deepcopy(self.plan)
        plan["fixed_question_reconstruction"]["protocol_schema_repairs"] = 2
        with self.assertRaisesRegex(StagePlanError, "one bounded"):
            validate_stage_plan(plan)


if __name__ == "__main__":
    unittest.main()
