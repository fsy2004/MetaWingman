#!/usr/bin/env python3
"""Method-layer 3.0 evaluation: scrutiny layer (oppose/adjudicate + precedent
retrieval) on top of the v2.2 judgment layer. Deterministic, zero training.

Variants (paired, same gold):
  L1  v2.2 baseline (design-pooling decoupled + taxonomy-aligned priority)
  L2  + scrutiny (negative-principle objections + adjudication)
  L3  + precedent retrieval (soft conflict; library = dev-40, family-isolated)

Pre-registration: rules are fixed by methodological principle ("what a
methodologist would object to"), not fitted on the OOD corpora. If a layer
produces no gain, that is reported (top-venue ablation discipline).

Usage: python scripts/method_layer3_eval.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from metawingman.agent.decision_core import (  # noqa: E402
    IDENTIFICATION_ASSUMPTIONS, derive_design_decision_v2)
from metawingman.agent.scrutiny import (  # noqa: E402
    adjudicate, oppose, precedent_retrieval)
from metawingman.agent.poolability_guard import calibrate_dimension_guard  # noqa: E402
from metawingman.scripts.metawingman_core.design_selection import (  # noqa: E402
    SYNTHESIS_ROUTES, derive_review_design)
from metawingman.training.method_trace_fidelity import WEIGHTS, fidelity  # noqa: E402
from metawingman.training.method_trace_normalizer import normalize_gold_trace  # noqa: E402
from run_fidelity_real import build_agent_input  # noqa: E402

RES = _REPO_ROOT / "research"
SEEDS = [20260826, 20260827, 20260828]
N_BOOT = 2000
V2_KEYS = ("intervention_arm_count", "comparator_count", "has_reference_standard",
           "has_prediction_model", "outcome_measure_type", "design_type_hint",
           "effect_measure_type", "analysis_unit", "conditioning_set",
           "population_description", "time_horizon")


def load_gold(name: str) -> list[dict]:
    path = RES / f"method-trace-{name}-signal-v2.jsonl"
    rows = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    return [g for g in (normalize_gold_trace(r) for r in rows) if g]


def guard_signal(gold: dict) -> dict:
    s = {k: gold["signal"].get(k) for k in V2_KEYS}
    s["n_nodes_assessed"] = True
    s["profile_hint"] = gold["design_selection"]
    s["estimand_aligned"] = gold["design_selection"] not in ("", "structured_no_pooling")
    return s


def run_case(gold: dict, guard_model, info_cost=0.70) -> tuple[dict, dict, dict, dict]:
    sig = {k: v for k, v in (gold["signal"] or {}).items() if k != "living_or_update"}
    q, landscape = build_agent_input(sig)
    d = derive_design_decision_v2(q, landscape, guard_signal=guard_signal(gold),
                                  guard_model=guard_model, info_cost=info_cost)
    agent = {"profile": d.profile, "living": d.living, "risk_guard": {"passes": d.risk_guard["passes"]}}
    obj = oppose({k: gold["signal"].get(k) for k in V2_KEYS} | {"profile_hint": d.profile}, agent)
    adj = adjudicate(agent, obj)
    agent_l2 = {"profile": adj["profile"], "living": agent["living"],
                "risk_guard": agent["risk_guard"]}
    lib = PRECEDENT_LIBRARY
    prec, margin = precedent_retrieval({k: gold["signal"].get(k) for k in V2_KEYS}, lib, k=3)
    return agent, agent_l2, {"obj": obj, "adj": adj, "prec": prec, "margin": margin}, gold


def trace_of(profile: str, living: bool, passes: bool) -> dict:
    return {"profile": profile or "",
            "identification_assumption": IDENTIFICATION_ASSUMPTIONS.get(profile, ""),
            "synthesis_route": SYNTHESIS_ROUTES.get(profile, ""),
            "living": living, "risk_guard": {"passes": passes}}


def main() -> int:
    global PRECEDENT_LIBRARY  # family-isolated: dev-40 only
    dev = load_gold("gold")
    PRECEDENT_LIBRARY = [{"signal": g["signal"], "design_selection": g["design_selection"],
                          "poolable": bool(g.get("poolable", True))} for g in dev]

    cal = [{**guard_signal(g), "is_pooling_misleading": not bool(g.get("poolable", True))}
           for g in dev]
    guard_model = calibrate_dimension_guard(cal, alpha=0.10, delta=0.10)

    out: dict = {"scope": ("method-layer 3.0 scrutiny evaluation, deterministic, zero training; "
                           "pre-registered fixed principles; precedent library = dev-40 (family-isolated)"),
                 "corpora": {}}
    for name in ("holdout", "large", "living"):
        cases = load_gold(name)
        per = []
        for gold in cases:
            a1, a2, meta, gold = run_case(gold, guard_model)
            t1 = trace_of(a1["profile"], a1["living"], a1["risk_guard"]["passes"])
            t2 = trace_of(a2["profile"], a2["living"], a2["risk_guard"]["passes"])
            s1 = fidelity(t1, gold).total
            s2 = fidelity(t2, gold).total
            pc = meta["adj"].get("precedent_conflict")
            prec_majority = pc["majority"] if pc else None
            per.append({"case_id": gold["case_id"], "gold": gold["design_selection"],
                        "l1_profile": a1["profile"], "l2_profile": a2["profile"],
                        "l1_total": s1, "l2_total": s2,
                        "objections": [o["principle"] for o in meta["obj"]],
                        "changes": meta["adj"]["changes"],
                        "precedent_conflict": pc,
                        "prec_majority_equals_gold": (prec_majority == gold["design_selection"]) if pc else None})
        v1 = np.array([p["l1_total"] for p in per])
        v2 = np.array([p["l2_total"] for p in per])
        changed = [p for p in per if p["l1_profile"] != p["l2_profile"]]
        changed_correct = [p for p in changed if p["l2_profile"] == p["gold"] and p["l1_profile"] != p["gold"]]
        changed_wrong = [p for p in changed if p["l2_profile"] != p["gold"] and p["l1_profile"] == p["gold"]]
        conflicts = [p for p in per if p["precedent_conflict"]]
        conflict_majority_gold = sum(1 for p in conflicts if p["prec_majority_equals_gold"])
        entry = {
            "n": len(per),
            "l1_mean": round(float(v1.mean()), 4),
            "l2_mean": round(float(v2.mean()), 4),
            "delta_l2_minus_l1": round(float(v2.mean() - v1.mean()), 4),
            "precedent_conflict_rate": round(len(conflicts) / len(per), 4),
            "precedent_majority_equals_gold_rate": round(conflict_majority_gold / len(conflicts), 4) if conflicts else None,
            "design_changes_applied": len(changed),
            "changes_correct": len(changed_correct),
            "changes_wrong": len(changed_wrong),
        }
        # paired bootstrap CI
        cis = []
        for seed in SEEDS:
            rng = np.random.default_rng(seed)
            idx = rng.integers(0, len(per), size=len(per))
            draws = []
            for _ in range(N_BOOT):
                ii = rng.integers(0, len(per), size=len(per))
                draws.append(float((v2[ii] - v1[ii]).mean()))
            cis.append([float(x) for x in np.percentile(draws, [2.5, 97.5])])
        entry["delta_ci95"] = [round(min(c[0] for c in cis), 4), round(max(c[1] for c in cis), 4)]
        out["corpora"][name] = entry
        (RES / f"method-layer3-{name}.json").write_text(
            json.dumps({**entry, "per_case": per}, indent=2) + "\n", encoding="utf-8")
        print(name, json.dumps({k: v for k, v in entry.items() if k != "per_case"}, indent=2))
    (RES / "method-layer3-summary.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")

    # ---------- checker diagnostic: would the scrutiny layer have caught the
    # historical design-pooling coupling bug? (retroactive audit, large corpus) ----------
    # emulate the pre-v2.1 semantics: guard failure ALWAYS rewrites the design.
    audit = {"scope": ("checker audit: does the scrutiny layer flag the historical "
                       "design-pooling coupling (guard failure -> narrative rewrite) and "
                       "would its fix (keep the strong design) match the reference?")}
    cases = load_gold("large")
    flagged = matched = fix_matches = 0
    false_o = []
    for gold in cases:
        sig = {k: v for k, v in (gold["signal"] or {}).items() if k != "living_or_update"}
        q, landscape = build_agent_input(sig)
        d = derive_design_decision_v2(q, landscape, guard_signal=guard_signal(gold),
                                      guard_model=guard_model, info_cost=0.70)
        signal_v = {k: gold["signal"].get(k) for k in V2_KEYS}
        strong = bool(any(signal_v.get(k) for k in ("has_reference_standard", "has_prediction_model"))) or \
            str(signal_v.get("outcome_measure_type") or "").casefold() in ("proportion", "prevalence")
        # coupled bug emulation: guard fail + strong design -> narrative (old semantics)
        coupled_profile = "structured_no_pooling" if (not d.risk_guard["passes"] and strong) else d.profile
        agent_c = {"profile": coupled_profile, "living": d.living,
                   "risk_guard": {"passes": d.risk_guard["passes"]}}
        obj = oppose(signal_v | {"profile_hint": d.profile}, agent_c)
        fires = [o for o in obj if o["principle"] in ("pooling_overwrites_design",
                                                      "narrative_overrides_strong_design")]
        if fires:
            flagged += 1
            if coupled_profile != gold["design_selection"] and d.risk_guard["passes"] is False:
                matched += 1
                if d.profile == gold["design_selection"]:
                    fix_matches += 1
            else:
                false_o.append(gold["case_id"])
    audit.update({"corpus": "large", "n": len(cases),
                  "flag_rate": round(flagged / len(cases), 4),
                  "flagged_n": flagged,
                  "coupled_wrong_and_flagged": matched,
                  "fix_matches_gold": fix_matches,
                  "flag_false_positives": len(false_o)})
    (RES / "method-layer3-checker-audit.json").write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
    print("checker audit:", json.dumps(audit))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
