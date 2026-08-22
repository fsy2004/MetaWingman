#!/usr/bin/env python3
"""Build a family-isolated protocol-action corpus from licensed JATS methods."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
from typing import Any


ACTION_PATTERNS = (
    ("registration", r"protocol|registration|prospero"),
    ("search", r"search|information source|database"),
    ("eligibility", r"eligib|inclusion|exclusion|selection criteria"),
    ("screening", r"screen|study selection|record selection"),
    ("extraction", r"extract|data collection|data item"),
    ("risk_of_bias", r"risk of bias|quality assessment|critical appraisal"),
    ("certainty", r"grade|certainty|quality of evidence"),
    ("synthesis", r"statistic|analysis|synthes|meta-analysis|heterogeneity"),
    ("reporting", r"reporting|prisma"),
    ("living_update", r"living|update"),
)
ALLOWED_LICENSE_PREFIXES = ("cc by", "cc0", "public domain")


def _sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha_path(path: Path) -> str:
    return _sha_bytes(path.read_bytes())


def _text(element: ET.Element) -> str:
    return re.sub(r"\s+", " ", "".join(element.itertext())).strip()


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _action(title: str) -> str | None:
    normalized = title.casefold()
    return next((name for name, pattern in ACTION_PATTERNS if re.search(pattern, normalized)), None)


def _method_trace(action: str, title: str, anchor: str) -> dict[str, str]:
    action_story = {
        "registration": "Protocol registration fixes the question before results can reshape it.",
        "search": "Search coverage determines whether the review can see the evidence needed to answer the question.",
        "eligibility": "Eligibility criteria decide which clinical comparison the review is actually about.",
        "screening": "Screening decisions can remove studies that would change the conclusion.",
        "extraction": "Extraction choices define the result values and estimands that enter synthesis.",
        "risk_of_bias": "Bias judgments can change whether an effect is credible enough to support a claim.",
        "certainty": "Certainty assessment controls how far the conclusion may travel beyond the evidence.",
        "synthesis": "The synthesis route can change whether a pooled answer is valid or misleading.",
        "reporting": "Reporting completeness controls whether readers can audit the conclusion.",
        "living_update": "Update rules decide when new evidence should reopen a settled conclusion.",
    }
    decision_tension = action_story.get(
        action,
        "This method choice can change the review question, evidence base, or conclusion.",
    )
    return {
        "decision_tension": decision_tension,
        "disconfirmation_design": (
            f"Challenge the {title} method by looking for a missing source, incompatible "
            "criterion, unsupported estimand, or alternative route that would change the action."
        ),
        "evidence_gap_anchor": anchor,
        "stopping_rule": (
            "Accept only after the source span is exact, the action is method-compatible, "
            "and no conclusion-changing missingness remains in this step."
        ),
    }


def select_records(records: list[dict[str, Any]], *, max_train_articles: int, max_dev_articles: int) -> dict[str, list[dict[str, Any]]]:
    selected: dict[str, list[dict[str, Any]]] = {}
    seen: set[str] = set()
    for split, limit in (("train", max_train_articles), ("development", max_dev_articles)):
        eligible = [row for row in records if row.get("split") == split and row.get("pmcid") and
                    str(row.get("declared_license") or "").casefold().startswith(ALLOWED_LICENSE_PREFIXES)]
        eligible.sort(key=lambda row: hashlib.sha256(str(row["record_id"]).encode()).hexdigest())
        rows = []
        for row in eligible:
            family = str(row.get("family_id") or "")
            if not family or family in seen:
                continue
            rows.append(row); seen.add(family)
            if len(rows) == limit:
                break
        selected[split] = rows
    return selected


def extract_method_examples(xml_bytes: bytes, record: dict[str, Any]) -> list[dict[str, Any]]:
    root = ET.fromstring(xml_bytes)
    methods = []
    for section in root.iter():
        if _local(section.tag) != "sec":
            continue
        title_node = next((child for child in section if _local(child.tag) == "title"), None)
        title = _text(title_node) if title_node is not None else ""
        if section.get("sec-type") == "methods" or re.fullmatch(r"methods?", title.casefold()):
            methods.append(section)
    if not methods:
        return []
    rows: list[dict[str, Any]] = []
    visited: set[int] = set()
    for container in methods:
        for section in container.iter():
            if _local(section.tag) != "sec":
                continue
            title_node = next((child for child in section if _local(child.tag) == "title"), None)
            title = _text(title_node) if title_node is not None else ""
            action = _action(title)
            if action is None:
                continue
            paragraph_index = 0
            for child in section:
                if _local(child.tag) != "p" or id(child) in visited:
                    continue
                statement = _text(child)
                if len(statement) < 80:
                    continue
                visited.add(id(child)); paragraph_index += 1
                identity = f"{record['record_id']}|{title}|{paragraph_index}|{statement}"
                rows.append({
                    "example_id": "protocol-" + hashlib.sha256(identity.encode()).hexdigest()[:20],
                    "record_id": record["record_id"], "family_id": record["family_id"],
                    "split": record["split"], "pmcid": record["pmcid"], "title": record.get("title"),
                    "license": record.get("declared_license"), "source_section_title": title,
                    "source_anchor": f"jats/methods/{title.casefold()}/paragraph-{paragraph_index}",
                    "method_statement": statement,
                    "input_state": {"source_section": title, "method_statement": statement},
                    "target_action": {"type": action, "source_section": action},
                    "target_decision": {"status": "accept"},
                    "target_method_trace": _method_trace(
                        action,
                        title,
                        f"jats/methods/{title.casefold()}/paragraph-{paragraph_index}",
                    ),
                    "published_answer_used_as_gold": False,
                })
    return rows


def build(plan_path: Path, outdir: Path, *, max_train_articles: int, max_dev_articles: int,
          min_train_examples: int, min_dev_examples: int, delay_seconds: float = 0.05) -> dict[str, Any]:
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    selected = select_records(plan["records"], max_train_articles=max_train_articles, max_dev_articles=max_dev_articles)
    outdir.mkdir(parents=True, exist_ok=False)
    source_dir = outdir / "sources"; source_dir.mkdir()
    examples = {"train": [], "development": []}
    failures = []
    for split in ("train", "development"):
        for record in selected[split]:
            url = f"https://www.ebi.ac.uk/europepmc/webservices/rest/{record['pmcid']}/fullTextXML"
            try:
                request = urllib.request.Request(url, headers={"User-Agent": "MetaWingman/1.0 (research corpus builder)"})
                with urllib.request.urlopen(request, timeout=45) as response:
                    xml_bytes = response.read()
                path = source_dir / f"{record['pmcid']}.xml"; path.write_bytes(xml_bytes)
                rows = extract_method_examples(xml_bytes, record)
                if not rows:
                    raise ValueError("no mapped methods paragraphs")
                for row in rows:
                    row["source_xml_sha256"] = _sha_bytes(xml_bytes)
                examples[split].extend(rows)
            except Exception as exc:  # network and heterogeneous JATS failures are retained
                failures.append({"record_id": record["record_id"], "split": split, "error_type": type(exc).__name__})
            time.sleep(delay_seconds)
    if len(examples["train"]) < min_train_examples or len(examples["development"]) < min_dev_examples:
        raise ValueError(f"insufficient extracted examples: train={len(examples['train'])}, development={len(examples['development'])}")
    paths = {}
    for split, rows in examples.items():
        path = outdir / f"{split}.jsonl"
        path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
        paths[split] = {"path": str(path), "sha256": _sha_path(path), "examples": len(rows),
                        "families": len({row["family_id"] for row in rows}), "actions": dict(Counter(row["target_action"]["type"] for row in rows))}
    manifest = {"schema_version": "1.0", "status": "complete", "scope": "protocol_action_stage_only",
                "label_authority": "exact_licensed_jats_methods_heading_map_not_published_answer",
                "plan_path": str(plan_path), "plan_sha256": _sha_path(plan_path), "datasets": paths,
                "failed_articles": failures, "family_overlap": sorted({row["family_id"] for row in examples["train"]} & {row["family_id"] for row in examples["development"]})}
    if manifest["family_overlap"]:
        raise ValueError("train/development family overlap")
    manifest_path = outdir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {**manifest, "manifest_path": str(manifest_path), "manifest_sha256": _sha_path(manifest_path)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True); parser.add_argument("--outdir", type=Path, required=True)
    parser.add_argument("--max-train-articles", type=int, default=240); parser.add_argument("--max-dev-articles", type=int, default=80)
    parser.add_argument("--min-train-examples", type=int, default=800); parser.add_argument("--min-dev-examples", type=int, default=200)
    args = parser.parse_args()
    print(json.dumps(build(args.plan, args.outdir, max_train_articles=args.max_train_articles, max_dev_articles=args.max_dev_articles,
                           min_train_examples=args.min_train_examples, min_dev_examples=args.min_dev_examples), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
