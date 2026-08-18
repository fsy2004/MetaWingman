"""Reconcile two corpus slices (cross-engine count check).

Compares two candidate-records JSONL files by stable ids (pmid when both
sides carry one, else normalized title), reports union/intersection counts,
Jaccard similarity, per-slice unique ids, and abstract coverage. Used for
the EPMC-translated vs NCBI-native PubMed slice reconciliation and any later
dedup step. Read-only: never modifies the slices.

Usage:
  python metawingman/scripts/reconcile_corpus_slices.py \
    --slices a.jsonl b.jsonl --out-dir <dir>
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


def load_ids(path: Path) -> tuple[list[str], dict[str, bool]]:
    """Return (ordered stable ids, id -> has_abstract)."""
    ids: list[str] = []
    abstract_map: dict[str, bool] = {}
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        pmid = record.get("pmid")
        if pmid:
            stable = f"pmid:{pmid}"
        else:
            title = re.sub(r"\W+", " ", record.get("title") or "").strip().lower()
            stable = f"title:{title}" if title else f"raw:{record.get('id')}"
        ids.append(stable)
        abstract_map[stable] = bool((record.get("abstract") or "").strip())
    return ids, abstract_map


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--slices", nargs=2, type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        started = time.monotonic()
        a_ids, a_abs = load_ids(args.slices[0])
        b_ids, b_abs = load_ids(args.slices[1])
        set_a, set_b = set(a_ids), set(b_ids)
        union = set_a | set_b
        intersection = set_a & set_b
        report = {
            "schema_version": "1.0",
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "slices": {
                str(args.slices[0]): {"count": len(set_a), "sha256": sha256_file(args.slices[0])},
                str(args.slices[1]): {"count": len(set_b), "sha256": sha256_file(args.slices[1])},
            },
            "union_count": len(union),
            "intersection_count": len(intersection),
            "jaccard": round(len(intersection) / len(union), 6) if union else 0.0,
            "only_in_first": sorted(set_a - set_b),
            "only_in_second": sorted(set_b - set_a),
            "abstract_coverage_first": round(
                sum(1 for i in intersection if a_abs.get(i)) / len(intersection), 4
            ) if intersection else 0.0,
            "abstract_coverage_second": round(
                sum(1 for i in intersection if b_abs.get(i)) / len(intersection), 4
            ) if intersection else 0.0,
        }
        args.out_dir.mkdir(parents=True, exist_ok=True)
        out = args.out_dir / "reconciliation.json"
        out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"execution_state": "failed", "error": str(exc)}, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
