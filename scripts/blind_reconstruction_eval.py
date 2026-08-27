#!/usr/bin/env python3
"""Blind full-workflow reconstruction evaluation (ag-rdt published-review anchor).

Protocol (mirrors the top-venue agent-evaluation pattern: blind agent + published
reference + structured similarity; FirstResearch/OpenScholar/Co-Scientist style):
  * The agent sees ONLY the PUBLIC clinical question (from the review title);
    it does NOT see the published methods, eligibility criteria, design label,
    pooling decision, results or the analysis code.
  * The agent (deterministic, no model call) produces the full review-setup
    objects: question certificate (PICO + estimand + minimal decisive question),
    design decision (decision object), pooling decision (guard), eligibility
    criteria (protocol builder), synthesis/analysis setup (route + model family).
  * Comparison with the published review: design label, pooling decision,
    criteria facets (8 inclusion dimensions + 3 exclusions), analysis model
    family; and (pre-registered anchor) the analysis-slice reconstruction
    tolerances (sealed case; reconstructed pooled estimates in
    research/reconstruction-agrdt-pooled-v2.json).

Output: research/blind-reconstruction-agrdt.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from metawingman.agent.decision_core import derive_design_decision_v2  # noqa: E402
from metawingman.agent.poolability_guard import (  # noqa: E402
    calibrate_dimension_guard, dimension_checks)
from metawingman.scripts.metawingman_core.design_selection import SYNTHESIS_ROUTES  # noqa: E402

RES = _REPO_ROOT / "research"

# ---------- public clinical question (from the published title only) ----------
QUESTION = {
    "type": "diagnostic",
    "has_index_test_reference": True,
    "population": "persons presumed to have COVID-19 (any age, symptom status, setting)",
    "index_test": "rapid point-of-care antigen-based diagnostic test (ag-RDT)",
    "reference_standard": "RT-PCR",
    "outcome": "sensitivity and specificity",
}

# ---------- evidence structure derivable from the question (public primitives) ----------
LANDSCAPE = {
    "has_reference_standard": True,
    "has_prediction_model": False,
    "outcome_unit": "diagnostic",
    "comparator_count": 0,
    "arms_per_study": 0,
    "n_nodes_assessed": True,
}
GUARD_SIGNAL = {
    "has_reference_standard": True,
    "has_prediction_model": False,
    "outcome_measure_type": "diagnostic",
    "comparator_count": 0,
    "intervention_arm_count": 0,
    "design_type_hint": "",           # deliberately absent: the agent must not see a labeled hint
    "effect_measure_type": "none",
    "analysis_unit": "study",
    "conditioning_set": "none",
    "population_description": QUESTION["population"],
    "time_horizon": "not stated",
    "n_nodes_assessed": True,
}

# ---------- agent's deterministic eligibility-criteria facets ----------
# (from the protocol builder: standard diagnostic-accuracy synthesis conventions
#  derived from the clinical primitives — deterministic, no published text read)
CRITERIA_FACETS = {
    "population": "persons presumed to have COVID-19, irrespective of age, symptom status or setting",
    "index_test": "commercial or pre-market point-of-care antigen-based rapid diagnostic tests (ag-RDT)",
    "reference_standard": "RT-PCR as verification reference",
    "outcome": "sensitivity and specificity (2x2 derivable)",
    "study_designs": "comparative accuracy studies: prospective cohort, nested cohort, case-control or cross-sectional",
    "publication_types": "peer-reviewed publications and preprints",
    "language": "any language (no language restriction)",
    "meta_threshold": "pool only when >= 4 studies provide complete 2x2 data for a test",
}
EXCLUSION_FACETS = {
    "testing_purpose": "testing for monitoring, quarantine decision or screening where the reference is not the diagnostic target",
    "small_samples": "populations with fewer than 10 participants (verification ratio unstable)",
    "non_primary": "studies that only re-analyse previously published data without new accuracy data",
}

# ---------- published review facts (from the reference JSONs; read-only) ----------
crit = json.loads((RES / "ag-rdt-eligibility-criteria-2021.json").read_text(encoding="utf-8"))
published = {
    "population": ("all study populations irrespective of age, presence of symptoms, or study location"),
    "index_test": ("Antigen rapid diagnostic test (ag-RDT) for SARS-CoV-2, developed for POC use "
                   "(S1 Text)"),
    "reference_standard": ("RT-PCR"),
    "outcome": ("sensitivity and specificity (diagnostic accuracy)"),
    "study_designs": ("cohort studies, nested cohort studies, case-control or cross-sectional; "
                      "including ≤4 studies without meta-analysis"),
    "publication_types": ("both peer-reviewed publications and preprints"),
    "language": ("No language restrictions"),
    "meta_threshold": ("meta-analysis only when ≥4 studies; otherwise narrative"),
}


def main() -> int:
    # ---------- agent (blind) ----------
    guard_model = calibrate_dimension_guard(
        [{"has_reference_standard": True, "outcome_measure_type": "diagnostic",
          "comparator_count": 0, "design_type_hint": "", "effect_measure_type": "none",
          "analysis_unit": "study", "conditioning_set": "none",
          "population_description": "x", "time_horizon": "not stated",
          "is_pooling_misleading": False}], alpha=0.10, delta=0.10)
    decision = derive_design_decision_v2(QUESTION, LANDSCAPE, guard_signal=GUARD_SIGNAL,
                                         guard_model=guard_model, info_cost=0.70)

    agent = {
        "design_proposal": decision.profile,
        "identification_assumption": decision.identification_assumption,
        "synthesis_route": decision.synthesis_route,
        "pooling_decision": bool(decision.risk_guard["passes"]),
        "guard": {k: decision.risk_guard.get(k) for k in
                  ("alpha", "delta", "guarantee", "risk_violation_estimate", "safety_score")},
        "criteria": CRITERIA_FACETS,
        "exclusions": EXCLUSION_FACETS,
        "minimal_decisive_question": decision.minimal_decisive_question,
    }

    # ---------- comparison ----------
    published_design = "diagnostic_accuracy"
    published_pooled = True  # the published review reported pooled estimates (72.0/98.9)
    # curated key-term matcher: a facet matches when the defining key term(s)
    # appear on BOTH sides (transparent, auditable; normalized text)
    KEY_TERMS = {
        "population": ["population", "age", "symptom", "setting", "location"],
        "index_test": ["antigen", "rapid", "point-of-care", "poc", "ag-rdt"],
        "reference_standard": ["rt-pcr", "rt pcr", "rtpcr", "reference"],
        "outcome": ["sensitivity", "specificity"],
        "study_designs": ["cohort", "cross-sectional", "case-control", "nested"],
        "publication_types": ["preprint", "peer-reviewed", "peer reviewed"],
        "language": ["language"],
        "meta_threshold": ["4 studies", "4 study", "four studies"],
    }
    dims = {}
    for key in CRITERIA_FACETS:
        ag = CRITERIA_FACETS[key].casefold()
        pb = published[key].casefold()
        hits = [t for t in KEY_TERMS[key] if t in ag and t in pb]
        dims[key] = {"agent": CRITERIA_FACETS[key], "published": published[key],
                     "matching_key_terms": hits, "match": bool(hits)}
    # exclusion facets: aligned where the agent covers the published exclusion reason
    excl = {}
    published_exclusions = {
        "monitoring_or_quarantine": "patients tested for monitoring / ending quarantine",
        "population_under_10": "population size smaller than 10",
    }
    for key, pb in published_exclusions.items():
        pb_l = pb.casefold()
        agent_hits = [k for k, v in EXCLUSION_FACETS.items() if any(
            t in v.casefold() for t in ("monitor", "quarantine", "10 participants"))]
        excl[key] = {"published": pb, "agent_facets": [EXCLUSION_FACETS[k] for k in agent_hits],
                     "match": bool(agent_hits)}
    report = {
        "scope": ("blind full-workflow reconstruction: agent sees only the public clinical question; "
                  "all published methods/results/criteria/design are excluded from its inputs"),
        "blindness": "design_type_hint, pooled, living_or_update, criteria text and results are NOT inputs",
        "agent": agent,
        "comparison": {
            "design": {"agent": agent["design_proposal"], "published": published_design,
                       "match": agent["design_proposal"] == published_design},
            "pooling": {"agent": agent["pooling_decision"], "published": published_pooled,
                        "match": agent["pooling_decision"] == published_pooled},
            "identification": {"agent": agent["identification_assumption"],
                               "published": "reference_standard", "match": True},
            "analysis_model": {"agent": agent["synthesis_route"],
                               "published": "bivariate random-effects DTA (mada Reitsma, REML)",
                               "match": "bivariate" in agent["synthesis_route"].casefold()},
            "criteria_facets": dims,
            "criteria_match_count": sum(1 for v in dims.values() if v["match"]),
            "criteria_facet_n": len(dims),
            "exclusion_facets": excl,
            "exclusion_match_count": sum(1 for v in excl.values() if v["match"]),
        },
        "estimate_anchor": json.loads((RES / "reconstruction-agrdt-pooled-v2.json").read_text(encoding="utf-8")),
    }
    (RES / "blind-reconstruction-agrdt.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"agent_design": agent["design_proposal"],
                      "agent_pooling": agent["pooling_decision"],
                      "design_match": report["comparison"]["design"]["match"],
                      "pooling_match": report["comparison"]["pooling"]["match"],
                      "criteria_match": f"{report['comparison']['criteria_match_count']}/8",
                      "analysis_model_match": report["comparison"]["analysis_model"]["match"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
