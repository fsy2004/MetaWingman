#!/usr/bin/env python3
"""ABLATION: measure the marginal contribution of each decision-object component.

Full (estimand-first + pooling guard + EVPI stop) vs dropping one component:
  no_guard      - ignore the poolability guard (never force a narrative/no-pool)
  no_evpi       - disable info-value stop (living always False)
  no_estimand   - drop the identification assumption (estimand-first gone)

Run on OOD holdout against the real published-meta gold (strict, no fallback).
The drop in fidelity vs full = that component's marginal contribution.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from metawingman.agent.decision_core import IDENTIFICATION_ASSUMPTIONS, derive_design_decision
from metawingman.scripts.metawingman_core.design_selection import SYNTHESIS_ROUTES, derive_review_design
from metawingman.training.method_trace_fidelity import aggregate_fidelity
from metawingman.training.method_trace_normalizer import normalize_gold_trace
from run_fidelity_real import build_agent_input

REPO = Path(__file__).resolve().parents[1]
SIGNAL = REPO / "research" / "method-trace-holdout-signal.jsonl"
OUT = REPO / "research" / "ablation-holdout.json"


def trace(profile, ident, route, living, passes):
    return {"profile": profile, "identification_assumption": ident,
            "synthesis_route": route, "living": living,
            "risk_guard": {"passes": passes}}


def main() -> int:
    rows = [json.loads(l) for l in SIGNAL.read_text(encoding="utf-8").splitlines() if l.strip()]
    gold_traces, variants = [], {k: [] for k in ("full", "no_guard", "no_evpi", "no_estimand")}
    for row in rows:
        gold = normalize_gold_trace(row)
        if gold is None:
            continue
        gold_traces.append(gold)
        q, l = build_agent_input(gold.get("signal") or {})
        full = derive_design_decision(q, l)
        base = derive_review_design(q, l)
        variants["full"].append(trace(full.profile, full.identification_assumption,
                                      full.synthesis_route, full.living, full.risk_guard["passes"]))
        # no_guard: use the base profile (never forced to narrative), guard always "poolable"
        variants["no_guard"].append(trace(base.profile,
                                          IDENTIFICATION_ASSUMPTIONS.get(base.profile, ""),
                                          SYNTHESIS_ROUTES.get(base.profile, ""),
                                          full.living, True))
        # no_evpi: disable info-value driven living/stop
        variants["no_evpi"].append(trace(full.profile, full.identification_assumption,
                                         full.synthesis_route, False, full.risk_guard["passes"]))
        # no_estimand: drop identification assumption (estimand-first gone)
        variants["no_estimand"].append(trace(full.profile, "",
                                             full.synthesis_route, full.living, full.risk_guard["passes"]))

    result = {}
    for name, agent in variants.items():
        agg = aggregate_fidelity(agent, gold_traces)
        result[name] = {"mean_fidelity": agg["mean_fidelity"],
                        "mean_dims": agg["mean_dimensions"]}
    full_m = result["full"]["mean_fidelity"]
    result["deltas"] = {name: full_m - result[name]["mean_fidelity"] for name in result if name != "full"}

    report = {"scope": "device-object ablation on OOD holdout (strict, no fallback)",
              "n": len(gold_traces), "variants": result}
    OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"n={len(gold_traces)}")
    for name, v in result.items():
        if name == "deltas":
            print("deltas (drop vs full):", {k: round(v, 4) for k, v in v.items()})
        else:
            print(f"  {name:<12} fidelity={v['mean_fidelity']:.4f}")
    print("wrote", OUT.name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
