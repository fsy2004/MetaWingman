#!/usr/bin/env python3
"""Run the preregistered AI-only component pilot (C0-C3) against a hosted model.

Design: docs/architecture/ai-only-pilot-preregistration.md. Tasks are sampled
deterministically; candidates are schema-gated by run_structured_batch; scoring
compares against the sealed weak-label key (dev examples and frozen pairs).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from collections import defaultdict
from pathlib import Path

from metawingman_core.provider_factory import build_provider, load_provider_config
from metawingman_core.schema_guard import validate_jsonl_file
from metawingman_core.state_store import atomic_write_json, canonical_json
from metawingman_core.structured_batch import run_structured_batch
from metawingman_core.training_corpus import _retrieval_query

ROLE_DEFINITIONS = (
    "search = strategy for finding studies; "
    "eligibility = inclusion and exclusion criteria; "
    "selection = study selection process; "
    "extraction = data extraction; "
    "appraisal = risk of bias or quality assessment; "
    "synthesis = statistical or narrative pooling of results; "
    "certainty = GRADE or certainty assessment; "
    "protocol = planned methods."
)

CONFIG_PROMPTS = {
    "C0": {
        "section_role": (
            "Predict the systematic-review workflow role of the passage in the "
            "input document. Answer with one of the allowed values only."
        ),
        "retrieval": (
            "Select the passage, by its index, that best supports the query in "
            "the input document. Answer with the index only."
        ),
    },
    "C1": {
        "section_role": (
            "Predict the systematic-review workflow role of the passage in the "
            "input document using these role definitions: " + ROLE_DEFINITIONS
        ),
        "retrieval": (
            "Select the passage, by its index, that best supports the query in "
            "the input document. Passage roles: " + ROLE_DEFINITIONS
        ),
    },
    "C2": {
        "section_role": (
            "Predict the systematic-review workflow role of the passage in the "
            "input document using these role definitions: " + ROLE_DEFINITIONS +
            " Consider the review's declared biomedical context in the input document."
        ),
        "retrieval": (
            "Select the passage, by its index, that best supports the query in "
            "the input document. Passage roles: " + ROLE_DEFINITIONS +
            " Consider the review's declared biomedical context in the input document."
        ),
    },
    "C3": {
        "section_role": (
            "Predict the systematic-review workflow role of the passage in the "
            "input document using these role definitions: " + ROLE_DEFINITIONS +
            " A trained domain verifier predicted the role recorded in the input "
            "document; verify or correct it and return your final answer."
        ),
        "retrieval": (
            "Select the passage, by its index, that best supports the query in "
            "the input document. A trained retrieval verifier ranked the "
            "candidates as recorded in the input document; verify or correct it "
            "and return your final index."
        ),
    },
}


def _stable_sample(items: list[dict], size: int, seed: int, key: str) -> list[dict]:
    ordered = sorted(
        items, key=lambda item: hashlib.sha256(f"{seed}:{item[key]}".encode()).hexdigest()
    )
    return ordered[:size]


def build_pilot_tasks(
    examples: list[dict],
    pairs: list[dict],
    config: str,
    *,
    sample_size: int = 200,
    seed: int = 20260817,
    strata_by_record: dict | None = None,
    verifier_predictions: dict | None = None,
) -> list[dict]:
    if config not in CONFIG_PROMPTS:
        raise ValueError(f"unknown configuration: {config}")
    strata_by_record = strata_by_record or {}
    verifier_predictions = verifier_predictions or {}
    prompts = CONFIG_PROMPTS[config]
    tasks: list[dict] = []
    section_role = [
        item for item in examples
        if item["task"] == "section_role_classification" and item["split"] == "development"
    ]
    for item in _stable_sample(section_role, sample_size, seed, "example_id"):
        input_document: dict = {"passage": item["input_text"]}
        if config in {"C2", "C3"}:
            input_document["biomedical_context"] = strata_by_record.get(item["record_id"], {})
        if config == "C3":
            input_document["verifier_prediction"] = verifier_predictions.get(item["example_id"], {})
        tasks.append({
            "schema_version": "1.0",
            "task_id": f"sr-{config}-{item['example_id'].split(':', 1)[-1]}",
            "instruction": prompts["section_role"],
            "input_document": input_document,
            "output_schema": "section_role_prediction",
            "max_tokens": 64,
            "thinking": False,
        })
    retrieval = [
        item for item in examples
        if item["task"] == "evidence_retrieval" and item["split"] == "development"
    ]
    positives_by_query = {
        pair["query_example_id"]: pair for pair in pairs if pair["query_split"] == "development" and pair["label"] == 1
    }
    negatives_by_query: dict[str, list[dict]] = defaultdict(list)
    for pair in pairs:
        if pair["query_split"] == "development" and pair["label"] == 0:
            negatives_by_query[pair["query_example_id"]].append(pair)
    example_by_id = {item["example_id"]: item for item in retrieval}
    for item in _stable_sample(retrieval, sample_size, seed, "example_id"):
        query_id = item["example_id"]
        positive = positives_by_query.get(query_id)
        if positive is None:
            continue
        candidates = [positive] + sorted(negatives_by_query.get(query_id, []), key=lambda pair: pair["pair_id"])[:3]
        order = _stable_sample(candidates, len(candidates), seed, "pair_id")
        input_document: dict = {
            "query": positive["query_text"],
            "candidates": [
                {"index": position, "text": pair["document_text"]}
                for position, pair in enumerate(order)
            ],
        }
        if config in {"C2", "C3"}:
            input_document["biomedical_context"] = strata_by_record.get(item["record_id"], {})
        if config == "C3":
            input_document["verifier_ranking"] = verifier_predictions.get(query_id, {})
        tasks.append({
            "schema_version": "1.0",
            "task_id": f"rt-{config}-{query_id.split(':', 1)[-1]}",
            "instruction": prompts["retrieval"],
            "input_document": input_document,
            "output_schema": "retrieval_selection_prediction",
            "max_tokens": 64,
            "thinking": False,
        })
    return tasks


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


def score_pilot_tasks(runs: list[dict], examples: list[dict], pairs: list[dict]) -> dict:
    section_role = [
        item for item in examples
        if item["task"] == "section_role_classification" and item["split"] == "development"
    ]
    section_role_by_id = {item["example_id"]: item for item in section_role}
    sr_predicted: list[str] = []
    sr_gold: list[str] = []
    sr_abstained = 0
    for run in runs:
        if not run["task_id"].startswith("sr-"):
            continue
        example_id = "example:" + run["task_id"].rsplit("-", 1)[-1]
        item = section_role_by_id.get(example_id)
        if item is None:
            continue
        if run["status"] == "abstain":
            sr_abstained += 1
            continue
        sr_predicted.append(run["candidate"]["section_role"])
        sr_gold.append(item["target"]["section_role"])
    positives_by_query = {
        pair["query_example_id"]: pair for pair in pairs if pair["query_split"] == "development" and pair["label"] == 1
    }
    negatives_by_query: dict[str, list[dict]] = defaultdict(list)
    for pair in pairs:
        if pair["query_split"] == "development" and pair["label"] == 0:
            negatives_by_query[pair["query_example_id"]].append(pair)
    mrr_sum = 0.0
    p1 = 0
    rt_scored = 0
    rt_abstained = 0
    for run in runs:
        if not run["task_id"].startswith("rt-"):
            continue
        query_id = "example:" + run["task_id"].rsplit("-", 1)[-1]
        if query_id not in positives_by_query:
            continue
        if run["status"] == "abstain":
            rt_abstained += 1
            continue
        candidates = [positives_by_query[query_id]] + sorted(
            negatives_by_query.get(query_id, []), key=lambda pair: pair["pair_id"]
        )[:3]
        order = sorted(
            candidates, key=lambda pair: hashlib.sha256(f"20260817:{pair['pair_id']}".encode()).hexdigest()
        )
        selected = run["candidate"]["selected_index"]
        if not 0 <= selected < len(order):
            rt_abstained += 1
            continue
        chosen = order[selected]
        if chosen["label"] == 1:
            rank = selected + 1
            mrr_sum += 1.0 / rank
            p1 += 1 if rank == 1 else 0
        rt_scored += 1
    total_calls = sum(run["attempts"] for run in runs)
    total_tokens = sum(run["usage_totals"]["total_tokens"] or 0 for run in runs)
    return {
        "section_role": {
            "scored": len(sr_gold),
            "abstained": sr_abstained,
            "macro_f1": round(_macro_f1(sr_predicted, sr_gold), 6) if sr_gold else None,
        },
        "retrieval": {
            "scored": rt_scored,
            "abstained": rt_abstained,
            "mrr": round(mrr_sum / max(1, rt_scored), 6),
            "precision_at_1": round(p1 / max(1, rt_scored), 6),
        },
        "cost": {"provider_calls": total_calls, "total_tokens": total_tokens},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("examples", type=Path)
    parser.add_argument("pairs", type=Path)
    parser.add_argument("plan", type=Path)
    parser.add_argument("--config", choices=tuple(CONFIG_PROMPTS), required=True)
    parser.add_argument("--provider-config", type=Path, required=True)
    parser.add_argument("--key-file", type=Path)
    parser.add_argument("--verifier-predictions", type=Path)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--sample-size", type=int, default=200)
    parser.add_argument("--seed", type=int, default=20260817)
    args = parser.parse_args()
    try:
        examples = validate_jsonl_file(args.examples, "training_example")
        pairs = validate_jsonl_file(args.pairs, "training_pair")
        plan = json.loads(args.plan.read_text(encoding="utf-8"))
        strata_by_record = {
            record["record_id"]: record.get("biomedical_stratum") or {}
            for record in plan["records"]
        }
        verifier_predictions = {}
        if args.verifier_predictions:
            verifier_predictions = json.loads(args.verifier_predictions.read_text(encoding="utf-8"))
        if args.key_file:
            os.environ["DEEPSEEK_API_KEY"] = args.key_file.read_text(encoding="utf-8").strip()
        tasks = build_pilot_tasks(
            examples, pairs, args.config,
            sample_size=args.sample_size, seed=args.seed,
            strata_by_record=strata_by_record, verifier_predictions=verifier_predictions,
        )
        config = load_provider_config(args.provider_config)
        provider = build_provider(config)
        args.out_dir.mkdir(parents=True, exist_ok=True)
        runs_path = args.out_dir / f"runs-{args.config}.jsonl"
        summary = run_structured_batch(
            tasks,
            provider=provider,
            output_path=runs_path,
            maximum_provider_calls=2 * len(tasks) + 2,
            maximum_reserved_output_tokens=2 * len(tasks) * 64,
        )
        runs = validate_jsonl_file(runs_path, "external_agent_candidate_run")
        scoring = score_pilot_tasks(runs, examples, pairs)
        report = {
            "schema_version": "1.0",
            "configuration": args.config,
            "sample_size": args.sample_size,
            "seed": args.seed,
            "tasks_built": len(tasks),
            "batch_summary": summary,
            "scoring": scoring,
            "config_prompt_sha256": {
                key: hashlib.sha256(value.encode("utf-8")).hexdigest()
                for key, value in CONFIG_PROMPTS[args.config].items()
            },
        }
        atomic_write_json(args.out_dir / f"report-{args.config}.json", report)
        print(json.dumps(report, indent=2, ensure_ascii=False))
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
