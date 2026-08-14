"""Deterministic policy judge for criterion-level AI or human screening proposals."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from .schema_guard import SchemaValidationError, validate_document


CriterionDecision = Literal["met", "not_met", "unclear", "not_reported"]


class ScreeningError(ValueError):
    """Raised when screening inputs cannot be evaluated under the protocol."""


def _missing(value: Any) -> bool:
    return value is None or value == "" or value == []


def _normalize(value: Any, rule: str) -> Any:
    if rule in {"none", "identity", ""}:
        return value
    if rule in {"casefold", "lowercase"}:
        if isinstance(value, str):
            return " ".join(value.casefold().split())
        if isinstance(value, list):
            return [_normalize(item, rule) for item in value]
    if rule == "strip":
        return value.strip() if isinstance(value, str) else value
    if rule in {"years", "months", "days"}:
        if isinstance(value, dict) and "value" in value and "unit" in value:
            number = float(value["value"])
            unit = str(value["unit"]).casefold()
            days = number * {"days": 1.0, "weeks": 7.0, "months": 30.4375, "years": 365.25}.get(unit, float("nan"))
            if days != days:
                raise ScreeningError(f"Unsupported time unit: {value['unit']}")
            return days / {"days": 1.0, "months": 30.4375, "years": 365.25}[rule]
        return float(value)
    raise ScreeningError(f"Unsupported normalization rule: {rule}")


def _compare(observed: Any, operator: str, expected: Any) -> bool:
    if operator == "exists":
        return not _missing(observed)
    if operator == "equals":
        return observed == expected
    if operator == "not_equals":
        return observed != expected
    if operator == "in":
        return observed in expected
    if operator == "not_in":
        return observed not in expected
    if operator == "contains":
        if isinstance(observed, str):
            return str(expected) in observed
        return expected in observed
    if operator == "gte":
        return observed >= expected
    if operator == "gt":
        return observed > expected
    if operator == "lte":
        return observed <= expected
    if operator == "lt":
        return observed < expected
    if operator == "between":
        return expected[0] <= observed <= expected[1]
    raise ScreeningError(f"Unsupported predicate operator: {operator}")


def evaluate_criterion(
    criterion: dict[str, Any],
    record: dict[str, Any],
    *,
    stage: str,
) -> dict[str, Any]:
    predicate = criterion["predicate"]
    field = predicate["field"]
    fields = record.get("fields", {})
    anchors = list(record.get("anchors", {}).get(field, []))
    confidence = record.get("confidence", {}).get(field)
    observed = fields.get(field)
    requires_full_text = stage == "title_abstract" and criterion["full_text_required"]
    if _missing(observed):
        decision: CriterionDecision = "not_reported"
        rationale = f"{field} was not reported in the available {stage.replace('_', '/')} evidence."
    elif requires_full_text:
        decision = "unclear"
        rationale = f"{field} requires full-text assessment under the frozen criterion."
    else:
        try:
            normalized_observed = _normalize(observed, predicate["normalization"])
            normalized_expected = _normalize(predicate["value"], predicate["normalization"])
            decision = "met" if _compare(normalized_observed, predicate["operator"], normalized_expected) else "not_met"
            rationale = f"Observed {field} was evaluated with {predicate['operator']}."
        except (TypeError, ValueError, ScreeningError) as exc:
            decision = "unclear"
            rationale = f"Could not evaluate {field} deterministically: {exc}"
    return {
        "criterion_id": criterion["criterion_id"],
        "decision": decision,
        "observed_value": observed,
        "anchor_ids": anchors,
        "rationale": rationale,
        "confidence": confidence,
        "requires_full_text": requires_full_text,
    }


def _policy_decision(
    criteria: list[dict[str, Any]],
    decisions: list[dict[str, Any]],
    *,
    stage: str,
    confidence_floor: float,
) -> dict[str, Any]:
    by_id = {item["criterion_id"]: item for item in decisions}
    exclusion_candidates = [
        by_id[criterion["criterion_id"]]
        for criterion in criteria
        if by_id[criterion["criterion_id"]]["decision"] == "not_met"
    ]
    low_confidence = [
        item for item in decisions
        if item["decision"] in {"met", "not_met"}
        and item["confidence"] is not None
        and item["confidence"] < confidence_floor
    ]
    unresolved = [item for item in decisions if item["decision"] in {"unclear", "not_reported"}]
    if low_confidence:
        return {
            "recommendation": "abstain", "primary_reason_code": None,
            "anchor_ids": sorted({anchor for item in low_confidence for anchor in item["anchor_ids"]}),
            "confidence": min(item["confidence"] for item in low_confidence),
            "reason_codes": ["calibration_confidence_below_floor"],
        }
    if exclusion_candidates:
        strongest = exclusion_candidates[0]
        if not strongest["anchor_ids"]:
            return {
                "recommendation": "abstain", "primary_reason_code": strongest["criterion_id"],
                "anchor_ids": [], "confidence": strongest["confidence"],
                "reason_codes": ["exclusion_evidence_anchor_missing"],
            }
        return {
            "recommendation": "exclude", "primary_reason_code": strongest["criterion_id"],
            "anchor_ids": strongest["anchor_ids"], "confidence": strongest["confidence"],
            "reason_codes": ["criterion_not_met"],
        }
    if unresolved:
        codes = ["criterion_unresolved"]
        if stage == "title_abstract" and any(item["requires_full_text"] for item in unresolved):
            codes.append("full_text_required")
        if any(item["decision"] == "not_reported" for item in unresolved):
            codes.append("missing_information_not_equivalent_to_exclusion")
        return {
            "recommendation": "abstain", "primary_reason_code": None,
            "anchor_ids": sorted({anchor for item in unresolved for anchor in item["anchor_ids"]}),
            "confidence": None, "reason_codes": codes,
        }
    confidence_values = [item["confidence"] for item in decisions if item["confidence"] is not None]
    return {
        "recommendation": "include", "primary_reason_code": None,
        "anchor_ids": sorted({anchor for item in decisions for anchor in item["anchor_ids"]}),
        "confidence": min(confidence_values) if confidence_values else None,
        "reason_codes": ["all_operational_criteria_met"],
    }


def screen_record(
    protocol_criteria: dict[str, Any],
    record: dict[str, Any],
    *,
    stage: str,
    confidence_floor: float = 0.8,
    created_at_utc: str | None = None,
) -> dict[str, Any]:
    try:
        validate_document(protocol_criteria, "protocol_criteria")
    except SchemaValidationError as exc:
        raise ScreeningError(str(exc)) from exc
    if protocol_criteria["status"] not in {"frozen", "amended"}:
        raise ScreeningError("Screening requires frozen or amended protocol criteria")
    if stage not in {"title_abstract", "full_text"}:
        raise ScreeningError(f"Unsupported screening stage: {stage}")
    if not isinstance(record.get("fields"), dict):
        raise ScreeningError("record.fields must be an object")
    criteria = protocol_criteria["criteria"]
    if any(item["status"] != "operational" for item in criteria):
        raise ScreeningError("All frozen criteria must be operational")
    decisions = [evaluate_criterion(item, record, stage=stage) for item in criteria]
    proposal = _policy_decision(criteria, decisions, stage=stage, confidence_floor=confidence_floor)

    counterevidence = record.get("counterevidence", {})
    if proposal["recommendation"] == "exclude" and proposal["primary_reason_code"] in counterevidence:
        opposition = {
            "verdict": "challenge",
            "reason_codes": ["counterevidence_for_primary_exclusion"],
            "counter_anchor_ids": list(counterevidence[proposal["primary_reason_code"]]),
        }
        policy = {
            "recommendation": "abstain", "primary_reason_code": proposal["primary_reason_code"],
            "anchor_ids": sorted(set(proposal["anchor_ids"] + opposition["counter_anchor_ids"])),
            "confidence": proposal["confidence"],
            "reason_codes": ["proposal_opposition_disagreement"],
        }
    elif proposal["recommendation"] == "abstain":
        opposition = {"verdict": "abstain", "reason_codes": ["insufficient_decisive_evidence"], "counter_anchor_ids": []}
        policy = proposal
    else:
        opposition = {"verdict": "uphold", "reason_codes": ["no_stronger_counterevidence_found"], "counter_anchor_ids": []}
        policy = proposal

    assessment = {
        "schema_version": "1.0",
        "assessment_id": str(record.get("assessment_id") or f"{record['record_id']}-{stage}"),
        "record_id": str(record["record_id"]),
        "report_id": record.get("report_id"),
        "stage": stage,
        "protocol_version": protocol_criteria["protocol_version"],
        "criterion_decisions": decisions,
        "proposal": proposal,
        "opposition": opposition,
        "policy_decision": policy,
        "status": "ready_for_human",
        "human_adjudication": {
            "status": "pending", "decision": None, "adjudicated_by": "",
            "adjudicated_at_utc": None, "notes": "",
        },
        "created_at_utc": created_at_utc or datetime.now(timezone.utc).isoformat(),
    }
    try:
        validate_document(assessment, "screening_assessment")
    except SchemaValidationError as exc:
        raise ScreeningError(str(exc)) from exc
    return assessment
