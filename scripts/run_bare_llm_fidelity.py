#!/usr/bin/env python3
"""BARE-LLM vs E-R-V Skill 增量对照（跨模型）。

On the same holdout reviews, ask the LLM DIRECTLY (no E-R-V flow) to pick the
review design; measure profile-match against the real published-meta gold. This
is the "no-Skill" arm: the Δ versus the E-R-V rule (design_selection dev 0.600 /
holdout 0.900) is the Skill's cross-model contribution. Uses the local deepseek
provider (a model point; can be repeated on other models incl. opus).

Output: research/bare-llm-holdout.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from metawingman.scripts.metawingman_core.model_provider import ModelProvider
from metawingman.scripts.metawingman_core.provider_factory import build_provider, load_provider_config
from metawingman.training.method_trace_normalizer import normalize_gold_trace
from run_fidelity_real import build_agent_input

REPO = Path(__file__).resolve().parents[1]
SIGNAL = REPO / "research" / "method-trace-holdout-signal.jsonl"
OUT = REPO / "research" / "bare-llm-holdout.json"

# base profiles (living_review is an ORTHOGONAL axis, not a base design choice)
BASE_PROFILES = [
    "intervention_pairwise", "intervention_network", "diagnostic_accuracy",
    "prognostic_prediction", "prevalence_incidence", "public_health_exposure",
    "structured_no_pooling",
]
SYSTEM = (
    "You are a senior systematic-review methodologist. Given a clinical question "
    "and the evidence structure, decide which review design a top-journal systematic "
    "review would use. Answer with ONLY ONE of: "
    + ", ".join(BASE_PROFILES) + "."

)


def main() -> int:
    provider = build_provider(load_provider_config(
        Path("metawingman/references/deepseek-provider-config.json")))
    rows = [json.loads(l) for l in SIGNAL.read_text(encoding="utf-8").splitlines() if l.strip()]
    per, n, ok = [], 0, 0
    unmatched = []
    for row in rows:
        gold = normalize_gold_trace(row)
        if gold is None:
            continue
        sig = gold.get("signal") or {}
        q, landscape = build_agent_input(sig)
        user = (f"Clinical question: {json.dumps(q)}\n"
                f"Evidence structure: {json.dumps(landscape)}\n"
                f"Which review design? Answer with exactly one of: "
                f"{', '.join(BASE_PROFILES)}.")
        try:
            res = provider.chat([{"role": "system", "content": SYSTEM},
                                 {"role": "user", "content": user}],
                                json_output=False, max_tokens=32)
            content = res.content or ""
        except Exception as exc:
            content = f"<error:{type(exc).__name__}>"
        low = content.lower()
        prof = next((p for p in BASE_PROFILES if p in low), None)
        hit = (prof == gold["design_selection"])
        n += 1
        ok += int(hit)
        if not hit:
            unmatched.append({"case_id": gold["case_id"], "gold": gold["design_selection"],
                              "bare": prof or "(none)", "raw": content[:80]})
        per.append({"case_id": gold["case_id"], "gold": gold["design_selection"],
                    "bare": prof, "hit": hit})
    accuracy = ok / n if n else 0.0
    by = {}
    for p in per:
        by[p["gold"]] = by.get(p["gold"], [0, 0])
        by[p["gold"]][1] += 1
        by[p["gold"]][0] += int(p["hit"])
    report = {
        "model_point": "deepseek (local provider)",
        "arm": "bare_llm_no_skill",
        "n": n, "profile_match_accuracy": round(accuracy, 4),
        "by_profile": {k: {"n": v[1], "match": round(v[0] / v[1], 4)} for k, v in by.items()},
        "per_case": per, "unmatched": unmatched,
        "er_v_design_selection_reference": {"dev": 0.600, "holdout": 0.900},
    }
    OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"n": n, "profile_match_accuracy": accuracy,
                      "er_v_holdout_design_selection": 0.900,
                      "by_profile": report["by_profile"]}, indent=2))
    print("wrote", OUT.name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
