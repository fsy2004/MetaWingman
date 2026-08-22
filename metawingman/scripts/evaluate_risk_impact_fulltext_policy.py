#!/usr/bin/env python3
"""Evaluate matched-budget full-text acquisition policies on frozen screening families."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable

from metawingman.scripts.evaluate_constrained_agent_actions import classification_metrics


def _probabilities(row: dict[str, Any]) -> dict[str, float]:
    probabilities = row.get("action_probabilities")
    if probabilities:
        return {str(key): float(value) for key, value in probabilities.items()}
    log_likelihoods = row.get("action_log_likelihoods")
    if not log_likelihoods:
        raise ValueError("score row requires action probabilities or log likelihoods")
    maximum = max(float(value) for value in log_likelihoods.values())
    weights = {str(key): math.exp(float(value) - maximum) for key, value in log_likelihoods.items()}
    total = sum(weights.values())
    if not math.isfinite(total) or total <= 0:
        raise ValueError("action log likelihoods cannot be normalized")
    return {key: value / total for key, value in weights.items()}


def _entropy(row: dict[str, Any]) -> float:
    return -sum(value * math.log(max(value, 1e-12)) for value in _probabilities(row).values())


def evaluate_policies(abstract_rows: list[dict[str, Any]], full_rows: list[dict[str, Any]], *, budget_fraction: float, false_exclusion_harm: float) -> dict[str, Any]:
    if not 0 < budget_fraction <= 1:
        raise ValueError("budget fraction must be in (0, 1]")
    if false_exclusion_harm <= 1:
        raise ValueError("false exclusion harm must exceed one")
    abstract_by_id = {row["example_id"]: row for row in abstract_rows}
    full_by_id = {row["example_id"]: row for row in full_rows}
    if set(abstract_by_id) != set(full_by_id):
        raise ValueError("abstract and full-text scores must contain the same examples")
    for example_id in abstract_by_id:
        left, right = abstract_by_id[example_id], full_by_id[example_id]
        if (left["family_id"], left["true"]) != (right["family_id"], right["true"]):
            raise ValueError("abstract and full-text score identity mismatch")

    families: dict[str, list[str]] = defaultdict(list)
    for row in abstract_rows:
        families[row["family_id"]].append(row["example_id"])
    budgets = {family: max(1, math.ceil(len(ids) * budget_fraction)) for family, ids in families.items()}

    scorers: dict[str, Callable[[dict[str, Any]], float]] = {
        "fixed_hash": lambda row: -int(hashlib.sha256(row["example_id"].encode()).hexdigest(), 16),
        "uncertainty_only": _entropy,
        "impact_only": lambda row: _probabilities(row)["include"],
        "minus_claim_impact": lambda row: _entropy(row) * (false_exclusion_harm if row["predicted"] == "exclude" else 1.0),
        "risk_impact_asymmetric": lambda row: _entropy(row) * _probabilities(row)["include"] * (false_exclusion_harm if row["predicted"] == "exclude" else 1.0),
    }
    arms = {}
    for arm, score_fn in scorers.items():
        predictions = {example_id: row["predicted"] for example_id, row in abstract_by_id.items()}
        trace = []
        for family in sorted(families):
            remaining = set(families[family])
            for iteration in range(1, budgets[family] + 1):
                ranked = sorted(remaining, key=lambda example_id: (score_fn(abstract_by_id[example_id]), example_id), reverse=True)
                selected = ranked[0]; prior = predictions[selected]; predictions[selected] = full_by_id[selected]["predicted"]; remaining.remove(selected)
                trace.append({"family_id": family, "iteration": iteration, "example_id": selected, "policy_score": score_fn(abstract_by_id[selected]), "prior_prediction": prior, "post_fulltext_prediction": predictions[selected], "risk_state_recomputed": True})
        scored = [{"example_id": example_id, "family_id": row["family_id"], "true": row["true"], "predicted": predictions[example_id], "confidence": row.get("confidence", 0.0)} for example_id, row in abstract_by_id.items()]
        metrics = classification_metrics(scored, ["exclude", "include"])
        metrics["false_exclusion_rate"] = 1.0 - metrics["include_recall"]
        arms[arm] = {"fulltext_actions": len(trace), "action_trace": trace, "metrics": metrics}

    abstract_metrics = classification_metrics([{"family_id": row["family_id"], "true": row["true"], "predicted": row["predicted"], "confidence": row.get("confidence", 0.0)} for row in abstract_rows], ["exclude", "include"])
    full_metrics = classification_metrics([{"family_id": row["family_id"], "true": row["true"], "predicted": row["predicted"], "confidence": row.get("confidence", 0.0)} for row in full_rows], ["exclude", "include"])
    return {"schema_version": "1.0", "status": "complete", "mechanism_scope": "selection_stage_fulltext_action_execute_replan_proxy", "budget_fraction": budget_fraction, "false_exclusion_harm": false_exclusion_harm, "matched_fulltext_actions_per_family": budgets, "abstract_only": abstract_metrics, "all_fulltext_upper_bound": full_metrics, "arms": arms}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--abstract-receipt", type=Path, required=True)
    parser.add_argument("--fulltext-receipt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--budget-fraction", type=float, default=0.25)
    parser.add_argument("--false-exclusion-harm", type=float, default=4.0)
    args = parser.parse_args()
    abstract = json.loads(args.abstract_receipt.read_text(encoding="utf-8")); full = json.loads(args.fulltext_receipt.read_text(encoding="utf-8"))
    result = evaluate_policies(abstract["student"]["rows"], full["student"]["rows"], budget_fraction=args.budget_fraction, false_exclusion_harm=args.false_exclusion_harm)
    result.update({"abstract_receipt_sha256": hashlib.sha256(args.abstract_receipt.read_bytes()).hexdigest(), "fulltext_receipt_sha256": hashlib.sha256(args.fulltext_receipt.read_bytes()).hexdigest()})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({**result, "output": str(args.output), "output_sha256": hashlib.sha256(args.output.read_bytes()).hexdigest()}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
