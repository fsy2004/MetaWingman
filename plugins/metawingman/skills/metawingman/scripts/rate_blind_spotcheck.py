"""Human rating tool for the VAL-2c blind appraisal spot-check.

Two modes:

1. export  --questions blind-questions.jsonl --out ratings.tsv
   Emits a rating sheet (task_id + passage + six choice labels) that the
   human rater fills in (or inspects in the exported order).

2. score   --questions ... --ratings ratings.tsv --key answer-key.jsonl --out report.json
   Computes Cohen's kappa with an approximate 95% CI (Fleiss SE formula),
   per-class agreement, and a confusion table. The sealed key is read
   internally and NEVER printed; the report contains only statistics.

Ratings file format: TSV with header "task_id\tlabel"; label must be one of
selection_bias/performance_bias/detection_bias/attrition_bias/reporting_bias/other.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path

DOMAIN_LABELS = (
    "selection_bias", "performance_bias", "detection_bias",
    "attrition_bias", "reporting_bias", "other",
)


def load_questions(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def load_key(path: Path) -> dict[str, str]:
    key = {}
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if not line.strip():
            continue
        entry = json.loads(line)
        key[entry["task_id"]] = entry["weak_label"]
    return key


def load_ratings(path: Path) -> dict[str, str]:
    ratings = {}
    with path.open(encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh, delimiter="\t"):
            task_id = (row.get("task_id") or "").strip()
            label = (row.get("label") or "").strip()
            if task_id:
                ratings[task_id] = label
    return ratings


def cohens_kappa(key: dict[str, str], ratings: dict[str, str]) -> dict:
    labels = DOMAIN_LABELS
    n = 0
    po_count = 0
    key_margin = {lab: 0 for lab in labels}
    rating_margin = {lab: 0 for lab in labels}
    confusion = {lab: {other: 0 for other in labels} for lab in labels}
    for task_id, true in key.items():
        rated = ratings.get(task_id)
        if rated is None or rated not in labels:
            continue  # unrated items are excluded from kappa but counted in coverage
        n += 1
        if rated == true:
            po_count += 1
        key_margin[true] += 1
        rating_margin[rated] += 1
        confusion[true][rated] += 1
    if n == 0:
        return {"scored": False, "reason": "no rated items matched the key"}
    po = po_count / n
    pe = sum(key_margin[lab] * rating_margin[lab] for lab in labels) / (n * n)
    kappa = (po - pe) / (1 - pe) if (1 - pe) > 0 else 0.0
    # Fleiss et al. 1969 approximate standard error.
    se = math.sqrt(po * (1 - po) / (n * (1 - pe) ** 2)) if (1 - pe) > 0 else float("nan")
    z = 1.96
    per_class = {}
    for lab in labels:
        total = key_margin[lab]
        per_class[lab] = {
            "n_reference": total,
            "agreed": confusion[lab][lab],
            "agreement": round(confusion[lab][lab] / total, 4) if total else None,
        }
    return {
        "scored": True,
        "n_rated": n,
        "n_key_total": len(key),
        "coverage": round(n / len(key), 4) if key else 0.0,
        "po": round(po, 4),
        "pe": round(pe, 4),
        "kappa": round(kappa, 4),
        "se_fleiss": round(se, 4),
        "ci95_low": round(kappa - z * se, 4),
        "ci95_high": round(kappa + z * se, 4),
        "se_note": "Fleiss et al. 1969 approximate SE, normal 95% CI",
        "band_convention": "Landis & Koch 1977 bands are a convention only (0.81/0.61/0.41)",
        "per_class_agreement": per_class,
        "confusion": confusion,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="mode", required=True)

    export_parser = sub.add_parser("export")
    export_parser.add_argument("--questions", type=Path, required=True)
    export_parser.add_argument("--out", type=Path, required=True)

    score_parser = sub.add_parser("score")
    score_parser.add_argument("--questions", type=Path, required=True)
    score_parser.add_argument("--ratings", type=Path, required=True)
    score_parser.add_argument("--key", type=Path, required=True)
    score_parser.add_argument("--out", type=Path, required=True)

    args = parser.parse_args()
    try:
        if args.mode == "export":
            questions = load_questions(args.questions)
            with args.out.open("w", encoding="utf-8", newline="") as fh:
                writer = csv.writer(fh, delimiter="\t")
                writer.writerow(["task_id", "label", "passage"])
                for q in questions:
                    # Flatten newlines so one task = one row; the original
                    # passage stays available in the questions JSONL.
                    flat = " ".join(q["passage"].split())
                    writer.writerow([q["task_id"], "", flat])
            print(json.dumps({"mode": "export", "tasks": len(questions), "out": str(args.out)}, indent=2))
            return 0

        key = load_key(args.key)
        ratings = load_ratings(args.ratings)
        report = cohens_kappa(key, ratings)
        report["mode"] = "score"
        report["ratings_file"] = str(args.ratings)
        args.out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        # Never print the key; print only the statistics.
        printable = {k: v for k, v in report.items() if k != "confusion"}
        print(json.dumps(printable, indent=2, ensure_ascii=False))
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"error": str(exc)}, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
