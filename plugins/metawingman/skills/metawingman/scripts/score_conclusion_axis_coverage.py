#!/usr/bin/env python3
"""Score post-lock coverage of expert-defined conclusion evidence axes."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from metawingman.scripts.metawingman_core.acquisition_scoring import (
    ScoringError, _xlsx_sheets, build_axis_reference_ids, score_axis_coverage, validate_scoring_gate,
)
from metawingman.scripts.metawingman_core.state_store import atomic_write_json
from metawingman.scripts.metawingman_core.operational_corpus import load_jsonl_records
from metawingman.scripts.score_conclusion_directed_acquisition import sha256


AXIS_SHEETS = {
    "symptom_status_and_duration": ("Duration of Symptoms", "MR_symptoms_positives", "MR_DOS_positives"),
    "viral_burden": ("Ct Value", "Viral Load", "TP vs FN"),
    "age": ("Age", "MR_Age"),
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path); parser.add_argument("lock", type=Path)
    parser.add_argument("--outputs-dir", type=Path, required=True); parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(); plan = json.loads(args.plan.read_text(encoding="utf-8")); lock = json.loads(args.lock.read_text(encoding="utf-8"))
    validate_scoring_gate(plan, lock, expected_slots=12)
    corpus_path = Path(plan["case"]["operational_corpus_path"]); reference = Path(plan["case"]["sealed_reference_path"])
    if sha256(corpus_path) != plan["case"]["operational_corpus_sha256"] or sha256(reference) != plan["case"]["sealed_reference_sha256"]:
        raise ScoringError("corpus or sealed reference SHA-256 mismatch")
    corpus = load_jsonl_records(corpus_path)
    axes, axis_audit = build_axis_reference_ids(_xlsx_sheets(reference), corpus, AXIS_SHEETS)
    receipt_paths = sorted(args.outputs_dir.glob("*.receipt.json"))
    if len(receipt_paths) != 12:
        raise ScoringError("exactly twelve receipts are required")
    scores = []
    for receipt_path in receipt_paths:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8")); output_path = Path(receipt["output_path"])
        if receipt.get("status") != "completed" or receipt.get("plan_id") != plan["plan_id"] or receipt.get("corpus_sha256") != plan["case"]["operational_corpus_sha256"] or sha256(output_path) != receipt.get("output_sha256"):
            raise ScoringError("receipt or output binding mismatch")
        output = json.loads(output_path.read_text(encoding="utf-8"))
        scores.append({"configuration_id": receipt["configuration_id"], "seed": receipt["seed"], **score_axis_coverage(output, axes)})
    result = {"schema_version": "1.0-development-axis-analysis", "plan_id": plan["plan_id"], "axis_sheet_registry": {key: list(value) for key, value in AXIS_SHEETS.items()}, "axis_audit": axis_audit, "scores": sorted(scores, key=lambda row: (row["configuration_id"], row["seed"]))}
    atomic_write_json(args.out, result); print(json.dumps(result, indent=2)); return 0


if __name__ == "__main__":
    try: raise SystemExit(main())
    except ScoringError as exc: raise SystemExit(str(exc)) from None
