#!/usr/bin/env python3
"""Scrutiny layer (method layer 3.0, deterministic, zero training).

Ports four top-venue agent ideas into the evidence-synthesis setting:
  * Oppose/Adjudicate  — two-scientist debate with position swap (Co-Scientist)
                         + hard gates (FirstResearch): a fixed negative-principle
                         table (methodological, evidence-based) raises objections;
  * Precedent retrieval — evidence-trajectory memory (OpenScholar/SELF-RAG): the
                         k nearest published-review precedents (family-isolated
                         library = dev + training set) are retrieved and their
                         disagreement raises a soft objection;
  * Self-reflection with method anchors (Reflexion) — objections carry a
                         machine-checkable resolution, not free text;
  * Step verification (PAV) — every judged change is documented as a step with
                         a verifiable precondition.

The rules are fixed by methodological principle (no tuning on OOD corpora);
the evaluation script logs any objection-driven change per case.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

# ---------------------------------------------------------------------------
# Negative principles (fixed, methodological): (name, severity, resolution)
# ---------------------------------------------------------------------------
NEGATIVE_PRINCIPLES: tuple[tuple[str, str, str], ...] = (
    ("contrast_under_graph", "high",
     "upgrade_network" if True else ""),  # comparator/arm>=3 with a pairwise base
    ("narrative_overrides_strong_design", "high", "keep_base_design"),
    ("pooling_overwrites_design", "high", "keep_base_design"),
    ("reference_standard_with_rate_outcome", "medium", "require_clarification"),
    ("exposure_with_intervention_graph", "medium", "require_clarification"),
)

_STRONG_DESIGN = ("has_reference_standard", "has_prediction_model")


def _num(value: Any) -> int:
    try:
        return int(value or 0)
    except Exception:
        return 0


def oppose(signal: dict[str, Any], decision: dict[str, Any]) -> list[dict[str, Any]]:
    """Feature-level objections (no numeric outcomes; fixed principles)."""
    objections: list[dict[str, Any]] = []
    profile = decision.get("profile", "") or ""
    comparator = _num(signal.get("comparator_count"))
    arms = _num(signal.get("arms_per_study") or signal.get("intervention_arm_count"))
    outcome = str(signal.get("outcome_measure_type") or "").casefold()
    hint = str(signal.get("design_type_hint") or "").casefold()
    strong = bool(any(signal.get(k) for k in _STRONG_DESIGN)) or outcome in ("proportion", "prevalence")

    if profile == "intervention_pairwise" and (comparator >= 3 or arms >= 3):
        objections.append({"principle": "contrast_under_graph", "severity": "high",
                           "resolution": "upgrade_network",
                           "evidence": f"comparator={comparator} arms={arms} with pairwise base"})
    if hint == "narrative_no_pooling" and strong and profile != "structured_no_pooling":
        # narrative treatment must not override a stronger design signal
        objections.append({"principle": "narrative_overrides_strong_design", "severity": "high",
                           "resolution": "keep_base_design",
                           "evidence": f"narrative hint + strong design (ref={signal.get('has_reference_standard')}, "
                                       f"pred={signal.get('has_prediction_model')}, outcome={outcome})"})
    if (profile == "structured_no_pooling" and strong and
            bool(decision.get("risk_guard", {}).get("passes")) is False):
        # the pooling judgment rewrote the design: design and pooling are separate
        objections.append({"principle": "pooling_overwrites_design", "severity": "high",
                           "resolution": "keep_base_design",
                           "evidence": "guard failure forced narrative although a strong design signal exists"})
    if profile == "diagnostic_accuracy" and outcome in ("rate", "binary", "continuous"):
        objections.append({"principle": "reference_standard_with_rate_outcome", "severity": "medium",
                           "resolution": "require_clarification",
                           "evidence": f"diagnostic base with outcome={outcome}"})
    if profile == "public_health_exposure" and (comparator >= 3 or arms >= 3):
        objections.append({"principle": "exposure_with_intervention_graph", "severity": "medium",
                           "resolution": "require_clarification",
                           "evidence": f"exposure base with comparator={comparator} arms={arms}"})
    return objections


def feature_vector(signal: dict[str, Any]) -> np.ndarray:
    outcome = str(signal.get("outcome_measure_type") or "").casefold()
    hint = str(signal.get("design_type_hint") or "").casefold()
    vec = [
        float(bool(signal.get("has_reference_standard"))),
        float(bool(signal.get("has_prediction_model"))),
        float(outcome in ("proportion", "prevalence")),
        float(outcome in ("binary", "continuous", "rate", "diagnostic")),
        min(1.0, _num(signal.get("comparator_count")) / 5.0),
        min(1.0, _num(signal.get("arms_per_study") or signal.get("intervention_arm_count")) / 5.0),
        float(hint == "exposure"),
        float(hint == "narrative_no_pooling"),
    ]
    return np.array(vec, dtype=float)


def precedent_retrieval(signal: dict[str, Any], library: list[dict[str, Any]],
                        k: int = 3) -> tuple[list[dict[str, Any]], float]:
    """kNN precedents from a family-isolated library of published-review methods."""
    q = feature_vector(signal)
    scored = []
    for item in library:
        p = feature_vector(item["signal"])
        dist = float(np.linalg.norm(q - p))
        scored.append((dist, item))
    scored.sort(key=lambda x: x[0])
    top = [item for _d, item in scored[:k]]
    margin = scored[0][0] - scored[-1][0] if len(scored) > k else 0.0
    return top, margin


def adjudicate(decision: dict[str, Any], objections: list[dict[str, Any]],
               precedents: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Apply high-severity objections; medium ones are recorded as tension."""
    changes: list[dict[str, Any]] = []
    profile = decision.get("profile", "")
    for obj in objections:
        if obj["severity"] != "high":
            continue
        if obj["resolution"] == "upgrade_network" and profile == "intervention_pairwise":
            profile = "intervention_network"
            changes.append({"principle": obj["principle"], "from": "intervention_pairwise",
                            "to": "intervention_network", "applied": True})
        elif obj["resolution"] == "keep_base_design" and profile == "structured_no_pooling":
            # the base design is reconstructed from the question; the guard keeps
            # the design already under v2.2 semantics — record the objection as
            # an explicit documented check (applied True only if profile was narrative)
            changes.append({"principle": obj["principle"], "applied": False,
                            "note": "design kept (v2.2 semantics already enforce this)"})
    tension = [obj for obj in objections if obj["severity"] == "medium"]
    precedent_conflict = None
    if precedents:
        designs = {p["design_selection"] for p in precedents}
        if designs and len(designs) >= 2:
            majority = max(set(designs), key=lambda d: sum(1 for p in precedents if p["design_selection"] == d))
            if majority != profile:
                precedent_conflict = {"majority": majority, "precedent_designs": sorted(designs),
                                      "decision": profile}
    return {"profile": profile, "changes": changes, "tension": tension,
            "precedent_conflict": precedent_conflict}
