"""Evaluate source-grounded pipeline cases with asymmetric scientific loss."""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Any, Iterable

from .reliability import evaluate_reliability
from .schema_guard import SchemaValidationError, validate_document


CRITICAL_ERRORS = {
    "false_exclusion", "unsupported_value", "unanchored_claim",
    "unauthorized_action", "missed_required_abstention",
}


class PipelineEvaluationError(ValueError):
    """Raised when an evaluation set is invalid or contaminated."""


def _value_matches(reference: Any, prediction: Any, tolerance: float | None) -> bool:
    if tolerance is not None:
        if isinstance(reference, bool) or isinstance(prediction, bool):
            return reference == prediction
        if isinstance(reference, (int, float)) and isinstance(prediction, (int, float)):
            return math.isclose(float(reference), float(prediction), abs_tol=tolerance, rel_tol=0.0)
    return reference == prediction


def _score_case(case: dict[str, Any]) -> dict[str, Any]:
    reference = case["reference"]
    prediction = case["prediction"]
    errors: dict[str, int] = defaultdict(int)
    ref_decision = (reference["decision"] or "").casefold()
    pred_decision = (prediction["decision"] or "").casefold()

    if case["task_type"] == "screening":
        if ref_decision == "include" and pred_decision == "exclude":
            errors["false_exclusion"] += 1
        elif ref_decision == "exclude" and pred_decision == "include":
            errors["false_inclusion"] += 1
    elif case["task_type"] == "action":
        if ref_decision != "allowed" and pred_decision == "allowed":
            errors["unauthorized_action"] += 1
    elif ref_decision and pred_decision and ref_decision != pred_decision:
        errors["incorrect_value"] += 1

    if reference["abstention_required"] and not prediction["abstained"]:
        errors["missed_required_abstention"] += 1
    if not reference["abstention_required"] and prediction["abstained"]:
        errors["unnecessary_abstention"] += 1

    reference_fields = {item["field"]: item for item in reference["fields"]}
    predicted_fields = {item["field"]: item for item in prediction["fields"]}
    if len(predicted_fields) != len(prediction["fields"]):
        errors["unsupported_value"] += len(prediction["fields"]) - len(predicted_fields)
    for field, predicted in predicted_fields.items():
        expected = reference_fields.get(field)
        if expected is None:
            errors["unsupported_value"] += 1
            continue
        if not predicted["anchor_ids"]:
            errors["unsupported_value"] += 1
        if not _value_matches(expected["value"], predicted["value"], expected["tolerance"]):
            errors["incorrect_value"] += 1

    if case["task_type"] == "claim" and (
        not prediction["anchor_ids"] or not set(prediction["anchor_ids"]) & set(reference["anchor_ids"])
    ):
        errors["unanchored_claim"] += 1
    return {
        "case_id": case["case_id"],
        "review_family_id": case["review_family_id"],
        "split": case["split"],
        "errors": dict(sorted(errors.items())),
        "critical_error": any(errors.get(name, 0) for name in CRITICAL_ERRORS),
    }


def _validate_isolation(spec: dict[str, Any], cases: list[dict[str, Any]]) -> None:
    assigned: dict[str, str] = {}
    for split in ("train", "dev", "test"):
        for family in spec["split_policy"][f"{split}_family_ids"]:
            if family in assigned:
                raise PipelineEvaluationError(
                    f"review family {family} appears in both {assigned[family]} and {split}"
                )
            assigned[family] = split
    review_splits: dict[str, set[str]] = defaultdict(set)
    review_families: dict[str, set[str]] = defaultdict(set)
    seen_cases: set[str] = set()
    for case in cases:
        case_id = case["case_id"]
        if case_id in seen_cases:
            raise PipelineEvaluationError(f"duplicate case_id: {case_id}")
        seen_cases.add(case_id)
        expected = assigned.get(case["review_family_id"])
        if expected is None:
            raise PipelineEvaluationError(
                f"case {case_id} uses unassigned review family {case['review_family_id']}"
            )
        if expected != case["split"]:
            raise PipelineEvaluationError(
                f"case {case_id} split {case['split']} conflicts with family assignment {expected}"
            )
        review_splits[case["review_id"]].add(case["split"])
        review_families[case["review_id"]].add(case["review_family_id"])
    contaminated = sorted(
        review_id for review_id, splits in review_splits.items()
        if len(splits) > 1 or len(review_families[review_id]) > 1
    )
    if contaminated:
        raise PipelineEvaluationError(
            "review-level split contamination: " + ", ".join(contaminated)
        )


