#!/usr/bin/env python3
"""Build family-isolated full-text selection actions from the pinned CSMeD-FT archive."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _clean(value: object, maximum: int) -> str:
    return " ".join(str(value or "").split())[:maximum]


def build_csmed_corpus(archive_path: Path, outdir: Path, *, minimum_rows: int = 100) -> dict[str, Any]:
    csv.field_size_limit(64 * 1024 * 1024)
    outdir.mkdir(parents=True, exist_ok=False)
    datasets: dict[str, dict[str, Any]] = {}
    family_sets: dict[str, set[str]] = {}
    with zipfile.ZipFile(archive_path) as archive:
        for output_split, source_split in (("train", "train"), ("development", "dev"), ("test", "test")):
            metadata_name = f"CSMeD-FT/CSMeD-FT-{source_split}_reviews_metadata.json"
            metadata = json.loads(archive.read(metadata_name))
            csv_name = f"CSMeD-FT/CSMeD-FT-{source_split}.csv"
            with archive.open(csv_name) as raw:
                reader = csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8-sig", errors="strict", newline=""))
                source_rows = list(reader)
            rows = []
            for source in source_rows:
                review_id = source["review_id"].strip(); review = metadata[review_id]
                decision = source["decision"].strip().casefold()
                if decision not in {"included", "excluded"}:
                    continue
                identity = f"{review_id}|{source['document_id']}|{decision}"
                rows.append({
                    "example_id": "csmed-ft-" + hashlib.sha256(identity.encode()).hexdigest()[:20],
                    "family_id": review_id, "split": output_split, "document_id": source["document_id"],
                    "input_state": {
                        "review_title": _clean(review.get("title"), 500),
                        "eligibility_criteria": _clean(review.get("criteria_text") or review.get("criteria"), 6000),
                        "candidate_title": _clean(source.get("title"), 500),
                        "candidate_abstract": _clean(source.get("abstract"), 3000),
                        "candidate_full_text": _clean(source.get("main_text"), 12000),
                    },
                    "target_action": {"type": "include" if decision == "included" else "exclude", "source_section": "full_text_selection"},
                    "target_decision": {"status": "include" if decision == "included" else "exclude"},
                    "reason_for_exclusion": _clean(source.get("reason_for_exclusion"), 500) if decision == "excluded" else "",
                    "label_authority": "csmed_ft_human_full_text_decision",
                    "published_review_abstract_used": False,
                })
            if len(rows) < minimum_rows:
                raise ValueError(f"{output_split} has too few rows")
            path = outdir / f"{output_split}.jsonl"
            path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
            families = {row["family_id"] for row in rows}; family_sets[output_split] = families
            datasets[output_split] = {"path": str(path), "sha256": _sha(path), "examples": len(rows), "families": len(families),
                                      "decisions": dict(Counter(row["target_action"]["type"] for row in rows))}
    overlaps = {f"{a}__{b}": sorted(family_sets[a] & family_sets[b]) for a, b in (("train", "development"), ("train", "test"), ("development", "test"))}
    if any(overlaps.values()):
        raise ValueError("CSMeD family splits overlap")
    manifest = {"schema_version": "1.0", "status": "complete", "scope": "full_text_selection_stage",
                "archive_path": str(archive_path), "archive_sha256": _sha(archive_path), "datasets": datasets,
                "family_overlaps": overlaps, "review_abstract_policy": "excluded_to_prevent_published_result_leakage"}
    path = outdir / "manifest.json"; path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {**manifest, "manifest_path": str(path), "manifest_sha256": _sha(path)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument("--archive", type=Path, required=True); parser.add_argument("--outdir", type=Path, required=True)
    args = parser.parse_args(); print(json.dumps(build_csmed_corpus(args.archive, args.outdir), indent=2, sort_keys=True)); return 0


if __name__ == "__main__": raise SystemExit(main())
