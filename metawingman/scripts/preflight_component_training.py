#!/usr/bin/env python3
"""Validate a component training job offline or inspect an authorized server."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from metawingman_core.state_store import atomic_write_json
from metawingman_core.training_corpus import TrainingCorpusError, preflight_component_training


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("job", type=Path)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--inspect-server", action="store_true")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    try:
        job = json.loads(args.job.read_text(encoding="utf-8"))
        report = preflight_component_training(job, args.root, inspect_server=args.inspect_server)
    except (OSError, json.JSONDecodeError, TrainingCorpusError, ValueError) as exc:
        report = {"manifest_valid": False, "ready": False, "training_started": False, "reason_codes": ["preflight_error"], "error": str(exc)}
    if args.out:
        atomic_write_json(args.out, report)
    print(json.dumps(report, indent=2))
    return 0 if report["ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
