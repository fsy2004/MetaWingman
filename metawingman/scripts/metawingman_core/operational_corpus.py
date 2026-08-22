"""Construct leakage-controlled operational literature corpora."""

from __future__ import annotations

import calendar
import json
import re
import unicodedata
from datetime import date
from pathlib import Path
from typing import Any, Iterable


_MONTHS = {
    name.casefold(): number
    for number in range(1, 13)
    for name in (calendar.month_abbr[number], calendar.month_name[number])
}


def load_jsonl_records(path: Path) -> list[dict[str, Any]]:
    """Load JSONL without treating Unicode line/paragraph separators as records."""
    text = path.read_text(encoding="utf-8-sig")
    return [json.loads(line) for line in text.split("\n") if line.strip()]


def _surface(value: Any) -> str:
    return unicodedata.normalize("NFKC", str(value or "")).casefold().strip()


def conservative_latest_date(value: Any, cutoff: date) -> date | None:
    """Return the latest date compatible with a publication-date string."""
    text = _surface(value)
    if not text:
        return None
    iso = re.match(r"^(\d{4})-(\d{2})-(\d{2})", text)
    if iso:
        try:
            return date(*(int(part) for part in iso.groups()))
        except ValueError:
            return None
    match = re.match(r"^(\d{4})\s+([a-z]+|\d{1,2})(?:\s+(\d{1,2}))?$", text)
    if match:
        year = int(match.group(1))
        month_text = match.group(2)
        month = int(month_text) if month_text.isdigit() else _MONTHS.get(month_text)
        if not month or not 1 <= month <= 12:
            return None
        day = int(match.group(3)) if match.group(3) else calendar.monthrange(year, month)[1]
        try:
            return date(year, month, day)
        except ValueError:
            return None
    year_match = re.match(r"^(\d{4})$", text)
    if year_match:
        year = int(year_match.group(1))
        if year < cutoff.year:
            return date(year, 12, 31)
        return None
    return None


def sanitize_records(
    records: Iterable[dict[str, Any]],
    *,
    cutoff: str,
    forbidden_identity_patterns: Iterable[str],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    cutoff_date = date.fromisoformat(cutoff)
    patterns = [_surface(pattern) for pattern in forbidden_identity_patterns if _surface(pattern)]
    clean: list[dict[str, Any]] = []
    audit = {
        "input_records": 0,
        "included": 0,
        "excluded_forbidden_identity": 0,
        "excluded_post_cutoff": 0,
        "excluded_unverifiable_date": 0,
    }
    for record in records:
        audit["input_records"] += 1
        identity = "\n".join(_surface(record.get(field)) for field in ("id", "pmid", "doi", "title"))
        if any(pattern in identity for pattern in patterns):
            audit["excluded_forbidden_identity"] += 1
            continue
        latest = conservative_latest_date(record.get("first_publication_date"), cutoff_date)
        if latest is None:
            audit["excluded_unverifiable_date"] += 1
            continue
        if latest > cutoff_date:
            audit["excluded_post_cutoff"] += 1
            continue
        normalized = dict(record)
        normalized["cutoff_verification"] = {
            "raw_publication_date": record.get("first_publication_date"),
            "conservative_latest_date": latest.isoformat(),
            "cutoff": cutoff,
            "status": "passed",
        }
        clean.append(normalized)
    audit["included"] = len(clean)
    return clean, audit
