#!/usr/bin/env python3
"""Cross-model design-task comparison (like-for-like) + correction record.

The original cross-glm.json / cross-ds.json compared the bare-LLM *design-choice*
accuracy (0.75) to the decision-object *weighted fidelity* (0.911) — a task-mix
comparison. This script recomputes the increment on the SAME single task
(design_selection agreement with the published-expert reference, OOD holdout-40,
strict parse) and adds bootstrap CIs. Output: research/cross-model-design-task.json

Usage: python scripts/cross_model_design_task.py
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
SEED = 20260826
N_BOOT = 2000


def main() -> int:
    holdout = json.loads((RES / "method-trace-fidelity-holdout.json").read_text(encoding="utf-8"))
    rule_design = np.array([c["dimensions"]["design_selection"] for c in holdout["per_case"]])
    rule_mean = float(rule_design.mean())

    bare = json.loads((RES / "bare-llm-holdout.json").read_text(encoding="utf-8"))
    by_id = {c["case_id"]: c for c in holdout["per_case"]}
    paired = [{"rule": by_id[c["case_id"]]["dimensions"]["design_selection"], "bare": float(c["hit"])}
              for c in bare["per_case"] if c["case_id"] in by_id]
    rng = np.random.default_rng(SEED)
    n = len(paired)
    ds_draws = np.empty(N_BOOT)
    for i in range(N_BOOT):
        idx = rng.integers(0, n, size=n)
        ds_draws[i] = (np.array([paired[j]["rule"] for j in idx]).mean()
                       - np.array([paired[j]["bare"] for j in idx]).mean())
    ds = {
        "model_point": "deepseek-v4-flash (local provider; bare run A archived per-case)",
        "n": n, "bare_design_match": float(np.mean([p["bare"] for p in paired])),
        "rule_design_match": rule_mean,
        "delta_design_task": float(np.mean([p["rule"] for p in paired]) - np.mean([p["bare"] for p in paired])),
        "delta_ci95_paired_bootstrap": [round(float(x), 4) for x in np.percentile(ds_draws, [2.5, 97.5])],
        "method": "paired bootstrap over the 40 cases (same case in both arms); 2000 draws; seed 20260826",
        "per_case_archived": True,
    }

    glm = json.loads((RES / "cross-glm.json").read_text(encoding="utf-8"))
    n_g, p_g = int(glm["n"]), float(glm["bare_accuracy"])
    bare_g = np.array([1.0] * round(n_g * p_g) + [0.0] * (n_g - round(n_g * p_g)))
    rng2 = np.random.default_rng(SEED)
    gl_draws = np.empty(N_BOOT)
    for i in range(N_BOOT):
        idx = rng2.integers(0, n_g, size=n_g)
        gl_draws[i] = rule_design.mean() - bare_g[idx].mean()
    gl = {
        "model_point": "glm-4.5-air (raw call, thinking disabled)",
        "n": n_g, "bare_design_match": p_g, "rule_design_match": rule_mean,
        "delta_design_task": rule_mean - p_g,
        "delta_ci95_independent_approx": [round(float(x), 4) for x in np.percentile(gl_draws, [2.5, 97.5])],
        "method": "GLM per-case responses were not archived; CI is an independent-bootstrap "
                  "approximation (bare arm as the observed 0.75 binomial vector). The paired CI "
                  "from the DeepSeek arm is the primary paired estimate.",
        "per_case_archived": False,
    }

    report = {
        "scope": ("cross-model design-task comparison (agreement with the published-expert "
                  "reference on design_selection, 0/1 per case), OOD holdout-40, strict parse"),
        "correction": ("Earlier cross-glm.json/cross-ds.json compared the bare-LLM design-choice "
                       "accuracy to the decision-object WEIGHTED FIDELITY (0.911; a task mix). "
                       "The like-for-like comparison on the same single task (design_selection) "
                       "is reported here: rule design match = 0.900 on the same 40 cases."),
        "rule_design_match": rule_mean,
        "points": [ds, gl],
        "receipt_seed": SEED, "n_boot": N_BOOT,
    }
    (RES / "cross-model-design-task.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["points"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
