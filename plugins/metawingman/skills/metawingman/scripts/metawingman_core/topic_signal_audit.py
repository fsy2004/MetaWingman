"""Promote model proposals only after an independent, replayable signal audit."""

from __future__ import annotations

from typing import Any

from .schema_guard import validate_document


SIGNAL_NAMES = {
    "decision_relevance", "unresolved_uncertainty", "feasibility", "evidence_maturity",
    "nonduplication", "update_need", "equity_priority", "cross_domain_value",
    "contamination_risk", "ambiguity_risk",
}


class TopicSignalAuditError(ValueError):
    pass


def landscape_node_ids(landscape: dict[str, Any]) -> set[str]:
    nodes = landscape.get("nodes")
    if not isinstance(nodes, list):
        raise TopicSignalAuditError("landscape requires the canonical nodes array")
    values = {
        str(node.get("node_id")) for node in nodes
        if isinstance(node, dict) and isinstance(node.get("node_id"), str) and node.get("node_id")
    }
    if len(values) != len(nodes):
        raise TopicSignalAuditError("every landscape node requires a unique node_id")
    return values


def promote_proposal_after_independent_audit(
    proposal: dict[str, Any],
    audit: dict[str, Any],
    *,
    proposal_provider_id: str,
    landscape_id: str,
    landscape_node_ids: set[str],
    created_at_utc: str,
) -> dict[str, Any]:
    if proposal.get("status") != "requires_independent_signal_audit":
        raise TopicSignalAuditError("proposal is not awaiting independent signal audit")
    if audit.get("proposal_id") != proposal.get("proposal_id"):
        raise TopicSignalAuditError("audit is bound to another proposal")
    if not isinstance(proposal_provider_id, str) or not proposal_provider_id:
        raise TopicSignalAuditError("proposal provider identity is required")
    if audit.get("proposal_provider_id") != proposal_provider_id:
        raise TopicSignalAuditError("audit proposal-provider binding does not match")
    if audit.get("auditor_kind") not in {"deterministic_external_search", "provider", "human"}:
        raise TopicSignalAuditError("unsupported signal auditor")
    if audit.get("auditor_kind") == "provider" and audit.get("auditor_id") == proposal_provider_id:
        raise TopicSignalAuditError("the proposal provider cannot self-score its own topic")
    signals = audit.get("signals")
    if not isinstance(signals, dict) or set(signals) != SIGNAL_NAMES:
        raise TopicSignalAuditError("every frozen opportunity signal requires an audit")
    cleaned_signals: dict[str, dict[str, Any]] = {}
    for name in sorted(SIGNAL_NAMES):
        signal = signals[name]
        calculation_id = signal.get("calculation_id") if isinstance(signal, dict) else None
        if not isinstance(calculation_id, str) or not calculation_id:
            raise TopicSignalAuditError(f"{name} lacks a replayable calculation identifier")
        evidence = signal.get("evidence_node_ids")
        if not isinstance(evidence, list) or not evidence:
            raise TopicSignalAuditError(f"{name} lacks evidence nodes")
        unknown = set(evidence) - landscape_node_ids
        if unknown:
            raise TopicSignalAuditError(f"{name} references unknown evidence: {sorted(unknown)}")
        cleaned_signals[name] = {
            "value": signal.get("value"),
            "calibration_status": signal.get("calibration_status"),
            "basis": f"{signal.get('basis')} [calculation_id={calculation_id}]",
            "evidence_node_ids": list(dict.fromkeys(evidence)),
        }
    source_families = list(dict.fromkeys(audit.get("source_family_ids") or []))
    if not source_families:
        raise TopicSignalAuditError("independent source families are required")
    feasibility = audit.get("feasibility_evidence")
    if not isinstance(feasibility, dict) or feasibility.get("independent_source_families") != len(source_families):
        raise TopicSignalAuditError("source-family count does not match feasibility evidence")
    leakage = audit.get("leakage_checks")
    if not isinstance(leakage, dict) or leakage.get("audit_status") != "passed" or any(
        leakage.get(field) for field in (
            "target_title_seen", "target_authors_seen", "target_identifier_seen",
            "target_descendant_seen", "post_cutoff_source_seen",
        )
    ):
        raise TopicSignalAuditError("proposal failed the identity or temporal leakage audit")
    candidate = {
        "schema_version": "1.0",
        "candidate_id": f"candidate-{proposal['proposal_id']}",
        "landscape_id": landscape_id,
        "generation_method": proposal["generation_method"],
        "question_framework": proposal["question_framework"],
        "concept_node_ids": proposal["concept_node_ids"],
        "evidence_node_ids": proposal["evidence_node_ids"],
        "source_family_ids": source_families,
        "signals": cleaned_signals,
        "feasibility_evidence": feasibility,
        "overlap_evidence": audit["overlap_evidence"],
        "leakage_checks": leakage,
        "operationalization": audit["operationalization"],
        "created_at_utc": created_at_utc,
    }
    try:
        validate_document(candidate, "topic_candidate")
    except Exception as exc:
        raise TopicSignalAuditError(str(exc)) from exc
    return candidate
