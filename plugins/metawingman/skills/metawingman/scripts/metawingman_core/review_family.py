"""Conservative family-candidate clustering for published systematic reviews."""

from __future__ import annotations

import hashlib
import itertools
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any

from .schema_guard import validate_document
from .state_store import sha256_json


GENERIC_TITLE_TOKENS = {
    "a", "an", "and", "of", "in", "on", "for", "to", "the", "with", "by",
    "from", "among", "systematic", "review", "reviews", "meta", "analysis",
    "analyses", "updated", "update", "evidence", "study", "studies", "report",
    "screening", "guideline", "clinical", "preventive", "services", "task", "force",
    "alert", "surveillance", "note", "corrigendum", "erratum", "correction",
    "comment", "comments", "correspondence", "response", "reply", "authors",
    "expression", "concern", "retraction", "notice", "article",
}


class ReviewFamilyError(ValueError):
    """Raised when a corpus cannot be converted into a family registry."""


class _UnionFind:
    def __init__(self, identifiers: list[str]):
        self.parent = {identifier: identifier for identifier in identifiers}

    def find(self, identifier: str) -> str:
        parent = self.parent[identifier]
        if parent != identifier:
            self.parent[identifier] = self.find(parent)
        return self.parent[identifier]

    def union(self, left: str, right: str) -> None:
        left_root, right_root = self.find(left), self.find(right)
        if left_root != right_root:
            self.parent[max(left_root, right_root)] = min(left_root, right_root)


def _title_tokens(title: str) -> frozenset[str]:
    normalized = unicodedata.normalize("NFKC", title).casefold()
    tokens = re.findall(r"[a-z0-9]+", normalized)
    return frozenset(
        token for token in tokens
        if token not in GENERIC_TITLE_TOKENS and not token.isdigit() and len(token) > 1
    )


def _normalized_title(title: str) -> str:
    return " ".join(sorted(_title_tokens(title)))


def _first_author(authors: str) -> str:
    first = re.split(r"[,;]", unicodedata.normalize("NFKC", authors).casefold(), maxsplit=1)[0]
    words = re.findall(r"[a-z]+", first)
    return words[0] if words else ""


def _identifier(prefix: str, values: list[str]) -> str:
    digest = hashlib.sha256("\n".join(sorted(values)).encode("utf-8")).hexdigest()[:16]
    return f"{prefix}:{digest}"


def _suggested_split(family_id: str) -> str:
    bucket = int(hashlib.sha256(family_id.encode("utf-8")).hexdigest()[:8], 16) % 100
    if bucket < 80:
        return "train"
    if bucket < 90:
        return "development"
    return "test"


