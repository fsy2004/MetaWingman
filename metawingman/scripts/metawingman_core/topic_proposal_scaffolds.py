"""Build small target-independent graph scaffolds for reliable topic proposal calls."""

from __future__ import annotations

import hashlib
from copy import deepcopy
from typing import Any

from .schema_guard import validate_document
from .state_store import sha256_json


class TopicProposalScaffoldError(ValueError):
    pass


def _seed_key(seed: int, value: str) -> str:
    return hashlib.sha256(f"{seed}|{value}".encode("utf-8")).hexdigest()


def build_topic_proposal_scaffolds(
    landscape: dict[str, Any], *, seed: int, maximum_scaffolds: int,
    maximum_publications: int, created_at_utc: str,
) -> dict[str, Any]:
    try:
        validate_document(landscape, "temporal_evidence_landscape")
    except Exception as exc:
        raise TopicProposalScaffoldError(str(exc)) from exc
    if not 1 <= maximum_scaffolds <= 20 or not 1 <= maximum_publications <= 500:
        raise TopicProposalScaffoldError("invalid scaffold limits")
    publications = {
        node["node_id"]: node for node in landscape["nodes"]
        if node["node_type"] != "concept"
    }
    concepts = {
        node["node_id"]: node for node in landscape["nodes"]
        if node["node_type"] == "concept"
    }
    if not publications or not concepts:
        raise TopicProposalScaffoldError("scaffolds require publication and concept nodes")
    by_concept: dict[str, set[str]] = {node_id: set() for node_id in concepts}
    by_publication: dict[str, set[str]] = {node_id: set() for node_id in publications}
    for edge in landscape["edges"]:
        source, target = edge["source_node_id"], edge["target_node_id"]
        if source in publications and target in concepts:
            by_concept[target].add(source)
            by_publication[source].add(target)
    active = [node_id for node_id in concepts if by_concept[node_id]]
    active.sort(key=lambda node_id: (-len(by_concept[node_id]), _seed_key(seed, node_id), node_id))
    if not active:
        raise TopicProposalScaffoldError("concept nodes have no publication support")

    concept_groups: list[list[str]] = [active[: min(12, len(active))]]
    for primary in active:
        cooccurrence: dict[str, int] = {}
        for publication_id in by_concept[primary]:
            for other in by_publication[publication_id] - {primary}:
                cooccurrence[other] = cooccurrence.get(other, 0) + 1
        companions = sorted(
            cooccurrence,
            key=lambda node_id: (-cooccurrence[node_id], _seed_key(seed, node_id), node_id),
        )[:2]
        group = [primary, *companions]
        if set(group) not in [set(existing) for existing in concept_groups]:
            concept_groups.append(group)
        if len(concept_groups) == maximum_scaffolds:
            break

    scaffolds: list[dict[str, Any]] = []
    for index, group in enumerate(concept_groups[:maximum_scaffolds], start=1):
        if index == 1:
            selected = sorted(publications, key=lambda value: (_seed_key(seed, value), value))[:maximum_publications]
            support = {
                concept_id: len(by_concept[concept_id] & set(selected)) for concept_id in active
            }
            group = sorted(
                (concept_id for concept_id, count in support.items() if count),
                key=lambda concept_id: (-support[concept_id], _seed_key(seed, concept_id), concept_id),
            )[:30]
        else:
            selected = []
            seen: set[str] = set()
            depth = 0
            buckets = {
                concept_id: sorted(by_concept[concept_id], key=lambda value: _seed_key(seed + index, value))
                for concept_id in group
            }
            while len(selected) < maximum_publications and any(depth < len(values) for values in buckets.values()):
                for concept_id in group:
                    values = buckets[concept_id]
                    if depth < len(values) and values[depth] not in seen:
                        selected.append(values[depth]); seen.add(values[depth])
                        if len(selected) == maximum_publications:
                            break
                depth += 1
        selected_set = set(selected)
        kept_edges = [
            deepcopy(edge) for edge in landscape["edges"]
            if edge["source_node_id"] in selected_set and edge["target_node_id"] in group
        ]
        supported_concepts = sorted({edge["target_node_id"] for edge in kept_edges})
        if not selected or not supported_concepts:
            continue
        scaffold_landscape = {
            "schema_version": "1.0",
            "landscape_id": f"{landscape['landscape_id']}-scaffold-{seed}-{index}",
            "run_context": landscape["run_context"],
            "domain_ids": deepcopy(landscape["domain_ids"]),
            "corpus_boundary": deepcopy(landscape["corpus_boundary"]),
            "nodes": [deepcopy(publications[node_id]) for node_id in selected]
            + [deepcopy(concepts[node_id]) for node_id in supported_concepts],
            "edges": kept_edges,
            "selection_policy": deepcopy(landscape["selection_policy"]),
            "created_at_utc": created_at_utc,
        }
        try:
            validate_document(scaffold_landscape, "temporal_evidence_landscape")
        except Exception as exc:
            raise TopicProposalScaffoldError(str(exc)) from exc
        scaffolds.append({
            "scaffold_id": f"scaffold-{seed}-{index}",
            "landscape": scaffold_landscape,
            "audit": {
                "source_landscape_sha256": sha256_json(landscape),
                "scaffold_landscape_sha256": sha256_json(scaffold_landscape),
                "seed": seed,
                "selected_publications": len(selected),
                "selected_concepts": len(supported_concepts),
                "target_identity_used": False,
                "selection_method": "uniform_evidence_then_degree_seeded_cooccurrence_scaffolds_v2",
            },
        })
    if not scaffolds:
        raise TopicProposalScaffoldError("no supported proposal scaffolds were produced")
    return {"schema_version": "1.0", "scaffolds": scaffolds}


