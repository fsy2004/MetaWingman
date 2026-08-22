"""Build and compile provider-free PubMed searches for topic-signal opposition."""

from __future__ import annotations

import hashlib
import re
from typing import Any


class TopicExternalSearchError(ValueError):
    pass


def _clean_term(value: Any) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^A-Za-z0-9 -]", " ", str(value or ""))).strip()


def _dimension(values: Any) -> str:
    phrases = list(dict.fromkeys(_clean_term(value) for value in (values or []) if _clean_term(value)))[:3]
    stopwords = {"adult", "adults", "among", "and", "for", "people", "patients", "the", "with"}
    tokens = [
        token.casefold() for phrase in phrases for token in phrase.split()
        if len(token) >= 4 and token.casefold() not in stopwords
    ]
    terms = list(dict.fromkeys([*phrases, *tokens]))[:8]
    if not terms:
        raise TopicExternalSearchError("population, intervention, and outcome terms are required")
    return "(" + " OR ".join(f'"{term}"[Title/Abstract]' for term in terms) + ")"


def _primary_design_filter(values: Any) -> str:
    text = " ".join(map(str, values or [])).casefold()
    filters: list[str] = []
    if any(term in text for term in ("random", "trial", "intervention")):
        filters.append("randomized controlled trial[Publication Type]")
    if any(term in text for term in ("cohort", "longitudinal", "observational")):
        filters.extend(("cohort studies[MeSH Terms]", "observational study[Publication Type]"))
    if "cross-sectional" in text or "cross sectional" in text:
        filters.append("cross-sectional studies[MeSH Terms]")
    if "case-control" in text or "case control" in text:
        filters.append("case-control studies[MeSH Terms]")
    if not filters:
        filters.extend((
            "randomized controlled trial[Publication Type]", "cohort studies[MeSH Terms]",
            "cross-sectional studies[MeSH Terms]", "case-control studies[MeSH Terms]",
            "observational study[Publication Type]",
        ))
    return "(" + " OR ".join(dict.fromkeys(filters)) + ")"


def _evidence_expansion(proposal: dict[str, Any], landscape: dict[str, Any] | None) -> list[str]:
    if not landscape:
        return []
    evidence_ids = set(map(str, proposal.get("evidence_node_ids") or []))
    framework_text = " ".join(
        map(str, sum((values for values in (proposal.get("question_framework") or {}).values() if isinstance(values, list)), []))
    ).casefold()
    existing = set(re.findall(r"[a-z0-9]+", framework_text))
    stop = {
        "after", "among", "children", "cohort", "duration", "hours", "importance", "multicenter",
        "schoolchildren", "sleep", "study", "time", "with", "without",
    }
    candidates: list[str] = []
    for node in landscape.get("nodes", []):
        if node.get("node_id") not in evidence_ids or node.get("node_type") == "concept":
            continue
        for token in re.findall(r"[a-z][a-z0-9-]{3,}", str(node.get("label") or "").casefold()):
            if token not in existing and token not in stop:
                candidates.append(token)
    return list(dict.fromkeys(candidates))[:12]


def build_topic_audit_queries(
    proposal: dict[str, Any], *, cutoff_date: str, lower_date: str,
    landscape: dict[str, Any] | None = None,
) -> dict[str, str]:
    framework = proposal.get("question_framework") or {}
    exposure = _dimension(framework.get("intervention_or_exposure"))
    expansions = _evidence_expansion(proposal, landscape)
    if expansions:
        exposure = "(" + exposure + " OR " + " OR ".join(
            f'"{term}"[Title/Abstract]' for term in expansions
        ) + ")"
    base = " AND ".join((
        _dimension(framework.get("population")),
        exposure,
        _dimension(framework.get("outcome")),
    ))
    start = lower_date.replace("-", "/")
    end = cutoff_date.replace("-", "/")
    dates = f'("{start}"[Date - Publication] : "{end}"[Date - Publication])'
    primary_filter = _primary_design_filter(framework.get("study_design"))
    return {
        "primary_studies": f"{base} AND {primary_filter} AND {dates}",
        "reviews": f"{base} AND (systematic review[Publication Type] OR meta-analysis[Publication Type]) AND {dates}",
        "protocols": f"{base} AND protocol[Title] AND {dates}",
    }


