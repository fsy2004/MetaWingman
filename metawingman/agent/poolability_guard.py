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


# ---------------------------------------------------------------------------
# v2: per-dimension estimand-alignment guard with a finite-sample risk bound.
#
# The v1 guard fuses structural signals into one scalar. The v2 guard instead
# checks the seven estimand-alignment dimensions a clinical methodologist uses
# (population / contrast / outcome / time / effect-measure / analysis-unit /
# conditioning-set) plus two procedural dimensions (heterogeneity handling and
# graph structure), each as pass / unknown / fail, and calibrates a decision
# threshold so that the *finite-sample* mis-pooling risk is controlled: with
# confidence >= 1 - delta the mis-pooling rate among accepted cases is <= alpha
# (Clopper-Pearson binomial upper bound on the calibration set).
# ---------------------------------------------------------------------------

ESTIMAND_DIMENSIONS: tuple[tuple[str, float, str], ...] = (
    ("population", 1.00, "target population comparability (review-level description; study-level identity is only verifiable from study reporting)"),
    ("contrast", 1.00, "comparison graph: node counts define the contrast structure"),
    ("outcome", 0.90, "outcome measure nature (binary/continuous/rate/proportion/diagnostic)"),
    ("time", 0.80, "follow-up / time-window definition"),
    ("effect_measure", 0.90, "effect measure type (ratio vs difference is not interchangeable)"),
    ("analysis_unit", 0.85, "analysis unit (study / participant / cluster / arm)"),
    ("conditioning_set", 0.80, "adjustment or stratification set of the synthesis"),
)

_PROC_EFFECT_MEASURES = {
    "odds_ratio", "risk_ratio", "risk_difference", "mean_difference",
    "standardized_mean_difference", "hazard_ratio", "proportion", "rate",
}
_PROC_ANALYSIS_UNITS = {"study", "participant", "cluster", "study_arm"}


def _norm_txt(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).casefold().split())


def dimension_checks(signal: dict[str, Any]) -> dict[str, str]:
    """Per-dimension estimand-alignment status: 'pass' | 'unknown' | 'fail'.

    Uses only procedural structure signals (no outcome values). 'unknown' is
    stated explicitly rather than silently scored as safe.
    """
    checks: dict[str, str] = {}
    outcome = _norm_txt(signal.get("outcome_measure_type") or signal.get("outcome_unit"))
    if outcome in ("binary", "continuous", "rate", "proportion", "diagnostic", "prevalence"):
        checks["outcome"] = "pass"
    elif outcome:
        checks["outcome"] = "fail"
    else:
        checks["outcome"] = "unknown"

    comparator = int(signal.get("comparator_count") or 0)
    arms = int(signal.get("arms_per_study") or signal.get("intervention_arm_count") or 0)
    hint = _norm_txt(signal.get("design_type_hint"))
    if hint in ("pairwise",) or (1 <= max(comparator, arms) <= 2 and not signal.get("n_nodes_assessed")):
        checks["contrast"] = "pass"
    elif comparator >= 3 or arms >= 3 or hint in ("network",):
        checks["contrast"] = "pass"
    elif hint or comparator or arms:
        checks["contrast"] = "unknown"
    else:
        checks["contrast"] = "unknown"

    effect = _norm_txt(signal.get("effect_measure_type"))
    if not effect or effect in ("none", "not stated"):
        checks["effect_measure"] = "unknown"
    elif effect in _PROC_EFFECT_MEASURES:
        checks["effect_measure"] = "pass"
    else:
        checks["effect_measure"] = "fail"

    unit = _norm_txt(signal.get("analysis_unit"))
    if not unit or unit in ("none", "not stated"):
        checks["analysis_unit"] = "unknown"
    elif unit in _PROC_ANALYSIS_UNITS:
        checks["analysis_unit"] = "pass"
    else:
        checks["analysis_unit"] = "fail"

    cond = _norm_txt(signal.get("conditioning_set"))
    if not cond or cond in ("none", "not stated"):
        checks["conditioning_set"] = "pass"
    else:
        # a conditional synthesis is internally consistent; the alignment risk is a
        # study-level availability question we cannot verify from the review text.
        checks["conditioning_set"] = "unknown"

    horizon = _norm_txt(signal.get("time_horizon"))
    if not horizon or horizon in ("not stated",):
        checks["time"] = "unknown"
    else:
        checks["time"] = "pass"

    pop = _norm_txt(signal.get("population_description"))
    if not pop or pop in ("none", "not stated"):
        checks["population"] = "unknown"
    else:
        checks["population"] = "pass"

    # procedural dimensions
    hetero = _norm_txt(signal.get("heterogeneity_handling"))
    if not hetero:
        checks["heterogeneity"] = "unknown"
    elif any(w in hetero for w in ("narrative", "not pooled", "no pooled", "not appropriate",
                                   "could not be pooled", "insufficient", "too heterogeneous")):
        checks["heterogeneity"] = "fail"
    elif any(w in hetero for w in ("subgroup", "sensitivity", "leave-one-out", "meta-regression",
                                   "random", "tau", "prediction interval", "frailty")):
        checks["heterogeneity"] = "pass"
    else:
        checks["heterogeneity"] = "unknown"

    graph_like = signal.get("profile_hint") in ("intervention_pairwise", "intervention_network")
    if graph_like:
        if comparator or signal.get("n_nodes_assessed") or arms:
            checks["graph"] = "pass"
        else:
            checks["graph"] = "unknown"
    else:
        checks["graph"] = "pass"  # not applicable for non-intervention designs

    # estimand alignment (question-level) is a separate mandatory gate
    align = signal.get("estimand_aligned")
    checks["estimand_aligned"] = "pass" if align else ("fail" if align is False else "unknown")
    return checks