def build_review_family_registry(
    corpus: dict[str, Any],
    *,
    source_path: str,
    minimum_shared_tokens: int = 4,
    general_jaccard: float = 0.8,
    same_first_author_jaccard: float = 0.65,
    maximum_year_gap: int = 10,
    common_token_cap: int = 200,
    generated_at_utc: str | None = None,
) -> dict[str, Any]:
    records = corpus.get("records")
    if not isinstance(records, list):
        raise ReviewFamilyError("corpus records must be an array")
    by_id = {str(record.get("record_id", "")): record for record in records}
    if not all(by_id) or len(by_id) != len(records):
        raise ReviewFamilyError("corpus record IDs must be non-empty and unique")
    if not 0 <= same_first_author_jaccard <= general_jaccard <= 1:
        raise ReviewFamilyError("family similarity thresholds are invalid")
    tokens = {identifier: _title_tokens(record["title"]) for identifier, record in by_id.items()}
    normalized = {
        identifier: _normalized_title(record["title"]) for identifier, record in by_id.items()
    }
    authors = {identifier: _first_author(record.get("authors", "")) for identifier, record in by_id.items()}
    inverted: dict[str, list[str]] = defaultdict(list)
    for identifier, values in tokens.items():
        for token in values:
            inverted[token].append(identifier)
    shared_counts: Counter[tuple[str, str]] = Counter()
    for identifiers in inverted.values():
        if not 2 <= len(identifiers) <= common_token_cap:
            continue
        for left, right in itertools.combinations(sorted(identifiers), 2):
            shared_counts[(left, right)] += 1
    exact_groups: dict[str, list[str]] = defaultdict(list)
    for identifier, value in normalized.items():
        if value:
            exact_groups[value].append(identifier)
    pairs = {
        pair for pair, count in shared_counts.items() if count >= minimum_shared_tokens
    }
    for identifiers in exact_groups.values():
        if len(identifiers) > 1:
            pairs.update(itertools.combinations(sorted(identifiers), 2))
    edges: list[dict[str, Any]] = []
    union_find = _UnionFind(sorted(by_id))
    for left, right in sorted(pairs):
        left_tokens, right_tokens = tokens[left], tokens[right]
        shared = len(left_tokens & right_tokens)
        union = len(left_tokens | right_tokens)
        jaccard = shared / union if union else 0.0
        year_gap = abs(int(by_id[left]["year"]) - int(by_id[right]["year"]))
        same_author = bool(authors[left] and authors[left] == authors[right])
        if normalized[left] == normalized[right] and normalized[left]:
            rule = "exact_normalized_title"
        elif year_gap <= maximum_year_gap and jaccard >= general_jaccard:
            rule = "high_title_overlap"
        elif (
            year_gap <= maximum_year_gap
            and same_author
            and jaccard >= same_first_author_jaccard
        ):
            rule = "author_supported_overlap"
        else:
            continue
        union_find.union(left, right)
        edges.append({
            "edge_id": _identifier("edge", [left, right]),
            "left_record_id": left,
            "right_record_id": right,
            "rule": rule,
            "title_jaccard": round(jaccard, 6),
            "shared_title_tokens": shared,
            "year_gap": year_gap,
            "same_first_author": same_author,
            "status": "requires_audit",
        })
    groups: dict[str, list[str]] = defaultdict(list)
    for identifier in sorted(by_id):
        groups[union_find.find(identifier)].append(identifier)
    families: list[dict[str, Any]] = []
    for members in sorted(groups.values(), key=lambda values: values[0]):
        family_id = _identifier("family", members)
        integrity_blocked = any(
            by_id[identifier].get("admission_status") in {
                "hold_integrity_review", "exclude_retracted"
            }
            for identifier in members
        )
        has_reference_candidate = any(
            by_id[identifier].get("admission_status") == "development_candidate"
            for identifier in members
        )
        if integrity_blocked:
            status, split = "blocked_integrity", "not_applicable"
        elif not has_reference_candidate:
            status, split = "excluded_non_reference", "not_applicable"
        elif len(members) > 1:
            status, split = "candidate_requires_audit", _suggested_split(family_id)
        else:
            status, split = "provisional_singleton", _suggested_split(family_id)
        families.append({
            "family_id": family_id,
            "record_ids": members,
            "status": status,
            "suggested_split": split,
            "split_status": "blocked_pending_family_audit",
        })
    status_counts = Counter(family["status"] for family in families)
    registry = {
        "schema_version": "1.0",
        "generated_at_utc": generated_at_utc or datetime.now(timezone.utc).isoformat(),
        "source_corpus": {
            "path": source_path,
            "sha256": sha256_json(corpus),
            "records": len(records),
        },
        "algorithm": {
            "name": "conservative_title_family_candidates",
            "version": "1.0",
            "minimum_shared_tokens": minimum_shared_tokens,
            "general_jaccard": general_jaccard,
            "same_first_author_jaccard": same_first_author_jaccard,
            "maximum_year_gap": maximum_year_gap,
            "common_token_cap": common_token_cap,
            "automatic_confirmation": False,
            "split_policy": "family_hash_80_10_10_suggestion_only",
        },
        "summary": {
            "records": len(records),
            "families": len(families),
            "provisional_singletons": status_counts["provisional_singleton"],
            "candidate_families": status_counts["candidate_requires_audit"],
            "blocked_integrity_families": status_counts["blocked_integrity"],
            "excluded_non_reference_families": status_counts["excluded_non_reference"],
            "candidate_edges": len(edges),
            "held_out_ready_families": 0,
        },
        "families": families,
        "candidate_edges": edges,
    }
    validate_document(registry, "review_family_registry")
    return registry


