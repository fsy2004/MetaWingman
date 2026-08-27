#!/usr/bin/env python3
"""Evidence-budget allocator: allocate computation (evidence depth) by residual risk.

依据(出处): _deliverables/deep-study/notes/test-time-compute.md (Eq.1: choose the
             configuration theta within budget N maximizing expected accuracy; the
             key mechanism: allocation follows residual difficulty/risk, not uniform),
             论文: arXiv:2408.03314 (Snell et al. 2024).
Official code for that paper is not public (verified by repository search); this
is a spec-faithful mapping onto evidence depth — no third-party code adopted.
"""

from __future__ import annotations

DEPTHS = ("standard", "reinforced", "full")
STEP_COST = {"standard": 1, "reinforced": 3, "full": 6}


def allocate(residual_risk: float, disagreement: float = 0.0) -> dict[str, Any]:
    """Map residual risk (+ disagreement) to an evidence-depth configuration.

    standard   : base decision object only;
    reinforced : + precedent retrieval + debate (3 evidence actions);
    full       : + external retriever expansion / cross-check (6 evidence actions).
    Budget = fixed N (evidence actions); the allocator only CHANGES the mix.
    """
    risk = max(0.0, min(1.0, float(residual_risk)))
    if disagreement > 0.2 or risk > 0.20:
        depth = "full"
    elif disagreement > 0.0 or risk > 0.10:
        depth = "reinforced"
    else:
        depth = "standard"
    cost = STEP_COST[depth]
    return {"depth": depth, "evidence_actions": cost,
            "residual_risk": round(risk, 4), "disagreement": round(float(disagreement), 4)}


def compare_budgeting(residual_risks: list[float], agreement_uniform: list[int],
                      agreement_risky: list[int]) -> dict[str, Any]:
    """Paired comparison of allocation policies under the same total budget.

    uniform : same evidence depth for every case (baseline);
    risky   : risk-weighted allocation (this allocator).
    Returns paired deltas (risky - uniform) as evidence.
    """
    import numpy as np
    u = np.array(agreement_uniform, dtype=float)
    r = np.array(agreement_risky, dtype=float)
    return {"n": len(u), "uniform_mean": round(float(u.mean()), 4),
            "risky_mean": round(float(r.mean()), 4),
            "delta_paired": round(float((r - u).mean()), 4)}
