#!/usr/bin/env python3
"""Evaluate an immutable asymmetric biomedical retriever on a frozen split."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import random
import time
from collections import defaultdict
from pathlib import Path

from metawingman_core.schema_guard import validate_jsonl_file
from metawingman_core.state_store import atomic_write_json
from metawingman_core.training_corpus import _retrieval_query
from run_component_training import _rank_metrics, _rank_positions


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _rank_receipt_rows(examples: list[dict], positions: list[int]) -> list[dict[str, object]]:
    if len(examples) != len(positions):
        raise ValueError("rank count must match example count")
    return [
        {
            "example_id": example["example_id"],
            "family_id": example["family_id"],
            "rank": int(position),
        }
        for example, position in zip(examples, positions, strict=True)
    ]


def _family_recall_summary(
    rows: list[dict[str, object]],
    *,
    k: int,
    bootstrap_replicates: int,
    bootstrap_seed: int,
) -> dict[str, object]:
    if k < 1 or bootstrap_replicates < 1:
        raise ValueError("k and bootstrap_replicates must be positive")
    by_family: dict[str, list[int]] = defaultdict(list)
    for row in rows:
        by_family[str(row["family_id"])].append(int(row["rank"]))
    if not by_family:
        raise ValueError("family recall requires at least one rank row")
    family_recalls = [
        sum(rank <= k for rank in ranks) / len(ranks)
        for _family, ranks in sorted(by_family.items())
    ]
    rng = random.Random(bootstrap_seed)
    bootstrapped = sorted(
        sum(rng.choice(family_recalls) for _ in family_recalls) / len(family_recalls)
        for _ in range(bootstrap_replicates)
    )
    lower_index = round(0.025 * (bootstrap_replicates - 1))
    upper_index = round(0.975 * (bootstrap_replicates - 1))
    family_sizes = [len(ranks) for ranks in by_family.values()]
    return {
        "families": len(by_family),
        "family_query_count_min": min(family_sizes),
        "family_query_count_max": max(family_sizes),
        f"family_macro_recall_at_{k}": sum(family_recalls) / len(family_recalls),
        "family_bootstrap_95_ci": [bootstrapped[lower_index], bootstrapped[upper_index]],
        "bootstrap_replicates": bootstrap_replicates,
        "bootstrap_seed": bootstrap_seed,
    }


def _checkpoint_provenance(
    load_path: Path,
    *,
    expected_sha256: str,
) -> dict[str, str]:
    weights = load_path / "model.safetensors"
    if not weights.is_file():
        raise ValueError(f"checkpoint weights missing: {weights}")
    observed = sha256(weights)
    if observed != expected_sha256:
        raise ValueError("checkpoint SHA-256 mismatch")
    return {"model_safetensors_sha256": observed}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("examples", type=Path)
    parser.add_argument("--split", default="development")
    parser.add_argument("--query-model", required=True)
    parser.add_argument("--query-revision", required=True)
    parser.add_argument("--query-load-path")
    parser.add_argument("--query-checkpoint-sha256")
    parser.add_argument("--document-model", required=True)
    parser.add_argument("--document-revision", required=True)
    parser.add_argument("--document-load-path")
    parser.add_argument("--document-checkpoint-sha256")
    parser.add_argument("--training-job-id")
    parser.add_argument("--training-receipt-sha256")
    parser.add_argument("--family-bootstrap-replicates", type=int, default=10000)
    parser.add_argument("--family-bootstrap-seed", type=int, default=20260821)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--ranks-out", type=Path)
    args = parser.parse_args()

    import torch
    from transformers import AutoModel, AutoTokenizer

    started = time.perf_counter()
    examples = [
        item for item in validate_jsonl_file(args.examples, "training_example")
        if item["task"] == "evidence_retrieval" and item["split"] == args.split
    ]
    if not examples:
        raise SystemExit("no retrieval examples in requested split")
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    query_source = args.query_load_path or args.query_model
    document_source = args.document_load_path or args.document_model
    checkpoint_provenance: dict[str, object] = {}
    if args.query_load_path:
        if not args.query_checkpoint_sha256:
            parser.error("--query-checkpoint-sha256 is required with --query-load-path")
        checkpoint_provenance["query_encoder"] = _checkpoint_provenance(
            Path(args.query_load_path), expected_sha256=args.query_checkpoint_sha256
        )
    if args.document_load_path:
        if not args.document_checkpoint_sha256:
            parser.error("--document-checkpoint-sha256 is required with --document-load-path")
        checkpoint_provenance["document_encoder"] = _checkpoint_provenance(
            Path(args.document_load_path), expected_sha256=args.document_checkpoint_sha256
        )
    if bool(args.training_job_id) != bool(args.training_receipt_sha256):
        parser.error("training job ID and receipt SHA-256 must be provided together")
    query_kwargs = {} if args.query_load_path else {"revision": args.query_revision}
    document_kwargs = {} if args.document_load_path else {"revision": args.document_revision}
    query_tokenizer = AutoTokenizer.from_pretrained(query_source, **query_kwargs)
    document_tokenizer = AutoTokenizer.from_pretrained(document_source, **document_kwargs)
    query_model = AutoModel.from_pretrained(query_source, **query_kwargs).to(device).eval()
    document_model = AutoModel.from_pretrained(document_source, **document_kwargs).to(device).eval()
    if device.type == "cuda":
        torch.cuda.reset_peak_memory_stats(device)

    def encode(texts: list[str], *, side: str) -> torch.Tensor:
        tokenizer = query_tokenizer if side == "query" else document_tokenizer
        model = query_model if side == "query" else document_model
        max_length = 64 if side == "query" else 512
        vectors = []
        for start in range(0, len(texts), args.batch_size):
            batch = tokenizer(
                texts[start:start + args.batch_size], padding=True, truncation=True,
                max_length=max_length, return_tensors="pt",
            ).to(device)
            with torch.inference_mode():
                vectors.append(model(**batch).last_hidden_state[:, 0].float().cpu())
        return torch.cat(vectors)

    query_vectors = encode([_retrieval_query(item) for item in examples], side="query")
    document_vectors = encode([item["input_text"] for item in examples], side="document")
    similarities = query_vectors @ document_vectors.T
    similarity_rows = similarities.tolist()
    families = [item["family_id"] for item in examples]
    positions = _rank_positions(similarity_rows, families)
    metrics = _rank_metrics(similarity_rows, families)
    rank_rows = _rank_receipt_rows(examples, positions)
    family_summary = _family_recall_summary(
        rank_rows,
        k=10,
        bootstrap_replicates=args.family_bootstrap_replicates,
        bootstrap_seed=args.family_bootstrap_seed,
    )
    receipt = {
        "schema_version": "1.1",
        "evaluation": "frozen_full_split_asymmetric_retrieval",
        "split": args.split,
        "examples_path": str(args.examples),
        "examples_sha256": sha256(args.examples),
        "queries": len(examples),
        "query_model": {"repository_id": args.query_model, "revision": args.query_revision},
        "document_model": {"repository_id": args.document_model, "revision": args.document_revision},
        "pooling": "cls",
        "similarity": "inner_product",
        "metrics": metrics,
        "family_summary": family_summary,
        "checkpoint_provenance": checkpoint_provenance,
        "source_training_receipt": (
            {
                "job_id": args.training_job_id,
                "sha256": args.training_receipt_sha256,
            }
            if args.training_job_id
            else None
        ),
        "wall_seconds": time.perf_counter() - started,
        "peak_gpu_memory_bytes": (
            int(torch.cuda.max_memory_allocated(device)) if device.type == "cuda" else None
        ),
        "torch_version": torch.__version__,
        "python_version": platform.python_version(),
    }
    if args.ranks_out:
        rank_receipt = {
            "schema_version": "1.1",
            "evaluation": "frozen_full_split_asymmetric_retrieval_ranks",
            "split": args.split,
            "examples_sha256": sha256(args.examples),
            "query_model": receipt["query_model"],
            "document_model": receipt["document_model"],
            "pooling": receipt["pooling"],
            "similarity": receipt["similarity"],
            "same_family_documents_masked": True,
            "family_summary": family_summary,
            "checkpoint_provenance": checkpoint_provenance,
            "source_training_receipt": receipt["source_training_receipt"],
            "rows": rank_rows,
        }
        args.ranks_out.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_json(args.ranks_out, rank_receipt)
        receipt["rank_receipt"] = {
            "path": str(args.ranks_out),
            "sha256": sha256(args.ranks_out),
            "rows": len(positions),
        }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(args.out, receipt)
    print(json.dumps(receipt, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
