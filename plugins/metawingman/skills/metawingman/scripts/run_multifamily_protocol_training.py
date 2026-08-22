#!/usr/bin/env python3
"""Train a family-held-out protocol-action LoRA and score semantic actions."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import time
from collections import Counter, defaultdict
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_SYSTEM_PROMPT = (
    "Act as a Skill-driven MetaWingman methods agent. Convert the source-grounded review state "
    "into a method action, decision, and method trace. Preserve Review Question Certificate "
    "reasoning, Socratic stage reflection, decision-aware topic and synthesis co-design, "
    "risk-impact evidence acquisition, disconfirmation design, evidence-gap anchoring, step "
    "verification, stopping rules, and meta-update learning. Return only JSON with "
    "target_action, target_decision, and target_method_trace."
)


def _read(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").split("\n") if line.strip()]


def load_corpus(train_path: Path, dev_path: Path, *, min_train: int = 200, min_dev: int = 50) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    train, dev = _read(train_path), _read(dev_path)
    if len(train) < min_train or len(dev) < min_dev:
        raise ValueError("insufficient multifamily corpus")
    overlap = {row["family_id"] for row in train} & {row["family_id"] for row in dev}
    if overlap:
        raise ValueError("train/development family overlap")
    return train, dev


def load_test_corpus(train_path: Path, dev_path: Path, test_path: Path, *, min_train: int = 200, min_dev: int = 50, min_test: int = 50) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    train, dev = load_corpus(train_path, dev_path, min_train=min_train, min_dev=min_dev)
    test = _read(test_path)
    if len(test) < min_test:
        raise ValueError("insufficient test corpus")
    test_families = {row["family_id"] for row in test}
    if test_families & ({row["family_id"] for row in train} | {row["family_id"] for row in dev}):
        raise ValueError("test family overlap")
    return train, dev, test


def _balance_action_rows(rows: list[dict[str, Any]], *, seed: int) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[row["target_action"]["type"]].append(row)
    if not grouped:
        return []
    target = max(len(values) for values in grouped.values())
    balanced: list[dict[str, Any]] = []
    for action_type in sorted(grouped):
        source_rows = sorted(grouped[action_type], key=lambda row: hashlib.sha256(str(row["example_id"]).encode()).hexdigest())
        balanced.extend(deepcopy(source_rows))
        rng = random.Random(f"{seed}:{action_type}")
        for index in range(target - len(source_rows)):
            clone = deepcopy(source_rows[index % len(source_rows)])
            clone["balancing_source_example_id"] = clone["example_id"]
            clone["example_id"] = f"{clone['example_id']}#balance-{index + 1}-{rng.randrange(10**9):09d}"
            balanced.append(clone)
    return sorted(balanced, key=lambda row: hashlib.sha256(str(row["example_id"]).encode()).hexdigest())


def _fallback_method_trace(row: dict[str, Any]) -> dict[str, str]:
    action = row.get("target_action", {}).get("type", "method_action")
    anchor = str(row.get("input_state", {}).get("source_section") or action)
    return {
        "decision_tension": f"The {action} decision can change the review question, evidence base, or conclusion.",
        "disconfirmation_design": "Seek a missing source, incompatible criterion, unsupported estimand, or alternative interpretation that would change this action.",
        "evidence_gap_anchor": anchor,
        "stopping_rule": "Stop only after the action is source-grounded, method-compatible, and no conclusion-changing gap remains for this step.",
    }


def _messages(row: dict[str, Any], target: bool, system_prompt: str = DEFAULT_SYSTEM_PROMPT) -> list[dict[str, str]]:
    messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": json.dumps(row["input_state"], ensure_ascii=False)}]
    if target:
        messages.append({"role": "assistant", "content": json.dumps({"target_action": row["target_action"], "target_decision": row["target_decision"], "target_method_trace": row.get("target_method_trace") or _fallback_method_trace(row)}, ensure_ascii=False, sort_keys=True)})
    return messages


def _parse(text: str) -> dict[str, Any] | None:
    try:
        return json.loads(text[text.index("{"):text.rindex("}") + 1])
    except (ValueError, json.JSONDecodeError):
        return None


def _encode_supervised(row: dict[str, Any], tokenizer: Any, system_prompt: str, *, max_length: int) -> dict[str, list[int]]:
    prompt = tokenizer.apply_chat_template(_messages(row, False, system_prompt), tokenize=False, add_generation_prompt=True)
    full = tokenizer.apply_chat_template(_messages(row, True, system_prompt), tokenize=False, add_generation_prompt=False)
    prompt_ids = tokenizer(prompt, add_special_tokens=False)["input_ids"]
    full_ids = tokenizer(full, add_special_tokens=False)["input_ids"]
    common = 0
    for left, right in zip(prompt_ids, full_ids):
        if left != right:
            break
        common += 1
    completion_ids = full_ids[common:]
    if not completion_ids:
        raise ValueError("assistant completion produced no supervised tokens")
    if len(completion_ids) >= max_length:
        raise ValueError("assistant completion exceeds training context")
    retained_prompt = prompt_ids[: max_length - len(completion_ids)]
    input_ids = retained_prompt + completion_ids
    labels = [-100] * len(retained_prompt) + completion_ids
    return {"input_ids": input_ids, "labels": labels}


def _score(model: Any, tokenizer: Any, rows: list[dict[str, Any]], device: Any, maximum: int, system_prompt: str, *, max_input_length: int) -> dict[str, Any]:
    import torch
    sampled = sorted(rows, key=lambda row: hashlib.sha256(row["example_id"].encode()).hexdigest())[:maximum]
    results = []
    model.eval()
    for row in sampled:
        prompt = tokenizer.apply_chat_template(_messages(row, False, system_prompt), tokenize=False, add_generation_prompt=True)
        encoded = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=max_input_length).to(device)
        with torch.no_grad():
            generated = model.generate(**encoded, max_new_tokens=192, do_sample=False, pad_token_id=tokenizer.eos_token_id)
        text = tokenizer.decode(generated[0][encoded["input_ids"].shape[1]:], skip_special_tokens=True)
        parsed = _parse(text); action = parsed.get("target_action") if isinstance(parsed, dict) else None
        decision = parsed.get("target_decision") if isinstance(parsed, dict) else None
        method_trace = parsed.get("target_method_trace") if isinstance(parsed, dict) else None
        predicted_type = action.get("type") if isinstance(action, dict) else None
        true_type = row["target_action"]["type"]
        trace_keys = {"decision_tension", "disconfirmation_design", "evidence_gap_anchor", "stopping_rule"}
        results.append({"example_id": row["example_id"], "family_id": row["family_id"], "json_valid": parsed is not None,
                        "true_action_type": true_type, "predicted_action_type": predicted_type,
                        "action_semantic_correct": predicted_type == true_type,
                        "decision_correct": isinstance(decision, dict) and decision.get("status") == row["target_decision"]["status"],
                        "method_trace_complete": isinstance(method_trace, dict) and trace_keys <= set(method_trace)})
    n = len(results)
    binary = {row["true_action_type"] for row in results} <= {"include", "exclude"}
    extra = {}
    if binary:
        tp = sum(row["true_action_type"] == "include" and row["predicted_action_type"] == "include" for row in results)
        fn = sum(row["true_action_type"] == "include" and row["predicted_action_type"] != "include" for row in results)
        tn = sum(row["true_action_type"] == "exclude" and row["predicted_action_type"] == "exclude" for row in results)
        fp = sum(row["true_action_type"] == "exclude" and row["predicted_action_type"] != "exclude" for row in results)
        recall = tp / (tp + fn) if tp + fn else 0.0; specificity = tn / (tn + fp) if tn + fp else 0.0
        extra = {"include_recall": recall, "include_precision": tp / (tp + fp) if tp + fp else 0.0,
                 "specificity": specificity, "balanced_accuracy": (recall + specificity) / 2,
                 "confusion": {"tp": tp, "fn": fn, "tn": tn, "fp": fp}}
    return {"examples": n, "families": len({row["family_id"] for row in results}),
            "json_valid_rate": sum(row["json_valid"] for row in results) / n,
            "semantic_action_accuracy": sum(row["action_semantic_correct"] for row in results) / n,
            "decision_accuracy": sum(row["decision_correct"] for row in results) / n,
            "complete_method_action_accuracy": sum(row["action_semantic_correct"] and row["decision_correct"] and row["method_trace_complete"] for row in results) / n,
            "method_trace_complete_rate": sum(row["method_trace_complete"] for row in results) / n, **extra, "rows": results}


def train(args: argparse.Namespace) -> dict[str, Any]:
    import torch
    from peft import LoraConfig, get_peft_model
    from torch.utils.data import DataLoader
    from transformers import AutoModelForCausalLM, AutoTokenizer

    if args.test:
        train_rows, dev_rows, test_rows = load_test_corpus(args.train, args.development, args.test)
    else:
        train_rows, dev_rows = load_corpus(args.train, args.development); test_rows = []
    raw_training_examples = len(train_rows); raw_action_counts = dict(Counter(row["target_action"]["type"] for row in train_rows))
    train_rows = _balance_action_rows(train_rows, seed=args.seed)
    random.seed(args.seed); torch.manual_seed(args.seed)
    if torch.cuda.is_available(): torch.cuda.manual_seed_all(args.seed)
    started = datetime.now(timezone.utc).isoformat(); clock = time.monotonic()
    tokenizer = AutoTokenizer.from_pretrained(args.base_model, revision=args.revision, trust_remote_code=False)
    if tokenizer.pad_token_id is None: tokenizer.pad_token = tokenizer.eos_token
    dtype = torch.bfloat16 if torch.cuda.is_available() and torch.cuda.is_bf16_supported() else torch.float32
    model = AutoModelForCausalLM.from_pretrained(args.base_model, revision=args.revision, torch_dtype=dtype, trust_remote_code=False)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu"); model.to(device)
    baseline = _score(model, tokenizer, dev_rows, device, args.max_eval_examples, args.system_prompt, max_input_length=args.max_length)
    baseline_test = _score(model, tokenizer, test_rows, device, args.max_eval_examples, args.system_prompt, max_input_length=args.max_length) if test_rows else None
    model = get_peft_model(model, LoraConfig(r=args.lora_rank, lora_alpha=args.lora_alpha, lora_dropout=0.05, bias="none", task_type="CAUSAL_LM",
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]))

    encoded_rows = [_encode_supervised(row, tokenizer, args.system_prompt, max_length=args.max_length) for row in train_rows]
    def collate(batch: list[dict[str, list[int]]]) -> dict[str, Any]:
        width = max(len(row["input_ids"]) for row in batch)
        inputs, labels, masks = [], [], []
        for row in batch:
            pad = width - len(row["input_ids"])
            inputs.append(row["input_ids"] + [tokenizer.pad_token_id] * pad); labels.append(row["labels"] + [-100] * pad); masks.append([1] * len(row["input_ids"]) + [0] * pad)
        return {"input_ids": torch.tensor(inputs), "labels": torch.tensor(labels), "attention_mask": torch.tensor(masks)}

    loader = DataLoader(encoded_rows, batch_size=args.batch_size, shuffle=True, collate_fn=collate, generator=torch.Generator().manual_seed(args.seed))
    optimizer = torch.optim.AdamW((p for p in model.parameters() if p.requires_grad), lr=args.learning_rate)
    losses = []; updates = 0; model.train(); optimizer.zero_grad(set_to_none=True)
    for _ in range(args.epochs):
        for index, batch in enumerate(loader, 1):
            batch = {key: value.to(device) for key, value in batch.items()}
            loss = model(**batch).loss / args.gradient_accumulation; loss.backward(); losses.append(float(loss.detach().cpu()) * args.gradient_accumulation)
            if index % args.gradient_accumulation == 0 or index == len(loader):
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0); optimizer.step(); optimizer.zero_grad(set_to_none=True); updates += 1
    student = _score(model, tokenizer, dev_rows, device, args.max_eval_examples, args.system_prompt, max_input_length=args.max_length)
    student_test = _score(model, tokenizer, test_rows, device, args.max_eval_examples, args.system_prompt, max_input_length=args.max_length) if test_rows else None
    args.output_dir.mkdir(parents=True, exist_ok=False); adapter = args.output_dir / "adapter"; model.save_pretrained(adapter, safe_serialization=True); tokenizer.save_pretrained(adapter)
    receipt = {"schema_version": "1.0", "status": "completed_family_heldout_development", "scientific_scope": args.scientific_scope,
               "primary_metric": "complete_method_action_accuracy", "semantic_action_metric_role": "component_metric", "strict_json_metric_role": "secondary_format_metric",
               "seed": args.seed, "base_model": args.base_model, "base_revision": args.revision,
               "training_examples": len(train_rows), "raw_training_examples": raw_training_examples,
               "training_action_balancing": {"strategy": "deterministic_upsample_to_largest_action_class", "raw_action_counts": raw_action_counts, "balanced_action_counts": dict(Counter(row["target_action"]["type"] for row in train_rows))},
               "training_families": len({row['family_id'] for row in train_rows}),
               "development_examples": len(dev_rows), "development_families": len({row['family_id'] for row in dev_rows}),
               "epochs": args.epochs, "optimizer_updates": updates, "loss": {"first": losses[0], "last": losses[-1], "mean": sum(losses)/len(losses)},
               "test_examples": len(test_rows), "test_families": len({row['family_id'] for row in test_rows}),
               "evaluation": {"development": {"base": baseline, "student": student}, "test": {"base": baseline_test, "student": student_test} if test_rows else None}, "started_at_utc": started,
               "completed_at_utc": datetime.now(timezone.utc).isoformat(), "wall_seconds": time.monotonic()-clock}
    receipt_path = args.output_dir / "training-receipt.json"; receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True)+"\n", encoding="utf-8")
    return {"receipt": str(receipt_path), **receipt}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--train", type=Path, required=True); parser.add_argument("--development", type=Path, required=True); parser.add_argument("--test", type=Path); parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--base-model", default="Qwen/Qwen2.5-1.5B-Instruct"); parser.add_argument("--revision", default="989aa7980e4cf806f80c7fef2b1adb7bc71aa306")
    parser.add_argument("--seed", type=int, default=20260822); parser.add_argument("--epochs", type=int, default=2); parser.add_argument("--batch-size", type=int, default=2)
    parser.add_argument("--gradient-accumulation", type=int, default=8); parser.add_argument("--learning-rate", type=float, default=2e-4); parser.add_argument("--max-length", type=int, default=768)
    parser.add_argument("--max-eval-examples", type=int, default=200); parser.add_argument("--lora-rank", type=int, default=16); parser.add_argument("--lora-alpha", type=int, default=32)
    parser.add_argument("--scientific-scope", default="protocol_action_stage_only"); parser.add_argument("--system-prompt", default=DEFAULT_SYSTEM_PROMPT)
    args = parser.parse_args(); print(json.dumps(train(args), indent=2, sort_keys=True)); return 0


if __name__ == "__main__": raise SystemExit(main())
