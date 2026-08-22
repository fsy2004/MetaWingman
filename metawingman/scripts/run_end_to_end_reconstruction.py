#!/usr/bin/env python3
"""Execute, lock, and score the frozen blind reconstruction factorial."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from metawingman_core.end_to_end_reconstruction import (
    EndToEndReconstructionError,
    unlock_reference,
    validate_execution_plan,
    validate_lock_set,
)
from metawingman_core.end_to_end_runner import (
    execute_reconstruction_slot,
    score_reconstruction_output,
)
from metawingman_core.operational_corpus import load_jsonl_records
from metawingman_core.provider_factory import build_provider, load_provider_config
from metawingman_core.state_store import atomic_write_json


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_bound(path_value: str, expected: str) -> Path:
    path = Path(path_value)
    if not path.is_file() or sha256(path) != expected:
        raise EndToEndReconstructionError(f"bound input missing or hash-drifted: {path.name}")
    return path


def _case(plan: dict, case_id: str) -> dict:
    entry = next(item for item in plan["cases"] if item["case_id"] == case_id)
    return json.loads(Path(entry["operational_path"]).read_text(encoding="utf-8-sig"))


def execute(plan: dict, outdir: Path) -> dict:
    summary = validate_execution_plan(plan)
    provider = build_provider(load_provider_config(Path(plan["runtime"]["provider_config_path"])))
    configs = {item["configuration_id"]: item for item in plan["configurations"]}
    outdir.mkdir(parents=True, exist_ok=True)
    processed = resumed = 0
    for slot in plan["slots"]:
        stem = f"{slot['case_id']}--{slot['configuration_id']}--{slot['seed']}"
        output_path = outdir / f"{stem}.json"
        receipt_path = outdir / f"{stem}.receipt.json"
        if output_path.is_file() and receipt_path.is_file():
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            if receipt.get("output_sha256") != sha256(output_path):
                raise EndToEndReconstructionError(f"resume hash drift: {stem}")
            resumed += 1
            continue
        case = _case(plan, slot["case_id"])
        corpus = _load_bound(case["corpus_path"], case["corpus_sha256"])
        config = configs[slot["configuration_id"]]
        factor = "directed" if config["conclusion_directed_acquisition"] else "generic"
        binding = case["acquisition_outputs"][factor][str(slot["seed"])]
        acquisition_path = _load_bound(binding["path"], binding["sha256"])
        result = execute_reconstruction_slot(
            plan_id=plan["plan_id"], case=case, configuration=config,
            seed=slot["seed"], provider=provider,
            records=load_jsonl_records(corpus),
            acquisition_output=json.loads(acquisition_path.read_text(encoding="utf-8")),
        )
        atomic_write_json(output_path, result)
        receipt = {
            "schema_version": "1.0", "plan_id": plan["plan_id"],
            **slot, "status": "completed", "output_path": str(output_path),
            "output_sha256": sha256(output_path), "provider_calls": result["provider_calls"],
            "input_tokens": result["input_tokens"], "output_tokens": result["output_tokens"],
            "cost": None, "cost_status": "unknown", "wall_seconds": result["wall_seconds"],
        }
        atomic_write_json(receipt_path, receipt)
        processed += 1
    return {**summary, "status": "executed", "processed": processed, "resumed": resumed}


def receipts(outdir: Path) -> list[dict]:
    return [json.loads(path.read_text(encoding="utf-8")) for path in sorted(outdir.glob("*.receipt.json"))]


def lock(plan: dict, outdir: Path, lock_path: Path) -> dict:
    records = receipts(outdir)
    summary = validate_lock_set(plan, records)
    payload = {
        "schema_version": "1.0", "plan_id": plan["plan_id"], **summary,
        "receipts": records,
        "provider_calls": sum(int(item.get("provider_calls", 0)) for item in records),
        "input_tokens": sum(int(item.get("input_tokens", 0)) for item in records),
        "output_tokens": sum(int(item.get("output_tokens", 0)) for item in records),
        "cost": None, "cost_status": "unknown",
        "wall_seconds": sum(float(item.get("wall_seconds", 0)) for item in records),
    }
    atomic_write_json(lock_path, payload)
    return payload


def score(plan: dict, lock_path: Path, outdir: Path, score_path: Path) -> dict:
    lock_payload = json.loads(lock_path.read_text(encoding="utf-8"))
    records = lock_payload["receipts"]
    validate_lock_set(plan, records)
    scores = []
    for entry in plan["cases"]:
        reference = unlock_reference(plan, records, entry["case_id"])
        for receipt in records:
            if receipt["case_id"] != entry["case_id"]:
                continue
            output_path = Path(receipt["output_path"])
            if sha256(output_path) != receipt["output_sha256"]:
                raise EndToEndReconstructionError("output drift after lock")
            scores.append(score_reconstruction_output(
                json.loads(output_path.read_text(encoding="utf-8")), reference,
            ))
    payload = {
        "schema_version": "1.0-development", "plan_id": plan["plan_id"],
        "lock_sha256": sha256(lock_path), "scores": scores,
        "reference_access_timing": "after_complete_lock_only",
    }
    atomic_write_json(score_path, payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("validate-only", "execute", "lock", "score"):
        command = sub.add_parser(name)
        command.add_argument("plan", type=Path)
        if name != "validate-only":
            command.add_argument("--outdir", type=Path, required=True)
        if name in {"lock", "score"}:
            command.add_argument("--lock", type=Path, required=True)
        if name == "score":
            command.add_argument("--score-out", type=Path, required=True)
    args = parser.parse_args()
    try:
        plan = json.loads(args.plan.read_text(encoding="utf-8"))
        if args.command == "validate-only": result = validate_execution_plan(plan)
        elif args.command == "execute": result = execute(plan, args.outdir)
        elif args.command == "lock": result = lock(plan, args.outdir, args.lock)
        else: result = score(plan, args.lock, args.outdir, args.score_out)
    except (OSError, KeyError, StopIteration, TypeError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}))
        return 1
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
