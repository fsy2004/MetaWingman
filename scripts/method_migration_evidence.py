#!/usr/bin/env python3
"""Evidence for the method-migration layer (v2.3 modules):
  1) question certificate completeness + hard gate outcome;
  2) risk controller three-action distribution;
  3) debate director verdict distribution + swap consistency;
  4) precedent store retrieval diagnostics;
  5) budget allocator allocation curve + monotonicity property.
Every module cites its source (docstring); this script only MEASURES, it does
not tune. Deposit: research/method-migration-evidence.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from metawingman.agent.budget_allocator import allocate, compare_budgeting  # noqa: E402
from metawingman.agent.debate_director import debate, stability  # noqa: E402
from metawingman.agent.poolability_guard import calibrate_dimension_guard  # noqa: E402
from metawingman.agent.decision_core import derive_design_decision_v2  # noqa: E402
from metawingman.agent.precedent_store import PrecedentStore  # noqa: E402
from metawingman.agent.question_certificate import (  # noqa: E402
    build_certificate, gate)
from metawingman.agent.risk_controller import RiskController  # noqa: E402
from metawingman.scripts.metawingman_core.design_selection import derive_review_design  # noqa: E402
from metawingman.training.method_trace_normalizer import normalize_gold_trace  # noqa: E402
from run_fidelity_real import build_agent_input  # noqa: E402

RES = _REPO_ROOT / "research"
V2_KEYS = ("intervention_arm_count", "comparator_count", "has_reference_standard",
           "has_prediction_model", "outcome_measure_type", "design_type_hint",
           "effect_measure_type", "analysis_unit", "conditioning_set",
           "population_description", "time_horizon")


def load_gold(name: str):
    rows = [json.loads(l) for l in (RES / f"method-trace-{name}-signal-v2.jsonl").read_text(
        encoding="utf-8").splitlines() if l.strip()]
    return [g for g in (normalize_gold_trace(r) for r in rows) if g]


def main() -> int:
    dev = load_gold("gold")
    hold = load_gold("holdout")
    large = load_gold("large")
    living = load_gold("living")
    out: dict = {"scope": "method-migration layer v2.3 evidence (no tuning; sources cited in module docstrings)",
                 "corpora": {}}

    cal = [{**{k: g["signal"].get(k) for k in V2_KEYS},
            "n_nodes_assessed": True,
            "profile_hint": g["design_selection"],
            "estimand_aligned": g["design_selection"] not in ("", "structured_no_pooling"),
            "is_pooling_misleading": not bool(g.get("poolable", True))} for g in dev]
    guard_model = calibrate_dimension_guard(cal, alpha=0.10, delta=0.10)

    # precedent store: dev-40 only (family-isolated)
    store = PrecedentStore(capacity=64)
    for g in dev:
        store.register({k: g["signal"].get(k) for k in V2_KEYS},
                       g["design_selection"], bool(g.get("poolable", True)),
                       bool(g.get("living_review", False)))
    controller = RiskController(tau_accept=0.1296)

    for name, cases in (("holdout", hold), ("large", large), ("living", living)):
        cert_stats = {"burned_fields": [], "gate_passed": 0, "soft_hit": 0, "n": 0}
        risk_actions = {"accept": 0, "audit": 0, "abstain": 0}
        debates = []
        allocs = []
        prec_rows = []
        for g in cases:
            sig = {k: v for k, v in (g["signal"] or {}).items() if k != "living_or_update"}
            q, landscape = build_agent_input(sig)
            d = derive_design_decision_v2(q, landscape,
                                          guard_signal={k: g["signal"].get(k) for k in V2_KEYS},
                                          guard_model=guard_model, info_cost=0.70)
            # 1) certificate
            cert = build_certificate(q, landscape, d.to_dict() if hasattr(d, "to_dict") else {
                "profile": d.profile, "estimand": d.estimand,
                "decision_tension": d.decision_tension,
                "risk_guard": d.risk_guard.to_dict(),
                "minimal_decisive_question": d.minimal_decisive_question})
            gv = gate(cert)
            cert_stats["n"] += 1
            cert_stats["gate_passed"] += int(gv["passed"])
            cert_stats["soft_hit"] += int(bool(gv["soft_boundary_hints"]))
            for f in gv["failed_hard"]:
                cert_stats["burned_fields"].append(f)
            # 2) risk controller
            verdict = controller.apply(d.risk_guard)
            risk_actions[verdict.action] += 1
            # 3) debate
            dbt = debate({k: g["signal"].get(k) for k in V2_KEYS} | {"profile_hint": d.profile},
                         {"profile": d.profile, "risk_guard": {"passes": d.risk_guard["passes"]}})
            debates.append(dbt.__dict__ if hasattr(dbt, "__dict__") else dbt)
            # 4) precedent retrieval
            top = store.retrieve({k: g["signal"].get(k) for k in V2_KEYS}, k=3)
            prec_rows.append({"top1_design": top[0]["design_selection"] if top else None,
                              "gold": g["design_selection"],
                              "top1_matches_gold": bool(top and top[0]["design_selection"] == g["design_selection"])})
            # 5) budget allocator
            allocs.append(allocate(d.risk_guard.safety_score if hasattr(d.risk_guard, "safety_score") else 0.13))
        from collections import Counter
        prec_diag = {"n": len(prec_rows),
                     "top1_matches_gold": sum(1 for r in prec_rows if r["top1_matches_gold"]),
                     "rate": round(sum(1 for r in prec_rows if r["top1_matches_gold"]) / len(prec_rows), 4)}
        alloc_counts = Counter(a["depth"] for a in allocs)
        deb_stab = stability(debates)
        out["corpora"][name] = {
            "certificate": {"n": cert_stats["n"], "gate_passed_rate": round(cert_stats["gate_passed"] / cert_stats["n"], 4),
                            "gate_passed": cert_stats["gate_passed"],
                            "soft_boundary_hint_rate": round(cert_stats["soft_hit"] / cert_stats["n"], 4),
                            "hard_failures": dict(Counter(cert_stats["burned_fields"]))},
            "risk_controller": risk_actions,
            "debate": deb_stab,
            "precedent_retrieval": prec_diag,
            "budget_allocator": {"depth_counts": dict(alloc_counts),
                                 "rates": {k: round(v / len(allocs), 4) for k, v in alloc_counts.items()}},
        }
    (RES / "method-migration-evidence.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(out, indent=2)[:3500])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
