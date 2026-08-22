#!/usr/bin/env python3
"""Replay a preregistered unknown/post-cutoff verifier counterfactual."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from metawingman.scripts.metawingman_core.conclusion_directed_acquisition import (
    AcquisitionError,
    replay_verifier_counterfactual,
)
from metawingman.scripts.metawingman_core.operational_corpus import load_jsonl_records
from metawingman.scripts.metawingman_core.state_store import atomic_write_json


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("--source-lock", type=Path, required=True)
    parser.add_argument("--operational-corpus", type=Path, required=True)
    parser.add_argument("--raw-corpus", type=Path, required=True)
    parser.add_argument("--source-outputs", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    if plan.get("provider_calls") != 0:
        raise AcquisitionError("counterfactual replay must make zero provider calls")
    lock_sha = _sha256(args.source_lock)
    lock = json.loads(args.source_lock.read_text(encoding="utf-8"))
    if lock_sha != plan.get("source_lock_sha256") or lock.get("status") != "locked" or lock.get("locked_slots") != 12:
        raise AcquisitionError("counterfactual source lock is missing, incomplete, or drifted")

    operational = load_jsonl_records(args.operational_corpus)
    raw = load_jsonl_records(args.raw_corpus)
    post_id = str(plan["postcutoff_candidate_id"])
    source_post = next((row for row in raw if str(row.get("id")) == post_id), None)
    if source_post is None or str(source_post.get("first_publication_date")) != plan["postcutoff_first_publication_date"]:
        raise AcquisitionError("preregistered post-cutoff record is missing or date-drifted")
    postcutoff_record = dict(source_post)
    postcutoff_record["cutoff_verification"] = {
        "status": "passed",
        "conservative_latest_date": plan["postcutoff_first_publication_date"],
        "cutoff": plan["historical_cutoff"],
    }

    replays = []
    for configuration_id in plan["source_configurations"]:
        for seed in plan["seeds"]:
            source_path = args.source_outputs / f"{configuration_id}-{seed}.json"
            source = json.loads(source_path.read_text(encoding="utf-8"))
            replay = replay_verifier_counterfactual(
                operational,
                source["proposed_candidate_ids"],
                cutoff=plan["historical_cutoff"],
                unknown_candidate_id=plan["unknown_candidate_id"],
                postcutoff_record=postcutoff_record,
            )
            expected = plan["expected"]
            audit = replay["verification_audit_delta"]
            if (
                audit["unknown"] != expected["unknown_rejected"]
                or audit["post_cutoff"] != expected["postcutoff_rejected"]
                or replay["baseline_verified_preserved"] is not expected["baseline_verified_preserved"]
            ):
                raise AcquisitionError("counterfactual result did not match the preregistered expectation")
            replay.update({
                "configuration_id": configuration_id,
                "seed": seed,
                "source_output_sha256": _sha256(source_path),
            })
            replays.append(replay)
    report = {
        "schema_version": "1.0",
        "counterfactual_id": plan["counterfactual_id"],
        "registration_timing": plan["registration_timing"],
        "plan_sha256": _sha256(args.plan),
        "source_lock_sha256": lock_sha,
        "provider_calls": 0,
        "replays": replays,
        "status": "completed_expected_delta_recovered",
    }
    atomic_write_json(args.out, report)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AcquisitionError, KeyError, OSError, json.JSONDecodeError) as exc:
        raise SystemExit(str(exc)) from None
