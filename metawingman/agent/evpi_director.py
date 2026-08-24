#!/usr/bin/env python3
"""V layer — value of information (EVPI) and the living/stop rule.

The core (evidence_acquisition.plan_evidence_acquisition) already scores candidate
evidence actions by residual-risk * claim-impact / cost. This layer overlays a
strict EVPI phrasing: for each candidate evidence gap we compute the expected
utility gain of resolving it vs its marginal cost, and we make the *finish/stop*
decision explicit: when the best remaining EVPI falls below the information
cost-to-benefit threshold, the review stops (living stops updating).

Deterministic and offline — no model call, no server.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class NextEvidence:
    """The single most valuable next evidence to acquire."""

    gap: str
    evpi: float
    expected_utility_gain: float


@dataclass(frozen=True)
class StopRule:
    """Whether to continue (living) or stop given information value vs cost."""

    threshold: float
    decision: str  # "continue" | "stop"

    def to_dict(self) -> dict[str, Any]:
        return {"threshold": self.threshold, "decision": self.decision}


def estimate_evpi(gap: dict[str, Any], info_cost: float = 1.0) -> float:
    """Expected value of perfect information for one gap, net of info cost.

    gap carries an expected utility loss *avoidable* if the gap is closed
    (`expected_utility_gain`) and optionally an information-entropy prior
    (`uncertainty`, 0..1). EVPI is the gain reduced by knowledge prior and cost.
    """
    gain = float(gap.get("expected_utility_gain") or 0.0)
    uncertainty = float(gap.get("uncertainty") or 0.5)
    evpi = gain * uncertainty - info_cost
    return round(evpi, 6)


def decide_stop(evpi: float, info_cost: float = 1.0, *, slack: float = 0.0) -> StopRule:
    """Stop when highest EVPI <= info_cost (+ small slack favouring continuation)."""
    return StopRule(threshold=info_cost, decision="stop" if evpi <= info_cost + slack else "continue")


def most_valuable_query(
    gaps: list[dict[str, Any]],
    *,
    prior_utility: dict[str, float] | None = None,
    info_cost: float = 1.0,
    slack: float = 0.0,
) -> NextEvidence | None:
    """Pick the gap with the highest expected utility gain after information value."""
    prior_utility = prior_utility or {}
    best: NextEvidence | None = None
    for gap in gaps:
        evpi = estimate_evpi(gap, info_cost=info_cost)
        gain = float(gap.get("expected_utility_gain") or evpi)
        if best is None or gain > best.expected_utility_gain:
            best = NextEvidence(
                gap=str(gap.get("gap") or gap.get("gap_id") or ""),
                evpi=evpi,
                expected_utility_gain=round(gain, 6),
            )
    return best


def evaluate_living(
    gap_scores: list[dict[str, Any]],
    *,
    info_cost: float = 1.0,
    slack: float = 0.0,
) -> dict[str, Any]:
    """Combine most-valuable-query with a stop rule into a living/stop decision."""
    next_q = most_valuable_query(gap_scores, info_cost=info_cost, slack=slack)
    if next_q is None:
        return {
            "next_evidence": None,
            "stop_rule": StopRule(info_cost, "stop").to_dict(),
            "living": False,
            "gap_count": 0,
        }
    stop = decide_stop(next_q.evpi, info_cost=info_cost, slack=slack)
    return {
        "next_evidence": {
            "gap": next_q.gap, "evpi": next_q.evpi,
            "expected_utility_gain": next_q.expected_utility_gain,
        },
        "stop_rule": stop.to_dict(),
        "living": stop.decision == "continue",
        "gap_count": len(gap_scores),
    }
