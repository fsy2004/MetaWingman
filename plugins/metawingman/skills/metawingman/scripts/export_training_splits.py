#!/usr/bin/env python3
"""Export frozen weak-supervision examples into model-neutral training formats."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

from metawingman_core.schema_guard import validate_document, validate_jsonl_file
from metawingman_core.state_store import atomic_write_json, canonical_json
from metawingman_core.training_corpus import TrainingCorpusError, build_retrieval_pairs, sha256_file, utc_now


def _chat_record(example: dict[str, object]) -> dict[str, object]:
    return {
        "example_id": example["example_id"], "family_id": example["family_id"],
        "messages": [
            {"role": "system", "content": "Return only the requested systematic-review section role and source section title."},
            {"role": "user", "content": str(example["instruction"]) + "\n\n" + str(example["input_text"])},
            {"role": "assistant", "content": json.dumps(example["target"], ensure_ascii=False, sort_keys=True)},
        ],
        "evidence_anchor": example["evidence_anchor"], "label_status": example["label_status"],
    }


def _retrieval_record(example: dict[str, object]) -> dict[str, object]:
    return {
        "example_id": example["example_id"], "family_id": example["family_id"],
        "query": example["instruction"], "positive_passage": example["input_text"],
        "target": example["target"], "evidence_anchor": example["evidence_anchor"],
        "label_status": example["label_status"], "negative_passages": [],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("examples", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--export-id", default="metawingman-training-export-v1")
    parser.add_argument("--created-at-utc")
    parser.add_argument("--training-plan", type=Path)
    parser.add_argument("--seed", type=int, default=20260815)
    args = parser.parse_args()
    try:
        examples = validate_jsonl_file(args.examples, "training_example")
        if not examples:
            raise TrainingCorpusError("training example stream is empty")
        family_splits: dict[str, set[str]] = defaultdict(set)
        for example in examples:
            family_splits[example["family_id"]].add(example["split"])
            if example["gold_label"] or example["label_status"] != "deterministic_weak_supervision_requires_independent_validation":
                raise TrainingCorpusError("export accepts only declared weak-supervision examples")
        conflicts = [family for family, splits in family_splits.items() if len(splits) > 1]
        if conflicts:
            raise TrainingCorpusError("review families cross exported splits")

        grouped: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
        for example in examples:
            grouped[(example["split"], example["task"])].append(example)
        args.out.mkdir(parents=True, exist_ok=True)
        export_entries = []
        split_counts = Counter()
        for (split, task), records in sorted(grouped.items()):
            if task == "section_role_classification":
                formatter, format_name, suffix, readiness = _chat_record, "chat_sft_jsonl", "section-role.sft", "candidate_sft_requires_review"
            else:
                formatter, format_name, suffix, readiness = _retrieval_record, "contrastive_positive_jsonl", "evidence-retrieval.positive", "positive_pairs_require_negative_mining"
            path = args.out / f"{split}.{suffix}.jsonl"
            with path.open("wb") as handle:
                for record in sorted(records, key=lambda item: item["example_id"]):
                    handle.write(canonical_json(formatter(record)) + b"\n")
            split_counts[split] += len(records)
            export_entries.append({
                "split": split, "task": task, "format": format_name,
                "relative_path": path.relative_to(args.out).as_posix(),
                "sha256": sha256_file(path), "records": len(records),
                "families": len({item["family_id"] for item in records}), "readiness": readiness,
            })
        pairs = []
        training_plan = None
        if args.training_plan:
            training_plan = json.loads(args.training_plan.read_text(encoding="utf-8"))
            validate_document(training_plan, "training_corpus_plan")
            strata_by_record = {
                item["record_id"]: item["biomedical_stratum"]
                for item in training_plan["records"]
                if "biomedical_stratum" in item
            }
            pairs = build_retrieval_pairs(examples, strata_by_record, args.seed)
            path = args.out / "evidence-retrieval.pairs.jsonl"
            with path.open("wb") as handle:
                for record in pairs:
                    handle.write(canonical_json(record) + b"\n")
            export_entries.append({
                "split": "mixed_train_development", "task": "evidence_retrieval", "format": "contrastive_pair_jsonl",
                "relative_path": path.relative_to(args.out).as_posix(), "sha256": sha256_file(path),
                "records": len(pairs), "families": len({item["query_family_id"] for item in pairs}),
                "readiness": "candidate_pairs_require_review",
            })
        manifest = {
            "schema_version": "1.1" if training_plan else "1.0", "export_id": args.export_id,
            "created_at_utc": args.created_at_utc or utc_now(),
            "source_examples": {"path": args.examples.as_posix(), "sha256": sha256_file(args.examples), "records": len(examples)},
            "policy": {
                "provider_neutral": True, "journal_feature_forbidden": True,
                "weak_labels_only": True, "retrieval_export_contains_positive_pairs_only": not bool(training_plan),
                "training_requires_model_and_license_review": True,
            },
            "summary": {
                "exports": len(export_entries), "records": len(examples), "families": len(family_splits),
                "train_records": split_counts["train"], "development_records": split_counts["development"],
                "held_out_records": 0,
            },
            "exports": export_entries,
        }
        if training_plan is not None:
            manifest["source_training_plan"] = {"path": args.training_plan.as_posix(), "sha256": sha256_file(args.training_plan), "records": len(training_plan["records"])}
            manifest["summary"].update({"pairs": len(pairs), "negative_pairs": sum(item["label"] == 0 for item in pairs)})
        atomic_write_json(args.out / "training-export-manifest.json", manifest, "training_export_manifest")
    except (OSError, TrainingCorpusError, ValueError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        return 1
    print(json.dumps({"ok": True, "manifest": str(args.out / "training-export-manifest.json"), "summary": manifest["summary"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
