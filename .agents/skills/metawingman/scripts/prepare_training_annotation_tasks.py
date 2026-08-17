#!/usr/bin/env python3
"""Prepare bounded source passages for schema-gated model annotation candidates."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path

from metawingman_core.schema_guard import validate_document, validate_jsonl_file
from metawingman_core.state_store import canonical_json


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("examples", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--maximum-documents", type=int, default=4)
    parser.add_argument("--maximum-passages", type=int, default=8)
    parser.add_argument("--maximum-characters", type=int, default=30000)
    parser.add_argument("--max-tokens", type=int, default=2400)
    args = parser.parse_args()
    if args.maximum_documents < 1 or args.maximum_passages < 1 or args.maximum_characters < 1:
        raise SystemExit("maximum-documents, maximum-passages, and maximum-characters must be positive")
    examples = validate_jsonl_file(args.examples, "training_example")
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for example in examples:
        if example["task"] == "section_role_classification":
            grouped[example["document_id"]].append(example)
    selected = sorted(grouped, key=lambda value: hashlib.sha256(value.encode()).hexdigest())[:args.maximum_documents]
    tasks = []
    for document_id in selected:
        passages = []
        total = 0
        for example in sorted(grouped[document_id], key=lambda item: item["evidence_anchor"]["section_index"]):
            text = example["input_text"]
            if len(passages) >= args.maximum_passages or total + len(text) > args.maximum_characters:
                break
            passages.append({
                "section_path": example["evidence_anchor"]["section_path"],
                "section_title": example["target"]["section_title"],
                "passage": text,
                "passage_sha256": example["evidence_anchor"]["source_text_sha256"],
            })
            total += len(text)
        source_sha = hashlib.sha256(canonical_json(passages)).hexdigest()
        if not passages:
            continue
        input_document = {"document_id": document_id, "source_text_sha256": source_sha, "passages": passages}
        task = {
            "schema_version": "1.0", "task_id": "training-annotation-" + document_id.split(":", 1)[-1],
            "instruction": (
                "Extract only systematic-review method fields explicitly supported by the supplied passages. "
                "Every evidence_excerpt must be an exact contiguous substring of the named passage. "
                "Echo document_id and source_text_sha256, abstain for unsupported fields, and keep all labels candidate-only."
            ),
            "input_document": input_document, "output_schema": "training_annotation_candidate",
            "max_tokens": args.max_tokens, "thinking": False,
        }
        validate_document(task, "external_agent_batch_task")
        tasks.append(task)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("wb") as handle:
        for task in tasks:
            handle.write(canonical_json(task) + b"\n")
    print(json.dumps({"ok": True, "tasks": len(tasks), "out": str(args.out)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
