"""Build an estimand-alignment matrix and non-final poolability recommendation."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .schema_guard import SchemaValidationError, validate_document


DIMENSIONS = (
    "population", "contrast", "outcome", "time_horizon",
    "effect_measure", "analysis_unit", "conditioning_set",
)


class PoolabilityError(ValueError):
    """Raised when result estimands cannot be compared to the target."""


def _normalize(value: Any) -> Any:
    if isinstance(value, str):
        return " ".join(value.casefold().split())
    if isinstance(value, list):
        return sorted(_normalize(item) for item in value)
    return value


def _alignment(
    dimension: str,
    target: Any,
    observed: Any,
    override: dict[str, Any] | None,
    default_anchor_ids: list[str],
) -> dict[str, Any]:
    if override:
        status = override.get("status")
        if status not in {"exact", "compatible", "unclear", "incompatible"}:
            raise PoolabilityError(f"Invalid alignment override for {dimension}: {status}")
        if status == "compatible" and not override.get("rationale"):
            raise PoolabilityError(f"Compatible override for {dimension} requires a rationale")
        anchors = list(override.get("anchor_ids") or default_anchor_ids)
        if status in {"compatible", "incompatible"} and not anchors:
            raise PoolabilityError(f"Alignment override for {dimension} requires evidence anchors")
        return {
            "dimension": dimension, "status": status,
            "target_value": target, "result_value": observed,
            "rationale": str(override.get("rationale") or "Explicit alignment override."),
            "anchor_ids": anchors,
        }
    if target is None or observed is None:
        status = "unclear"
        rationale = "Target or result estimand component is missing."
    elif _normalize(target) == _normalize(observed):
        status = "exact"
        rationale = "Normalized target and result components are identical."
    else:
        status = "incompatible"
        rationale = "Components differ and no evidence-anchored compatibility override was supplied."
    return {
        "dimension": dimension, "status": status,
        "target_value": target, "result_value": observed,
        "rationale": rationale, "anchor_ids": default_anchor_ids,
    }


def build_poolability_matrix(candidate: dict[str, Any], *, created_at_utc: str | None = None) -> dict[str, Any]:
    target = candidate.get("target_estimand")
    inputs = candidate.get("results")
    if not isinstance(target, dict) or not isinstance(inputs, list) or not inputs:
        raise PoolabilityError("target_estimand and a non-empty results list are required")
    if set(target) != set(DIMENSIONS):
        raise PoolabilityError("target_estimand must define exactly the seven alignment dimensions")

    results: list[dict[str, Any]] = []
    for item in inputs:
        estimand = item.get("estimand")
        if not isinstance(estimand, dict) or set(estimand) != set(DIMENSIONS):
            raise PoolabilityError(f"Result {item.get('result_id')} lacks a complete estimand")
        anchors = list(item.get("anchor_ids") or [])
        overrides = item.get("alignment_overrides") or {}
        if not isinstance(overrides, dict):
            raise PoolabilityError("alignment_overrides must be an object")
        unknown_overrides = sorted(set(overrides) - set(DIMENSIONS))
        if unknown_overrides:
            raise PoolabilityError("Unknown alignment override dimensions: " + ", ".join(unknown_overrides))
        alignments = [
            _alignment(dimension, target[dimension], estimand[dimension], overrides.get(dimension), anchors)
            for dimension in DIMENSIONS
        ]
        statuses = {alignment["status"] for alignment in alignments}
        if "incompatible" in statuses:
            recommendation = "exclude"
            reason_codes = ["estimand_component_incompatible"]
        elif "unclear" in statuses:
            recommendation = "abstain"
            reason_codes = ["estimand_component_unclear"]
        else:
            recommendation = "include"
            reason_codes = ["estimand_components_aligned"]
        results.append({
            "result_id": str(item.get("result_id") or ""),
            "study_id": str(item.get("study_id") or ""),
            "estimand": estimand,
            "alignment": alignments,
            "recommendation": recommendation,
            "reason_codes": reason_codes,
            "anchor_ids": anchors,
        })

    proposal = candidate.get("proposal") or {
        "actor_id": "deterministic-alignment-engine",
        "judgment": "proceed_to_human_poolability_conference",
        "reason_codes": sorted({code for item in results for code in item["reason_codes"]}),
        "rationale": "Deterministic component matching completed; clinical compatibility still requires adjudication.",
        "abstained": any(item["recommendation"] == "abstain" for item in results),
    }
    opposition = candidate.get("opposition") or {
        "actor_id": "", "judgment": "", "reason_codes": ["opposition_not_run"],
        "rationale": "", "abstained": True,
    }
    judge = candidate.get("judge_recommendation") or {
        "actor_id": "", "judgment": "", "reason_codes": ["judge_not_run"],
        "rationale": "", "abstained": True,
    }
    ready = all(role.get("actor_id") and role.get("judgment") and role.get("rationale") for role in (proposal, opposition, judge))
    now = created_at_utc or datetime.now(timezone.utc).isoformat()
    output = {
        "schema_version": "1.0",
        "matrix_id": str(candidate.get("matrix_id") or ""),
        "synthesis_id": str(candidate.get("synthesis_id") or ""),
        "target_estimand": target,
        "results": results,
        "proposal": proposal,
        "opposition": opposition,
        "judge_recommendation": judge,
        "status": "ready_for_adjudication" if ready else "draft",
        "final_decision": None,
        "human_signature": {"status": "pending", "signed_by": "", "signed_at_utc": None, "notes": ""},
        "created_at_utc": now,
        "updated_at_utc": now,
    }
    try:
        validate_document(output, "poolability_matrix")
    except SchemaValidationError as exc:
        raise PoolabilityError(str(exc)) from exc
    return output
