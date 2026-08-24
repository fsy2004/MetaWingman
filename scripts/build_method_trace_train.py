#!/usr/bin/env python3
"""Build method-trace TRAINING data from the 40 real published-meta structure
signals. Each sample teaches the agent to map (clinical question + evidence
structural signal) -> the real design decision that published review actually
made. Outcome values were stripped during extraction, so the agent learns the
*process*, never the answer.

Addresses the same-source leak honestly: the OUTPUT is created from real,
independently-extracted signals (arm count, reference standard, prediction model,
outcome unit, pooled, living) — NOT from a mapping we feed the agent. The agent's
input question/landscape is built from those signals; the gold completion is the
reference design.

NOTE: a genuinely OOD holdout for measuring "training lift" must be a SEPARATE
batch of published reviews that never appear in this training file. This file is
labeled training-only; do not score it as a held-out gain.

Output: research/method-trace-train.jsonl
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
SIGNAL = REPO / "research" / "method-trace-gold-signal.jsonl"
OUT = REPO / "research" / "method-trace-train.jsonl"


def main() -> int:
    rows = [json.loads(l) for l in SIGNAL.read_text(encoding="utf-8").splitlines() if l.strip()]
    samples = []
    skipped = 0
    for row in rows:
        gold = normalize_gold_trace(row)
        if gold is None:
            skipped += 1
            continue
        signal = gold.get("signal") or {}
        question, landscape = build_agent_input(signal)
        prompt_object = {
            "question": question,
            "evidence_structure": landscape,
        }
        completion_object = {
            "profile": gold["design_selection"],
            "estimand_identification": gold["estimand_identification"],
            "synthesis_route": gold["synthesis_choice"],
            "pooled": gold["poolable"],
            "living": gold["living_review"],
        }
        samples.append({
            "type": "design_selection",
            "prompt": json.dumps(prompt_object, ensure_ascii=False),
            "completion": json.dumps(completion_object, ensure_ascii=False),
            "meta": {
                "case_id": gold["case_id"],
                "profile": gold["design_selection"],
                "pooled": gold["poolable"],
                "living": gold["living_review"],
                "source": "independent_real_published_review_structure",
                "results_stripped": True,
            },
        })

    with OUT.open("w", encoding="utf-8") as handle:
        for s in samples:
            handle.write(json.dumps(s, ensure_ascii=False) + "\n")

    by_profile = {}
    for s in samples:
        by_profile[s["meta"]["profile"]] = by_profile.get(s["meta"]["profile"], 0) + 1
    summary = {"samples": len(samples), "skipped": skipped,
               "profile_distribution": by_profile,
               "note": "training-only; OOD holdout requires separately-extracted reviews (not included)",
               "out": str(OUT)}
    summary["receipt_sha256"] = sha256_json(summary)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
