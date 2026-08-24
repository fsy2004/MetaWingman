#!/usr/bin/env python3
"""Network / graph search director — the agent's way of *searching* evidence.

Instead of a one-shot query list, the agent searches a graph of evidence: a seed
query expands into synonyms / MeSH / adjacent themes, then snowballs out of the
references and citations of the hits. At each step it consumes *landscape signals*
(comparator count, node coverage, update flag) to decide which direction to expand
and how deep — not to "search enough", but to close the specific evidence gap the
design decision needs. Deterministic and offline.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class SearchNode:
    term: str
    source: str
    hits: int = 0
    in_review: bool = False
    depth: int = 0


@dataclass(frozen=True)
class SearchPlan:
    phase: str                     # seed | expand | snowball | saturate
    queries: list[str]
    target_sources: list[str]
    depth_reason: str
    gap_ids: list[str]


def _expansion_terms(seed: str, sources: list[str]) -> list[str]:
    """Deterministic term expansion around a seed (synonym frame)."""
    return [
        seed.lower(),
        f"{seed} effectiveness",
        f"{seed} safety",
        f"{seed} systematic review",
    ]


def _snowball_terms(seed: str) -> list[str]:
    return [f"{seed} cited-by", f"{seed} references-of"]


def plan_next_search(
    nodes: list[SearchNode],
    landscape: dict[str, Any],
    *,
    seed: str = "",
    sources: list[str] | None = None,
    budget: int = 4,
) -> SearchPlan:
    sources = sources or ["pubmed", "embase", "cochrane_library", "clinicaltrials"]
    comparator = landscape.get("comparator_count") or 0
    is_update = bool(landscape.get("is_update"))
    nodes_covered = bool(landscape.get("n_nodes_assessed"))

    if not nodes:
        # phase 0: no search yet — emit the seed queries.
        return SearchPlan("seed", _expansion_terms(seed, sources)[:budget], sources,
                          "no evidence searched yet; seed queries for the clinical question.",
                          ["comparison_graph_coverage", "reference_standard_verification"])

    # saturated: node coverage present and enough comparators, no update requirement.
    if nodes_covered and comparator >= 3 and not is_update:
        return SearchPlan("saturate", [], [],
                          "comparison graph covered and sufficient comparators; "
                          "no further expansion needed (stop/search saturation).",
                          [])

    depth = max(node.depth for node in nodes) if nodes else 0
    # expand synonyms one level, then snowball on depth.
    if depth < 1:
        return SearchPlan("expand", _expansion_terms(seed, sources)[budget:], sources[:2],
                          "comparison graph or node coverage incomplete; broaden terms "
                          "into adjacent themes.", ["comparison_graph_coverage"])

    return SearchPlan("snowball", _snowball_terms(seed), sources,
                      "need to close the node/reference gap via citation snowballing; "
                      "expand from existing hits.",
                      ["node_coverage_assessment", "comparison_graph_coverage"])
