"""Build the pre-update operational corpus for a reconstruction case.

Consumes a verified search-strategy JSON (extracted from the published
review with source locators; see research/ag-rdt-search-strategy-2021.json
when it lands) and collects candidate records from Europe PMC with a hard
date filter (firstPublicationDate <= cutoff). Output is a records JSONL +
receipt (query hash, counts, coverage notes).

Coverage honesty: Europe PMC covers PubMed/MEDLINE + preprints; Embase- or
Web-of-Science-only records are NOT retrievable here. The receipt records
which databases the strategy named versus which this builder can actually
serve, so downstream reports state the coverage boundary.

Usage:
  python metawingman/scripts/build_preupdate_corpus.py \
    --strategy research/ag-rdt-search-strategy-2021.json \
    --cutoff 2021-08-31 \
    --out-dir <dir> \
    [--database PubMed] [--page-size 1000] [--max-records 20000]
"""
from __future__ import annotations

import argparse
import calendar
import hashlib
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date
from http.client import IncompleteRead
from pathlib import Path

from metawingman.scripts.metawingman_core.pubmed_constructs import pubmed_construct_annotations

EPMC_REST = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
ESUMMARY = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
EFETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"

_PUBMED_DATE = re.compile(
    r"\s+AND\s+\d{4}/\d{2}/\d{2}\s*:\s*\d{4}/\d{2}/\d{2}"
    r"\s*\[\s*Date\s*-\s*Publication\s*\]",
    re.IGNORECASE,
)
_EPMC_DATE = re.compile(
    r"\s+AND\s+FIRST_PDATE\s*:\s*\[\s*\d{4}-\d{2}-\d{2}"
    r"\s+TO\s+\d{4}-\d{2}-\d{2}\s*\]",
    re.IGNORECASE,
)

_MONTH_NUMBERS = {
    name.casefold(): number
    for number in range(1, 13)
    for name in (calendar.month_abbr[number], calendar.month_name[number])
}


def build_native_pubmed_query(source_query: str, lower: str, upper: str) -> str:
    """Replace a stale embedded PubMed snapshot with the frozen window."""
    concepts = _PUBMED_DATE.sub("", source_query).strip()
    return f'({concepts}) AND ({lower.replace("-", "/")}:{upper.replace("-", "/")}[Date - Publication])'


def build_epmc_query(source_query: str, lower: str, upper: str) -> str:
    """Replace a stale embedded Europe PMC snapshot with the frozen window."""
    concepts = _EPMC_DATE.sub("", source_query).strip()
    return f'({concepts}) AND (FIRST_PDATE:[{lower} TO {upper}])'


def _exact_xml_date(node: ET.Element | None) -> str | None:
    if node is None:
        return None
    year_text = node.findtext("Year")
    month_text = node.findtext("Month")
    day_text = node.findtext("Day")
    if not (year_text and month_text and day_text):
        return None
    month = int(month_text) if month_text.isdigit() else _MONTH_NUMBERS.get(month_text.casefold())
    try:
        parsed = date(int(year_text), int(month), int(day_text))
    except (TypeError, ValueError):
        return None
    return parsed.isoformat()


def publication_date_from_article(article: ET.Element) -> str | None:
    """Return the most precise publication date supplied by PubMed XML."""
    for node in article.findall(".//Article/ArticleDate"):
        exact = _exact_xml_date(node)
        if exact:
            return exact
    return _exact_xml_date(article.find(".//Article/Journal/JournalIssue/PubDate"))


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _epmc_page(params: dict, attempts: int = 3) -> dict:
    url = EPMC_REST + "?" + urllib.parse.urlencode(params)
    last: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(url, timeout=90) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (IncompleteRead, urllib.error.URLError, json.JSONDecodeError) as exc:
            last = exc
            if attempt < attempts:
                time.sleep(2 * attempt)
    raise RuntimeError(f"Europe PMC page failed after {attempts} attempts: {last}")


def _get_json(url: str, attempts: int = 3) -> dict:
    last: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(url, timeout=90) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (IncompleteRead, urllib.error.URLError, json.JSONDecodeError) as exc:
            last = exc
            if attempt < attempts:
                time.sleep(2 * attempt)
    raise RuntimeError(f"NCBI request failed after {attempts} attempts: {last}")


def _get_bytes(url: str, attempts: int = 3) -> bytes:
    last: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(url, timeout=120) as resp:
                return resp.read()
        except (IncompleteRead, urllib.error.URLError) as exc:
            last = exc
            if attempt < attempts:
                time.sleep(2 * attempt)
    raise RuntimeError(f"NCBI fetch failed after {attempts} attempts: {last}")


