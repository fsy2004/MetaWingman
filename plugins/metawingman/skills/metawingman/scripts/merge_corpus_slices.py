"""Merge corpus slices into one deduplicated candidate-records JSONL.

Deterministic merge: slices processed in argument order; dedup by stable id
(pmid when present, else normalized title, else raw id). Every record keeps
a provenance list of slice paths. Read-only on the inputs.

Usage:
  python metawingman/scripts/merge_corpus_slices.py \
    --slices a.jsonl b.jsonl ... --out-dir <dir>
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from pathlib import Path


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stable_id(record: dict) -> str:
    pmid = record.get("pmid")
    if pmid:
        return f"pmid:{pmid}"
    title = re.sub(r"\W+", " ", record.get("title") or "").strip().lower()
    if title:
        return f"title:{title}"
    return f"raw:{record.get('id')}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--slices", nargs="+", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        started = time.monotonic()
        seen: dict[str, dict] = {}
        slice_stats: list[dict] = []
        for slice_path in args.slices:
            count = 0
            new = 0
            for line in slice_path.read_text(encoding="utf-8-sig").splitlines():
                if not line.strip():
                    continue
                record = json.loads(line)
                sid = stable_id(record)
                count += 1
                if sid in seen:
                    seen[sid].setdefault("provenance", []).append(str(slice_path))
                    continue
                record = dict(record)
                record["provenance"] = [str(slice_path)]
                seen[sid] = record
                new += 1
            slice_stats.append({"slice": str(slice_path), "count": count, "new_after_dedup": new})
        args.out_dir.mkdir(parents=True, exist_ok=False)
        records = [seen[sid] for sid in seen]
        records_path = args.out_dir / "merged-candidates.jsonl"
        records_path.write_text(
            "\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n", encoding="utf-8"
        )
        receipt = {
            "schema_version": "1.0",
            "execution_state": "completed",
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "slice_stats": slice_stats,
            "total_rows_read": sum(s["count"] for s in slice_stats),
            "merged_records": len(records),
            "dedup_removed": sum(s["count"] for s in slice_stats) - len(records),
            "merged_sha256": sha256_file(records_path),
            "slice_sha256s": {str(p): sha256_file(p) for p in args.slices},
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
