#!/usr/bin/env python3
"""Download DOI-linked open-access PDFs through Unpaywall with audit logging."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from metawingman_core.network_security import (
    PublicNetworkError,
    public_https_opener,
    validate_public_https_url,
)


DEFAULT_MAX_BYTES = 100 * 1024 * 1024


def safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", value)[:160]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--outdir", required=True, type=Path)
    parser.add_argument("--doi-column", default="doi")
    parser.add_argument("--max-files", type=int, default=0)
    parser.add_argument("--max-bytes", type=int, default=DEFAULT_MAX_BYTES)
    args = parser.parse_args()
    email = os.getenv("UNPAYWALL_EMAIL", "").strip()
    if not email: raise SystemExit("Set UNPAYWALL_EMAIL; it is required by the Unpaywall API")
    if args.max_bytes < 1: raise SystemExit("--max-bytes must be positive")
    args.outdir.mkdir(parents=True, exist_ok=True)
    with args.input.open(encoding="utf-8-sig", newline="") as handle: rows = list(csv.DictReader(handle))
    log, downloaded = [], 0
    for row in rows:
        doi = row.get(args.doi_column, "").strip().lower()
        if not doi: continue
        item = {"record_id": row.get("record_id", ""), "doi": doi, "status": "", "oa_url": "", "resolved_url": "", "license": "", "host_type": "", "retrieved_at": datetime.now(timezone.utc).isoformat(), "sha256": "", "bytes": 0, "file": "", "note": ""}
        try:
            api = f"https://api.unpaywall.org/v2/{urllib.parse.quote(doi, safe='')}?email={urllib.parse.quote(email)}"
            req = urllib.request.Request(api, headers={"User-Agent": f"MetaWingman/1.0 mailto:{email}"})
            validate_public_https_url(api)
            with public_https_opener().open(req, timeout=60) as response:
                validate_public_https_url(response.geturl())
                meta = json.load(response)
            loc = meta.get("best_oa_location") or {}
            url = loc.get("url_for_pdf") or ""
            item.update({"oa_url": url, "license": loc.get("license") or "", "host_type": loc.get("host_type") or ""})
            if not meta.get("is_oa") or not url:
                item["status"] = "no_verified_oa_pdf"; log.append(item); continue
            validate_public_https_url(url)
            req = urllib.request.Request(url, headers={"User-Agent": f"MetaWingman/1.0 mailto:{email}"})
            with public_https_opener().open(req, timeout=120) as response:
                item["resolved_url"] = response.geturl()
                validate_public_https_url(item["resolved_url"])
                content_length = response.headers.get("Content-Length")
                if content_length and int(content_length) > args.max_bytes:
                    raise ValueError(f"PDF exceeds byte limit {args.max_bytes}")
                body = response.read(args.max_bytes + 1)
                content_type = response.headers.get("Content-Type", "")
            if len(body) > args.max_bytes:
                raise ValueError(f"PDF exceeds byte limit {args.max_bytes}")
            if not body.startswith(b"%PDF"):
                item["status"] = "rejected_not_pdf"; item["note"] = content_type; log.append(item); continue
            filename = safe_name(doi) + ".pdf"; path = args.outdir / filename; path.write_bytes(body)
            item.update({"status": "downloaded", "sha256": hashlib.sha256(body).hexdigest(), "bytes": len(body), "file": filename}); downloaded += 1; log.append(item)
            if args.max_files and downloaded >= args.max_files: break
            time.sleep(0.15)
        except (Exception, PublicNetworkError) as exc:
            item["status"] = "error"; item["note"] = f"{type(exc).__name__}: {exc}"; log.append(item)
    fields = ["record_id", "doi", "status", "oa_url", "resolved_url", "license", "host_type", "retrieved_at", "sha256", "bytes", "file", "note"]
    with (args.outdir / "download_audit.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader(); writer.writerows(log)
    print(json.dumps({"attempted": len(log), "downloaded": downloaded, "audit": str(args.outdir / 'download_audit.csv')}))
    return 0


if __name__ == "__main__": raise SystemExit(main())
