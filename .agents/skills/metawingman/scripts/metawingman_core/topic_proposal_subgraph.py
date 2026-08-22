"""Build bounded, target-free proposal subgraphs from broad historical landscapes."""

from __future__ import annotations

import hashlib
from copy import deepcopy
from typing import Any

from .schema_guard import validate_document
from .state_store import sha256_json


class TopicProposalSubgraphError(ValueError):
    pass


def _seeded_key(seed: int, node_id: str) -> str:
    return hashlib.sha256(f"{seed}|{node_id}".encode("utf-8")).hexdigest()


def build_topic_proposal_subgraph(
    landscape: dict[str, Any],
    *,
    seed: int,
    maximum_publications: int,
    created_at_utc: str,
) -> dict[str, Any]:
    try:
        validate_document(landscape, "temporal_evidence_landscape")
    except Exception as exc:
        raise TopicProposalSubgraphError(str(exc)) from exc
    if maximum_publications < 1:
        raise TopicProposalSubgraphError("maximum_publications must be positive")
    publications = {
        node["node_id"]: node for node in landscape["nodes"]
        if node["node_type"] == "publication"
    }
    concepts = {
        node["node_id"]: node for node in landscape["nodes"]
        if node["node_type"] != "publication"
    }
    if not publications or not concepts:
        raise TopicProposalSubgraphError("proposal subgraph requires publication and concept nodes")
    buckets: dict[str, list[str]] = {node_id: [] for node_id in concepts}
    for edge in landscape["edges"]:
        source = edge["source_node_id"]
        target = edge["target_node_id"]
        if source in publications and target in buckets:
            buckets[target].append(source)
    for node_id in buckets:
        buckets[node_id] = sorted(set(buckets[node_id]), key=lambda value: _seeded_key(seed, value))

    selected: list[str] = []
    selected_set: set[str] = set()
    depth = 0
    active = [node_id for node_id in sorted(buckets) if buckets[node_id]]
    while len(selected) < maximum_publications and any(depth < len(buckets[node_id]) for node_id in active):
        for concept_id in active:
            if depth < len(buckets[concept_id]):
                publication_id = buckets[concept_id][depth]
                if publication_id not in selected_set:
                    selected.append(publication_id)
                    selected_set.add(publication_id)
                    if len(selected) == maximum_publications:
                        break
        depth += 1
    for publication_id in sorted(publications, key=lambda value: _seeded_key(seed, value)):
        if len(selected) == maximum_publications:
            break
        if publication_id not in selected_set:
            selected.append(publication_id)
            selected_set.add(publication_id)

    kept_edges = [
        deepcopy(edge) for edge in landscape["edges"]
        if edge["source_node_id"] in selected_set and edge["target_node_id"] in concepts
    ]
    concept_sources: dict[str, set[str]] = {}
    for edge in kept_edges:
        concept_sources.setdefault(edge["target_node_id"], set()).update(edge["source_ids"])
    kept_concepts = []
    for concept_id in sorted(concept_sources):
        node = deepcopy(concepts[concept_id])
        node["source_ids"] = sorted(concept_sources[concept_id])
        kept_concepts.append(node)
    subgraph = {
        "schema_version": "1.0",
        "landscape_id": f"{landscape['landscape_id']}-proposal-{seed}",
        "run_context": landscape["run_context"],
        "domain_ids": deepcopy(landscape["domain_ids"]),
        "corpus_boundary": deepcopy(landscape["corpus_boundary"]),
        "nodes": [deepcopy(publications[node_id]) for node_id in selected] + kept_concepts,
        "edges": kept_edges,
        "selection_policy": deepcopy(landscape["selection_policy"]),
        "created_at_utc": created_at_utc,
    }
    try:
        validate_document(subgraph, "temporal_evidence_landscape")
    except Exception as exc:
        raise TopicProposalSubgraphError(str(exc)) from exc
    return {
        "landscape": subgraph,
        "audit": {
            "source_landscape_sha256": sha256_json(landscape),
            "proposal_landscape_sha256": sha256_json(subgraph),
            "seed": seed,
            "full_publications": len(publications),
            "selected_publications": len(selected),
            "selected_concepts": len(kept_concepts),
            "selected_edges": len(kept_edges),
            "selection_method": "concept_stratified_seeded_round_robin_then_seeded_fill",
            "target_identity_used": False,
        },
    }
