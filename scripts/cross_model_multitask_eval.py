#!/usr/bin/env python3
"""BARE-LLM MULTI-TASK arm: one prompt asks the model for the three decisions
(design / pooled / living) as strict JSON; each task scored 0/1 against the
published-expert reference (same gold as the rule + honest-parse rules).

This is the like-for-like L0 baseline for the MULTI-TASK comparison: the
decision-object agent answers design + pooling (risk-controlled) + stop (EVPI);
the bare model is asked the same three questions with no decision-object flow.
Strict parsing: profile must be one of BASE_PROFILES, pooled/living must be
booleans; anything else scores 0 (parse failure recorded, never fallback).

Usage:
  python scripts/cross_model_multitask_eval.py --signal research/method-trace-holdout-signal.jsonl \
      --out research/cross-ds-multitask-holdout.json --provider-config metawingman/references/deepseek-provider-config.json
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
SYSTEM = ("You are a senior systematic-review methodologist. Given a clinical question and "
          "the evidence structure, output ONLY a JSON object with three keys: "
          '"profile" (one of: ' + ", ".join(BASE_PROFILES) + '), "pooled" (true/false: whether '
          'a pooled estimate is scientifically defensible), "living" (true/false: whether the '
          'evidence is still updating / the review is living). Do not output anything else.')


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--signal", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--provider-config", default="metawingman/references/deepseek-provider-config.json")
    ap.add_argument("--model-label", default="ds-v4-flash")
    ap.add_argument("--max-tokens", type=int, default=120)
    args = ap.parse_args()

    provider = build_provider(load_provider_config(Path(args.provider_config)))
    rows = [json.loads(l) for l in Path(args.signal).read_text(encoding="utf-8").splitlines() if l.strip()]
    per = []
    n = parse_fail = 0
    for row in rows:
        gold = normalize_gold_trace(row)
        if gold is None:
            continue
        q, landscape = build_agent_input(gold.get("signal") or {})
        user = (f"Clinical question: {json.dumps(q)}\n"
                f"Evidence structure: {json.dumps(landscape)}\n"
                "Answer with the JSON object only.")
        try:
            content = provider.chat([{"role": "system", "content": SYSTEM},
                                     {"role": "user", "content": user}],
                                    json_output=False, max_tokens=args.max_tokens).content or ""
        except Exception as exc:
            content = f"<error:{type(exc).__name__}>"
        comp = {}
        s = content.find("{")
        if s >= 0:
            try:
                comp = json.loads(content[s:])
            except Exception:
                comp = {}
        if not isinstance(comp, dict):
            comp = {}
        prof = comp.get("profile", "")
        pooled = comp.get("pooled")
        living = comp.get("living")
        if not isinstance(prof, str) or prof not in BASE_PROFILES:
            prof = ""
        ok_design = int(prof == gold["design_selection"]) if prof else 0
        ok_pool = 0
        if isinstance(pooled, bool):
            ok_pool = int(pooled == bool(gold.get("poolable", True)))
        ok_stop = 0
        if isinstance(living, bool):
            ok_stop = int(living == bool(gold.get("living_review", False)))
        if not (prof and isinstance(pooled, bool) and isinstance(living, bool)):
            parse_fail += 1
        n += 1
        per.append({"case_id": gold["case_id"], "gold_profile": gold["design_selection"],
                    "agent_profile": prof or "(parse_fail)",
                    "gold_poolable": bool(gold.get("poolable", True)),
                    "agent_pooled": pooled if isinstance(pooled, bool) else None,
                    "gold_living": bool(gold.get("living_review", False)),
                    "agent_living": living if isinstance(living, bool) else None,
                    "design_ok": ok_design, "pool_ok": ok_pool, "stop_ok": ok_stop,
                    "raw_tail": content[-200:] if len(content) > 200 else content})
    report = {
        "scope": "bare-LLM multitask arm (design + pooled + living in one prompt, strict parse, no fallback)",
        "model_label": args.model_label, "n": n, "parse_fail": parse_fail,
        "design_agreement": round(sum(c["design_ok"] for c in per) / n, 4) if n else 0.0,
        "pooling_agreement": round(sum(c["pool_ok"] for c in per) / n, 4) if n else 0.0,
        "stop_agreement": round(sum(c["stop_ok"] for c in per) / n, 4) if n else 0.0,
        "three_task_mean": round(sum((c["design_ok"] + c["pool_ok"] + c["stop_ok"]) / 3
                                     for c in per) / n, 4) if n else 0.0,
        "per_case": per,
    }
    Path(args.out).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "per_case"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
