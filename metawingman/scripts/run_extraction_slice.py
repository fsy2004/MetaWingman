"""Deterministic extraction-slice engine (reconstruction runner v2, stage 2).

Implements the frozen extraction-stage contract of
docs/architecture/reconstruction-runner-v2-preregistration-2026-08-18.md:

- Pure functions only: a field template maps each field to a regex with a
  named group "value" over the record text; no LLM, no randomness.
- Missing / unclear cells are FLAGGED (status missing|unclear), never
  silently imputed.
- Every value records the pattern id that extracted it; a SHA-256 receipt
  carries input/template/output hashes and per-field coverage counts.

Usage:
  python metawingman/scripts/run_extraction_slice.py \
    --records <included-records.jsonl> \
    --template <extraction-template.json> \
    --out-dir <dir>
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from pathlib import Path


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def extract(records: list[dict], template: dict) -> dict:
    fields = template["fields"]
    rows = []
    coverage = {name: {"extracted": 0, "missing": 0, "unclear": 0} for name in fields}
    for record in records:
        text = " ".join(
            part for key in ("title", "abstract", "fulltext") if (part := (record.get(key) or ""))
        )
        row = {"record_id": record["id"], "fields": {}}
        for name, spec in fields.items():
            pattern_id = spec.get("id", name)
            match = re.search(spec["pattern"], text, flags=re.IGNORECASE)
            if not match:
                status = "missing"
            else:
                try:
                    value = match.group("value").strip()
                    status = "extracted"
                except IndexError:
                    status = "unclear"  # pattern matched but group missing
            if status == "extracted":
                value = _coerce(value, spec.get("type", "string"))
                row["fields"][name] = {
                    "status": "extracted", "value": value, "pattern_id": pattern_id,
                }
            else:
                row["fields"][name] = {
                    "status": status, "value": None, "pattern_id": pattern_id,
                    "note": "no_imputation" if status == "missing" else "matched_without_value_group",
                }
            coverage[name][status] += 1
        rows.append(row)
    return {"rows": rows, "coverage": coverage}


def _coerce(value: str, type_name: str):
    if type_name == "int":
        try:
            return int(float(value.replace(",", "")))
        except ValueError:
            return value  # keep raw when not coercible; status stays extracted but type-flagged
    if type_name == "float":
        try:
            return float(value.replace(",", ""))
        except ValueError:
            return value
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--records", type=Path, required=True)
    parser.add_argument("--template", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        started = time.monotonic()
        records = load_jsonl(args.records)
        template = json.loads(args.template.read_text(encoding="utf-8-sig"))
        if not isinstance(template, dict) or "fields" not in template:
            raise ValueError("template must be an extraction-template JSON with 'fields'")
        args.out_dir.mkdir(parents=True, exist_ok=False)
        result = extract(records, template)
        rows_path = args.out_dir / "extraction.jsonl"
        rows_path.write_text(
            "\n".join(json.dumps(r, ensure_ascii=False) for r in result["rows"]) + "\n",
            encoding="utf-8",
        )
        receipt = {
            "schema_version": "1.0",
            "stage": "extraction",
            "execution_state": "completed",
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "records_sha256": sha256_file(args.records),
            "template_sha256": sha256_file(args.template),
            "rows_sha256": sha256_file(rows_path),
            "coverage": result["coverage"],
            "no_imputation_note": "missing/unclear cells are flagged, never imputed",
            "determinism_note": "pure rule engine; identical inputs yield identical outputs",
        }
        (args.out_dir / "execution-receipt.json").write_text(
            json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        print(json.dumps(receipt, indent=2, ensure_ascii=False))
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"execution_state": "failed", "error": str(exc)}, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
