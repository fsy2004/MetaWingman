#!/usr/bin/env python3
"""Real fidelity on an OUT-OF-DISTRIBUTION holdout: the 40 real published-meta
reviews (independent structure-signal extraction). The gold profile / pooled /
living decisions come from the paper's own method structure (independent, outcome
stripped). The agent sees ONLY the evidence-structure signal (arm count, reference
standard, prediction model, outcome unit) and must decide; we compare.

The design_selection dimension tends to be high because a sound agent *should*
infer the same design from the same real evidence structure — that is the point.
The guard_consistency (agent's risk-control pooling vs the reference's pooled)
and stop_decision (agent's EVPI living vs the reference's living) dimensions are
the genuinely discriminative ones, since the agent's guard/EVPI rules are not
copied from the reference.

Deterministic + offline given the extracted signals.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from metawingman.agent.decision_core import derive_design_decision
from metawingman.training.method_trace_normalizer import normalize_gold_trace
from metawingman.training.method_trace_fidelity import fidelity, aggregate_fidelity
from metawingman.scripts.metawingman_core.state_store import sha256_json

REPO = Path(__file__).resolve().parents[1]
SIGNAL = REPO / "research" / "method-trace-gold-signal.jsonl"
OUT = REPO / "research" / "method-trace-fidelity-real.json"


def build_agent_input(signal: dict) -> tuple[dict, dict]:
    """Construct the agent's question + landscape from the real evidence signal."""
    outcome = signal.get("outcome_measure_type")
    hint = str(signal.get("design_type_hint") or "").casefold()
    arms = int(signal.get("intervention_arm_count") or 0)
    comps = int(signal.get("comparator_count") or 0)
    q: dict = {}
    if outcome == "proportion":
        q["type"] = "prevalence"
    elif signal.get("has_reference_standard"):
        q["type"] = "diagnostic"; q["has_index_test_reference"] = True
    elif signal.get("has_prediction_model"):
        q["type"] = "prediction"; q["has_prediction_model"] = True
    elif hint == "exposure":
        q["type"] = "exposure"; q["is_public_health_exposure"] = True
    else:
        q["type"] = "intervention"; q["intervention_count"] = max(arms, comps)
    if signal.get("living_or_update"):
        q["is_living_or_update"] = True
    landscape = {
        "comparator_count": max(comps, arms) or None,
        "arms_per_study": arms or None,
        "has_reference_standard": bool(signal.get("has_reference_standard")),
        "has_prediction_model": bool(signal.get("has_prediction_model")),
        "outcome_unit": outcome,
        "is_update": bool(signal.get("living_or_update")),
        "n_nodes_assessed": True,
        "exposure_outcome_design": "observational" if hint == "exposure" else None,
    }
    return q, landscape


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--signal", default=str(SIGNAL))
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args()
    signal_path = Path(args.signal)
    out_path = Path(args.out)
    rows = [json.loads(l) for l in signal_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    gold_traces, agent_traces, per_case = [], [], []
    skipped = 0
    for row in rows:
        gold = normalize_gold_trace(row)
        if gold is None:
            skipped += 1
            continue
        signal = gold.get("signal") or {}
        q, landscape = build_agent_input(signal)
        d = derive_design_decision(q, landscape)
        agent_trace = {
            "profile": d.profile,
            "identification_assumption": d.identification_assumption,
            "synthesis_route": d.synthesis_route,
            "living": d.living,
            "risk_guard": {"passes": d.risk_guard["passes"]},
        }
        score = fidelity(agent_trace, gold)
        agent_traces.append(agent_trace)
        gold_traces.append(gold)
        per_case.append({
            "case_id": gold["case_id"], "agent_profile": d.profile,
            "gold_profile": gold["design_selection"],
            "fidelity_total": score.total, "dimensions": score.dimensions,
            "agent_living": d.living, "gold_living": gold["living_review"],
            "agent_poolable": d.risk_guard["passes"], "gold_poolable": gold["poolable"],
        })
    agg = aggregate_fidelity(agent_traces, gold_traces)
    report = {
        "scope": "real fidelity on 40 real published-meta reviews (independent structure signal; outcomes stripped)",
        "n": agg["n"], "skipped": skipped,
        "mean_fidelity": agg["mean_fidelity"],
        "mean_dimensions": agg["mean_dimensions"],
        "verdict": agg["verdict"],
        "per_case": per_case,
    }
    report["receipt_sha256"] = sha256_json(report)
    out_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print("=== REAL fidelity vs independent published-meta structure (outcomes stripped) ===")
    print(f"n={agg['n']}  skipped={skipped}  mean_fidelity={agg['mean_fidelity']:.3f}  verdict={agg['verdict']}")
    print("mean dimensions:")
    for k, v in agg["mean_dimensions"].items():
        print(f"  {k:<24} {v:.3f}")
    print(f"wrote {out_path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
