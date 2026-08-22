"""Build a target-free historical topic landscape from a frozen broad corpus."""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter
from datetime import date
from typing import Any

from .schema_guard import validate_document


class LandscapeBuildError(ValueError):
    pass


_DECISION_ANCHOR_TYPES = {
    "guideline": "guideline",
    "hta": "health_technology_assessment",
    "health_technology_assessment": "health_technology_assessment",
    "priority": "priority_statement",
    "priority_statement": "priority_statement",
    "stakeholder": "stakeholder_decision",
    "stakeholder_decision": "stakeholder_decision",
}


def _normal(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").casefold()).strip()


def _sha(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _observed_publication_date(row: dict[str, Any], cutoff: date) -> date:
    raw_value = row.get("first_publication_date")
    raw_date = str(raw_value or "")[:10]
    try:
        return date.fromisoformat(raw_date)
    except ValueError:
        verification = row.get("cutoff_verification")
        if not isinstance(verification, dict) or (
            verification.get("status") != "passed"
            or verification.get("raw_publication_date") != raw_value
            or verification.get("cutoff") != cutoff.isoformat()
        ):
            raise LandscapeBuildError("record lacks a bound audited conservative publication date")
        try:
            observed = date.fromisoformat(str(verification["conservative_latest_date"]))
        except (KeyError, TypeError, ValueError) as exc:
            raise LandscapeBuildError("record lacks a bound audited conservative publication date") from exc
        return observed


def _explicit_domain_ids(row: dict[str, Any], allowed: set[str]) -> list[str]:
    raw = row.get("domain_ids")
    if raw is None:
        return []
    if not isinstance(raw, list) or not all(isinstance(item, str) and item.strip() for item in raw):
        raise LandscapeBuildError("record domain_ids must be an explicit string array")
    values = sorted(set(item.strip() for item in raw))
    unknown = set(values) - allowed
    if unknown:
        raise LandscapeBuildError(f"record domain_ids fall outside the frozen landscape scope: {sorted(unknown)}")
    return values


def _family_values(row: dict[str, Any], singular: str, plural: str) -> list[str]:
    raw_plural = row.get(plural)
    raw_singular = row.get(singular)
    if raw_plural is not None and raw_singular is not None:
        raise LandscapeBuildError(f"record cannot define both {singular} and {plural}")
    raw = raw_plural if raw_plural is not None else raw_singular
    if raw is None:
        return []
    values = raw if isinstance(raw, list) else [raw]
    if not all(isinstance(item, str) and item.strip() for item in values):
        raise LandscapeBuildError(f"record {singular}/{plural} must contain explicit identifiers")
    return sorted(set(item.strip() for item in values))


def _explicit_source_family_ids(row: dict[str, Any]) -> list[str]:
    study = _family_values(row, "study_family_id", "study_family_ids")
    if study:
        return [value if value.startswith("study:") else f"study:{value}" for value in study]
    source = _family_values(row, "source_family_id", "source_family_ids")
    return [value if value.startswith("source:") else f"source:{value}" for value in source]


def _derive_corpus_concepts(
    records: list[dict[str, Any]],
    derivation: dict[str, Any],
) -> list[dict[str, Any]]:
    if derivation.get("method") != "corpus_ngram_document_frequency_v1":
        raise LandscapeBuildError("unsupported target-independent concept derivation method")
    maximum = int(derivation.get("maximum_concepts") or 0)
    minimum_df = int(derivation.get("minimum_document_frequency") or 0)
    if not 1 <= maximum <= 200 or minimum_df < 2:
        raise LandscapeBuildError("invalid corpus-derived concept limits")
    stopwords = {
        "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "in", "is",
        "of", "on", "or", "that", "the", "this", "to", "was", "were", "with",
    }
    boilerplate = {
        "analysis", "controlled", "effect", "effects", "meta", "randomized", "review",
        "study", "studies", "systematic", "trial", "trials",
    }
    counts: Counter[str] = Counter()
    for record in records:
        text = _normal(" ".join((str(record.get("title") or ""), str(record.get("abstract") or ""))))
        tokens = [
            token for token in re.findall(r"[a-z][a-z0-9-]{2,}", text)
            if token not in stopwords
        ]
        phrases: set[str] = set()
        for width in (1, 2, 3):
            for index in range(0, len(tokens) - width + 1):
                phrase_tokens = tokens[index:index + width]
                if all(token in boilerplate for token in phrase_tokens):
                    continue
                phrases.add(" ".join(phrase_tokens))
        counts.update(phrases)
    total = max(1, len(records))
    ranked = sorted(
        (
            (frequency * math.log((total + 1) / (frequency + 0.5)) * (1 + 0.15 * phrase.count(" ")), frequency, phrase)
            for phrase, frequency in counts.items()
            if frequency >= minimum_df and frequency <= max(minimum_df, int(total * 0.5))
        ),
        key=lambda item: (-item[0], -item[1], item[2]),
    )
    selected: list[tuple[str, int]] = []
    for _, frequency, phrase in ranked:
        phrase_tokens = set(phrase.split())
        if any(
            len(phrase_tokens & set(existing.split())) / len(phrase_tokens | set(existing.split())) > 0.8
            for existing, _ in selected
        ):
            continue
        selected.append((phrase, frequency))
        if len(selected) == maximum:
            break
    if not selected:
        raise LandscapeBuildError("target-independent concept derivation produced no concepts")
    return [{
        "node_id": "concept-auto-" + hashlib.sha256(phrase.encode("utf-8")).hexdigest()[:16],
        "node_type": "concept",
        "label": phrase,
        "patterns": [phrase],
        "document_frequency": frequency,
    } for phrase, frequency in selected]


def _derive_corpus_concepts_v2(
    records: list[dict[str, Any]], derivation: dict[str, Any],
) -> list[dict[str, Any]]:
    maximum = int(derivation.get("maximum_concepts") or 0)
    minimum_df = int(derivation.get("minimum_document_frequency") or 0)
    if not 1 <= maximum <= 200 or minimum_df < 2:
        raise LandscapeBuildError("invalid corpus-derived concept limits")
    stopwords = set("""
        a about after again against all am an and any are as at be because been before being below between
        both but by can could did do does doing down during each few for from further had has have having he
        her here hers herself him himself his how i if in into is it its itself just may me might more most
        must my myself no nor not now of off on once only or other our ours ourselves out over own same she
        should so some such than that the their theirs them themselves then there these they this those through
        to too under until up very was we were what when where which while who whom why will with would you
        your yours yourself yourselves among compared significantly significant associated increased higher
        lower mean total results data using years age group groups patients patient clinical index time
    """.split())
    boilerplate = {
        "analysis", "controlled", "effect", "effects", "meta", "randomized", "review",
        "study", "studies", "systematic", "trial", "trials", "background", "objective",
        "methods", "results", "conclusion", "conclusions",
    }
    counts: Counter[str] = Counter()
    for record in records:
        text = _normal(" ".join((str(record.get("title") or ""), str(record.get("abstract") or ""))))
        tokens = re.findall(r"[a-z][a-z0-9-]{2,}", text)
        phrases: set[str] = set()
        for width in (1, 2, 3):
            for index in range(0, len(tokens) - width + 1):
                phrase_tokens = tokens[index:index + width]
                if phrase_tokens[0] in stopwords or phrase_tokens[-1] in stopwords:
                    continue
                if all(token in stopwords or token in boilerplate for token in phrase_tokens):
                    continue
                if width == 1 and phrase_tokens[0] in boilerplate:
                    continue
                phrases.add(" ".join(phrase_tokens))
        counts.update(phrases)
    total = max(1, len(records))
    ranked = sorted((
        (
            math.log1p(frequency) * math.log((total + 1) / (frequency + 0.5))
            * (1 + 0.65 * phrase.count(" ")),
            frequency,
            phrase,
        )
        for phrase, frequency in counts.items()
        if minimum_df <= frequency <= max(minimum_df, int(total * 0.5))
    ), key=lambda item: (-item[0], -item[1], item[2]))
    selected: list[tuple[str, int]] = []
    for _, frequency, phrase in ranked:
        phrase_tokens = set(phrase.split())
        if any(
            len(phrase_tokens & set(existing.split())) / len(phrase_tokens | set(existing.split())) > 0.8
            for existing, _ in selected
        ):
            continue
        selected.append((phrase, frequency))
        if len(selected) == maximum:
            break
    if not selected:
        raise LandscapeBuildError("target-independent concept derivation produced no concepts")
    return [{
        "node_id": "concept-auto-v2-" + hashlib.sha256(phrase.encode("utf-8")).hexdigest()[:16],
        "node_type": "concept", "label": phrase, "patterns": [phrase],
        "document_frequency": frequency,
    } for phrase, frequency in selected]


def _derive_decision_opportunity_concepts(
    records: list[dict[str, Any]], derivation: dict[str, Any],
) -> list[dict[str, Any]]:
    maximum = int(derivation.get("maximum_concepts") or 0)
    minimum_df = int(derivation.get("minimum_document_frequency") or 0)
    maximum_df = int(derivation.get("maximum_document_frequency") or 200)
    if not 1 <= maximum <= 200 or minimum_df < 2 or maximum_df < minimum_df:
        raise LandscapeBuildError("invalid decision-opportunity concept limits")
    stopwords = set("""
        a about after again against all am an and any are as at be because been before being below between
        both but by can could did do does doing down during each few for from further had has have having he
        her here hers herself him himself his how i if in into is it its itself just may me might more most
        must my myself no nor not now of off on once only or other our ours ourselves out over own same she
        should so some such than that the their theirs them themselves then there these they this those through
        to too under until up very was we were what when where which while who whom why will with would you
        your yours yourself yourselves among compared significantly significant associated increased higher
        lower mean total results data using years age group groups patients patient clinical index time
    """.split())
    method_terms = set("""
        analysis analyses assess assessed association associations background conclusion conclusions conducted
        controlled data determine differences efficacy evaluate evaluated examining examine examined investigate
        investigated logistic meta method methods model models objective performed prevalence prospective randomized
        regression results retrospective review statistically study studies survey systematic trial trials used
    """.split())
    documents: list[tuple[set[str], bool, int]] = []
    years: list[int] = []
    for record in records:
        text = _normal(" ".join((str(record.get("title") or ""), str(record.get("abstract") or ""))))
        tokens = re.findall(r"[a-z][a-z0-9-]{2,}", text)
        phrases: set[str] = set()
        for width in (1, 2, 3):
            for index in range(0, len(tokens) - width + 1):
                words = tokens[index:index + width]
                if words[0] in stopwords or words[-1] in stopwords:
                    continue
                if width == 1 and words[0] in method_terms:
                    continue
                if sum(word in method_terms for word in words) >= max(1, width - 1):
                    continue
                phrases.add(" ".join(words))
        publication_types = " ".join(map(str, record.get("publication_types") or [])).casefold()
        title = str(record.get("title") or "").casefold()
        is_review = any(term in publication_types or term in title for term in ("systematic review", "meta-analysis", "meta analysis", "review"))
        raw_year = str(record.get("first_publication_date") or "")[:4]
        year = int(raw_year) if raw_year.isdigit() else 0
        years.append(year)
        documents.append((phrases, is_review, year))
    valid_years = sorted(year for year in years if year)
    recent_boundary = valid_years[len(valid_years) // 2] if valid_years else 0
    stats: dict[str, list[int]] = {}
    for phrases, is_review, year in documents:
        for phrase in phrases:
            values = stats.setdefault(phrase, [0, 0, 0])
            values[0] += 1
            values[1] += int(is_review)
            values[2] += int(not is_review and year >= recent_boundary)
    total = max(1, len(records))
    ranked: list[tuple[float, int, str]] = []
    for phrase, (frequency, reviews, recent_primary) in stats.items():
        if not minimum_df <= frequency <= maximum_df:
            continue
        primary = frequency - reviews
        if primary < minimum_df:
            continue
        idf = math.log((total + 1) / (frequency + 0.5))
        nonduplication = 1 - reviews / frequency
        recent_share = recent_primary / primary
        phrase_specificity = 1 + 0.35 * phrase.count(" ")
        score = math.log1p(primary) * idf * nonduplication * (0.75 + 0.5 * recent_share) * phrase_specificity
        ranked.append((score, frequency, phrase))
    ranked.sort(key=lambda item: (-item[0], -item[1], item[2]))
    selected: list[tuple[str, int]] = []
    if derivation.get("method") == "decision_opportunity_ngram_v2":
        buckets = {width: [item for item in ranked if item[2].count(" ") == width] for width in (0, 1, 2)}
        positions = {width: 0 for width in buckets}
        while len(selected) < maximum and any(positions[w] < len(buckets[w]) for w in buckets):
            for width in (0, 1, 2):
                while positions[width] < len(buckets[width]):
                    _, frequency, phrase = buckets[width][positions[width]]; positions[width] += 1
                    tokens = set(phrase.split())
                    if any(len(tokens & set(old.split())) / len(tokens | set(old.split())) > 0.8 for old, _ in selected):
                        continue
                    selected.append((phrase, frequency))
                    break
                if len(selected) == maximum:
                    break
    else:
        for _, frequency, phrase in ranked:
            tokens = set(phrase.split())
            if any(len(tokens & set(old.split())) / len(tokens | set(old.split())) > 0.8 for old, _ in selected):
                continue
            selected.append((phrase, frequency))
            if len(selected) == maximum:
                break
    if not selected:
        raise LandscapeBuildError("decision-opportunity concept derivation produced no concepts")
    return [{
        "node_id": "concept-opportunity-" + hashlib.sha256(phrase.encode("utf-8")).hexdigest()[:16],
        "node_type": "concept", "label": phrase, "patterns": [phrase], "document_frequency": frequency,
    } for phrase, frequency in selected]


def build_broad_temporal_landscape(
    records: list[dict[str, Any]],
    spec: dict[str, Any],
    forbidden_identity_patterns: list[str],
    *,
    created_at_utc: str,
) -> dict[str, Any]:
    if spec.get("query_class") != "broad_non_target_domain_query":
        raise LandscapeBuildError("topic landscape requires a broad non-target domain query")
    minimum = int(spec.get("minimum_records") or 0)
    if len(records) < minimum:
        raise LandscapeBuildError("broad landscape is below the frozen minimum record floor")
    forbidden = [_normal(item) for item in forbidden_identity_patterns if _normal(item)]
    if not forbidden:
        raise LandscapeBuildError("sealed target identity patterns are required for leakage audit")
    query = _normal(spec.get("query_text"))
    if any(pattern in query for pattern in forbidden):
        raise LandscapeBuildError("target identity leakage detected in broad query")
    cutoff = date.fromisoformat(spec["cutoff_date"])

    publication_nodes: list[dict[str, Any]] = []
    searchable: dict[str, str] = {}
    observed: dict[str, str] = {}
    allowed_domains = set(spec["domain_ids"])
    for row in records:
        record_id = str(row.get("id") or "")
        title = str(row.get("title") or "").strip()
        try:
            published = _observed_publication_date(row, cutoff)
        except LandscapeBuildError as exc:
            raise LandscapeBuildError(f"record {record_id} {exc}") from exc
        if published > cutoff:
            raise LandscapeBuildError(f"post-cutoff record detected: {record_id}")
        identity_text = _normal(" ".join((title, str(row.get("doi") or ""), str(row.get("pmid") or ""))))
        if any(pattern in identity_text for pattern in forbidden):
            raise LandscapeBuildError(f"target identity leakage detected: {record_id}")
        if not record_id or not title:
            raise LandscapeBuildError("every landscape record requires an ID and title")
        node_id = "publication-" + hashlib.sha256(record_id.encode("utf-8")).hexdigest()[:16]
        domains = _explicit_domain_ids(row, allowed_domains)
        source_families = _explicit_source_family_ids(row)
        anchor_type = _normal(row.get("decision_anchor_type"))
        node_type = _DECISION_ANCHOR_TYPES.get(anchor_type, "publication")
        publication_nodes.append({
            "node_id": node_id,
            "node_type": node_type,
            "label": title,
            "domain_ids": domains,
            "domain_assignment_status": "explicit_record" if domains else "unavailable",
            "observed_at": published.isoformat(),
            "source_ids": [record_id],
            "source_family_ids": source_families,
            "provenance_status": "verified",
        })
        searchable[node_id] = _normal(" ".join((title, str(row.get("abstract") or ""))))
        observed[node_id] = published.isoformat()

    concept_nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    derivation = spec.get("concept_derivation")
    if isinstance(derivation, dict):
        if derivation.get("method") in {"decision_opportunity_ngram_v1", "decision_opportunity_ngram_v2"}:
            concepts = _derive_decision_opportunity_concepts(records, derivation)
        elif derivation.get("method") == "corpus_ngram_document_frequency_v2":
            concepts = _derive_corpus_concepts_v2(records, derivation)
        else:
            concepts = _derive_corpus_concepts(records, derivation)
    else:
        concepts = spec.get("concepts", [])
    for concept in concepts:
        patterns = [_normal(item) for item in concept.get("patterns", []) if _normal(item)]
        matches = [node for node in publication_nodes if any(pattern in searchable[node["node_id"]] for pattern in patterns)]
        if not matches:
            continue
        complete_domain_assignment = all(
            node["domain_assignment_status"] == "explicit_record" and node["domain_ids"]
            for node in matches
        )
        concept_domains = (
            sorted({domain for node in matches for domain in node["domain_ids"]})
            if complete_domain_assignment else []
        )
        concept_nodes.append({
            "node_id": concept["node_id"],
            "node_type": concept["node_type"],
            "label": concept["label"],
            "domain_ids": concept_domains,
            "domain_assignment_status": (
                "derived_from_explicit_records" if concept_domains else "unavailable"
            ),
            "observed_at": min(node["observed_at"] for node in matches),
            "source_ids": sorted(source_id for node in matches for source_id in node["source_ids"]),
            "source_family_ids": sorted({
                family for node in matches for family in node["source_family_ids"]
            }),
            "provenance_status": "machine_extracted",
        })
        for node in matches:
            edge_body = f"{node['node_id']}|{concept['node_id']}"
            edges.append({
                "edge_id": "edge-" + hashlib.sha256(edge_body.encode("utf-8")).hexdigest()[:16],
                "source_node_id": node["node_id"],
                "target_node_id": concept["node_id"],
                "relation": "mentions",
                "observed_at": node["observed_at"],
                "source_ids": node["source_ids"],
            })
    if not concept_nodes:
        raise LandscapeBuildError("frozen broad concept vocabulary matched no records")

    landscape = {
        "schema_version": "1.0",
        "landscape_id": spec["landscape_id"],
        "run_context": spec["run_context"],
        "domain_ids": spec["domain_ids"],
        "corpus_boundary": {
            "cutoff_date": spec["cutoff_date"],
            "target_identity_status": "sealed",
            "target_descendants_status": "sealed",
            "post_cutoff_evidence_status": "sealed",
            "leakage_audit": "passed",
            "excluded_identity_fields": [
                "title", "authors", "doi", "pmid", "journal", "abstract",
                "keywords", "citations", "descendants",
            ],
        },
        "nodes": [*publication_nodes, *concept_nodes],
        "edges": edges,
        "selection_policy": spec["selection_policy"],
        "created_at_utc": created_at_utc,
        "build_audit": {
            "query_class": spec["query_class"],
            "query_sha256": _sha(spec["query_text"]),
            "forbidden_identity_patterns_sha256": _sha(sorted(forbidden)),
            "input_records": len(records),
            "included_records": len(publication_nodes),
            "concept_nodes": len(concept_nodes),
            "edges": len(edges),
            "nodes_with_explicit_domains": sum(
                node["domain_assignment_status"] != "unavailable"
                for node in [*publication_nodes, *concept_nodes]
            ),
            "nodes_with_explicit_source_families": sum(
                bool(node["source_family_ids"])
                for node in [*publication_nodes, *concept_nodes]
            ),
            "raw_abstracts_exported": False,
            "concept_source": (
                str(derivation.get("method")) if isinstance(derivation, dict)
                else "manual_frozen_vocabulary"
            ),
        },
    }
    try:
        validate_document(landscape, "temporal_evidence_landscape")
    except Exception as exc:
        raise LandscapeBuildError(str(exc)) from exc
    return landscape
