#!/usr/bin/env python3
"""Create a deterministic, family-isolated OA training-corpus plan."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from metawingman_core.state_store import atomic_write_json
from metawingman_core.training_corpus import DEFAULT_LICENSES, TrainingCorpusError, build_training_plan, sha256_file


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--families", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--plan-id", default="top-journal-oa-training-v1")
    parser.add_argument("--maximum-records", type=int, default=24)
    parser.add_argument("--seed", type=int, default=20260815)
    parser.add_argument("--train-fraction", type=float, default=0.8)
    parser.add_argument("--allowed-license", action="append")
    parser.add_argument("--created-at-utc")
    args = parser.parse_args()
    try:
        corpus = json.loads(args.corpus.read_text(encoding="utf-8"))
        families = json.loads(args.families.read_text(encoding="utf-8"))
        plan = build_training_plan(
            corpus, families, plan_id=args.plan_id,
            source_corpus_path=args.corpus.as_posix(), source_corpus_sha256=sha256_file(args.corpus),
            family_registry_path=args.families.as_posix(), family_registry_sha256=sha256_file(args.families),
            maximum_records=args.maximum_records, seed=args.seed, train_fraction=args.train_fraction,
            allowed_licenses=args.allowed_license or DEFAULT_LICENSES, created_at_utc=args.created_at_utc,
        )
        atomic_write_json(args.out, plan, "training_corpus_plan")
    except (OSError, json.JSONDecodeError, TrainingCorpusError, ValueError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        return 1
    print(json.dumps({"ok": True, "out": str(args.out), "summary": plan["summary"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
