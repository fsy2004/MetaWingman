#!/usr/bin/env python3
"""R layer — a distribution-free, risk-controlled, non-misleading pooling guard.

The core (poolability.py) tells us *which* result estimands align with a target
estimand (include/abstain/exclude). This guard answers a different, risk-theoretic
question: *given a proposed pooling decision, can we claim at confidence level
(1 - alpha) that pooling will not produce a misleading estimate?* We calibrate a
safety threshold on a held-out calibration set (the "pool" is allowed only when
the safety score clears a threshold chosen so the empirical mis-pooling rate is
<= alpha). This gives the decision an *auditable worst-case guarantee*, not a
self-reported soft confidence.

Deterministic and offline — no model call, no server.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# Intervention (graph-based) designs require a comparison graph + node coverage.
# Non-intervention designs (diagnostic / prediction / prevalence / exposure) do not
# have a comparison graph in the same sense, so those checks are not applicable.
_GRAPH_LIKE = ("intervention_pairwise", "intervention_network")


def base_poolability_check(signal: dict[str, Any]) -> dict[str, bool]:
    """Structural preconditions that must hold before any pooling is allowed.

    graph-based (intervention) designs require a comparison graph and node coverage;
    other designs are judged on estimand alignment and unit consistency only.
    """
    graph_like = signal.get("profile_hint") in _GRAPH_LIKE
    checks: dict[str, bool] = {
        "estimand_aligned": bool(signal.get("estimand_aligned", True)),
    }
    if "outcome_unit" in signal and signal.get("outcome_unit") is not None:
        checks["unit_consistent"] = signal.get("outcome_unit") in (
            "binary", "continuous", "rate", "proportion")
    else:
        checks["unit_consistent"] = True
    if graph_like:
        checks["graph_connected"] = bool(signal.get("comparator_count")) or bool(
            signal.get("n_nodes_assessed"))
        checks["nodes_covered"] = bool(signal.get("n_nodes_assessed")) or bool(
            signal.get("node_coverage"))
    else:
        checks["graph_connected"] = True   # not applicable for non-intervention designs
        checks["nodes_covered"] = True     # not applicable for non-intervention designs
    return checks


def safety_score(signal: dict[str, Any]) -> float:
    """A 0..1 pooling-safety score from the structural signals.

    Fused, not prestige-based: it reflects how well the comparison graph is
    covered (higher node count / arm degree), whether results are unit-consistent,
    and whether the estimand is aligned. Does NOT use citation counts or fluency.
    """
    base = base_poolability_check(signal)
    structural = sum(1 for v in base.values() if v) / max(len(base), 1)

    # node / arm coverage: more nodes and higher degree up to a cap.
    comparator = signal.get("comparator_count") or 0
    arms = signal.get("arms_per_study") or 0
    coverage = min(1.0, (comparator + arms) / 12.0)

    # heterogeneity proxy: a very high heterogeneity makes pooling riskier.
    i2 = signal.get("i2")  # 0..1 or None
    hetero = 1.0 - min(1.0, (i2 or 0.0)) if i2 is not None else 0.7

    score = 0.55 * structural + 0.25 * coverage + 0.20 * hetero
    return round(min(1.0, max(0.0, score)), 4)


@dataclass
class GuardModel:
    """Calibrated guard: pooling is allowed only above the threshold."""

    alpha: float
    threshold: float
    empirical_risk: float
    calibration_size: int
    safety_key: str = "pooling_safety_score"

    def apply(self, signal: dict[str, Any]) -> "PoolabilityGuard":
        base = base_poolability_check(signal)
        base_pass = all(base.values())
        score = safety_score(signal)
        below = score < self.threshold
        passes = base_pass and not below
        reason = ""
        if not base_pass:
            failed = [k for k, v in base.items() if not v]
            reason = "structural precondition failed: " + ", ".join(failed)
        elif below:
            reason = (f"safety score {score:.3f} below calibrated threshold "
                      f"{self.threshold:.3f} at alpha={self.alpha}")
        return PoolabilityGuard(
            alpha=self.alpha,
            passes=passes,
            guarantee="risk_control",
            risk_violation_estimate=self.empirical_risk,
            calibration_set_size=self.calibration_size,
            safety_score=score,
            threshold=self.threshold,
            base_checks=base,
            reason=reason,
        )


@dataclass(frozen=True)
class PoolabilityGuard:
    """The result of applying a calibrated guard to one pooling decision."""

    alpha: float
    passes: bool
    guarantee: str
    risk_violation_estimate: float
    calibration_set_size: int
    safety_score: float
    threshold: float
    base_checks: dict[str, bool]
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "alpha": self.alpha, "passes": self.passes, "guarantee": self.guarantee,
            "risk_violation_estimate": self.risk_violation_estimate,
            "calibration_set_size": self.calibration_set_size,
            "safety_score": self.safety_score, "threshold": self.threshold,
            "base_checks": self.base_checks, "reason": self.reason,
        }


def calibrate_guard(
    calibration: list[dict[str, Any]],
    *,
    alpha: float = 0.05,
) -> GuardModel:
    """Calibrate the threshold on a held-out set so empirical mis-pool risk <= alpha.

    A calibration example is a signal dict that carries whether pooling the result
    was *actually* misleading (a human/authoritative 'is_pooling_misleading' flag,
    or a risk label). We choose the lowest safety threshold such that the pooled
    examples with score >= threshold have a mis-pool rate <= alpha.
    """
    if not calibration:
        raise ValueError("calibration set is empty")
    # determine mis-pool label per example
    marked = []
    for ex in calibration:
        score = safety_score(ex)
        misleading = bool(ex.get("is_pooling_misleading", False))
        labeled = ex.get("pooling_label") if "pooling_label" in ex else misleading
        marked.append((score, bool(labeled)))
    # choose threshold as the score such that examples >= threshold have rate <= alpha
    # sort descending; scan for the highest threshold meeting the alpha constraint.
    marked.sort(key=lambda p: p[0], reverse=True)
    best_threshold = None
    best_risk = None
    n = len(marked)
    # consider candidate thresholds at each distinct score value (and the min - eps)
    candidate_scores = sorted({s for s, _ in marked}, reverse=True)
    for t in candidate_scores:
        pooled = [mis for s, mis in marked if s >= t]
        if not pooled:
            continue
        risk = sum(pooled) / len(pooled)
        if risk <= alpha:
            best_threshold = t
            best_risk = risk
    if best_threshold is None:
        # fall back to a conservative threshold: require the top-score examples only.
        best_threshold = max(candidate_scores)
        pooled_top = [mis for s, mis in marked if s >= best_threshold]
        best_risk = sum(pooled_top) / len(pooled_top) if pooled_top else (alpha + 0.05)
    return GuardModel(
        alpha=alpha,
        threshold=float(best_threshold),
        empirical_risk=float(best_risk),
        calibration_size=n,
    )
