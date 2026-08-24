#!/usr/bin/env python3
"""Fidelity benchmark: agent's method trajectory vs the real published-meta
expert reference, with outcomes stripped. The fidelity score is the training
reward signal for the E-R-V agent (higher fidelity = closer to a seasoned
top-journal systematic-review author).

Deterministic and offline. Output: research/method-trace-fidelity-v1.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from metawingman.agent.decision_core import derive_design_decision
from metawingman.benchmark.gold_loader import load_gold
from metawingman.training.method_trace_fidelity import aggregate_fidelity, fidelity
from metawingman.scripts.metawingman_core.state_store import sha256_json

REPO = Path(__file__).resolve().parents[1]
GOLD = REPO / "research" / "design-selection-gold-v1.json"
REFERENCE = REPO / "research" / "method-trace-gold-v1.json"
OUT = REPO / "research" / "method-trace-fidelity-v1.json"


def main() -> int:
    gold = load_gold(GOLD)
    references = {r["case_id"]: r for r in json.loads(REFERENCE.read_text(encoding="utf-8"))["references"]}

    agent_traces, gold_traces, per_case = [], [], []
    for case in gold:
        d = derive_design_decision(case.question, case.landscape)
        agent_trace = {
            "profile": d.profile,
            "identification_assumption": d.identification_assumption,
            "synthesis_route": d.synthesis_route,
            "living": d.living,
            "risk_guard": {"passes": d.risk_guard["passes"]},
        }
        gold_trace = references[case.case_id]
        score = fidelity(agent_trace, gold_trace)
        agent_traces.append(agent_trace)
        gold_traces.append(gold_trace)
        per_case.append({
            "case_id": case.case_id,
            "agent_profile": d.profile,
            "reference_profile": gold_trace["design_selection"],
            "fidelity_total": score.total,
            "dimension": score.dimensions,
            "verdict": score.verdict,
        })

    agg = aggregate_fidelity(agent_traces, gold_traces)
    report = {
        "scope": "fidelity of agent method trajectory vs real published-meta expert reference (outcomes stripped)",
        "reference_type": "published_expert_reference",
        "n": agg["n"],
        "mean_fidelity": agg["mean_fidelity"],
        "mean_dimensions": agg["mean_dimensions"],
        "verdict": agg["verdict"],
        "per_case": per_case,
    }
    report["receipt_sha256"] = sha256_json(report)
    OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print("=== fidelity (agent vs real top-journal published meta; outcomes stripped) ===")
    print(f"cases: {agg['n']}   mean_fidelity: {agg['mean_fidelity']:.3f}   verdict: {agg['verdict']}")
    print("mean dimension fidelity: " + ", ".join(f"{k}={v:.3f}" for k, v in agg["mean_dimensions"].items()))
    print(f"wrote {OUT.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
