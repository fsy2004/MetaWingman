"""Contracts that prevent topic discovery and fixed-question reconstruction conflation."""

from __future__ import annotations

from typing import Any


TOPIC_ARMS = {
    "bibliometric_count", "semantic_gap", "graph_only", "llm_proposal_order",
    "decision_aware_full", "no_overlap_opposition", "no_decision_relevance",
    "no_portfolio_diversity",
}
FIXED_QUESTION_ARMS = {
    "generic_fixed_acquisition", "conclusion_directed_acquisition",
}


class StagePlanError(ValueError):
    pass


def _exact_keys(value: dict[str, Any], expected: set[str], context: str) -> None:
    extra = set(value) - expected
    missing = expected - set(value)
    if extra or missing:
        if context == "fixed_question_reconstruction" and "topic_opportunity_control" in extra:
            raise StagePlanError("topic mechanism cannot appear in fixed-question reconstruction")
        raise StagePlanError(f"{context} fields mismatch; missing={sorted(missing)}, extra={sorted(extra)}")


def validate_stage_plan(plan: dict[str, Any]) -> dict[str, int]:
    if not isinstance(plan, dict):
        raise StagePlanError("plan must be an object")
    _exact_keys(plan, {
        "schema_version", "plan_id", "frozen_at_utc", "case_registry_sha256",
        "repeats", "topic_rediscovery", "fixed_question_reconstruction",
    }, "plan")
    if plan["schema_version"] != "1.1":
        raise StagePlanError("stage-appropriate plan requires schema_version 1.1")
    repeats = plan["repeats"]
    if not isinstance(repeats, list) or len(repeats) != 3 or len(set(repeats)) != 3:
        raise StagePlanError("exactly three distinct frozen repeats are required")
    digest = plan["case_registry_sha256"]
    if not isinstance(digest, str) or len(digest) != 64:
        raise StagePlanError("case registry SHA-256 binding is required")

    topic = plan["topic_rediscovery"]
    _exact_keys(topic, {
        "input_condition", "target_identity_sealed", "published_answers_sealed",
        "independent_signal_audit_required", "arms",
    }, "topic_rediscovery")
    if topic["input_condition"] != "broad_non_target_historical_landscape":
        raise StagePlanError("topic rediscovery requires a broad non-target historical landscape")
    if not all(topic[field] is True for field in (
        "target_identity_sealed", "published_answers_sealed", "independent_signal_audit_required",
    )):
        raise StagePlanError("topic identity, answers, and independent signal audit gates are mandatory")
    if set(topic["arms"]) != TOPIC_ARMS or len(topic["arms"]) != len(TOPIC_ARMS):
        raise StagePlanError("topic rediscovery requires the exact frozen arms")

    fixed = plan["fixed_question_reconstruction"]
    _exact_keys(fixed, {
        "input_condition", "published_answers_sealed", "arms",
        "protocol_schema_repairs", "synthesis_schema_repairs",
    }, "fixed_question_reconstruction")
    if fixed["input_condition"] != "frozen_question_and_operational_corpus":
        raise StagePlanError("fixed-question reconstruction input condition is invalid")
    if fixed["published_answers_sealed"] is not True:
        raise StagePlanError("published answers must remain sealed")
    if set(fixed["arms"]) != FIXED_QUESTION_ARMS or len(fixed["arms"]) != len(FIXED_QUESTION_ARMS):
        raise StagePlanError("fixed-question reconstruction requires the exact frozen arms")
    if fixed["protocol_schema_repairs"] != 1 or fixed["synthesis_schema_repairs"] != 1:
        raise StagePlanError("protocol and synthesis each permit one bounded schema repair")
    return {
        "topic_slots_per_case": len(TOPIC_ARMS) * len(repeats),
        "fixed_question_slots_per_case": len(FIXED_QUESTION_ARMS) * len(repeats),
    }
