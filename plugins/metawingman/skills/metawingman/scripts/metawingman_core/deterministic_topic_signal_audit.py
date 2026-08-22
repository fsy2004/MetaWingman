"""Calculate replayable topic signals from frozen landscape and external-search facts."""

from __future__ import annotations

import hashlib
from datetime import date
from typing import Any

from .schema_guard import validate_document


class DeterministicTopicAuditError(ValueError):
    pass


_DECISION_ANCHOR_TYPES = {
    "guideline",
    "health_technology_assessment",
    "priority_statement",
    "stakeholder_decision",
}
_TRUSTED_DOMAIN_ASSIGNMENTS = {
    "explicit_record",
    "derived_from_explicit_records",
}


def _calculation_id(name: str, auditor_id: str, query_sha256s: list[str]) -> str:
    body = "|".join((name, auditor_id, *query_sha256s))
    return f"deterministic-{name}-" + hashlib.sha256(body.encode("utf-8")).hexdigest()[:16]


def _signal(
    name: str, value: float, basis: str, evidence: list[str],
    *, auditor_id: str, query_sha256s: list[str],
) -> dict[str, Any]:
    return {
        "value": max(0.0, min(1.0, float(value))),
        "calibration_status": "heuristic",
        "basis": basis,
        "calculation_id": _calculation_id(name, auditor_id, query_sha256s),
        "evidence_node_ids": list(dict.fromkeys(evidence)),
    }


def _unavailable_signal(
    name: str, basis: str, evidence: list[str],
    *, auditor_id: str, query_sha256s: list[str],
) -> dict[str, Any]:
    return {
        "value": None,
        "calibration_status": "unavailable",
        "basis": basis,
        "calculation_id": _calculation_id(name, auditor_id, query_sha256s),
        "evidence_node_ids": list(dict.fromkeys(evidence)),
    }


def _family_id(prefix: str, value: str) -> str:
    normalized = value.strip()
    if normalized.startswith(("study:", "source:")):
        return normalized
    return f"{prefix}:{normalized}"


