#!/usr/bin/env python3
"""Normalize an independently-extracted method trajectory (free text from a real
published review) to the canonical E-R-V fields, so it can be compared to the
agent's structured decision.

The profile is classified from the actual method text the review used (not from
our mapping table), which is what makes the gold *independent* — the key to
avoiding the same-source self-check. Identification/synthesis are then derived
from that independent profile. Deterministic and offline.
"""

from __future__ import annotations

from typing import Any

from metawingman.agent.decision_core import IDENTIFICATION_ASSUMPTIONS
from metawingman.scripts.metawingman_core.design_selection import SYNTHESIS_ROUTES

# Ordered, most-specific first. Match on the review's own method text.
_PROFILE_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("diagnostic_accuracy", ("sensitivity", "specificity", "diagnostic", "sroc",
                             "reference standard", "index test", "accuracy of")),
    ("prognostic_prediction", ("prediction model", "risk model", "prognostic", "discrimination",
                               "calibration", "prediction"),),
    ("prevalence_incidence", ("prevalence", "incidence", "pooled proportion", "pooled prevalence")),
    ("public_health_exposure", ("association", "exposure", "observational", "cross-sectional",
                                "cohort", "risk factor", "correlation")),
    ("intervention_network", ("network meta", "multiple", "competing", "head to head",
                              "indirect comparison", "several interventions")),
    ("intervention_pairwise", ("pairwise", "two-arm", "two arm", "placebo-controlled",
                               "head-to-head", "single intervention")),
]

_LIVING_TERMS = ("living", "update", "ongoing", "continuing", "living review", "rapid")


def classify_profile(text: str, *, pooled_first: bool = True) -> str | None:
    """Classify the review design from its method text (independent of our maps)."""
    t = text.casefold()
    for profile, terms in _PROFILE_RULES:
        if any(term in t for term in terms):
            return profile
    return None


def classify_from_signal(signal: dict[str, Any]) -> str | None:
    """Classify the review design from *procedural structure signals* (reliable).

    Uses the same priority as the agent's design selection but grounded in the
    real procedural signals extracted from the paper: a reference standard implies
    diagnostic; a prediction model implies prognostic; a proportion/rate outcome
    implies prevalence; an observational exposure/association implies
    public-health exposure; >=3 comparator/arm nodes implies network; 1-2 nodes
    implies pairwise; a narrative / no-pooling implies structured_no_pooling.
    This is independent of the agent's input (the signals come from the paper).
    """
    if signal.get("has_reference_standard"):
        return "diagnostic_accuracy"
    if signal.get("has_prediction_model"):
        return "prognostic_prediction"
    outcome = str(signal.get("outcome_measure_type") or "").casefold()
    if outcome in ("proportion", "prevalence"):
        return "prevalence_incidence"
    if not signal.get("pooled"):
        dtype = str(signal.get("design_type_hint") or "").casefold()
        if dtype in ("narrative_no_pooling",) or str(signal.get("heterogeneity_handling") or "").casefold().startswith("narrative"):
            return "structured_no_pooling"
    comparator = int(signal.get("comparator_count") or 0)
    arms = int(signal.get("intervention_arm_count") or 0)
    hint = str(signal.get("design_type_hint") or "").casefold()
    if hint == "exposure" or (outcome == "rate" and not comparator and not arms):
        return "public_health_exposure"
    if comparator >= 3 or arms >= 3 or hint == "network":
        return "intervention_network"
    if comparator in (1, 2) or arms in (1, 2) or hint in ("pairwise", "prevalence"):
        if hint == "prevalence":
            return "prevalence_incidence"
        return "intervention_pairwise"
    return None


def infer_living(stop_or_update: str | None) -> bool:
    if not stop_or_update:
        return False
    return any(term in stop_or_update.casefold() for term in _LIVING_TERMS)


def normalize_gold_trace(extracted: dict[str, Any]) -> dict[str, Any] | None:
    """Turn an extracted row into a structured gold method trajectory, or None.

    Prefers the reliable structure-signal classification; falls back to the
    free-text classifier only when the signals are ambiguous.
    """
    mt = extracted.get("method_trace") or {}
    profile = classify_from_signal(mt)
    if profile is None:
        profile = classify_profile(str(mt.get("design_type_hint") or ""))
    if profile is None:
        return None
    return {
        "case_id": str(extracted.get("record_id") or ""),
        "design_selection": profile,
        "estimand_identification": IDENTIFICATION_ASSUMPTIONS.get(profile, ""),
        "synthesis_choice": SYNTHESIS_ROUTES.get(profile, ""),
        "poolable": bool(mt.get("pooled")),
        "living_review": bool(mt.get("living_or_update")),
        "source_text": str(mt.get("design_type_hint") or "")[:160],
        "source": "independent_real_published_review_structure_extraction",
        "signal": {k: mt.get(k) for k in (
            "intervention_arm_count", "comparator_count", "has_reference_standard",
            "has_prediction_model", "outcome_measure_type", "pooled", "living_or_update",
            "design_type_hint", "heterogeneity_handling", "effect_measure_type",
            "analysis_unit", "conditioning_set", "population_description", "time_horizon")},
    }


def normalize_batch(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    out, skipped = [], 0
    for row in rows:
        if row.get("status") != "extracted":
            skipped += 1
            continue
        g = normalize_gold_trace(row)
        if g is None:
            skipped += 1
            continue
        out.append(g)
    return out, skipped
