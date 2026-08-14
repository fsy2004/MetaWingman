#!/usr/bin/env python3
"""Harvest a license-aware metadata intake of published systematic reviews."""

from __future__ import annotations

import argparse
import json
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from metawingman_core.network_security import public_https_opener, validate_public_https_url
from metawingman_core.schema_guard import validate_document


BASE_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
REVIEW_CLAUSE = '(PUB_TYPE:"Systematic Review" OR PUB_TYPE:"Meta-Analysis" OR TITLE:"systematic review" OR TITLE:"meta-analysis")'
DEFAULT_JOURNAL_STRATA = {
    "top_general_medical": [
        "BMJ", "JAMA", "The Lancet", "New England Journal of Medicine",
        "Annals of Internal Medicine",
    ],
    "top_biomedical_and_multidisciplinary": [
        "Nature Medicine", "Nature Communications", "Science Translational Medicine",
        "PLOS Medicine",
    ],
    "leading_open_and_field_medical": [
        "JAMA Network Open", "eClinicalMedicine", "BMC Medicine",
        "The Lancet Digital Health", "The Lancet Public Health",
        "The Lancet Global Health", "The Lancet Psychiatry", "JAMA Pediatrics",
        "JAMA Internal Medicine", "JAMA Oncology", "Gut", "Circulation",
        "European Heart Journal", "British Journal of Sports Medicine",
    ],
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _request_json(url: str) -> dict[str, Any]:
    validate_public_https_url(url)
    request = urllib.request.Request(
        url, headers={"User-Agent": "MetaWingman/1.0 top-journal-corpus"}
    )
    with public_https_opener().open(request, timeout=90) as response:
        validate_public_https_url(response.geturl())
        return json.loads(response.read(100 * 1024 * 1024))


def _publication_types(item: dict[str, Any]) -> list[str]:
    values = item.get("pubTypeList", {}).get("pubType", [])
    if isinstance(values, str):
        values = [values]
    return sorted({str(value).strip() for value in values if str(value).strip()}, key=str.casefold)


def _status_updates(item: dict[str, Any]) -> list[str]:
    values = item.get("commentCorrectionList", {}).get("commentCorrection", [])
    if isinstance(values, dict):
        values = [values]
    return sorted(
        {str(value.get("type", "")).strip() for value in values if str(value.get("type", "")).strip()},
        key=str.casefold,
    )


def _integrity(updates: list[str]) -> tuple[str, str]:
    folded = " ".join(updates).casefold()
    if "retract" in folded:
        return "retracted", "exclude_retracted"
    material = ("erratum", "correct", "expression of concern", "duplicate publication")
    if any(token in folded for token in material):
        return "status_update_requires_audit", "hold_integrity_review"
    return "no_status_update_in_epmc_record", "development_candidate"


def _record(item: dict[str, Any], stratum: str) -> dict[str, Any] | None:
    title = str(item.get("title", "")).strip()
    year_text = str(item.get("pubYear") or item.get("firstPublicationDate", "")[:4])
    journal = str(
        item.get("journalInfo", {}).get("journal", {}).get("title", "")
        or item.get("journalTitle", "")
    ).strip()
    if not title or not year_text.isdigit() or not journal:
        return None
    source = str(item.get("source", "")).strip()
    identifier = str(item.get("id", "")).strip()
    if not source or not identifier:
        return None
    updates = _status_updates(item)
    integrity_status, admission_status = _integrity(updates)
    folded_title = title.casefold()
    if "protocol" in folded_title and admission_status == "development_candidate":
        admission_status = "exclude_non_reference"
    return {
        "record_id": f"epmc:{source}:{identifier}",
        "source_id": f"{source}:{identifier}",
        "title": title,
        "authors": str(item.get("authorString", "")).strip(),
        "year": int(year_text),
        "journal": journal,
        "journal_stratum": stratum,
        "doi": str(item.get("doi", "")).strip().casefold(),
        "pmid": str(item.get("pmid", "")).strip(),
        "pmcid": str(item.get("pmcid", "")).strip(),
        "publication_types": _publication_types(item),
        "is_open_access": str(item.get("isOpenAccess", "")).upper() == "Y",
        "license": str(item.get("license", "")).strip().casefold(),
        "cited_by_count": max(0, int(item.get("citedByCount", 0) or 0)),
        "source_url": f"https://europepmc.org/article/{urllib.parse.quote(source)}/{urllib.parse.quote(identifier)}",
        "reference_status": "published_expert_reference",
        "integrity_status": integrity_status,
        "status_update_types": updates,
        "admission_status": admission_status,
        "family_assignment_status": "pending_review_family_clustering",
        "split_status": "unassigned_pending_family_audit",
    }


def harvest(
    year_start: int,
    year_end: int,
    per_journal_limit: int = 0,
    requester: Callable[[str], dict[str, Any]] = _request_json,
    journal_strata: dict[str, list[str]] | None = None,
) -> dict[str, Any]:
    strata = journal_strata or DEFAULT_JOURNAL_STRATA
    records_by_key: dict[str, dict[str, Any]] = {}
    api_version = "unknown"
    reported_hits = 0
    query_count = 0
    for stratum, journals in strata.items():
        for journal in journals:
            query_count += 1
            query = f'JOURNAL:"{journal}" AND {REVIEW_CLAUSE} AND FIRST_PDATE:[{year_start}-01-01 TO {year_end}-12-31]'
            cursor = "*"
            retrieved = 0
            while True:
                params = {
                    "query": query, "format": "json", "resultType": "core",
                    "pageSize": 1000, "cursorMark": cursor,
                }
                data = requester(BASE_URL + "?" + urllib.parse.urlencode(params))
                api_version = str(data.get("version", api_version))
                if cursor == "*":
                    reported_hits += int(data.get("hitCount", 0) or 0)
                items = data.get("resultList", {}).get("result", [])
                for item in items:
                    if per_journal_limit and retrieved >= per_journal_limit:
                        break
                    retrieved += 1
                    record = _record(item, stratum)
                    if record is None:
                        continue
                    key = record["doi"] or record["pmid"] or record["record_id"]
                    records_by_key.setdefault(key, record)
                if (per_journal_limit and retrieved >= per_journal_limit) or retrieved >= int(data.get("hitCount", 0) or 0):
                    break
                next_cursor = str(data.get("nextCursorMark", ""))
                if not next_cursor or next_cursor == cursor:
                    break
                cursor = next_cursor
    records = sorted(records_by_key.values(), key=lambda row: (row["journal_stratum"], row["journal"].casefold(), -row["year"], row["record_id"]))
    status_counts = Counter(record["admission_status"] for record in records)
    stratum_counts = Counter(record["journal_stratum"] for record in records)
    corpus = {
        "schema_version": "1.0",
        "generated_at_utc": _now(),
        "source": {"name": "Europe PMC", "api_version": api_version, "base_url": BASE_URL},
        "sampling_policy": {
            "year_start": year_start,
            "year_end": year_end,
            "journal_is_stratum_not_oracle": True,
            "abstracts_excluded": True,
            "journal_strata": [{"stratum": key, "journals": value} for key, value in strata.items()],
        },
        "reference_policy": {
            "published_expert_outputs_are_reference": True,
            "reference_is_not_oracle": True,
            "corrected_current_version_only": True,
            "unresolved_integrity_blocks_held_out": True,
            "no_de_novo_human_adjudication": True,
            "family_split_before_evaluation": True,
        },
        "summary": {
            "queries": query_count,
            "reported_hits": reported_hits,
            "unique_records": len(records),
            "development_candidates": status_counts["development_candidate"],
            "held_for_integrity": status_counts["hold_integrity_review"],
            "excluded_retracted": status_counts["exclude_retracted"],
            "excluded_non_reference": status_counts["exclude_non_reference"],
            "open_access_records": sum(record["is_open_access"] for record in records),
            "by_stratum": dict(sorted(stratum_counts.items())),
        },
        "records": records,
    }
    validate_document(corpus, "top_journal_training_corpus")
    return corpus


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--year-start", type=int, default=2018)
    parser.add_argument("--year-end", type=int, default=datetime.now(timezone.utc).year)
    parser.add_argument("--per-journal-limit", type=int, default=0, help="0 retrieves every matching record")
    args = parser.parse_args()
    if args.year_start > args.year_end:
        raise SystemExit("year-start must not exceed year-end")
    corpus = harvest(args.year_start, args.year_end, args.per_journal_limit)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(corpus, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(corpus["summary"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
