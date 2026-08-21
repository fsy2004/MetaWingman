"""Immutable-style evidence-constrained search over joint review designs."""

from __future__ import annotations

import copy
import math
from dataclasses import dataclass
from typing import Any

from .schema_guard import validate_document
from .state_store import sha256_json


class QuestionSynthesisSearchError(ValueError):
    """Raised when a search transition violates evidence or budget boundaries."""


@dataclass(frozen=True)
class SearchBudget:
    max_nodes: int
    max_model_calls: int
    max_verifier_calls: int
    max_rounds: int


ALLOWED_MUTATIONS = {
    "narrow_scope", "broaden_scope", "split_question", "change_comparator",
    "change_outcome", "change_time_horizon", "change_design",
    "switch_review_family", "switch_synthesis_route", "request_evidence",
    "reject_duplicate", "abstain_no_pooling",
}


def _budget(value: dict[str, Any]) -> SearchBudget:
    try:
        budget = SearchBudget(**{field: int(value[field]) for field in SearchBudget.__annotations__})
    except (KeyError, TypeError, ValueError) as exc:
        raise QuestionSynthesisSearchError("search budget is incomplete") from exc
    if any(getattr(budget, field) < 1 for field in SearchBudget.__annotations__):
        raise QuestionSynthesisSearchError("search budget values must be positive")
    return budget


def _node(candidate: dict[str, Any]) -> dict[str, Any]:
    validate_document(candidate, "question_synthesis_candidate")
    level = candidate.get("uncertainty", {}).get("level", "unknown")
    uncertainty = {"low": 0.2, "moderate": 0.5, "high": 0.8, "unknown": 1.0}[level]
    return {
        "candidate_id": candidate["candidate_id"],
        "candidate": copy.deepcopy(candidate),
        "verified_objective_sum": 0.0,
        "downstream_impact": 0.0,
        "uncertainty": uncertainty,
        "visits": 0,
        "hard_failed": candidate.get("disposition") in {"rejected", "abstained"},
        "leakage_failed": False,
    }


def start_question_synthesis_search(
    landscape: dict[str, Any],
    context: dict[str, Any],
    seed_candidates: list[dict[str, Any]],
    budget: dict[str, Any],
    *,
    created_at_utc: str,
) -> dict[str, Any]:
    frozen_budget = _budget(budget)
    if not seed_candidates:
        raise QuestionSynthesisSearchError("at least one seed candidate is required")
    nodes = sorted((_node(item) for item in seed_candidates), key=lambda item: item["candidate_id"])
    ids = [item["candidate_id"] for item in nodes]
    if len(ids) != len(set(ids)):
        raise QuestionSynthesisSearchError("candidate ids must be unique")
    if len(nodes) > frozen_budget.max_nodes:
        raise QuestionSynthesisSearchError("seed candidates exceed max_nodes")
    if any(item["candidate"]["context_id"] != context["context_id"] for item in nodes):
        raise QuestionSynthesisSearchError("seed candidate context mismatch")
    evidence_ids = sorted(str(item["node_id"]) for item in landscape.get("nodes", []) if "node_id" in item)
    identity = {"landscape_id": landscape.get("landscape_id"), "context_id": context["context_id"], "candidate_ids": ids, "budget": budget}
    search = {
        "schema_version": "1.0",
        "search_id": f"question-search-{sha256_json(identity)[:20]}",
        "landscape_id": str(landscape.get("landscape_id") or ""),
        "context_id": context["context_id"],
        "policy": {"exploration_weight": 1.0, "known_evidence_ids": evidence_ids, "parent_visits": 0},
        "budget": {**budget, "model_calls_used": 0, "verifier_calls_used": 0, "rounds_used": 0},
        "nodes": nodes,
        "edges": [],
        "observations": [],
        "portfolio": [],
        "status": "active",
        "created_at_utc": created_at_utc,
        "updated_at_utc": created_at_utc,
    }
    validate_document(search, "question_synthesis_search")
    return search


def frontier_priority(node: dict[str, Any], parent_visits: int, exploration_weight: float) -> tuple[float, str]:
    value = float(node["verified_objective_sum"])
    impact = float(node["downstream_impact"])
    uncertainty = float(node["uncertainty"])
    visits = int(node["visits"])
    exploration = exploration_weight * uncertainty * math.sqrt(parent_visits + 1) / (visits + 1)
    return value + impact + exploration, str(node["candidate_id"])


def select_frontier_node(search: dict[str, Any]) -> str:
    eligible = [item for item in search["nodes"] if not item["hard_failed"] and not item["leakage_failed"]]
    if not eligible:
        raise QuestionSynthesisSearchError("no eligible frontier node remains")
    parent_visits = int(search["policy"].get("parent_visits", 0))
    weight = float(search["policy"].get("exploration_weight", 1.0))
    ranked = sorted(eligible, key=lambda item: (-frontier_priority(item, parent_visits, weight)[0], item["candidate_id"]))
    return str(ranked[0]["candidate_id"])


def apply_candidate_mutation(
    search: dict[str, Any],
    mutation: dict[str, Any],
    observation: dict[str, Any],
    *,
    updated_at_utc: str,
) -> dict[str, Any]:
    if search.get("status") != "active":
        raise QuestionSynthesisSearchError("search is not active")
    mutation_type = str(mutation.get("type") or "")
    if mutation_type not in ALLOWED_MUTATIONS:
        raise QuestionSynthesisSearchError("unknown mutation type")
    known = set(search["policy"].get("known_evidence_ids", []))
    referenced = set(observation.get("evidence_anchor_ids", []))
    if not referenced.issubset(known):
        raise QuestionSynthesisSearchError("mutation observation references unknown evidence")
    if int(search["budget"].get("rounds_used", 0)) >= int(search["budget"]["max_rounds"]):
        raise QuestionSynthesisSearchError("search round budget exhausted")
    next_search = copy.deepcopy(search)
    child = mutation.get("candidate")
    child_id = None
    if child is not None:
        if len(next_search["nodes"]) >= int(next_search["budget"]["max_nodes"]):
            raise QuestionSynthesisSearchError("search node budget exhausted")
        child_node = _node(child)
        if any(item["candidate_id"] == child_node["candidate_id"] for item in next_search["nodes"]):
            raise QuestionSynthesisSearchError("mutation candidate id already exists")
        next_search["nodes"].append(child_node)
        child_id = child_node["candidate_id"]
    next_search["edges"].append(
        {
            "parent_candidate_id": mutation.get("parent_candidate_id"),
            "child_candidate_id": child_id,
            "mutation_type": mutation_type,
            "actor_capability": mutation.get("actor_capability", "deterministic"),
            "provider_receipt_id": mutation.get("provider_receipt_id"),
            "verifier_observations": [copy.deepcopy(observation)],
            "disposition_reason": mutation.get("rationale", "evidence-constrained transition"),
        }
    )
    next_search["observations"].append(copy.deepcopy(observation))
    next_search["budget"]["rounds_used"] = int(next_search["budget"].get("rounds_used", 0)) + 1
    next_search["updated_at_utc"] = updated_at_utc
    next_search["nodes"].sort(key=lambda item: item["candidate_id"])
    validate_document(next_search, "question_synthesis_search")
    return next_search


def finalize_question_portfolio(search: dict[str, Any], *, updated_at_utc: str) -> dict[str, Any]:
    result = copy.deepcopy(search)
    result["portfolio"] = [select_frontier_node(result)]
    result["status"] = "complete"
    result["updated_at_utc"] = updated_at_utc
    validate_document(result, "question_synthesis_search")
    return result
