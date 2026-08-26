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


# ---------------------------------------------------------------------------
# v2: landscape-driven value of information + discriminative stop calibration.
#
# v1 used a fixed gap prior (default utilities), which made the stop rule
# unidentifiable (living always False at the default info cost). v2 derives
# candidate gaps and their expected utility gain / uncertainty from the actual
# evidence structure, then calibrates ONE scalar (information cost) on a frozen
# calibration split so the stop decision can be measured (agreement, precision,
# recall) on OOD reviews — including real living/update reviews.
# ---------------------------------------------------------------------------

def landscape_gaps(
    landscape: dict[str, Any],
    profile: str,
    *,
    heterogeneity_handling: str | None = None,
    gains: dict[str, float] | None = None,
) -> list[dict[str, Any]]:
    """Derive evidence gaps and their value-of-information from the structure.

    gains overrides the expected-utility-gain table (used by the calibration
    search); defaults: graph 0.85/0.40, node 0.65, refstd 0.90, extval 0.75,
    heterogeneity 0.85/0.55, freshness 0.70.
    """
    gains = gains or {}
    g_graph_thin, g_graph_ok = gains.get("graph_thin", 0.85), gains.get("graph_ok", 0.40)
    g_node, g_refstd, g_extval = gains.get("node", 0.65), gains.get("refstd", 0.90), gains.get("extval", 0.75)
    g_hetero_hi, g_hetero_lo = gains.get("hetero_hi", 0.85), gains.get("hetero_lo", 0.55)
    g_fresh = gains.get("freshness", 0.70)
    comparator = int(landscape.get("comparator_count") or 0)
    nodes = landscape.get("n_nodes_assessed")
    hetero = (" ".join(str(heterogeneity_handling or "").casefold().split())
              if heterogeneity_handling else "")
    gaps: list[dict[str, Any]] = []

    if profile in ("intervention_pairwise", "intervention_network"):
        if not nodes:
            gaps.append({"gap": "node_coverage_assessment",
                         "expected_utility_gain": g_node, "uncertainty": 0.75,
                         "note": "graph coverage not assessed"})
        if comparator < 2:
            gaps.append({"gap": "comparison_graph_coverage",
                         "expected_utility_gain": g_graph_thin, "uncertainty": 0.80,
                         "note": "thin comparison graph"})
        else:
            gaps.append({"gap": "comparison_graph_coverage",
                         "expected_utility_gain": g_graph_ok, "uncertainty": 0.50,
                         "note": "graph present"})
    if profile == "diagnostic_accuracy" and not landscape.get("has_reference_standard"):
        gaps.append({"gap": "reference_standard_verification",
                     "expected_utility_gain": g_refstd, "uncertainty": 0.80})
    if profile == "prognostic_prediction" and landscape.get("has_prediction_model"):
        gaps.append({"gap": "external_validity",
                     "expected_utility_gain": g_extval, "uncertainty": 0.70})
    if hetero and any(w in hetero for w in ("narrative", "not pooled", "insufficient",
                                            "too heterogeneous", "not appropriate")):
        gaps.append({"gap": "heterogeneity_quantification",
                     "expected_utility_gain": g_hetero_hi, "uncertainty": 0.80,
                     "note": "heterogeneity handled narratively"})
    elif not hetero:
        gaps.append({"gap": "heterogeneity_quantification",
                     "expected_utility_gain": g_hetero_lo, "uncertainty": 0.65})
    # topic dynamism is not directly observable from the review text; keep the
    # update-freshness gap present with a prior gain (never zero).
    gaps.append({"gap": "update_freshness",
                 "expected_utility_gain": g_fresh, "uncertainty": 0.75})
    return gaps


