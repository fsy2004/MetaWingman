#!/usr/bin/env python3
"""Phase-2 method evidence: which new methods actually help (keep/drop test).

Measures on OOD corpora (holdout/large/living), no tuning:
  * design_search (ToT-style) vs v2.2 baseline: design agreement delta (paired CI);
  * step_compliance (AgentIF CSR/ISR style): per-stage rate + full-flow rate;
  * error_taxonomy (MAST-adapted): category distribution of remaining errors.
Oracle diagnosis lives in scripts/oracle_diagnosis_v2.py (results read here).

Rule (user directive): methods with no measured gain are reported as such and
are eligible for removal; only the auditable/verification semantics may remain.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from metawingman.agent.decision_core import derive_design_decision_v2  # noqa: E402
from metawingman.agent.design_search import search as design_search  # noqa: E402
from metawingman.agent.error_taxonomy import aggregate  # noqa: E402
from metawingman.agent.poolability_guard import calibrate_dimension_guard  # noqa: E402
from metawingman.agent.step_compliance import check_flow  # noqa: E402
from metawingman.scripts.metawingman_core.design_selection import SYNTHESIS_ROUTES  # noqa: E402
from metawingman.training.method_trace_normalizer import normalize_gold_trace  # noqa: E402
from run_fidelity_real import build_agent_input  # noqa: E402

RES = _REPO_ROOT / "research"
V2_KEYS = ("intervention_arm_count", "comparator_count", "has_reference_standard",
           "has_prediction_model", "outcome_measure_type", "design_type_hint",
           "effect_measure_type", "analysis_unit", "conditioning_set",
           "population_description", "time_horizon")
SEEDS = [20260826, 20260827, 20260828]
N_BOOT = 2000


def load_gold(name: str):
    rows = [json.loads(l) for l in (RES / f"method-trace-{name}-signal-v2.jsonl").read_text(
        encoding="utf-8").splitlines() if l.strip()]
    return [g for g in (normalize_gold_trace(r) for r in rows) if g]


def main() -> int:
    dev = load_gold("gold")
    cal = [{**{k: g["signal"].get(k) for k in V2_KEYS}, "n_nodes_assessed": True,
            "profile_hint": g["design_selection"],
            "estimand_aligned": g["design_selection"] not in ("", "structured_no_pooling"),
            "is_pooling_misleading": not bool(g.get("poolable", True))} for g in dev]
    guard_model = calibrate_dimension_guard(cal, alpha=0.10, delta=0.10)

    out: dict = {"scope": ("phase-2 method evidence (keep/drop); "
                           "no tuning; gains reported honestly")}
    for name in ("holdout", "large", "living"):
        cases = load_gold(name)
        base_oks: list[int] = []
        sr_oks: list[int] = []
        flow = []
        err_cases = []
        for g in cases:
            sig = {k: v for k, v in (g["signal"] or {}).items() if k != "living_or_update"}
            q, landscape = build_agent_input(sig)
            base = derive_design_decision_v2(q, landscape,
                                             guard_signal={k: g["signal"].get(k) for k in V2_KEYS},
                                             guard_model=guard_model, info_cost=0.70)
            ok_b = int(base.profile == g["design_selection"])
            base_oks.append(ok_b)
            s = design_search({k: g["signal"].get(k) for k in V2_KEYS}, base.profile,
                              gold=None, breadth=3)
            sr_oks.append(int(s.profile == g["design_selection"]))
            # step compliance (AgentIF-style) on the decision objects
            cert = {"primitives": "x", "hypothesis": "h", "falsifier": "f",
                    "mechanism_model": "m", "minimal_decisive_test": "d",
                    "failure_update": "u"}
            fl = check_flow(cert,
                            {"profile": base.profile,
                             "identification_assumption": base.identification_assumption,
                             "synthesis_route": base.synthesis_route},
                            {"passes": base.risk_guard["passes"],
                             "guarantee": base.risk_guard.get("guarantee", ""),
                             "alpha": base.risk_guard.get("alpha")},
                            {"living": base.living,
                             "stop_rule": base.stop_rule})
            flow.append(fl)
            if base.profile != g["design_selection"]:
                err_cases.append({"case_id": g["case_id"], "gold_profile": g["design_selection"],
                                  "agent_profile": base.profile,
                                  "dimensions": {"design_selection": 0.0},
                                  "agent_poolable": bool(base.risk_guard["passes"]),
                                  "gold_poolable": bool(g.get("poolable", True)),
                                  "unknown_dimensions": []})
        n = len(cases)
        base_a = round(sum(base_oks) / n, 4)
        sr_a = round(sum(sr_oks) / n, 4)
        v_base = np.array(base_oks, dtype=float)
        v_sr = np.array(sr_oks, dtype=float)
        # paired bootstrap CI on search-minus-baseline
        cis = []
        for seed in SEEDS:
            rng = np.random.default_rng(seed)
            draws = np.empty(N_BOOT)
            for i in range(N_BOOT):
                ii = rng.integers(0, n, size=n)
                draws[i] = (v_sr[ii] - v_base[ii]).mean()
            cis.append([float(x) for x in np.percentile(draws, [2.5, 97.5])])
        out[name] = {
            "n": n,
            "baseline_design_agreement": base_a,
            "design_search_agreement": sr_a,
            "delta_search_minus_baseline": round(sr_a - base_a, 4),
            "delta_ci95": [round(min(c[0] for c in cis), 4), round(max(c[1] for c in cis), 4)],
            "step_compliance": {
                "mean_per_stage_rate": round(float(np.mean([f["per_stage_rate"] for f in flow])), 4),
                "full_flow_rate": round(float(np.mean([f["full_flow_rate"] for f in flow])), 4),
                "per_stage_ok_rates": {
                    s["stage"]: round(float(np.mean([f["checks"][i]["ok"] for f in flow])), 4)
                    for i, s in enumerate(flow[0]["checks"])}},
            "error_taxonomy": aggregate(err_cases),
        }
    (RES / "method-phase2-evidence.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(out, indent=2)[:3600])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
