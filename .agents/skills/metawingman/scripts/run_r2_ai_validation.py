#!/usr/bin/env python3
"""R2-AI independent validation runner (server side).

Runs the preregistered C3 configuration (hosted DeepSeek model + the two 12k
retrained components as verifiers) over:
  (a) the 200-record independent-validation blind sample (section-role), and
  (b) a pilot-style 200-query retrieval sample drawn from the 12k dev split.

Design grounding: docs/architecture/ai-only-pilot-preregistration.md and
docs/architecture/label-and-heldout-validation-protocol.md. The C3 prompt text
is copied verbatim from run_ai_only_pilot.py so its sha256 matches the frozen
pilot prompt. Deviations (documented in the R2 results doc):
  * the `biomedical_context` input_document field is omitted for both tasks —
    the C3 prompt does not reference it, and for the blind section-role tasks
    including it would leak the reference stratum (blindness).

The weak-label key is NEVER read on the server during prediction; scoring
happens locally against the sealed key.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from collections import defaultdict
from pathlib import Path

ROLE_DEFINITIONS = (
    "search = strategy for finding studies; "
    "eligibility = inclusion and exclusion criteria; "
    "selection = study selection process; "
    "extraction = data extraction; "
    "appraisal = risk of bias or quality assessment; "
    "synthesis = statistical or narrative pooling of results; "
    "certainty = GRADE or certainty assessment; "
    "protocol = planned methods."
)

C3_PROMPTS = {
    "section_role": (
        "Predict the systematic-review workflow role of the passage in the "
        "input document using these role definitions: " + ROLE_DEFINITIONS +
        " A trained domain verifier predicted the role recorded in the input "
        "document; verify or correct it and return your final answer."
    ),
    "retrieval": (
        "Select the passage, by its index, that best supports the query in "
        "the input document. A trained retrieval verifier ranked the "
        "candidates as recorded in the input document; verify or correct it "
        "and return your final index."
    ),
}


def _stable_sample(items: list, size: int, seed: int, key: str) -> list:
    return sorted(
        items, key=lambda item: hashlib.sha256(f"{seed}:{item[key]}".encode()).hexdigest()
    )[:size]


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _hash_tree(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(item for item in root.rglob("*") if item.is_file())
    }


def _load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _load_section_role_model(final_dir: Path, device: str):
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(str(final_dir))
    model = AutoModelForSequenceClassification.from_pretrained(str(final_dir))
    model.to(device)
    model.eval()
    return model, tokenizer


def _load_retrieval_model(final_dir: Path, device: str):
    import torch
    from transformers import AutoModel, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(str(final_dir))
    model = AutoModel.from_pretrained(str(final_dir))
    model.to(device)
    model.eval()
    return model, tokenizer


def _sr_predict(model, tokenizer, texts: list[str], device: str, batch_size: int = 32) -> list[str]:
    import torch

    id2label = model.config.id2label
    predictions: list[str] = []
    for start in range(0, len(texts), batch_size):
        batch = tokenizer(
            texts[start:start + batch_size],
            padding=True, truncation=True, max_length=512, return_tensors="pt",
        ).to(device)
        with torch.no_grad():
            logits = model(**batch).logits
        ids = logits.argmax(dim=-1).tolist()
        for i in ids:
            predictions.append(id2label.get(i) if i in id2label else id2label.get(str(i), "?"))
    return predictions


def _er_encode(model, tokenizer, texts: list[str], device: str, max_length: int) -> "torch.Tensor":
    import torch
    import torch.nn.functional as functional

    vectors = []
    for start in range(0, len(texts), 32):
        batch = tokenizer(
            texts[start:start + 32],
            padding=True, truncation=True, max_length=max_length, return_tensors="pt",
        ).to(device)
        with torch.no_grad():
            vectors.append(functional.normalize(model(**batch).last_hidden_state[:, 0], dim=-1))
    return torch.cat(vectors)


def build_sr_tasks(blind_tasks: Path, model, tokenizer, device: str, out_dir: Path) -> tuple[list[dict], list[dict]]:
    """Verifier predictions + C3 tasks + manifest for the 200-record blind sample."""
    rows = _load_jsonl(blind_tasks)
    passages: list[dict] = []  # (record_id, pmcid, section_path, section_title, text)
    for row in rows:
        for passage in row["passages"]:
            passages.append({
                "record_id": row["record_id"],
                "pmcid": row.get("pmcid"),
                "section_path": passage["section_path"],
                "section_title": passage["section_title"],
                "text": passage["passage"],
            })
    predictions = _sr_predict(model, tokenizer, [p["text"] for p in passages], device)
    tasks: list[dict] = []
    manifest: list[dict] = []
    for index, (passage, role) in enumerate(zip(passages, predictions)):
        task_id = f"sr-r2-{index:04d}"
        tasks.append({
            "schema_version": "1.0",
            "task_id": task_id,
            "instruction": C3_PROMPTS["section_role"],
            "input_document": {
                "passage": passage["text"],
                "verifier_prediction": {"section_role": role},
            },
            "output_schema": "section_role_prediction",
            "max_tokens": 64,
            "thinking": False,
        })
        manifest.append({
            "task_id": task_id,
            "record_id": passage["record_id"],
            "pmcid": passage["pmcid"],
            "section_path": passage["section_path"],
            "section_title": passage["section_title"],
            "verifier_role": role,
            "passage_sha256": hashlib.sha256(passage["text"].encode("utf-8")).hexdigest(),
        })
    return tasks, manifest


def build_rt_tasks(examples: Path, pairs: Path, model, tokenizer, device: str,
                   sample_size: int, seed: int, out_dir: Path) -> tuple[list[dict], list[dict]]:
    """Pilot-style retrieval sample from the 12k dev split + verifier ranking + C3 tasks."""
    # 1. sample dev retrieval query example ids (stable order, seed 20260817).
    retrieval_example_ids: list[str] = []
    with open(examples, encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            item = json.loads(line)
            if item["task"] == "evidence_retrieval" and item["split"] == "development":
                retrieval_example_ids.append(item["example_id"])
    sampled_rows = _stable_sample(
        [{"example_id": identifier} for identifier in retrieval_example_ids],
        sample_size, seed, "example_id",
    )
    sampled_ids = {item["example_id"] for item in sampled_rows}

    # 2. stream pairs once, keeping positives + negatives for sampled dev queries.
    positives_by_query: dict[str, dict] = {}
    negatives_by_query: dict[str, list[dict]] = defaultdict(list)
    with open(pairs, encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            pair = json.loads(line)
            if pair["query_split"] != "development":
                continue
            query_id = pair["query_example_id"]
            if query_id not in sampled_ids:
                continue
            if pair["label"] == 1:
                positives_by_query[query_id] = pair
            else:
                negatives_by_query[query_id].append(pair)

    tasks: list[dict] = []
    manifest: list[dict] = []
    task_index = 0
    for query_id in sorted(sampled_ids, key=lambda q: hashlib.sha256(f"{seed}:{q}".encode()).hexdigest()):
        positive = positives_by_query.get(query_id)
        if positive is None:
            continue
        candidates = [positive] + sorted(negatives_by_query.get(query_id, []), key=lambda pair: pair["pair_id"])[:3]
        order = _stable_sample(candidates, len(candidates), seed, "pair_id")
        # verifier ranking: best index in `order` by cosine similarity.
        query_vector = _er_encode(model, tokenizer, [positive["query_text"]], device, 256)
        document_vectors = _er_encode(model, tokenizer, [pair["document_text"] for pair in order], device, 512)
        scores = (query_vector @ document_vectors.T)[0].tolist()
        best_index = int(max(range(len(order)), key=lambda i: scores[i]))
        task_id = f"rt-r2-{task_index:03d}"
        tasks.append({
            "schema_version": "1.0",
            "task_id": task_id,
            "instruction": C3_PROMPTS["retrieval"],
            "input_document": {
                "query": positive["query_text"],
                "candidates": [
                    {"index": position, "text": pair["document_text"]}
                    for position, pair in enumerate(order)
                ],
                "verifier_ranking": {"best_index": best_index},
            },
            "output_schema": "retrieval_selection_prediction",
            "max_tokens": 64,
            "thinking": False,
        })
        manifest.append({
            "task_id": task_id,
            "query_example_id": query_id,
            "query_text": positive["query_text"],
            "candidates": [
                {"pair_id": pair["pair_id"], "label": pair["label"], "document_example_id": pair["document_example_id"]}
                for pair in order
            ],
            "verifier_best_index": best_index,
            "verifier_scores": [round(score, 8) for score in scores],
        })
        task_index += 1
    return tasks, manifest


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")


def _run_hosted_batch(tasks: list[dict], provider_config: Path, key_file: Path, output_path: Path) -> dict:
    from metawingman_core.provider_factory import build_provider, load_provider_config
    from metawingman_core.structured_batch import run_structured_batch

    os.environ["DEEPSEEK_API_KEY"] = key_file.read_text(encoding="utf-8").strip()
    provider = build_provider(load_provider_config(provider_config))
    return run_structured_batch(
        tasks,
        provider=provider,
        output_path=output_path,
        maximum_provider_calls=2 * len(tasks) + 2,
        maximum_reserved_output_tokens=2 * len(tasks) * 64,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blind-tasks", type=Path, required=True)
    parser.add_argument("--examples", type=Path, required=True)
    parser.add_argument("--pairs", type=Path, required=True)
    parser.add_argument("--sr-final", type=Path, required=True)
    parser.add_argument("--er-final", type=Path, required=True)
    parser.add_argument("--provider-config", type=Path, required=True)
    parser.add_argument("--key-file", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--task", choices=["sr", "rt", "both"], default="both")
    parser.add_argument("--sample-size", type=int, default=200)
    parser.add_argument("--seed", type=int, default=20260817)
    parser.add_argument("--device", default=None)
    args = parser.parse_args()

    import torch

    device = args.device or ("cuda" if torch.cuda.is_available() else "cpu")
    args.out_dir.mkdir(parents=True, exist_ok=True)

    model_hashes = {
        "section_role_final": _hash_tree(args.sr_final),
        "evidence_retrieval_final": _hash_tree(args.er_final),
    }

    report = {
        "schema_version": "1.0",
        "configuration": "C3",
        "round": "R2-AI",
        "seed": args.seed,
        "sample_size": args.sample_size,
        "device": device,
        "config_prompt_sha256": {
            key: hashlib.sha256(value.encode("utf-8")).hexdigest()
            for key, value in C3_PROMPTS.items()
        },
        "model_hashes": model_hashes,
        "blind_tasks_sha256": _sha256_file(args.blind_tasks),
        "sections": {},
    }

    if args.task in ("sr", "both"):
        sr_model, sr_tokenizer = _load_section_role_model(args.sr_final, device)
        tasks_sr, manifest_sr = build_sr_tasks(args.blind_tasks, sr_model, sr_tokenizer, device, args.out_dir)
        _write_jsonl(args.out_dir / "tasks-sr.jsonl", tasks_sr)
        _write_jsonl(args.out_dir / "manifest-sr.jsonl", manifest_sr)
        summary_sr = _run_hosted_batch(tasks_sr, args.provider_config, args.key_file, args.out_dir / "runs-sr.jsonl")
        report["sections"]["section_role"] = {
            "tasks_built": len(tasks_sr),
            "records": 200,
            "passages": len(tasks_sr),
            "batch_summary": summary_sr,
        }

    if args.task in ("rt", "both"):
        rt_model, rt_tokenizer = _load_retrieval_model(args.er_final, device)
        tasks_rt, manifest_rt = build_rt_tasks(
            args.examples, args.pairs, rt_model, rt_tokenizer, device,
            args.sample_size, args.seed, args.out_dir,
        )
        _write_jsonl(args.out_dir / "tasks-rt.jsonl", tasks_rt)
        _write_jsonl(args.out_dir / "manifest-rt.jsonl", manifest_rt)
        summary_rt = _run_hosted_batch(tasks_rt, args.provider_config, args.key_file, args.out_dir / "runs-rt.jsonl")
        report["sections"]["retrieval"] = {
            "tasks_built": len(tasks_rt),
            "batch_summary": summary_rt,
        }

    with open(args.out_dir / "report.json", "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
