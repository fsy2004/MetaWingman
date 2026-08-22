#!/usr/bin/env python3
"""Score locked acquisition outputs against a sealed screening snapshot."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from metawingman.scripts.metawingman_core.acquisition_scoring import (
    ScoringError,
    extract_screening_workbook_reference,
    match_reference_rows,
    score_rankings,
    validate_exact_receipt_slots,
    validate_scoring_gate,
)
from metawingman.scripts.metawingman_core.state_store import atomic_write_json
from metawingman.scripts.metawingman_core.operational_corpus import load_jsonl_records


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("lock", type=Path)
    parser.add_argument("--outputs-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    lock = json.loads(args.lock.read_text(encoding="utf-8"))
    validate_scoring_gate(plan, lock, expected_slots=12)
    receipt_paths = sorted(args.outputs_dir.glob("*.receipt.json"))
    receipts = [json.loads(path.read_text(encoding="utf-8")) for path in receipt_paths]
    validate_exact_receipt_slots(
        receipts,
        plan_id=plan["plan_id"],
        case_id=plan["case"]["case_id"],
        corpus_sha256=plan["case"]["operational_corpus_sha256"],
    )

    outputs = []
    for receipt in receipts:
        output_path = Path(receipt["output_path"])
        if sha256(output_path) != receipt["output_sha256"]:
            raise ScoringError("output SHA-256 mismatch")
        output = json.loads(output_path.read_text(encoding="utf-8"))
        if (
            output.get("plan_id") != receipt["plan_id"]
            or output.get("case_id") != receipt["case_id"]
            or output.get("configuration_id") != receipt["configuration_id"]
            or output.get("seed") != receipt["seed"]
        ):
            raise ScoringError("output identity does not match receipt")
        outputs.append((receipt, output))

    reference = Path(plan["case"]["sealed_reference_path"])
    if sha256(reference) != plan["case"]["sealed_reference_sha256"]:
        raise ScoringError("sealed reference SHA-256 mismatch")
    corpus_path = Path(plan["case"]["operational_corpus_path"])
    if sha256(corpus_path) != plan["case"]["operational_corpus_sha256"]:
        raise ScoringError("operational corpus SHA-256 mismatch")
    corpus = load_jsonl_records(corpus_path)
    reference_rows, extraction_audit = extract_screening_workbook_reference(reference)
    matched, mapping_audit = match_reference_rows(reference_rows, corpus)
    valid_ids = {str(row["id"]) for row in corpus}
    scores = [
        {
            "configuration_id": receipt["configuration_id"],
            "seed": receipt["seed"],
            **score_rankings(output, matched, valid_corpus_ids=valid_ids),
            "input_tokens": receipt["input_tokens"],
            "output_tokens": receipt["output_tokens"],
            "wall_seconds": receipt["wall_seconds"],
        }
        for receipt, output in outputs
    ]
    result = {
        "schema_version": "1.0",
        "plan_id": plan["plan_id"],
        "reference_sha256": sha256(reference),
        "extraction_audit": extraction_audit,
        "mapping_audit": mapping_audit,
        "scores": sorted(scores, key=lambda row: (row["configuration_id"], row["seed"])),
    }
    atomic_write_json(args.out, result)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ScoringError as exc:
        raise SystemExit(str(exc)) from None
