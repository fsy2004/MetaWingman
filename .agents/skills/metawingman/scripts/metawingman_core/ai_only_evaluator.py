"""Aggregate AI-only repeated-run benchmark accuracy, reliability, time, and cost."""

from __future__ import annotations

from collections import defaultdict
import hashlib
from itertools import combinations
import json
from statistics import mean
from typing import Any, Iterable

from .schema_guard import SchemaValidationError, validate_document


class AIOnlyEvaluationError(ValueError):
    """Raised when AI-only run records violate the frozen evaluation design."""


def _rate(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def _optional_sum(records: list[dict[str, Any]], field: str) -> float | None:
    values = [record[field] for record in records]
    return None if any(value is None for value in values) else float(sum(values))


def _optional_mean(records: list[dict[str, Any]], field: str) -> float | None:
    values = [record[field] for record in records]
    return None if not values or any(value is None for value in values) else mean(values)


def _manifest_sha256(reviews: list[dict[str, Any]]) -> str:
    raw = json.dumps(reviews, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def question_synthesis_receipt_to_run_record(
    receipt: dict[str, Any],
    *,
    benchmark_id: str,
    review_id: str,
    review_family_id: str,
    repetition_index: int,
    case_result: dict[str, Any],
) -> dict[str, Any]:
    """Adapt one scored immutable slot without turning unknown cost into zero."""
    required = {
        "plan_id", "case_id", "configuration_id", "seed", "wall_time_seconds",
        "model_calls", "input_tokens", "output_tokens", "provider_cost",
        "provider_cost_status", "output_sha256",
    }
    missing = sorted(required - set(receipt))
    if missing:
        raise AIOnlyEvaluationError(f"question-synthesis receipt is incomplete: {missing}")
    if case_result.get("case_id") != receipt["case_id"]:
        raise AIOnlyEvaluationError("receipt and scored case_result case_id drift")
    provider_cost = receipt["provider_cost"]
    if receipt["provider_cost_status"] == "unknown":
        provider_cost = None
    return {
        "schema_version": "1.0",
        "run_id": f"{receipt['plan_id']}.{receipt['case_id']}.{receipt['configuration_id']}.{receipt['seed']}",
        "benchmark_id": benchmark_id,
        "review_id": review_id,
        "review_family_id": review_family_id,
        "configuration_id": receipt["configuration_id"],
        "repetition_index": repetition_index,
        "execution_mode": "ai_only",
        "human_interventions": 0,
        "case_results": [case_result],
        "wall_clock_seconds": receipt["wall_time_seconds"],
        "model_calls": receipt["model_calls"],
        "input_tokens": receipt["input_tokens"],
        "output_tokens": receipt["output_tokens"],
        "api_cost": provider_cost,
        "compute_cost": None,
        "cost_currency": "unknown" if provider_cost is None else "USD",
        "output_sha256": receipt["output_sha256"],
    }


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
    manifest = plan["expected_review_case_manifest"]
    if _manifest_sha256(manifest["reviews"]) != manifest["sha256"]:
        raise AIOnlyEvaluationError("expected review/case manifest SHA-256 drift")
    expected_reviews = {
        (item["benchmark_id"], item["review_id"]): {
            "review_family_id": item["review_family_id"],
            "case_ids": set(item["case_ids"]),
        }
        for item in manifest["reviews"]
    }
    if len(expected_reviews) != len(manifest["reviews"]):
        raise AIOnlyEvaluationError("duplicate expected review/case manifest entry")
    expected_configurations = {
        "general-model-baseline", "generic-retrieval", "biomedical-schema",
        "biomedical-routing", "full-biomedical-stack",
    }
    if configurations != expected_configurations:
        raise AIOnlyEvaluationError("Evaluation requires the exact five configurations")
    matched_budget_fields = (
        "max_model_calls",
        "max_input_tokens",
        "max_output_tokens",
        "retry_budget",
        "wall_time_ceiling_seconds",
    )
    budget_signatures = {
        tuple(item[field] for field in matched_budget_fields)
        for item in plan["configurations"]
    }
    if len(budget_signatures) != 1:
        raise AIOnlyEvaluationError(
            "All five configurations must use one matched budget ceiling"
        )
    model_signatures = {
        tuple(item["model_registry_refs"]) for item in plan["configurations"]
    }
    if len(model_signatures) != 1:
        raise AIOnlyEvaluationError(
            "All five configurations must use the same frozen model reference"
        )
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
            schema_record = record
            if record.get("api_cost") is None or record.get("compute_cost") is None:
                schema_record = dict(record)
                schema_record["api_cost"] = 0 if record.get("api_cost") is None else record["api_cost"]
                schema_record["compute_cost"] = 0 if record.get("compute_cost") is None else record["compute_cost"]
            validate_document(schema_record, "ai_only_run_record")
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
        if record["repetition_index"] < 1:
            raise AIOnlyEvaluationError("repetition_index must begin at one")
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
        if record["cost_currency"] != "unknown":
            currencies.add(record["cost_currency"])
        by_configuration[record["configuration_id"]].append(record)
    if len(currencies) > 1:
        raise AIOnlyEvaluationError("All runs must use one cost currency")

    review_families: dict[tuple[str, str], str] = {}
    cross_configuration_cases: dict[tuple[str, str], set[str]] = {}
    for record in runs:
        review_key = (record["benchmark_id"], record["review_id"])
        expected = expected_reviews.get(review_key)
        case_set = {item["case_id"] for item in record["case_results"]}
        if (
            expected is None
            or expected["review_family_id"] != record["review_family_id"]
            or expected["case_ids"] != case_set
        ):
            raise AIOnlyEvaluationError(
                f"run does not match expected review/case manifest: {review_key}"
            )
        previous_family = review_families.setdefault(review_key, record["review_family_id"])
        if previous_family != record["review_family_id"]:
            raise AIOnlyEvaluationError(f"Review family changed across runs: {review_key}")
        previous_cases = cross_configuration_cases.setdefault(review_key, case_set)
        if previous_cases != case_set:
            raise AIOnlyEvaluationError(
                f"Configurations or repetitions use different case sets for {review_key}"
            )

    summaries: list[dict[str, Any]] = []
    incomplete: list[str] = [
        f"{configuration_id}:missing_all_repetitions"
        for configuration_id in sorted(configurations - set(by_configuration))
    ]
    for configuration_id in sorted(configurations):
        config_runs = by_configuration.get(configuration_id, [])
        reviews: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for record in config_runs:
            reviews[record["review_id"]].append(record)
        for benchmark_id, review_id in expected_reviews:
            review_runs = [
                record for record in config_runs
                if record["benchmark_id"] == benchmark_id and record["review_id"] == review_id
            ]
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
            "wall_clock_seconds_total": _optional_sum(config_runs, "wall_clock_seconds"),
            "wall_clock_seconds_mean": mean(record["wall_clock_seconds"] for record in config_runs) if config_runs else None,
            "model_calls_total": int(_optional_sum(config_runs, "model_calls") or 0),
            "input_tokens_total": int(_optional_sum(config_runs, "input_tokens") or 0),
            "output_tokens_total": int(_optional_sum(config_runs, "output_tokens") or 0),
            "api_cost_total": _optional_sum(config_runs, "api_cost"),
            "api_cost_mean": _optional_mean(config_runs, "api_cost"),
            "compute_cost_total": _optional_sum(config_runs, "compute_cost"),
            "compute_cost_mean": _optional_mean(config_runs, "compute_cost"),
            "total_cost_total": None,
            "total_cost_mean": None,
            "cost_currency": next(iter(currencies)) if currencies else "unknown",
        }
        if summary["api_cost_total"] is not None and summary["compute_cost_total"] is not None:
            summary["total_cost_total"] = summary["api_cost_total"] + summary["compute_cost_total"]
            summary["total_cost_mean"] = (
                summary["total_cost_total"] / len(config_runs) if config_runs else None
            )
        summary["cost_status"] = (
            "known" if summary["total_cost_total"] is not None else "unknown"
        )
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
