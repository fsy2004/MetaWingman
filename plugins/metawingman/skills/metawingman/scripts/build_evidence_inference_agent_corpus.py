#!/usr/bin/env python3
"""Build family-isolated effect-direction actions from Evidence Inference 2.0."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import tarfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


LABELS = {"-1": "effect_decreased", "0": "no_significant_difference", "1": "effect_increased"}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _member(members: list[tarfile.TarInfo], suffix: str) -> tarfile.TarInfo:
    return next(item for item in members if item.name.endswith(suffix))


def _pmcid(value: object) -> str:
    return str(value or "").strip().upper().removeprefix("PMC")


def _clean(value: object, maximum: int) -> str:
    return " ".join(str(value or "").split())[:maximum]


def build_evidence_inference_corpus(archive_path: Path, outdir: Path, *, minimum_rows: int = 100) -> dict[str, Any]:
    outdir.mkdir(parents=True, exist_ok=False)
    discarded = Counter()
    with tarfile.open(archive_path, "r:gz") as archive:
        members = [item for item in archive.getmembers() if item.isfile()]

        def read_text(suffix: str) -> str:
            return archive.extractfile(_member(members, suffix)).read().decode("utf-8-sig", errors="strict")

        annotations = list(csv.DictReader(io.StringIO(read_text("annotations/annotations_merged.csv"))))
        prompts = list(csv.DictReader(io.StringIO(read_text("annotations/prompts_merged.csv"))))
        prompt_by_id: dict[str, dict[str, str]] = {}
        for row in prompts:
            prompt_by_id.setdefault(row["PromptID"].strip(), row)

        split_ids = {
            "train": {_pmcid(value) for value in read_text("annotations/splits/train_article_ids.txt").splitlines() if value.strip()},
            "development": {_pmcid(value) for value in read_text("annotations/splits/validation_article_ids.txt").splitlines() if value.strip()},
            "test": {_pmcid(value) for value in read_text("annotations/splits/test_article_ids.txt").splitlines() if value.strip()},
        }
        if (split_ids["train"] & split_ids["development"]) or (split_ids["train"] & split_ids["test"]) or (split_ids["development"] & split_ids["test"]):
            raise ValueError("Evidence Inference article splits overlap")

        documents: dict[str, str] = {}
        for member in members:
            if "/annotations/txt_files/PMC" not in member.name or not member.name.endswith(".txt"):
                continue
            article_id = _pmcid(Path(member.name).stem)
            documents[article_id] = archive.extractfile(member).read().decode("utf-8", errors="replace")

        valid_by_prompt: dict[str, list[dict[str, str]]] = defaultdict(list)
        for row in annotations:
            if row.get("Valid Label", "").strip().casefold() != "true" or row.get("Valid Reasoning", "").strip().casefold() != "true":
                discarded["invalid_annotation_rows"] += 1
                continue
            if row.get("Label Code", "").strip() not in LABELS:
                discarded["unknown_label_rows"] += 1
                continue
            valid_by_prompt[row["PromptID"].strip()].append(row)

        output_rows: dict[str, list[dict[str, Any]]] = {key: [] for key in split_ids}
        for prompt_id, rows in sorted(valid_by_prompt.items()):
            prompt = prompt_by_id.get(prompt_id)
            if prompt is None:
                discarded["missing_prompt"] += 1
                continue
            article_id = _pmcid(prompt.get("PMCID") or rows[0].get("PMCID"))
            split = next((name for name, ids in split_ids.items() if article_id in ids), None)
            if split is None:
                discarded["article_outside_frozen_splits"] += 1
                continue
            counts = Counter(row["Label Code"].strip() for row in rows)
            top_count = max(counts.values()); winners = sorted(label for label, count in counts.items() if count == top_count)
            if len(winners) != 1:
                discarded["label_ties"] += 1
                continue
            label = winners[0]
            candidates = sorted((row for row in rows if row["Label Code"].strip() == label), key=lambda row: (row.get("UserID", ""), row.get("Evidence Start", ""), row.get("Evidence End", "")))
            document = documents.get(article_id)
            if document is None:
                discarded["missing_document"] += 1
                continue
            selected = None
            for row in candidates:
                try:
                    start, end = int(float(row["Evidence Start"])), int(float(row["Evidence End"]))
                except (TypeError, ValueError):
                    continue
                if 0 <= start < end <= len(document) and document[start:end].strip():
                    selected = (row, start, end, document[start:end])
                    break
            if selected is None:
                discarded["invalid_source_offsets"] += 1
                continue
            source, start, end, span = selected
            context_start, context_end = max(0, start - 1200), min(len(document), end + 1200)
            identity = f"{article_id}|{prompt_id}|{label}|{start}|{end}"
            action = LABELS[label]
            output_rows[split].append({
                "example_id": "evidence-inference-v2-" + hashlib.sha256(identity.encode()).hexdigest()[:20],
                "family_id": f"evidence-inference-PMC{article_id}",
                "split": split,
                "document_id": f"PMC{article_id}",
                "prompt_id": prompt_id,
                "input_state": {
                    "intervention": _clean(prompt.get("Intervention"), 500),
                    "comparator": _clean(prompt.get("Comparator"), 500),
                    "outcome": _clean(prompt.get("Outcome"), 500),
                    "evidence_context": document[context_start:context_end],
                    "evidence_span": span,
                },
                "target_action": {"type": action, "source_section": "result_extraction"},
                "target_decision": {"status": action},
                "source_span": {"start": start, "end": end, "sha256": hashlib.sha256(span.encode()).hexdigest()},
                "source_span_verified": True,
                "annotation_text_matches_span": _clean(source.get("Annotations"), 4000).casefold() in _clean(span, 4000).casefold(),
                "label_votes": dict(sorted(counts.items())),
                "label_authority": "evidence_inference_v2_doctor_annotation_majority",
                "published_review_answer_used_as_gold": False,
            })

    datasets: dict[str, dict[str, Any]] = {}
    families: dict[str, set[str]] = {}
    for split, rows in output_rows.items():
        rows.sort(key=lambda row: (row["family_id"], row["prompt_id"], row["example_id"]))
        if len(rows) < minimum_rows:
            raise ValueError(f"{split} has too few Evidence Inference examples")
        path = outdir / f"{split}.jsonl"
        path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
        families[split] = {row["family_id"] for row in rows}
        datasets[split] = {"path": str(path), "sha256": _sha(path), "examples": len(rows), "families": len(families[split]), "actions": dict(Counter(row["target_action"]["type"] for row in rows))}
    overlaps = {f"{a}__{b}": sorted(families[a] & families[b]) for a, b in (("train", "development"), ("train", "test"), ("development", "test"))}
    if any(overlaps.values()):
        raise ValueError("Evidence Inference output family overlap")
    manifest = {"schema_version": "1.0", "status": "complete", "scope": "result_direction_from_verified_source_span", "archive_path": str(archive_path), "archive_sha256": _sha(archive_path), "datasets": datasets, "family_overlaps": overlaps, "discarded": dict(discarded), "published_review_answer_policy": "excluded"}
    manifest_path = outdir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {**manifest, "manifest_path": str(manifest_path), "manifest_sha256": _sha(manifest_path)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--outdir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build_evidence_inference_corpus(args.archive, args.outdir), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