def audit_review_families(
    registry: dict[str, Any],
    corpus: dict[str, Any],
    decisions: list[dict[str, Any]],
) -> dict[str, Any]:
    """Recompute family components from human-confirmed edges.

    Emits an audit report without rewriting the registry: registry schema 1.0
    hard-codes held_out_ready_families=0, so confirmed families and held-out
    candidates live in this report until the registry schema evolves.
    """
    records = corpus.get("records")
    if not isinstance(records, list):
        raise ReviewFamilyError("corpus records must be an array")
    admission = {str(record.get("record_id", "")): str(record.get("admission_status", "")) for record in records}
    if not all(admission) or len(admission) != len(records):
        raise ReviewFamilyError("corpus record IDs must be non-empty and unique")
    edges = {edge["edge_id"]: edge for edge in registry.get("candidate_edges", [])}
    if len(edges) != len(registry.get("candidate_edges", [])):
        raise ReviewFamilyError("registry candidate edge IDs must be unique")
    confirmed_edges: list[tuple[str, str]] = []
    seen: set[str] = set()
    rejected = 0
    for decision in decisions:
        edge_id = decision.get("edge_id")
        verdict = decision.get("decision")
        if verdict not in {"confirm", "reject"}:
            raise ReviewFamilyError(f"decision must be confirm or reject: {edge_id}")
        if edge_id not in edges:
            raise ReviewFamilyError(f"decision references unknown edge: {edge_id}")
        if edge_id in seen:
            raise ReviewFamilyError(f"duplicate decision for edge: {edge_id}")
        seen.add(edge_id)
        if verdict == "confirm":
            edge = edges[edge_id]
            confirmed_edges.append((edge["left_record_id"], edge["right_record_id"]))
        else:
            rejected += 1
    components = _UnionFind(sorted(admission))
    for left, right in confirmed_edges:
        if left not in admission or right not in admission:
            raise ReviewFamilyError("confirmed edge references a record outside the corpus")
        components.union(left, right)
    grouped: dict[str, list[str]] = defaultdict(list)
    for record_id in sorted(admission):
        grouped[components.find(record_id)].append(record_id)
    registry_membership: dict[str, set[str]] = defaultdict(set)
    for family in registry.get("families", []):
        registry_membership[family["family_id"]] = set(family["record_ids"])
    pending_edges = set(edges) - seen
    families: list[dict[str, Any]] = []
    held_out_candidates: list[str] = []
    confirmed_families = 0
    for members in sorted(grouped.values(), key=lambda values: values[0]):
        family_id = _identifier("family", members)
        integrity_blocked = any(
            admission[identifier] in {"hold_integrity_review", "exclude_retracted"}
            for identifier in members
        )
        has_reference = any(
            admission[identifier] == "development_candidate" for identifier in members
        )
        if integrity_blocked:
            status = "blocked_integrity"
        elif not has_reference:
            status = "excluded_non_reference"
        elif len(members) == 1:
            status = "provisional_singleton"
        elif any(
            {edges[edge_id]["left_record_id"], edges[edge_id]["right_record_id"]} <= set(members)
            for edge_id in pending_edges
        ):
            status = "unconfirmed_candidate"
        else:
            status = "confirmed"
        bucket = int(hashlib.sha256(family_id.encode("utf-8")).hexdigest()[:8], 16) % 100
        suggested = "train" if bucket < 80 else ("development" if bucket < 90 else "test")
        held_out = status == "confirmed" and len(members) >= 2 and suggested == "test"
        if held_out:
            held_out_candidates.append(family_id)
        if status == "confirmed":
            confirmed_families += 1
        families.append({
            "family_id": family_id,
            "record_ids": members,
            "status": status,
            "suggested_split": suggested,
            "held_out_candidate": held_out,
        })
    report = {
        "schema_version": "1.0",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "decisions": {
            "total": len(decisions),
            "confirmed": len(confirmed_edges),
            "rejected": rejected,
            "pending_edges": len(pending_edges),
        },
        "summary": {
            "families": len(families),
            "confirmed_families": confirmed_families,
            "held_out_candidates": len(held_out_candidates),
        },
        "families": families,
        "held_out_candidates": held_out_candidates,
    }
    validate_document(report, "family_audit_report")
    return report
