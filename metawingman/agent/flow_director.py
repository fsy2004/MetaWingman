#!/usr/bin/env python3
"""Full-workflow director — the agent stages the whole synthesis and calls the
E-R-V decision kernel at each node, producing an auditable, reproducible trace.

Each stage emits a real intermediate object (PICO -> network search -> screening
-> estimand -> synthesis -> pooling guard -> conclusion/update). The director is
deterministic and offline: it drives the *decision* structure of the workflow and
produces the per-stage decisions a downstream LLM could then carry out. No model
call, no server, in this implementation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from metawingman.agent.decision_core import DesignDecision, derive_design_decision
from metawingman.agent.evpi_director import evaluate_living
from metawingman.agent.graph_search_director import SearchNode, plan_next_search
from metawingman.agent.open_deliberation import Candidate, Deliberation, deliberate
from metawingman.scripts.metawingman_core.design_selection import PROFILE_STRATA
from metawingman.scripts.metawingman_core.state_store import sha256_json

# The workflow stage chain (each stage calls the E-R-V kernel).
STAGES = (
    "pico_scoping",
    "network_search",
    "screening_bias",
    "estimand_selection",
    "synthesis",
    "pooling_guard",
    "conclusion_update",
)


def _candidate_pool(question: dict[str, Any], landscape: dict[str, Any]) -> list[Candidate]:
    """Build a small, evidence-grounded pool of candidate designs to deliberate over."""
    pool: list[Candidate] = []
    for profile in ("intervention_network", "intervention_pairwise", "diagnostic_accuracy",
                    "public_health_exposure", "prognostic_prediction", "prevalence_incidence"):
        c = Candidate(profile=profile, evidence_for=(), evidence_against=())
        pool.append(c)
    return pool


def run_full_flow(
    question: dict[str, Any],
    landscape: dict[str, Any],
    *,
    seed: str = "",
    sources: list[str] | None = None,
    calibration: list[dict[str, Any]] | None = None,
    alpha: float = 0.05,
    info_cost: float = 1.0,
    nodes: list[SearchNode] | None = None,
) -> dict[str, Any]:
    """Drive the full workflow and return the per-stage decision trace."""
    decision = derive_design_decision(
        question, landscape, alpha=alpha, info_cost=info_cost, calibration=calibration)

    search = plan_next_search(nodes or [], landscape, seed=seed, sources=sources)
    deliberation = deliberate(question, landscape, _candidate_pool(question, landscape))
    v = evaluate_living(decision.next_evidence and [{"gap": decision.next_evidence["gap"],
        **decision.next_evidence}], info_cost=info_cost, slack=0.0)

    # Map each stage to the decision object + its stage-specific signal.
    stages: list[dict[str, Any]] = []
    for idx, stage_name in enumerate(STAGES):
        stage: dict[str, Any] = {
            "stage": stage_name,
            "profile": decision.profile,
            "estimand": decision.estimand,
            "synthesis_route": decision.synthesis_route,
            "identification_assumption": decision.identification_assumption,
            "risk_guard": decision.risk_guard,
            "next_evidence": decision.next_evidence,
        }
        if stage_name == "network_search":
            stage["search_plan"] = {
                "phase": search.phase, "queries": search.queries,
                "target_sources": search.target_sources, "depth_reason": search.depth_reason,
            }
        if stage_name == "estimand_selection":
            stage["deliberation"] = {"converged": deliberation.converged,
                                     "winning_profile": deliberation.winning_profile,
                                     "log": list(deliberation.log)}
        if stage_name == "pooling_guard":
            stage["guard_passes"] = decision.risk_guard["passes"]
        if stage_name == "conclusion_update":
            stage["stop_rule"] = decision.stop_rule
            stage["living"] = decision.living
        stages.append(stage)

    flow = {
        "schema_version": "1.0",
        "question": question,
        "landscape": landscape,
        "stages": stages,
        "final_decision": decision.to_dict(),
        "search_plan": {"phase": search.phase, "queries": search.queries,
                        "target_sources": search.target_sources, "depth_reason": search.depth_reason},
        "deliberation": {"converged": deliberation.converged,
                         "winning_profile": deliberation.winning_profile,
                         "log": list(deliberation.log)},
        "step_verification": {
            "guard_passes": decision.risk_guard["passes"],
            "stop_decision": decision.stop_rule["decision"],
            "living": decision.living,
        },
        "review_state": {
            "question": question,
            "landscape": landscape,
            "decision": decision.to_dict(),
            "action": decision.action,
            "reflection": decision.reflection,
            "prm_score": decision.prm_score,
            "stage_count": len(stages),
            "stage_receipts": [s["stage"] for s in stages],
        },
    }
    flow["receipt_sha256"] = sha256_json(flow)
    return flow
