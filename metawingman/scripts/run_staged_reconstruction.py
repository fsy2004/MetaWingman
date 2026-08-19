"""Stage-chaining orchestrator (reconstruction runner v2, step 3).

Wires the deterministic stage engines into one auditable chain:
  screening -> extraction (included records only)
Each stage writes its own receipt (unchanged engines); this orchestrator adds
a chain receipt that links the stage hashes, so any single stage can be
audited or re-run alone (preregistration: reconstruction-runner-v2-
preregistration-2026-08-18.md). No LLM, no randomness; the analysis stage is
NOT wired here (v1 R-adapters already cover it and will join per-case).

Usage:
  python metawingman/scripts/run_staged_reconstruction.py \
    --case <staged-case.json> --out-dir <dir>
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_stage(script: Path, args: list[str], out_dir: Path) -> dict:
    proc = subprocess.run(
        [sys.executable, str(script), *args, "--out-dir", str(out_dir)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if proc.returncode != 0:
        raise RuntimeError(f"stage {script.name} failed (rc={proc.returncode}):\n{proc.stdout[-1500:]}\n{proc.stderr[-1500:]}")
    receipt_path = out_dir / "execution-receipt.json"
    if not receipt_path.is_file():
        raise RuntimeError(f"stage {script.name} wrote no receipt")
    return json.loads(receipt_path.read_text(encoding="utf-8"))


def included_records(records_path: Path, decisions_path: Path) -> tuple[list[dict], list[str]]:
    records = [json.loads(line) for line in records_path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    include_ids = []
    for line in decisions_path.read_text(encoding="utf-8-sig").splitlines():
        if not line.strip():
            continue
        decision = json.loads(line)
        if decision["decision"] == "include":
            include_ids.append(decision["record_id"])
    included = [r for r in records if r["id"] in include_ids]
    if len(included) != len(include_ids):
        raise RuntimeError("include ids do not resolve to records")
    return included, include_ids


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        started = time.monotonic()
        case = json.loads(args.case.read_text(encoding="utf-8-sig"))
        if case.get("schema_version") != "1.0" or "stages" not in case:
            raise ValueError("case must be a staged-case JSON (schema_version 1.0, stages)")
        args.out_dir.mkdir(parents=True, exist_ok=False)

        screening = case["stages"]["screening"]
        screening_out = args.out_dir / "screening"
        screening_receipt = run_stage(
            SCRIPTS / "run_screening_slice.py",
            ["--records", str(Path(screening["records"])), "--rules", str(Path(screening["rules"]))],
            screening_out,
        )
        decisions_path = screening_out / "decisions.jsonl"

        included, include_ids = included_records(Path(screening["records"]), decisions_path)
        included_path = args.out_dir / "included-records.jsonl"
        included_path.write_text(
            "\n".join(json.dumps(r, ensure_ascii=False) for r in included) + "\n", encoding="utf-8"
        )

        extraction = case["stages"]["extraction"]
        extraction_out = args.out_dir / "extraction"
        extraction_receipt = run_stage(
            SCRIPTS / "run_extraction_slice.py",
            ["--records", str(included_path), "--template", str(Path(extraction["template"]))],
            extraction_out,
        )

        chain_receipt = {
            "schema_version": "1.0",
            "execution_state": "completed",
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "stage_chain": ["screening", "extraction"],
            "include_count": len(include_ids),
            "screening_receipt_sha256": sha256_file(screening_out / "execution-receipt.json"),
            "extraction_receipt_sha256": sha256_file(extraction_out / "execution-receipt.json"),
            "screening_counts": screening_receipt.get("counts"),
            "extraction_coverage": extraction_receipt.get("coverage"),
            "determinism_note": "pure stage engines; identical inputs yield identical outputs",
        }
        (args.out_dir / "chain-receipt.json").write_text(
            json.dumps(chain_receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        print(json.dumps(chain_receipt, indent=2, ensure_ascii=False))
        return 0
    except (OSError, ValueError, json.JSONDecodeError, RuntimeError) as exc:
        print(json.dumps({"execution_state": "failed", "error": str(exc)}, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
