#!/usr/bin/env python3
"""Run matched-candidate topic-opportunity baselines and ablations."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from metawingman_core.topic_opportunity_controls import evaluate_topic_control_arms


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("landscape", type=Path)
    parser.add_argument("candidates", type=Path)
    parser.add_argument("labels", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    try:
        landscape = json.loads(args.landscape.read_text(encoding="utf-8"))
        candidates = json.loads(args.candidates.read_text(encoding="utf-8"))
        labels = json.loads(args.labels.read_text(encoding="utf-8"))
        result = evaluate_topic_control_arms(
            landscape,
            candidates,
            target_candidate_ids=set(labels["target_candidate_ids"]),
            false_opportunity_candidate_ids=set(labels["false_opportunity_candidate_ids"]),
            created_at_utc=labels.get("created_at_utc"),
        )
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}))
        return 1
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
