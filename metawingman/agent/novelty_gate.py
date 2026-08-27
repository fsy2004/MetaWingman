#!/usr/bin/env python3
"""Novelty x executability gate for the review-selection (topic) layer.

依据(出处): _deliverables/deep-study/notes/novelty-executability-and-virtual-lab.md
             §① arXiv:2409.04109 (ICLR 2025): four dimensions
             novelty/excitement/feasibility/expected effectiveness (1-10);
             "Overall correlated r=0.725 with Novelty, r=0.854 with Excitement but
             only r=0.097 with Feasibility" -> judges are pulled by novelty and
             almost ignore feasibility; AI ideas were LESS feasible than human
             (6.34 vs 6.61, n.s.) — hence feasibility needs its own objective path.
             Feasibility failure modes (vague details / wrong dataset / missing
             baseline / unrealistic assumption / excessive resources) become the
             executable quality checklist.
Virtual Lab (bioRxiv 2024.11.11.623004) contributes the "external verifier" point:
             executability must be checked against evidence outside the generation
             chain (their wet-lab; our benchmark data / extractability), not by a
             more critical LLM.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

EXEC_CHECKLIST = {
    "vague_detail": "evidence structure missing arm/ref/prediction/outcome signals",
    "wrong_dataset": "no (or unmatched) public evidence anchor for the question",
    "missing_baseline": "no published-review precedent/source corpus found for the topic",
    "unrealistic_assumption": "question requires data that is not publicly recoverable",
    "excessive_resources": "estimated evidence-actions exceed the budget",
}


@dataclass
class TopicGateResult:
    novelty: float        # 1..10 (inverse coverage proxy)
    executability: float  # 1..10 (objective check score)
    expected_effectiveness: float
    excitement: float
    decision: str         # "select" | "review" | "reject"
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"novelty": round(self.novelty, 2), "executability": round(self.executability, 2),
                "expected_effectiveness": round(self.expected_effectiveness, 2),
                "excitement": round(self.excitement, 2), "decision": self.decision,
                "reasons": self.reasons}


def coverage_proxy(question_tokens: list[str], index: dict[str, int]) -> float:
    """novelty proxy: fraction of the question's key terms already covered by
    published reviews (index built from our own corpus assets)."""
    if not question_tokens:
        return 0.0
    hits = sum(1 for t in question_tokens if t in index and index[t] > 0)
    return min(1.0, hits / len(question_tokens))


def executability_score(evidence: dict[str, Any], public_anchor: bool,
                        budget: int = 8) -> tuple[float, list[str]]:
    """Objective score 1..10 from the checklist (outside the generation chain)."""
    points = 0.0
    failures: list[str] = []
    if evidence.get("has_reference_standard") or evidence.get("has_prediction_model") \
            or evidence.get("comparator_count") or evidence.get("outcome_measure_type"):
        points += 3.0
    else:
        failures.append(EXEC_CHECKLIST["vague_detail"])
    if public_anchor:
        points += 3.0
    else:
        failures.append(EXEC_CHECKLIST["wrong_dataset"])
    if evidence.get("precedent_found"):
        points += 2.0
    else:
        failures.append(EXEC_CHECKLIST["missing_baseline"])
    est_actions = int(evidence.get("evidence_actions", 1))
    if est_actions <= budget:
        points += 2.0
    else:
        failures.append(EXEC_CHECKLIST["excessive_resources"])
    return min(10.0, points), failures


def gate(question_tokens: list[str], index: dict[str, int],
         evidence: dict[str, Any], public_anchor: bool) -> TopicGateResult:
    coverage = coverage_proxy(question_tokens, index)
    novelty = round(10.0 * (1.0 - coverage), 2)
    exec_score, reasons = executability_score(evidence, public_anchor)
    effectiveness = round(0.5 * novelty + 0.5 * exec_score, 2)
    excitement = round(min(10.0, 0.5 * novelty + 0.3 * exec_score + 2.0), 2)
    if exec_score < 5.0:
        decision = "reject"
        reasons.append("executability below 5 (objective checklist) — reject despite novelty")
    elif novelty < 2.5:
        decision = "reject"
        reasons.append("novelty below 2.5 (topic already covered by published reviews)")
    elif exec_score < 7.0:
        decision = "review"
    else:
        decision = "select"
    return TopicGateResult(novelty, exec_score, effectiveness, excitement, decision, reasons)
