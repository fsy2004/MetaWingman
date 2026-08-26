#!/usr/bin/env python3
"""Like-for-like multi-task comparison: decision-object rule vs bare-LLM multitask arm.

Both arms answer the same three tasks per case (design / pooling / stop), scored
0/1 against the published-expert reference. For comparability the weighted
fidelity of each arm is computed with the same weights: estimand/synthesis follow
the agent profile through the same canonical maps (identical derivation for both
arms), so weighted = 0.70*design + 0.15*pooling + 0.15*stop.

Outputs research/multitask-compare.json with means + bootstrap CIs + pooling
confusion for each arm and corpus (holdout-40, large-170).

Usage: python scripts/multitask_compare.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

RES = _REPO_ROOT / "research"
SEEDS = [20260826, 20260827, 20260828]
N_BOOT = 2000

WEIGHTS_TASKS = {"design": 0.70, "pooling": 0.15, "stop": 0.15}


def load(p: str) -> dict:
    return json.loads((RES / p).read_text(encoding="utf-8"))


def ci(values: np.ndarray, seed: int) -> list[float]:
    rng = np.random.default_rng(seed)
    n = len(values)
    draws = np.empty(N_BOOT)
    for i in range(N_BOOT):
        idx = rng.integers(0, n, size=n)
        draws[i] = values[idx].mean()
    return [round(float(x), 4) for x in np.percentile(draws, [2.5, 97.5])]


def multi_ci(values: np.ndarray) -> dict:
    per = {s: ci(values, s) for s in SEEDS}
    return {"ci95": [min(v[0] for v in per.values()), max(v[1] for v in per.values())],
            "per_seed": per}


def confusion(cases: list[dict], agent_key: str, gold_key: str) -> dict:
    tp = sum(1 for c in cases if c[agent_key] and c[gold_key])
    fp = sum(1 for c in cases if c[agent_key] and not c[gold_key])
    tn = sum(1 for c in cases if not c[agent_key] and not c[gold_key])
    fn = sum(1 for c in cases if not c[agent_key] and c[gold_key])
    out = {"tp": tp, "fp": fp, "tn": tn, "fn": fn}
    out["pooled_precision"] = round(tp / (tp + fp), 4) if (tp + fp) else None
    out["pooled_recall"] = round(tp / (tp + fn), 4) if (tp + fn) else None
    return out


def main() -> int:
    mt = load("multitask-agreement.json")["corpora"]
    report: dict = {"scope": ("multi-task comparison (design/pooling/stop), strict parse, "
                              "no fallback; rule = decision-object, bare = single-prompt LLM arm (deepseek-v4-flash)"),
                    "corpora": {}}

    for corpus, bare_path in (("holdout_40", "cross-ds-multitask-holdout.json"),
                              ("large_170", "cross-ds-multitask-large.json")):
        bare = load(bare_path)
        rule = mt[corpus]
        bare_cases = bare["per_case"]
        # rule per-case from the fidelity archive (same cases)
        rule_file = "method-trace-fidelity-holdout.json" if corpus == "holdout_40" else "method-trace-fidelity-large.json"
        rule_cases = load(rule_file)["per_case"]
        rule_by_id = {c["case_id"]: c for c in rule_cases}
        joined = []
        for b in bare_cases:
            r = rule_by_id.get(b["case_id"])
            if r is None:
                continue
            joined.append({"case_id": b["case_id"],
                           "rule_design": float(r["dimensions"]["design_selection"]),
                           "rule_pool": float(r["dimensions"]["guard_consistency"]),
                           "rule_stop": float(r["dimensions"]["stop_decision"]),
                           "bare_design": float(b["design_ok"]),
                           "bare_pool": float(b["pool_ok"]),
                           "bare_stop": float(b["stop_ok"]),
                           "bare_pooled": bool(b["agent_pooled"]) if b["agent_pooled"] is not None else False,
                           "gold_pooled": bool(b["gold_poolable"])})
        rule_v = {t: np.array([c[f"rule_{t.split('_')[0]}"] for c in joined]) for t in
                  ("design", "pool", "stop")}
        bare_v = {t: np.array([c[f"bare_{t.split('_')[0]}"] for c in joined]) for t in
                  ("design", "pool", "stop")}
        def weighted(v: dict) -> np.ndarray:
            return WEIGHTS_TASKS["design"] * v["design"] + WEIGHTS_TASKS["pooling"] * v["pool"] + WEIGHTS_TASKS["stop"] * v["stop"]
        entry = {
            "n": len(joined),
            "rule": {
                "three_task_mean": round(float((rule_v["design"] + rule_v["pool"] + rule_v["stop"]).mean() / 3), 4),
                "three_task_mean_ci95": multi_ci((rule_v["design"] + rule_v["pool"] + rule_v["stop"]) / 3)["ci95"],
                "weighted_fidelity": round(float(weighted(rule_v).mean()), 4),
                "weighted_fidelity_ci95": multi_ci(weighted(rule_v))["ci95"],
            },
            "bare_llm": {
                "three_task_mean": round(float((bare_v["design"] + bare_v["pool"] + bare_v["stop"]).mean() / 3), 4),
                "three_task_mean_ci95": multi_ci((bare_v["design"] + bare_v["pool"] + bare_v["stop"]) / 3)["ci95"],
                "weighted_fidelity": round(float(weighted(bare_v).mean()), 4),
                "weighted_fidelity_ci95": multi_ci(weighted(bare_v))["ci95"],
                "parse_fail": bare.get("parse_fail", 0),
                "pooling_confusion": confusion(joined, "bare_pooled", "gold_pooled"),
            },
            "delta_rule_minus_bare_3task": round(float(((rule_v["design"] + rule_v["pool"] + rule_v["stop"]) / 3
                                                        - (bare_v["design"] + bare_v["pool"] + bare_v["stop"]) / 3).mean()), 4),
        }
        report["corpora"][corpus] = entry
    (RES / "multitask-compare.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