def evaluate_pipeline(
    spec: dict[str, Any],
    cases: Iterable[dict[str, Any]],
    reliability_trials: Iterable[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    try:
        validate_document(spec, "pipeline_spec")
    except SchemaValidationError as exc:
        raise PipelineEvaluationError(str(exc)) from exc
    records = list(cases)
    if not records:
        raise PipelineEvaluationError("At least one evaluation case is required")
    for case in records:
        try:
            validate_document(case, "pipeline_evaluation_case")
        except SchemaValidationError as exc:
            raise PipelineEvaluationError(str(exc)) from exc
        if case["task_type"] != spec["task_type"]:
            raise PipelineEvaluationError(
                f"case {case['case_id']} task {case['task_type']} does not match pipeline task {spec['task_type']}"
            )
    _validate_isolation(spec, records)

    results = [_score_case(case) for case in records]
    weights = spec["loss_weights"]
    for result in results:
        result["loss"] = sum(weights[name] * count for name, count in result["errors"].items())

    split_metrics: dict[str, dict[str, Any]] = {}
    for split in ("train", "dev", "test"):
        split_cases = [case for case in records if case["split"] == split]
        split_results = [result for result in results if result["split"] == split]
        error_counts: dict[str, int] = defaultdict(int)
        for result in split_results:
            for name, count in result["errors"].items():
                error_counts[name] += count
        split_metrics[split] = {
            "cases": len(split_results),
            "review_families": len({case["review_family_id"] for case in split_cases}),
            "mean_loss": (
                sum(result["loss"] for result in split_results) / len(split_results)
                if split_results else None
            ),
            "critical_error_rate": (
                sum(result["critical_error"] for result in split_results) / len(split_results)
                if split_results else None
            ),
            "error_counts": dict(sorted(error_counts.items())),
        }

    reasons: list[str] = []
    test_cases = [case for case in records if case["split"] == "test"]
    if not test_cases:
        reasons.append("held_out_test_cases_missing")
    if any(
        not case["verifier"]["source_grounded"] or case["verifier"]["status"] != "passed"
        for case in test_cases
    ):
        reasons.append("test_verifier_not_source_grounded_and_passed")
    test_metrics = split_metrics["test"]
    gates = spec["release_gates"]
    if test_metrics["mean_loss"] is not None and test_metrics["mean_loss"] > gates["max_mean_loss"]:
        reasons.append("test_mean_loss_above_ceiling")
    if (
        test_metrics["critical_error_rate"] is not None
        and test_metrics["critical_error_rate"] > gates["max_critical_error_rate"]
    ):
        reasons.append("test_critical_error_rate_above_ceiling")

    reliability = None
    if reliability_trials is None:
        reasons.append("reliability_trials_missing")
    else:
        reliability = evaluate_reliability(
            reliability_trials,
            repeat_k=gates["repeat_k"],
            min_pass_power_k=gates["min_pass_power_k"],
            max_critical_error_rate=gates["max_critical_error_rate"],
            max_position_gap=gates["max_position_gap"],
            max_judge_order_disagreement=gates["max_judge_order_disagreement"],
        )
        if not reliability["valid"]:
            reasons.extend(f"reliability:{reason}" for reason in reliability["reason_codes"])

    return {
        "release_ready": not reasons,
        "reason_codes": reasons,
        "pipeline_id": spec["pipeline_id"],
        "pipeline_version": spec["pipeline_version"],
        "split_metrics": split_metrics,
        "reliability": reliability,
        "case_results": results,
    }
