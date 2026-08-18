"""Build weak-supervised training candidates for the appraisal-step
verifier component (R6, trained version).

Task: given an appraisal-role passage, classify the risk-of-bias domain it
discusses (selection / performance / detection / attrition / reporting /
other). Labels are deterministic keyword rules — weak supervision, NOT
gold; the trained component's ceiling is rule-consistency, and independent
human validation remains a separate gate.

Usage (on the training server):
  python metawingman/scripts/build_appraisal_step_candidates.py \
    validation-output/training-corpus/training-examples.jsonl \
    --out validation-output/training-corpus/appraisal-step-candidates.jsonl \
    --stats validation-output/training-corpus/appraisal-step-stats.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

DOMAIN_RULES: list[tuple[str, list[str]]] = [
    ("selection_bias", ["allocation concealment", "random sequence", "baseline imbalance", "randomisation", "randomization"]),
    ("performance_bias", ["blinding of participants", "blinding of personnel", "blinded participants", "double-blind", "blinding of providers"]),
    ("detection_bias", ["blinding of outcome", "outcome assessor", "blinded assessor", "assessment blinded"]),
    ("attrition_bias", ["lost to follow", "withdrawal", "dropout", "incomplete outcome", "intention-to-treat", "per-protocol", "missing outcome"]),
    ("reporting_bias", ["selective reporting", "prespecified outcome", "pre-specified outcome", "protocol deviation", "unreported outcome", "selective outcome"]),
]
OTHER_LABEL = "other"
UNMATCHED_LABEL = "abstain"


def classify_domain(text: str) -> str:
    lowered = text.lower()
    for label, terms in DOMAIN_RULES:
        if any(term in lowered for term in terms):
            return label
    if re.search(r"\b(bias|risk of bias|quality)\b", lowered):
        return OTHER_LABEL
    return UNMATCHED_LABEL


def build_candidates(examples_path: Path, out_path: Path, stats_path: Path) -> dict[str, Any]:
    counts: dict[str, int] = {}
    written = 0
    with examples_path.open("r", encoding="utf-8") as source, out_path.open("w", encoding="utf-8") as target:
        for line in source:
            if not line.strip():
                continue
            example = json.loads(line)
            if example.get("task") != "section_role_classification":
                continue
            if example.get("target", {}).get("section_role") != "appraisal":
                continue
            text = example.get("input_text") or ""
            label = classify_domain(text)
            counts[label] = counts.get(label, 0) + 1
            if label == UNMATCHED_LABEL:
                continue
            candidate = {
                "schema_version": "1.0",
                "candidate_id": "appraisal-step:" + hashlib.sha256((example.get("example_id", "") + label).encode()).hexdigest()[:20],
                "source_example_id": example.get("example_id"),
                "family_id": example.get("family_id"),
                "split": example.get("split"),
                "text": text[:4000],
                "weak_label": label,
                "label_status": "deterministic_weak_supervision_requires_independent_validation",
            }
            target.write(json.dumps(candidate, ensure_ascii=False) + "\n")
            written += 1
    stats = {"written": written, "label_counts": counts}
    stats_path.write_text(json.dumps(stats, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return stats


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("examples", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--stats", type=Path, required=True)
    args = parser.parse_args()
    try:
        stats = build_candidates(args.examples, args.out, args.stats)
        print(json.dumps(stats, indent=2, ensure_ascii=False))
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"error": str(exc)}, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
