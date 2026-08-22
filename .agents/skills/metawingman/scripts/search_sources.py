#!/usr/bin/env python3
"""Retrieve auditable records from PubMed, Europe PMC, and ClinicalTrials.gov."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, datetime, timezone
from pathlib import Path

from metawingman_core.network_security import (
    PublicNetworkError,
    public_https_opener,
    validate_public_https_url,
)
from metawingman_core.pubmed_constructs import pubmed_construct_annotations


FIELDS = ["record_id", "source", "source_record_id", "title", "abstract", "authors", "year", "first_publication_date", "journal", "doi", "pmid", "pmcid", "nct_id", "url", "publication_type", "mesh_terms", "registry_ids", "study_family_ids", "decision_anchor_type", "construct_annotation_basis", "is_open_access", "retrieved_at", "query_hash"]
UA = "MetaWingman/1.0"
MAX_RAW_RESPONSE_BYTES = 100 * 1024 * 1024


class SearchIntegrityError(ValueError):
    """Raised when an API response cannot prove a complete bounded retrieval."""


_MONTH_NUMBERS = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
    "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
    "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12,
}


def _exact_xml_date(node: ET.Element | None) -> str:
    if node is None:
        return ""
    year_text = node.findtext("Year")
    month_text = node.findtext("Month")
    day_text = node.findtext("Day")
    if not (year_text and month_text and day_text):
        return ""
    month = int(month_text) if month_text.isdigit() else _MONTH_NUMBERS.get(month_text.casefold())
    try:
        return date(int(year_text), int(month), int(day_text)).isoformat()
    except (TypeError, ValueError):
        return ""


def publication_date_from_article(article: ET.Element) -> str:
    """Return an exact PubMed publication date; never invent month/day precision."""
    for node in article.findall(".//Article/ArticleDate"):
        exact = _exact_xml_date(node)
        if exact:
            return exact
    return _exact_xml_date(article.find(".//Article/Journal/JournalIssue/PubDate"))


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def fetch(
    url: str, raw_dir: Path, prefix: str, retries: int = 4,
    max_bytes: int = MAX_RAW_RESPONSE_BYTES,
) -> bytes:
    validate_public_https_url(url)
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with public_https_opener().open(req, timeout=90) as response:
                validate_public_https_url(response.geturl())
                declared = response.headers.get("Content-Length")
                if declared and int(declared) > max_bytes:
                    raise SearchIntegrityError(f"response exceeds byte limit {max_bytes}")
                body = response.read(max_bytes + 1)
            if len(body) > max_bytes:
                raise SearchIntegrityError(f"response exceeds byte limit {max_bytes}")
            digest = hashlib.sha256(body).hexdigest()
            raw_dir.mkdir(parents=True, exist_ok=True)
            (raw_dir / f"{prefix}-{digest[:12]}.raw").write_bytes(body)
            return body
        except (OSError, PublicNetworkError, SearchIntegrityError, ValueError):
            if attempt + 1 == retries:
                raise
            time.sleep(2 ** attempt)
    raise RuntimeError("unreachable")


def assert_complete(records: list[dict], total: int, limit: int, source: str) -> None:
    identifiers = [str(item.get("record_id") or "") for item in records]
    if any(not value for value in identifiers):
        raise SearchIntegrityError(f"{source}: one or more records lack a stable identifier")
    if len(set(identifiers)) != len(identifiers):
        raise SearchIntegrityError(f"{source}: duplicate records survived source pagination")
    expected = min(total, limit) if limit else total
    if len(records) != expected:
        raise SearchIntegrityError(
            f"{source}: API reported {total}, bounded retrieval expected {expected}, got {len(records)}"
        )


def text(node, path: str) -> str:
    found = node.find(path)
    return "" if found is None else "".join(found.itertext()).strip()


def pubmed(query: str, limit: int, raw_dir: Path) -> tuple[list[dict], dict]:
    email = os.getenv("NCBI_EMAIL", "")
    api_key = os.getenv("NCBI_API_KEY", "")
    common = {"db": "pubmed", "term": query, "retmode": "json", "tool": "systematic_review_meta_analysis"}
    if email:
        common["email"] = email
    if api_key:
        common["api_key"] = api_key
    search_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?" + urllib.parse.urlencode({**common, "retmax": 0})
    search_data = json.loads(fetch(search_url, raw_dir, "pubmed-esearch-count"))
    total = int(search_data["esearchresult"]["count"])
    wanted = min(total, limit) if limit else total
    records = []
    qhash = hashlib.sha256(query.encode()).hexdigest()
    delay = 0.11 if api_key else 0.36
    for start in range(0, wanted, 5000):
        count = min(5000, wanted - start)
        id_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?" + urllib.parse.urlencode({**common, "retstart": start, "retmax": count})
        ids = json.loads(fetch(id_url, raw_dir, f"pubmed-esearch-{start}"))["esearchresult"]["idlist"]
        time.sleep(delay)
        for offset in range(0, len(ids), 200):
            batch = ids[offset:offset + 200]
            params = {"db": "pubmed", "id": ",".join(batch), "retmode": "xml", "tool": "systematic_review_meta_analysis"}
            if email:
                params["email"] = email
            if api_key:
                params["api_key"] = api_key
            url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?" + urllib.parse.urlencode(params)
            root = ET.fromstring(fetch(url, raw_dir, f"pubmed-efetch-{start + offset}"))
            for article in root.findall(".//PubmedArticle"):
                pmid = text(article, ".//MedlineCitation/PMID")
                title = text(article, ".//Article/ArticleTitle")
                abstract = " ".join("".join(x.itertext()).strip() for x in article.findall(".//Article/Abstract/AbstractText"))
                authors = []
                for author in article.findall(".//Article/AuthorList/Author"):
                    name = " ".join(filter(None, [text(author, "ForeName"), text(author, "LastName")]))
                    if name:
                        authors.append(name)
                doi = pmcid = ""
                for aid in article.findall(".//PubmedData/ArticleIdList/ArticleId"):
                    kind = aid.attrib.get("IdType", "")
                    if kind == "doi": doi = (aid.text or "").strip()
                    if kind == "pmc": pmcid = (aid.text or "").strip()
                year = text(article, ".//Article/Journal/JournalIssue/PubDate/Year") or text(article, ".//Article/Journal/JournalIssue/PubDate/MedlineDate")[:4]
                annotations = pubmed_construct_annotations(article)
                records.append({
                    "record_id": f"pubmed:{pmid}", "source": "PubMed", "source_record_id": pmid,
                    "title": title, "abstract": abstract, "authors": "; ".join(authors), "year": year,
                    "first_publication_date": publication_date_from_article(article),
                    "journal": text(article, ".//Article/Journal/Title"), "doi": doi, "pmid": pmid, "pmcid": pmcid,
                    "nct_id": "", "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/", "publication_type": "; ".join(x.text or "" for x in article.findall(".//Article/PublicationTypeList/PublicationType")),
                    "mesh_terms": annotations["mesh_terms"], "registry_ids": annotations["registry_ids"],
                    "study_family_ids": annotations["study_family_ids"],
                    "decision_anchor_type": annotations.get("decision_anchor_type", ""),
                    "construct_annotation_basis": annotations["construct_annotation_basis"],
                    "is_open_access": "", "retrieved_at": now(), "query_hash": qhash,
                })
            time.sleep(delay)
    assert_complete(records, total, limit, "PubMed")
    return records, {"source": "PubMed", "query": query, "reported_count": total, "retrieved_count": len(records), "limit": limit}


def europe_pmc(query: str, limit: int, raw_dir: Path) -> tuple[list[dict], dict]:
    records, cursor, total = [], "*", None
    qhash = hashlib.sha256(query.encode()).hexdigest()
    page = 0
    while True:
        page += 1
        params = {"query": query, "format": "json", "resultType": "core", "pageSize": 1000, "cursorMark": cursor}
        url = "https://www.ebi.ac.uk/europepmc/webservices/rest/search?" + urllib.parse.urlencode(params)
        data = json.loads(fetch(url, raw_dir, f"europepmc-{page}"))
        total = int(data.get("hitCount", 0))
        for item in data.get("resultList", {}).get("result", []):
            if limit and len(records) >= limit: break
            source_id = f"{item.get('source','')}:{item.get('id','')}"
            records.append({
                "record_id": f"europepmc:{source_id}", "source": "Europe PMC", "source_record_id": source_id,
                "title": item.get("title", ""), "abstract": item.get("abstractText", ""),
                "authors": item.get("authorString", ""), "year": item.get("pubYear", ""),
                "first_publication_date": item.get("firstPublicationDate", ""),
                "journal": item.get("journalTitle", ""), "doi": item.get("doi", ""),
                "pmid": item.get("pmid", ""), "pmcid": item.get("pmcid", ""), "nct_id": "",
                "url": f"https://europepmc.org/article/{item.get('source','')}/{item.get('id','')}",
                "publication_type": item.get("pubType", "") if isinstance(item.get("pubType", ""), str) else "; ".join(item.get("pubTypeList", {}).get("pubType", [])),
                "is_open_access": item.get("isOpenAccess", ""), "retrieved_at": now(), "query_hash": qhash,
            })
        if (limit and len(records) >= limit) or len(records) >= total: break
        next_cursor = data.get("nextCursorMark")
        if not next_cursor or next_cursor == cursor: break
        cursor = next_cursor
        time.sleep(0.2)
    assert_complete(records, total or 0, limit, "Europe PMC")
    return records, {"source": "Europe PMC", "query": query, "reported_count": total or 0, "retrieved_count": len(records), "limit": limit}


def clinical_trials(query: str, limit: int, raw_dir: Path) -> tuple[list[dict], dict]:
    records, token, total, page = [], "", None, 0
    seen_tokens: set[str] = set()
    qhash = hashlib.sha256(query.encode()).hexdigest()
    while True:
        page += 1
        params = {"query.term": query, "pageSize": 1000, "countTotal": "true", "format": "json"}
        if token: params["pageToken"] = token
        url = "https://clinicaltrials.gov/api/v2/studies?" + urllib.parse.urlencode(params)
        data = json.loads(fetch(url, raw_dir, f"ctg-{page}"))
        total = int(data.get("totalCount", 0))
        for study in data.get("studies", []):
            if limit and len(records) >= limit: break
            proto = study.get("protocolSection", {})
            ident = proto.get("identificationModule", {})
            desc = proto.get("descriptionModule", {})
            nct = ident.get("nctId", "")
            sponsor = proto.get("sponsorCollaboratorsModule", {}).get("leadSponsor", {}).get("name", "")
            first_post = proto.get("statusModule", {}).get("studyFirstPostDateStruct", {}).get("date", "")
            records.append({
                "record_id": f"ctg:{nct}", "source": "ClinicalTrials.gov", "source_record_id": nct,
                "title": ident.get("briefTitle", ""), "abstract": desc.get("briefSummary", ""), "authors": sponsor,
                "year": first_post[:4], "first_publication_date": first_post,
                "journal": "ClinicalTrials.gov", "doi": "", "pmid": "", "pmcid": "", "nct_id": nct,
                "url": f"https://clinicaltrials.gov/study/{nct}", "publication_type": "trial registry",
                "is_open_access": "Y", "retrieved_at": now(), "query_hash": qhash,
            })
        if (limit and len(records) >= limit): break
        next_token = data.get("nextPageToken", "")
        if not next_token: break
        if next_token == token or next_token in seen_tokens:
            raise SearchIntegrityError("ClinicalTrials.gov: repeated pagination token")
        seen_tokens.add(next_token)
        token = next_token
        time.sleep(0.2)
    assert_complete(records, total or 0, limit, "ClinicalTrials.gov")
    return records, {"source": "ClinicalTrials.gov", "query": query, "reported_count": total or 0, "retrieved_count": len(records), "limit": limit}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--outdir", required=True, type=Path)
    parser.add_argument("--pubmed-query")
    parser.add_argument("--europepmc-query")
    parser.add_argument("--ctg-query")
    parser.add_argument("--limit", type=int, default=0, help="Per-source cap; 0 retrieves all")
    args = parser.parse_args()
    if not any([args.pubmed_query, args.europepmc_query, args.ctg_query]):
        raise SystemExit("Provide at least one source query")
    outdir = args.outdir.resolve(); raw_dir = outdir / "raw"; outdir.mkdir(parents=True, exist_ok=True)
    all_records, audits = [], []
    for query, fn in [(args.pubmed_query, pubmed), (args.europepmc_query, europe_pmc), (args.ctg_query, clinical_trials)]:
        if query:
            records, audit = fn(query, args.limit, raw_dir)
            all_records.extend(records); audits.append(audit)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    csv_path = outdir / f"records-{stamp}.csv"
    with csv_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS); writer.writeheader(); writer.writerows(all_records)
    audit = {"created_at": now(), "records_file": csv_path.name, "records_sha256": hashlib.sha256(csv_path.read_bytes()).hexdigest(), "sources": audits}
    (outdir / f"search-audit-{stamp}.json").write_text(json.dumps(audit, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(audit, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