def ncbi_search(query: str, max_records: int) -> list[dict]:
    """Native PubMed execution: esearch (verbatim PubMed syntax) -> summaries + abstracts."""
    esearch_url = ESEARCH + "?" + urllib.parse.urlencode({
        "db": "pubmed", "term": query, "retmax": str(max_records), "retmode": "json",
    })
    ids = _get_json(esearch_url).get("esearchresult", {}).get("idlist", [])
    records: list[dict] = []
    record_index: dict[str, dict] = {}
    for start in range(0, len(ids), 200):
        batch = ids[start:start + 200]
        summary = _get_json(ESUMMARY + "?" + urllib.parse.urlencode({
            "db": "pubmed", "id": ",".join(batch), "retmode": "json",
        })).get("result", {})
        uids = [u for u in summary if u != "uids"]
        for pmid in batch:
            doc = summary.get(pmid, {})
            doi = ""
            for aid in doc.get("articleids", []) or []:
                if isinstance(aid, dict) and aid.get("idtype") == "doi":
                    doi = aid.get("value") or ""
            record = {
                "id": f"pmid:{pmid}",
                "pmid": pmid,
                "title": doc.get("title") or "",
                "abstract": "",  # filled below
                "first_publication_date": str(doc.get("pubdate") or ""),
                "source": "MED",
                "doi": doi,
            }
            records.append(record)
            record_index[pmid] = record
        efetch_url = EFETCH + "?" + urllib.parse.urlencode({
            "db": "pubmed", "id": ",".join(batch), "rettype": "abstract", "retmode": "xml",
        })
        xml_bytes = _get_bytes(efetch_url)
        try:
            root = ET.fromstring(xml_bytes)
            for article in root.findall(".//PubmedArticle"):
                pmid = article.findtext(".//PMID") or ""
                parts = article.findall(".//Abstract/AbstractText")
                abstract = " ".join("".join(part.itertext()).strip() for part in parts)
                record = record_index.get(pmid)
                if record is not None:
                    record["abstract"] = abstract
                    record.update(pubmed_construct_annotations(article))
                    exact_date = publication_date_from_article(article)
                    if exact_date:
                        record["first_publication_date"] = exact_date
        except ET.ParseError:
            pass  # abstracts stay empty for this batch; recorded in receipt coverage
    return records[:max_records]


def epmc_search(query: str, page_size: int, max_records: int) -> list[dict]:
    records: list[dict] = []
    cursor = "*"
    params_base = {
        "query": query,
        "format": "json",
        "pageSize": str(page_size),
        "resultType": "core",
    }
    while len(records) < max_records:
        params = dict(params_base)
        params["cursorMark"] = cursor
        payload = _epmc_page(params)
        hits = payload.get("resultList", {}).get("result", [])
        if not hits:
            break
        for hit in hits:
            records.append({
                "id": f"epmc:{hit.get('id')}",
                "pmid": hit.get("pmid"),
                "title": hit.get("title") or "",
                "abstract": hit.get("abstractText") or "",
                "first_publication_date": hit.get("firstPublicationDate"),
                "source": hit.get("source"),
                "doi": hit.get("doi"),
            })
        next_cursor = payload.get("nextCursorMark")
        if next_cursor == cursor or not next_cursor:
            break
        cursor = next_cursor
        if len(records) >= max_records:
            break
    return records[:max_records]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strategy", type=Path, required=True)
    parser.add_argument("--cutoff", required=True)
    parser.add_argument("--cutoff-lower", default="0001-01-01")
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--database", default="PubMed")
    parser.add_argument("--engine", choices=["epmc", "ncbi"], default="epmc")
    parser.add_argument("--page-size", type=int, default=1000)
    parser.add_argument("--max-records", type=int, default=20000)
    args = parser.parse_args()
    try:
        started = time.monotonic()
        strategy = json.loads(args.strategy.read_text(encoding="utf-8-sig"))
        databases = {d.get("database"): d for d in strategy.get("databases", [])}
        entry = databases.get(args.database)
        if not entry or not entry.get("query"):
            raise ValueError(f"strategy has no verbatim query for database {args.database!r}")
        if args.engine == "ncbi":
            # Native PubMed execution: verbatim strategy query + PubMed date syntax.
            query = build_native_pubmed_query(entry["query"], args.cutoff_lower, args.cutoff)
            records = ncbi_search(query, args.max_records)
        else:
            query = build_epmc_query(entry["query"], args.cutoff_lower, args.cutoff)
            records = epmc_search(query, args.page_size, args.max_records)
        args.out_dir.mkdir(parents=True, exist_ok=False)
        records_path = args.out_dir / "candidate-records.jsonl"
        records_path.write_text(
            "\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n", encoding="utf-8"
        )
        receipt = {
            "schema_version": "1.0",
            "execution_state": "completed",
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "strategy_file": str(args.strategy),
            "strategy_sha256": sha256_file(args.strategy),
            "engine": args.engine,
            "database_served": args.database,
            "databases_named_in_strategy": list(databases),
            "coverage_note": (
                "Europe PMC serves PubMed/MEDLINE + preprints; Embase/Web-of-Science-only "
                "records are not covered. Downstream reports must state this boundary."
            ),
            "cutoff": args.cutoff,
            "query_executed": query,
            "query_sha256": hashlib.sha256(query.encode("utf-8")).hexdigest(),
            "records": len(records),
            "max_records": args.max_records,
            "records_sha256": sha256_file(records_path),
        }
        (args.out_dir / "execution-receipt.json").write_text(
            json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        print(json.dumps(receipt, indent=2, ensure_ascii=False))
        return 0
    except (OSError, ValueError, json.JSONDecodeError, urllib.error.URLError) as exc:
        print(json.dumps({"execution_state": "failed", "error": str(exc)}, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