def build_deterministic_topic_signal_audit(
    proposal: dict[str, Any],
    landscape: dict[str, Any],
    external_search_receipt: dict[str, Any],
    *,
    proposal_provider_id: str,
    auditor_id: str,
) -> dict[str, Any]:
    """Build an honest heuristic audit; no signal is represented as calibrated."""
    try:
        validate_document(landscape, "temporal_evidence_landscape")
    except Exception as exc:
        raise DeterministicTopicAuditError(str(exc)) from exc
    if proposal.get("status") != "requires_independent_signal_audit":
        raise DeterministicTopicAuditError("proposal is not awaiting signal audit")
    if not proposal_provider_id or not auditor_id or proposal_provider_id == auditor_id:
        raise DeterministicTopicAuditError("independent proposal and auditor identities are required")
    receipt = external_search_receipt
    if receipt.get("status") != "completed" or receipt.get("engine") != "ncbi_pubmed_eutils":
        raise DeterministicTopicAuditError("a completed NCBI external-search receipt is required")
    if receipt.get("provider_calls") != 0:
        raise DeterministicTopicAuditError("deterministic signal audit requires zero provider calls")
    if receipt.get("cutoff_date") != landscape["corpus_boundary"]["cutoff_date"]:
        raise DeterministicTopicAuditError("external-search cutoff does not match landscape")
    query_sha256s = receipt.get("query_sha256s")
    if not isinstance(query_sha256s, list) or not query_sha256s or not all(
        isinstance(value, str) and len(value) == 64 for value in query_sha256s
    ):
        raise DeterministicTopicAuditError("external queries require frozen SHA-256 identifiers")

    nodes = {node["node_id"]: node for node in landscape["nodes"]}
    proposal_evidence = list(dict.fromkeys(proposal.get("evidence_node_ids") or []))
    concepts = list(dict.fromkeys(proposal.get("concept_node_ids") or []))
    primary_ids = list(dict.fromkeys(receipt.get("primary_study_node_ids") or []))
    review_matches = receipt.get("review_matches") or []
    protocol_matches = receipt.get("protocol_matches") or []
    if not proposal_evidence or not primary_ids:
        raise DeterministicTopicAuditError("proposal evidence and independently found primary studies are required")
    review_ids = [str(item.get("node_id")) for item in review_matches if isinstance(item, dict)]
    protocol_ids = [str(item.get("node_id")) for item in protocol_matches if isinstance(item, dict)]
    interpretations = proposal.get("evidence_interpretations") or []
    interpretation_ids = [
        str(item.get("node_id")) for item in interpretations
        if isinstance(item, dict) and item.get("node_id")
    ]
    protocol_result_count = receipt.get("protocol_result_count")
    if not isinstance(protocol_result_count, int) or protocol_result_count < 0:
        raise DeterministicTopicAuditError("protocol result count is required")
    known_item_recall = receipt.get("proposal_evidence_recall")
    if not isinstance(known_item_recall, (int, float)) or not 0 <= float(known_item_recall) <= 1:
        raise DeterministicTopicAuditError("proposal-evidence recall is required")
    referenced = set(
        proposal_evidence + concepts + primary_ids + review_ids + protocol_ids + interpretation_ids
    )
    unknown = referenced - set(nodes)
    if unknown:
        raise DeterministicTopicAuditError(f"audit references unknown nodes: {sorted(unknown)}")
    if any(nodes[node_id]["node_type"] != "publication" for node_id in primary_ids + review_ids + protocol_ids):
        raise DeterministicTopicAuditError("external-search matches must reference publication nodes")

    overlaps: list[float] = []
    for item in review_matches:
        value = item.get("framework_overlap") if isinstance(item, dict) else None
        if not isinstance(value, (int, float)) or not 0 <= float(value) <= 1:
            raise DeterministicTopicAuditError("review framework overlap must be bounded from zero to one")
        overlaps.append(float(value))
    maximum_overlap = max(overlaps, default=0.0)
    family_map = receipt.get("primary_study_family_ids")
    unassigned_family_nodes: list[str] = []
    ambiguous_family_nodes: list[str] = []
    if family_map is not None:
        if not isinstance(family_map, dict) or not all(
            isinstance(key, str) and isinstance(value, str) and value.strip()
            for key, value in family_map.items()
        ):
            raise DeterministicTopicAuditError(
                "primary-study family mapping must bind node IDs to explicit family IDs"
            )
        missing_family_nodes = sorted(set(primary_ids) - set(family_map))
        if missing_family_nodes:
            raise DeterministicTopicAuditError(
                f"primary-study family mapping is incomplete: {missing_family_nodes}"
            )
        source_families = sorted({
            _family_id("study", family_map[node_id]) for node_id in primary_ids
        })
    else:
        family_assignments: dict[str, str] = {}
        for node_id in primary_ids:
            families = sorted({
                _family_id("source", str(family))
                for family in (nodes[node_id].get("source_family_ids") or [])
                if isinstance(family, str) and family.strip()
            })
            if not families:
                unassigned_family_nodes.append(node_id)
            elif len(families) > 1:
                ambiguous_family_nodes.append(node_id)
            else:
                family_assignments[node_id] = families[0]
        source_families = (
            sorted(set(family_assignments.values()))
            if not unassigned_family_nodes and not ambiguous_family_nodes else []
        )
    legacy_record_ids = sorted({
        str(source)
        for node_id in primary_ids
        for source in (nodes[node_id].get("source_ids") or [])
        if isinstance(source, str) and source.strip()
    })

    framework = proposal.get("question_framework") or {}
    framework_names = (
        "population", "intervention_or_exposure", "comparator", "outcome", "study_design",
    )
    arrays = [framework.get(name) for name in framework_names]
    complete_fields = sum(isinstance(value, list) and any(str(item).strip() for item in value) for value in arrays)
    synthesis_complete = bool(str(framework.get("synthesis_route") or "").strip())
    framework_completeness = (complete_fields + int(synthesis_complete)) / 6
    cutoff_date = date.fromisoformat(landscape["corpus_boundary"]["cutoff_date"])
    decision_anchor_ids: list[str] = []
    for item in interpretations:
        if not isinstance(item, dict) or item.get("role") != "decision_need":
            continue
        node_id = str(item.get("node_id") or "")
        node = nodes.get(node_id)
        if node is None or node.get("node_type") not in _DECISION_ANCHOR_TYPES:
            continue
        try:
            observed_at = date.fromisoformat(str(node.get("observed_at")))
        except ValueError as exc:
            raise DeterministicTopicAuditError("decision anchor lacks an auditable date") from exc
        if observed_at > cutoff_date:
            raise DeterministicTopicAuditError("decision anchor falls after the historical cutoff")
        if node.get("provenance_status") != "verified":
            continue
        decision_anchor_ids.append(node_id)
    decision_anchor_ids = list(dict.fromkeys(decision_anchor_ids))
    decision_anchor_types = sorted({nodes[node_id]["node_type"] for node_id in decision_anchor_ids})
    decision_relevance = (
        len(decision_anchor_types) / len(_DECISION_ANCHOR_TYPES)
        if decision_anchor_types else None
    )
    flattened = [str(item).casefold().strip() for values in arrays if isinstance(values, list) for item in values]
    placeholders = {"unknown", "unspecified", "tbd", "not specified"}
    ambiguity = sum(value in placeholders for value in flattened) / max(1, len(flattened))
    uncertainty_ids = [
        str(item.get("node_id")) for item in interpretations
        if isinstance(item, dict) and item.get("role") == "uncertainty" and item.get("node_id") in nodes
    ]
    uncertainty = min(1.0, len(uncertainty_ids) / max(1, len(proposal_evidence)))
    minimum_primary = int(landscape["selection_policy"]["minimum_primary_studies"])
    feasibility = min(1.0, len(primary_ids) / minimum_primary)
    years = {nodes[node_id]["observed_at"][:4] for node_id in primary_ids}
    maturity = min(1.0, (len(primary_ids) / max(1, minimum_primary)) * 0.75 + min(len(years), 3) / 12)
    newest_primary = date.fromisoformat(receipt["newest_primary_date"])
    newest_review_raw = receipt.get("newest_review_date")
    newest_review = date.fromisoformat(newest_review_raw) if newest_review_raw else None
    update_need = 1.0 if newest_review is not None and newest_primary > newest_review else 0.0
    equity_ids = [node_id for node_id in concepts if "equity" in nodes[node_id]["label"].casefold()]
    equity = 1.0 if equity_ids else 0.0
    domain_candidate_ids = list(dict.fromkeys(proposal_evidence + concepts))
    domain_evidence_ids = [
        node_id for node_id in domain_candidate_ids
        if nodes[node_id].get("domain_assignment_status") in _TRUSTED_DOMAIN_ASSIGNMENTS
        and nodes[node_id].get("domain_ids")
    ]
    unassigned_domain_nodes = sorted(set(domain_candidate_ids) - set(domain_evidence_ids))
    domains = sorted({
        str(domain) for node_id in domain_evidence_ids
        for domain in nodes[node_id]["domain_ids"]
    })
    domain_assignment_complete = bool(domains) and not unassigned_domain_nodes
    cross_domain = (
        min(1.0, max(0, len(domains) - 1) / 2)
        if domain_assignment_complete else None
    )
    boundary = landscape["corpus_boundary"]
    leakage_passed = boundary.get("leakage_audit") == "passed" and all(
        boundary.get(name) == "sealed" for name in (
            "target_identity_status", "target_descendants_status", "post_cutoff_evidence_status",
        )
    )
    if not leakage_passed:
        raise DeterministicTopicAuditError("landscape leakage boundary is not sealed and passed")

    decision_signal = (
        _signal(
            "decision_relevance", decision_relevance,
            "fraction of four cutoff-bound decision-anchor classes explicitly referenced: guideline, health technology assessment, priority statement, and stakeholder decision",
            decision_anchor_ids, auditor_id=auditor_id, query_sha256s=query_sha256s,
        )
        if decision_relevance is not None else
        _unavailable_signal(
            "decision_relevance",
            "unavailable: no verified cutoff-bound guideline, health technology assessment, priority statement, or stakeholder decision anchor was explicitly referenced",
            proposal_evidence, auditor_id=auditor_id, query_sha256s=query_sha256s,
        )
    )
    cross_domain_signal = (
        _signal(
            "cross_domain_value", cross_domain,
            "number of represented domains beyond one using explicit node-level domain assignments only",
            domain_evidence_ids, auditor_id=auditor_id, query_sha256s=query_sha256s,
        )
        if cross_domain is not None else
        _unavailable_signal(
            "cross_domain_value",
            "unavailable: proposal nodes lack explicit node-level domain assignments; landscape-wide domain scope is diagnostic only",
            proposal_evidence, auditor_id=auditor_id, query_sha256s=query_sha256s,
        )
    )
    signals = {
        "decision_relevance": decision_signal,
        "unresolved_uncertainty": _signal("unresolved_uncertainty", uncertainty, "share of proposal evidence explicitly interpreted as uncertainty", uncertainty_ids or proposal_evidence, auditor_id=auditor_id, query_sha256s=query_sha256s),
        "feasibility": _signal("feasibility", feasibility, "independently retrieved primary publications relative to frozen minimum", primary_ids, auditor_id=auditor_id, query_sha256s=query_sha256s),
        "evidence_maturity": _signal("evidence_maturity", maturity, "primary-publication count and distinct observed years relative to frozen minimum", primary_ids, auditor_id=auditor_id, query_sha256s=query_sha256s),
        "nonduplication": _signal("nonduplication", 1.0 - maximum_overlap, "one minus maximum deterministic framework overlap with retrieved reviews", review_ids or proposal_evidence, auditor_id=auditor_id, query_sha256s=query_sha256s),
        "update_need": _signal("update_need", update_need, "newest retrieved primary publication postdates newest overlapping review", list(dict.fromkeys(primary_ids + review_ids)), auditor_id=auditor_id, query_sha256s=query_sha256s),
        "equity_priority": _signal("equity_priority", equity, "explicit equity concept present in proposal subgraph", equity_ids or concepts or proposal_evidence, auditor_id=auditor_id, query_sha256s=query_sha256s),
        "cross_domain_value": cross_domain_signal,
        "contamination_risk": _signal("contamination_risk", 0.0, "sealed identity, descendant, and post-cutoff boundary passed", proposal_evidence, auditor_id=auditor_id, query_sha256s=query_sha256s),
        "ambiguity_risk": _signal("ambiguity_risk", ambiguity, "fraction of explicit placeholder terms in framework arrays", proposal_evidence, auditor_id=auditor_id, query_sha256s=query_sha256s),
    }
    return {
        "schema_version": "1.0",
        "proposal_id": proposal["proposal_id"],
        "proposal_provider_id": proposal_provider_id,
        "auditor_kind": "deterministic_external_search",
        "auditor_id": auditor_id,
        "source_family_ids": source_families,
        "signals": signals,
        "construct_validity": {
            "decision_relevance": {
                "status": "available" if decision_anchor_ids else "unavailable",
                "anchor_node_ids": decision_anchor_ids,
                "anchor_types": decision_anchor_types,
            },
            "cross_domain": {
                "status": "available" if domain_assignment_complete else "unavailable",
                "domain_ids": domains,
                "evidence_node_ids": domain_evidence_ids,
                "unassigned_node_ids": unassigned_domain_nodes,
            },
            "source_diversity": {
                "status": "available" if source_families else "unavailable",
                "family_ids": source_families,
                "primary_study_node_ids": primary_ids,
                "unassigned_node_ids": unassigned_family_nodes,
                "ambiguous_node_ids": ambiguous_family_nodes,
            },
        },
        "legacy_diagnostics": {
            "framework_completeness_fraction": framework_completeness,
            "landscape_global_domain_ids": list(landscape.get("domain_ids") or []),
            "record_identifier_count": len(legacy_record_ids),
            "record_identifiers": legacy_record_ids,
            "excluded_from_primary_signals": True,
        },
        "feasibility_evidence": {
            "primary_study_count": len(primary_ids),
            "independent_source_families": len(source_families),
            "known_item_recall": float(known_item_recall),
            "full_text_access_fraction": None,
            "extractable_result_fraction": None,
        },
        "overlap_evidence": {
            "maximum_existing_review_overlap": maximum_overlap,
            "active_protocol_overlap": protocol_result_count > 0,
            "update_justification": (
                "new primary publications postdate the newest overlapping review"
                if update_need else "no temporal update signal was established"
            ),
        },
        "leakage_checks": {
            "audit_status": "passed", "target_title_seen": False,
            "target_authors_seen": False, "target_identifier_seen": False,
            "target_descendant_seen": False, "post_cutoff_source_seen": False,
        },
        "operationalization": {
            "status": (
                "complete" if decision_anchor_ids and domain_assignment_complete and source_families else "incomplete"
            ),
            "missing_fields": [
                name for name, available in (
                    ("decision_relevance_anchor", bool(decision_anchor_ids)),
                    ("node_level_domain_ids", domain_assignment_complete),
                    ("study_or_source_family_ids", bool(source_families)),
                ) if not available
            ],
            "rationale": (
                "The question framework is explicit and every construct-bearing anchor is available."
                if decision_anchor_ids and domain_assignment_complete and source_families else
                "The question framework is explicit, but one or more construct-bearing anchors are unavailable; the candidate must abstain before scoring."
            ),
        },
        "external_search_receipt": receipt,
    }
