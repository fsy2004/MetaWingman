#!/usr/bin/env python3
"""Stratified independent-validation sample (label-and-heldout-validation-protocol Part A).

Draws a deterministic, stratum-proportional sample of development records and
writes two files: a blind annotation file (no weak labels) and a sealed key
file (weak labels, withheld until annotation completes).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path

from metawingman_core.schema_guard import validate_document, validate_jsonl_file
from metawingman_core.state_store import atomic_write_json, canonical_json


def _stratum_key(stratum: dict) -> str:
    return stratum.get("sampling_key") or (
        f"{stratum.get('primary_specialty', '?')}|{stratum.get('question_type', '?')}"
    )


def _stable_order(values: list[str], seed: int) -> list[str]:
    return sorted(values, key=lambda value: hashlib.sha256(f"{seed}:{value}".encode()).hexdigest())


def build_validation_sample(
    examples: list[dict],
    plan: dict,
    *,
    target_records: int = 200,
    minimum_strata: int = 20,
    seed: int = 20260817,
    max_passages_per_record: int = 6,
    max_characters_per_record: int = 24000,
) -> tuple[list[dict], list[dict], dict]:
    strata_by_record = {
        record["record_id"]: record.get("biomedical_stratum") or {}
        for record in plan["records"]
    }
    pmcid_by_record = {
        record["record_id"]: record.get("pmcid") for record in plan["records"]
    }
    by_record: dict[str, list[dict]] = defaultdict(list)
    for example in examples:
        if example["split"] == "development":
            by_record[example["record_id"]].append(example)
    keyed: dict[str, list[str]] = defaultdict(list)
    for record_id in by_record:
        keyed[_stratum_key(strata_by_record.get(record_id, {}))].append(record_id)
    if len(keyed) < minimum_strata:
        raise ValueError(
            f"insufficient strata for independent validation: {len(keyed)} < {minimum_strata}"
        )
    per_stratum = max(1, math.ceil(target_records / len(keyed)))
    selected: list[str] = []
    for key in sorted(keyed):
        pool = _stable_order(keyed[key], seed)
        selected.extend(pool[:per_stratum])
    for key in sorted(keyed):
        if len(selected) >= target_records:
            break
        pool = _stable_order(keyed[key], seed)
        for record_id in pool:
            if record_id not in selected and len(selected) < target_records:
                selected.append(record_id)
    selected = sorted(set(selected))

    blind_rows: list[dict] = []
    key_rows: list[dict] = []
    strata_covered: set[str] = set()
    for record_id in selected:
        record_examples = sorted(
            by_record[record_id], key=lambda item: item["evidence_anchor"]["section_index"]
        )
        passages = []
        total = 0
        for example in record_examples:
            text = example["input_text"]
            if len(passages) >= max_passages_per_record or total + len(text) > max_characters_per_record:
                break
            passages.append({
                "section_path": example["evidence_anchor"]["section_path"],
                "section_title": example["target"]["section_title"],
                "passage": text,
            })
            total += len(text)
        if not passages:
            continue
        stratum = strata_by_record.get(record_id, {})
        strata_covered.add(_stratum_key(stratum))
        blind_rows.append({
            "schema_version": "1.0",
            "record_id": record_id,
            "pmcid": pmcid_by_record.get(record_id),
            "instruction": (
                "Independently label primary_specialty, question_type, each section's "
                "section_role, and whether each evidence excerpt is an exact source "
                "substring. Do not consult any prior labels; read the full text first."
            ),
            "passages": passages,
        })
        key_rows.append({
            "schema_version": "1.0",
            "record_id": record_id,
            "weak_labels": {
                "biomedical_stratum": stratum,
                "section_roles": {
                    example["evidence_anchor"]["section_path"]: example["target"]["section_role"]
                    for example in record_examples
                    if example["task"] == "section_role_classification"
                },
            },
        })
    summary = {
        "target_records": target_records,
        "selected_records": len(blind_rows),
        "strata_covered": len(strata_covered),
        "seed": seed,
    }
    if len(blind_rows) < target_records or len(strata_covered) < minimum_strata:
        raise ValueError(f"sample fell below protocol minimums: {summary}")
    return blind_rows, key_rows, summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("examples", type=Path)
    parser.add_argument("plan", type=Path)
    parser.add_argument("--blind-out", type=Path, required=True)
    parser.add_argument("--key-out", type=Path, required=True)
    parser.add_argument("--target-records", type=int, default=200)
    parser.add_argument("--minimum-strata", type=int, default=20)
    parser.add_argument("--seed", type=int, default=20260817)
    args = parser.parse_args()
    try:
        examples = validate_jsonl_file(args.examples, "training_example")
        plan = json.loads(args.plan.read_text(encoding="utf-8"))
        validate_document(plan, "training_corpus_plan")
        blind_rows, key_rows, summary = build_validation_sample(
            examples, plan,
            target_records=args.target_records,
            minimum_strata=args.minimum_strata,
            seed=args.seed,
        )
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        return 1
    args.blind_out.parent.mkdir(parents=True, exist_ok=True)
    args.key_out.parent.mkdir(parents=True, exist_ok=True)
    with args.blind_out.open("wb") as handle:
        for row in blind_rows:
            handle.write(canonical_json(row) + b"\n")
    atomic_write_json(args.key_out, {"schema_version": "1.0", "rows": key_rows, "summary": summary})
    print(json.dumps({"ok": True, "blind_out": str(args.blind_out), "key_out": str(args.key_out), "summary": summary}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
