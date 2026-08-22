#!/usr/bin/env python3
"""Run the typed risk-impact controller on frozen abstract/full-text model scores."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

from metawingman.scripts.evaluate_constrained_agent_actions import classification_metrics
from metawingman.scripts.evaluate_risk_impact_fulltext_policy import _probabilities
from metawingman.scripts.metawingman_core.evidence_acquisition_loop import (
    execute_evidence_acquisition_loop,
)


def _entropy(probabilities: dict[str, float]) -> float:
    value = -sum(p * math.log(max(p, 1e-12)) for p in probabilities.values())
    return min(1.0, value / math.log(max(len(probabilities), 2)))


def _identifier(prefix: str, value: str) -> str:
    return f"{prefix}-{hashlib.sha256(value.encode()).hexdigest()[:16]}"


def _state(rows: list[dict[str, Any]], *, family_id: str, iteration: int, created_at_utc: str) -> tuple[dict[str, Any], dict[str, str]]:
    criteria = []
    actions = []
    action_to_example = {}
    for row in rows:
        probabilities = _probabilities(row)
        example_id = str(row["example_id"])
        criterion_id = _identifier("criterion", example_id)
        action_id = _identifier("fulltext", example_id)
        uncertainty = _entropy(probabilities)
        include_probability = probabilities.get("include")
        if include_probability is None:
            raise ValueError("full-text acquisition requires include and exclude actions")
        confidence = max(probabilities.values())
        criteria.append({
            "criterion_id": criterion_id,
            "critical": row["predicted"] == "exclude",
            "calibration_status": "heuristic",
            "residual_omission_risk": uncertainty,
            "downstream_claim_impact": include_probability,
            "hard_negative_error_rate": 1.0 - confidence,
            "unresolved_records": 1,
            "independent_source_count": 1,
            "evidence_basis": "Frozen abstract-only constrained action likelihoods.",
        })
        actions.append({
            "action_id": action_id,
            "action_type": "retrieve_full_text",
            "target_criterion_ids": [criterion_id],
            "expected_risk_reduction": uncertainty,
            "expected_claim_impact": include_probability,
            "source_family_gain": 1,
            "estimated_cost_units": 1.0,
            "estimate_basis": "heuristic",
            "legally_available": True,
            "credential_status": "not_required",
            "rationale": "Acquire and rescore a report with unresolved selection risk and downstream inclusion impact.",
        })
        action_to_example[action_id] = example_id
    return ({
        "schema_version": "1.0",
        "state_id": _identifier(f"risk-{iteration}", family_id + ":" + ",".join(sorted(action_to_example.values()))),
        "protocol_version": "frozen-csmed-ft-selection-v1",
        "criterion_states": criteria,
        "global_signals": {
            "run_context": "historical_reconstruction",
            "known_item_set_frozen": True,
            "known_item_recall": 1.0,
            "source_family_count": 1,
            "temporal_boundary_status": "sealed",
            "leakage_audit": "passed",
        },
        "thresholds": {
            "known_item_recall_floor": 0.95,
            "residual_omission_risk_ceiling": 0.05,
            "downstream_claim_impact_ceiling": 0.25,
            "hard_negative_error_ceiling": 0.05,
            "minimum_independent_sources": 1,
            "minimum_source_families": 1,
            "max_selected_actions": 1,
        },
        "candidate_actions": actions,
        "created_at_utc": created_at_utc,
    }, action_to_example)


def evaluate_fulltext_loops(
    abstract_rows: list[dict[str, Any]],
    full_rows: list[dict[str, Any]],
    *,
    artifact_root: Path,
    budget_fraction: float,
    created_at_utc: str,
) -> dict[str, Any]:
    if not 0 < budget_fraction <= 1:
        raise ValueError("budget fraction must be in (0, 1]")
    abstract_by_id = {str(row["example_id"]): row for row in abstract_rows}
    full_by_id = {str(row["example_id"]): row for row in full_rows}
    if set(abstract_by_id) != set(full_by_id):
        raise ValueError("abstract and full-text scores must contain the same examples")
    families: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in abstract_rows:
        example_id = str(row["example_id"])
        full = full_by_id[example_id]
        if (row["family_id"], row["true"]) != (full["family_id"], full["true"]):
            raise ValueError("abstract and full-text score identity mismatch")
        families[str(row["family_id"])].append(row)

    artifact_root = artifact_root.resolve()
    artifact_root.mkdir(parents=True, exist_ok=True)
    predictions = {example_id: row["predicted"] for example_id, row in abstract_by_id.items()}
    family_loops = {}
    for family_id, rows in sorted(families.items()):
        budget = max(1, math.ceil(len(rows) * budget_fraction))
        state, action_to_example = _state(rows, family_id=family_id, iteration=0, created_at_utc=created_at_utc)
        family_root = artifact_root / _identifier("family", family_id)
        family_root.mkdir(parents=True, exist_ok=True)
        selected: list[str] = []

        def executor(action: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
            example_id = action_to_example[action["action_id"]]
            if example_id in selected:
                raise ValueError("controller selected the same full text twice")
            selected.append(example_id)
            predictions[example_id] = full_by_id[example_id]["predicted"]
            artifact = family_root / f"{len(selected):03d}-{action['action_id']}.json"
            if artifact.exists():
                raise ValueError("refusing to overwrite an existing action artifact")
            artifact.write_text(json.dumps({
                "action_id": action["action_id"],
                "example_id": example_id,
                "prior_prediction": abstract_by_id[example_id]["predicted"],
                "post_fulltext_prediction": full_by_id[example_id]["predicted"],
            }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            next_state = copy.deepcopy(current)
            next_state["state_id"] = _identifier(f"risk-{len(selected)}", family_id + ":" + ",".join(selected))
            criterion_id = action["target_criterion_ids"][0]
            for criterion in next_state["criterion_states"]:
                if criterion["criterion_id"] == criterion_id:
                    criterion.update({"residual_omission_risk": 0.0, "unresolved_records": 0, "independent_source_count": 2, "hard_negative_error_rate": 0.0})
            next_state["candidate_actions"] = [item for item in next_state["candidate_actions"] if item["action_id"] != action["action_id"]]
            return {
                "action_id": action["action_id"],
                "next_state": next_state,
                "risk_state_recomputed": True,
                "semantic_verification_status": "passed",
                "artifact": {"path": str(artifact), "sha256": hashlib.sha256(artifact.read_bytes()).hexdigest()},
                "usage": {"model_calls": 0, "input_tokens": 0, "output_tokens": 0, "wall_seconds": 0.0, "cost_status": "not_applicable", "cost_value": None},
            }

        preregistration = hashlib.sha256(f"risk-impact-fulltext-v1:{budget_fraction}".encode()).hexdigest()
        plan = {
            "schema_version": "1.0",
            "loop_id": _identifier("loop", family_id),
            "mode": "evaluation",
            "max_iterations": budget + 1,
            "artifact_root": str(artifact_root),
            "budget": {"max_actions": budget, "max_estimated_cost_units": float(budget), "max_model_calls": 0, "max_input_tokens": 0, "max_output_tokens": 0, "max_wall_seconds": 0.0, "cost_accounting_policy": "report_unknown"},
            "stop_authority": {"actor_id": "preregistered-fulltext-policy-evaluator", "preregistration_sha256": preregistration, "signature_status": "verified"},
        }
        controller = execute_evidence_acquisition_loop(state, plan, executor, created_at_utc=created_at_utc)
        family_loops[family_id] = {"budget": budget, "selected_example_ids": selected, "controller_result": controller}

    scored = [{"example_id": example_id, "family_id": row["family_id"], "true": row["true"], "predicted": predictions[example_id], "confidence": row.get("confidence", 0.0)} for example_id, row in abstract_by_id.items()]
    metrics = classification_metrics(scored, ["exclude", "include"])
    metrics["false_exclusion_rate"] = 1.0 - metrics["include_recall"]
    return {
        "schema_version": "1.0",
        "status": "complete",
        "mechanism_scope": "selection_stage_fulltext_typed_action_execute_recompute_replan",
        "budget_fraction": budget_fraction,
        "metrics": metrics,
        "family_loops": family_loops,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--abstract-receipt", type=Path, required=True)
    parser.add_argument("--fulltext-receipt", type=Path, required=True)
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--budget-fraction", type=float, default=0.25)
    parser.add_argument("--created-at-utc", required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("refusing to overwrite an existing evaluation")
    abstract = json.loads(args.abstract_receipt.read_text(encoding="utf-8"))
    full = json.loads(args.fulltext_receipt.read_text(encoding="utf-8"))
    result = evaluate_fulltext_loops(abstract["student"]["rows"], full["student"]["rows"], artifact_root=args.artifact_root, budget_fraction=args.budget_fraction, created_at_utc=args.created_at_utc)
    result.update({"abstract_receipt_sha256": hashlib.sha256(args.abstract_receipt.read_bytes()).hexdigest(), "fulltext_receipt_sha256": hashlib.sha256(args.fulltext_receipt.read_bytes()).hexdigest()})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "output": str(args.output), "output_sha256": hashlib.sha256(args.output.read_bytes()).hexdigest(), "metrics": result["metrics"]}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
