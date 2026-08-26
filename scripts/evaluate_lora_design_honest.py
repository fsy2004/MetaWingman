#!/usr/bin/env python3
"""Honest strict evaluation of a LoRA design model on the OOD holdout (public).

Strict rules (iron rule):
  * parse the model's generated text as a JSON decision;
  * profile missing/unparseable -> the case scores fidelity 0 (parse failure);
  * 'living' / 'pooled' fields missing -> the corresponding dimensions score 0
    (never fall back to the gold value);
  * no fallback to the reference in any dimension.

The same code path runs on a training server via the private handoff wrapper;
this file is the public, re-runnable module. Weighted fidelity uses the same
weights as metawingman/training/method_trace_fidelity.py.

Usage:
  python scripts/evaluate_lora_design_honest.py \
      --holdout-signal research/method-trace-holdout-signal.jsonl \
      --model-dir <output>/final --base-model Qwen/Qwen2.5-1.5B-Instruct \
      --out research/method-trace-fidelity-lora-honest.json --max-new 120
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from run_fidelity_real import build_agent_input

from metawingman.agent.decision_core import IDENTIFICATION_ASSUMPTIONS
from metawingman.scripts.metawingman_core.design_selection import SYNTHESIS_ROUTES
from metawingman.training.method_trace_fidelity import WEIGHTS
from metawingman.training.method_trace_normalizer import normalize_gold_trace


def _prompt(question: dict, landscape: dict) -> str:
    return ("<|design_selection|>\n" + json.dumps(
        {"question": question, "evidence_structure": landscape},
        ensure_ascii=False) + "\n<|answer|>\n")


def _parse_completion(text: str) -> dict:
    t = text.strip()
    start = t.find("{")
    if start < 0:
        return {}
    try:
        parsed = json.loads(t[start:])
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def score_case(comp: dict, gold: dict) -> tuple[float, dict[str, float], int, int]:
    """Strict per-case scoring. Returns (total, dims, parse_fail, partial_missing)."""
    dims = {k: 0.0 for k in WEIGHTS}
    parse_fail = partial = 0
    prof = comp.get("profile", "")
    if not prof:
        return 0.0, dims, 1, 0
    if prof == gold["design_selection"]:
        dims["design_selection"] = 1.0
        dims["estimand_identification"] = (
            1.0 if IDENTIFICATION_ASSUMPTIONS.get(prof, "") == gold.get("estimand_identification", "")
            else 0.0)
    agent_route = (SYNTHESIS_ROUTES.get(prof, "") or "").casefold()
    gold_route = (gold.get("synthesis_choice")
                  or SYNTHESIS_ROUTES.get(gold["design_selection"], "") or "").casefold()
    dims["synthesis_route"] = 1.0 if (agent_route and agent_route == gold_route) else 0.0
    if "living" in comp and isinstance(comp["living"], bool):
        dims["stop_decision"] = 1.0 if comp["living"] == bool(gold.get("living_review", False)) else 0.0
    else:
        partial += 1
    if "pooled" in comp and isinstance(comp["pooled"], bool):
        dims["guard_consistency"] = 1.0 if comp["pooled"] == bool(gold.get("poolable", True)) else 0.0
    else:
        partial += 1
    total = round(sum(WEIGHTS[k] * dims[k] for k in WEIGHTS), 4)
    return total, dims, parse_fail, partial


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--holdout-signal", required=True)
    ap.add_argument("--model-dir", required=True)
    ap.add_argument("--base-model", default="Qwen/Qwen2.5-1.5B-Instruct")
    ap.add_argument("--max-new", type=int, default=120)
    ap.add_argument("--max-seq", type=int, default=768)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    device = "cuda" if torch.cuda.is_available() else "cpu"
    tokenizer = AutoTokenizer.from_pretrained(args.base_model)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    model = AutoModelForCausalLM.from_pretrained(
        args.base_model, torch_dtype=torch.bfloat16, device_map="auto")
    model = PeftModel.from_pretrained(model, args.model_dir)
    model.eval()

    rows = [json.loads(l) for l in Path(args.holdout_signal).read_text(
        encoding="utf-8").splitlines() if l.strip()]
    per, totals, by = [], [], {}
    parse_fail = partial = n = 0
    for row in rows:
        gold = normalize_gold_trace(row)
        if gold is None:
            continue
        q, landscape = build_agent_input(gold.get("signal") or {})
        prompt = _prompt(q, landscape)
        inputs = tokenizer(prompt, return_tensors="pt", truncation=True,
                           max_length=args.max_seq).to(device)
        with torch.no_grad():
            outs = model.generate(**inputs, max_new_tokens=args.max_new, do_sample=False,
                                  pad_token_id=tokenizer.pad_token_id)
        gen = tokenizer.decode(outs[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True)
        comp = _parse_completion(gen)
        total, dims, pf, pm = score_case(comp, gold)
        parse_fail += pf
        partial += pm
        n += 1
        totals.append(total)
        by.setdefault(gold["design_selection"], []).append(total)
        per.append({"case_id": gold["case_id"], "gold": gold["design_selection"],
                    "agent": comp.get("profile", "") or "(parse_fail)",
                    "fid": total, "dims": dims})

    report = {
        "scope": (f"honest strict evaluation of a LoRA design model (base {args.base_model}, "
                  f"adapter {args.model_dir}) on OOD holdout; no fallback to gold"),
        "n": n, "parse_fail": parse_fail, "n_partial_missing": partial,
        "mean_fidelity": round(sum(totals) / n, 4) if n else 0.0,
        "mean_dimensions": {k: round(sum(c["dims"][k] for c in per) / n, 4) if n else 0.0
                            for k in WEIGHTS},
        "by_profile": {p: {"n": len(v), "mean": round(sum(v) / len(v), 4)}
                       for p, v in sorted(by.items(), key=lambda kv: -sum(kv[1]) / len(kv[1]))},
        "per_case": per,
        "harness": {"max_new_tokens": args.max_new, "max_seq": args.max_seq,
                    "do_sample": False, "strict_parse": True},
    }
    Path(args.out).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"n": n, "parse_fail": parse_fail, "partial_missing": partial,
                      "mean_fidelity": report["mean_fidelity"],
                      "mean_dimensions": report["mean_dimensions"],
                      "by_profile": report["by_profile"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
