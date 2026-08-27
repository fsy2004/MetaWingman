#!/usr/bin/env python3
"""MetaWingman design-selection skill method.

Given a typed clinical/methodological question and a cutoff-bounded evidence
landscape, derive an *autonomous design decision*: which review profile
(stratum) is appropriate, what the estimand should be, and which synthesis
route is faithful. This is the one-story decision the agent makes before
workflow execution, and it is a first-class, user-verifiable object.

Design principle (top-journal agentic paradigm): the agent reasons about the
*design* (review type + estimand + synthesis route) from clinical reality and
the evidence structure, not from a fixed/default profile. It abstains (does not
guess) when the question structure or evidence is ambiguous.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class DesignSelectionError(ValueError):
    """Raised when a design decision cannot be formed safely."""


# The 8 methodological profile strata (canonical for MetaWingman).
PROFILE_STRATA: tuple[str, ...] = (
    "intervention_pairwise",        # two (or few) arm comparisons
    "intervention_network",         # multiple competing interventions, NMA
    "diagnostic_accuracy",          # index test vs reference standard
    "prognostic_prediction",        # prediction / risk model
    "prevalence_incidence",         # proportion / rate in a population
    "public_health_exposure",       # exposure-outcome, often non-randomised
    "living_review",                # update / living
    "structured_no_pooling",        # heterogeneous, justified narrative/SWiM
)

# Estimand templates per profile (the quantity the review estimates).
ESTIMAND_TEMPLATES: dict[str, str] = {
    "intervention_pairwise": "relative effect of one intervention vs comparator (OR/RR/MD/SMD, or HR if time-to-event)",
    "intervention_network": "relative effect of each intervention vs a common reference, with consistency assumption",
    "diagnostic_accuracy": "sensitivity and specificity (or ROC) of the index test against the reference standard",
    "prognostic_prediction": "risk-model discrimination and calibration, validated in an independent or temporally separated sample",
    "prevalence_incidence": "pooled proportion or incidence rate with a pre-specified denominator unit",
    "public_health_exposure": "association between exposure and outcome, heterogeneity-aware, with possible dose-response",
    "living_review": "the same estimand as the base review, re-estimated on each update window",
    "structured_no_pooling": "a structured synthesis (SWiM) rather than a single pooled estimate",
}

# Synthesis route per profile (the faithful way to combine).
SYNTHESIS_ROUTES: dict[str, str] = {
    "intervention_pairwise": "random-effects pairwise meta-analysis (REML; Hartung-Knapp where suitable)",
    "intervention_network": "network meta-analysis with a single baseline consistency model",
    "diagnostic_accuracy": "bivariate/hierarchical summary ROC with sensitivity at a pre-specified specificity",
    "prognostic_prediction": "narrative of model performance with quantitative calibration pooling where meta-able",
    "prevalence_incidence": "transformed-proportion meta-analysis with heterogeneity and prediction interval",
    "public_health_exposure": "multi-level random-effects meta-analysis with geo/dose subgrouping; avoid naive pooling of incommensurate metrics",
    "living_review": "a pre-registered update rule re-running the same synthesis on each window",
    "structured_no_pooling": "SWiM / structured narrative; no single pooled estimate",
}


@dataclass(frozen=True)
class DesignDecision:
    """The one-story design decision produced by the skill."""

    profile: str
    estimand: str
    synthesis_route: str
    justification: str
    confidence: float            # 0..1 calibrated confidence in this decision
    decision_tension: str
    minimal_decisive_question: str
    disconfirmation_design: str
    missingness_anchor: str | None
    living: bool = False         # orthogonal axis: is this a living/update review?
    abstain: bool = False
    abstain_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile": self.profile, "estimand": self.estimand,
            "synthesis_route": self.synthesis_route, "justification": self.justification,
            "confidence": self.confidence, "decision_tension": self.decision_tension,
            "minimal_decisive_question": self.minimal_decisive_question,
            "disconfirmation_design": self.disconfirmation_design,
            "missingness_anchor": self.missingness_anchor, "living": self.living,
            "abstain": self.abstain, "abstain_reason": self.abstain_reason,
        }


def _abstain(reason: str) -> DesignDecision:
    return DesignDecision(
        profile="", estimand="", synthesis_route="", justification=reason,
        confidence=0.0, decision_tension="", minimal_decisive_question="",
        disconfirmation_design="", missingness_anchor=None, abstain=True,
        abstain_reason=reason,
    )


def _structure_evidence(landscape: dict[str, Any]) -> dict[str, Any]:
    """Summarise the evidence-structure signals from a landscape summary."""
    return {
        "arms_per_study": landscape.get("arms_per_study"),           # typical comparison graph degree
        "has_reference_standard": landscape.get("has_reference_standard", False),
        "has_prediction_model": landscape.get("has_prediction_model", False),
        "outcome_unit": landscape.get("outcome_unit"),               # 'rate'|'proportion'|'continuous'|'binary'
        "exposure_outcome_design": landscape.get("exposure_outcome_design"),   # 'rct'|'observational'|'both'
        "is_update": landscape.get("is_update", False),
        "comparator_count": landscape.get("comparator_count"),        # number of distinct intervention nodes
        "n_nodes_assessed": landscape.get("n_nodes_assessed", False),
        "has_geographic_dose_heterogeneity": landscape.get("has_geographic_dose_heterogeneity", False),
    }


def derive_review_design(question: dict[str, Any], landscape: dict[str, Any]) -> DesignDecision:
    """Derive a design decision from a typed question + evidence structure.

    The question carries the clinical shape; the landscape carries what the
    evidence can actually support (comparator count, reference standard, etc).
    Deterministic, rule-gated, with abstention when signals conflict.
    """
    q = question
    # --- question shape ---
    q_type = (q.get("type") or "").strip().lower()
    has_period = "diagnos" in q_type or bool(q.get("has_index_test_reference"))
    has_model = "prediction" in q_type or bool(q.get("has_prediction_model"))
    is_prevalence = "prevalence" in q_type or "incidence" in q_type or "proportion" in q_type
    is_exposure = "exposure" in q_type or bool(q.get("is_public_health_exposure"))
    intervention_count = q.get("intervention_count", 0)
    is_update = bool(q.get("is_living_or_update")) or bool(landscape.get("is_update"))

    s = _structure_evidence(landscape)

    # collect candidate signals in priority order with evidence-backed rationale
    candidates: list[tuple[str, str, float]] = []  # (profile, reason, confidence)

    if has_period and s["has_reference_standard"]:
        candidates.append(("diagnostic_accuracy",
                           "index test against a verified reference standard", 0.90))
    if has_model and s["has_prediction_model"]:
        candidates.append(("prognostic_prediction",
                           "prediction/risk model with discrimination and calibration", 0.88))
    if is_prevalence and s["outcome_unit"] in ("rate", "proportion"):
        candidates.append(("prevalence_incidence",
                           "proportion/rate with a defined denominator unit", 0.90))
    if is_exposure and s["exposure_outcome_design"] in ("observational", "both"):
        candidates.append(("public_health_exposure",
                           "exposure-outcome association, heterogeneity-aware", 0.80))
    if intervention_count and (s["arms_per_study"] or s["comparator_count"]):
        if (s["comparator_count"] or 0) >= 3 or (s["arms_per_study"] or 0) >= 3:
            candidates.append(("intervention_network",
                               "multiple competing interventions warrant network comparison", 0.86))
        else:
            candidates.append(("intervention_pairwise",
                               "a single intervention-vs-comparator contrast", 0.84))
    # living/update is an ORTHOGONAL axis, not a base profile; compute separately.

    # decide
    if not candidates:
        # ambiguous question shape -> abstain rather than guess
        return _abstain("question shape is ambiguous about review type; ask for the clinical structure or abstain")
    # pick the highest-confidence candidate; if ties or conflict (e.g. diagnostic + exposure), prefer
    # the more specific one and note the conflict.
    candidates.sort(key=lambda item: item[2], reverse=True)
    profile, reason, conf = candidates[0]

    # conflict guard: preventable double-signal -> abstain unless one clearly dominates
    top = {c[0] for c in candidates if c[2] >= conf - 0.08}
    if len(top) > 1:
        # diagnostic vs prediction both possible -> not ambiguous; but if the #1 vs #2 are far apart, proceed.
        if abs(candidates[0][2] - candidates[1][2]) < 0.12 and not (
            profile in ("intervention_pairwise", "intervention_network")
        ):
            return _abstain(f"ambiguous: signals {sorted(top)} both plausible; abstain until evidence clarifies")

    estimand = ESTIMAND_TEMPLATES[profile]
    route = SYNTHESIS_ROUTES[profile]
    gap_anchor = None
    if s["n_nodes_assessed"] is False:
        gap_anchor = "evidence graph node coverage not assessed; check record nodes before poolability"
    return DesignDecision(
        profile=profile, estimand=estimand, synthesis_route=route,
        justification=f"{reason} (evidence structure: {_structure_summary(s)})",
        confidence=round(conf, 2),
        decision_tension=(
            f"The review type choice ({profile}) determines whether a single pooled "
            f"answer is scientifically defensible."
        ),
        minimal_decisive_question=(
            f"Is this {profile} question answerable with the available node structure, "
            f"or would pooling be misleading?"
        ),
        disconfirmation_design=(
            "Look for an incompatible design, an unsupported estimand, or a "
            "heterogeneous population that would change the required profile."
        ),
        missingness_anchor=gap_anchor,
        living=bool(is_update or s.get("is_update")),
    )


def _structure_summary(s: dict[str, Any]) -> str:
    parts = []
    if s["reference_standard"] if "reference_standard" in s else s.get("has_reference_standard"):
        parts.append("reference-standard present")
    if s.get("has_prediction_model"):
        parts.append("prediction model present")
    if s.get("comparator_count"):
        parts.append(f"{s['comparator_count']} comparator nodes")
    return ", ".join(parts) if parts else "no strong signals"


if __name__ == "__main__":
    import json
    import sys
    question = json.loads(sys.argv[1])
    landscape = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}
    print(json.dumps(derive_review_design(question, landscape).to_dict(), indent=2))
