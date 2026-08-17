#!/usr/bin/env python3
"""Audit a frozen MetaWingman training dataset, files, hashes, and family splits."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from metawingman_core.schema_guard import validate_jsonl_file
from metawingman_core.training_corpus import TrainingCorpusError, audit_training_dataset


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--examples", type=Path, required=True)
    parser.add_argument("--run-plan", type=Path, required=True)
    parser.add_argument("--artifact-root", type=Path, required=True)
    args = parser.parse_args()
    try:
        plan = json.loads(args.plan.read_text(encoding="utf-8"))
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        run_plan = json.loads(args.run_plan.read_text(encoding="utf-8"))
        examples = validate_jsonl_file(args.examples, "training_example")
        result = audit_training_dataset(
            plan, manifest, examples, run_plan, args.artifact_root,
            args.manifest, args.examples,
        )
    except (OSError, json.JSONDecodeError, TrainingCorpusError, ValueError) as exc:
        print(json.dumps({"valid": False, "issues": [str(exc)]}, indent=2))
        return 1
    print(json.dumps(result, indent=2))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
