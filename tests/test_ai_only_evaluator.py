from __future__ import annotations

import copy
import hashlib
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "metawingman/scripts"))

from metawingman_core.ai_only_evaluator import (  # noqa: E402
    AIOnlyEvaluationError,
    aggregate_ai_only_runs,
    question_synthesis_receipt_to_run_record,
)
from metawingman_core.question_synthesis_runner import _capabilities  # noqa: E402


HASH_A = "a" * 64
HASH_B = "b" * 64
CONFIGURATION_IDS = [
    "general-model-baseline",
    "generic-retrieval",
    "biomedical-schema",
    "biomedical-routing",
    "full-biomedical-stack",
]
BIOMEDICAL_SECONDARY_METRICS = {
    "anchor_accuracy",
    "lineage_precision",
    "lineage_recall",
    "exact_recomputation_rate",
    "selective_coverage",
    "abstention_quality",
}


def load_ai_only_template() -> dict[str, object]:
    return json.loads(
        (ROOT / "metawingman/references/ai-only-evaluation-plan.template.json")
        .read_text(encoding="utf-8")
    )


def plan() -> dict[str, object]:
    reviews = [{
        "benchmark_id": "benchmark-1",
        "review_id": "review-1",
        "review_family_id": "family-1",
        "case_ids": ["case-1", "case-2"],
    }]
    manifest_sha = hashlib.sha256(json.dumps(
        reviews, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")).hexdigest()
    return {
        "schema_version": "2.0",
        "plan_id": "pilot-1",
        "plan_version": "1.0-frozen",
        "status": "frozen",
        "benchmark_version": "1.0",
        "expected_review_case_manifest": {
            "reviews": reviews,
            "sha256": manifest_sha,
        },
        "design": "ai_only_repeated_runs",
        "target_tasks": ["screening"],
        "configurations": [
            {
                "configuration_id": configuration_id,
                "description": f"Fixture for {configuration_id}.",
                "model_registry_refs": ["model@1"],
                "pipeline_version": "1.0",
                "prompt_sha256": HASH_A,
                "tool_versions": ["tool@1"],
                "ablations": [],
                "max_model_calls": 10,
                "max_input_tokens": 4000,
                "max_output_tokens": 1000,
                "retry_budget": 0,
                "wall_time_ceiling_seconds": 120,
            }
            for configuration_id in CONFIGURATION_IDS
        ],
        "repetitions_per_case": 3,
        "orchestration_seeds": [20260820, 20260821, 20260822],
        "provider_seed_supported": False,
        "seed_scope": "orchestration_order_and_tie_breaks",
        "same_provider_roles_are_independent_evidence": False,
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


def run(
    run_id: str,
    repetition: int,
    decisions: list[tuple[str, bool, bool]],
    configuration_id: str = "full-biomedical-stack",
) -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "run_id": run_id,
        "benchmark_id": "benchmark-1",
        "review_id": "review-1",
        "review_family_id": "family-1",
        "configuration_id": configuration_id,
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
    def test_ai_only_template_has_exact_biomedical_configurations_and_metrics(self) -> None:
        template = load_ai_only_template()
        self.assertEqual(
            [item["configuration_id"] for item in template["configurations"]],
            CONFIGURATION_IDS,
        )
        self.assertTrue(
            BIOMEDICAL_SECONDARY_METRICS.issubset(template["metrics"]["secondary"])
        )
        self.assertEqual(template["metrics"]["aggregation_unit"], "review_family")
        self.assertTrue(template["inference_limits"]["human_comparison_absent"])
        self.assertFalse(template["inference_limits"]["may_claim_human_superiority"])
        self.assertFalse(template["inference_limits"]["may_claim_labor_savings"])

    def test_generic_retrieval_metadata_matches_runtime_deliberation_and_shared_ceiling(self) -> None:
        template = load_ai_only_template()
        generic = next(
            item for item in template["configurations"]
            if item["configuration_id"] == "generic-retrieval"
        )
        self.assertTrue(_capabilities("generic-retrieval")["opposition_judge"])
        self.assertNotIn("test_time_scaling", generic["ablations"])
        self.assertIn("call-matched", generic["description"].casefold())
        self.assertEqual(
            {item["max_input_tokens"] for item in template["configurations"]},
            {16000},
        )

        from metawingman_core.schema_guard import validate_document

        validate_document(template, "ai_only_evaluation_plan")

    def test_ai_only_schema_rejects_configuration_id_drift(self) -> None:
        template = load_ai_only_template()
        template["configurations"][0]["configuration_id"] = "routing-renamed"

        from metawingman_core.schema_guard import SchemaValidationError, validate_document

        with self.assertRaises(SchemaValidationError):
            validate_document(template, "ai_only_evaluation_plan")

    def test_frozen_plan_rejects_matched_budget_drift(self) -> None:
        frozen = plan()
        frozen["configurations"][1]["max_output_tokens"] = 999
        with self.assertRaisesRegex(AIOnlyEvaluationError, "matched budget"):
            aggregate_ai_only_runs(
                frozen,
                [run("run-1", 1, [("case-1", True, True)])],
            )

    def test_complete_repeated_runs_aggregate_accuracy_reliability_time_and_cost(self) -> None:
        records = []
        for configuration_id in CONFIGURATION_IDS:
            records.extend([
                run(
                    f"{configuration_id}-run-1", 1,
                    [("case-1", True, True), ("case-2", False, False)],
                    configuration_id,
                ),
                run(
                    f"{configuration_id}-run-2", 2,
                    [("case-1", True, True), ("case-2", True, True)],
                    configuration_id,
                ),
                run(
                    f"{configuration_id}-run-3", 3,
                    [("case-1", True, True), ("case-2", True, True)],
                    configuration_id,
                ),
            ])
        result = aggregate_ai_only_runs(plan(), records)
        summary = next(
            item for item in result["configurations"]
            if item["configuration_id"] == "full-biomedical-stack"
        )
        self.assertTrue(result["complete"])
        self.assertAlmostEqual(summary["accuracy"], 5 / 6)
        self.assertAlmostEqual(summary["critical_error_rate"], 1 / 6)
        self.assertAlmostEqual(summary["pairwise_run_agreement"], 2 / 3)
        self.assertEqual(summary["all_repeats_correct_rate"], 0.5)
        self.assertEqual(summary["wall_clock_seconds_total"], 36.0)
        self.assertAlmostEqual(summary["api_cost_total"], 0.3)
        self.assertAlmostEqual(summary["total_cost_mean"], 0.12)
        self.assertTrue(summary["thresholds_passed"])
        self.assertTrue(result["release_ready"])
        self.assertFalse(result["human_superiority_claim_permitted"])
        self.assertFalse(result["labor_savings_claim_permitted"])

    def test_missing_repetition_is_not_complete(self) -> None:
        result = aggregate_ai_only_runs(plan(), [
            run("run-1", 1, [("case-1", True, True), ("case-2", True, True)])
        ])
        self.assertFalse(result["complete"])
        self.assertFalse(result["release_ready"])
        self.assertIn(
            "full-biomedical-stack:review-1",
            result["incomplete_configuration_reviews"],
        )

    def test_five_arms_must_score_the_same_review_case_set_at_exactly_three_repetitions(self) -> None:
        records = []
        for configuration_id in CONFIGURATION_IDS[:-1]:
            for repetition in (1, 2, 3):
                records.append(run(
                    f"{configuration_id}-{repetition}", repetition,
                    [("case-1", True, True), ("case-2", True, True)], configuration_id,
                ))
        result = aggregate_ai_only_runs(plan(), records)
        self.assertFalse(result["complete"])
        self.assertIn("full-biomedical-stack:missing_all_repetitions", result["incomplete_configuration_reviews"])

    def test_expected_manifest_rejects_a_case_omitted_by_every_configuration(self) -> None:
        records = []
        for configuration_id in CONFIGURATION_IDS:
            for repetition in (1, 2, 3):
                records.append(run(
                    f"{configuration_id}-{repetition}", repetition,
                    [("case-1", True, True)], configuration_id,
                ))
        with self.assertRaisesRegex(AIOnlyEvaluationError, "expected review/case manifest"):
            aggregate_ai_only_runs(plan(), records)

    def test_unknown_cost_is_propagated_as_unknown_instead_of_zero(self) -> None:
        records = []
        for configuration_id in CONFIGURATION_IDS:
            for repetition in (1, 2, 3):
                record = run(
                    f"{configuration_id}-{repetition}", repetition,
                    [("case-1", True, True), ("case-2", True, True)], configuration_id,
                )
                record["api_cost"] = None
                record["compute_cost"] = None
                record["cost_currency"] = "unknown"
                records.append(record)
        result = aggregate_ai_only_runs(plan(), records)
        summary = result["configurations"][0]
        self.assertTrue(result["complete"])
        self.assertIsNone(summary["api_cost_total"])
        self.assertIsNone(summary["compute_cost_total"])
        self.assertIsNone(summary["total_cost_total"])
        self.assertEqual(summary["cost_status"], "unknown")

    def test_question_synthesis_receipt_adapter_preserves_unknown_cost(self) -> None:
        record = question_synthesis_receipt_to_run_record(
            {
                "plan_id": "pilot-1", "case_id": "case-1",
                "configuration_id": "generic-retrieval", "seed": 20260820,
                "wall_time_seconds": 2.5, "model_calls": 1,
                "input_tokens": 50, "output_tokens": 10,
                "provider_cost": None, "provider_cost_status": "unknown",
                "output_sha256": HASH_A,
            },
            benchmark_id="benchmark-1", review_id="review-1",
            review_family_id="family-1", repetition_index=1,
            case_result={
                "case_id": "case-1", "decision_sha256": HASH_A,
                "answered": True, "correct": True, "abstained": False,
                "critical_error": False, "false_exclusion": False,
                "unsupported_value": False,
            },
        )
        self.assertIsNone(record["api_cost"])
        self.assertIsNone(record["compute_cost"])
        self.assertEqual(record["cost_currency"], "unknown")

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
        records = []
        for configuration_id in CONFIGURATION_IDS:
            records.extend([
                run(
                    f"{configuration_id}-run-1", 1,
                    [("case-1", True, True), ("case-2", False, False)],
                    configuration_id,
                ),
                run(
                    f"{configuration_id}-run-2", 2,
                    [("case-1", True, True), ("case-2", True, True)],
                    configuration_id,
                ),
                run(
                    f"{configuration_id}-run-3", 3,
                    [("case-1", True, True), ("case-2", True, True)],
                    configuration_id,
                ),
            ])
        result = aggregate_ai_only_runs(frozen, records)
        self.assertTrue(result["complete"])
        self.assertFalse(result["release_ready"])
        self.assertFalse(result["configurations"][0]["thresholds_passed"])


if __name__ == "__main__":
    unittest.main()
