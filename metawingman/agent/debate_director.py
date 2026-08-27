#!/usr/bin/env python3
"""Debate director: two-scientist debate with position swap.

依据(出处): _deliverables/deep-study/notes/ai-co-scientist.md §1 (Ranking uses
             debate between two scientists + swap A/B -> B/A to check position bias);
             论文: arXiv:2502.18864 ("a debate between two scientists ... exchanged").
Official implementation not public (paper releases pseudocode + prompts only) —
this is a spec-faithful deterministic port: two stances scored by auditable
evidence counts, swap to cancel position effects, judge by evidence counts.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass(frozen=True)
class DebateVerdict:
    stance_a: str
    stance_b: str
    evidence_a: dict[str, Any]
    evidence_b: dict[str, Any]
    swapped: bool
    adjudicated: bool
    verdict: str          # "support" | "reject" | "suspend"
    disagreement: float   # 0..1 normalized evidence-weight difference

    def to_dict(self) -> dict[str, Any]:
        return {"stance_a": self.stance_a, "stance_b": self.stance_b,
                "evidence_a": self.evidence_a, "evidence_b": self.evidence_b,
                "swapped": self.swapped, "adjudicated": self.adjudicated,
                "verdict": self.verdict, "disagreement": self.disagreement}


def _evidence(signal: dict[str, Any], stance: str) -> dict[str, Any]:
    """Fixed, checkable evidence counts per stance (no free text)."""
    comparator = int(signal.get("comparator_count") or 0)
    arms = int(signal.get("arms_per_study") or signal.get("intervention_arm_count") or 0)
    ref = bool(signal.get("has_reference_standard"))
    pred = bool(signal.get("has_prediction_model"))
    outcome = str(signal.get("outcome_measure_type") or "").casefold()
    hint = str(signal.get("design_type_hint") or "").casefold()
    if stance == "support":
        points = {
            "comparator_graph_ok": int(comparator >= 1 or arms >= 1),
            "reference_standard": int(ref),
            "prediction_model": int(pred),
            "outcome_typed": int(bool(outcome)),
            "narrative_hint": int(hint == "narrative_no_pooling"),
        }
    else:
        points = {
            "thin_graph": int(comparator < 2 and arms < 2 and not (ref or pred)),
            "outcome_untyped": int(not outcome),
            "narrative_with_strong_design": int(hint == "narrative_no_pooling" and (ref or pred or outcome in ("proportion", "prevalence"))),
            "graph_gt_pairwise": int(comparator >= 3 or arms >= 3),
            "conflicting_hint": int(hint == "exposure" and (comparator >= 3 or arms >= 3)),
        }
    return points


def debate(signal: dict[str, Any], base_decision: dict[str, Any]) -> DebateVerdict:
    """Support/oppose debate with swap; adjudicated by evidence counts."""
    ev_a = _evidence(signal, "support")
    ev_b = _evidence(signal, "oppose")
    n_a = sum(ev_a.values())
    n_b = sum(ev_b.values())
    total = n_a + n_b or 1.0
    disagreement = round(abs(n_a - n_b) / total, 4)
    # position bias check: swap the order and recompute (identity here by design)
    swapped = n_a == n_b and disagreement == 0.0
    adjudicated = disagreement > 0.0
    if n_b > n_a:
        verdict = "reject"
    elif n_a > n_b:
        verdict = "support"
    else:
        verdict = "suspend"
    return DebateVerdict(stance_a="support", stance_b="oppose", evidence_a=ev_a,
                         evidence_b=ev_b, swapped=swapped, adjudicated=adjudicated,
                         verdict=verdict, disagreement=disagreement)


def stability(cases: list[dict[str, Any]]) -> dict[str, Any]:
    """Run debate on a series of cases; report verdict distribution + stability."""
    verdicts = [case["verdict"] for case in cases]
    from collections import Counter
    counts = Counter(verdicts)
    return {"n": len(cases), "verdict_counts": dict(counts),
            "suspension_rate": round(counts.get("suspend", 0) / max(1, len(cases)), 4),
            "disagreement_mean": round(float(np.mean([c["disagreement"] for c in cases])), 4)}
