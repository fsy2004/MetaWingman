"""Select a diverse portfolio of review topics from a time-bounded evidence landscape."""

from __future__ import annotations

import re
from datetime import date, datetime, timezone
from typing import Any

from .schema_guard import SchemaValidationError, validate_document
from .state_store import sha256_json


POSITIVE_SIGNALS = (
    "decision_relevance",
    "unresolved_uncertainty",
    "feasibility",
    "evidence_maturity",
    "nonduplication",
    "update_need",
    "equity_priority",
    "cross_domain_value",
)
STRICTLY_SEALED_IDENTITY_FIELDS = {
    "title", "authors", "doi", "pmid", "journal", "abstract", "keywords",
    "citations", "descendants",
}


class TopicOpportunityError(ValueError):
    """Raised when a topic landscape or candidate set is unsafe to evaluate."""


def validate_topic_landscape(
    landscape: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    """Validate a temporal landscape and return its node index."""
    return _validate_landscape(landscape)


def _parse_date(value: str) -> date:
    return date.fromisoformat(value)


def _validate_landscape(landscape: dict[str, Any]) -> dict[str, dict[str, Any]]:
    try:
        validate_document(landscape, "temporal_evidence_landscape")
    except SchemaValidationError as exc:
        raise TopicOpportunityError(str(exc)) from exc

    weights = landscape["selection_policy"]["weights"]
    if abs(sum(float(value) for value in weights.values()) - 1.0) > 1e-6:
        raise TopicOpportunityError("selection-policy weights must sum to 1.0")

    node_ids = [item["node_id"] for item in landscape["nodes"]]
    edge_ids = [item["edge_id"] for item in landscape["edges"]]
    if len(node_ids) != len(set(node_ids)):
        raise TopicOpportunityError("node_id values must be unique")
    if len(edge_ids) != len(set(edge_ids)):
        raise TopicOpportunityError("edge_id values must be unique")

    cutoff = _parse_date(landscape["corpus_boundary"]["cutoff_date"])
    domain_ids = set(landscape["domain_ids"])
    nodes = {item["node_id"]: item for item in landscape["nodes"]}
    for node in landscape["nodes"]:
        if not set(node["domain_ids"]).issubset(domain_ids):
            raise TopicOpportunityError(
                f"node {node['node_id']} declares a domain outside landscape.domain_ids"
            )
        if _parse_date(node["observed_at"]) > cutoff:
            raise TopicOpportunityError(
                f"node {node['node_id']} is post-cutoff evidence"
            )
    for edge in landscape["edges"]:
        unknown = {
            edge["source_node_id"], edge["target_node_id"]
        } - set(nodes)
        if unknown:
            raise TopicOpportunityError(
                f"edge {edge['edge_id']} references unknown nodes: {sorted(unknown)}"
            )
        if _parse_date(edge["observed_at"]) > cutoff:
            raise TopicOpportunityError(
                f"edge {edge['edge_id']} is post-cutoff evidence"
            )

    if landscape["run_context"] == "historical_rediscovery":
        boundary = landscape["corpus_boundary"]
        if boundary["target_identity_status"] != "sealed":
            raise TopicOpportunityError("historical target identity is not sealed")
        if boundary["target_descendants_status"] != "sealed":
            raise TopicOpportunityError("historical target descendants are not sealed")
        if boundary["post_cutoff_evidence_status"] != "sealed":
            raise TopicOpportunityError("historical post-cutoff evidence is not sealed")
        if boundary["leakage_audit"] != "passed":
            raise TopicOpportunityError("historical leakage audit has not passed")
        missing = STRICTLY_SEALED_IDENTITY_FIELDS - set(boundary["excluded_identity_fields"])
        if missing:
            raise TopicOpportunityError(
                f"historical identity exclusion is incomplete: {sorted(missing)}"
            )
    return nodes


def _validate_candidates(
    landscape: dict[str, Any],
    candidates: list[dict[str, Any]],
    nodes: dict[str, dict[str, Any]],
) -> None:
    if not candidates:
        raise TopicOpportunityError("at least one topic candidate is required")
    candidate_ids: set[str] = set()
    historical = landscape["run_context"] == "historical_rediscovery"
    for candidate in candidates:
        try:
            validate_document(candidate, "topic_candidate")
        except SchemaValidationError as exc:
            raise TopicOpportunityError(str(exc)) from exc
        candidate_id = candidate["candidate_id"]
        if candidate_id in candidate_ids:
            raise TopicOpportunityError(f"duplicate candidate_id: {candidate_id}")
        candidate_ids.add(candidate_id)
        if candidate["landscape_id"] != landscape["landscape_id"]:
            raise TopicOpportunityError(
                f"candidate {candidate_id} belongs to another landscape"
            )
        referenced = set(candidate["concept_node_ids"]) | set(candidate["evidence_node_ids"])
        for signal in candidate["signals"].values():
            referenced.update(signal["evidence_node_ids"])
            if signal["calibration_status"] == "unavailable" and signal["value"] is not None:
                raise TopicOpportunityError(
                    f"candidate {candidate_id} has a value for an unavailable signal"
                )
            if signal["calibration_status"] != "unavailable" and signal["value"] is None:
                raise TopicOpportunityError(
                    f"candidate {candidate_id} has a missing value for an available signal"
                )
        unknown = referenced - set(nodes)
        if unknown:
            raise TopicOpportunityError(
                f"candidate {candidate_id} references unknown nodes: {sorted(unknown)}"
            )
        independent = candidate["feasibility_evidence"]["independent_source_families"]
        if independent != len(candidate["source_family_ids"]):
            raise TopicOpportunityError(
                f"candidate {candidate_id} source-family count does not match source_family_ids"
            )
        if historical:
            leakage = candidate["leakage_checks"]
            exposed = any(
                leakage[field]
                for field in (
                    "target_title_seen", "target_authors_seen", "target_identifier_seen",
                    "target_descendant_seen", "post_cutoff_source_seen",
                )
            )
            if leakage["audit_status"] != "passed" or exposed:
                raise TopicOpportunityError(
                    f"candidate {candidate_id} failed the historical leakage boundary"
                )


def _eligibility_reasons(
    candidate: dict[str, Any],
    policy: dict[str, Any],
) -> list[str]:
    reasons: list[str] = []
    feasibility = candidate["feasibility_evidence"]
    overlap = candidate["overlap_evidence"]
    signals = candidate["signals"]
    leakage = candidate["leakage_checks"]

    if candidate["operationalization"]["status"] != "complete":
        reasons.append("question_framework_not_operational")
    if feasibility["primary_study_count"] < policy["minimum_primary_studies"]:
        reasons.append("insufficient_primary_studies")
    if feasibility["independent_source_families"] < policy["minimum_source_families"]:
        reasons.append("insufficient_source_family_coverage")
    if feasibility["known_item_recall"] is None:
        reasons.append("known_item_recall_unavailable")
    elif feasibility["known_item_recall"] < policy["minimum_known_item_recall"]:
        reasons.append("known_item_recall_below_floor")

    update_is_justified = (
        policy["allow_update_topics"]
        and bool(overlap["update_justification"].strip())
        and signals["update_need"]["value"] is not None
        and signals["update_need"]["value"] > 0
    )
    if (
        overlap["maximum_existing_review_overlap"] > policy["maximum_review_overlap"]
        and not update_is_justified
    ):
        reasons.append("existing_review_overlap_above_ceiling")
    if overlap["active_protocol_overlap"] and not update_is_justified:
        reasons.append("active_review_protocol_overlap")

    contamination = signals["contamination_risk"]["value"]
    ambiguity = signals["ambiguity_risk"]["value"]
    if contamination is None:
        reasons.append("contamination_risk_unavailable")
    elif contamination > policy["maximum_contamination_risk"]:
        reasons.append("contamination_risk_above_ceiling")
    if ambiguity is None:
        reasons.append("ambiguity_risk_unavailable")
    elif ambiguity > policy["maximum_ambiguity_risk"]:
        reasons.append("ambiguity_risk_above_ceiling")

    for name in POSITIVE_SIGNALS:
        if signals[name]["value"] is None:
            reasons.append(f"{name}_unavailable")
    if leakage["audit_status"] in {"not_run", "failed"}:
        reasons.append("candidate_leakage_audit_not_passed")
    if any(
        leakage[field]
        for field in (
            "target_title_seen", "target_authors_seen", "target_identifier_seen",
            "target_descendant_seen", "post_cutoff_source_seen",
        )
    ):
        reasons.append("candidate_identity_or_temporal_leakage")
    return sorted(set(reasons))


def _score(
    candidate: dict[str, Any],
    weights: dict[str, float],
) -> tuple[float, dict[str, float]]:
    contamination = float(candidate["signals"]["contamination_risk"]["value"])
    ambiguity = float(candidate["signals"]["ambiguity_risk"]["value"])
    reliability = (1.0 - contamination) * (1.0 - ambiguity)
    contributions = {
        name: round(
            float(weights[name]) * float(candidate["signals"][name]["value"]) * reliability,
            8,
        )
        for name in POSITIVE_SIGNALS
    }
    return round(sum(contributions.values()), 8), contributions


def _normalise(value: str) -> str:
    return re.sub(r"\s+", " ", value.casefold().strip())


def _topic_terms(candidate: dict[str, Any]) -> set[str]:
    terms = {_normalise(item) for item in candidate["concept_node_ids"]}
    for field, values in candidate["question_framework"].items():
        if field == "synthesis_route":
            terms.add(_normalise(values))
        else:
            terms.update(_normalise(value) for value in values)
    return terms


def _similarity(left: dict[str, Any], right: dict[str, Any]) -> float:
    left_terms = _topic_terms(left)
    right_terms = _topic_terms(right)
    union = left_terms | right_terms
    return len(left_terms & right_terms) / len(union) if union else 0.0


def select_topic_portfolio(
    landscape: dict[str, Any],
    candidates: list[dict[str, Any]],
    *,
    created_at_utc: str | None = None,
) -> dict[str, Any]:
    """Apply frozen gates and diversity-aware ranking to evidence-grounded topics."""
    nodes = _validate_landscape(landscape)
    _validate_candidates(landscape, candidates, nodes)
    policy = landscape["selection_policy"]
    weights = policy["weights"]
    by_id = {item["candidate_id"]: item for item in candidates}
    rows: dict[str, dict[str, Any]] = {}

    for candidate in candidates:
        reasons = _eligibility_reasons(candidate, policy)
        candidate_id = candidate["candidate_id"]
        if reasons:
            rows[candidate_id] = {
                "candidate_id": candidate_id,
                "eligible": False,
                "base_utility": None,
                "marginal_utility": None,
                "rank": None,
                "selected": False,
                "component_contributions": {},
                "reason_codes": reasons,
            }
            continue
        utility, contributions = _score(candidate, weights)
        reason_codes = ["eligible_evidence_grounded_topic"]
        if any(
            candidate["signals"][name]["calibration_status"] == "heuristic"
            for name in (*POSITIVE_SIGNALS, "contamination_risk", "ambiguity_risk")
        ):
            reason_codes.append("heuristic_signal_requires_calibration")
        rows[candidate_id] = {
            "candidate_id": candidate_id,
            "eligible": True,
            "base_utility": utility,
            "marginal_utility": None,
            "rank": None,
            "selected": False,
            "component_contributions": contributions,
            "reason_codes": reason_codes,
        }

    eligible_ids = sorted(
        (candidate_id for candidate_id, row in rows.items() if row["eligible"]),
        key=lambda candidate_id: (-rows[candidate_id]["base_utility"], candidate_id),
    )
    for rank, candidate_id in enumerate(eligible_ids, start=1):
        rows[candidate_id]["rank"] = rank

    selected: list[str] = []
    remaining = {
        candidate_id for candidate_id in eligible_ids
        if rows[candidate_id]["base_utility"] >= policy["minimum_utility_score"]
    }
    while remaining and len(selected) < policy["maximum_portfolio_size"]:
        scored: list[tuple[float, float, str]] = []
        for candidate_id in remaining:
            max_similarity = max(
                (_similarity(by_id[candidate_id], by_id[item]) for item in selected),
                default=0.0,
            )
            marginal = round(
                rows[candidate_id]["base_utility"]
                - policy["diversity_penalty"] * max_similarity,
                8,
            )
            scored.append((marginal, rows[candidate_id]["base_utility"], candidate_id))
        marginal, _, chosen = sorted(scored, key=lambda item: (-item[0], -item[1], item[2]))[0]
        if marginal < policy["minimum_utility_score"]:
            break
        selected.append(chosen)
        remaining.remove(chosen)
        rows[chosen]["selected"] = True
        rows[chosen]["marginal_utility"] = marginal
        rows[chosen]["reason_codes"].append("selected_for_diverse_topic_portfolio")

    for candidate_id in eligible_ids:
        if rows[candidate_id]["selected"]:
            continue
        max_similarity = max(
            (_similarity(by_id[candidate_id], by_id[item]) for item in selected),
            default=0.0,
        )
        rows[candidate_id]["marginal_utility"] = round(
            rows[candidate_id]["base_utility"]
            - policy["diversity_penalty"] * max_similarity,
            8,
        )
        if rows[candidate_id]["base_utility"] < policy["minimum_utility_score"]:
            rows[candidate_id]["reason_codes"].append("base_utility_below_frozen_floor")
        else:
            rows[candidate_id]["reason_codes"].append("not_selected_by_portfolio_policy")

    timestamp = created_at_utc or datetime.now(timezone.utc).isoformat()
    historical = landscape["run_context"] == "historical_rediscovery"
    decision = {
        "schema_version": "1.0",
        "decision_id": f"{landscape['landscape_id']}-topic-decision",
        "landscape_id": landscape["landscape_id"],
        "landscape_sha256": sha256_json(landscape),
        "candidate_set_sha256": sha256_json(sorted(candidates, key=lambda item: item["candidate_id"])),
        "policy_version": policy["policy_version"],
        "status": "portfolio_selected" if selected else "abstain",
        "ranked_candidates": sorted(
            rows.values(),
            key=lambda row: (
                not row["eligible"],
                row["rank"] if row["rank"] is not None else 10**9,
                row["candidate_id"],
            ),
        ),
        "selected_candidate_ids": selected,
        "reason_codes": (
            ["frozen_topic_policy_selected_diverse_portfolio"]
            if selected else
            ["no_candidate_met_frozen_topic_policy"]
        ),
        "oversight_boundary": {
            "mode": "post_run_reference_only" if historical else "final_topic_signature",
            "intervention_during_run_allowed": False,
            "final_topic_signature_required": not historical,
        },
        "created_at_utc": timestamp,
    }
    try:
        validate_document(decision, "topic_opportunity_decision")
    except SchemaValidationError as exc:
        raise TopicOpportunityError(str(exc)) from exc
    return decision
