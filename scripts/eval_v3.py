#!/usr/bin/env python3
"""v3 judgment-layer evaluation + scale curve (n=40 / 196 / 601).

Same rule (v2.2, guard calibrated on dev-40, EVPI conservative default),
same strict metrics; the scale curve uses the archived per-case totals.
Outputs research/fidelity-v3-summary.json + scale-curve.json.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from metawingman.agent.decision_core import (
    IDENTIFICATION_ASSUMPTIONS, derive_design_decision_v2)
from metawingman.agent.poolability_guard import calibrate_dimension_guard, clopper_pearson_upper
from metawingman.scripts.metawingman_core.design_selection import SYNTHESIS_ROUTES
from metawingman.training.method_trace_fidelity import WEIGHTS, fidelity
from metawingman.training.method_trace_normalizer import normalize_gold_trace
from run_fidelity_real import build_agent_input

RES = _REPO_ROOT / "research"
SEEDS = [20260826, 20260827, 20260828]
N_BOOT = 2000
V2_KEYS = ("intervention_arm_count", "comparator_count", "has_reference_standard",
           "has_prediction_model", "outcome_measure_type", "design_type_hint",
           "effect_measure_type", "analysis_unit", "conditioning_set",
           "population_description", "time_horizon")


def multi_ci(values: np.ndarray) -> dict:
    out = []
    for seed in SEEDS:
        rng = np.random.default_rng(seed)
        n = len(values)
        draws = np.empty(N_BOOT)
        for i in range(N_BOOT):
            ii = rng.integers(0, n, size=n)
            draws[i] = values[ii].mean()
        out.append([float(x) for x in np.percentile(draws, [2.5, 97.5])])
    return {"mean": round(float(values.mean()), 4),
            "ci95": [round(min(c[0] for c in out), 4), round(max(c[1] for c in out), 4)]}


def main() -> int:
    dev_rows = [json.loads(l) for l in (RES / "method-trace-gold-signal-v2.jsonl").read_text(
        encoding="utf-8").splitlines() if l.strip()]
    dev = [g for g in (normalize_gold_trace(r) for r in dev_rows) if g]
    cal = [{**{k: g["signal"].get(k) for k in V2_KEYS}, "n_nodes_assessed": True,
            "profile_hint": g["design_selection"],
            "estimand_aligned": g["design_selection"] not in ("", "structured_no_pooling"),
            "is_pooling_misleading": not bool(g.get("poolable", True))} for g in dev]
    guard_model = calibrate_dimension_guard(cal, alpha=0.10, delta=0.10)

    v3_rows = [json.loads(l) for l in (RES / "method-trace-v3-signal.jsonl").read_text(
        encoding="utf-8").splitlines() if l.strip()]
    v3 = [g for g in (normalize_gold_trace(r) for r in v3_rows) if g]
    print("v3 gold valid:", len(v3))

    per = []
    for g in v3:
        sig = {k: v for k, v in (g["signal"] or {}).items() if k != "living_or_update"}
        q, landscape = build_agent_input(sig)
        d = derive_design_decision_v2(q, landscape,
                                      guard_signal={k: g["signal"].get(k) for k in V2_KEYS},
                                      guard_model=guard_model, info_cost=0.70)
        tr = {"profile": d.profile,
              "identification_assumption": IDENTIFICATION_ASSUMPTIONS.get(d.profile, ""),
              "synthesis_route": SYNTHESIS_ROUTES.get(d.profile, ""),
              "living": d.living, "risk_guard": {"passes": d.risk_guard["passes"]}}
        s = fidelity(tr, g)
        per.append({"case_id": g["case_id"], "gold": g["design_selection"],
                    "agent": d.profile, "total": s.total, "dims": dict(s.dimensions)})
    totals = np.array([p["total"] for p in per])
    dims = {k: np.array([p["dims"][k] for p in per]) for k in WEIGHTS}
    from collections import Counter
    by = Counter(p["gold"] for p in per)
    acc_pool = sum(1 for p in per if p["dims"]["guard_consistency"] == 1.0)
    accepted = [(1 if p["dims"]["guard_consistency"] == 1.0 else 0) for p in per]
    # risk audit on v3 (accepted cases)
    acc = [p for p in per if p["dims"]["guard_consistency"] == 1.0 or True]
    # guard decision vs gold pooled directly
    pool_mismatch = sum(1 for p in per if (1.0 if (p["dims"]["guard_consistency"] == 1.0) else 0.0) != 1.0)
    summary = {
        "scope": "v3 judgment layer (601 reviews from the 12k asset; family-isolated; strict v2 protocol)",
        "n": len(per),
        "mean_fidelity": round(float(totals.mean()), 4),
        "mean_fidelity_ci": multi_ci(totals),
        "design_agreement": round(float(dims["design_selection"].mean()), 4),
        "pooling_agreement": round(float(dims["guard_consistency"].mean()), 4),
        "stop_agreement": round(float(dims["stop_decision"].mean()), 4),
        "three_task_mean": round(float((dims["design_selection"] + dims["guard_consistency"]
                                        + dims["stop_decision"]).mean() / 3), 4),
        "three_task_ci": multi_ci((dims["design_selection"] + dims["guard_consistency"]
                                   + dims["stop_decision"]) / 3),
        "profile_counts": dict(by),
        "per_case": per,
    }
    (RES / "fidelity-v3-summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    # scale curve: combine archived holdout(39)/large(196) + v3(601)
    curve = []
    for name, count in (("holdout_39", 39), ("large_196", 196), ("v3_601", len(per))):
        if name == "v3_601":
            vals = totals
        else:
            f = json.loads((RES / f"fidelity-v2-{name.split('_')[0]}.json").read_text(encoding="utf-8"))
            vals = np.array([c["total"] for c in f["per_case"]])
        curve.append({"stage": name, "n": len(vals), **multi_ci(vals)})
    (RES / "scale-curve.json").write_text(json.dumps({"scope": "scale curve (40/196/601)",
                                                      "points": curve}, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(curve, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
