#!/usr/bin/env python3
"""Build source-anchored weak-supervision examples and freeze a model-neutral run plan."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from metawingman_core.schema_guard import validate_document
from metawingman_core.state_store import atomic_write_json, canonical_json
from metawingman_core.training_corpus import TrainingCorpusError, build_training_examples, build_training_run_plan


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--examples-out", type=Path, required=True)
    parser.add_argument("--run-plan-out", type=Path, required=True)
    parser.add_argument("--run-plan-id", default="metawingman-method-retrieval-v1")
    parser.add_argument("--maximum-characters", type=int, default=8000)
    parser.add_argument("--minimum-characters", type=int, default=200)
    parser.add_argument("--created-at-utc")
    args = parser.parse_args()
    try:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        validate_document(manifest, "training_document_manifest")
        examples = build_training_examples(
            manifest, args.artifact_root, maximum_characters=args.maximum_characters,
            minimum_characters=args.minimum_characters,
        )
        args.examples_out.parent.mkdir(parents=True, exist_ok=True)
        with args.examples_out.open("wb") as handle:
            for example in examples:
                handle.write(canonical_json(example) + b"\n")
        run_plan = build_training_run_plan(
            manifest, args.manifest, args.examples_out, examples,
            run_plan_id=args.run_plan_id, created_at_utc=args.created_at_utc,
        )
        atomic_write_json(args.run_plan_out, run_plan, "training_run_plan")
    except (OSError, json.JSONDecodeError, TrainingCorpusError, ValueError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        return 1
    print(json.dumps({
        "ok": True, "examples": len(examples), "examples_out": str(args.examples_out),
        "run_plan_out": str(args.run_plan_out), "dataset": run_plan["dataset"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
