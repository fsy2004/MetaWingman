#!/usr/bin/env python3
"""Method-trace fidelity — how closely an agent's procedural decisions match a
*real top-journal published systematic review* (the expert reference).

This replaces a subjective external judge. The standard is agreement with the
published expert reference (published_expert_reference): we compare the agent's
method trajectory against a gold expert trajectory extracted from an actual
published review, *with outcome values stripped* so the agent cannot cheat by
memorising the result. Higher fidelity = closer to a seasoned systematic-review
author. Deterministic and offline.

Fidelity dimensions (each 0..1):
  design_selection        whether the chosen review profile matches the reference
  estimand_identification whether the causal/identification assumption matches
  synthesis_route         whether the synthesis route matches
  stop_decision           whether the living/stop decision matches
  guard_consistency       whether the risk-controlled guard agrees (poolable or not)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from metawingman.scripts.metawingman_core.design_selection import SYNTHESIS_ROUTES

WEIGHTS = {
    "design_selection": 0.30,
    "estimand_identification": 0.20,
    "synthesis_route": 0.20,
    "stop_decision": 0.15,
    "guard_consistency": 0.15,
}

DIMENSIONS = tuple(WEIGHTS.keys())


def _norm(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, str):
        return " ".join(value.casefold().split())
    if isinstance(value, list):
        return sorted(_norm(item) for item in value)
    return value


@dataclass(frozen=True)
class FidelityScore:
    total: float
    dimensions: dict[str, float]
    verdict: str
    feedback: str

    def to_dict(self) -> dict[str, Any]:
        return {"total": self.total, "dimensions": self.dimensions,
                "verdict": self.verdict, "feedback": self.feedback}


def _route(agent: dict[str, Any], gold: dict[str, Any]) -> tuple[str, str]:
    """Return (agent_route, gold_route) in a comparable canonical form."""
    agent_route = agent.get("synthesis_route") or SYNTHESIS_ROUTES.get(agent.get("profile"), "")
    gold_route = gold.get("synthesis_choice") or SYNTHESIS_ROUTES.get(gold.get("design_selection"), "")
    return _norm(agent_route) or _norm(SYNTHESIS_ROUTES.get(agent.get("profile"), "")), \
        _norm(gold_route) or _norm(SYNTHESIS_ROUTES.get(gold.get("design_selection"), ""))


def fidelity(
    agent_trace: dict[str, Any],
    gold_trace: dict[str, Any],
) -> FidelityScore:
    """Score how closely the agent's method trajectory matches the expert reference."""
    agent_profile = agent_trace.get("profile") or ""
    agent_id = agent_trace.get("identification_assumption") or ""
    gold_profile = gold_trace.get("design_selection") or ""
    gold_id = gold_trace.get("estimand_identification") or ""

    agent_route, gold_route = _route(agent_trace, gold_trace)

    # guard consistency: agent says poolable iff the gold review actually pooled.
    agent_poolable = bool(agent_trace.get("risk_guard", {}).get("passes"))
    gold_poolable = bool(gold_trace.get("poolable", True))

    dimensions = {
        "design_selection": 1.0 if agent_profile == gold_profile else 0.0,
        "estimand_identification": 1.0 if agent_id == gold_id else 0.0,
        "synthesis_route": 1.0 if (agent_route and agent_route == gold_route) else 0.0,
        "stop_decision": 1.0 if bool(agent_trace.get("living")) == bool(gold_trace.get("living_review", False)) else 0.0,
        "guard_consistency": 1.0 if agent_poolable == gold_poolable else 0.0,
    }
    total = round(sum(WEIGHTS[k] * dimensions[k] for k in DIMENSIONS), 4)
    if total >= 0.85:
        verdict = "high_fidelity"
    elif total >= 0.55:
        verdict = "partial_fidelity"
    else:
        verdict = "low_fidelity"
    feedback = (f"fidelity={total:.3f} ({verdict}); "
                f"design={agent_profile or '(none)'} ref={gold_profile or '(none)'}"
                + ("" if dimensions["design_selection"] else " (design mismatch)")
                + ("" if dimensions["guard_consistency"] else " (guard mismatch)"))
    return FidelityScore(total=total, dimensions=dimensions, verdict=verdict, feedback=feedback)


def aggregate_fidelity(
    agent_traces: list[dict[str, Any]],
    gold_traces: list[dict[str, Any]],
) -> dict[str, Any]:
    """Aggregate fidelity over a set of cases and report the training/reward signal."""
    if len(agent_traces) != len(gold_traces):
        raise ValueError("agent and gold traces must have matching counts")
    totals, dims_all = [], {k: [] for k in DIMENSIONS}
    for a, g in zip(agent_traces, gold_traces):
        score = fidelity(a, g)
        totals.append(score.total)
        for k in DIMENSIONS:
            dims_all[k].append(score.dimensions[k])
    mean_total = round(sum(totals) / len(totals), 4) if totals else 0.0
    mean_dims = {k: round(sum(v) / len(v), 4) if v else 0.0 for k, v in dims_all.items()}
    return {
        "n": len(totals),
        "mean_fidelity": mean_total,
        "mean_dimensions": mean_dims,
        "verdict": "high_fidelity" if mean_total >= 0.85 else ("partial_fidelity" if mean_total >= 0.55 else "low_fidelity"),
    }
