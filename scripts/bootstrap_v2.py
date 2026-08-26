#!/usr/bin/env python3
"""Bootstrap CIs + multi-seed stability for the v2 evidence chain (methods-text gold).

Reads the v2 per-case files and reports, per corpus (dev/holdout/large/living):
weighted-fidelity CI, per-task CIs, three-task-mean CI; plus the like-for-like
rule-vs-bare multi-task comparison with paired CIs; and CIs for the ablation
deltas (read from ablation-v2.json's per-case rebuild is done here by reusing
fidelity-v2 per_case totals).

Usage: python scripts/bootstrap_v2.py
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
SEEDS = [20260826, 20260827, 20260828, 20260829, 20260830]
N_BOOT = 2000
WEIGHTS = {"design_selection": 0.30, "estimand_identification": 0.20,
           "synthesis_route": 0.20, "stop_decision": 0.15, "guard_consistency": 0.15}


def multi_ci(values: np.ndarray) -> dict:
    out = []
    for seed in SEEDS:
        rng = np.random.default_rng(seed)
        n = len(values)
        draws = np.empty(N_BOOT)
        for i in range(N_BOOT):
            idx = rng.integers(0, n, size=n)
            draws[i] = values[idx].mean()
        out.append([round(float(x), 4) for x in np.percentile(draws, [2.5, 97.5])])
    return {"mean": round(float(values.mean()), 4),
            "ci95": [min(c[0] for c in out), max(c[1] for c in out)],
            "per_seed": out}


def main() -> int:
    report: dict = {"scope": "v2 bootstrap CIs (methods-text gold)", "n_boot": N_BOOT,
                    "seeds": SEEDS, "corpora": {}}
    for name in ("dev", "holdout", "large", "living"):
        f = RES / f"fidelity-v2-{name}.json"
        if not f.exists():
            continue
        d = json.loads(f.read_text(encoding="utf-8"))
        cases = d["per_case"]
        totals = np.array([c["total"] for c in cases])
        report["corpora"][name] = {
            "n": len(cases),
            "weighted_fidelity": multi_ci(totals),
            "tasks": {k: multi_ci(np.array([c["dims"][k] for c in cases]))
                      for k in WEIGHTS},
            "three_task_mean": multi_ci(np.array([
                round((c["dims"]["design_selection"] + c["dims"]["guard_consistency"]
                       + c["dims"]["stop_decision"]) / 3, 6) for c in cases])),
        }
    # rule vs bare multitask (like-for-like, paired)
    compare: dict = {"scope": "v2 rule vs bare multi-task (paired per case, 3-task mean + tasks)",
                     "corpora": {}}
    for name, bare_file, rule_file in (
            ("holdout", "cross-ds-multitask-holdout-v2.json", "fidelity-v2-holdout.json"),
            ("large", "cross-ds-multitask-large-v2.json", "fidelity-v2-large.json")):
        bf, rf = RES / bare_file, RES / rule_file
        if not (bf.exists() and rf.exists()):
            continue
        bare = json.loads(bf.read_text(encoding="utf-8"))["per_case"]
        rule = {c["case_id"]: c for c in json.loads(rf.read_text(encoding="utf-8"))["per_case"]}
        rule_v, bare_v = [], []
        for b in bare:
            r = rule.get(b["case_id"])
            if r is None:
                continue
            rule_v.append([r["dims"]["design_selection"], r["dims"]["guard_consistency"],
                           r["dims"]["stop_decision"]])
            bare_v.append([b["design_ok"], b["pool_ok"], b["stop_ok"]])
        rule_v, bare_v = np.array(rule_v), np.array(bare_v)
        compare["corpora"][name] = {
            "n": len(rule_v),
            "rule_3task": multi_ci(rule_v.mean(axis=1)),
            "bare_3task": multi_ci(bare_v.mean(axis=1)),
            "delta_rule_minus_bare": multi_ci(rule_v.mean(axis=1) - bare_v.mean(axis=1)),
            "rule_pooling": multi_ci(rule_v[:, 1]),
            "bare_pooling": multi_ci(bare_v[:, 1]),
            "rule_design": multi_ci(rule_v[:, 0]),
            "bare_design": multi_ci(bare_v[:, 0]),
        }
    (RES / "bootstrap-v2-ci.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    (RES / "multitask-compare-v2.json").write_text(json.dumps(compare, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"corpora": {k: {"n": v["n"], "fid": v["weighted_fidelity"]}
                                  for k, v in report["corpora"].items()},
                      "compare": {k: {"n": v["n"], "rule": v["rule_3task"], "bare": v["bare_3task"]}
                                  for k, v in compare["corpora"].items()}}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
