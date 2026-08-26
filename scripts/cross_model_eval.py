#!/usr/bin/env python3
"""CROSS-MODEL fidelity: bare-LLM design choice vs the decision-object rule.

For a given provider config, ask the model DIRECTLY (no E-R-V flow) to pick the
review design for each holdout case; measure profile match against the real
published-meta gold; report bare accuracy, the rule-baseline, and the delta
(the decision-object architecture's increment on that model point).

Usage:
  python scripts/cross_model_eval.py --provider-config <cfg> --model-label <label> \
      --signal research/method-trace-holdout-signal.jsonl --out research/cross-<label>.json
GLM key: set GLM_API_KEY in the environment (never in the repo).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from metawingman.scripts.metawingman_core.provider_factory import build_provider, load_provider_config
from metawingman.training.method_trace_normalizer import normalize_gold_trace
from run_fidelity_real import build_agent_input

BASE_PROFILES = ["intervention_pairwise", "intervention_network", "diagnostic_accuracy",
                 "prognostic_prediction", "prevalence_incidence", "public_health_exposure",
                 "structured_no_pooling"]
SYSTEM = ("You are a senior systematic-review methodologist. Given a clinical question "
          "and the evidence structure, decide which review design a top-journal systematic "
          "review would use. Answer with ONLY ONE of: " + ", ".join(BASE_PROFILES) + ".")
RULE_BASELINE = 0.911  # decision-object rule on OOD holdout (design_selection)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider-config", required=True)
    ap.add_argument("--model-label", required=True)
    ap.add_argument("--signal", default="research/method-trace-holdout-signal.jsonl")
    ap.add_argument("--out", required=True)
    ap.add_argument("--rule-baseline", type=float, default=RULE_BASELINE)
    args = ap.parse_args()

    provider = build_provider(load_provider_config(Path(args.provider_config)))
    rows = [json.loads(l) for l in Path(args.signal).read_text(encoding="utf-8").splitlines() if l.strip()]
    n = ok = 0
    for row in rows:
        gold = normalize_gold_trace(row)
        if gold is None:
            continue
        q, landscape = build_agent_input(gold.get("signal") or {})
        user = (f"Clinical question: {json.dumps(q)}\n"
                f"Evidence structure: {json.dumps(landscape)}\n"
                f"Which review design? Answer with exactly one of: {', '.join(BASE_PROFILES)}.")
        try:
            content = provider.chat([{"role": "system", "content": SYSTEM},
                                     {"role": "user", "content": user}],
                                    json_output=False, max_tokens=32).content or ""
        except Exception as exc:
            content = f"<error:{type(exc).__name__}>"
        low = content.lower()
        prof = next((p for p in BASE_PROFILES if p in low), None)
        n += 1
        ok += int(prof == gold["design_selection"])
    acc = ok / n if n else 0.0
    report = {"model_label": args.model_label, "n": n, "bare_accuracy": round(acc, 4),
              "rule_baseline": args.rule_baseline, "delta": round(args.rule_baseline - acc, 4)}
    Path(args.out).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
