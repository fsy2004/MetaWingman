#!/usr/bin/env python3
"""Train and score a development-only protocol-action LoRA from a ready export."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import random
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SYSTEM_PROMPT = (
    "You are the Skill-driven protocol-action component of MetaWingman. Convert "
    "the supplied source-anchored methods state into exactly one JSON object with "
    "target_action and target_decision. Preserve the original method loop inside "
    "target_action.method_trace: Review Question Certificate linkage, Socratic "
    "stage reflection, PRM-style step verification, and meta-update learning. "
    "Use only the supplied state and preserve its scope."
)


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_training_examples(export_path: Path, readiness_path: Path) -> list[dict[str, Any]]:
    export = json.loads(export_path.read_text(encoding="utf-8"))
    readiness = json.loads(readiness_path.read_text(encoding="utf-8"))
    if readiness.get("ready_for_student_training") is not True or readiness.get("blockers"):
        raise ValueError("distillation readiness is not green")
    eligible = set(readiness.get("eligible_example_ids") or [])
    examples = [
        row for row in export.get("examples", [])
        if row.get("example_id") in eligible
        and row.get("training_disposition") in {
            "positive_demonstration", "negative_decision", "abstention_demonstration",
        }
    ]
    if len(examples) < 8:
        raise ValueError("at least eight governed examples are required for bootstrap training")
    if {row.get("canonical_stage") for row in examples} != {"protocol_registration"}:
        raise ValueError("this bounded trainer accepts protocol-registration examples only")
    return examples


def deterministic_split(examples: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in examples:
        groups[str(row["target_action"]["type"])].append(row)
    train: list[dict[str, Any]] = []
    dev: list[dict[str, Any]] = []
    for rows in groups.values():
        ordered = sorted(rows, key=lambda row: hashlib.sha256(row["example_id"].encode()).hexdigest())
        if len(ordered) >= 2:
            dev.append(ordered[-1])
            train.extend(ordered[:-1])
        else:
            train.extend(ordered)
    if not dev:
        ordered = sorted(train, key=lambda row: hashlib.sha256(row["example_id"].encode()).hexdigest())
        dev, train = ordered[-2:], ordered[:-2]
    return train, dev


def _messages(row: dict[str, Any], *, with_target: bool) -> list[dict[str, str]]:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": json.dumps(row["input_state"], ensure_ascii=False, sort_keys=True)},
    ]
    if with_target:
        messages.append({"role": "assistant", "content": json.dumps({
            "target_action": row["target_action"], "target_decision": row["target_decision"],
        }, ensure_ascii=False, sort_keys=True)})
    return messages


def _parse_json(text: str) -> dict[str, Any] | None:
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        value = json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def _score(model: Any, tokenizer: Any, examples: list[dict[str, Any]], device: Any) -> dict[str, Any]:
    import torch
    rows = []
    model.eval()
    for example in examples:
        prompt = tokenizer.apply_chat_template(_messages(example, with_target=False), tokenize=False, add_generation_prompt=True)
        encoded = tokenizer(prompt, return_tensors="pt").to(device)
        with torch.no_grad():
            generated = model.generate(**encoded, max_new_tokens=640, do_sample=False, pad_token_id=tokenizer.eos_token_id)
        text = tokenizer.decode(generated[0][encoded["input_ids"].shape[1]:], skip_special_tokens=True)
        parsed = _parse_json(text)
        action = parsed.get("target_action") if isinstance(parsed, dict) else None
        decision = parsed.get("target_decision") if isinstance(parsed, dict) else None
        method_trace = action.get("method_trace") if isinstance(action, dict) else None
        trace_keys = {
            "review_question_certificate_link",
            "socratic_stage_reflection",
            "step_verification",
            "meta_update",
        }
        rows.append({
            "example_id": example["example_id"], "prediction_sha256": hashlib.sha256(text.encode()).hexdigest(),
            "json_valid": parsed is not None,
            "action_type_exact": isinstance(action, dict) and action.get("type") == example["target_action"]["type"],
            "section_exact": isinstance(action, dict) and action.get("source_section") == example["target_action"]["source_section"],
            "decision_exact": isinstance(decision, dict) and decision.get("status") == example["target_decision"]["status"],
            "method_trace_complete": isinstance(method_trace, dict) and trace_keys <= set(method_trace),
        })
    total = len(rows)
    return {
        "examples": total,
        "json_valid_rate": sum(row["json_valid"] for row in rows) / total,
        "complete_action_accuracy": sum(row["action_type_exact"] and row["section_exact"] and row["decision_exact"] for row in rows) / total,
        "method_trace_complete_rate": sum(row["method_trace_complete"] for row in rows) / total,
        "complete_method_action_accuracy": sum(
            row["action_type_exact"] and row["section_exact"] and row["decision_exact"] and row["method_trace_complete"]
            for row in rows
        ) / total,
        "rows": rows,
    }


def train(args: argparse.Namespace) -> dict[str, Any]:
    import torch
    from peft import LoraConfig, get_peft_model
    from transformers import AutoModelForCausalLM, AutoTokenizer

    examples = load_training_examples(args.export, args.readiness)
    train_rows, dev_rows = deterministic_split(examples)
    random.seed(args.seed)
    torch.manual_seed(args.seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(args.seed)
    started = datetime.now(timezone.utc).isoformat()
    start_time = time.monotonic()
    tokenizer = AutoTokenizer.from_pretrained(args.base_model, revision=args.revision, trust_remote_code=False)
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    dtype = torch.bfloat16 if torch.cuda.is_available() and torch.cuda.is_bf16_supported() else torch.float32
    model = AutoModelForCausalLM.from_pretrained(args.base_model, revision=args.revision, dtype=dtype, trust_remote_code=False)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)
    baseline = _score(model, tokenizer, dev_rows, device)
    config = LoraConfig(
        r=args.lora_rank, lora_alpha=args.lora_alpha, lora_dropout=args.lora_dropout,
        bias="none", task_type="CAUSAL_LM",
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
    )
    model = get_peft_model(model, config)
    model.train()
    optimizer = torch.optim.AdamW((parameter for parameter in model.parameters() if parameter.requires_grad), lr=args.learning_rate)
    losses: list[float] = []
    optimizer.zero_grad(set_to_none=True)
    update = 0
    for epoch in range(args.epochs):
        order = list(train_rows)
        random.Random(args.seed + epoch).shuffle(order)
        for index, row in enumerate(order, start=1):
            prompt_text = tokenizer.apply_chat_template(_messages(row, with_target=False), tokenize=False, add_generation_prompt=True)
            full_text = tokenizer.apply_chat_template(_messages(row, with_target=True), tokenize=False, add_generation_prompt=False)
            prompt_ids = tokenizer(prompt_text, add_special_tokens=False)["input_ids"]
            encoded = tokenizer(full_text, return_tensors="pt", truncation=True, max_length=args.max_length).to(device)
            labels = encoded["input_ids"].clone()
            labels[:, : min(len(prompt_ids), labels.shape[1])] = -100
            loss = model(**encoded, labels=labels).loss / args.gradient_accumulation
            loss.backward(); losses.append(float(loss.detach().cpu()) * args.gradient_accumulation)
            if index % args.gradient_accumulation == 0 or index == len(order):
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                optimizer.step(); optimizer.zero_grad(set_to_none=True); update += 1
    trained = _score(model, tokenizer, dev_rows, device)
    adapter_dir = args.output_dir / "adapter"
    adapter_dir.mkdir(parents=True, exist_ok=False)
    model.save_pretrained(adapter_dir, safe_serialization=True)
    tokenizer.save_pretrained(adapter_dir)
    metrics_path = args.output_dir / "evaluation.json"
    metrics = {"baseline": baseline, "student": trained}
    metrics_path.write_text(json.dumps(metrics, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    artifacts = {}
    for path in sorted(adapter_dir.rglob("*")):
        if path.is_file():
            artifacts[path.relative_to(args.output_dir).as_posix()] = {"bytes": path.stat().st_size, "sha256": _sha(path)}
    artifacts[metrics_path.name] = {"bytes": metrics_path.stat().st_size, "sha256": _sha(metrics_path)}
    receipt = {
        "schema_version": "1.0", "job_id": args.job_id, "status": "completed_development_bootstrap",
        "scientific_claim_status": "no_generalization_claim_single_development_family",
        "base_model": args.base_model, "base_revision": args.revision, "seed": args.seed,
        "training_examples": len(train_rows), "development_examples": len(dev_rows),
        "epochs": args.epochs, "optimizer_updates": update, "learning_rate": args.learning_rate,
        "lora": {"rank": args.lora_rank, "alpha": args.lora_alpha, "dropout": args.lora_dropout},
        "loss": {"first": losses[0], "last": losses[-1], "mean": sum(losses) / len(losses)},
        "evaluation": metrics, "input_hashes": {"export": _sha(args.export), "readiness": _sha(args.readiness)},
        "started_at_utc": started, "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "wall_seconds": time.monotonic() - start_time, "artifacts": artifacts,
    }
    receipt_path = args.output_dir / "training-receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"job_id": args.job_id, "status": receipt["status"], "receipt": str(receipt_path), "receipt_sha256": _sha(receipt_path), "evaluation": metrics}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--export", type=Path, required=True)
    parser.add_argument("--readiness", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--base-model", default="Qwen/Qwen2.5-1.5B-Instruct")
    parser.add_argument("--revision", default="989aa7980e4cf806f80c7fef2b1adb7bc71aa306")
    parser.add_argument("--seed", type=int, default=20260822)
    parser.add_argument("--epochs", type=int, default=8)
    parser.add_argument("--learning-rate", type=float, default=2e-4)
    parser.add_argument("--gradient-accumulation", type=int, default=4)
    parser.add_argument("--max-length", type=int, default=1024)
    parser.add_argument("--lora-rank", type=int, default=8)
    parser.add_argument("--lora-alpha", type=int, default=16)
    parser.add_argument("--lora-dropout", type=float, default=0.05)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=False)
    print(json.dumps(train(args), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
