#!/usr/bin/env python3
"""Score the R2-AI C3 run against the sealed weak-label key (local, post-run).

Reads the manifests + run records produced by run_r2_ai_validation.py and the
sealed weak-label-key.json, and computes the pilot-protocol metrics:
  * section-role: passage-level macro-F1 + per-class F1, per-passage pass/fail,
    per-record agreement, abstention. Also the 12k verifier's own agreement.
  * retrieval: candidate-set MRR / P@1 for the hosted C3 selection and for the
    12k verifier's own best_index, plus abstention.

Agreement is against deterministic weak labels, NOT human gold or truth.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def _load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _macro_f1(predicted: list[str], gold: list[str]) -> float:
    classes = sorted(set(gold))
    per_class = {}
    for label in classes:
        tp = sum(1 for p, g in zip(predicted, gold) if p == g == label)
        fp = sum(1 for p, g in zip(predicted, gold) if p == label and g != label)
        fn = sum(1 for p, g in zip(predicted, gold) if p != label and g == label)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        per_class[label] = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return sum(per_class.values()) / len(classes) if classes else 0.0


def _per_class_f1(predicted: list[str], gold: list[str]) -> dict[str, float]:
    classes = sorted(set(gold) | set(predicted))
    out = {}
    for label in classes:
        tp = sum(1 for p, g in zip(predicted, gold) if p == g == label)
        fp = sum(1 for p, g in zip(predicted, gold) if p == label and g != label)
        fn = sum(1 for p, g in zip(predicted, gold) if p != label and g == label)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        out[label] = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return out


def _runs_by_task(runs: list[dict]) -> dict[str, dict]:
    return {run["task_id"]: run for run in runs}


def score_section_role(manifest: list[dict], key_rows: list[dict], runs: list[dict]) -> dict:
    roles_by_record = {
        row["record_id"]: row["weak_labels"]["section_roles"] for row in key_rows
    }
    runs_by_task = _runs_by_task(runs)
    hosted_pred: list[str] = []
    verifier_pred: list[str] = []
    gold: list[str] = []
    abstained = 0
    per_passage: list[dict] = []
    for row in manifest:
        gold_role = roles_by_record.get(row["record_id"], {}).get(row["section_path"])
        if gold_role is None:
            continue
        run = runs_by_task.get(row["task_id"])
        gold.append(gold_role)
        verifier_pred.append(row["verifier_role"])
        if run is None or run["status"] == "abstain":
            hosted_pred.append("<abstain>")
            abstained += 1
            per_passage.append({
                "task_id": row["task_id"], "record_id": row["record_id"],
                "section_path": row["section_path"], "gold": gold_role,
                "hosted": None, "verifier": row["verifier_role"],
                "pass": False, "status": "abstain" if run is None else run["status"],
            })
            continue
        hosted_role = run["candidate"]["section_role"]
        hosted_pred.append(hosted_role)
        per_passage.append({
            "task_id": row["task_id"], "record_id": row["record_id"],
            "section_path": row["section_path"], "gold": gold_role,
            "hosted": hosted_role, "verifier": row["verifier_role"],
            "pass": hosted_role == gold_role, "status": run["status"],
        })
    # scored-only predictions (exclude abstain) for macro-F1.
    scored_idx = [i for i, p in enumerate(hosted_pred) if p != "<abstain>"]
    hosted_scored = [hosted_pred[i] for i in scored_idx]
    gold_scored = [gold[i] for i in scored_idx]
    verifier_scored = [verifier_pred[i] for i in scored_idx]

    # per-record agreement (record passes iff every scored passage passes; abstain counts as fail).
    record_pass: dict[str, bool] = {}
    for row in per_passage:
        record_pass.setdefault(row["record_id"], True)
        if not row["pass"]:
            record_pass[row["record_id"]] = False
    records_correct = sum(1 for value in record_pass.values() if value)

    return {
        "scored": len(gold),
        "hosted_scored": len(hosted_scored),
        "abstained": abstained,
        "hosted_macro_f1": round(_macro_f1(hosted_scored, gold_scored), 6) if hosted_scored else None,
        "verifier_macro_f1": round(_macro_f1(verifier_scored, gold_scored), 6) if verifier_scored else None,
        "hosted_per_class_f1": {k: round(v, 6) for k, v in _per_class_f1(hosted_scored, gold_scored).items()},
        "verifier_per_class_f1": {k: round(v, 6) for k, v in _per_class_f1(verifier_scored, gold_scored).items()},
        "per_passage_pass": sum(1 for row in per_passage if row["pass"]),
        "per_passage_total": len(per_passage),
        "records_correct": records_correct,
        "records_total": len(record_pass),
        "per_passage": per_passage,
    }


def score_retrieval(manifest: list[dict], runs: list[dict]) -> dict:
    """Score retrieval.

    Hosted: the pilot's exact single-selection metric (score_pilot_tasks), where
    "rank" is the selected index's 1-based position in the shuffled candidate
    order. Selection accuracy (selected == gold index) is also reported.

    Verifier: standard candidate-set MRR/P@1, i.e. sort the candidates by the
    verifier's cosine score and take the positive's reciprocal rank (the same
    definition as the training report's hard-negative MRR/P@1).
    """
    runs_by_task = _runs_by_task(runs)
    hosted_mrr_sum = 0.0
    hosted_p1 = 0
    hosted_accuracy = 0
    verifier_mrr_sum = 0.0
    verifier_p1 = 0
    verifier_accuracy = 0
    scored = 0
    abstained = 0
    per_query: list[dict] = []
    for row in manifest:
        candidates = row["candidates"]
        scores = row["verifier_scores"]
        gold_index = next(i for i, cand in enumerate(candidates) if cand["label"] == 1)
        run = runs_by_task.get(row["task_id"])
        if run is None or run["status"] == "abstain":
            abstained += 1
            per_query.append({
                "task_id": row["task_id"], "query_example_id": row["query_example_id"],
                "gold_index": gold_index, "hosted_index": None,
                "verifier_index": row["verifier_best_index"], "hosted_pass": False,
            })
            continue
        selected = run["candidate"]["selected_index"]
        if not 0 <= selected < len(candidates):
            abstained += 1
            per_query.append({
                "task_id": row["task_id"], "query_example_id": row["query_example_id"],
                "gold_index": gold_index, "hosted_index": selected,
                "verifier_index": row["verifier_best_index"], "hosted_pass": False,
            })
            continue
        scored += 1
        # hosted: pilot-consistent single-selection metric.
        if candidates[selected]["label"] == 1:
            rank = selected + 1
            hosted_mrr_sum += 1.0 / rank
            hosted_p1 += 1 if rank == 1 else 0
            hosted_pass = True
        else:
            hosted_pass = False
        hosted_accuracy += 1 if selected == gold_index else 0
        # verifier: standard candidate-set MRR/P@1 by sorting scores descending.
        order = sorted(range(len(candidates)), key=lambda i: scores[i], reverse=True)
        vrank = next(position + 1 for position, idx in enumerate(order) if candidates[idx]["label"] == 1)
        verifier_mrr_sum += 1.0 / vrank
        verifier_p1 += 1 if vrank == 1 else 0
        verifier_accuracy += 1 if row["verifier_best_index"] == gold_index else 0
        per_query.append({
            "task_id": row["task_id"], "query_example_id": row["query_example_id"],
            "gold_index": gold_index, "hosted_index": selected,
            "verifier_index": row["verifier_best_index"], "hosted_pass": hosted_pass,
        })
    return {
        "scored": scored,
        "abstained": abstained,
        "hosted_mrr": round(hosted_mrr_sum / max(1, scored), 6),
        "hosted_precision_at_1": round(hosted_p1 / max(1, scored), 6),
        "hosted_selection_accuracy": round(hosted_accuracy / max(1, scored), 6),
        "verifier_mrr": round(verifier_mrr_sum / max(1, scored), 6),
        "verifier_precision_at_1": round(verifier_p1 / max(1, scored), 6),
        "verifier_selection_accuracy": round(verifier_accuracy / max(1, scored), 6),
        "per_query": per_query,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs-dir", type=Path, required=True)
    parser.add_argument("--key", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    key = json.loads(args.key.read_text(encoding="utf-8"))
    results: dict = {"schema_version": "1.0", "sections": {}}
    if (args.runs_dir / "manifest-sr.jsonl").exists():
        manifest = _load_jsonl(args.runs_dir / "manifest-sr.jsonl")
        runs = _load_jsonl(args.runs_dir / "runs-sr.jsonl")
        results["sections"]["section_role"] = score_section_role(manifest, key["rows"], runs)
    if (args.runs_dir / "manifest-rt.jsonl").exists():
        manifest = _load_jsonl(args.runs_dir / "manifest-rt.jsonl")
        runs = _load_jsonl(args.runs_dir / "runs-rt.jsonl")
        results["sections"]["retrieval"] = score_retrieval(manifest, runs)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    print(json.dumps(results, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
