#!/usr/bin/env python3
"""Open-world deliberation — the agent keeps a pool of candidate *designs* and
reasons over them, rather than jumping straight to one answer.

For each candidate design the agent records supporting/contradicting evidence
signals and a confidence; it only converges when a candidate's confidence
decisively dominates the pool. Otherwise it stays open and asks for the single
most informative piece of next evidence (funnelling into the V layer).
Deterministic and offline.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Candidate:
    profile: str
    evidence_for: tuple[str, ...]
    evidence_against: tuple[str, ...]


@dataclass(frozen=True)
class Deliberation:
    pool: tuple[str, ...]
    log: tuple[str, ...]
    converged: bool
    winning_profile: str | None
    next_query: str


def _profile_signal(profile: str, landscape: dict[str, Any]) -> tuple[list[str], list[str]]:
    """For each design, derive supporting/contradicting structural signals."""
    evidence_for: list[str] = []
    evidence_against: list[str] = []
    comparator = landscape.get("comparator_count") or 0
    if profile == "intervention_network":
        if comparator >= 3:
            evidence_for.append(f"{comparator} comparator nodes warrant network comparison")
        else:
            evidence_against.append("few comparators reduce the value of a network comparison")
    if profile == "intervention_pairwise":
        if comparator in (1, 2):
            evidence_for.append("single/few arm contrast")
        else:
            evidence_against.append("many comparators suggest a network is more faithful")
    if profile == "diagnostic_accuracy":
        if landscape.get("has_reference_standard"):
            evidence_for.append("a reference standard is present")
        else:
            evidence_against.append("no verified reference standard")
    if profile == "public_health_exposure":
        if str(landscape.get("exposure_outcome_design")) in ("observational", "both"):
            evidence_for.append("observational exposure-outcome design")
        else:
            evidence_against.append("not an observational exposure design")
    if profile == "prognostic_prediction":
        if landscape.get("has_prediction_model"):
            evidence_for.append("a prediction/risk model is present")
        else:
            evidence_against.append("no prediction model signal")
    if profile == "prevalence_incidence":
        if landscape.get("outcome_unit") in ("rate", "proportion"):
            evidence_for.append("proportion/rate outcome unit present")
        else:
            evidence_against.append("outcome unit is not a proportion/rate")
    return evidence_for, evidence_against


def deliberate(
    question: dict[str, Any],
    landscape: dict[str, Any],
    candidates: list[Candidate],
    *,
    max_pool: int = 4,
    dominance: float = 0.25,
) -> Deliberation:
    """Reason over the candidate pool and decide whether it has converged."""
    scored: list[tuple[str, list[str], list[str], float]] = []
    for cand in candidates:
        evid_f, evid_a = cand.evidence_for, cand.evidence_against
        # a candidate's current "belief" = for-signals weighted against against-signals.
        # We combine with the structural evidence actually present.
        f = cand.evidence_for
        # derive signals from the landscape so the pool is evidence-grounded.
        f, a = _profile_signal(cand.profile, landscape)
        if cand.evidence_for:
            f = list(f) + list(cand.evidence_for)
        if cand.evidence_against:
            a = list(a) + list(cand.evidence_against)
        belief = 1.0 + len(f) - 1.4 * len(a)
        scored.append((cand.profile, f, a, round(belief, 4)))

    scored.sort(key=lambda t: t[3], reverse=True)
    top = scored[0]
    converged = len(scored) > 0 and (len(scored) == 1 or top[3] - scored[1][3] >= dominance)
    winning = top[0] if converged else None

    log = tuple(
        f"{profile}: belief={b:.3f} (for={list(f)}) (against={list(a)})"
        for profile, f, a, b in scored
    )
    if len(scored) > max_pool:
        log = log[:max_pool]

    if converged:
        next_query = f"evidence supports {winning}; proceed to synthesis decision."
    else:
        # still open: ask for the single most informative next evidence.
        gap_candidates = {"comparison_graph_coverage", "reference_standard_verification",
                          "heterogeneity_quantification", "node_coverage_assessment"}
        next_query = "still ambiguous between " + ", ".join(p for p, _, _, _ in scored[:2]) + \
                     "; acquire " + sorted(gap_candidates)[0] + " next."
    return Deliberation(tuple(p for p, _, _, _ in scored), log, converged, winning, next_query)