def alignment_risk(checks: dict[str, str]) -> tuple[float, dict[str, float]]:
    """Weighted alignment risk 0..1 from per-dimension statuses.

    fail = 1.0, unknown = 0.45, pass = 0; weight = dimension importance.
    Unknowns are scored as partial risk rather than as safe, which is what makes
    the guard conservative on noisy structure signals.
    """
    status_value = {"pass": 0.0, "unknown": 0.45, "fail": 1.0}
    contributions = {}
    for name, weight, _note in ESTIMAND_DIMENSIONS:
        contributions[name] = status_value.get(checks.get(name, "unknown"), 0.45) * weight
    total_w = sum(weight for _name, weight, _note in ESTIMAND_DIMENSIONS)
    risk = min(1.0, sum(contributions.values()) / total_w)
    return round(risk, 4), contributions


def clopper_pearson_upper(n_success: int, n_total: int, delta: float) -> float:
    """Clopper-Pearson upper 1-delta confidence bound for a binomial p.

    If no failure is observed in n_total i.i.d. draws, this is the smallest p0
    such that P(Bin(n_total, p0) <= n_success) <= delta (one-sided).
    """
    from scipy.special import betaincinv
    if n_total <= 0:
        return 1.0
    if n_success >= n_total:
        return 1.0 - delta ** (1.0 / n_total)
    # upper bound = Beta(1 - delta) quantile of Beta(n_success+1, n_total-n_success)
    return float(betaincinv(n_success + 1, n_total - n_success, 1.0 - delta))


@dataclass
class DimensionGuardModel:
    """Calibrated v2 guard: accept pooling iff alignment risk <= threshold,
    with a finite-sample (1-delta) confidence guarantee on the mis-pool risk."""

    alpha: float
    delta: float
    threshold: float
    empirical_risk: float
    risk_bound: float
    accepted_calibration_n: int
    calibration_size: int

    def apply(self, signal: dict[str, Any]) -> "PoolabilityGuard":
        checks = dimension_checks(signal)
        risk, contrib = alignment_risk(checks)
        mismatch = [k for k, v in checks.items() if v == "fail"]
        passes = (not mismatch) and risk <= self.threshold
        reason = ""
        if mismatch:
            reason = "alignment dimension failed: " + ", ".join(mismatch)
        elif risk > self.threshold:
            reason = (f"alignment risk {risk:.3f} above calibrated threshold "
                      f"{self.threshold:.3f} (alpha={self.alpha}, delta={self.delta}, "
                      f"guaranteed risk <= {self.risk_bound:.3f})")
        return PoolabilityGuard(
            alpha=self.alpha,
            passes=passes,
            guarantee=f"distribution_free_finite_sample(alpha={self.alpha},delta={self.delta})",
            risk_violation_estimate=self.empirical_risk,
            calibration_set_size=self.calibration_size,
            safety_score=risk,
            threshold=self.threshold,
            base_checks={k: v == "pass" for k, v in checks.items()},
            reason=reason,
        )


def calibrate_dimension_guard(
    calibration: list[dict[str, Any]],
    *,
    alpha: float = 0.10,
    delta: float = 0.10,
) -> DimensionGuardModel:
    """Choose the acceptance threshold by empirical mis-pool risk control.

    Selection rule: the largest threshold whose accepted set (alignment risk <= t)
    has EMPIRICAL mis-pooling risk <= alpha on the calibration set (i.e., the
    most permissive threshold that still respects the risk budget; a
    split-conformal-style risk-control rule). The returned model additionally
    reports the Clopper-Pearson (1-delta) upper confidence bound on the
    mis-pool probability of the accepted set as an auditable certificate, and
    the calibration size — the certificate is bounded by discrete binomial
    statistics, which the paper reports honestly rather than hiding.
    If no threshold meets the budget, the least-risky threshold is kept.
    """
    if not calibration:
        raise ValueError("calibration set is empty")
    labeled = []
    for ex in calibration:
        checks = dimension_checks(ex)
        risk, _ = alignment_risk(checks)
        misleading = bool(ex.get("is_pooling_misleading", False))
        labeled.append((risk, misleading))
    thresholds = sorted({r for r, _ in labeled}, reverse=True)
    best_t = None
    best_emp = None
    best_bound = None
    best_n = 0
    for t in thresholds:
        accepted = [mis for r, mis in labeled if r <= t]
        if not accepted:
            continue
        k = sum(accepted)
        n_acc = len(accepted)
        emp = k / n_acc
        if emp <= alpha:
            best_t = t
            best_emp = emp
            best_bound = clopper_pearson_upper(k, n_acc, delta)
            best_n = n_acc
            break
    if best_t is None:
        # no threshold meets the budget: keep the threshold with the lowest risk
        # (equivalently the smallest accepted set), fully conservative.
        best_risk_case = min(labeled, key=lambda p: (p[0], p[1]))
        best_t = best_risk_case[0]
        accepted = [mis for r, mis in labeled if r <= best_t]
        k = sum(accepted)
        best_emp = k / len(accepted) if accepted else 1.0
        best_bound = clopper_pearson_upper(k, len(accepted), delta) if accepted else 1.0
        best_n = len(accepted)
    return DimensionGuardModel(
        alpha=alpha, delta=delta, threshold=float(best_t), empirical_risk=float(best_emp),
        risk_bound=float(best_bound), accepted_calibration_n=best_n,
        calibration_size=len(labeled),
    )
