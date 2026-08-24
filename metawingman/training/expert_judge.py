#!/usr/bin/env python3
"""External heterogeneous expert judge — the training reward.

We do not let the agent reward itself: an external judge scores the agent's
*process* against how a top-journal / seasoned systematic-review author would
behave, on several dimensions. This judge is deliberately heterogeneous (its
criteria differ from the agent's own objective) so alignment cannot become
self-serving. Deterministic and offline.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# Judge dimensions: how a seasoned review author would judge the *process*.
DIMENSIONS = (
    "design_correctness",      # is the chosen design defensible for the estimand?
    "novelty_boldness",        # is the design selection appropriately bold, not defaulting to pairwise?
    "guard_respected",         # does it refuse to pool when that would be misleading?
    "honest_uncertainty",      # is uncertainty expressed honestly, not as a fake precise estimate?
    "clinical_accessibility",  # is the decision actually usable for clinical decision-making?
    "method_rigor",            # does it follow sound method-critique (estimand-first, stop rule)?
)

WEIGHTS: dict[str, float] = {
    "design_correctness": 0.25,
    "novelty_boldness": 0.20,
    "guard_respected": 0.20,
    "honest_uncertainty": 0.15,
    "clinical_accessibility": 0.10,
    "method_rigor": 0.10,
}


@dataclass(frozen=True)
class JudgeScore:
    total: float
    dimensions: dict[str, float]
    verdict: str
    feedback: str

    def to_dict(self) -> dict[str, Any]:
        return {"total": self.total, "dimensions": self.dimensions,
                "verdict": self.verdict, "feedback": self.feedback}


def judge_process(agent_process: dict[str, Any], *, gold_profile: str | None = None) -> JudgeScore:
    """Score an agent's process (a design decision + stage trace) as an expert judge."""
    decision = agent_process.get("decision") or agent_process
    profile = decision.get("profile") or ""
    risk_guard = decision.get("risk_guard") or {}
    stop_rule = decision.get("stop_rule") or {}
    identification = decision.get("identification_assumption") or ""

    # design_correctness: correct profile unless forced to structured_no_pooling or abstain.
    base_correct = (
        (gold_profile is None or profile == gold_profile)
        if profile not in ("", "structured_no_pooling")
        else (gold_profile == "structured_no_pooling" if gold_profile else bool(profile))
    )
    # novelty_boldness: rewarding a non-default (non-pairwise) choice; defaulting to
    # pairwise when richer evidence exists is penalised.
    bold = 1.0 if profile not in ("intervention_pairwise", "") else 0.3

    guard_passes = bool(risk_guard.get("passes"))
    risk_violation = float(risk_guard.get("risk_violation_estimate") or 0.0)
    has_guard = bool(risk_guard) and "alpha" in risk_guard

    # honest_uncertainty: guard present with a risk floor is honest; a vanishing risk
    # violated estimate is suspicious if we claim a guarantee.
    honest = 1.0 if (has_guard and risk_violation <= 0.10) else 0.5

    # clinical_accessibility: an explicit identification assumption + a decisive
    # stop rule make the decision usable.
    accessible = 1.0 if (identification and stop_rule) else 0.4

    # method_rigor: estimand-first + explicit route + stop rule present.
    rigor = 1.0 if (profile and decision.get("estimand") and decision.get("synthesis_route")
                    and stop_rule) else 0.4

    dims = {
        "design_correctness": float(base_correct),
        "novelty_boldness": bold,
        "guard_respected": float(guard_passes),
        "honest_uncertainty": honest,
        "clinical_accessibility": accessible,
        "method_rigor": rigor,
    }
    total = round(sum(WEIGHTS[k] * dims[k] for k in DIMENSIONS), 4)
    if total >= 0.75:
        verdict = "accept"
    elif total >= 0.5:
        verdict = "major_revision"
    else:
        verdict = "reject"
    feedback = (f"judge: {verdict} (score={total:.3f}); "
                f"design={profile or '(none)'} guard={guard_passes} "
                f"stop={stop_rule.get('decision', '')}")
    return JudgeScore(total=total, dimensions=dims, verdict=verdict, feedback=feedback)


def preference_pairs(
    trajectories: list[tuple[dict[str, Any], str | None]],
) -> list[dict[str, Any]]:
    """Build (chosen, rejected) preference pairs by external-judge score.

    Each trajectory is (agent_process, gold_profile). We rank by judge score and
    create a pair of the highest and lowest as a DPO preference example.
    """
    scored = [(t, judge_process(t[0], gold_profile=t[1]).total) for t in trajectories]
    scored.sort(key=lambda p: p[1], reverse=True)
    pairs: list[dict[str, Any]] = []
    if len(scored) >= 2:
        (chosen, _), (rejected, _) = scored[0], scored[-1]
        pairs.append({
            "chosen": chosen[0], "chosen_score": scored[0][1],
            "rejected": rejected[0], "rejected_score": scored[-1][1],
        })
    return pairs
