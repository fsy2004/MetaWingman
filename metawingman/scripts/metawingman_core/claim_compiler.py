"""Compile support-bounded claims without assuming final scientific responsibility."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from .schema_guard import SchemaValidationError, validate_document


NUMBER_PATTERN = re.compile(r"(?<![A-Za-z0-9_.])[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?%?")
PROHIBITED_ABSOLUTE_PHRASES = (
    "proves", "proved", "guarantees", "guaranteed", "eliminates risk",
    "no uncertainty", "definitively establishes", "conclusively demonstrates",
)
CAUSAL_TERMS = ("causes", "caused", "prevents", "prevented", "leads to", "resulted in")
DEFAULT_ALLOWED_VERBS = {
    "observation": ("estimated", "observed", "reported", "found", "was associated with"),
    "interpretation": ("suggests", "may", "could", "is consistent with"),
    "implication": ("may inform", "supports consideration", "warrants further study"),
}


class ClaimCompileError(ValueError):
    """Raised when claim wording exceeds its verified evidence contract."""


def _normalized_number_token(value: str) -> float:
    is_percent = value.endswith("%")
    number = float(value[:-1] if is_percent else value)
    return number / 100 if is_percent else number


def _match_supported_numbers(text: str, numeric_support: list[dict[str, Any]]) -> tuple[bool, list[str]]:
    tokens = NUMBER_PATTERN.findall(text)
    unsupported: list[str] = []
    support = []
    for item in numeric_support:
        value = float(item["value"])
        tolerance = float(item.get("tolerance", 0.0))
        support.append((value, tolerance))
    for token in tokens:
        value = _normalized_number_token(token)
        if not any(abs(value - supported) <= tolerance for supported, tolerance in support):
            unsupported.append(token)
    return not unsupported, unsupported


def compile_claim(candidate: dict[str, Any], *, created_at_utc: str | None = None) -> dict[str, Any]:
    claim_type = str(candidate.get("claim_type") or "")
    if claim_type not in DEFAULT_ALLOWED_VERBS:
        raise ClaimCompileError(f"Unsupported claim type: {claim_type}")
    text = str(candidate.get("text") or "").strip()
    if not text:
        raise ClaimCompileError("Claim text is required")
    evidence_nodes = list(candidate.get("evidence_node_ids") or [])
    analysis_outputs = list(candidate.get("analysis_output_ids") or [])
    assertion_ids = list(candidate.get("assertion_ids") or [])
    if not (evidence_nodes or analysis_outputs or assertion_ids):
        raise ClaimCompileError("A claim requires at least one verified support reference")
    if not candidate.get("support_verifier_id"):
        raise ClaimCompileError("An external support verifier ID is required")

    lowered = text.casefold()
    prohibited = [phrase for phrase in PROHIBITED_ABSOLUTE_PHRASES if phrase in lowered]
    if prohibited:
        raise ClaimCompileError("Absolute wording is prohibited: " + ", ".join(prohibited))
    evidence_design = str(candidate.get("evidence_design") or "association").casefold()
    causal_terms = [phrase for phrase in CAUSAL_TERMS if phrase in lowered]
    if causal_terms and evidence_design not in {"randomized_causal_estimand", "validated_causal_design"}:
        raise ClaimCompileError(
            "Causal wording is not permitted for the declared evidence design: "
            + ", ".join(causal_terms)
        )
    certainty = candidate.get("certainty")
    if not isinstance(certainty, dict) or not certainty.get("framework") or not certainty.get("judgment"):
        raise ClaimCompileError("A framework-specific certainty judgment is required")
    judgment = str(certainty["judgment"]).casefold().replace("_", " ")
    if judgment in {"low", "very low", "very-low"} and any(
        term in lowered for term in ("demonstrates", "establishes", "confirms")
    ):
        raise ClaimCompileError("Strong certainty wording is not allowed for low or very-low certainty")

    numeric_support = candidate.get("numeric_support") or []
    if not isinstance(numeric_support, list):
        raise ClaimCompileError("numeric_support must be a list")
    numeric_ok, unsupported_numbers = _match_supported_numbers(text, numeric_support)
    if not numeric_ok:
        raise ClaimCompileError("Unsupported numeric tokens in claim: " + ", ".join(unsupported_numbers))

    allowed_verbs = list(candidate.get("allowed_verbs") or DEFAULT_ALLOWED_VERBS[claim_type])
    if not allowed_verbs:
        raise ClaimCompileError("At least one allowed verb or phrase is required")
    if not any(verb.casefold() in lowered for verb in allowed_verbs):
        raise ClaimCompileError("Claim does not use any declared support-bounded verb")

    now = created_at_utc or datetime.now(timezone.utc).isoformat()
    output = {
        "schema_version": "1.0",
        "claim_id": str(candidate.get("claim_id") or ""),
        "claim_type": claim_type,
        "text": text,
        "scope": candidate.get("scope"),
        "certainty": certainty,
        "allowed_verbs": allowed_verbs,
        "evidence_node_ids": evidence_nodes,
        "assertion_ids": assertion_ids,
        "analysis_output_ids": analysis_outputs,
        "counterevidence_node_ids": list(candidate.get("counterevidence_node_ids") or []),
        "status": "accepted",
        "created_by": candidate.get("created_by"),
        "verification": {
            "status": "passed",
            "support_check": True,
            "numeric_check": numeric_ok,
            "scope_check": bool(candidate.get("scope_verified", False)),
            "verified_by": str(candidate["support_verifier_id"]),
            "verified_at_utc": now,
            "notes": "Compiled against declared evidence, numeric support, scope, certainty, and wording policy.",
        },
        "human_responsibility": {
            "status": "pending", "responsible_by": "", "accepted_at_utc": None,
        },
        "created_at_utc": now,
        "updated_at_utc": now,
    }
    if not output["verification"]["scope_check"]:
        raise ClaimCompileError("Scope verification must pass before a claim can be accepted")
    try:
        validate_document(output, "claim")
    except SchemaValidationError as exc:
        raise ClaimCompileError(str(exc)) from exc
    return output