def build_exhaustive_topic_proposal_shards(
    landscape: dict[str, Any], *, seed: int, maximum_publications: int,
    maximum_shards: int, created_at_utc: str,
) -> dict[str, Any]:
    """Partition every evidence node exactly once into bounded target-independent shards."""
    try:
        validate_document(landscape, "temporal_evidence_landscape")
    except Exception as exc:
        raise TopicProposalScaffoldError(str(exc)) from exc
    if not 1 <= maximum_publications <= 500 or not 1 <= maximum_shards <= 100:
        raise TopicProposalScaffoldError("invalid exhaustive shard limits")
    publications = {n["node_id"]: n for n in landscape["nodes"] if n["node_type"] != "concept"}
    concepts = {n["node_id"]: n for n in landscape["nodes"] if n["node_type"] == "concept"}
    if not publications or not concepts:
        raise TopicProposalScaffoldError("exhaustive shards require publication and concept nodes")
    ordered = sorted(publications, key=lambda node_id: (_seed_key(seed, node_id), node_id))
    chunks = [ordered[index:index + maximum_publications] for index in range(0, len(ordered), maximum_publications)]
    if len(chunks) > maximum_shards:
        raise TopicProposalScaffoldError(
            f"exhaustive coverage requires {len(chunks)} shards, above frozen maximum {maximum_shards}"
        )
    scaffolds: list[dict[str, Any]] = []
    for index, selected in enumerate(chunks, start=1):
        selected_set = set(selected)
        support: dict[str, int] = {}
        for edge in landscape["edges"]:
            if edge["source_node_id"] in selected_set and edge["target_node_id"] in concepts:
                support[edge["target_node_id"]] = support.get(edge["target_node_id"], 0) + 1
        kept_concepts = sorted(
            support, key=lambda node_id: (-support[node_id], _seed_key(seed + index, node_id), node_id)
        )[:30]
        kept_set = set(kept_concepts)
        kept_edges = [
            deepcopy(edge) for edge in landscape["edges"]
            if edge["source_node_id"] in selected_set and edge["target_node_id"] in kept_set
        ]
        shard = {
            "schema_version": "1.0",
            "landscape_id": f"{landscape['landscape_id']}-exhaustive-{seed}-{index}",
            "run_context": landscape["run_context"], "domain_ids": deepcopy(landscape["domain_ids"]),
            "corpus_boundary": deepcopy(landscape["corpus_boundary"]),
            "nodes": [deepcopy(publications[node_id]) for node_id in selected]
            + [deepcopy(concepts[node_id]) for node_id in kept_concepts],
            "edges": kept_edges, "selection_policy": deepcopy(landscape["selection_policy"]),
            "created_at_utc": created_at_utc,
        }
        validate_document(shard, "temporal_evidence_landscape")
        scaffolds.append({
            "scaffold_id": f"exhaustive-{seed}-{index}", "landscape": shard,
            "audit": {
                "source_landscape_sha256": sha256_json(landscape),
                "scaffold_landscape_sha256": sha256_json(shard), "seed": seed,
                "selected_publications": len(selected), "selected_concepts": len(kept_concepts),
                "target_identity_used": False,
                "selection_method": "seeded_exhaustive_evidence_partition_v1",
            },
        })
    return {
        "schema_version": "1.0", "scaffolds": scaffolds,
        "audit": {
            "source_publications": len(publications), "covered_publications": sum(len(x) for x in chunks),
            "coverage_fraction": 1.0, "overlap_count": 0, "target_identity_used": False,
        },
    }
