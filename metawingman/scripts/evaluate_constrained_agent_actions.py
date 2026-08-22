#!/usr/bin/env python3
"""Evaluate base and LoRA agents with frozen action choices, independent of JSON formatting."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from metawingman.scripts.run_multifamily_protocol_training import DEFAULT_SYSTEM_PROMPT, _messages


def _read(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def derive_action_contract(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for row in rows:
        action = row["target_action"]
        grouped[action["type"]].append((action.get("source_section", ""), row["target_decision"]["status"]))
    contract = {}
    for action_type in sorted(grouped):
        source_section, status = Counter(grouped[action_type]).most_common(1)[0][0]
        contract[action_type] = {"target_action": {"type": action_type, "source_section": source_section}, "target_decision": {"status": status}}
    return contract


def classification_metrics(rows: list[dict[str, Any]], labels: list[str]) -> dict[str, Any]:
    if not rows:
        raise ValueError("no evaluation rows")
    confusion = {truth: {prediction: 0 for prediction in labels} for truth in labels}
    for row in rows:
        confusion[row["true"]][row["predicted"]] += 1
    recalls = {}
    precisions = {}
    for label in labels:
        tp = confusion[label][label]
        truth_total = sum(confusion[label].values())
        predicted_total = sum(confusion[truth][label] for truth in labels)
        recalls[label] = tp / truth_total if truth_total else 0.0
        precisions[label] = tp / predicted_total if predicted_total else 0.0
    per_family: dict[str, list[bool]] = defaultdict(list)
    for row in rows:
        per_family[row["family_id"]].append(row["true"] == row["predicted"])
    result = {
        "examples": len(rows),
        "families": len(per_family),
        "record_accuracy": sum(row["true"] == row["predicted"] for row in rows) / len(rows),
        "family_macro_accuracy": sum(sum(values) / len(values) for values in per_family.values()) / len(per_family),
        "macro_recall": sum(recalls.values()) / len(labels),
        "macro_precision": sum(precisions.values()) / len(labels),
        "confusion": confusion,
        "per_label_recall": recalls,
        "per_label_precision": precisions,
        "mean_confidence": sum(float(row.get("confidence", 0.0)) for row in rows) / len(rows),
    }
    if labels == ["exclude", "include"] or set(labels) == {"exclude", "include"}:
        result.update({"include_recall": recalls["include"], "include_precision": precisions["include"], "specificity": recalls["exclude"], "balanced_accuracy": (recalls["include"] + recalls["exclude"]) / 2})
    elif len(labels) == 2:
        result["balanced_accuracy"] = sum(recalls.values()) / 2
    return result


def _conditional_score(model: Any, tokenizer: Any, prompt: str, completion: str, device: Any, max_length: int) -> float:
    import torch

    prompt_ids = tokenizer(prompt, add_special_tokens=False)["input_ids"]
    completion_ids = tokenizer(completion + (tokenizer.eos_token or ""), add_special_tokens=False)["input_ids"]
    if len(completion_ids) >= max_length:
        raise ValueError("completion exceeds evaluation context")
    prompt_ids = prompt_ids[-(max_length - len(completion_ids)):]
    input_ids = torch.tensor([prompt_ids + completion_ids], device=device)
    with torch.no_grad():
        logits = model(input_ids=input_ids).logits[:, :-1, :]
        targets = input_ids[:, 1:]
        token_log_probs = torch.log_softmax(logits, dim=-1).gather(-1, targets.unsqueeze(-1)).squeeze(-1)
    completion_start = max(len(prompt_ids) - 1, 0)
    return float(token_log_probs[0, completion_start:].mean().cpu())


def score_model(model: Any, tokenizer: Any, rows: list[dict[str, Any]], device: Any, *, maximum: int, max_length: int, system_prompt: str) -> dict[str, Any]:
    import torch

    sampled = sorted(rows, key=lambda row: hashlib.sha256(row["example_id"].encode()).hexdigest())[:maximum]
    contract = derive_action_contract(rows); labels = list(contract); scored = []
    model.eval()
    for row in sampled:
        prompt = tokenizer.apply_chat_template(_messages(row, False, system_prompt), tokenize=False, add_generation_prompt=True)
        action_scores = {action: _conditional_score(model, tokenizer, prompt, json.dumps(target, ensure_ascii=False, sort_keys=True), device, max_length) for action, target in contract.items()}
        values = torch.tensor(list(action_scores.values()), dtype=torch.float64)
        probabilities = torch.softmax(values, dim=0).tolist(); predicted = max(action_scores, key=action_scores.get)
        scored.append({"example_id": row["example_id"], "family_id": row["family_id"], "true": row["target_action"]["type"], "predicted": predicted, "confidence": max(probabilities), "action_probabilities": dict(zip(labels, probabilities)), "action_log_likelihoods": action_scores})
    return {"metric_contract": "choice_constrained_conditional_mean_token_log_likelihood", "actions": labels, **classification_metrics(scored, labels), "rows": scored}


def evaluate(args: argparse.Namespace) -> dict[str, Any]:
    import copy
    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    rows = _read(args.data)
    if args.blank_input_field:
        rows = copy.deepcopy(rows)
        for row in rows:
            if args.blank_input_field not in row["input_state"]:
                raise ValueError(f"blank input field is absent: {args.blank_input_field}")
            row["input_state"][args.blank_input_field] = ""
    tokenizer = AutoTokenizer.from_pretrained(args.base_model, revision=args.revision, trust_remote_code=False)
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    dtype = torch.bfloat16 if torch.cuda.is_available() and torch.cuda.is_bf16_supported() else torch.float32
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    base = AutoModelForCausalLM.from_pretrained(args.base_model, revision=args.revision, torch_dtype=dtype, trust_remote_code=False).to(device)
    base_result = score_model(base, tokenizer, rows, device, maximum=args.max_examples, max_length=args.max_length, system_prompt=args.system_prompt)
    student = PeftModel.from_pretrained(base, args.adapter, is_trainable=False).to(device)
    student_result = score_model(student, tokenizer, rows, device, maximum=args.max_examples, max_length=args.max_length, system_prompt=args.system_prompt)
    receipt = {"schema_version": "1.0", "status": "complete", "data_path": str(args.data), "data_sha256": hashlib.sha256(args.data.read_bytes()).hexdigest(), "input_ablation": {"blank_input_field": args.blank_input_field}, "adapter_path": str(args.adapter), "base_model": args.base_model, "base_revision": args.revision, "max_length": args.max_length, "max_examples": args.max_examples, "system_prompt_sha256": hashlib.sha256(args.system_prompt.encode()).hexdigest(), "base": base_result, "student": student_result}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {**receipt, "receipt_path": str(args.output), "receipt_sha256": hashlib.sha256(args.output.read_bytes()).hexdigest()}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--adapter", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--base-model", default="Qwen/Qwen2.5-1.5B-Instruct")
    parser.add_argument("--revision", default="989aa7980e4cf806f80c7fef2b1adb7bc71aa306")
    parser.add_argument("--max-examples", type=int, default=300)
    parser.add_argument("--max-length", type=int, default=1536)
    parser.add_argument("--system-prompt", default=DEFAULT_SYSTEM_PROMPT)
    parser.add_argument("--blank-input-field")
    args = parser.parse_args()
    print(json.dumps(evaluate(args), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
