#!/usr/bin/env python3
"""Build an EXPANDED method-trace training set: 177 new extracted reviews +
the original 40, so the training signal is much larger. The holdout (40) is
never touched and stays OOD. Outcomes were stripped during extraction.

Output: research/method-trace-train-expanded.jsonl
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from metawingman.training.method_trace_normalizer import normalize_gold_trace
from metawingman.scripts.metawingman_core.state_store import sha256_json

from run_fidelity_real import build_agent_input  # reused construction

REPO = Path(__file__).resolve().parents[1]
LARGE_SIGNAL = REPO / "research" / "method-trace-large-signal.jsonl"
ORIG_TRAIN = REPO / "research" / "method-trace-train.jsonl"
OUT = REPO / "research" / "method-trace-train-expanded.jsonl"


def make_sample(record_id: str, gold: dict, signal: dict) -> dict:
    question, landscape = build_agent_input(signal)
    return {
        "type": "design_selection",
        "prompt": json.dumps({"question": question, "evidence_structure": landscape},
                             ensure_ascii=False),
        "completion": json.dumps({
            "profile": gold["design_selection"],
            "estimand_identification": gold["estimand_identification"],
            "synthesis_route": gold["synthesis_choice"],
            "pooled": gold["poolable"],
            "living": gold["living_review"],
        }, ensure_ascii=False),
        "meta": {"case_id": record_id, "profile": gold["design_selection"],
                 "pooled": gold["poolable"], "living": gold["living_review"],
                 "source": "independent_real_published_review_structure",
                 "results_stripped": True},
    }


def main() -> int:
    samples, seen = [], set()
    # new 177
    for line in LARGE_SIGNAL.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        gold = normalize_gold_trace(row)
        if gold is None:
            continue
        cid = gold["case_id"]
        if cid in seen:
            continue
        seen.add(cid)
        samples.append(make_sample(cid, gold, gold.get("signal") or {}))
    # original 40
    for line in ORIG_TRAIN.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        s = json.loads(line)
        cid = s["meta"]["case_id"]
        if cid in seen:
            continue
        seen.add(cid)
        samples.append(s)

    with OUT.open("w", encoding="utf-8") as handle:
        for s in samples:
            handle.write(json.dumps(s, ensure_ascii=False) + "\n")

    by_profile = {}
    for s in samples:
        by_profile[s["meta"]["profile"]] = by_profile.get(s["meta"]["profile"], 0) + 1
    print(json.dumps({
        "samples": len(samples),
        "profile_distribution": dict(sorted(by_profile.items(), key=lambda kv: -kv[1])),
        "note": "expanded training set (177 new + 40 original); OOD holdout untouched",
        "out": str(OUT),
        "receipt_sha256": sha256_json({"samples": len(samples), "profiles": by_profile}),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
