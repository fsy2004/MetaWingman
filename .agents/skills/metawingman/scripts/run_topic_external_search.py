#!/usr/bin/env python3
"""Run three bounded PubMed opposition searches for one locked topic proposal."""

from __future__ import annotations

import argparse
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

from metawingman_core.topic_external_search import (
    TopicExternalSearchError,
    build_topic_audit_queries,
    compile_topic_external_search_receipt,
)


ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"


def _search(query: str, maximum_records: int) -> list[str]:
    url = ESEARCH + "?" + urllib.parse.urlencode({
        "db": "pubmed", "term": query, "retmax": str(maximum_records), "retmode": "json",
    })
    last: Exception | None = None
    for attempt in range(1, 4):
        try:
            with urllib.request.urlopen(url, timeout=90) as response:
                payload = json.loads(response.read().decode("utf-8"))
            return [str(value) for value in payload.get("esearchresult", {}).get("idlist", [])]
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            last = exc
            if attempt < 3:
                time.sleep(2 * attempt)
    raise TopicExternalSearchError(f"PubMed search failed after three attempts: {last}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("proposal_batch", type=Path)
    parser.add_argument("landscape", type=Path)
    parser.add_argument("--proposal-id", required=True)
    parser.add_argument("--lower-date", required=True)
    parser.add_argument("--maximum-records", type=int, default=500)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    try:
        if not 1 <= args.maximum_records <= 5000:
            raise TopicExternalSearchError("maximum-records must be between 1 and 5000")
        batch = json.loads(args.proposal_batch.read_text(encoding="utf-8"))
        matches = [item for item in batch["proposals"] if item.get("proposal_id") == args.proposal_id]
        if len(matches) != 1:
            raise TopicExternalSearchError(
                f"proposal_id must match exactly one proposal; found {len(matches)}"
            )
        landscape = json.loads(args.landscape.read_text(encoding="utf-8"))
        queries = build_topic_audit_queries(
            matches[0], cutoff_date=landscape["corpus_boundary"]["cutoff_date"],
            lower_date=args.lower_date, landscape=landscape,
        )
        raw = {
            kind: {"query": query, "pmids": _search(query, args.maximum_records)}
            for kind, query in queries.items()
        }
        receipt = compile_topic_external_search_receipt(matches[0], landscape, raw)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(
            json.dumps(receipt, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError, TopicExternalSearchError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}))
        return 1
    print(json.dumps({
        "status": "completed", "proposal_id": args.proposal_id,
        "provider_calls": 0, "out": str(args.out),
        "mapped_primary_studies": len(receipt["primary_study_node_ids"]),
        "mapped_reviews": len(receipt["review_matches"]),
        "mapped_protocols": len(receipt["protocol_matches"]),
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
