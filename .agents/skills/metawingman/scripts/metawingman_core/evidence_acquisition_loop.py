"""Execute the risk-impact evidence acquisition controller between real actions."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Callable

from .evidence_acquisition import EvidenceAcquisitionError, plan_evidence_acquisition
from .schema_guard import SchemaValidationError, validate_document
from .state_store import sha256_json


ActionExecutor = Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]]


def _validate_plan(plan: dict[str, Any]) -> None:
    try:
        validate_document(plan, "evidence_acquisition_loop_plan")
    except SchemaValidationError as exc:
        raise EvidenceAcquisitionError(str(exc)) from exc
    if plan["mode"] == "evaluation" and plan["stop_authority"]["signature_status"] != "verified":
        raise EvidenceAcquisitionError("evaluation stop authority must be preregistered and verified")


def _artifact_binding(binding: dict[str, Any], root: Path) -> dict[str, str]:
    if not isinstance(binding, dict) or set(binding) != {"path", "sha256"}:
        raise EvidenceAcquisitionError("action artifact binding must contain only path and sha256")
    path = Path(str(binding["path"])).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise EvidenceAcquisitionError("action artifact is outside the frozen artifact root") from exc
    if not path.is_file():
        raise EvidenceAcquisitionError("action artifact does not exist")
    observed = hashlib.sha256(path.read_bytes()).hexdigest()
    if observed != binding["sha256"]:
        raise EvidenceAcquisitionError("action artifact sha256 mismatch")
    return {"path": str(path), "sha256": observed}


def _validate_usage(usage: dict[str, Any]) -> dict[str, Any]:
    required = {
        "model_calls", "input_tokens", "output_tokens", "wall_seconds",
        "cost_status", "cost_value",
    }
    if not isinstance(usage, dict) or set(usage) != required:
        raise EvidenceAcquisitionError("action usage must use the exact budget receipt fields")
    for field in ("model_calls", "input_tokens", "output_tokens"):
        if isinstance(usage[field], bool) or not isinstance(usage[field], int) or usage[field] < 0:
            raise EvidenceAcquisitionError(f"action usage {field} must be a non-negative integer")
    if isinstance(usage["wall_seconds"], bool) or not isinstance(usage["wall_seconds"], (int, float)) or usage["wall_seconds"] < 0:
        raise EvidenceAcquisitionError("action usage wall_seconds must be non-negative")
    if usage["cost_status"] not in {"known", "unknown", "not_applicable"}:
        raise EvidenceAcquisitionError("action usage cost_status is invalid")
    if usage["cost_status"] == "known":
        if isinstance(usage["cost_value"], bool) or not isinstance(usage["cost_value"], (int, float)) or usage["cost_value"] < 0:
            raise EvidenceAcquisitionError("known action cost requires a non-negative numeric value")
    elif usage["cost_value"] is not None:
        raise EvidenceAcquisitionError("unknown or not-applicable action cost must be null")
    return dict(usage)


def _usage_totals(receipts: list[dict[str, Any]], estimated_cost_units: float) -> dict[str, Any]:
    usages = [item["usage"] for item in receipts]
    statuses = {item["cost_status"] for item in usages}
    if "unknown" in statuses:
        cost_status = "unknown"
        cost_value = None
    elif statuses and statuses <= {"known", "not_applicable"} and "known" in statuses:
        cost_status = "known"
        cost_value = round(sum(float(item["cost_value"] or 0.0) for item in usages), 8)
    else:
        cost_status = "not_applicable"
        cost_value = None
    return {
        "actions": len(receipts),
        "estimated_cost_units": round(estimated_cost_units, 8),
        "model_calls": sum(item["model_calls"] for item in usages),
        "input_tokens": sum(item["input_tokens"] for item in usages),
        "output_tokens": sum(item["output_tokens"] for item in usages),
        "wall_seconds": round(sum(float(item["wall_seconds"]) for item in usages), 8),
        "cost_status": cost_status,
        "cost_value": cost_value,
    }


def _budget_exceeded(totals: dict[str, Any], budget: dict[str, Any]) -> bool:
    return any((
        totals["actions"] > budget["max_actions"],
        totals["estimated_cost_units"] > budget["max_estimated_cost_units"],
        totals["model_calls"] > budget["max_model_calls"],
        totals["input_tokens"] > budget["max_input_tokens"],
        totals["output_tokens"] > budget["max_output_tokens"],
        totals["wall_seconds"] > budget["max_wall_seconds"],
    ))


def _finalize(
    *,
    plan: dict[str, Any],
    initial_hash: str,
    state: dict[str, Any],
    decisions: list[dict[str, Any]],
    receipts: list[dict[str, Any]],
    estimated_cost_units: float,
    status: str,
    reason: str,
    instantiated: bool,
    created_at_utc: str,
) -> dict[str, Any]:
    result = {
        "schema_version": "1.0",
        "loop_id": plan["loop_id"],
        "status": status,
        "terminal_reason": reason,
        "initial_state_sha256": initial_hash,
        "final_state_sha256": sha256_json(state),
        "decisions": decisions,
        "action_receipts": receipts,
        "usage_totals": _usage_totals(receipts, estimated_cost_units),
        "stop_authority": dict(plan["stop_authority"]),
        "full_risk_impact_controller_instantiated": instantiated,
        "created_at_utc": created_at_utc,
    }
    try:
        validate_document(result, "evidence_acquisition_loop_result")
    except SchemaValidationError as exc:
        raise EvidenceAcquisitionError(str(exc)) from exc
    return result


def execute_evidence_acquisition_loop(
    initial_state: dict[str, Any],
    plan: dict[str, Any],
    executor: ActionExecutor,
    *,
    created_at_utc: str,
) -> dict[str, Any]:
    """Plan, execute one action, recompute risk, and repeat until a signed stop or abstention."""
    _validate_plan(plan)
    state = initial_state
    initial_hash = sha256_json(state)
    root = Path(plan["artifact_root"]).resolve()
    if not root.is_dir():
        raise EvidenceAcquisitionError("frozen artifact root does not exist")
    decisions: list[dict[str, Any]] = []
    receipts: list[dict[str, Any]] = []
    estimated_cost_units = 0.0
    instantiated = False

    for iteration in range(1, plan["max_iterations"] + 1):
        decision = plan_evidence_acquisition(state, created_at_utc=created_at_utc)
        decisions.append(decision)
        if decision["status"] == "abstain":
            return _finalize(
                plan=plan, initial_hash=initial_hash, state=state, decisions=decisions,
                receipts=receipts, estimated_cost_units=estimated_cost_units,
                status="abstained", reason="controller_abstained", instantiated=instantiated,
                created_at_utc=created_at_utc,
            )
        if decision["status"] == "stop_candidate":
            signed = plan["stop_authority"]["signature_status"] == "verified"
            return _finalize(
                plan=plan, initial_hash=initial_hash, state=state, decisions=decisions,
                receipts=receipts, estimated_cost_units=estimated_cost_units,
                status="completed" if signed else "awaiting_stop_authority",
                reason="stop_authority_verified" if signed else "stop_authority_pending",
                instantiated=instantiated, created_at_utc=created_at_utc,
            )

        selected_id = decision["selected_actions"][0]["action_id"]
        action = next(item for item in state["candidate_actions"] if item["action_id"] == selected_id)
        projected_estimated = estimated_cost_units + float(action["estimated_cost_units"])
        if len(receipts) + 1 > plan["budget"]["max_actions"] or projected_estimated > plan["budget"]["max_estimated_cost_units"]:
            return _finalize(
                plan=plan, initial_hash=initial_hash, state=state, decisions=decisions,
                receipts=receipts, estimated_cost_units=estimated_cost_units,
                status="abstained", reason="budget_precheck_failed", instantiated=instantiated,
                created_at_utc=created_at_utc,
            )

        raw = executor(dict(action), state)
        if not isinstance(raw, dict) or raw.get("action_id") != selected_id:
            raise EvidenceAcquisitionError("executor action receipt does not match the selected action")
        if raw.get("risk_state_recomputed") is not True:
            raise EvidenceAcquisitionError("executor must return an independently recomputed risk state")
        if raw.get("semantic_verification_status") not in {"passed", "not_applicable"}:
            raise EvidenceAcquisitionError("executor semantic verification did not pass")
        next_state = raw.get("next_state")
        if not isinstance(next_state, dict):
            raise EvidenceAcquisitionError("executor must return the next typed risk state")
        next_hash = sha256_json(next_state)
        prior_hash = sha256_json(state)
        if next_hash == prior_hash or next_state.get("state_id") == state.get("state_id"):
            raise EvidenceAcquisitionError("recomputed risk state must change content and state_id")
        if next_state.get("protocol_version") != state.get("protocol_version"):
            raise EvidenceAcquisitionError("action cannot mutate the frozen protocol version")
        # Reusing the planner validates the next state before the transition is admitted.
        plan_evidence_acquisition(next_state, created_at_utc=created_at_utc)
        artifact = _artifact_binding(raw.get("artifact"), root)
        usage = _validate_usage(raw.get("usage"))
        receipt = {
            "schema_version": "1.0",
            "iteration": iteration,
            "action_id": selected_id,
            "decision_sha256": sha256_json(decision),
            "prior_state_sha256": prior_hash,
            "next_state_sha256": next_hash,
            "risk_state_recomputed": True,
            "semantic_verification_status": raw["semantic_verification_status"],
            "artifact": artifact,
            "usage": usage,
            "created_at_utc": created_at_utc,
        }
        try:
            validate_document(receipt, "evidence_acquisition_loop_receipt")
        except SchemaValidationError as exc:
            raise EvidenceAcquisitionError(str(exc)) from exc
        receipts.append(receipt)
        estimated_cost_units = projected_estimated
        state = next_state
        instantiated = True
        totals = _usage_totals(receipts, estimated_cost_units)
        if _budget_exceeded(totals, plan["budget"]):
            return _finalize(
                plan=plan, initial_hash=initial_hash, state=state, decisions=decisions,
                receipts=receipts, estimated_cost_units=estimated_cost_units,
                status="abstained", reason="budget_exceeded_after_action", instantiated=instantiated,
                created_at_utc=created_at_utc,
            )
        if plan["budget"]["cost_accounting_policy"] == "require_known" and totals["cost_status"] != "known":
            return _finalize(
                plan=plan, initial_hash=initial_hash, state=state, decisions=decisions,
                receipts=receipts, estimated_cost_units=estimated_cost_units,
                status="abstained", reason="cost_accounting_unavailable", instantiated=instantiated,
                created_at_utc=created_at_utc,
            )

    return _finalize(
        plan=plan, initial_hash=initial_hash, state=state, decisions=decisions,
        receipts=receipts, estimated_cost_units=estimated_cost_units,
        status="abstained", reason="max_iterations_reached", instantiated=instantiated,
        created_at_utc=created_at_utc,
    )