_STOPWORDS = {"a", "an", "and", "for", "in", "of", "or", "the", "to", "with"}


def _tokens(value: Any) -> set[str]:
    return {
        token for token in re.findall(r"[a-z0-9]+", str(value or "").casefold())
        if len(token) > 2 and token not in _STOPWORDS
    }


def _framework_overlap(proposal: dict[str, Any], title: str) -> float:
    framework = proposal["question_framework"]
    title_tokens = _tokens(title)
    dimensions = []
    for name in ("population", "intervention_or_exposure", "outcome"):
        terms = set().union(*(_tokens(value) for value in framework.get(name, [])))
        dimensions.append(bool(terms & title_tokens))
    return sum(dimensions) / len(dimensions)


def compile_topic_external_search_receipt(
    proposal: dict[str, Any],
    landscape: dict[str, Any],
    raw_results: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    expected = {"primary_studies", "reviews", "protocols"}
    if set(raw_results) != expected:
        raise TopicExternalSearchError("three exact external-search result classes are required")
    by_pmid: dict[str, dict[str, Any]] = {}
    for node in landscape.get("nodes", []):
        if node.get("node_type") != "publication":
            continue
        for source_id in node.get("source_ids", []):
            if str(source_id).startswith("pmid:"):
                by_pmid[str(source_id).split(":", 1)[1]] = node
    mapped: dict[str, list[dict[str, Any]]] = {}
    unmapped: set[str] = set()
    query_sha256s: list[str] = []
    query_audit: list[dict[str, Any]] = []
    for kind in sorted(expected):
        result = raw_results[kind]
        query = str(result.get("query") or "")
        if not query:
            raise TopicExternalSearchError(f"{kind} lacks its executed query")
        query_sha = hashlib.sha256(query.encode("utf-8")).hexdigest()
        query_sha256s.append(query_sha)
        nodes = []
        for pmid in list(dict.fromkeys(str(value) for value in result.get("pmids", []))):
            node = by_pmid.get(pmid)
            if node is None:
                unmapped.add(pmid)
            else:
                nodes.append(node)
        mapped[kind] = nodes
        query_audit.append({
            "kind": kind, "query": query, "query_sha256": query_sha,
            "returned_pmids": len(result.get("pmids", [])), "mapped_landscape_nodes": len(nodes),
        })
    primary = mapped["primary_studies"]
    reviews = mapped["reviews"]
    protocols = mapped["protocols"]
    retrieved_node_ids = {
        node["node_id"] for values in mapped.values() for node in values
    }
    proposal_publication_ids = {
        node_id for node_id in proposal.get("evidence_node_ids", [])
        if node_id in {node["node_id"] for node in by_pmid.values()}
    }
    proposal_evidence_recall = (
        len(proposal_publication_ids & retrieved_node_ids) / len(proposal_publication_ids)
        if proposal_publication_ids else None
    )
    return {
        "schema_version": "1.0", "status": "completed",
        "engine": "ncbi_pubmed_eutils",
        "cutoff_date": landscape["corpus_boundary"]["cutoff_date"],
        "provider_calls": 0,
        "query_sha256s": sorted(query_sha256s),
        "queries": query_audit,
        "primary_study_node_ids": sorted(node["node_id"] for node in primary),
        "review_matches": sorted((
            {"node_id": node["node_id"], "framework_overlap": _framework_overlap(proposal, node["label"])}
            for node in reviews
        ), key=lambda item: item["node_id"]),
        "protocol_matches": sorted((
            {"node_id": node["node_id"], "framework_overlap": _framework_overlap(proposal, node["label"])}
            for node in protocols
        ), key=lambda item: item["node_id"]),
        "protocol_result_count": len(raw_results["protocols"].get("pmids", [])),
        "proposal_evidence_recall": proposal_evidence_recall,
        "newest_primary_date": max((node["observed_at"] for node in primary), default=None),
        "newest_review_date": max((node["observed_at"] for node in reviews), default=None),
        "unmapped_pmids": sorted(unmapped),
    }
