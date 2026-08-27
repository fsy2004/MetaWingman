#!/usr/bin/env python3
"""Oracle diagnosis (MetaSyn-style): where does a disagreement originate —
judgment layer or signal/data layer?

依据(出处): _deliverables/deep-study/notes/metasyn.md (oracle diagnosis:
             "检索到位≠选择到位"; feeding the correct input isolates the layer),
             论文: MetaSyn (arXiv 2606.17041).
Protocol: (a) real-input run: rule on the actual extracted signals (measured);
(b) oracle-input run: rule with the reference design label made explicit in the
input (lower bound on the judgment layer's achievable agreement given the gold
signal); delta = signal-layer cost vs judgment-layer cost.
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
from metawingman.agent.poolability_guard import calibrate_dimension_guard  # noqa: E402
from metawingman.training.method_trace_fidelity import WEIGHTS, fidelity  # noqa: E402
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


PROFILE_TO_HINT = {
    "intervention_pairwise": "pairwise",
    "intervention_network": "network",
    "diagnostic_accuracy": "diagnostic",
    "prognostic_prediction": "prediction",
    "prevalence_incidence": "prevalence",
    "public_health_exposure": "exposure",
    "structured_no_pooling": "narrative_no_pooling",
}


def main() -> int:
    dev = load_gold("gold")
    cal = [{**{k: g["signal"].get(k) for k in V2_KEYS}, "n_nodes_assessed": True,
            "profile_hint": g["design_selection"],
            "estimand_aligned": g["design_selection"] not in ("", "structured_no_pooling"),
            "is_pooling_misleading": not bool(g.get("poolable", True))} for g in dev]
    guard_model = calibrate_dimension_guard(cal, alpha=0.10, delta=0.10)

    report = {"scope": ("oracle diagnosis: layer attribution of design disagreements "
                        "(MetaSyn-style; =which layer contains the failure)"),
              "corpora": {}}
    for name in ("holdout", "large", "living"):
        cases = load_gold(name)
        real_ok = oracle_ok = 0
        for g in cases:
            sig = {k: v for k, v in (g["signal"] or {}).items() if k != "living_or_update"}
            q, landscape = build_agent_input(sig)
            d = derive_design_decision_v2(q, landscape,
                                          guard_signal={k: g["signal"].get(k) for k in V2_KEYS},
                                          guard_model=guard_model, info_cost=0.70)
            real_ok += int(d.profile == g["design_selection"])
            # oracle: correct the (noisy) extracted hint to its canonical enum as
            # if the signal layer were perfect — signal no longer contains noise,
            # the judgment layer still does its own inference.
            correct_hint = PROFILE_TO_HINT.get(g["design_selection"], "")
            sig_or = dict(sig)
            sig_or["design_type_hint"] = correct_hint
            q2, landscape2 = build_agent_input(sig_or)
            d2 = derive_design_decision_v2(
                q2, landscape2,
                guard_signal={k: g["signal"].get(k) for k in V2_KEYS} | {"design_type_hint": correct_hint},
                guard_model=guard_model, info_cost=0.70)
            oracle_ok += int(d2.profile == g["design_selection"])
        n = len(cases)
        report["corpora"][name] = {
            "n": n,
            "real_input_agreement": round(real_ok / n, 4),
            "oracle_input_agreement": round(oracle_ok / n, 4),
            "signal_layer_share": round((oracle_ok - real_ok) / max(1, n - real_ok), 4) if n > real_ok else 0.0,
            "judgment_residual": round((n - oracle_ok) / n, 4),
            "reading": ("disagreements mostly attributable to the signal/label layer if "
                        "oracle agreement is much higher; to the judgment layer otherwise"),
        }
    (RES / "oracle-diagnosis-v2.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
