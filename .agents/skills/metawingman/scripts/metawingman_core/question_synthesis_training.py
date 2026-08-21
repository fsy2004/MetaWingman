"""Build family/time-safe training examples for bounded question-synthesis components."""

from __future__ import annotations

from typing import Any

from .question_synthesis_evaluator import QuestionSynthesisBenchmarkError, validate_family_isolation
from .schema_guard import validate_document
from .state_store import sha256_json
from .training_corpus import TrainingCorpusError


COMPONENT_TASKS = {
    "question_method_ranker": "pairwise_preference",
    "source_support_verifier": "binary_with_abstention",
    "risk_cost_router": "bounded_loss_policy",
}


def _split(value: str) -> str:
    return "train" if value == "development" else value


def _example(
    case: dict[str, Any],
    component: str,
    suffix: str,
    label: int,
    decision: str,
    input_document: dict[str, Any],
    *,
    violated_rule: str | None,
    created_at_utc: str,
) -> dict[str, Any]:
    row = {
        "schema_version": "1.0",
        "example_id": f"{case['case_id']}-{component}-{suffix}",
        "component_type": component,
        "task": COMPONENT_TASKS[component],
        "split": _split(case["split"]),
        "family_id": case["review_family_id"],
        "input": input_document,
        "target": {"label": label, "decision": decision},
        "label_authority": "published_reference",
        "violated_rule": violated_rule,
        "source_anchor_ids": [item["material_id"] for item in case["visible_material"]],
        "created_at_utc": created_at_utc,
    }
    validate_document(row, "question_synthesis_training_example")
    return row


def export_question_synthesis_examples(
    cases: list[dict[str, Any]],
    trajectories: list[dict[str, Any]],
    *,
    created_at_utc: str,
) -> dict[str, Any]:
    try:
        validate_family_isolation(cases)
    except QuestionSynthesisBenchmarkError as exc:
        raise TrainingCorpusError(str(exc)) from exc
    examples: list[dict[str, Any]] = []
    for case in sorted(cases, key=lambda item: item["case_id"]):
        reference = case["published_reference"]
        visible = {"case_id": case["case_id"], "visible_material": case["visible_material"]}
        examples.extend(
            [
                _example(case, "question_method_ranker", "positive", 1, reference["synthesis_route"], {**visible, "candidate_review_family": reference["review_family"], "candidate_route": reference["synthesis_route"]}, violated_rule=None, created_at_utc=created_at_utc),
                _example(case, "question_method_ranker", "wrong-route", 0, "reject", {**visible, "candidate_review_family": reference["review_family"], "candidate_route": "incompatible_route"}, violated_rule="incompatible_effect_measure", created_at_utc=created_at_utc),
                _example(case, "source_support_verifier", "supported", 1, "supported", {**visible, "assertion": "source-anchored candidate", "anchor_present": True}, violated_rule=None, created_at_utc=created_at_utc),
                _example(case, "source_support_verifier", "unsupported", 0, "abstain", {**visible, "assertion": "unanchored candidate", "anchor_present": False}, violated_rule="unsupported_source_span", created_at_utc=created_at_utc),
                _example(case, "risk_cost_router", "bounded", 1, "bounded_budget", {**visible, "risk": "high", "uncertainty": "moderate", "cost": "bounded"}, violated_rule=None, created_at_utc=created_at_utc),
                _example(case, "risk_cost_router", "unbounded", 0, "reject", {**visible, "risk": "high", "uncertainty": "moderate", "cost": "unbounded"}, violated_rule="unbounded_action_budget", created_at_utc=created_at_utc),
            ]
        )
    allowed_rules = {
        "wrong_review_family", "incompatible_effect_measure", "unidentifiable_estimand",
        "disconnected_network", "threshold_time_mismatch", "duplicate_topic",
        "unsupported_source_span", "report_study_result_lineage_break",
    }
    for trajectory in trajectories:
        rule = trajectory.get("violated_rule")
        if rule not in allowed_rules:
            continue
        case_id = trajectory.get("case_id")
        case = next((item for item in cases if item["case_id"] == case_id), None)
        if case is None:
            raise TrainingCorpusError("trajectory references unknown case")
        component = str(trajectory.get("component_type") or "source_support_verifier")
        if component not in COMPONENT_TASKS:
            raise TrainingCorpusError("trajectory references unknown component")
        examples.append(_example(case, component, f"trajectory-{len(examples)}", 0, "reject", dict(trajectory.get("input") or {}), violated_rule=rule, created_at_utc=created_at_utc))
    return {
        "schema_version": "1.0",
        "created_at_utc": created_at_utc,
        "label_policy": "published_reference_not_gold",
        "family_isolation": True,
        "examples": examples,
        "examples_sha256": sha256_json(examples),
    }
