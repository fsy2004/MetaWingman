#!/usr/bin/env python3
"""Build a frozen, family-held-out protocol-action test corpus.

The frozen test set is disjoint from the families already used for training
and development in the multi-family protocol-action corpus. Gold labels come
from exact, license-permitted JATS methods-heading maps (same deterministic
authority as the training/dev corpus); no published answer is used as gold.

The evaluation that consumes this corpus compares the unadapted base model
against the existing Skill-method LoRA student under an identical evaluation
budget, on a set of review families never seen during training.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from metawingman.scripts.build_multifamily_protocol_corpus import (
    ALLOWED_LICENSE_PREFIXES,
    _sha_path,
    extract_method_examples,
)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _family_ids(path: Path) -> set[str]:
    if not path.is_file():
        raise ValueError(f"existing corpus split missing: {path}")
    return {row["family_id"] for row in _read_jsonl(path) if row.get("family_id")}


def select_test_records(
    records: list[dict[str, Any]],
    excluded_families: set[str],
    *,
    max_test_articles: int,
) -> list[dict[str, Any]]:
    eligible = [
        row
        for row in records
        if row.get("pmcid")
        and str(row.get("declared_license") or "").casefold().startswith(ALLOWED_LICENSE_PREFIXES)
        and str(row.get("family_id") or "") not in excluded_families
    ]
    eligible.sort(key=lambda row: hashlib.sha256(str(row["record_id"]).encode()).hexdigest())
    selected: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in eligible:
        family = str(row.get("family_id") or "")
        if not family or family in seen:
            continue
        selected.append(row)
        seen.add(family)
        if len(selected) == max_test_articles:
            break
    return selected


def build(
    plan_path: Path,
    existing_train: Path,
    existing_development: Path,
    outdir: Path,
    *,
    max_test_articles: int,
    min_test_examples: int,
    delay_seconds: float = 0.05,
) -> dict[str, object]:
    import time
    import urllib.request

    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    excluded = _family_ids(existing_train) | _family_ids(existing_development)
    selected = select_test_records(plan["records"], excluded, max_test_articles=max_test_articles)
    outdir.mkdir(parents=True, exist_ok=False)
    source_dir = outdir / "sources"
    source_dir.mkdir()
    examples: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    for record in selected:
        url = f"https://www.ebi.ac.uk/europepmc/webservices/rest/{record['pmcid']}/fullTextXML"
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "MetaWingman/1.0 (frozen test corpus builder)"})
            with urllib.request.urlopen(request, timeout=45) as response:
                xml_bytes = response.read()
            xml_path = source_dir / f"{record['pmcid']}.xml"
            xml_path.write_bytes(xml_bytes)
            rows = extract_method_examples(xml_bytes, record)
            if not rows:
                raise ValueError("no mapped methods paragraphs")
            for row in rows:
                row["source_xml_sha256"] = hashlib.sha256(xml_bytes).hexdigest()
            examples.extend(rows)
        except Exception as exc:
            failures.append({"record_id": record["record_id"], "error_type": type(exc).__name__})
        time.sleep(delay_seconds)
    if len(examples) < min_test_examples:
        raise ValueError(f"insufficient frozen test examples: {len(examples)}")
    test_path = outdir / "test.jsonl"
    test_path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in examples),
        encoding="utf-8",
    )
    manifest = {
        "schema_version": "1.0",
        "status": "complete",
        "scope": "protocol_action_stage_only",
        "label_authority": "exact_licensed_jats_methods_heading_map_not_published_answer",
        "split_role": "frozen_family_held_out_test",
        "plan_path": str(plan_path),
        "plan_sha256": _sha_path(plan_path),
        "excluded_families_source": {"train": str(existing_train), "development": str(existing_development)},
        "excluded_family_count": len(excluded),
        "test": {
            "path": str(test_path),
            "sha256": _sha_path(test_path),
            "examples": len(examples),
            "families": len({row["family_id"] for row in examples}),
        },
        "selected_articles": [row["record_id"] for row in selected],
        "failed_articles": failures,
        "family_overlap_with_existing": sorted({row["family_id"] for row in examples} & excluded),
    }
    if manifest["family_overlap_with_existing"]:
        raise ValueError("frozen test family overlap with existing corpus")
    manifest_path = outdir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {**manifest, "manifest_path": str(manifest_path), "manifest_sha256": _sha_path(manifest_path)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--existing-train", type=Path, required=True)
    parser.add_argument("--existing-development", type=Path, required=True)
    parser.add_argument("--outdir", type=Path, required=True)
    parser.add_argument("--max-test-articles", type=int, default=60)
    parser.add_argument("--min-test-examples", type=int, default=120)
    args = parser.parse_args()
    print(
        json.dumps(
            build(
                args.plan,
                args.existing_train,
                args.existing_development,
                args.outdir,
                max_test_articles=args.max_test_articles,
                min_test_examples=args.min_test_examples,
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
