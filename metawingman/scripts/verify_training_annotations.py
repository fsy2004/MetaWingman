#!/usr/bin/env python3
"""Verify model annotation candidates against exact source passages."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from metawingman_core.schema_guard import SchemaValidationError, validate_document, validate_jsonl_file


def _normalise(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tasks", type=Path, required=True)
    parser.add_argument("--runs", type=Path, required=True)
    args = parser.parse_args()
    tasks = {item["task_id"]: item for item in validate_jsonl_file(args.tasks, "external_agent_batch_task")}
    runs = validate_jsonl_file(args.runs, "external_agent_candidate_run")
    issues = []
    verified_annotations = 0
    abstained_runs = 0
    run_ids = [run["task_id"] for run in runs]
    if len(run_ids) != len(set(run_ids)):
        issues.append("candidate run stream contains duplicate task_id values")
    missing = sorted(set(tasks) - set(run_ids))
    if missing:
        issues.append("candidate run stream is incomplete: " + ", ".join(missing))
    for run in runs:
        task = tasks.get(run["task_id"])
        if task is None:
            issues.append(f"run references unknown task: {run['task_id']}")
            continue
        if run["status"] == "abstain":
            abstained_runs += 1
            continue
        candidate = run["candidate"]
        if run["output_schema"] != "training_annotation_candidate":
            issues.append(f"run uses the wrong output schema: {run['task_id']}")
            continue
        try:
            validate_document(candidate, "training_annotation_candidate")
        except SchemaValidationError as exc:
            issues.append(f"candidate schema drift: {run['task_id']}: {exc}")
            continue
        source = task["input_document"]
        if candidate["document_id"] != source["document_id"] or candidate["source_text_sha256"] != source["source_text_sha256"]:
            issues.append(f"candidate source identity mismatch: {run['task_id']}")
            continue
        passages = {item["section_path"]: _normalise(item["passage"]) for item in source["passages"]}
        for annotation in candidate["annotations"]:
            passage = passages.get(annotation["section_path"])
            if passage is None:
                issues.append(f"unknown section_path: {run['task_id']}:{annotation['section_path']}")
                continue
            if _normalise(annotation["evidence_excerpt"]) not in passage:
                issues.append(f"evidence excerpt is not an exact source substring: {run['task_id']}:{annotation['field']}")
                continue
            verified_annotations += 1
    result = {
        "valid": not issues, "issues": issues, "tasks": len(tasks), "runs": len(runs),
        "candidate_runs": len(runs) - abstained_runs, "abstained_runs": abstained_runs,
        "exact_anchor_verified_annotations": verified_annotations,
        "acceptance_boundary": "exact_anchor_verified_but_not_independently_validated_not_gold",
    }
    print(json.dumps(result, indent=2))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
