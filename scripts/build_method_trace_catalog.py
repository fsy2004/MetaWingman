#!/usr/bin/env python3
"""Build a real method-trace training catalog from a published-meta corpus.

We select records whose publication_types include Meta-Analysis or Systematic
Review (and that are open-access so full text can be fetched), which are the
"already-published meta" we learn the *process* from. The catalog itself carries
only metadata (never outcome values) — the actual method trajectory is extracted
later by a provider from the paper's methods, with the outcome stripped.

Deterministic and offline. Output: research/method-trace-request-catalog.json
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
OUT = REPO / "research" / "method-trace-request-catalog.json"

META_TYPES = ("meta-analysis", "systematic review", "systematic-review", "meta-analysis")
DEFAULT_LIMIT = 40


def main() -> int:
    data = json.loads(CORPUS.read_text(encoding="utf-8"))
    records = data["records"]

    selected = []
    for rec in records:
        ptypes = [str(p).casefold() for p in (rec.get("publication_types") or [])]
        is_meta = any(any(t in pt for t in META_TYPES) for pt in ptypes)
        if not is_meta:
            continue
        if not rec.get("doi"):
            continue
        if not rec.get("is_open_access"):
            continue
        if not rec.get("pmcid"):
            continue  # fullTextXML requires a PMC id; MED-only records usually have no full text XML
        selected.append({
            "record_id": rec["record_id"],
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
        if len(selected) >= DEFAULT_LIMIT:
            break

    catalog = {
        "schema_version": "1.0",
        "source_corpus": str(CORPUS),
        "selection_policy": "open_access meta-analyses/systematic reviews with DOI",
        "count": len(selected),
        "records": selected,
    }
    catalog["receipt_sha256"] = sha256_json(catalog)
    OUT.write_text(json.dumps(catalog, indent=2) + "\n", encoding="utf-8")
    print(f"selected {len(selected)} real meta/systematic reviews -> {OUT.name}")
    years = [r["year"] for r in selected if r.get("year")]
    print("year range:", min(years) if years else "?", "to", max(years) if years else "?")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
