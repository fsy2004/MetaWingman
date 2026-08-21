"""Leakage-safe direct and selective metrics for joint-design evaluation."""

from __future__ import annotations

import hashlib
import unicodedata
from collections.abc import Iterator
from datetime import datetime
from typing import Any

from .schema_guard import SchemaValidationError, validate_document


class QuestionSynthesisBenchmarkError(ValueError):
    """Raised when a benchmark case or run violates its frozen boundary."""


def _dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _normalized(value: str) -> str:
    return unicodedata.normalize("NFKC", value).casefold()


def _string_values(value: Any) -> Iterator[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _string_values(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _string_values(item)


def _case_closure(case: dict[str, Any]) -> set[str]:
    identifiers = {
        case["review_family_id"],
        *case["dependency_family_ids"],
        *case["graph_node_ids"],
        *case["descendant_source_record_ids"],
    }
    return {_normalized(identifier) for identifier in identifiers}


def validate_benchmark_case(case: dict[str, Any]) -> None:
    try:
        validate_document(case, "question_synthesis_benchmark_case")
    except SchemaValidationError as exc:
        raise QuestionSynthesisBenchmarkError(str(exc)) from exc
    if case["status"] != "sealed":
        raise QuestionSynthesisBenchmarkError("benchmark case is not sealed")

    graph_nodes = set(case["graph_node_ids"])
    source_records = set(case["descendant_source_record_ids"])
    for item in case["visible_material"]:
        actual_hash = hashlib.sha256(item["text"].encode("utf-8")).hexdigest()
        if actual_hash != item["sha256"]:
            raise QuestionSynthesisBenchmarkError("visible material SHA-256 mismatch")
        if not set(item["source_node_ids"]).issubset(graph_nodes):
            raise QuestionSynthesisBenchmarkError("visible source node is outside the declared graph closure")
        if not set(item["source_record_ids"]).issubset(source_records):
            raise QuestionSynthesisBenchmarkError("visible source record is outside the declared record closure")

    cutoff = _dt(case["cutoff_at_utc"])
    visible_surface = {
        "case_id": case["case_id"],
        "review_family_id": case["review_family_id"],
        "dependency_family_ids": case["dependency_family_ids"],
        "graph_node_ids": case["graph_node_ids"],
        "descendant_source_record_ids": case["descendant_source_record_ids"],
        "visible_material": case["visible_material"],
    }
    visible_values = [_normalized(value) for value in _string_values(visible_surface)]
    patterns = list(case["leakage_patterns"])
    target = case["sealed_target"]
    patterns.extend([target["title"], target["doi"], *target["authors"], *target.get("identifiers", [])])
    if any(_normalized(pattern) in value for pattern in patterns for value in visible_values):
        raise QuestionSynthesisBenchmarkError("sealed target identity appears in visible material")
    if any(_dt(item["observed_at_utc"]) > cutoff for item in case["visible_material"]):
        raise QuestionSynthesisBenchmarkError("visible material is post-cutoff")


def validate_family_isolation(cases: list[dict[str, Any]]) -> None:
    assignments: dict[str, set[str]] = {}
    case_ids: set[str] = set()
    for case in cases:
        validate_benchmark_case(case)
        if case["case_id"] in case_ids:
            raise QuestionSynthesisBenchmarkError("duplicate benchmark case_id")
        case_ids.add(case["case_id"])
        for identifier in _case_closure(case):
            assignments.setdefault(identifier, set()).add(case["split"])
    conflicts = {identifier: splits for identifier, splits in assignments.items() if len(splits) > 1}
    if conflicts:
        raise QuestionSynthesisBenchmarkError("family/dependency closure crosses benchmark splits")


def score_open_rubric(outcome: str, rubric: dict[str, float]) -> float:
    if outcome not in rubric:
        raise QuestionSynthesisBenchmarkError(f"outcome is not registered in rubric: {outcome}")
    return float(rubric[outcome])


def selective_curve(rows: list[dict[str, Any]]) -> list[dict[str, float]]:
    if not rows:
        return []
    ordered = sorted(rows, key=lambda row: (-float(row["confidence"]), str(row["case_id"])))
    return [
        {
            "coverage": end / len(ordered),
            "risk": sum(float(item["loss"]) for item in ordered[:end]) / end,
        }
        for end in range(1, len(ordered) + 1)
    ]


def evaluate_question_portfolio(case: dict[str, Any], run: dict[str, Any], rubric: dict[str, float] | None = None) -> dict[str, Any]:
    validate_benchmark_case(case)
    active_rubric = rubric or case["loss_rubric"]
    if run.get("status") == "abstained":
        outcome = "abstain"
    else:
        candidate = run.get("candidate") or {}
        reference = case["published_reference"]
        hard_failures = [item for item in run.get("verifier_observations", []) if item.get("status") == "failed"]
        matched = candidate.get("review_family") == reference["review_family"] and candidate.get("synthesis_route") == reference["synthesis_route"]
        outcome = "correct" if matched and not hard_failures else "critical_error"
    score = score_open_rubric(outcome, active_rubric)
    return {
        "case_id": case["case_id"],
        "review_family_id": case["review_family_id"],
        "split": case["split"],
        "configuration_id": run.get("configuration_id"),
        "seed": run.get("seed"),
        "outcome": outcome,
        "score": score,
        "loss": -score,
        "confidence": float(run.get("confidence", 0.0)),
        "wall_time_seconds": float(run.get("wall_time_seconds", 0.0)),
        "provider_tokens": int(run.get("provider_tokens", 0)),
        "provider_cost": float(run.get("provider_cost", 0.0)),
        "gpu_seconds": float(run.get("gpu_seconds", 0.0)),
        "peak_memory_bytes": int(run.get("peak_memory_bytes", 0)),
        "storage_growth_bytes": int(run.get("storage_growth_bytes", 0)),
    }


def aggregate_question_benchmark(reports: list[dict[str, Any]]) -> dict[str, Any]:
    if not reports:
        raise QuestionSynthesisBenchmarkError("at least one report is required")
    correct = sum(item["outcome"] == "correct" for item in reports)
    critical = sum(item["outcome"] == "critical_error" for item in reports)
    abstained = sum(item["outcome"] == "abstain" for item in reports)
    return {
        "runs": len(reports),
        "correct_fraction": correct / len(reports),
        "critical_error_fraction": critical / len(reports),
        "abstention_fraction": abstained / len(reports),
        "mean_score": sum(float(item["score"]) for item in reports) / len(reports),
        "total_wall_time_seconds": sum(float(item["wall_time_seconds"]) for item in reports),
        "total_provider_tokens": sum(int(item["provider_tokens"]) for item in reports),
        "total_provider_cost": sum(float(item["provider_cost"]) for item in reports),
        "peak_memory_bytes": max(int(item["peak_memory_bytes"]) for item in reports),
        "selective_curve": selective_curve(reports),
    }
