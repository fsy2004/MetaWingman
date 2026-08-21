"""Compile source-preserving clinical decision context documents."""

from __future__ import annotations

from typing import Any

from .schema_guard import validate_document
from .state_store import sha256_json


class ClinicalQuestionError(ValueError):
    """Raised when a clinical context cannot be compiled safely."""


def _strings(value: Any) -> list[str]:
    if value is None:
        return []
    values = value if isinstance(value, list) else [value]
    result: list[str] = []
    for item in values:
        text = str(item).strip()
        if text and text not in result:
            result.append(text)
    return result


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _anchors(raw: dict[str, Any]) -> list[dict[str, str]]:
    anchors: list[dict[str, str]] = []
    for field, value in raw.items():
        for position, text in enumerate(_strings(value), start=1):
            anchors.append(
                {
                    "anchor_id": f"input-{field}-{position}",
                    "field": field,
                    "verbatim": text,
                    "source_type": "user_input",
                }
            )
    return anchors


def compile_clinical_decision_context(
    raw: dict[str, Any], *, created_at_utc: str
) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ClinicalQuestionError("clinical input must be an object")
    decision_problem = _text(raw.get("decision_problem"))
    actions = _strings(raw.get("candidate_actions"))
    outcomes = _strings(raw.get("outcomes") or raw.get("patient_important_outcomes"))
    identity = {"raw": raw, "created_at_utc": created_at_utc}
    context = {
        "schema_version": "1.0",
        "context_id": f"clinical-{sha256_json(identity)[:20]}",
        "stakeholders": _strings(raw.get("stakeholders")),
        "setting": _strings(raw.get("setting")),
        "decision_problem": decision_problem,
        "candidate_actions": actions,
        "time_horizon": _text(raw.get("time_horizon")),
        "patient_important_outcomes": outcomes,
        "subgroups": _strings(raw.get("subgroups")),
        "equity_factors": _strings(raw.get("equity_factors")),
        "implementation_constraints": _strings(raw.get("constraints") or raw.get("implementation_constraints")),
        "source_anchors": _anchors(raw),
        "status": "complete" if decision_problem and actions and outcomes else "incomplete",
        "created_at_utc": created_at_utc,
    }
    validate_document(context, "clinical_decision_context")
    return context
