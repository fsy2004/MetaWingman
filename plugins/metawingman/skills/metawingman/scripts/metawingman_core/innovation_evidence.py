"""Semantic audit for MetaWingman's two innovation claims and full lifecycle."""

from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
from typing import Any

from .case_admission import CaseAdmissionError, validate_case_registry


LIFECYCLE_STAGES = (
    "topic_feasibility",
    "protocol_registration",
    "search_retrieval",
    "selection",
    "data_lineage",
    "appraisal",
    "freeze_synthesis",
    "certainty_interpretation",
    "reporting_review",
    "living_update",
)

CLAIM_IDS = (
    "topic_opportunity_control",
    "conclusion_directed_acquisition",
    "joint_lifecycle_control",
    "agent_distillation",
)


class InnovationEvidenceError(ValueError):
    """Raised when the ledger violates a scientific-integrity invariant."""


def _require_unique(values: list[str], label: str) -> None:
    duplicates = sorted(value for value, count in Counter(values).items() if count > 1)
    if duplicates:
        raise InnovationEvidenceError(f"duplicate {label}: {duplicates}")


def _case_index(ledger: dict[str, Any]) -> dict[str, dict[str, Any]]:
    cases = ledger.get("cases")
    if not isinstance(cases, list) or not cases:
        raise InnovationEvidenceError("at least one registered case is required")
    identifiers = [str(case.get("case_id", "")) for case in cases]
    _require_unique(identifiers, "case_id")
    index = {case["case_id"]: case for case in cases}
    family_splits: dict[str, set[str]] = {}
    for case in cases:
        split = case.get("split")
        family = case.get("review_family_id")
        if split not in {"development", "held_out", "prospective", "diagnostic_only"}:
            raise InnovationEvidenceError(f"{case['case_id']}: invalid split")
        family_splits.setdefault(str(family), set()).add(str(split))
        if split in {"held_out", "prospective"} and case.get("training_use") != "forbidden":
            raise InnovationEvidenceError(f"{split.replace('_', '-') } case cannot enter training: {case['case_id']}")
        if split == "diagnostic_only" and case.get("training_use") not in {"forbidden", "audit_only"}:
            raise InnovationEvidenceError(f"diagnostic-only case cannot enter positive training: {case['case_id']}")
    for family, splits in family_splits.items():
        if "development" in splits and ({"held_out", "prospective"} & splits):
            raise InnovationEvidenceError(f"review family crosses development and evaluation splits: {family}")
    return index


def _validate_stages(ledger: dict[str, Any]) -> None:
    stages = ledger.get("lifecycle_stages")
    if not isinstance(stages, list):
        raise InnovationEvidenceError("exact ten-stage lifecycle declaration is required")
    stage_ids = [stage.get("stage_id") for stage in stages if isinstance(stage, dict)]
    if tuple(stage_ids) != LIFECYCLE_STAGES:
        raise InnovationEvidenceError("exact ten-stage lifecycle declaration is required in canonical order")


