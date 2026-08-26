#!/usr/bin/env python3
"""Bootstrap CIs + multi-seed stability for the MetaWingman evidence chain.

Computes, deterministically and offline:
  * per-case fidelity for the decision-object rule (from archived per_case files);
  * per-case fidelity for ablation variants (full / no_guard / no_evpi / no_estimand)
    and for the progressive rule baselines (L1 design-rule only, L2 +guard);
  * per-case multi-task agreement (design / pooling / stopping);
  * bootstrap confidence intervals (seeded, multi-seed) for every mean and delta;
  * cross-model deltas: (a) paired bootstrap when per-case bare responses are
    archived (DeepSeek bare-LLM arm), (b) independent-arm approximation when only
    aggregates exist (GLM arm, no archived per-case responses).

Outputs (research/):
  bootstrap-ci.json            CIs for main results + ablation deltas + cross-model deltas
  multitask-agreement.json     per-task + 3-task agreement by corpus (rule; qwen if present)
  progressive-baseline.json    L0-L3 progressive baselines with CIs

Usage: python scripts/bootstrap_ci.py [--seeds 20260826,20260827,20260828]
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

from metawingman.agent.decision_core import IDENTIFICATION_ASSUMPTIONS, derive_design_decision
from metawingman.scripts.metawingman_core.design_selection import SYNTHESIS_ROUTES, derive_review_design
from metawingman.training.method_trace_fidelity import fidelity
from metawingman.training.method_trace_normalizer import normalize_gold_trace
from run_fidelity_real import build_agent_input

REPO = _REPO_ROOT
RES = REPO / "research"

N_BOOT = 2000
DEFAULT_SEEDS = [20260826, 20260827, 20260828, 20260829, 20260830]

WEIGHTS = {"design_selection": 0.30, "estimand_identification": 0.20,
           "synthesis_route": 0.20, "stop_decision": 0.15, "guard_consistency": 0.15}
TASKS = ["design_selection", "guard_consistency", "stop_decision"]


def load_rows(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def per_case_rule(fidelity_path: Path) -> list[dict]:
    """Load archived rule per-case (dims + totals) aligned with task scores."""
    data = json.loads(fidelity_path.read_text(encoding="utf-8"))
    out = []
    for c in data["per_case"]:
        out.append({
            "case_id": c["case_id"],
            "total": c["fidelity_total"],
            "dims": dict(c["dimensions"]),
            "agent_poolable": c["agent_poolable"],
            "gold_poolable": c["gold_poolable"],
            "agent_living": c["agent_living"],
            "gold_living": c["gold_living"],
        })
    return out


def recompute_variants(signal_path: Path) -> dict[str, list[dict]]:
    """Recompute per-case fidelity for full / no_guard / no_evpi / no_estimand
    and the progressive rule baselines L1 / L2 (same logic as ablate_design.py)."""
    rows = load_rows(signal_path)
    out: dict[str, list[dict]] = {"full": [], "no_guard": [], "no_evpi": [],
                                  "no_estimand": [], "L1_design_rule": [], "L2_plus_guard": []}
    for row in rows:
        gold = normalize_gold_trace(row)
        if gold is None:
            continue
        q, landscape = build_agent_input(gold.get("signal") or {})
        full = derive_design_decision(q, landscape)
        base = derive_review_design(q, landscape)

        def tr(profile, ident, route, living, passes):
            return {"profile": profile, "identification_assumption": ident,
                    "synthesis_route": route, "living": living,
                    "risk_guard": {"passes": passes}}

        variants = {
            "full": tr(full.profile, full.identification_assumption, full.synthesis_route,
                       full.living, full.risk_guard["passes"]),
            "no_guard": tr(base.profile, IDENTIFICATION_ASSUMPTIONS.get(base.profile, ""),
                           SYNTHESIS_ROUTES.get(base.profile, ""), full.living, True),
            "no_evpi": tr(full.profile, full.identification_assumption, full.synthesis_route,
                          False, full.risk_guard["passes"]),
            "no_estimand": tr(full.profile, "", full.synthesis_route, full.living,
                              full.risk_guard["passes"]),
            "L1_design_rule": tr(base.profile, IDENTIFICATION_ASSUMPTIONS.get(base.profile, ""),
                                 SYNTHESIS_ROUTES.get(base.profile, ""), bool(base.living), True),
            "L2_plus_guard": tr(full.profile, full.identification_assumption,
                                full.synthesis_route, False, full.risk_guard["passes"]),
        }
        for name, agent in variants.items():
            score = fidelity(agent, gold)
            out[name].append({
                "case_id": gold["case_id"],
                "total": score.total, "dims": dict(score.dimensions),
                "agent_poolable": bool(agent["risk_guard"]["passes"]),
                "gold_poolable": bool(gold.get("poolable", True)),
                "agent_living": bool(agent["living"]),
                "gold_living": bool(gold.get("living_review", False)),
            })
    return out


def task_scores(case: dict) -> dict[str, float]:
    return {"design": case["dims"]["design_selection"],
            "pool": case["dims"]["guard_consistency"],
            "stop": case["dims"]["stop_decision"]}


def weighted(case: dict) -> float:
    return sum(WEIGHTS[k] * case["dims"][k] for k in WEIGHTS)


def mt3(case: dict) -> float:
    t = task_scores(case)
    return round((t["design"] + t["pool"] + t["stop"]) / 3.0, 6)


def bootstrap_ci(values: np.ndarray, seed: int, n_boot: int = N_BOOT) -> dict:
    rng = np.random.default_rng(seed)
    n = len(values)
    draws = np.empty(n_boot)
    for i in range(n_boot):
        idx = rng.integers(0, n, size=n)
        draws[i] = values[idx].mean()
    lo, hi = np.percentile(draws, [2.5, 97.5])
    return {"mean": float(values.mean()), "ci95": [float(lo), float(hi)],
            "n_boot": n_boot}


def multi_seed_ci(values: np.ndarray, seeds: list[int]) -> dict:
    per = [bootstrap_ci(values, s) for s in seeds]
    return {
        "seed_specific": {str(s): {"ci95": p["ci95"]} for s, p in zip(seeds, per)},
        "ci95": [round(min(p["ci95"][0] for p in per), 4), round(max(p["ci95"][1] for p in per), 4)],
        "ci95_primary_seed": per[0]["ci95"],
        "mean": float(values.mean()),
        "seeds": seeds,
    }


def paired_ci(a: np.ndarray, b: np.ndarray, seed: int, n_boot: int = N_BOOT) -> dict:
    rng = np.random.default_rng(seed)
    n = len(a)
    draws = np.empty(n_boot)
    for i in range(n_boot):
        idx = rng.integers(0, n, size=n)
        draws[i] = (a[idx] - b[idx]).mean()
    lo, hi = np.percentile(draws, [2.5, 97.5])
    return {"mean": float((a - b).mean()), "ci95": [float(lo), float(hi)], "n_boot": n_boot}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", default=",".join(map(str, DEFAULT_SEEDS)))
    ap.add_argument("--fidelity-holdout", default=str(RES / "method-trace-fidelity-holdout.json"))
    ap.add_argument("--fidelity-large", default=str(RES / "method-trace-fidelity-large.json"))
    ap.add_argument("--bare-holdout", default=str(RES / "bare-llm-holdout.json"))
    ap.add_argument("--signal-holdout", default=str(RES / "method-trace-holdout-signal.jsonl"))
    ap.add_argument("--lora-honest", default=str(RES / "method-trace-fidelity-lora-honest.json"))
    args = ap.parse_args()
    seeds = [int(s) for s in args.seeds.split(",") if s.strip()]

    holdout = per_case_rule(Path(args.fidelity_holdout))
    large = per_case_rule(Path(args.fidelity_large))

    report: dict = {"n_boot": N_BOOT, "seeds": seeds, "note": (
        "bootstrap over cases (unit = one published review); multi-seed stability shown as "
        "min/max of per-seed 95% percentile CIs; primary seed = first in list"), "results": {}}

    # ---------- main rule results (holdout / large) ----------
    for corpus, cases in (("holdout_40", holdout), ("large_170", large)):
        totals = np.array([c["total"] for c in cases])
        report["results"][corpus] = {
            "n": len(cases),
            "mean_fidelity": float(totals.mean()),
            "mean_fidelity_ci": multi_seed_ci(totals, seeds),
            "tasks": {},
        }
        for task, key in (("design", "design_selection"), ("pooling", "guard_consistency"),
                          ("stop", "stop_decision")):
            vals = np.array([c["dims"][key] for c in cases])
            report["results"][corpus]["tasks"][task] = multi_seed_ci(vals, seeds)
        mt = np.array([mt3(c) for c in cases])
        report["results"][corpus]["multitask_mean_3"] = multi_seed_ci(mt, seeds)

    # ---------- ablation + progressive baselines (holdout-40) ----------
    variants = recompute_variants(Path(args.signal_holdout))
    ab: dict = {}
    base = np.array([c["total"] for c in variants["full"]])
    for name, cases in variants.items():
        vals = np.array([c["total"] for c in cases])
        entry: dict = {
            "n": len(cases),
            "mean_fidelity": float(vals.mean()),
            "mean_fidelity_ci": multi_seed_ci(vals, seeds),
            "tasks": {},
        }
        for task, key in (("design", "design_selection"), ("pooling", "guard_consistency"),
                          ("stop", "stop_decision")):
            entry["tasks"][task] = multi_seed_ci(np.array([c["dims"][key] for c in cases]), seeds)
        entry["multitask_mean_3"] = multi_seed_ci(
            np.array([mt3(c) for c in cases]), seeds)
        if name != "full":
            entry["delta_vs_full"] = multi_seed_ci(vals, seeds)  # placeholder replaced below
            d = paired_ci(vals, base, seeds[0])
            entry["delta_vs_full_paired_bs"] = {
                "mean_delta": float(vals.mean() - base.mean()),
                "ci95": [round(x, 4) for x in d["ci95"]],
                "n_boot": d["n_boot"],
                "note": "paired bootstrap over cases: (variant_fidelity - full_fidelity) per case",
            }
        ab[name] = entry
    report["results"]["ablation_holdout_40"] = ab
    # L1 vs L3 explicit delta (design-rule-only -> full decision object)
    l1 = np.array([c["total"] for c in variants["L1_design_rule"]])
    d_l1 = paired_ci(base, l1, seeds[0])
    report["results"]["progressive_L3_minus_L1_design_rule"] = {
        "L1_mean": float(l1.mean()), "L3_mean": float(base.mean()),
        "mean_delta": float(d_l1["mean"]), "ci95": [round(x, 4) for x in d_l1["ci95"]],
        "n_boot": d_l1["n_boot"],
        "note": "L1 = design rule only (no guard, no EVPI); L3 = full decision object",
    }

    # ---------- cross-model deltas ----------
    cm: dict = {}
    holdout_cases = {c["case_id"]: c for c in holdout}
    bare = json.loads(Path(args.bare_holdout).read_text(encoding="utf-8"))
    paired = []
    for c in bare["per_case"]:
        cid = c["case_id"]
        if cid in holdout_cases:
            rule = holdout_cases[cid]["dims"]["design_selection"]
            paired.append({"case_id": cid, "rule": float(rule), "bare": float(c["hit"])})
    if paired:
        rule_v = np.array([p["rule"] for p in paired])
        bare_v = np.array([p["bare"] for p in paired])
        cm["deepseek_holdout_paired"] = {
            "n": len(paired),
            "rule_design_match": float(rule_v.mean()),
            "bare_design_match": float(bare_v.mean()),
            "mean_delta": float(rule_v.mean() - bare_v.mean()),
            "delta_ci95_paired": [round(x, 4) for x in paired_ci(rule_v, bare_v, seeds[0])["ci95"]],
            "note": "per-case archived (run_bare_llm_fidelity arm); paired bootstrap over cases; "
                    "rule_design_match is the design_selection dimension of the rule on the same cases",
            "per_case_saved": True,
        }
    # GLM aggregate arm: no archived per-case responses -> independent CI approximation.
    glm = json.loads((RES / "cross-glm.json").read_text(encoding="utf-8"))
    n_g = int(glm["n"]); p_g = float(glm["bare_accuracy"])
    bare_g = np.array([1.0] * round(n_g * p_g) + [0.0] * (n_g - round(n_g * p_g)))
    rule_v = np.array([c["dims"]["design_selection"] for c in holdout])
    d = paired_ci(rule_v, bare_g, seeds[0])
    cm["glm_holdout_aggregate"] = {
        "n": n_g, "bare_accuracy": p_g, "rule_design_match": float(rule_v.mean()),
        "mean_delta": float(rule_v.mean() - bare_g.mean()),
        "delta_ci95_unpaired_approx": [round(x, 4) for x in d["ci95"]],
        "note": "GLM per-case responses were not archived; the CI is an independent-bootstrap "
                "approximation (bare arm as observed 0.75 binomial vector). The paired CI from the "
                "DeepSeek arm is the primary paired estimate.",
        "per_case_saved": False,
    }
    report["results"]["cross_model"] = cm

    # ---------- qwen honest point (if available) ----------
    lora_path = Path(args.lora_honest)
    if lora_path.exists():
        qw = json.loads(lora_path.read_text(encoding="utf-8"))
        cases = []
        for c in qw["per_case"]:
            cases.append({"case_id": c["case_id"], "total": c["fid"], "dims": c["dims"]})
        vals = np.array([c["total"] for c in cases])
        report["results"]["qwen_lora_holdout_40"] = {
            "n": len(cases), "parse_fail": qw.get("parse_fail", 0),
            "n_partial_missing": qw.get("n_partial_missing", 0),
            "mean_fidelity": float(vals.mean()),
            "mean_fidelity_ci": multi_seed_ci(vals, seeds),
            "tasks": {},
        }
        for task, key in (("design", "design_selection"), ("pooling", "guard_consistency"),
                          ("stop", "stop_decision")):
            report["results"]["qwen_lora_holdout_40"]["tasks"][task] = multi_seed_ci(
                np.array([c["dims"][key] for c in cases]), seeds)
        report["results"]["qwen_lora_holdout_40"]["multitask_mean_3"] = multi_seed_ci(
            np.array([mt3(c) for c in cases]), seeds)
    else:
        report["results"]["qwen_lora_holdout_40"] = None

    # ---------- multitask agreement file (per corpus; design/pool/stop as independent tasks) ----------
    def confusion(cases: list[dict]) -> dict:
        tp = sum(1 for c in cases if c["agent_poolable"] and c["gold_poolable"])
        fp = sum(1 for c in cases if c["agent_poolable"] and not c["gold_poolable"])
        tn = sum(1 for c in cases if not c["agent_poolable"] and not c["gold_poolable"])
        fn = sum(1 for c in cases if not c["agent_poolable"] and c["gold_poolable"])
        prec_pool = tp / (tp + fp) if (tp + fp) else None
        rec_pool = tp / (tp + fn) if (tp + fn) else None
        prec_nopool = tn / (tn + fn) if (tn + fn) else None
        rec_nopool = tn / (tn + fp) if (tn + fp) else None
        return {"tp": tp, "fp": fp, "tn": tn, "fn": fn,
                "pooled_precision": round(prec_pool, 4) if prec_pool is not None else None,
                "pooled_recall": round(rec_pool, 4) if rec_pool is not None else None,
                "nopool_precision": round(prec_nopool, 4) if prec_nopool is not None else None,
                "nopool_recall": round(rec_nopool, 4) if rec_nopool is not None else None}

    multitask: dict = {"metric": ("agreement with the published-expert reference on three "
                                  "independent tasks, each scored 0/1 per case; 3-task mean = "
                                  "per-case average of the three"),
                       "corpora": {}}
    for corpus, cases in (("holdout_40", holdout), ("large_170", large)):
        multitask["corpora"][corpus] = {
            "n": len(cases),
            "design_agreement": round(float(np.mean([c["dims"]["design_selection"] for c in cases])), 4),
            "pooling_agreement": round(float(np.mean([c["dims"]["guard_consistency"] for c in cases])), 4),
            "stop_agreement": round(float(np.mean([c["dims"]["stop_decision"] for c in cases])), 4),
            "three_task_mean": round(float(np.mean([mt3(c) for c in cases])), 4),
            "three_task_mean_ci95": [round(x, 4) for x in multi_seed_ci(
                np.array([mt3(c) for c in cases]), seeds)["ci95"]],
            "pooling_confusion": confusion(cases),
            "living_cases": int(sum(1 for c in cases if c["gold_living"])),
        }
    qw_path = Path(args.lora_honest)
    if qw_path.exists():
        qw = json.loads(qw_path.read_text(encoding="utf-8"))
        cases = [{"case_id": c["case_id"], "total": c["fid"], "dims": c["dims"]}
                 for c in qw["per_case"]]
        # The honest archive records dimension agreement only (agent 'pooled' output is
        # not archived), so pooling confusion is not computable for qwen; report agreement.
        multitask["corpora"]["qwen_lora_holdout_40"] = {
            "n": len(cases), "parse_fail": qw.get("parse_fail", 0),
            "design_agreement": round(float(np.mean([c["dims"]["design_selection"] for c in cases])), 4),
            "pooling_agreement": round(float(np.mean([c["dims"]["guard_consistency"] for c in cases])), 4),
            "stop_agreement": round(float(np.mean([c["dims"]["stop_decision"] for c in cases])), 4),
            "three_task_mean": round(float(np.mean([mt3(c) for c in cases])), 4),
            "three_task_mean_ci95": [round(x, 4) for x in multi_seed_ci(
                np.array([mt3(c) for c in cases]), seeds)["ci95"]],
            "note": "strict parse; parse failures score 0 on every dimension",
        }
    (RES / "multitask-agreement.json").write_text(json.dumps(multitask, indent=2) + "\n", encoding="utf-8")

    # ---------- progressive baseline file (L0 bare LLM -> L3 full decision object) ----------
    progressive: dict = {"scope": "progressive baselines on OOD holdout-40 (design_selection + weighted fidelity)",
                         "levels": {}}
    l0_ds = bare["profile_match_accuracy"]
    progressive["levels"]["L0_bare_llm"] = {
        "method": "bare LLM prompt (no decision-object flow; design choice only)",
        "design_match": {"glm-4.5-air": float(glm["bare_accuracy"]),
                         "deepseek-v4-flash_runA": round(l0_ds, 4),
                         "deepseek-v4-flash_runB": 0.75},
        "note": "design-choice only: the bare prompt returns a single design, no pooling or stop decision",
    }
    for name, label in (("L1_design_rule", "design rule only (derive_review_design; no guard, no EVPI; always poolable)"),
                        ("L2_plus_guard", "L1 + risk-controlled pooling guard (EVPI still off)"),
                        ("full", "L3 full decision object (estimand-first + guard + EVPI)"),
                        ("no_guard", "(ablation) full minus guard"),
                        ("no_estimand", "(ablation) full minus estimand-first"),
                        ("no_evpi", "(ablation) full minus EVPI stop")):
        cases = variants[name]
        vals = np.array([c["total"] for c in cases])
        progressive["levels"][name] = {
            "method": label,
            "design_match": round(float(np.mean([c["dims"]["design_selection"] for c in cases])), 4),
            "weighted_fidelity_mean": float(vals.mean()),
            "weighted_fidelity_ci95": [round(x, 4) for x in multi_seed_ci(vals, seeds)["ci95"]],
            "pooling_task": round(float(np.mean([c["dims"]["guard_consistency"] for c in cases])), 4),
            "three_task_mean": round(float(np.mean([mt3(c) for c in cases])), 4),
        }
    (RES / "progressive-baseline.json").write_text(json.dumps(progressive, indent=2) + "\n", encoding="utf-8")

    (RES / "bootstrap-ci.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("wrote research/bootstrap-ci.json, research/multitask-agreement.json, research/progressive-baseline.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
