#!/usr/bin/env python3
"""Build a LARGE training catalog of real published meta reviews, excluding the
40 already used for train and the 40 held out for OOD, so the expanded training
set is fresh and the holdout stays unseen. Selects up to 200 reviews.

Output: research/method-trace-large-catalog.json
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
HOLDOUT = REPO / "research" / "method-trace-holdout-catalog.json"
OUT = REPO / "research" / "method-trace-large-catalog.json"
META_TYPES = ("meta-analysis", "systematic review", "systematic-review", "meta-analysis")
DEFAULT_LIMIT = 200


def main() -> int:
    used = set()
    if TRAIN.is_file():
        for line in TRAIN.read_text(encoding="utf-8").splitlines():
            if line.strip():
                used.add(json.loads(line)["meta"]["case_id"])
    if HOLDOUT.is_file():
        for rec in json.loads(HOLDOUT.read_text(encoding="utf-8"))["records"]:
            used.add(rec["record_id"])

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
            "record_id": rid, "pmcid": rec["pmcid"], "doi": rec["doi"],
            "title": rec.get("title") or "", "authors": rec.get("authors") or "",
            "year": rec.get("year"), "journal": rec.get("journal") or "",
            "journal_stratum": rec.get("journal_stratum") or "",
            "publication_types": rec.get("publication_types") or [],
            "cited_by_count": rec.get("cited_by_count"),
        })
        seen.add(rid)
        if len(selected) >= DEFAULT_LIMIT:
            break

    catalog = {
        "schema_version": "1.0", "source_corpus": str(CORPUS),
        "role": "expanded_training", "excluded_records": len(used),
        "count": len(selected), "records": selected,
    }
    catalog["receipt_sha256"] = sha256_json(catalog)
    OUT.write_text(json.dumps(catalog, indent=2) + "\n", encoding="utf-8")
    print(f"expanded training catalog: {len(selected)} reviews (excluded {len(used)} train+holdout) -> {OUT.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
