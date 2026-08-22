"""Deterministically bind selected evidence to identity, version, study, and result fields."""

from __future__ import annotations

from collections import Counter
from datetime import date
import re
import unicodedata
from typing import Any, Iterable


class EvidenceSemanticVerifierError(ValueError):
    """Raised when a verifier input is ambiguous or structurally unsafe."""


def _title(value: Any) -> str:
    return " ".join(unicodedata.normalize("NFKC", str(value)).casefold().split())


def _doi(value: Any) -> str:
    text = str(value).strip().casefold()
    text = re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", "", text)
    return text.rstrip("./")


def _reject(
    rejected: list[dict[str, str]], binding_id: str, reason: str,
) -> None:
    rejected.append({"binding_id": binding_id, "reason": reason})


def _identity_reason(record: dict[str, Any], identity: dict[str, Any]) -> str | None:
    required = {"title", "doi", "version_id", "study_family_id"}
    if not isinstance(identity, dict) or set(identity) != required:
        raise EvidenceSemanticVerifierError("identity binding must contain exact title, DOI, version, and study family fields")
    if _doi(identity["doi"]) != _doi(record.get("doi")):
        return "doi_mismatch"
    if _title(identity["title"]) != _title(record.get("title")):
        return "title_mismatch"
    if str(identity["version_id"]) != str(record.get("version_id")):
        return "version_mismatch"
    if str(identity["study_family_id"]) != str(record.get("study_family_id")):
        return "study_family_mismatch"
    return None


_RESULT_FIELDS = (
    "arm",
    "comparator_arm",
    "timepoint",
    "effect_measure",
    "effect_value",
    "numerator",
    "denominator",
    "source_span_sha256",
)


def _result_reason(record: dict[str, Any], proposed: dict[str, Any]) -> str | None:
    required = {"result_id", *_RESULT_FIELDS}
    if not isinstance(proposed, dict) or set(proposed) != required:
        raise EvidenceSemanticVerifierError("result binding must contain exact estimand, value, denominator, and source-span fields")
    results = record.get("results")
    if not isinstance(results, list):
        raise EvidenceSemanticVerifierError("record results must be an array")
    matches = [item for item in results if str(item.get("result_id")) == str(proposed["result_id"])]
    if len(matches) != 1:
        return "unknown_or_ambiguous_result"
    expected = matches[0]
    for field in _RESULT_FIELDS:
        if proposed[field] != expected.get(field):
            return {
                "arm": "arm_mismatch",
                "comparator_arm": "comparator_arm_mismatch",
                "timepoint": "timepoint_mismatch",
                "effect_measure": "effect_measure_mismatch",
                "effect_value": "effect_value_mismatch",
                "numerator": "numerator_mismatch",
                "denominator": "denominator_mismatch",
                "source_span_sha256": "source_span_mismatch",
            }[field]
    return None


def verify_evidence_bindings(
    records: Iterable[dict[str, Any]],
    bindings: Iterable[dict[str, Any]],
    *,
    cutoff: str,
) -> dict[str, Any]:
    """Reject identity collisions, wrong versions/studies, and wrong result semantics."""
    try:
        cutoff_date = date.fromisoformat(cutoff)
    except (TypeError, ValueError) as exc:
        raise EvidenceSemanticVerifierError("cutoff must be an ISO date") from exc
    record_list = list(records)
    record_ids = [str(item.get("id", "")) for item in record_list]
    if any(not value for value in record_ids) or len(record_ids) != len(set(record_ids)):
        raise EvidenceSemanticVerifierError("record IDs must be non-empty and unique")
    index = dict(zip(record_ids, record_list, strict=True))
    binding_list = list(bindings)
    binding_ids = [str(item.get("binding_id", "")) for item in binding_list]
    if any(not value for value in binding_ids) or len(binding_ids) != len(set(binding_ids)):
        raise EvidenceSemanticVerifierError("binding_id values must be non-empty and unique")

    accepted: list[str] = []
    rejected: list[dict[str, str]] = []
    for binding in binding_list:
        if not isinstance(binding, dict) or set(binding) != {"binding_id", "record_id", "identity", "result"}:
            raise EvidenceSemanticVerifierError("evidence binding uses unexpected or missing fields")
        binding_id = str(binding["binding_id"])
        record = index.get(str(binding["record_id"]))
        if record is None:
            _reject(rejected, binding_id, "unknown_record")
            continue
        verification = record.get("cutoff_verification")
        try:
            observed_date = date.fromisoformat(str(verification.get("conservative_latest_date")))
        except (AttributeError, TypeError, ValueError):
            _reject(rejected, binding_id, "unverified_date")
            continue
        if verification.get("status") != "passed" or observed_date > cutoff_date:
            _reject(rejected, binding_id, "post_cutoff")
            continue
        reason = _identity_reason(record, binding["identity"])
        if reason is None:
            reason = _result_reason(record, binding["result"])
        if reason is None:
            accepted.append(binding_id)
        else:
            _reject(rejected, binding_id, reason)

    counts = Counter(item["reason"] for item in rejected)
    return {
        "accepted_binding_ids": accepted,
        "rejected_bindings": rejected,
        "audit": {
            "requested": len(binding_list),
            "accepted": len(accepted),
            "rejected": len(rejected),
            "reason_counts": dict(sorted(counts.items())),
        },
    }
