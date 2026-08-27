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
from metawingman.agent.poolability_guard import (
    DimensionGuardModel, GuardModel, PoolabilityGuard, calibrate_dimension_guard,
    base_poolability_check, safety_score, calibrate_guard)
from metawingman.agent.evpi_director import (
    evaluate_living, decide_living_v2, landscape_gaps, calibrate_living)

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


def derive_design_decision_v2(
    question: dict[str, Any],
    landscape: dict[str, Any],
    *,
    guard_signal: dict[str, Any] | None = None,
    guard_model: DimensionGuardModel | None = None,
    info_cost: float | None = None,
    gains: dict[str, float] | None = None,
    alpha: float = 0.10,
    delta: float = 0.10,
    use_input_living_flag: bool = False,
) -> DesignDecision:
    """V2 E-R-V decision: per-dimension (seven estimand-alignment) risk-controlled
    guard with a finite-sample guarantee, and EVPI-only living/stop.

    The guard input is the *evidence structure* only — procedural alignment
    dimensions (population / contrast / outcome / time / effect-measure /
    analysis-unit / conditioning-set) plus graph coverage and the question-level
    estimand-alignment gate. It never reads the review's own pooling decision or
    its heterogeneity treatment. `guard_model` is calibrated externally on a
    frozen calibration set (see calibrate_dimension_guard); when None, a
    maximally conservative model is used (accept only zero alignment risk).

    The stop decision comes from value-of-information only (landscape-derived
    gaps and the calibrated information cost); the extracted living/update flag
    is deliberately not used as an input (`use_input_living_flag=False`).
    """
    base = derive_review_design(question, landscape)
    signal = dict(guard_signal or landscape)
    signal.setdefault("profile_hint", base.profile)
    signal["estimand_aligned"] = base.profile not in ("", "structured_no_pooling")
    if guard_model is None:
        guard_model = DimensionGuardModel(alpha=alpha, delta=delta, threshold=0.0,
                                          empirical_risk=1.0, risk_bound=1.0,
                                          accepted_calibration_n=0, calibration_size=0)
    guard = guard_model.apply(signal)

    if not guard.passes:
        # v2.1 semantics: design and pooling are SEPARATE judgments. A failed
        # alignment check means "do not pool" (risk control), not "the design is
        # different". The profile changes to structured_narrative only when the
        # evidence structure itself is narrative-defined (design_type_hint
        # narrative_no_pooling AND no stronger design signal) or no base design
        # is identifiable. The priority mirrors the reference taxonomy:
        # reference-standard / prediction-model / proportion-prevalence outcomes
        # define the design even when the evidence body is narratively handled.
        hint_narrative = bool(signal.get("design_type_hint") == "narrative_no_pooling")
        outcome = str(signal.get("outcome_measure_type") or "").casefold()
        strong_design = bool(signal.get("has_reference_standard") or
                             signal.get("has_prediction_model") or
                             outcome in ("proportion", "prevalence"))
        narrative_defined = (hint_narrative and not strong_design) or not base.profile
        if narrative_defined:
            profile = "structured_no_pooling"
            estimand = ESTIMAND_TEMPLATES["structured_no_pooling"]
            route = SYNTHESIS_ROUTES["structured_no_pooling"]
        else:
            profile = base.profile
            estimand = base.estimand
            route = base.synthesis_route
    else:
        profile = base.profile
        estimand = base.estimand
        route = base.synthesis_route

    # V layer: EVPI-only stop (no calendar prior, no gold living flag).
    gaps = landscape_gaps(landscape, profile,
                          heterogeneity_handling=None, gains=gains)
    if info_cost is None:
        info_cost = 0.5  # fall back only if uncalibrated
    v = decide_living_v2(gaps, info_cost=info_cost)
    living = bool(v["living"])

    identification_assumption = IDENTIFICATION_ASSUMPTIONS.get(profile, "")
    decision_tension = (
        f"The design type ({profile}) determines whether a single pooled answer is "
        f"scientifically defensible; v2 guard{' fails' if not guard.passes else ' passes'} "
        f"at alpha={alpha}, delta={delta} (guaranteed mis-pool risk <= "
        f"{guard.risk_violation_estimate:.3f})."
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
            "guard_version": "v2.1",
            "verified": "yes" if guard.passes else ("abstain" if base.abstain else
                        ("override_to_narrative" if narrative_defined else "narrative_synthesis_with_design_kept")),
            "note": decision_tension,
        },
        prm_score=round(base.confidence * (1.0 if guard.passes else 0.6), 3),
    )
