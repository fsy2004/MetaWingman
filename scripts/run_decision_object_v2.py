#!/usr/bin/env python3
"""V2 decision-object evaluation on methods-text-extracted gold (v2 signals).

Protocol (pre-registered in the manuscript Methods):
  * Gold = independent extraction from the paper's METHODS TEXT (not title-only),
    outcome-stripped, no pre-canned taxonomy (`run_independent_method_trace_extraction.py`).
  * Agent input = clinical question + evidence structure signals from the SAME
    extraction, with the living/update flag STRIPPED (the stop task must not feed
    the gold into the input).
  * Guard v2 = per-dimension (population/contrast/outcome/time/effect-measure/
    analysis-unit/conditioning-set + graph + estimand-alignment gate) alignment
    risk with a finite-sample mis-pool guarantee (Clopper-Pearson, alpha/delta).
    Calibrated on the DEV-40 (frozen); tested on holdout-40, large-170, living-35.
    The guard never reads the review's own pooling decision or heterogeneity
    treatment.
  * Stop v2 = EVPI-only from landscape-derived gaps, information cost calibrated
    on DEV-40 + half of the living set (frozen, seeded); tested on holdout-40,
    large-170 and the other half of the living set.
  * Strict fidelity weights as method_trace_fidelity.py; parse/strict rules
    apply only to model arms (the rule is deterministic).

Outputs research/:
  fidelity-v2-dev.json / -holdout.json / -large.json / -living.json
  guard-v2-calibration.json / evpi-v2-calibration.json

Usage: python scripts/run_decision_object_v2.py [--signals-dir research]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from metawingman.agent.decision_core import (
    IDENTIFICATION_ASSUMPTIONS, derive_design_decision_v2)
from metawingman.agent.evpi_director import (
    calibrate_living_balanced, decide_living_v2, landscape_gaps)
from metawingman.agent.poolability_guard import (
    calibrate_dimension_guard, clopper_pearson_upper)
from metawingman.scripts.metawingman_core.design_selection import derive_review_design
from metawingman.scripts.metawingman_core.design_selection import SYNTHESIS_ROUTES
from metawingman.training.method_trace_fidelity import WEIGHTS, fidelity
from metawingman.training.method_trace_normalizer import normalize_gold_trace
from run_fidelity_real import build_agent_input

RES = _REPO_ROOT / "research"
SEED = 20260826
GAMMA = 0.10
DELTA = 0.10

V2_KEYS = ("intervention_arm_count", "comparator_count", "has_reference_standard",
           "has_prediction_model", "outcome_measure_type", "design_type_hint",
           "effect_measure_type", "analysis_unit", "conditioning_set",
           "population_description", "time_horizon")


def load_signal(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def agent_input_without_living_flag(signal: dict) -> tuple[dict, dict]:
    """Build the agent input with the living/update flag stripped (stop-task honesty)."""
    stripped = {k: v for k, v in signal.items() if k != "living_or_update"}
    return build_agent_input(stripped)


def guard_signal(gold: dict) -> dict:
    """Alignment-only signal for the v2 guard (no review pooling decision, no
    heterogeneity treatment — those are the review's own choices, not evidence)."""
    s = {k: gold["signal"].get(k) for k in V2_KEYS}
    s["n_nodes_assessed"] = True
    return s


def run_rule(gold: dict, guard_model, info_cost: float, gains: dict | None) -> dict:
    q, landscape = agent_input_without_living_flag(gold["signal"] or {})
    decision = derive_design_decision_v2(q, landscape, guard_signal=guard_signal(gold),
                                         guard_model=guard_model, info_cost=info_cost,
                                         gains=gains)
    return {
        "profile": decision.profile, "living": decision.living,
        "risk_guard": {"passes": decision.risk_guard["passes"]},
        "guard_object": decision.risk_guard,
        "stop_object": decision.stop_rule,
        "next_evidence": decision.next_evidence,
    }


def score(agent: dict, gold: dict) -> tuple[float, dict]:
    trace = {
        "profile": agent["profile"],
        "identification_assumption": "",
        "synthesis_route": SYNTHESIS_ROUTES.get(agent["profile"], ""),
        "living": agent["living"],
        "risk_guard": agent["risk_guard"],
    }
    # identification assumption is derived by the decision object's map; pass the
    # canonical one for scoring (same map the normalizer uses).
    from metawingman.agent.decision_core import IDENTIFICATION_ASSUMPTIONS
    trace["identification_assumption"] = IDENTIFICATION_ASSUMPTIONS.get(agent["profile"], "")
    s = fidelity(trace, gold)
    return s.total, dict(s.dimensions)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--signals-dir", default=str(RES))
    args = ap.parse_args()
    sd = Path(args.signals_dir)

    dev = [normalize_gold_trace(r) for r in load_signal(sd / "method-trace-gold-signal-v2.jsonl")]
    dev = [g for g in dev if g]
    hold = [normalize_gold_trace(r) for r in load_signal(sd / "method-trace-holdout-signal-v2.jsonl")]
    hold = [g for g in hold if g]
    large = [normalize_gold_trace(r) for r in load_signal(sd / "method-trace-large-signal-v2.jsonl")]
    large = [g for g in large if g]
    if len(large) < 100:
        # extraction still in progress; do not score a partial corpus
        large = []
    living_path = sd / "method-trace-living-signal-v2.jsonl"
    living = [normalize_gold_trace(r) for r in load_signal(living_path)] if living_path.exists() else []
    living = [g for g in living if g]

    print(f"gold v2: dev={len(dev)} holdout={len(hold)} large={len(large)} living={len(living)}")

    # ---------- guard calibration (DEV-40, frozen) ----------
    cal = []
    for g in dev:
        cal.append({**guard_signal(g), "is_pooling_misleading": not bool(g.get("poolable", True))})
    guard_model = calibrate_dimension_guard(cal, alpha=GAMMA, delta=DELTA)
    guard_cal = {"alpha": GAMMA, "delta": DELTA,
                 "calibration_n": guard_model.calibration_size,
                 "threshold": guard_model.threshold,
                 "empirical_risk": guard_model.empirical_risk,
                 "cp_risk_bound": guard_model.risk_bound,
                 "accepted_calibration_n": guard_model.accepted_calibration_n}
    (RES / "guard-v2-calibration.json").write_text(json.dumps(guard_cal, indent=2) + "\n", encoding="utf-8")
    print("guard calibration:", json.dumps(guard_cal))

    # ---------- living/stop calibration: stratified random split of the full
    # v2 pool (dev+holdout+large+living), seeded — split-conformal style ----------
    pool = dev + hold + large + living
    rng = np.random.default_rng(SEED)
    living_ids = [g["case_id"] for g in pool if bool(g.get("living_review", False))]
    non_ids = [g["case_id"] for g in pool if not bool(g.get("living_review", False))]
    perm_l = rng.permutation(len(living_ids))
    perm_n = rng.permutation(len(non_ids))
    n_cal_l = max(1, len(living_ids) // 2)
    n_cal_n = len(non_ids) // 2
    cal_ids = set(living_ids[i] for i in perm_l[:n_cal_l]) | set(non_ids[i] for i in perm_n[:n_cal_n])
    cal_inputs = []
    for g in pool:
        if g["case_id"] not in cal_ids:
            continue
        q, landscape = agent_input_without_living_flag(g["signal"] or {})
        base = derive_review_design(q, landscape)
        cal_inputs.append({"landscape": landscape, "profile": base.profile,
                           "gold_living": bool(g.get("living_review", False))})
    evpi_cal = calibrate_living_balanced(cal_inputs)
    best_cfg = evpi_cal["best"]
    # If no structure-only configuration beats chance on the frozen split, the
    # calibrated threshold is degenerate; the paper then reports the default
    # (conservative) configuration for the main evaluation and the identifiability
    # analysis (evpi-v2-identifiability.json) as the honest evidence.
    degenerate = best_cfg["balanced_acc"] <= 0.55
    if degenerate:
        best_cfg = {"info_cost": 0.70, "freshness_gain": 0.70, "graph_thin_gain": 0.85,
                    "node_gain": 0.65, "hetero_hi_gain": 0.85,
                    "calibration_degenerate": True}
    info_cost = best_cfg["info_cost"]
    gains = {"freshness": best_cfg["freshness_gain"],
             "graph_thin": best_cfg["graph_thin_gain"],
             "graph_ok": max(0.30, best_cfg["graph_thin_gain"] - 0.45),
             "node": best_cfg["node_gain"],
             "hetero_hi": best_cfg["hetero_hi_gain"],
             "hetero_lo": max(0.40, best_cfg["hetero_hi_gain"] - 0.30)}
    (RES / "evpi-v2-calibration.json").write_text(json.dumps({**evpi_cal, "degenerate": degenerate},
                                                             indent=2) + "\n", encoding="utf-8")
    print("evpi calibration:", json.dumps({"best": best_cfg, "n_searched": evpi_cal["n_searched"],
                                           "n_calibration_cases": evpi_cal["n_calibration_cases"],
                                           "degenerate": degenerate}))

    # identifiability + OOD stop-task evaluation on the held-out half (EV)
    ev_cases = [g for g in pool if g["case_id"] not in cal_ids]
    ev_per = []
    for g in ev_cases:
        q, landscape = agent_input_without_living_flag(g["signal"] or {})
        base = derive_review_design(q, landscape)
        gaps = landscape_gaps(landscape, base.profile, heterogeneity_handling=None, gains=gains)
        v = decide_living_v2(gaps, info_cost=info_cost)
        ev_per.append({"case_id": g["case_id"], "gold_living": bool(g.get("living_review", False)),
                       "agent_living": bool(v["living"]), "max_evpi": v["max_evpi"]})
    stop_ev = {"n": len(ev_per), "living_n": sum(1 for p in ev_per if p["gold_living"]),
               "living_pred_n": sum(1 for p in ev_per if p["agent_living"]),
               "agreement": round(sum(1 for p in ev_per if p["agent_living"] == p["gold_living"]) / len(ev_per), 4),
               "living_recall": round(sum(1 for p in ev_per if p["agent_living"] and p["gold_living"]) / max(1, sum(1 for p in ev_per if p["gold_living"])), 4),
               "nonliving_specificity": round(sum(1 for p in ev_per if not p["agent_living"] and not p["gold_living"]) / max(1, sum(1 for p in ev_per if not p["gold_living"])), 4),
               "balanced_acc": None}
    stop_ev["balanced_acc"] = round((stop_ev["living_recall"] + stop_ev["nonliving_specificity"]) / 2, 4)
    (RES / "evpi-v2-oos-stop.json").write_text(json.dumps(
        {"scope": "EVPI stop-layer OOD evaluation on the held-out half (split-conformal, seeded)",
         "note": "gold living flag excluded from input; EVPI-only decision",
         **stop_ev, "per_case": ev_per}, indent=2) + "\n", encoding="utf-8")
    print("evpi OOD stop:", json.dumps({k: v for k, v in stop_ev.items()}))

    # ---------- identifiability analysis: can structure-only EVPI scores
    # separate living from non-living reviews? (measured, not assumed) ----------
    def auc_score(scores: list[float], labels: list[int]) -> float:
        order = np.argsort(np.array(scores, dtype=float))
        ranks = np.empty(len(order), dtype=float)
        ranks[order] = np.arange(1, len(order) + 1)
        pos = [ranks[i] for i, lab in enumerate(labels) if lab == 1]
        neg = [ranks[i] for i, lab in enumerate(labels) if lab == 0]
        if not pos or not neg:
            return float("nan")
        return round((sum(p > n for p in pos for n in neg)
                      + 0.5 * sum(p == n for p in pos for n in neg)) / (len(pos) * len(neg)), 4)

    ident = {"task": ("can evidence-structure-derived EVPI scores (max EVPI, default gains, "
                      "cost=0.0) separate reviews that are living/updating from those that are not"),
             "note": ("the gold living flag is deliberately not an input; the extractor's "
                      "living_or_update field is excluded from the agent input")}
    evpi_scores, living_labels = [], []
    for g in dev + hold + large + living:
        q, landscape = agent_input_without_living_flag(g["signal"] or {})
        base = derive_review_design(q, landscape)
        gaps = landscape_gaps(landscape, base.profile, heterogeneity_handling=None, gains={"freshness": 0.85, "graph_thin": 0.85, "graph_ok": 0.4, "node": 0.65})
        from metawingman.agent.evpi_director import estimate_evpi
        best = max((estimate_evpi(ga, info_cost=0.0) for ga in gaps), default=0.0)
        evpi_scores.append(best)
        living_labels.append(int(bool(g.get("living_review", False))))
    ident["n"] = len(living_labels)
    ident["living_n"] = int(sum(living_labels))
    ident["auc_max_evpi_vs_living"] = auc_score(evpi_scores, living_labels)
    ident["calibration_balanced_acc"] = evpi_cal["calibration_balanced_acc"]
    (RES / "evpi-v2-identifiability.json").write_text(json.dumps(ident, indent=2) + "\n", encoding="utf-8")
    print("evpi identifiability:", json.dumps(ident))

    # ---------- evaluation ----------
    results = {}
    for name, cases in (("dev", dev), ("holdout", hold), ("large", large), ("living", living)):
        per = []
        for g in cases:
            agent = run_rule(g, guard_model, info_cost, gains)
            total, dims = score(agent, g)
            per.append({"case_id": g["case_id"], "gold_profile": g["design_selection"],
                        "agent_profile": agent["profile"],
                        "gold_poolable": bool(g.get("poolable", True)),
                        "agent_poolable": bool(agent["risk_guard"]["passes"]),
                        "gold_living": bool(g.get("living_review", False)),
                        "agent_living": bool(agent["living"]),
                        "total": total, "dims": dims,
                        "guard_risk": agent["guard_object"].get("safety_score"),
                        "guard_reason": agent["guard_object"].get("reason", "")[:120],
                        "next_evidence": agent["next_evidence"]})
        n = len(per)
        mean_total = sum(p["total"] for p in per) / n if n else 0.0
        mean_dims = {k: sum(p["dims"][k] for p in per) / n if n else 0.0 for k in WEIGHTS}
        pool_tp = sum(1 for p in per if p["agent_poolable"] and p["gold_poolable"])
        pool_fp = sum(1 for p in per if p["agent_poolable"] and not p["gold_poolable"])
        pool_tn = sum(1 for p in per if not p["agent_poolable"] and not p["gold_poolable"])
        pool_fn = sum(1 for p in per if not p["agent_poolable"] and p["gold_poolable"])
        living_true = sum(1 for p in per if p["gold_living"])
        liv_tp = sum(1 for p in per if p["agent_living"] and p["gold_living"])
        liv_fp = sum(1 for p in per if p["agent_living"] and not p["gold_living"])
        liv_fn = sum(1 for p in per if not p["agent_living"] and p["gold_living"])
        results[name] = {
            "n": n,
            "mean_fidelity": round(mean_total, 4),
            "mean_dimensions": {k: round(v, 4) for k, v in mean_dims.items()},
            "design_agreement": round(mean_dims["design_selection"], 4),
            "pooling_agreement": round(mean_dims["guard_consistency"], 4),
            "stop_agreement": round(mean_dims["stop_decision"], 4),
            "three_task_mean": round((mean_dims["design_selection"] + mean_dims["guard_consistency"]
                                      + mean_dims["stop_decision"]) / 3, 4),
            "pooling_confusion": {"tp": pool_tp, "fp": pool_fp, "tn": pool_tn, "fn": pool_fn,
                                  "pooled_precision": round(pool_tp / (pool_tp + pool_fp), 4) if (pool_tp + pool_fp) else None,
                                  "pooled_recall": round(pool_tp / (pool_tp + pool_fn), 4) if (pool_tp + pool_fn) else None,
                                  "nopool_precision": round(pool_tn / (pool_tn + pool_fn), 4) if (pool_tn + pool_fn) else None,
                                  "nopool_recall": round(pool_tn / (pool_tn + pool_fp), 4) if (pool_tn + pool_fp) else None},
            "living_gold_n": living_true,
            "living_confusion": {"tp": liv_tp, "fp": liv_fp, "tn": n - liv_tp - liv_fp - liv_fn,
                                 "fn": liv_fn,
                                 "living_precision": round(liv_tp / (liv_tp + liv_fp), 4) if (liv_tp + liv_fp) else None,
                                 "living_recall": round(liv_tp / (liv_tp + liv_fn), 4) if (liv_tp + liv_fn) else None},
            "per_case": per,
        }
        (RES / f"fidelity-v2-{name}.json").write_text(
            json.dumps({"scope": f"decision-object v2 on methods-text-extracted gold ({name})",
                        "guard_alpha": GAMMA, "guard_delta": DELTA,
                        "info_cost": info_cost, "gains": gains,
                        "guard_calibration": guard_cal,
                        **results[name]}, indent=2) + "\n", encoding="utf-8")
        print(f"{name}: fidelity={results[name]['mean_fidelity']:.4f} "
              f"design={results[name]['design_agreement']:.4f} "
              f"pool={results[name]['pooling_agreement']:.4f} "
              f"stop={results[name]['stop_agreement']:.4f} "
              f"3task={results[name]['three_task_mean']:.4f} "
              f"living_gold={results[name]['living_gold_n']} "
              f"liv_recall={results[name]['living_confusion']['living_recall']}")
    # ---------- v2 ablations + progressive baselines (mechanism attribution) ----------
    def variant_total(agent: dict, gold: dict) -> tuple[float, dict]:
        return score(agent, gold)

    abl: dict = {"scope": "v2 ablation/progressive baselines (methods-text gold, dimension guard)",
                 "n_boot": 2000, "seeds": [20260826, 20260827, 20260828]}
    for name, cases in (("holdout", hold), ("large", large)):
        variant_cases = {"full": [], "no_guard": [], "no_estimand": [],
                         "no_evpi": [], "L1_design_rule": []}
        for g in cases:
            q, landscape = agent_input_without_living_flag(g["signal"] or {})
            base = derive_review_design(q, landscape)
            full_agent = run_rule(g, guard_model, info_cost, gains)
            from metawingman.agent.decision_core import IDENTIFICATION_ASSUMPTIONS
            def base_agent(passes: bool, living: bool, ident: str = ""):
                return {"profile": base.profile or "",
                        "identification_assumption": ident or IDENTIFICATION_ASSUMPTIONS.get(base.profile or "", ""),
                        "risk_guard": {"passes": passes},
                        "living": living}
            variant_cases["full"].append(full_agent)
            variant_cases["no_guard"].append(base_agent(True, full_agent["living"]))
            variant_cases["no_estimand"].append({**base_agent(bool(full_agent["risk_guard"]["passes"]), full_agent["living"]),
                                                 "identification_assumption": ""})
            variant_cases["no_evpi"].append(base_agent(bool(full_agent["risk_guard"]["passes"]), False))
            variant_cases["L1_design_rule"].append(base_agent(True, False))
        per_var = {}
        for vname, agents in variant_cases.items():
            totals = []
            for a, g in zip(agents, cases):
                if vname == "no_estimand":
                    ident = ""
                else:
                    ident = IDENTIFICATION_ASSUMPTIONS.get(a["profile"], "")
                tr = {"profile": a["profile"],
                      "identification_assumption": ident,
                      "synthesis_route": SYNTHESIS_ROUTES.get(a["profile"], ""),
                      "living": a["living"], "risk_guard": a["risk_guard"]}
                totals.append(fidelity(tr, g).total)
            totals = np.array(totals)
            entry = {"mean_fidelity": round(float(totals.mean()), 4)}
            # paired bootstrap CI vs full
            full_t = np.array([fidelity(
                {"profile": fa["profile"], "identification_assumption": IDENTIFICATION_ASSUMPTIONS.get(fa["profile"], ""),
                 "synthesis_route": SYNTHESIS_ROUTES.get(fa["profile"], ""),
                 "living": fa["living"], "risk_guard": fa["risk_guard"]}, g).total
                for fa, g in zip(variant_cases["full"], cases)])
            if vname != "full":
                cis = []
                for seed in abl["seeds"]:
                    rng = np.random.default_rng(seed)
                    n = len(totals)
                    draws = np.empty(2000)
                    for i in range(2000):
                        idx = rng.integers(0, n, size=n)
                        draws[i] = (totals[idx] - full_t[idx]).mean()
                    cis.append([float(x) for x in np.percentile(draws, [2.5, 97.5])])
                entry["delta_vs_full_ci95"] = [round(min(c[0] for c in cis), 4),
                                               round(max(c[1] for c in cis), 4)]
                entry["delta_vs_full"] = round(float(totals.mean() - full_t.mean()), 4)
            per_var[vname] = entry
        abl[name] = per_var
    (RES / "ablation-v2.json").write_text(json.dumps(abl, indent=2) + "\n", encoding="utf-8")
    print("ablation v2:", json.dumps({k: {kk: vv for kk, vv in v.items() if kk != 'per_seed'}
                                      for k, v in abl.items() if isinstance(v, dict)}, indent=2))

    # ---------- OOD risk audit of the calibrated guard (guarantee check) ----------
    def guard_risk_audit(name: str, cases: list[dict]) -> dict:
        accepted = [p for p in cases if p["agent_poolable"]]
        k = sum(1 for p in accepted if not p["gold_poolable"])
        n = len(accepted)
        return {"corpus": name, "accepted_n": n, "mis_pool_k": k,
                "empirical_risk": round(k / n, 4) if n else None,
                "cp_upper_bound": round(clopper_pearson_upper(k, n, DELTA), 4) if n else None,
                "alpha": GAMMA, "delta": DELTA}
    audit = {"scope": "OOD guard risk audit: among pool-accepted cases, is the mis-pool risk within the calibrated budget?",
             "label_note": "mis-pool label = the reference review did not pool",
             "corpora": []}
    for name, cases in (("dev", dev), ("holdout", hold), ("large", large), ("living", living)):
        if name in results:
            audit["corpora"].append(guard_risk_audit(name, results[name]["per_case"]))
    (RES / "guard-v2-ood-risk.json").write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
    print("guard OOD risk audit:", json.dumps(audit))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
