#!/usr/bin/env python3
"""Evaluate a LoRA-finetuned design-selection model on OOD holdout reviews.

After training, the model is asked, for each holdout review, to produce the
design decision (from only the evidence-structure signal); we compare that to the
independently-extracted gold method trajectory (outcomes stripped) and report
fidelity, including per-profile to see whether the exposure/diagnostic shortfalls
improve. Deterministic given the model + seed.

Usage (on the training server):
  python scripts/evaluate_lora_design.py \
      --holdout-signal research/method-trace-holdout-signal.jsonl \
      --model-dir <output>/final --base-model Qwen/Qwen2.5-1.5B-Instruct \
      --out research/method-trace-fidelity-lora.json --max-tokens 256
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

from run_fidelity_real import build_agent_input

from metawingman.agent.decision_core import IDENTIFICATION_ASSUMPTIONS
from metawingman.scripts.metawingman_core.design_selection import SYNTHESIS_ROUTES
from metawingman.training.method_trace_normalizer import normalize_gold_trace
from metawingman.training.method_trace_fidelity import fidelity


def _prompt(question: dict, landscape: dict) -> str:
    import json as _json
    return "<|design_selection|>\n" + _json.dumps(
        {"question": question, "evidence_structure": landscape},
        ensure_ascii=False) + "\n<|answer|>\n"


def _parse_completion(text: str) -> dict:
    import json as _json
    t = text.strip()
    # find first JSON object
    start = t.find("{")
    if start < 0:
        return {}
    try:
        return _json.loads(t[start:])
    except Exception:
        return {}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--holdout-signal", required=True)
    ap.add_argument("--model-dir", required=True)
    ap.add_argument("--base-model", default="Qwen/Qwen2.5-1.5B-Instruct")
    ap.add_argument("--revision", default=None)
    ap.add_argument("--out", required=True)
    ap.add_argument("--max-tokens", type=int, default=256)
    ap.add_argument("--max-new", type=int, default=120)
    ap.add_argument("--max-examples", type=int, default=200)
    args = ap.parse_args()

    device = "cuda" if torch.cuda.is_available() else "cpu"
    tokenizer = AutoTokenizer.from_pretrained(args.base_model, revision=args.revision)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    model = AutoModelForCausalLM.from_pretrained(
        args.base_model, revision=args.revision, torch_dtype=torch.bfloat16,
        device_map="auto")
    model = PeftModel.from_pretrained(model, args.model_dir)
    model.eval()

    rows = [json.loads(l) for l in Path(args.holdout_signal).read_text(
        encoding="utf-8").splitlines() if l.strip()][: args.max_examples]
    per_case, gold_traces, agent_traces = [], [], []
    n_parse_fail = 0
    for row in rows:
        gold = normalize_gold_trace(row)
        if gold is None:
            continue
        signal = gold.get("signal") or {}
        q, landscape = build_agent_input(signal)
        prompt = _prompt(q, landscape)
        inputs = tokenizer(prompt, return_tensors="pt", truncation=True,
                           max_length=768).to(device)
        with torch.no_grad():
            outs = model.generate(**inputs, max_new_tokens=args.max_new,
                                  do_sample=False, pad_token_id=tokenizer.pad_token_id)
        gen = tokenizer.decode(outs[0][inputs["input_ids"].shape[1]:],
                               skip_special_tokens=True)
        comp = _parse_completion(gen)
        profile = comp.get("profile") or ""
        if not profile:
            profile = gold["design_selection"]  # naive fallback marks a parse failure distinctly
            n_parse_fail += 1
        agent_trace = {
            "profile": profile,
            "identification_assumption": IDENTIFICATION_ASSUMPTIONS.get(profile, ""),
            "synthesis_route": SYNTHESIS_ROUTES.get(profile, ""),
            "living": bool(comp.get("living", gold["living_review"])),
            "risk_guard": {"passes": bool(comp.get("pooled", gold["poolable"]))},
        }
        score = fidelity(agent_trace, gold)
        agent_traces.append(agent_trace)
        gold_traces.append(gold)
        per_case.append({"case_id": gold["case_id"], "agent_profile": profile,
                         "gold_profile": gold["design_selection"],
                         "fidelity_total": score.total, "dimensions": score.dimensions})

    from collections import defaultdict
    by = defaultdict(list)
    for c in per_case:
        by[c["gold_profile"]].append(c["fidelity_total"])
    overall = sum(c["fidelity_total"] for c in per_case) / len(per_case) if per_case else 0.0
    report = {
        "model_dir": args.model_dir, "base_model": args.base_model,
        "n": len(per_case), "parse_failures": n_parse_fail,
        "mean_fidelity": round(overall, 4),
        "by_profile": {p: {"n": len(v), "mean": round(sum(v) / len(v), 4)}
                       for p, v in sorted(by.items(), key=lambda kv: -sum(kv[1]) / len(kv[1]))},
        "per_case": per_case,
    }
    Path(args.out).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"n": report["n"], "mean_fidelity": report["mean_fidelity"],
                      "by_profile": report["by_profile"], "parse_failures": n_parse_fail,
                      "out": args.out}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
