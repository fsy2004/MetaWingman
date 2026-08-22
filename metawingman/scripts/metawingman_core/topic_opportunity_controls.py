"""Matched-candidate direct controls for the topic-opportunity policy."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable

from .state_store import sha256_json
from .topic_opportunity import select_topic_portfolio


def _baseline_selection(
    candidates: list[dict[str, Any]],
    *,
    key: Callable[[dict[str, Any]], float],
    maximum: int,
) -> list[str]:
    ranked = sorted(candidates, key=lambda item: (-key(item), item["candidate_id"]))
    return [str(item["candidate_id"]) for item in ranked[:maximum]]


def _metrics(
    selected: list[str],
    *,
    targets: set[str],
    false_opportunities: set[str],
) -> dict[str, Any]:
    return {
        "selected_candidate_ids": selected,
        "target_hit_at_1": bool(selected and selected[0] in targets),
        "target_hit_at_3": any(item in targets for item in selected[:3]),
        "false_opportunity_rate": (
            sum(item in false_opportunities for item in selected) / len(selected)
            if selected else 0.0
        ),
        "selected_count": len(selected),
    }


def _decision_selection(
    landscape: dict[str, Any],
    candidates: list[dict[str, Any]],
    *,
    created_at_utc: str | None,
) -> list[str]:
    decision = select_topic_portfolio(
        landscape, candidates, created_at_utc=created_at_utc,
    )
    return list(decision["selected_candidate_ids"])


def evaluate_topic_control_arms(
    landscape: dict[str, Any],
    candidates: list[dict[str, Any]],
    *,
    target_candidate_ids: set[str],
    false_opportunity_candidate_ids: set[str],
    created_at_utc: str | None = None,
) -> dict[str, Any]:
    """Run transparent baselines and one-component ablations on one locked set.

    These arms isolate ranking and gate behavior. They do not evaluate candidate
    generation and make no provider calls.
    """
    ids = {str(item["candidate_id"]) for item in candidates}
    unknown = (target_candidate_ids | false_opportunity_candidate_ids) - ids
    if unknown:
        raise ValueError(f"control labels reference unknown candidates: {sorted(unknown)}")
    maximum = int(landscape["selection_policy"]["maximum_portfolio_size"])
    arms: dict[str, list[str]] = {
        "bibliometric-count": _baseline_selection(
            candidates,
            key=lambda item: float(item["feasibility_evidence"]["primary_study_count"]),
            maximum=maximum,
        ),
        "semantic-gap": _baseline_selection(
            candidates,
            key=lambda item: float(item["signals"]["unresolved_uncertainty"]["value"] or 0.0),
            maximum=maximum,
        ),
        "graph-only": _baseline_selection(
            candidates,
            key=lambda item: float(item["signals"]["cross_domain_value"]["value"] or 0.0),
            maximum=maximum,
        ),
        "llm-proposal-order": [str(item["candidate_id"]) for item in candidates[:maximum]],
        "full-decision-aware": _decision_selection(
            landscape, candidates, created_at_utc=created_at_utc,
        ),
    }

    without_overlap = deepcopy(candidates)
    for item in without_overlap:
        item["overlap_evidence"]["maximum_existing_review_overlap"] = 0.0
        item["overlap_evidence"]["active_protocol_overlap"] = False
    arms["without-overlap-opposition"] = _decision_selection(
        landscape, without_overlap, created_at_utc=created_at_utc,
    )

    without_decision = deepcopy(landscape)
    weights = without_decision["selection_policy"]["weights"]
    weights["decision_relevance"] = 0.0
    denominator = sum(float(value) for value in weights.values())
    for name in weights:
        weights[name] = float(weights[name]) / denominator
    arms["without-decision-relevance"] = _decision_selection(
        without_decision, candidates, created_at_utc=created_at_utc,
    )

    without_diversity = deepcopy(landscape)
    without_diversity["selection_policy"]["diversity_penalty"] = 0.0
    arms["without-portfolio-diversity"] = _decision_selection(
        without_diversity, candidates, created_at_utc=created_at_utc,
    )

    return {
        "schema_version": "1.0-development-direct-control",
        "landscape_sha256": sha256_json(landscape),
        "candidate_set_sha256": sha256_json(
            sorted(candidates, key=lambda item: item["candidate_id"])
        ),
        "comparison_boundary": "matched_locked_candidate_set_ranking_and_gates_only",
        "provider_calls": 0,
        "arms": {
            name: _metrics(
                selected,
                targets=target_candidate_ids,
                false_opportunities=false_opportunity_candidate_ids,
            )
            for name, selected in arms.items()
        },
    }
