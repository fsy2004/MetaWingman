#!/usr/bin/env python3
"""E-R-V decision kernel — the agent's one-decision-per-stage thinking structure.

It wraps the base design-selection skill (which already yields profile, estimand,
synthesis route, confidence, living) and adds the two layers we need for a real
*decision* object:
  * E: an explicit Causal identity assumption (identification_assumption) — what
    must be assumed for the estimand to be identifiable;
  * R: a calibrated, distribution-free pooling guard (alpha risk control);
  * V: the single most valuable next evidence + a stop rule (EVPI-driven living).

Deterministic and offline — no model call, no server.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from metawingman.scripts.metawingman_core.design_selection import (
    ESTIMAND_TEMPLATES, SYNTHESIS_ROUTES, derive_review_design)
from metawingman.agent.poolability_guard import PoolabilityGuard, GuardModel, calibrate_guard
from metawingman.agent.evpi_director import evaluate_living

# E layer: which causal / identification assumption is required for each profile
# (a canonical enum id consumed by the schema; the human note follows in ENTITY_NOTES).
IDENTIFICATION_ASSUMPTIONS: dict[str, str] = {
    "intervention_pairwise": "rct_contrast",
    "intervention_network": "nma_consistency",
    "diagnostic_accuracy": "reference_standard",
    "prognostic_prediction": "external_validity",
    "prevalence_incidence": "population_representativeness",
    "public_health_exposure": "observational_adjustment",
    "living_review": "update_rule",
    "structured_no_pooling": "heterogeneity_non_poolable",
}

# gap ids the V layer can reason over (conceptual; real gaps come from acquisition).
DEFAULT_GAPS: dict[str, dict[str, float]] = {
    "comparison_graph_coverage": {"expected_utility_gain": 0.7, "uncertainty": 0.6},
    "reference_standard_verification": {"expected_utility_gain": 0.85, "uncertainty": 0.5},
    "heterogeneity_quantification": {"expected_utility_gain": 0.6, "uncertainty": 0.7},
    "update_freshness": {"expected_utility_gain": 0.5, "uncertainty": 0.8},
    "node_coverage_assessment": {"expected_utility_gain": 0.4, "uncertainty": 0.5},
}


@dataclass(frozen=True)
class DesignDecision:
    """The E-R-V decision object produced at a stage."""

    profile: str
    estimand: str
    synthesis_route: str
    identification_assumption: str
    confidence: float
    risk_guard: dict[str, Any]
    next_evidence: dict[str, Any] | None
    stop_rule: dict[str, Any]
    living: bool
    decision_tension: str
    minimal_decisive_question: str
    disconfirmation_design: str
    abstain: bool = False
    abstain_reason: str | None = None
    action: str = ""                                # typed action (operable)
    reflection: dict[str, Any] | None = None        # self-evaluation (operable)
    prm_score: float | None = None                  # process reward (operable)

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile": self.profile, "estimand": self.estimand,
            "synthesis_route": self.synthesis_route,
            "identification_assumption": self.identification_assumption,
            "confidence": self.confidence, "risk_guard": self.risk_guard,
            "next_evidence": self.next_evidence, "stop_rule": self.stop_rule,
            "living": self.living, "decision_tension": self.decision_tension,
            "minimal_decisive_question": self.minimal_decisive_question,
            "disconfirmation_design": self.disconfirmation_design,
            "abstain": self.abstain, "abstain_reason": self.abstain_reason,
            "action": self.action, "reflection": self.reflection,
            "prm_score": self.prm_score,
        }


def _guard_model(
    calibration: list[dict[str, Any]] | None,
    alpha: float,
    *,
    pass_threshold: float = 0.45,
) -> GuardModel:
    """Return a calibrated guard model, or an uncalibrated base-check-only model."""
    if calibration:
        return calibrate_guard(calibration, alpha=alpha)
    return GuardModel(alpha=alpha, threshold=pass_threshold, empirical_risk=0.0,
                      calibration_size=0)


def _gaps(landscape: dict[str, Any]) -> list[dict[str, Any]]:
    """Derive candidate evidence gaps relevant to the evidence structure."""
    gaps: list[dict[str, Any]] = []
    for gap_id, attrs in DEFAULT_GAPS.items():
        gap: dict[str, Any] = {"gap": gap_id, **attrs}
        if gap_id == "comparison_graph_coverage" and not landscape.get("comparator_count"):
            gap["uncertainty"] = 0.9
        if gap_id == "node_coverage_assessment" and landscape.get("n_nodes_assessed") is True:
            gap["expected_utility_gain"] = 0.2
        gaps.append(gap)
    return gaps


def derive_design_decision(
    question: dict[str, Any],
    landscape: dict[str, Any],
    *,
    prior_acceptance: dict[str, float] | None = None,
    alpha: float = 0.05,
    info_cost: float = 1.0,
    calibration: list[dict[str, Any]] | None = None,
) -> DesignDecision:
    """Build an E-R-V decision from a typed question + evidence structure."""
    base = derive_review_design(question, landscape)

    # R layer: risk-controlled pooling guard (reuse the base profile's confidence).
    model = _guard_model(calibration, alpha)
    signal_for_guard = dict(landscape)
    signal_for_guard["estimand_aligned"] = base.profile not in ("", "structured_no_pooling")
    signal_for_guard["profile_hint"] = base.profile
    guard = model.apply(signal_for_guard)

    # If the guard fails (would be misleading), force structured_no_pooling.
    if not guard.passes:
        profile = "structured_no_pooling"
        estimand = ESTIMAND_TEMPLATES["structured_no_pooling"]
        route = SYNTHESIS_ROUTES["structured_no_pooling"]
    else:
        profile = base.profile
        estimand = base.estimand
        route = base.synthesis_route

    identification_assumption = IDENTIFICATION_ASSUMPTIONS.get(profile, "")

    # V layer: most valuable next query + stop rule (drives living).
    v = evaluate_living(_gaps(landscape), info_cost=info_cost, slack=0.0)

    living = bool(v["living"] or base.living)
    decision_tension = (
        f"The design type ({profile}) determines whether a single pooled answer is "
        f"scientifically defensible; guard{' fails' if not guard.passes else ' passes'} "
        f"at alpha={alpha} (risk_violation~{guard.risk_violation_estimate:.3f})."
    )
    return DesignDecision(
        profile=profile,
        estimand=estimand,
        synthesis_route=route,
        identification_assumption=identification_assumption,
        confidence=round(base.confidence, 2),
        risk_guard=guard.to_dict(),
        next_evidence=v["next_evidence"],
        stop_rule=v["stop_rule"],
        living=living,
        decision_tension=decision_tension,
        minimal_decisive_question=(
            f"Is this {profile} question answerable with the available node structure, "
            f"or would pooling be misleading at alpha={alpha}?"
        ),
        disconfirmation_design=(
            "Look for an incompatible design, an unsupported estimand, or a heterogeneous "
            "population that would change the required profile."
        ),
        abstain=base.abstain,
        abstain_reason=base.abstain_reason,
        action="design_decision" if not base.abstain else "abstain",
        reflection={
            "guard_passes": guard.passes,
            "verified": "yes" if guard.passes else ("abstain" if base.abstain else "override_to_narrative"),
            "note": decision_tension,
        },
        prm_score=round(base.confidence * (1.0 if guard.passes else 0.6), 3),
    )
