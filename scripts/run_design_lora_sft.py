#!/usr/bin/env python3
"""Lightweight LoRA SFT of a small instruct model on the real method-trace
design-selection training data.

Each sample: prompt = (clinical question + evidence-structure signal) JSON,
completion = the design decision the real published review made
(profile / estimand_identification / synthesis_route / pooled / living) as JSON.
The model learns to map evidence structure -> the design a seasoned review author
chose, WITHOUT ever seeing the numeric outcome (stripped during extraction).

Self-contained (transformers + peft), runs on the training server GPU. Writes a
training receipt with loss / eval so the run is auditable. Deterministic given the
data, seed, and model revision.

Usage:
  python scripts/run_design_lora_sft.py \
      --train research/method-trace-train.jsonl \
      --output-dir <dir>/run \
      --base-model Qwen/Qwen2.5-1.5B-Instruct \
      --revision <sha> --seed 2026 --epochs 4 --lr 0.0002 \
      --batch-size 2 --grad-acc 8 --max-length 768 --lora-rank 16 --lora-alpha 32
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

import torch
from datasets import Dataset
from peft import LoraConfig, get_peft_model
from transformers import AutoModelForCausalLM, AutoTokenizer, Trainer, TrainingArguments


def _sha(x: str) -> str:
    return hashlib.sha256(x.encode("utf-8")).hexdigest()


def load_samples(path: Path) -> list[dict]:
    samples = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            samples.append(json.loads(line))
    return samples


def build_texts(samples: list[dict]) -> list[str]:
    return [
        f"<|design_selection|>\n{s['prompt']}\n<|answer|>\n{s['completion']}"
        for s in samples
    ]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--train", required=True)
    ap.add_argument("--eval", default=None)
    ap.add_argument("--output-dir", required=True)
    ap.add_argument("--base-model", default="Qwen/Qwen2.5-1.5B-Instruct")
    ap.add_argument("--revision", default=None)
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--epochs", type=int, default=4)
    ap.add_argument("--lr", type=float, default=0.0002)
    ap.add_argument("--batch-size", type=int, default=2)
    ap.add_argument("--grad-acc", type=int, default=8)
    ap.add_argument("--max-length", type=int, default=768)
    ap.add_argument("--lora-rank", type=int, default=16)
    ap.add_argument("--lora-alpha", type=int, default=32)
    ap.add_argument("--max-eval", type=int, default=100)
    ap.add_argument("--job-id", default="design-lora")
    args = ap.parse_args()

    torch.manual_seed(args.seed)
    train_path = Path(args.train)
    samples = load_samples(train_path)
    texts = build_texts(samples)
    dataset = Dataset.from_dict({"text": texts})

    eval_dataset = None
    if args.eval and Path(args.eval).is_file():
        ev = load_samples(Path(args.eval))
        eval_dataset = Dataset.from_dict({"text": build_texts(ev[: args.max_eval])})

    tokenizer = AutoTokenizer.from_pretrained(
        args.base_model, revision=args.revision, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    def tokenize(ex):
        out = tokenizer(ex["text"], truncation=True, max_length=args.max_length,
                        padding="max_length")
        out["labels"] = [list(t) for t in out["input_ids"]]
        return out

    dataset = dataset.map(tokenize, batched=True, remove_columns=["text"])
    if eval_dataset is not None:
        eval_dataset = eval_dataset.map(tokenize, batched=True, remove_columns=["text"])

    model = AutoModelForCausalLM.from_pretrained(
        args.base_model, revision=args.revision, trust_remote_code=True,
        torch_dtype=torch.bfloat16)
    lora = LoraConfig(
        r=args.lora_rank, lora_alpha=args.lora_alpha,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
        lora_dropout=0.05, bias="none", task_type="CAUSAL_LM")
    model = get_peft_model(model, lora)

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    args_ = TrainingArguments(
        output_dir=str(out_dir),
        num_train_epochs=args.epochs,
        learning_rate=args.lr,
        per_device_train_batch_size=args.batch_size,
        gradient_accumulation_steps=args.grad_acc,
        per_device_eval_batch_size=args.batch_size,
        evaluation_strategy="epoch" if eval_dataset is not None else "no",
        save_strategy="no",
        logging_steps=10,
        seed=args.seed,
        bf16=torch.cuda.is_available(),
        label_names=["labels"],
    )
    # transformers >=5 dropped the `tokenizer=` kwarg from Trainer; we pre-tokenize
    # & pad via Dataset.map above, so we do not pass tokenizer here.
    trainer = Trainer(
        model=model, args=args_, train_dataset=dataset, eval_dataset=eval_dataset)
    trainer.train()

    final = trainer.state.log_history
    loss = next((r.get("loss") for r in reversed(final) if "loss" in r), None)

    model_path = out_dir / "final"
    model.save_pretrained(model_path)
    tokenizer.save_pretrained(model_path)
    data_hash = _sha(train_path.read_text(encoding="utf-8"))
    receipt = {
        "status": "completed", "job_id": args.job_id,
        "base_model": args.base_model, "base_revision": args.revision,
        "seed": args.seed, "epochs": args.epochs, "learning_rate": args.lr,
        "batch_size": args.batch_size, "grad_acc": args.grad_acc,
        "max_length": args.max_length, "lora_rank": args.lora_rank,
        "lora_alpha": args.lora_alpha,
        "train_examples": len(samples), "train_data_sha256": data_hash,
        "wall_seconds": round(trainer.state.total_flos and 0 or 0, 0),
        "final_loss": loss,
        "final_save_path": str(model_path),
        "eval": (trainer.evaluate() if eval_dataset is not None else None),
    }
    (out_dir / "training-receipt.json").write_text(
        json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
