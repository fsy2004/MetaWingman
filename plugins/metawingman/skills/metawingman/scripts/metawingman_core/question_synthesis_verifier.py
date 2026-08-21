"""External source and executable observations for question-synthesis candidates."""

from __future__ import annotations

from typing import Any, Callable


class QuestionSynthesisVerificationError(ValueError):
    """Raised when a consequential candidate lacks an external verification path."""


def _observation(verifier_id: str, status: str, reason: str, anchors: list[str]) -> dict[str, Any]:
    return {
        "verifier_id": verifier_id,
        "status": status,
        "reason": reason,
        "evidence_anchor_ids": sorted(set(anchors)),
        "external": True,
    }


def verify_evidence_anchor_identity(candidate: dict[str, Any], landscape: dict[str, Any], route: dict[str, Any]) -> dict[str, Any]:
    known = {str(item.get("node_id")) for item in landscape.get("nodes", [])}
    anchors = list(candidate.get("evidence_anchor_ids", []))
    unknown = sorted(set(anchors) - known)
    return _observation("evidence_anchor_identity", "failed" if unknown else "passed", f"unknown={unknown}" if unknown else "all anchors resolve", anchors)


def verify_temporal_cutoff(candidate: dict[str, Any], landscape: dict[str, Any], route: dict[str, Any]) -> dict[str, Any]:
    cutoff = landscape.get("corpus_boundary", {}).get("cutoff_date")
    return _observation("temporal_cutoff", "passed" if cutoff else "unknown", "cutoff recorded" if cutoff else "cutoff unavailable", list(candidate.get("evidence_anchor_ids", [])))


def verify_review_family_compatibility(candidate: dict[str, Any], landscape: dict[str, Any], route: dict[str, Any]) -> dict[str, Any]:
    rejected = {item.get("route_id"): item.get("failed_checks", []) for item in route.get("rejected_routes", [])}
    failed = "review_family_compatibility" in rejected.get(candidate.get("synthesis_route"), [])
    return _observation("review_family_compatibility", "failed" if failed else "passed", "route family rejected" if failed else "route family compatible", list(candidate.get("evidence_anchor_ids", [])))


def verify_estimand_completeness(candidate: dict[str, Any], landscape: dict[str, Any], route: dict[str, Any]) -> dict[str, Any]:
    estimand = candidate.get("estimand") or {}
    required = {"population", "treatment_condition", "variable", "population_summary", "intercurrent_event_strategy"}
    missing = sorted(field for field in required if not str(estimand.get(field) or "").strip())
    return _observation("estimand_completeness", "failed" if missing else "passed", f"missing={missing}" if missing else "estimand complete", list(candidate.get("evidence_anchor_ids", [])))


def verify_synthesis_route(candidate: dict[str, Any], landscape: dict[str, Any], route: dict[str, Any]) -> dict[str, Any]:
    compatible = {item.get("route_id") for item in route.get("compatible_routes", [])}
    candidate_route = candidate.get("synthesis_route")
    accepted = candidate_route in compatible and route.get("status") != "abstained"
    return _observation("synthesis_route", "passed" if accepted else "failed", "route accepted by deterministic router" if accepted else "route is not externally executable", list(candidate.get("evidence_anchor_ids", [])))


def verify_overlap_and_active_protocols(candidate: dict[str, Any], landscape: dict[str, Any], route: dict[str, Any]) -> dict[str, Any]:
    status = candidate.get("overlap", {}).get("status")
    passed = status in {"not_duplicative", "justified_update", "verified"}
    return _observation("overlap_and_active_protocols", "passed" if passed else "unknown", str(status or "unavailable"), list(candidate.get("evidence_anchor_ids", [])))


def verify_access_and_extractability(candidate: dict[str, Any], landscape: dict[str, Any], route: dict[str, Any]) -> dict[str, Any]:
    status = candidate.get("feasibility", {}).get("status")
    passed = status == "verified"
    return _observation("access_and_extractability", "passed" if passed else "unknown", str(status or "unavailable"), list(candidate.get("evidence_anchor_ids", [])))


VERIFIERS: tuple[Callable[[dict[str, Any], dict[str, Any], dict[str, Any]], dict[str, Any]], ...] = (
    verify_evidence_anchor_identity,
    verify_temporal_cutoff,
    verify_review_family_compatibility,
    verify_estimand_completeness,
    verify_synthesis_route,
    verify_overlap_and_active_protocols,
    verify_access_and_extractability,
)


def verify_question_candidate(candidate: dict[str, Any], landscape: dict[str, Any], route_decision: dict[str, Any]) -> list[dict[str, Any]]:
    return sorted((fn(candidate, landscape, route_decision) for fn in VERIFIERS), key=lambda item: item["verifier_id"])


def require_hard_verifiers(observations: list[dict[str, Any]]) -> None:
    hard = {"evidence_anchor_identity", "review_family_compatibility", "estimand_completeness", "synthesis_route"}
    failures = [item["verifier_id"] for item in observations if item["verifier_id"] in hard and item["status"] != "passed"]
    if failures:
        raise QuestionSynthesisVerificationError(f"hard verifier failures: {sorted(failures)}")
