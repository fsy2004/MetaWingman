#!/usr/bin/env python3
"""Run and lock a blinded conclusion-directed acquisition experiment."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
import time
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from metawingman.scripts.metawingman_core.conclusion_directed_acquisition import (
    AcquisitionError,
    CONFIGURATIONS,
    interpret_candidate_response,
    lock_acquisition_outputs,
    parse_query_response,
    validate_acquisition_plan,
    verify_candidates,
)
from metawingman.scripts.metawingman_core.provider_factory import build_provider, load_provider_config
from metawingman.scripts.metawingman_core.operational_corpus import load_jsonl_records
from metawingman.scripts.metawingman_core.state_store import atomic_write_json


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_plan(path: Path) -> dict:
    return validate_acquisition_plan(json.loads(path.read_text(encoding="utf-8")))


def load_records(path: Path) -> list[dict]:
    records = load_jsonl_records(path)
    if not records or len({str(row.get("id")) for row in records}) != len(records):
        raise AcquisitionError("operational corpus is empty or has duplicate IDs")
    return records


def _encode(tokenizer, model, texts: list[str], *, max_length: int, batch_size: int, device):
    import torch

    chunks = []
    for start in range(0, len(texts), batch_size):
        batch = tokenizer(
            texts[start:start + batch_size], padding=True, truncation=True,
            max_length=max_length, return_tensors="pt",
        ).to(device)
        with torch.inference_mode():
            chunks.append(model(**batch).last_hidden_state[:, 0].float().cpu())
    return torch.cat(chunks)


def _load_encoder(path: str, device):
    from transformers import AutoModel, AutoTokenizer

    return AutoTokenizer.from_pretrained(path), AutoModel.from_pretrained(path).to(device).eval()


def encode_corpus(plan: dict, outdir: Path, *, batch_size: int) -> list[dict]:
    import torch

    records = load_records(Path(plan["case"]["operational_corpus_path"]))
    texts = [f"{row.get('title', '')}\n{row.get('abstract', '')}".strip() for row in records]
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    outdir.mkdir(parents=True, exist_ok=True)
    receipts = []
    for checkpoint in plan["checkpoints"]:
        started = time.perf_counter()
        if device.type == "cuda":
            torch.cuda.reset_peak_memory_stats(device)
        tokenizer, model = _load_encoder(checkpoint["document_path"], device)
        vectors = _encode(tokenizer, model, texts, max_length=512, batch_size=batch_size, device=device)
        payload_path = outdir / f"documents-{checkpoint['seed']}.pt"
        torch.save({"ids": [str(row["id"]) for row in records], "vectors": vectors}, payload_path)
        receipt = {
            "schema_version": "1.0", "seed": checkpoint["seed"],
            "corpus_sha256": plan["case"]["operational_corpus_sha256"],
            "document_checkpoint_sha256": checkpoint["document_sha256"],
            "rows": len(records), "embedding_path": str(payload_path),
            "embedding_sha256": sha256(payload_path), "wall_seconds": time.perf_counter() - started,
            "peak_gpu_memory_bytes": int(torch.cuda.max_memory_allocated(device)) if device.type == "cuda" else None,
            "torch_version": torch.__version__, "python_version": platform.python_version(),
        }
        receipt_path = outdir / f"documents-{checkpoint['seed']}.receipt.json"
        atomic_write_json(receipt_path, receipt)
        receipts.append(receipt)
        del model, tokenizer, vectors
        if device.type == "cuda":
            torch.cuda.empty_cache()
    return receipts


def _call(provider, messages: list[dict], plan: dict):
    budget = plan["runtime"]["matched_budget"]
    result = provider.chat(
        messages, model=plan["runtime"]["model_id"], max_tokens=budget["max_output_tokens"], json_output=True
    )
    if result.model != plan["runtime"]["model_id"]:
        raise AcquisitionError("provider returned the wrong model")
    return result


def _query_messages(plan: dict, configuration_id: str) -> list[dict]:
    case = plan["case"]
    directed = plan["capabilities"][configuration_id]["conclusion_directed"]
    mode = (
        "derive distinct decision-relevant conclusion axes, then write retrieval queries for each axis"
        if directed else
        "write broad, conventional topic queries without hypothesizing conclusion axes"
    )
    prompt = Path(plan["runtime"]["prompt_path"]).read_text(encoding="utf-8")
    user = {
        "task": mode, "question": case["operational_question"],
        "eligibility_criteria": case["eligibility_criteria"],
        "generic_query_anchors": case["generic_queries"], "historical_cutoff": case["historical_cutoff"],
        "required_output": {"queries": ["6 to 12 non-empty query strings"]},
        "prohibition": "Do not infer or name any target review, authors, DOI, or published answer.",
    }
    return [{"role": "system", "content": prompt}, {"role": "user", "content": json.dumps(user, ensure_ascii=False)}]


def _selection_messages(plan: dict, configuration_id: str, rows: list[dict]) -> list[dict]:
    directed = plan["capabilities"][configuration_id]["conclusion_directed"]
    candidates = [{"id": row.get("id"), "title": row.get("title", "")} for row in rows]
    instruction = (
        "select records that jointly cover distinct decision-relevant conclusion axes"
        if directed else "select the most topically relevant records"
    )
    return [
        {"role": "system", "content": "Return strict JSON only. Use only candidate IDs supplied by the user."},
        {"role": "user", "content": json.dumps({
            "task": instruction, "question": plan["case"]["operational_question"],
            "eligibility_criteria": plan["case"]["eligibility_criteria"],
            "candidates": candidates,
            "required_output": {
                "candidate_ids": ["zero to 100 supplied IDs; use an empty array when none is supportable"]
            },
        }, ensure_ascii=False)},
    ]


def execute(plan: dict, cache_dir: Path, outdir: Path, *, top_pool: int, batch_size: int) -> list[dict]:
    import torch

    records = load_records(Path(plan["case"]["operational_corpus_path"]))
    record_index = {str(row["id"]): row for row in records}
    provider = build_provider(load_provider_config(Path(plan["runtime"]["provider_config_path"])))
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    outdir.mkdir(parents=True, exist_ok=True)
    receipts = []
    for checkpoint in plan["checkpoints"]:
        cache_path = cache_dir / f"documents-{checkpoint['seed']}.pt"
        cache_receipt_path = cache_dir / f"documents-{checkpoint['seed']}.receipt.json"
        cache_receipt = json.loads(cache_receipt_path.read_text(encoding="utf-8"))
        from metawingman.scripts.metawingman_core.conclusion_directed_acquisition import validate_embedding_cache
        validate_embedding_cache(cache_receipt, plan, seed=checkpoint["seed"])
        if sha256(cache_path) != cache_receipt["embedding_sha256"]:
            raise AcquisitionError("embedding payload SHA-256 mismatch")
        cache = torch.load(cache_path, map_location="cpu", weights_only=True)
        tokenizer, model = _load_encoder(checkpoint["query_path"], device)
        for configuration_id in CONFIGURATIONS:
            started = time.perf_counter()
            if device.type == "cuda":
                torch.cuda.reset_peak_memory_stats(device)
            output_path = outdir / f"{configuration_id}-{checkpoint['seed']}.json"
            receipt_path = outdir / f"{configuration_id}-{checkpoint['seed']}.receipt.json"
            if output_path.exists() or receipt_path.exists():
                if not output_path.is_file() or not receipt_path.is_file():
                    raise AcquisitionError("partial existing slot cannot be resumed or overwritten")
                existing = json.loads(receipt_path.read_text(encoding="utf-8"))
                expected = {
                    "plan_id": plan["plan_id"], "case_id": plan["case"]["case_id"],
                    "configuration_id": configuration_id, "seed": checkpoint["seed"],
                    "corpus_sha256": plan["case"]["operational_corpus_sha256"],
                }
                if any(existing.get(key) != value for key, value in expected.items()):
                    raise AcquisitionError("existing slot receipt does not match the frozen plan")
                if existing.get("status") != "completed" or sha256(output_path) != existing.get("output_sha256"):
                    raise AcquisitionError("existing slot output is incomplete or has a SHA-256 mismatch")
                receipts.append(existing)
                continue
            query_result = _call(provider, _query_messages(plan, configuration_id), plan)
            from metawingman.scripts.metawingman_core.conclusion_directed_acquisition import interpret_query_response
            queries, query_status = interpret_query_response(
                query_result.content, plan["case"]["generic_queries"]
            )
            query_vectors = _encode(tokenizer, model, queries, max_length=64, batch_size=batch_size, device=device)
            similarities = query_vectors @ cache["vectors"].T
            scores = similarities.max(dim=0).values.tolist()
            ranked_ids = [
                document_id for _score, document_id in sorted(
                    zip(scores, cache["ids"], strict=True), key=lambda row: (-row[0], str(row[1]))
                )[:top_pool]
            ]
            selection_rows = [record_index[str(value)] for value in ranked_ids[:100]]
            selection_result = _call(provider, _selection_messages(plan, configuration_id, selection_rows), plan)
            proposed_ids, provider_selection_status = interpret_candidate_response(selection_result.content)
            if plan["capabilities"][configuration_id]["source_verifier"]:
                verified, verification = verify_candidates(records, proposed_ids, cutoff=plan["case"]["historical_cutoff"])
                selected_ids = [str(row["id"]) for row in verified]
            else:
                selected_ids = proposed_ids
                verification = {"requested": len(proposed_ids), "verified": None, "unknown": None, "post_cutoff": None}
            output = {
                "schema_version": "1.0", "plan_id": plan["plan_id"], "case_id": plan["case"]["case_id"],
                "configuration_id": configuration_id, "seed": checkpoint["seed"],
                "capabilities": plan["capabilities"][configuration_id], "queries": queries,
                "query_status": query_status,
                "retrieval_candidate_ids": ranked_ids, "proposed_candidate_ids": proposed_ids,
                "selected_candidate_ids": selected_ids, "source_verification": verification,
                "selection_status": (
                    provider_selection_status
                    if provider_selection_status == "abstained_provider_schema_invalid"
                    else "selected" if selected_ids else "abstained_no_supported_candidate"
                ),
            }
            atomic_write_json(output_path, output)
            audits = [query_result.audit_record(), selection_result.audit_record()]
            receipt = {
                "schema_version": "1.0", "plan_id": plan["plan_id"], "case_id": plan["case"]["case_id"],
                "configuration_id": configuration_id, "seed": checkpoint["seed"], "status": "completed",
                "corpus_sha256": plan["case"]["operational_corpus_sha256"],
                "query_checkpoint_sha256": checkpoint["query_sha256"],
                "document_checkpoint_sha256": checkpoint["document_sha256"],
                "prompt_sha256": plan["runtime"]["prompt_sha256"], "model_id": plan["runtime"]["model_id"],
                "output_path": str(output_path), "output_sha256": sha256(output_path),
                "model_calls": 2,
                "input_tokens": sum(item["prompt_tokens"] or 0 for item in audits),
                "output_tokens": sum(item["completion_tokens"] or 0 for item in audits),
                "provider_audits": audits, "cost": None, "cost_status": "unknown",
                "wall_seconds": time.perf_counter() - started,
                "peak_gpu_memory_bytes": int(torch.cuda.max_memory_allocated(device)) if device.type == "cuda" else None,
            }
            atomic_write_json(receipt_path, receipt)
            receipts.append(receipt)
        del model, tokenizer
        if device.type == "cuda":
            torch.cuda.empty_cache()
    return receipts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    validate_parser = sub.add_parser("validate-only")
    validate_parser.add_argument("plan", type=Path)
    encode_parser = sub.add_parser("encode")
    encode_parser.add_argument("plan", type=Path); encode_parser.add_argument("--outdir", type=Path, required=True); encode_parser.add_argument("--batch-size", type=int, default=64)
    execute_parser = sub.add_parser("execute")
    execute_parser.add_argument("plan", type=Path); execute_parser.add_argument("--cache-dir", type=Path, required=True); execute_parser.add_argument("--outdir", type=Path, required=True); execute_parser.add_argument("--top-pool", type=int, default=1000); execute_parser.add_argument("--batch-size", type=int, default=64)
    lock_parser = sub.add_parser("lock")
    lock_parser.add_argument("plan", type=Path); lock_parser.add_argument("--receipts-dir", type=Path, required=True); lock_parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    plan = load_plan(args.plan)
    if args.command == "validate-only":
        print(json.dumps({"status": "ready", "plan_id": plan["plan_id"], "provider_calls": 0}))
    elif args.command == "encode":
        print(json.dumps(encode_corpus(plan, args.outdir, batch_size=args.batch_size), indent=2))
    elif args.command == "execute":
        print(json.dumps(execute(plan, args.cache_dir, args.outdir, top_pool=args.top_pool, batch_size=args.batch_size), indent=2))
    else:
        receipts = [json.loads(path.read_text(encoding="utf-8")) for path in sorted(args.receipts_dir.glob("*.receipt.json"))]
        lock = lock_acquisition_outputs(plan, receipts)
        atomic_write_json(args.out, lock)
        print(json.dumps(lock, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AcquisitionError as exc:
        raise SystemExit(str(exc)) from None
