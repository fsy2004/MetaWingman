#!/usr/bin/env python3
"""Verify DOI/PMID citation identity against Crossref or PubMed."""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import time
import unicodedata
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from difflib import SequenceMatcher
from pathlib import Path


def norm(value: str) -> str:
    value = unicodedata.normalize("NFKD", value or "").casefold()
    return " ".join(re.sub(r"[^\w]+", " ", value).split())


def get_json(url: str, user_agent: str) -> dict:
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": user_agent}), timeout=60) as response: return json.load(response)


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--input", required=True, type=Path); parser.add_argument("--output", required=True, type=Path); parser.add_argument("--title-threshold", type=float, default=0.90); args = parser.parse_args()
    email = os.getenv("CROSSREF_EMAIL", "") or os.getenv("NCBI_EMAIL", "") or "unknown@example.invalid"
    ua = f"MetaWingman/1.0 mailto:{email}"
    with args.input.open(encoding="utf-8-sig", newline="") as handle: rows = list(csv.DictReader(handle))
    output = []
    for row in rows:
        doi = (row.get("doi") or "").strip().lower(); pmid = (row.get("pmid") or "").strip(); supplied = row.get("title") or ""; found = ""; source = ""; note = ""
        try:
            if doi:
                url = "https://api.crossref.org/works/" + urllib.parse.quote(doi, safe="") + "?mailto=" + urllib.parse.quote(email)
                msg = get_json(url, ua).get("message", {}); found = " ".join(msg.get("title", [])[:1]); source = "Crossref"
                if msg.get("relation", {}).get("is-retracted-by"): note = "Crossref relation indicates retraction"
            elif pmid:
                params = {"db": "pubmed", "id": pmid, "retmode": "xml", "tool": "systematic_review_meta_analysis", "email": email}
                url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?" + urllib.parse.urlencode(params)
                with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": ua}), timeout=60) as response: root = ET.fromstring(response.read())
                node = root.find(".//ArticleTitle"); found = "" if node is None else "".join(node.itertext()); source = "PubMed"
            else:
                output.append({**row, "verification_status": "no_identifier", "verified_title": "", "title_similarity": "", "verification_source": "", "verification_note": "DOI or PMID required"}); continue
            similarity = SequenceMatcher(None, norm(supplied), norm(found)).ratio() if supplied and found else 0.0
            status = "verified" if found and similarity >= args.title_threshold else "metadata_mismatch"
            output.append({**row, "verification_status": status, "verified_title": found, "title_similarity": f"{similarity:.4f}", "verification_source": source, "verification_note": note}); time.sleep(0.12)
        except Exception as exc:
            output.append({**row, "verification_status": "lookup_failed", "verified_title": found, "title_similarity": "", "verification_source": source, "verification_note": f"{type(exc).__name__}: {exc}"})
    fields = list(rows[0]) if rows else ["title", "doi", "pmid"]
    fields += ["verification_status", "verified_title", "title_similarity", "verification_source", "verification_note"]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore"); writer.writeheader(); writer.writerows(output)
    failed = sum(x["verification_status"] != "verified" for x in output); print(json.dumps({"citations": len(output), "verified": len(output) - failed, "requires_resolution": failed, "output": str(args.output)}))
    return 1 if failed else 0


if __name__ == "__main__": raise SystemExit(main())