def _validate_evidence(
    ledger: dict[str, Any], cases: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    items = ledger.get("evidence_items")
    if not isinstance(items, list):
        raise InnovationEvidenceError("evidence_items must be an array")
    _require_unique([str(item.get("evidence_id", "")) for item in items], "evidence_id")
    for item in items:
        unknown_claims = sorted(set(item.get("claim_ids", [])) - set(CLAIM_IDS))
        if unknown_claims:
            raise InnovationEvidenceError(f"{item['evidence_id']}: unknown claim ids {unknown_claims}")
        unknown_cases = sorted(set(item.get("case_ids", [])) - set(cases))
        if unknown_cases:
            raise InnovationEvidenceError(f"{item['evidence_id']}: unknown case ids {unknown_cases}")
        actual_families = {cases[case_id]["review_family_id"] for case_id in item.get("case_ids", [])}
        if actual_families != set(item.get("review_family_ids", [])):
            raise InnovationEvidenceError(f"{item['evidence_id']}: case/family binding mismatch")
        covered = item.get("covered_stage_ids", [])
        if len(covered) != len(set(covered)) or not set(covered).issubset(LIFECYCLE_STAGES):
            raise InnovationEvidenceError(f"{item['evidence_id']}: invalid lifecycle stage coverage")
        if (
            item.get("provider_relation") == "same_provider_roles"
            and item.get("independent_verification_claimed") is True
        ):
            raise InnovationEvidenceError(
                f"{item['evidence_id']}: same-provider roles cannot claim independent verification"
            )
        if item.get("same_case_full_lifecycle") is True:
            if set(covered) != set(LIFECYCLE_STAGES):
                raise InnovationEvidenceError(
                    f"{item['evidence_id']}: full lifecycle requires all ten stages"
                )
            if len(item.get("case_ids", [])) != 1:
                raise InnovationEvidenceError(
                    f"{item['evidence_id']}: full lifecycle must execute on one bound case"
                )
        resources = item.get("resource_audit")
        required_resources = {
            "provider_calls", "input_tokens", "output_tokens", "wall_seconds",
            "cost", "cost_status",
        }
        if not isinstance(resources, dict) or set(resources) != required_resources:
            raise InnovationEvidenceError(f"{item['evidence_id']}: complete resource audit is required")
        if resources["cost"] is None and resources["cost_status"] == "not_applicable":
            if any(resources[field] != 0 for field in (
                "provider_calls", "input_tokens", "output_tokens",
            )):
                raise InnovationEvidenceError(
                    f"{item['evidence_id']}: nonzero provider use cannot mark cost not applicable"
                )
        elif resources["cost"] is None and resources["cost_status"] != "unknown":
            raise InnovationEvidenceError(f"{item['evidence_id']}: null cost must be marked unknown")
    return items


def _validate_canonical_case_registry(
    ledger: dict[str, Any],
    cases: dict[str, dict[str, Any]],
    repository_root: Path | None,
) -> dict[str, Any]:
    policy = ledger["policy"]
    path_value = policy.get("canonical_case_registry_path")
    expected_hash = policy.get("canonical_case_registry_sha256")
    if (path_value is None) != (expected_hash is None):
        raise InnovationEvidenceError("canonical case registry path and sha256 must be declared together")
    if path_value is None:
        return {"bound": False, "path": None, "sha256": None}
    if repository_root is None:
        raise InnovationEvidenceError("canonical case registry binding requires repository_root")
    root = repository_root.resolve()
    path = (root / path_value).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise InnovationEvidenceError("canonical case registry escapes repository") from exc
    if not path.is_file():
        raise InnovationEvidenceError(f"canonical case registry is missing: {path_value}")
    raw = path.read_bytes()
    observed_hash = hashlib.sha256(raw).hexdigest()
    if observed_hash != expected_hash:
        raise InnovationEvidenceError("canonical case registry sha256 mismatch")
    try:
        registry = json.loads(raw.decode("utf-8"))
        validate_case_registry(registry)
    except (UnicodeDecodeError, json.JSONDecodeError, CaseAdmissionError) as exc:
        raise InnovationEvidenceError(f"canonical case registry is invalid: {exc}") from exc
    registry_cases = {item["case_id"]: item for item in registry["cases"]}
    if set(registry_cases) != set(cases):
        raise InnovationEvidenceError("canonical case registry mismatch: case set differs")
    for case_id, case in cases.items():
        canonical = registry_cases[case_id]
        bindings = {
            "review_family_id": canonical["review_family_id"],
            "split": canonical["split"],
            "training_use": canonical["training_use"],
            "profile_strata": canonical["profile_strata"],
        }
        for field, expected in bindings.items():
            observed = case[field]
            if field == "profile_strata":
                equal = set(observed) == set(expected)
            else:
                equal = observed == expected
            if not equal:
                raise InnovationEvidenceError(
                    f"canonical case registry mismatch: {case_id}.{field}"
                )
    return {"bound": True, "path": path_value, "sha256": observed_hash}


def _qualifying_positive(
    item: dict[str, Any], cases: dict[str, dict[str, Any]], claim_id: str,
) -> bool:
    if claim_id not in item["claim_ids"] or item["result_direction"] != "positive":
        return False
    if not all((
        item["full_mechanism_executed"],
        item["direct_baseline_passed"],
        item["frozen_before_reference"],
        item["reference_opened_after_complete_lock"],
    )):
        return False
    if (
        claim_id == "topic_opportunity_control"
        and item.get("construct_validity_status") != "confirmed"
    ):
        return False
    return bool(item["case_ids"]) and all(
        cases[case_id]["split"] in {"held_out", "prospective"}
        for case_id in item["case_ids"]
    )


def _claim_ceilings(
    items: list[dict[str, Any]], cases: dict[str, dict[str, Any]], blockers: list[str],
) -> dict[str, str]:
    topic_positive = [
        item for item in items
        if _qualifying_positive(item, cases, "topic_opportunity_control")
    ]
    topic_candidate_control = [
        item for item in items
        if "topic_opportunity_control" in item["claim_ids"]
        and item["result_direction"] == "positive"
        and item["direct_baseline_passed"] is True
        and item["full_mechanism_executed"] is False
        and item.get("construct_validity_status") == "confirmed"
        and item["frozen_before_reference"] is True
        and item["reference_opened_after_complete_lock"] is True
        and item["case_ids"]
        and all(cases[case_id]["split"] in {"held_out", "prospective"} for case_id in item["case_ids"])
    ]
    topic_pre_construct = [
        item for item in items
        if "topic_opportunity_control" in item["claim_ids"]
        and item["result_direction"] == "positive"
        and item["direct_baseline_passed"] is True
        and item.get("construct_validity_status") != "confirmed"
        and item["frozen_before_reference"] is True
        and item["reference_opened_after_complete_lock"] is True
        and item["case_ids"]
        and all(cases[case_id]["split"] in {"held_out", "prospective"} for case_id in item["case_ids"])
    ]
    topic_families = {
        family for item in topic_positive for family in item["review_family_ids"]
    }
    if len(topic_families) >= 2:
        if all(item["predicted_ablation_degradation_observed"] for item in topic_positive):
            topic = "replicated_held_out_families_mechanism_identified"
        else:
            topic = "replicated_held_out_families_integrated_mechanism_only"
            blockers.append("component necessity remains unresolved")
    elif len(topic_families) == 1:
        topic = "single_held_out_family_positive"
        blockers.append("topic opportunity has only one positive held-out family")
        if not topic_positive[0]["predicted_ablation_degradation_observed"]:
            blockers.append("component necessity remains unresolved")
    elif topic_candidate_control:
        candidate_families = {
            family for item in topic_candidate_control for family in item["review_family_ids"]
        }
        topic = (
            "single_held_out_candidate_control_positive_not_discovery"
            if len(candidate_families) == 1
            else "replicated_candidate_control_positive_not_discovery"
        )
        blockers.append("topic candidate control did not execute unbiased candidate generation")
        blockers.append("component necessity remains unresolved")
    elif topic_pre_construct:
        topic = "pre_construct_fix_shared_candidate_positive_not_confirmatory"
        blockers.append(
            "topic evidence predates and fails the current construct-validity contract"
        )
        blockers.append("topic candidate control did not execute unbiased candidate generation")
        blockers.append("component necessity remains unresolved")
    else:
        topic = "direct_benefit_not_supported" if any(
            "topic_opportunity_control" in item["claim_ids"]
            and item["result_direction"] == "negative" for item in items
        ) else "not_evaluated_on_held_out_family"

    acquisition_positive = [
        item for item in items
        if _qualifying_positive(item, cases, "conclusion_directed_acquisition")
    ]
    acquisition_families = {
        family for item in acquisition_positive for family in item["review_family_ids"]
    }
    if len(acquisition_families) >= 2:
        acquisition = "replicated_held_out_families_positive"
    elif len(acquisition_families) == 1:
        acquisition = "single_held_out_family_positive"
    elif any(
        "conclusion_directed_acquisition" in item["claim_ids"]
        and item["result_direction"] == "negative" for item in items
        if item["full_mechanism_executed"] is True
    ):
        acquisition = "direct_benefit_not_supported"
        blockers.append("conclusion-directed acquisition did not beat its direct baseline")
    elif any(
        "conclusion_directed_acquisition" in item["claim_ids"]
        and item["result_direction"] == "negative"
        and item["full_mechanism_executed"] is False
        for item in items
    ):
        acquisition = "axis_prompt_proxy_negative_not_full_controller"
        blockers.append(
            "the full risk-times-impact acquisition controller has not been directly evaluated"
        )
    else:
        acquisition = "not_evaluated_on_held_out_family"

    joint_positive = [
        item for item in items
        if "joint_lifecycle_control" in item["claim_ids"]
        and item["same_case_full_lifecycle"] is True
        and _qualifying_positive(item, cases, "joint_lifecycle_control")
    ]
    joint = (
        "single_case_full_lifecycle_positive" if joint_positive
        else "not_evaluated_full_lifecycle"
    )
    if not joint_positive:
        blockers.append("the two innovations have not been evaluated in one blind ten-stage case")

    student_positive = [
        item for item in items
        if item["evaluation_kind"] == "student_comparison"
        and _qualifying_positive(item, cases, "agent_distillation")
    ]
    development_student_positive = [
        item for item in items
        if item["evaluation_kind"] == "student_comparison"
        and "agent_distillation" in item["claim_ids"]
        and item["result_direction"] == "positive"
        and item["direct_baseline_passed"] is True
        and item["frozen_before_reference"] is True
        and item["case_ids"]
        and all(cases[case_id]["split"] == "development" for case_id in item["case_ids"])
    ]
    development_student_comparisons = [
        item for item in items
        if item["evaluation_kind"] == "student_comparison"
        and "agent_distillation" in item["claim_ids"]
        and item["case_ids"]
        and all(cases[case_id]["split"] == "development" for case_id in item["case_ids"])
    ]
    if student_positive:
        distillation = "single_held_out_student_gain"
    elif development_student_positive:
        distillation = "development_only_student_gain_not_generalization"
        blockers.append("agent distillation gain is limited to development families")
        blockers.append("agent distillation has no held-out student-versus-control evaluation")
    elif development_student_comparisons:
        distillation = "development_student_comparison_no_gain"
        blockers.append("agent distillation did not show a development-set student gain")
        blockers.append("agent distillation has no held-out student-versus-control evaluation")
    elif any("agent_distillation" in item["claim_ids"] for item in items):
        distillation = "governance_only_no_student_gain"
        blockers.append("agent distillation has no held-out student-versus-control evaluation")
    else:
        distillation = "not_evaluated"

    return {
        "topic_opportunity_control": topic,
        "conclusion_directed_acquisition": acquisition,
        "joint_lifecycle_control": joint,
        "agent_distillation": distillation,
    }


def audit_innovation_evidence(
    ledger: dict[str, Any], repository_root: Path | None = None,
) -> dict[str, Any]:
    """Derive claim ceilings without upgrading negative or partial evidence."""
    if not isinstance(ledger, dict) or ledger.get("schema_version") != "1.0":
        raise InnovationEvidenceError("innovation evidence ledger schema_version 1.0 is required")
    policy = ledger.get("policy")
    if not isinstance(policy, dict) or not all(policy.get(key) is True for key in (
        "journal_prestige_is_admission_only",
        "same_provider_is_not_independent",
        "negative_results_must_be_retained",
        "full_lifecycle_requires_same_case",
    )):
        raise InnovationEvidenceError("scientific integrity policy is incomplete")
    _validate_stages(ledger)
    cases = _case_index(ledger)
    items = _validate_evidence(ledger, cases)
    registry_binding = _validate_canonical_case_registry(
        ledger, cases, repository_root,
    )
    if repository_root is not None:
        root = repository_root.resolve()
        artifact_paths = [
            path
            for stage in ledger["lifecycle_stages"]
            for path in stage["artifact_paths"]
        ] + [
            path
            for item in items
            for path in item["artifact_paths"]
        ]
        for relative in artifact_paths:
            resolved = (root / relative).resolve()
            try:
                resolved.relative_to(root)
            except ValueError as exc:
                raise InnovationEvidenceError(
                    f"evidence artifact escapes repository: {relative}"
                ) from exc
            if not resolved.is_file():
                raise InnovationEvidenceError(f"missing evidence artifact: {relative}")

    required_profiles = list(policy.get("required_profile_strata", []))
    present_profiles = {
        profile
        for case in cases.values()
        if case.get("authority_identity_verified") is True
        and case.get("broad_decision_relevance") is True
        and case.get("common_or_high_burden") is True
        and case.get("representativeness_sources")
        for profile in case.get("profile_strata", [])
    }
    missing_profiles = sorted(set(required_profiles) - present_profiles)
    blockers: list[str] = []
    if missing_profiles:
        blockers.append("representative profile portfolio is incomplete")
    ceilings = _claim_ceilings(items, cases, blockers)

    joint_items = [item for item in items if "joint_lifecycle_control" in item["claim_ids"]]
    complete_joint = [item for item in joint_items if item["same_case_full_lifecycle"] is True]
    covered_joint = {
        stage for item in complete_joint for stage in item["covered_stage_ids"]
    }
    if not complete_joint:
        covered_joint = {
            stage for item in joint_items for stage in item["covered_stage_ids"]
        }
    missing_joint = [stage for stage in LIFECYCLE_STAGES if stage not in covered_joint]

    return {
        "valid": True,
        "ledger_id": ledger.get("ledger_id"),
        "claim_ceilings": ceilings,
        "claim_blockers": list(dict.fromkeys(blockers)),
        "canonical_case_registry": registry_binding,
        "portfolio": {
            "registered_cases": len(cases),
            "required_profile_strata": required_profiles,
            "represented_profile_strata": sorted(present_profiles),
            "missing_profile_strata": missing_profiles,
            "representative_profile_coverage_complete": not missing_profiles,
        },
        "joint_lifecycle": {
            "complete": bool(complete_joint),
            "complete_case_ids": [item["case_ids"][0] for item in complete_joint],
            "covered_stage_ids": [stage for stage in LIFECYCLE_STAGES if stage in covered_joint],
            "missing_stage_ids": missing_joint,
        },
        "result_direction_counts": dict(sorted(Counter(
            item["result_direction"] for item in items
        ).items())),
    }
