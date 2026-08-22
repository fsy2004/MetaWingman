#!/usr/bin/env python3
"""Build verified topic-proposal trajectories from locked audit artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from metawingman_core.agent_distillation import build_topic_proposal_traces


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("proposal_batch", type=Path)
    parser.add_argument("landscape", type=Path)
    parser.add_argument("audit_dir", type=Path)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--review-family-id", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    batch = json.loads(args.proposal_batch.read_text(encoding="utf-8"))
    landscape = json.loads(args.landscape.read_text(encoding="utf-8"))
    candidates: dict[str, dict] = {}
    failures: dict[str, dict] = {}
    for path in sorted(args.audit_dir.glob(f"{args.seed}-*.candidate.json")):
        value = json.loads(path.read_text(encoding="utf-8"))
        candidate_id = str(value.get("candidate_id") or "")
        if not candidate_id.startswith("candidate-"):
            raise ValueError(f"invalid candidate ID in {path}")
        candidates[candidate_id.removeprefix("candidate-")] = value
    for path in sorted(args.audit_dir.glob(f"{args.seed}-*.failure.json")):
        value = json.loads(path.read_text(encoding="utf-8"))
        failures[str(value["proposal_id"])] = value
    traces = build_topic_proposal_traces(
        batch, landscape, candidates, failures,
        case_id=args.case_id, review_family_id=args.review_family_id, seed=args.seed,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        "\n".join(json.dumps(trace, ensure_ascii=False, sort_keys=True) for trace in traces) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": "completed", "out": str(args.out), "traces": len(traces)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
