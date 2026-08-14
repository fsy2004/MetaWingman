from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "metawingman/scripts"))

from metawingman_core.ai_only_evaluator import (  # noqa: E402
    AIOnlyEvaluationError,
    aggregate_ai_only_runs,
)


HASH_A = "a" * 64
HASH_B = "b" * 64


def plan() -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "plan_id": "pilot-1",
        "plan_version": "1.0-frozen",
        "status": "frozen",
        "benchmark_version": "1.0",
        "design": "ai_only_repeated_runs",
        "target_tasks": ["screening"],
        "configurations": [{
            "configuration_id": "full",
            "description": "Full fixture configuration.",
            "model_registry_refs": ["model@1"],
            "pipeline_version": "1.0",
            "prompt_sha256": HASH_A,
            "tool_versions": ["tool@1"],
            "ablations": [],
            "max_model_calls": 10,
            "retry_budget": 1,
        }],
        "repetitions_per_case": 2,
        "reference_standard": {
            "source": "published_expert_reference",
            "correction_policy": "verified_corrected_version_only",
            "integrity_policy": "unresolved_cases_excluded_from_held_out_scoring",
            "de_novo_human_adjudication": False,
            "answers_sealed_until_all_runs_locked": True,
        },
        "metrics": {
            "primary": ["critical_error_rate", "false_exclusion_rate"],
            "secondary": ["coverage", "run_to_run_reliability", "wall_clock_seconds", "api_cost"],
            "aggregation_unit": "review_family",
            "uncertainty_method": "paired_bootstrap_by_review_family",
        },
        "critical_error_weights": {"false_exclusion": 10},
        "release_thresholds": {
            "max_critical_error_rate": 0.25,
            "min_coverage": 1.0,
            "min_run_to_run_reliability": 0.5,
        },
        "inference_limits": {
            "human_comparison_absent": True,
            "may_claim_human_superiority": False,
            "may_claim_labor_savings": False,
            "allowed_claim": "AI agreement with published expert references, reliability, risk-coverage, latency, and cost",
        },
        "frozen_at_utc": "2026-08-13T00:00:00Z",
    }


def run(run_id: str, repetition: int, decisions: list[tuple[str, bool, bool]]) -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "run_id": run_id,
        "benchmark_id": "benchmark-1",
        "review_id": "review-1",
        "review_family_id": "family-1",
        "configuration_id": "full",
        "repetition_index": repetition,
        "execution_mode": "ai_only",
        "human_interventions": 0,
        "case_results": [{
            "case_id": case_id,
            "decision_sha256": HASH_A if decision else HASH_B,
            "answered": True,
            "correct": correct,
            "abstained": False,
            "critical_error": not correct,
            "false_exclusion": not correct,
            "unsupported_value": False,
        } for case_id, decision, correct in decisions],
        "wall_clock_seconds": 10.0 + repetition,
        "model_calls": 2,
        "input_tokens": 100,
        "output_tokens": 20,
        "api_cost": 0.1,
        "compute_cost": 0.02,
        "cost_currency": "USD",
        "output_sha256": HASH_A,
    }


class AIOnlyEvaluatorTests(unittest.TestCase):
    def test_complete_repeated_runs_aggregate_accuracy_reliability_time_and_cost(self) -> None:
        records = [
            run("run-1", 1, [("case-1", True, True), ("case-2", False, False)]),
            run("run-2", 2, [("case-1", True, True), ("case-2", True, True)]),
        ]
        result = aggregate_ai_only_runs(plan(), records)
        summary = result["configurations"][0]
        self.assertTrue(result["complete"])
        self.assertEqual(summary["accuracy"], 0.75)
        self.assertEqual(summary["critical_error_rate"], 0.25)
        self.assertEqual(summary["pairwise_run_agreement"], 0.5)
        self.assertEqual(summary["all_repeats_correct_rate"], 0.5)
        self.assertEqual(summary["wall_clock_seconds_total"], 23.0)
        self.assertAlmostEqual(summary["api_cost_total"], 0.2)
        self.assertAlmostEqual(summary["total_cost_mean"], 0.12)
        self.assertTrue(summary["thresholds_passed"])
        self.assertTrue(result["release_ready"])
        self.assertFalse(result["human_superiority_claim_permitted"])
        self.assertFalse(result["labor_savings_claim_permitted"])

    def test_missing_repetition_is_not_complete(self) -> None:
        result = aggregate_ai_only_runs(plan(), [
            run("run-1", 1, [("case-1", True, True)])
        ])
        self.assertFalse(result["complete"])
        self.assertFalse(result["release_ready"])
        self.assertEqual(result["incomplete_configuration_reviews"], ["full:review-1"])

    def test_human_intervention_is_rejected_by_schema(self) -> None:
        record = run("run-1", 1, [("case-1", True, True)])
        record["human_interventions"] = 1
        with self.assertRaises(AIOnlyEvaluationError):
            aggregate_ai_only_runs(plan(), [record])

    def test_draft_plan_cannot_score_runs(self) -> None:
        draft = copy.deepcopy(plan())
        draft["status"] = "draft"
        draft["frozen_at_utc"] = None
        with self.assertRaises(AIOnlyEvaluationError):
            aggregate_ai_only_runs(draft, [
                run("run-1", 1, [("case-1", True, True)])
            ])

    def test_frozen_plan_rejects_placeholder_configuration(self) -> None:
        frozen = plan()
        frozen["configurations"][0]["prompt_sha256"] = "0" * 64
        with self.assertRaises(AIOnlyEvaluationError):
            aggregate_ai_only_runs(frozen, [
                run("run-1", 1, [("case-1", True, True)])
            ])

    def test_threshold_failure_blocks_release(self) -> None:
        frozen = plan()
        frozen["release_thresholds"]["max_critical_error_rate"] = 0.1
        records = [
            run("run-1", 1, [("case-1", True, True), ("case-2", False, False)]),
            run("run-2", 2, [("case-1", True, True), ("case-2", True, True)]),
        ]
        result = aggregate_ai_only_runs(frozen, records)
        self.assertTrue(result["complete"])
        self.assertFalse(result["release_ready"])
        self.assertFalse(result["configurations"][0]["thresholds_passed"])


if __name__ == "__main__":
    unittest.main()
