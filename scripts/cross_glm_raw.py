#!/usr/bin/env python3
"""GLM-4.5-Air cross-model bare fidelity (raw call with `thinking` disabled).

The OpenAI-compatible adapter doesn't forward GLM's `thinking` param, and
glm-4.5-air defaults to thinking mode (content empty). This calls the endpoint
directly with thinking disabled to get a usable answer. Requires GLM_API_KEY env.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from metawingman.training.method_trace_normalizer import normalize_gold_trace
from run_fidelity_real import build_agent_input

BASE = ["intervention_pairwise", "intervention_network", "diagnostic_accuracy",
        "prognostic_prediction", "prevalence_incidence", "public_health_exposure",
        "structured_no_pooling"]
SYSTEM = ("You are a senior systematic-review methodologist. Given a clinical question "
          "and the evidence structure, decide which review design a top-journal systematic "
          "review would use. Answer with ONLY ONE of: " + ", ".join(BASE) + ".")
BASE_URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
RULE_BASELINE = 0.911


def chat(prompt_user: str) -> str:
    key = os.environ["GLM_API_KEY"]
    payload = {
        "model": "glm-4.5-air",
        "messages": [{"role": "system", "content": SYSTEM},
                     {"role": "user", "content": prompt_user}],
        "max_tokens": 120,
        "thinking": {"type": "disabled"},
    }
    req = urllib.request.Request(
        BASE_URL, data=json.dumps(payload).encode("utf-8"), method="POST",
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return (data.get("choices") or [{}])[0].get("message", {}).get("content") or ""


def main() -> int:
    rows = [json.loads(l) for l in Path("research/method-trace-holdout-signal.jsonl").read_text(
        encoding="utf-8").splitlines() if l.strip()]
    n = ok = 0
    empty = 0
    for row in rows:
        gold = normalize_gold_trace(row)
        if gold is None:
            continue
        q, land = build_agent_input(gold.get("signal") or {})
        user = (f"Clinical question: {json.dumps(q)}\n"
                f"Evidence structure: {json.dumps(land)}\n"
                f"Which review design? Answer with exactly one of: {', '.join(BASE)}.")
        content = chat(user)
        if not content.strip():
            empty += 1
        low = content.lower()
        prof = next((p for p in BASE if p in low), None)
        n += 1
        ok += int(prof == gold["design_selection"])
    acc = ok / n if n else 0.0
    report = {"model_label": "glm-4.5-air", "n": n, "bare_accuracy": round(acc, 4),
              "rule_baseline": RULE_BASELINE, "delta": round(RULE_BASELINE - acc, 4),
              "empty_responses": empty}
    Path("research/cross-glm.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
