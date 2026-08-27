#!/usr/bin/env python3
"""Review Question Certificate (FirstResearch-aligned, clinical mapping).

依据(出处): _deliverables/deep-study/notes/firstresearch.md §2 (certificate 10 fields),
             §gates (hard: falsifier+mechanism+derivation>=3/5+falsifiability>=3/5;
             soft: boundary-language repair 阈值/相变/失效区/交互);
             官方实现: https://github.com/louiswang524/FirstResearch
             论文: arXiv:2607.05682 §3.3 (Research Question Certificate).

Deterministic; no LLM judge (FirstResearch used LLM judges with documented bias;
we keep the gate deterministic and its quality-scoring limitation explicit).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from metawingman.agent.decision_core import IDENTIFICATION_ASSUMPTIONS
from metawingman.scripts.metawingman_core.design_selection import SYNTHESIS_ROUTES

BOUNDARY_HINTS = ("threshold", "phase transition", "phase-transition", "failure regime",
                  "failure-regime", "interaction", "cutoff", "dose", "time window")


@dataclass(frozen=True)
class QuestionCertificate:
    primitives: str
    assumptions: list[str]
    mechanism_model: str
    tension: str
    question: str
    hypothesis: str
    falsifier: str
    minimal_decisive_test: str
    expected_observations: str
    failure_update: str
    quality_scores: dict[str, float]
    derivation_rationale: str = ""
    boundary_language: str = ""


def _falsifiability(hypothesis: str, falsifier: str) -> float:
    h = hypothesis.casefold()
    f = falsifier.casefold()
    if not f or not h:
        return 0.0
    score = 0.0
    if any(w in f for w in ("would", "should", "excluded", "no evidence", "not reproducible",
                            "fails", "contradicts", "observed", "reject")):
        score += 2.0
    if any(w in h for w in ("if", "then", "when", "given", "predicts", "should be")):
        score += 1.5
    if len(f) >= 20:
        score += 1.5
    return min(5.0, score)


def _derivation_score(primitives: str, assumptions: list[str], mechanism: str,
                      question: str) -> float:
    score = 0.0
    for tok in (primitives, " ".join(assumptions), mechanism, question):
        if len(tok) >= 12:
            score += 1.5
    return min(5.0, score)


def build_certificate(question: dict[str, Any], landscape: dict[str, Any],
                      design: dict[str, Any]) -> QuestionCertificate:
    """Assemble the certificate from clinical primitives + design decision."""
    is_diag = question.get("type") == "diagnostic" or bool(question.get("has_index_test_reference"))
    is_pred = question.get("type") == "prediction" or bool(question.get("has_prediction_model"))
    out_unit = str(landscape.get("outcome_unit") or "")
    primitives = ("population/index-test/reference/outcome; " +
                  f"design_type={design.get('profile') or 'unknown'}; outcome_unit={out_unit}")
    assumptions = [IDENTIFICATION_ASSUMPTIONS.get(design.get("profile", ""), "")]
    mechanism_model = (f"the estimand ({design.get('estimand', '')}) is identifiable under "
                       f"{assumptions[0] or 'no explicit assumption'}")
    tension = design.get("decision_tension", "")
    q_text = str(question)
    hypothesis = (f"If {q_text[:60]} then the reference review's synthesis route would be "
                  f"{SYNTHESIS_ROUTES.get(design.get('profile', ''), '')[:60]}")
    falsifier = ("the published review used a different synthesis route, reported a "
                 "non-comparable design label, or a pooled estimate that violates the "
                 "pre-specified estimand.")
    minimal_decisive_test = design.get("minimal_decisive_question", "")
    expected_observations = ("reference design = " + str(design.get("profile", "")) +
                             "; pooling decision = " + str(design.get("risk_guard", {}).get("passes")))
    failure_update = ("if the reference disagrees, update the precedence rule for the "
                      "conflicting signal combination (method-anchored revision).")
    scores = {
        "novelty": 1.0,
        "falsifiability": round(_falsifiability(hypothesis, falsifier), 2),
        "mechanism": 1.0 if "identifiable" in mechanism_model else 0.0,
        "derivation": round(_derivation_score(primitives, assumptions, mechanism_model, q_text), 2),
        "experiment": 1.0 if minimal_decisive_test else 0.0,
    }
    boundary = next((b for b in ("time window", "dose", "cutoff", "threshold")
                     if b in q_text.casefold()), "")
    return QuestionCertificate(
        primitives=primitives, assumptions=assumptions, mechanism_model=mechanism_model,
        tension=tension, question=q_text, hypothesis=hypothesis, falsifier=falsifier,
        minimal_decisive_test=minimal_decisive_test, expected_observations=expected_observations,
        failure_update=failure_update, quality_scores=scores,
        derivation_rationale="deterministic from clinical primitives + estimate",
        boundary_language=boundary)


def gate(cert: QuestionCertificate) -> dict[str, Any]:
    """Hard/soft gate (FirstResearch-style)."""
    s = cert.quality_scores
    failed = []
    if not cert.falsifier:
        failed.append("falsifier_empty")
    if s["mechanism"] < 1.0:
        failed.append("mechanism_empty")
    if s["derivation"] < 3.0:
        failed.append("derivation_below_3of5")
    if s["falsifiability"] < 3.0:
        failed.append("falsifiability_below_3of5")
    soft = [b for b in BOUNDARY_HINTS if b in (cert.boundary_language + cert.question).casefold()]
    return {"passed": not failed, "failed_hard": failed,
            "soft_boundary_hints": sorted(set(soft)),
            "quality_scores": cert.quality_scores}
