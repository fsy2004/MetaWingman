"""Evaluate time-sealed reconstruction of a published systematic-review topic."""

from __future__ import annotations

import re
from typing import Any

from .schema_guard import SchemaValidationError, validate_document


FIELDS = (
    "population",
    "intervention_or_exposure",
    "comparator",
    "outcome",
    "study_design",
    "synthesis_route",
)


class TopicRediscoveryError(ValueError):
    """Raised when a rediscovery case violates its sealed evaluation contract."""


def _normalise(value: str) -> str:
    return re.sub(r"\s+", " ", value.casefold().strip())


def _set_similarity(left: list[str], right: list[str]) -> float:
    stopwords = {"a", "an", "and", "for", "in", "of", "or", "the", "to", "with"}
    def tokens(values: list[str]) -> set[str]:
        output = {
            token for item in values for token in re.findall(r"[a-z0-9]+", _normalise(item))
            if token not in stopwords
        }
        return output or {_normalise(item) for item in values if _normalise(item)}
    left_set = tokens(left)
    right_set = tokens(right)
    union = left_set | right_set
    return len(left_set & right_set) / len(union) if union else 0.0


def _field_similarities(
    predicted: dict[str, Any],
    reference: dict[str, Any],
    accepted: dict[str, list[str]] | None = None,
) -> dict[str, float]:
    output = {
        field: round(max(
            [_set_similarity(predicted[field], reference[field])]
            + ([_set_similarity(predicted[field], [term]) for term in accepted[field]] if accepted else [])
        ), 8)
        for field in FIELDS if field != "synthesis_route"
    }
    accepted_routes = [reference["synthesis_route"], *(accepted["synthesis_route"] if accepted else [])]
    output["synthesis_route"] = float(any(
        _normalise(predicted["synthesis_route"]) == _normalise(route)
        for route in accepted_routes
    ))
    return output


def evaluate_topic_rediscovery(case: dict[str, Any]) -> dict[str, Any]:
    """Score framework-level concordance without comparing answer-bearing titles."""
    try:
        validate_document(case, "topic_rediscovery_case")
    except SchemaValidationError as exc:
        raise TopicRediscoveryError(str(exc)) from exc

    ranks = [item["rank"] for item in case["ranked_predictions"]]
    if len(ranks) != len(set(ranks)) or sorted(ranks) != list(range(1, len(ranks) + 1)):
        raise TopicRediscoveryError("prediction ranks must be unique and contiguous from one")
    weights = case["evaluation_policy"]["field_weights"]
    if abs(sum(float(value) for value in weights.values()) - 1.0) > 1e-6:
        raise TopicRediscoveryError("field weights must sum to 1.0")

    reference = case["sealed_reference"]["question_framework"]
    accepted = case["sealed_reference"].get("accepted_term_sets")
    scored: list[tuple[float, int, str, dict[str, float]]] = []
    for prediction in case["ranked_predictions"]:
        similarities = _field_similarities(prediction["question_framework"], reference, accepted)
        score = round(sum(weights[field] * similarities[field] for field in FIELDS), 8)
        scored.append((score, prediction["rank"], prediction["candidate_id"], similarities))
    scored.sort(key=lambda item: (-item[0], item[1], item[2]))
    best_score, _, best_id, best_fields = scored[0]
    threshold = case["evaluation_policy"]["minimum_framework_similarity"]
    matching_ranks = sorted(rank for score, rank, _, _ in scored if score >= threshold)
    top_k_hits = {
        str(k): any(rank <= k for rank in matching_ranks)
        for k in sorted(case["evaluation_policy"]["top_k"])
    }
    exact = all(value == 1.0 for value in best_fields.values())
    reasons = [
        "published_topic_reconstructed_within_framework_threshold"
        if matching_ranks else
        "no_prediction_met_framework_threshold"
    ]
    if exact:
        reasons.append("exact_normalized_framework_match")
    if case["sealed_reference"]["reference_status"] == "published_expert_reference":
        reasons.append("published_expert_reference_is_not_an_oracle")
    else:
        reasons.append("published_reference_uses_verified_correction")
    memory = case["model_memory_boundary"]
    prospective_support = (
        case["split"] == "prospective"
        and memory["model_version_frozen"]
        and memory["prospective_run_registered_before_reference"]
    )
    historical_support = (
        case["split"] != "prospective"
        and memory["model_version_frozen"]
        and memory["training_cutoff_status"] == "documented_before_target"
        and memory["memorization_probe"] == "passed_no_target_recall"
        and memory["contamination_risk"] == "low"
    )
    independence_supported = prospective_support or historical_support
    reasons.append(
        "independent_discovery_boundary_supported"
        if independence_supported else
        "model_memory_contamination_not_excluded"
    )

    report = {
        "schema_version": "1.0",
        "case_id": case["case_id"],
        "reference_status": case["sealed_reference"]["reference_status"],
        "venue_stratum": case["sealed_reference"]["venue_stratum"],
        "top_k_hits": top_k_hits,
        "first_matching_rank": matching_ranks[0] if matching_ranks else None,
        "best_candidate_id": best_id,
        "best_framework_similarity": best_score,
        "exact_framework_hit": exact,
        "best_field_similarities": best_fields,
        "independence_claim_status": "supported" if independence_supported else "not_supported",
        "reason_codes": reasons,
    }
    try:
        validate_document(report, "topic_rediscovery_report")
    except SchemaValidationError as exc:
        raise TopicRediscoveryError(str(exc)) from exc
    return report
