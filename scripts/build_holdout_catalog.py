#!/usr/bin/env python3
"""Build a HOLD-OUT catalog of real published meta reviews that never appear in
the training set. Excludes the record_ids already used for training, so the
hold-out is genuinely OOD. Used to measure the real fidelity lift after training.

Output: research/method-trace-holdout-catalog.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from metawingman.scripts.metawingman_core.state_store import sha256_json

REPO = Path(__file__).resolve().parents[1]
CORPUS = REPO / "research" / "top-journal-training-corpus-v2.json"
TRAIN = REPO / "research" / "method-trace-train.jsonl"
OUT = REPO / "research" / "method-trace-holdout-catalog.json"
META_TYPES = ("meta-analysis", "systematic review", "systematic-review", "meta-analysis")
DEFAULT_LIMIT = 40


def main() -> int:
    # record_ids already used in training -> must be excluded from holdout.
    used = set()
    if TRAIN.is_file():
        for line in TRAIN.read_text(encoding="utf-8").splitlines():
            if line.strip():
                s = json.loads(line)
                used.add(s["meta"]["case_id"])

    data = json.loads(CORPUS.read_text(encoding="utf-8"))
    selected, seen = [], set()
    for rec in data["records"]:
        rid = rec.get("record_id")
        if rid in used or rid in seen:
            continue
        ptypes = [str(p).casefold() for p in (rec.get("publication_types") or [])]
        if not any(any(t in pt for t in META_TYPES) for pt in ptypes):
            continue
        if not rec.get("doi") or not rec.get("pmcid") or not rec.get("is_open_access"):
            continue
        selected.append({
            "record_id": rid,
            "pmcid": rec["pmcid"],
            "doi": rec["doi"],
            "title": rec.get("title") or "",
            "authors": rec.get("authors") or "",
            "year": rec.get("year"),
            "journal": rec.get("journal") or "",
            "journal_stratum": rec.get("journal_stratum") or "",
            "publication_types": rec.get("publication_types") or [],
            "cited_by_count": rec.get("cited_by_count"),
        })
        seen.add(rid)
        if len(selected) >= DEFAULT_LIMIT:
            break

    catalog = {
        "schema_version": "1.0",
        "source_corpus": str(CORPUS),
        "role": "holdout_ood",
        "excluded_training_records": len(used),
        "count": len(selected),
        "records": selected,
    }
    catalog["receipt_sha256"] = sha256_json(catalog)
    OUT.write_text(json.dumps(catalog, indent=2) + "\n", encoding="utf-8")
    print(f"holdout catalog: {len(selected)} OOD reviews (excluded {len(used)} training records) -> {OUT.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
