#!/usr/bin/env python3
"""Development-only paired replay with shared query sets and balanced aggregation."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from metawingman.scripts.metawingman_core.conclusion_directed_acquisition import (
    CONFIGURATIONS, AcquisitionError, balanced_round_robin, lock_acquisition_outputs,
    reciprocal_rank_fusion, validate_acquisition_plan, verify_candidates,
)
from metawingman.scripts.metawingman_core.state_store import atomic_write_json
from metawingman.scripts.run_conclusion_directed_acquisition import _encode, _load_encoder, load_records, sha256


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path); parser.add_argument("--source-outputs", type=Path, required=True)
    parser.add_argument("--cache-dir", type=Path, required=True); parser.add_argument("--outdir", type=Path, required=True)
    parser.add_argument("--top-k", type=int, default=1000); parser.add_argument("--query-count", type=int, default=8)
    args = parser.parse_args()
    import torch

    plan = validate_acquisition_plan(json.loads(args.plan.read_text(encoding="utf-8")))
    records = load_records(Path(plan["case"]["operational_corpus_path"])); valid_ids = {str(row["id"]) for row in records}
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu"); args.outdir.mkdir(parents=True, exist_ok=True)
    receipts = []
    for checkpoint in plan["checkpoints"]:
        cache = torch.load(args.cache_dir / f"documents-{checkpoint['seed']}.pt", map_location="cpu", weights_only=True)
        tokenizer, model = _load_encoder(checkpoint["query_path"], device)
        factor_outputs = {}
        for directed, source_config in ((False, "generic-fixed-unverified"), (True, "conclusion-directed-unverified")):
            source_path = args.source_outputs / f"{source_config}-{checkpoint['seed']}.json"
            source_receipt_path = args.source_outputs / f"{source_config}-{checkpoint['seed']}.receipt.json"
            source = json.loads(source_path.read_text(encoding="utf-8")); source_receipt = json.loads(source_receipt_path.read_text(encoding="utf-8")); queries = source["queries"]
            if len(queries) < args.query_count:
                raise AcquisitionError("source query set has fewer than the frozen eight queries")
            queries = queries[:args.query_count]
            vectors = _encode(tokenizer, model, queries, max_length=64, batch_size=64, device=device)
            score_rows = vectors @ cache["vectors"].T
            per_query = []
            for scores in score_rows.tolist():
                per_query.append([value for _score, value in sorted(zip(scores, cache["ids"], strict=True), key=lambda row: (-row[0], str(row[1])))])
            factor_outputs[directed] = {
                "queries": queries,
                "balanced": balanced_round_robin(per_query, top_k=args.top_k),
                "rrf": reciprocal_rank_fusion(per_query, top_k=args.top_k, constant=60),
                "proposed": source["proposed_candidate_ids"],
                "source_output_sha256": sha256(source_path),
                "source_configuration_id": source_config,
                "input_tokens": source_receipt["input_tokens"], "output_tokens": source_receipt["output_tokens"],
            }
        for configuration_id in CONFIGURATIONS:
            started = time.perf_counter(); capabilities = plan["capabilities"][configuration_id]
            factor = factor_outputs[capabilities["conclusion_directed"]]; proposed = factor["proposed"]
            if capabilities["source_verifier"]:
                verified, audit = verify_candidates(records, proposed, cutoff=plan["case"]["historical_cutoff"])
                selected = [str(row["id"]) for row in verified]
            else:
                selected = list(proposed); audit = {"requested": len(proposed), "verified": None, "unknown": None, "post_cutoff": None}
            output = {
                "schema_version": "1.1-development-replay", "plan_id": plan["plan_id"], "case_id": plan["case"]["case_id"],
                "configuration_id": configuration_id, "seed": checkpoint["seed"], "capabilities": capabilities,
                "queries": factor["queries"], "query_count": args.query_count,
                "query_source_configuration_id": factor["source_configuration_id"], "source_output_sha256": factor["source_output_sha256"],
                "retrieval_aggregation": "balanced_round_robin", "retrieval_candidate_ids": factor["balanced"],
                "rrf_sensitivity_candidate_ids": factor["rrf"], "rrf_constant": 60,
                "proposed_candidate_ids": proposed, "selected_candidate_ids": selected, "source_verification": audit,
            }
            output_path = args.outdir / f"{configuration_id}-{checkpoint['seed']}.json"; atomic_write_json(output_path, output)
            receipt = {
                "schema_version": "1.0", "plan_id": plan["plan_id"], "case_id": plan["case"]["case_id"],
                "configuration_id": configuration_id, "seed": checkpoint["seed"], "status": "completed",
                "corpus_sha256": plan["case"]["operational_corpus_sha256"], "output_path": str(output_path), "output_sha256": sha256(output_path),
                "model_calls": 0, "derivation": "paired_locked_query_replay",
                "input_tokens": factor["input_tokens"], "output_tokens": factor["output_tokens"],
                "wall_seconds": time.perf_counter() - started,
            }
            atomic_write_json(args.outdir / f"{configuration_id}-{checkpoint['seed']}.receipt.json", receipt); receipts.append(receipt)
        del model, tokenizer
        if device.type == "cuda": torch.cuda.empty_cache()
    lock = lock_acquisition_outputs(plan, receipts); atomic_write_json(args.outdir / "acquisition-r2.lock.json", lock)
    print(json.dumps({"status": "locked", "slots": len(receipts), "lock": lock}, indent=2)); return 0


if __name__ == "__main__":
    try: raise SystemExit(main())
    except AcquisitionError as exc: raise SystemExit(str(exc)) from None
