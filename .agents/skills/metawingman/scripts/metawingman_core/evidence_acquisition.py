"""Plan evidence acquisition from residual omission risk and claim impact."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .schema_guard import SchemaValidationError, validate_document
from .state_store import sha256_json


POLICY_VERSION = "1.0"


class EvidenceAcquisitionError(ValueError):
    """Raised when an acquisition state cannot be evaluated safely."""


def _check_identifiers(state: dict[str, Any]) -> None:
    criterion_ids = [item["criterion_id"] for item in state["criterion_states"]]
    if len(criterion_ids) != len(set(criterion_ids)):
        raise EvidenceAcquisitionError("criterion_id values must be unique")
    action_ids = [item["action_id"] for item in state["candidate_actions"]]
    if len(action_ids) != len(set(action_ids)):
        raise EvidenceAcquisitionError("action_id values must be unique")
    known = set(criterion_ids)
    for action in state["candidate_actions"]:
        unknown = sorted(set(action["target_criterion_ids"]) - known)
        if unknown:
            raise EvidenceAcquisitionError(
                f"action {action['action_id']} targets unknown criteria: {unknown}"
            )


def _high_impact_criteria(state: dict[str, Any]) -> set[str]:
    thresholds = state["thresholds"]
    high: set[str] = set()
    for criterion in state["criterion_states"]:
        risk = criterion["residual_omission_risk"]
        impact = criterion["downstream_claim_impact"]
        hard_error = criterion["hard_negative_error_rate"]
        critical = criterion["critical"]
        if risk is not None and risk > thresholds["residual_omission_risk_ceiling"]:
            if critical or (impact is not None and impact > thresholds["downstream_claim_impact_ceiling"]):
                high.add(criterion["criterion_id"])
        if criterion["unresolved_records"] > 0 and (
            critical or (impact is not None and impact > thresholds["downstream_claim_impact_ceiling"])
        ):
            high.add(criterion["criterion_id"])
        if criterion["independent_source_count"] < thresholds["minimum_independent_sources"] and (
            critical or (impact is not None and impact > thresholds["downstream_claim_impact_ceiling"])
        ):
            high.add(criterion["criterion_id"])
        if hard_error is not None and hard_error > thresholds["hard_negative_error_ceiling"]:
            high.add(criterion["criterion_id"])
    return high


def _global_need_reasons(state: dict[str, Any]) -> list[str]:
    signals = state["global_signals"]
    thresholds = state["thresholds"]
    reasons: list[str] = []
    if not signals["known_item_set_frozen"]:
        reasons.append("known_item_set_not_frozen")
    if signals["known_item_recall"] is None:
        reasons.append("known_item_recall_unavailable")
    elif signals["known_item_recall"] < thresholds["known_item_recall_floor"]:
        reasons.append("known_item_recall_below_floor")
    if signals["source_family_count"] < thresholds["minimum_source_families"]:
        reasons.append("source_family_coverage_below_floor")
    return reasons


def _temporal_or_leakage_failure(state: dict[str, Any]) -> list[str]:
    signals = state["global_signals"]
    if signals["run_context"] != "historical_reconstruction":
        return []
    reasons: list[str] = []
    if signals["temporal_boundary_status"] != "sealed":
        reasons.append("historical_temporal_boundary_not_sealed")
    if signals["leakage_audit"] != "passed":
        reasons.append("historical_leakage_audit_not_passed")
    return reasons


def _utility(
    action: dict[str, Any],
    criterion_by_id: dict[str, dict[str, Any]],
    state: dict[str, Any],
) -> float:
    targets = [criterion_by_id[item] for item in action["target_criterion_ids"]]
    risks = [item["residual_omission_risk"] for item in targets if item["residual_omission_risk"] is not None]
    impacts = [item["downstream_claim_impact"] for item in targets if item["downstream_claim_impact"] is not None]
    hard_errors = [item["hard_negative_error_rate"] for item in targets if item["hard_negative_error_rate"] is not None]
    critical_multiplier = 1.5 if any(item["critical"] for item in targets) else 1.0
    local_need = max(risks, default=1.0 if any(item["calibration_status"] != "calibrated" for item in targets) else 0.05)
    if state["global_signals"]["known_item_recall"] is not None:
        local_need = max(local_need, 1.0 - state["global_signals"]["known_item_recall"])
    claim_impact = max([action["expected_claim_impact"], *impacts, 0.05])
    hardness = 1.0 + max(hard_errors, default=0.0)
    diversity = 1.0 + 0.25 * action["source_family_gain"]
    score = (
        action["expected_risk_reduction"]
        * local_need
        * claim_impact
        * hardness
        * diversity
        * critical_multiplier
        / action["estimated_cost_units"]
    )
    return round(score, 8)


def plan_evidence_acquisition(
    state: dict[str, Any],
    *,
    created_at_utc: str | None = None,
) -> dict[str, Any]:
    """Return continue, stop-candidate, or abstain under a typed stopping contract."""
    try:
        validate_document(state, "evidence_acquisition_state")
    except SchemaValidationError as exc:
        raise EvidenceAcquisitionError(str(exc)) from exc
    _check_identifiers(state)

    timestamp = created_at_utc or datetime.now(timezone.utc).isoformat()
    high = _high_impact_criteria(state)
    global_reasons = _global_need_reasons(state)
    temporal_reasons = _temporal_or_leakage_failure(state)
    uncalibrated = {
        item["criterion_id"]
        for item in state["criterion_states"]
        if item["calibration_status"] != "calibrated"
        or item["residual_omission_risk"] is None
        or item["downstream_claim_impact"] is None
    }
    criterion_by_id = {item["criterion_id"]: item for item in state["criterion_states"]}

    executable_actions = [
        item for item in state["candidate_actions"]
        if item["legally_available"] and item["credential_status"] in {"not_required", "available"}
    ]
    blocked_action_ids = sorted(
        item["action_id"] for item in state["candidate_actions"] if item not in executable_actions
    )

    if temporal_reasons:
        status = "abstain"
        stop_allowed = False
        selected_actions: list[dict[str, Any]] = []
        reasons = temporal_reasons
        human_trigger = "Historical reconstruction boundary or leakage control failed."
    else:
        needs_more_evidence = bool(high or global_reasons or uncalibrated)
        relevant_actions = [
            item for item in executable_actions
            if not high or set(item["target_criterion_ids"]) & high
        ]
        if needs_more_evidence and relevant_actions:
            ranked = sorted(
                ((item, _utility(item, criterion_by_id, state)) for item in relevant_actions),
                key=lambda pair: (pair[1], pair[0]["action_id"]),
                reverse=True,
            )
            selected_actions = [
                {
                    "action_id": item["action_id"],
                    "utility_score": score,
                    "reason_codes": [
                        "expected_residual_risk_reduction",
                        "downstream_claim_impact_weighted",
                    ] + (["source_diversity_gain"] if item["source_family_gain"] else []),
                }
                for item, score in ranked[: state["thresholds"]["max_selected_actions"]]
            ]
            status = "continue"
            stop_allowed = False
            reasons = sorted(set([*global_reasons, "high_impact_or_uncalibrated_evidence_gap"]))
            human_trigger = ""
        elif needs_more_evidence:
            selected_actions = []
            status = "abstain"
            stop_allowed = False
            reasons = sorted(set([*global_reasons, "no_executable_evidence_action"]))
            if any(item["credential_status"] == "human_handoff" for item in state["candidate_actions"]):
                reasons.append("credential_handoff_required")
            if any(not item["legally_available"] for item in state["candidate_actions"]):
                reasons.append("lawful_access_unavailable")
            reasons = sorted(set(reasons))
            human_trigger = "Residual risk cannot be reduced by an authorized executable action."
        else:
            selected_actions = []
            status = "stop_candidate"
            stop_allowed = True
            reasons = ["residual_search_and_claim_impact_within_frozen_thresholds"]
            human_trigger = "Search completion is a high-risk scientific responsibility node."

    human_required = status in {"stop_candidate", "abstain"}
    decision = {
        "schema_version": "1.0",
        "decision_id": f"{state['state_id']}-decision",
        "state_id": state["state_id"],
        "state_sha256": sha256_json(state),
        "policy_version": POLICY_VERSION,
        "status": status,
        "stop_allowed": stop_allowed,
        "selected_actions": selected_actions,
        "blocked_action_ids": blocked_action_ids,
        "high_impact_criterion_ids": sorted(high),
        "uncalibrated_criterion_ids": sorted(uncalibrated),
        "reason_codes": reasons,
        "human_review": {
            "required": human_required,
            "status": "pending" if human_required else "not_required",
            "trigger": human_trigger,
        },
        "created_at_utc": timestamp,
    }
    try:
        validate_document(decision, "evidence_acquisition_decision")
    except SchemaValidationError as exc:
        raise EvidenceAcquisitionError(str(exc)) from exc
    return decision
