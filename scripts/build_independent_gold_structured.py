#!/usr/bin/env python3
"""Build a structured, independently-extracted gold method-trajectory library
from the real published reviews, and report the real profile distribution.

This replaces the same-source gold with genuinely independent gold (extracted
from each paper's own methods). It is the ground truth for fidelity and the real
evidence that top-journal meta-analyses span many profiles, not just pairwise.
Outcome values were stripped during extraction.

Usage: python scripts/build_independent_gold_structured.py
Output: research/method-trace-gold-independent-structured.json
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from metawingman.training.method_trace_normalizer import normalize_batch
from metawingman.scripts.metawingman_core.state_store import sha256_json

REPO = Path(__file__).resolve().parents[1]
INP = REPO / "research" / "method-trace-gold-independent.jsonl"
OUT = REPO / "research" / "method-trace-gold-independent-structured.json"


def main() -> int:
    rows = []
    for line in INP.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    gold, skipped = normalize_batch(rows)

    profile_counts = Counter(g["design_selection"] for g in gold)
    pooled = sum(1 for g in gold if g["poolable"])
    living = sum(1 for g in gold if g["living_review"])

    data = {
        "schema_version": "1.0",
        "source": INP.name,
        "extracted_rows": len(rows),
        "normalized_gold": len(gold),
        "skipped": skipped,
        "profile_distribution": dict(sorted(profile_counts.items(), key=lambda kv: -kv[1])),
        "pooled_count": pooled,
        "living_count": living,
        "n_profiles_covered": len(profile_counts),
        "gold": gold,
    }
    data["receipt_sha256"] = sha256_json(data)
    OUT.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    print(f"extracted_rows={len(rows)}  normalized_gold={len(gold)}  skipped={skipped}")
    print("profile distribution (real published reviews):")
    for profile, n in data["profile_distribution"].items():
        print(f"  {profile:<26} {n}")
    print(f"pooled={pooled}/{len(gold)}   living={living}/{len(gold)}   profiles_covered={len(profile_counts)}")
    print(f"wrote {OUT.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