def decide_living_v2(
    gaps: list[dict[str, Any]],
    *,
    info_cost: float,
) -> dict[str, Any]:
    """EVPI-only stop decision (no input living flag, no calendar prior)."""
    best = None
    for gap in gaps:
        evpi = estimate_evpi(gap, info_cost=info_cost)
        gain = float(gap.get("expected_utility_gain") or 0.0)
        if best is None or gain > best[1]:
            best = (gap["gap"], gain, evpi)
    if best is None:
        return {"living": False, "next_evidence": None,
                "stop_rule": StopRule(info_cost, "stop").to_dict(), "max_evpi": None}
    living = best[2] > 0.0
    return {
        "living": living,
        "next_evidence": {"gap": best[0], "evpi": best[2],
                          "expected_utility_gain": best[1]},
        "stop_rule": StopRule(info_cost, "continue" if living else "stop").to_dict(),
        "max_evpi": best[2],
    }


def calibrate_living(
    cases: list[tuple[list[dict[str, Any]], bool]],
    *,
    grid: tuple[float, ...] = tuple(round(0.05 * i, 2) for i in range(1, 21)),
) -> dict[str, Any]:
    """Choose the information cost maximizing stop-task agreement (0/1) on a
    frozen calibration set. Ties are broken toward the smallest cost (favours
    the living/continue direction, i.e. sensitivity). Returns the grid search
    result (used to report the calibration curve plus the chosen value)."""
    best_cost, best_score, curve = grid[0], -1.0, []
    for cost in grid:
        agree = 0
        for gaps, gold_living in cases:
            agree += int(decide_living_v2(gaps, info_cost=cost)["living"] == bool(gold_living))
        score = agree / len(cases)
        curve.append({"info_cost": cost, "agreement": round(score, 4)})
        if score > best_score:
            best_score, best_cost = score, cost
    return {"info_cost": best_cost, "calibration_agreement": round(best_score, 4),
            "curve": curve, "n_calibration_cases": len(cases)}


def calibrate_living_balanced(
    cal_inputs: list[dict[str, Any]],
    *,
    cost_grid: tuple[float, ...] = tuple(round(0.05 + 0.05 * i, 2) for i in range(0, 20)),
    fresh_grid: tuple[float, ...] = (0.70, 0.85, 0.95),
    graph_grid: tuple[float, ...] = (0.75, 0.85, 0.95),
    node_grid: tuple[float, ...] = (0.60, 0.75),
    hetero_grid: tuple[float, ...] = (0.75, 0.85),
) -> dict[str, Any]:
    """Calibrate the EVPI layer (information cost + gain table) on a frozen
    split by BALANCED accuracy (mean of living-recall and non-living specificity),
    so a majority of non-living cases cannot dominate the objective. Each cal
    input is {"landscape": ..., "profile": ..., "gold_living": ...}."""
    best = None
    best_score = -1.0
    results: list[dict[str, Any]] = []
    for cost in cost_grid:
        for fresh in fresh_grid:
            for graph in graph_grid:
                for node in node_grid:
                    for hetero in hetero_grid:
                        gains = {"freshness": fresh, "graph_thin": graph,
                                 "graph_ok": max(0.30, graph - 0.45), "node": node,
                                 "hetero_hi": hetero, "hetero_lo": max(0.40, hetero - 0.30)}
                        tp = fp = tn = fn = 0
                        for c in cal_inputs:
                            gaps = landscape_gaps(c["landscape"], c["profile"], gains=gains)
                            pred = decide_living_v2(gaps, info_cost=cost)["living"]
                            gol = bool(c["gold_living"])
                            tp += int(pred and gol); fp += int(pred and not gol)
                            tn += int(not pred and not gol); fn += int(not pred and gol)
                        rec = tp / (tp + fn) if (tp + fn) else 1.0
                        spec = tn / (tn + fp) if (tn + fp) else 1.0
                        score = (rec + spec) / 2
                        results.append({"info_cost": cost, "freshness_gain": fresh,
                                        "graph_thin_gain": graph, "node_gain": node,
                                        "hetero_hi_gain": hetero,
                                        "balanced_acc": round(score, 4),
                                        "living_recall": round(rec, 4),
                                        "nonliving_specificity": round(spec, 4)})
                        if score > best_score:
                            best_score = score
                            best = results[-1]
    return {"best": best, "n_searched": len(results),
            "n_calibration_cases": len(cal_inputs),
            "calibration_balanced_acc": best_score}
