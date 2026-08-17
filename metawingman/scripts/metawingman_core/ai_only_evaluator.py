"""Aggregate AI-only repeated-run benchmark accuracy, reliability, time, and cost."""

from __future__ import annotations

from collections import defaultdict
from itertools import combinations
from statistics import mean
from typing import Any, Iterable

from .schema_guard import SchemaValidationError, validate_document


class AIOnlyEvaluationError(ValueError):
    """Raised when AI-only run records violate the frozen evaluation design."""


def _rate(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def _sum(records: list[dict[str, Any]], field: str) -> float:
    return float(sum(record[field] for record in records))


def _threshold_results(
    summary: dict[str, Any], thresholds: dict[str, float]
) -> list[dict[str, Any]]:
    specifications = {
        "max_critical_error_rate": ("critical_error_rate", "max"),
        "max_false_exclusion_rate": ("false_exclusion_rate", "max"),
        "max_unsupported_value_rate": ("unsupported_value_rate", "max"),
        "min_accuracy": ("accuracy", "min"),
        "min_coverage": ("coverage", "min"),
        "min_run_to_run_reliability": ("pairwise_run_agreement", "min"),
        "max_mean_wall_clock_seconds": ("wall_clock_seconds_mean", "max"),
        "max_mean_total_cost": ("total_cost_mean", "max"),
    }
    results: list[dict[str, Any]] = []
    for threshold_name, threshold in sorted(thresholds.items()):
        metric, direction = specifications[threshold_name]
        observed = summary[metric]
        passed = observed is not None and (
            observed <= threshold if direction == "max" else observed >= threshold
        )
        results.append({
            "threshold": threshold_name,
            "metric": metric,
            "direction": direction,
            "limit": threshold,
            "observed": observed,
            "passed": passed,
        })
    return results


def aggregate_ai_only_runs(
    plan: dict[str, Any],
    records: Iterable[dict[str, Any]],
) -> dict[str, Any]:
    try:
        validate_document(plan, "ai_only_evaluation_plan")
    except SchemaValidationError as exc:
        raise AIOnlyEvaluationError(str(exc)) from exc
    if plan["status"] != "frozen":
        raise AIOnlyEvaluationError("Evaluation plan must be frozen before scoring runs")

    runs = list(records)
    if not runs:
        raise AIOnlyEvaluationError("At least one AI-only run record is required")
    configuration_ids = [item["configuration_id"] for item in plan["configurations"]]
    if len(configuration_ids) != len(set(configuration_ids)):
        raise AIOnlyEvaluationError("configuration_id values must be unique")
    configurations = set(configuration_ids)
    for item in plan["configurations"]:
        if item["prompt_sha256"] == "0" * 64:
            raise AIOnlyEvaluationError("Frozen plans cannot use a placeholder prompt SHA-256")
        placeholder_values = (
            item["model_registry_refs"]
            + [item["pipeline_version"]]
            + item["tool_versions"]
        )
        if any("replace" in value.lower() for value in placeholder_values):
            raise AIOnlyEvaluationError("Frozen plans cannot contain replace-* placeholders")
    repeat_k = plan["repetitions_per_case"]
    seen_runs: set[str] = set()
    seen_slots: set[tuple[str, str, str, int]] = set()
    currencies: set[str] = set()
    by_configuration: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for record in runs:
        try:
            validate_document(record, "ai_only_run_record")
        except SchemaValidationError as exc:
            raise AIOnlyEvaluationError(str(exc)) from exc
        if record["run_id"] in seen_runs:
            raise AIOnlyEvaluationError(f"Duplicate run_id: {record['run_id']}")
        seen_runs.add(record["run_id"])
        if record["configuration_id"] not in configurations:
            raise AIOnlyEvaluationError(
                f"Unregistered configuration_id: {record['configuration_id']}"
            )
        if record["repetition_index"] > repeat_k:
            raise AIOnlyEvaluationError("repetition_index exceeds frozen repetitions_per_case")
        slot = (
            record["benchmark_id"], record["review_id"],
            record["configuration_id"], record["repetition_index"]
        )
        if slot in seen_slots:
            raise AIOnlyEvaluationError(f"Duplicate review/configuration/repetition slot: {slot}")
        seen_slots.add(slot)
        case_ids = [item["case_id"] for item in record["case_results"]]
        if len(case_ids) != len(set(case_ids)):
            raise AIOnlyEvaluationError(f"Duplicate case_id in run {record['run_id']}")
        currencies.add(record["cost_currency"])
        by_configuration[record["configuration_id"]].append(record)
    if len(currencies) != 1:
        raise AIOnlyEvaluationError("All runs must use one cost currency")

    review_families: dict[tuple[str, str], str] = {}
    cross_configuration_cases: dict[tuple[str, str], set[str]] = {}
    for record in runs:
        review_key = (record["benchmark_id"], record["review_id"])
        previous_family = review_families.setdefault(review_key, record["review_family_id"])
        if previous_family != record["review_family_id"]:
            raise AIOnlyEvaluationError(f"Review family changed across runs: {review_key}")
        case_set = {item["case_id"] for item in record["case_results"]}
        previous_cases = cross_configuration_cases.setdefault(review_key, case_set)
        if previous_cases != case_set:
            raise AIOnlyEvaluationError(
                f"Configurations or repetitions use different case sets for {review_key}"
            )

    summaries: list[dict[str, Any]] = []
    incomplete: list[str] = []
    for configuration_id in sorted(configurations):
        config_runs = by_configuration.get(configuration_id, [])
        reviews: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for record in config_runs:
            reviews[record["review_id"]].append(record)
        for review_id, review_runs in reviews.items():
            repetitions = {record["repetition_index"] for record in review_runs}
            if repetitions != set(range(1, repeat_k + 1)):
                incomplete.append(f"{configuration_id}:{review_id}")
            case_sets = [set(item["case_id"] for item in record["case_results"]) for record in review_runs]
            if case_sets and any(case_set != case_sets[0] for case_set in case_sets[1:]):
                raise AIOnlyEvaluationError(
                    f"Repeated runs use different case sets for {configuration_id}:{review_id}"
                )

        cases = [item for record in config_runs for item in record["case_results"]]
        pair_agreements: list[float] = []
        all_repeat_correct: list[bool] = []
        for review_runs in reviews.values():
            indexed = {
                record["repetition_index"]: {
                    item["case_id"]: item for item in record["case_results"]
                }
                for record in review_runs
            }
            if len(indexed) < 2:
                continue
            case_ids = sorted(next(iter(indexed.values())))
            for left, right in combinations(sorted(indexed), 2):
                pair_agreements.append(mean(
                    indexed[left][case_id]["decision_sha256"]
                    == indexed[right][case_id]["decision_sha256"]
                    for case_id in case_ids
                ))
            if set(indexed) == set(range(1, repeat_k + 1)):
                all_repeat_correct.extend(
                    all(indexed[rep][case_id]["correct"] for rep in indexed)
                    for case_id in case_ids
                )

        total_cases = len(cases)
        answered = sum(item["answered"] for item in cases)
        correct = sum(item["correct"] for item in cases)
        critical = sum(item["critical_error"] for item in cases)
        false_exclusion = sum(item["false_exclusion"] for item in cases)
        unsupported = sum(item["unsupported_value"] for item in cases)
        abstained = sum(item["abstained"] for item in cases)
        summary = {
            "configuration_id": configuration_id,
            "runs": len(config_runs),
            "reviews": len(reviews),
            "review_families": len({record["review_family_id"] for record in config_runs}),
            "case_evaluations": total_cases,
            "accuracy": _rate(correct, total_cases),
            "coverage": _rate(answered, total_cases),
            "selective_accuracy": _rate(
                sum(item["correct"] for item in cases if item["answered"]), answered
            ),
            "abstention_rate": _rate(abstained, total_cases),
            "critical_error_rate": _rate(critical, total_cases),
            "false_exclusion_rate": _rate(false_exclusion, total_cases),
            "unsupported_value_rate": _rate(unsupported, total_cases),
            "pairwise_run_agreement": mean(pair_agreements) if pair_agreements else None,
            "all_repeats_correct_rate": mean(all_repeat_correct) if all_repeat_correct else None,
            "wall_clock_seconds_total": _sum(config_runs, "wall_clock_seconds"),
            "wall_clock_seconds_mean": mean(record["wall_clock_seconds"] for record in config_runs) if config_runs else None,
            "model_calls_total": int(_sum(config_runs, "model_calls")),
            "input_tokens_total": int(_sum(config_runs, "input_tokens")),
            "output_tokens_total": int(_sum(config_runs, "output_tokens")),
            "api_cost_total": _sum(config_runs, "api_cost"),
            "api_cost_mean": mean(record["api_cost"] for record in config_runs) if config_runs else None,
            "compute_cost_total": _sum(config_runs, "compute_cost"),
            "compute_cost_mean": mean(record["compute_cost"] for record in config_runs) if config_runs else None,
            "total_cost_total": _sum(config_runs, "api_cost") + _sum(config_runs, "compute_cost"),
            "total_cost_mean": mean(
                record["api_cost"] + record["compute_cost"] for record in config_runs
            ) if config_runs else None,
            "cost_currency": next(iter(currencies)),
        }
        summary["threshold_results"] = _threshold_results(
            summary, plan["release_thresholds"]
        )
        summary["thresholds_passed"] = all(
            item["passed"] for item in summary["threshold_results"]
        )
        summaries.append(summary)

    complete = not incomplete and all(by_configuration.get(item) for item in configurations)
    return {
        "evaluation_design": "ai_only_repeated_runs",
        "plan_id": plan["plan_id"],
        "plan_version": plan["plan_version"],
        "complete": complete,
        "release_ready": complete and all(item["thresholds_passed"] for item in summaries),
        "incomplete_configuration_reviews": sorted(incomplete),
        "inference_scope": plan["inference_limits"]["allowed_claim"],
        "human_superiority_claim_permitted": False,
        "labor_savings_claim_permitted": False,
        "configurations": summaries,
    }
