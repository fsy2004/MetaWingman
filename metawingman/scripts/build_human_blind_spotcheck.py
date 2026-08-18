"""Build the VAL-2b human-blind appraisal-domain spot-check set.

Purpose: freeze a reproducible 100-item sample from the appraisal-step
development split so a human reviewer can rate risk-of-bias domain labels
WITHOUT seeing the weak labels. The weak labels come from deterministic
rules (`build_appraisal_step_candidates.py`), so human agreement measures
rule clarity and annotation quality, NOT scientific validation of any
clinical claim. See docs/architecture/appraisal-human-blind-spotcheck-
protocol-2026-08-18.md for the frozen protocol.

Freeze-once semantics: the question file, sealed answer key, and manifest
are written only if absent. Re-running refuses to overwrite unless
--force is given (which records a new freeze generation).

Usage (server):
  python metawingman/scripts/build_human_blind_spotcheck.py \
    --candidates validation-output/training-corpus/appraisal-step-candidates.jsonl \
    --out-dir validation-output/independent-validation/human-blind-appraisal-spotcheck \
    --n 100 --seed 20260815
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import random
from pathlib import Path

DOMAIN_LABELS = (
    "selection_bias",
    "performance_bias",
    "detection_bias",
    "attrition_bias",
    "reporting_bias",
    "other",
)
INSTRUCTION = (
    "You are reviewing a passage from the methods or results of a systematic "
    "review / meta-analysis. Label the SINGLE risk-of-bias domain that this "
    "passage most directly concerns, choosing exactly one of: selection_bias, "
    "performance_bias, detection_bias, attrition_bias, reporting_bias, other. "
    "Base the label only on the passage text. Do not consult outside sources."
)


def load_candidates(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def stratified_sample(items: list[dict], n: int, seed: int) -> list[dict]:
    """Deterministic stratified sample by weak_label.

    Every label present in the pool gets a minimum share of
    min(count_in_pool, ceil(n / len(all_labels_in_pool))), then remaining
    slots go to the labels with the largest residual pool (sorted
    deterministically), all drawing via a seeded RNG per label.
    """
    by_label: dict[str, list[dict]] = {}
    for item in items:
        by_label.setdefault(item["weak_label"], []).append(item)
    labels_in_pool = sorted(by_label)
    rng = random.Random(seed)
    quota_min = -(-n // len(labels_in_pool))  # ceil
    chosen: list[dict] = []
    for label in labels_in_pool:
        pool = by_label[label]
        quota = min(len(pool), quota_min)
        chosen.extend(rng.sample(pool, quota))
    while len(chosen) < n:
        # Top up from labels whose pool still has unused items.
        candidates = [
            (len(by_label[label]) - sum(1 for c in chosen if c["weak_label"] == label), label)
            for label in labels_in_pool
        ]
        candidates.sort(key=lambda pair: (-pair[0], pair[1]))
        spare = candidates[0][1]
        pool = by_label[spare]
        taken = {id(c) for c in chosen}
        unused = [c for c in pool if id(c) not in taken]
        if not unused:
            break
        chosen.append(rng.sample(unused, 1)[0])
    return chosen


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--n", type=int, default=100)
    parser.add_argument("--seed", type=int, default=20260815)
    parser.add_argument("--force", action="store_true", help="overwrite an existing freeze (records a new generation)")
    args = parser.parse_args()

    try:
        candidates = load_candidates(args.candidates)
        dev = [c for c in candidates if c.get("split") == "development"]
        if len(dev) < args.n:
            raise ValueError(f"development split has {len(dev)} items, fewer than n={args.n}")
        args.out_dir.mkdir(parents=True, exist_ok=True)
        questions_path = args.out_dir / "blind-questions.jsonl"
        key_path = args.out_dir / "answer-key.jsonl"
        manifest_path = args.out_dir / "manifest.json"
        if not args.force and (questions_path.exists() or key_path.exists() or manifest_path.exists()):
            print(json.dumps({
                "execution_state": "already_frozen",
                "note": "spot-check set exists; re-run with --force to create a new generation",
                "out_dir": str(args.out_dir),
            }, indent=2))
            return 0

        sampled = stratified_sample(dev, args.n, args.seed)
        sampled.sort(key=lambda c: c["candidate_id"])
        questions = []
        key = []
        for index, item in enumerate(sampled, start=1):
            task_id = f"hbas-{args.seed}-{index:03d}"
            questions.append({
                "task_id": task_id,
                "instruction": INSTRUCTION,
                "passage": item["text"],
            })
            key.append({
                "task_id": task_id,
                "weak_label": item["weak_label"],
                "source_candidate_id": item["candidate_id"],
                "family_id": item.get("family_id"),
            })
        questions_path.write_text(
            "\n".join(json.dumps(q, ensure_ascii=False) for q in questions) + "\n", encoding="utf-8"
        )
        key_path.write_text(
            "\n".join(json.dumps(k, ensure_ascii=False) for k in key) + "\n", encoding="utf-8"
        )
        label_counts: dict[str, int] = {}
        for k in key:
            label_counts[k["weak_label"]] = label_counts.get(k["weak_label"], 0) + 1
        manifest = {
            "schema_version": "1.0",
            "generation": "val2b-human-blind-appraisal-spotcheck",
            "frozen_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "n": len(questions),
            "seed": args.seed,
            "source": str(args.candidates),
            "development_split_size": len(dev),
            "label_counts": label_counts,
            "questions_sha256": sha256_file(questions_path),
            "answer_key_sha256": sha256_file(key_path),
            "answer_key_is_sealed": True,
            "claim_policy": (
                "Weak labels are deterministic-rule outputs. Human agreement with them "
                "measures rule clarity / annotation quality only; it is NOT scientific "
                "validation of a clinical claim."
            ),
        }
        manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(json.dumps({
            "execution_state": "frozen",
            "out_dir": str(args.out_dir),
            "n": manifest["n"],
            "label_counts": label_counts,
            "questions_sha256": manifest["questions_sha256"],
            "answer_key_sha256": manifest["answer_key_sha256"],
        }, indent=2))
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"execution_state": "failed", "error": str(exc)}, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
