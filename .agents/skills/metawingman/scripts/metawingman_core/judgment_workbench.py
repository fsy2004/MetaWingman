"""Build evidence dossiers for appraisal, missing evidence, and certainty judgments."""

from __future__ import annotations

import copy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .schema_guard import SchemaValidationError, validate_document, validate_json_file


class JudgmentWorkbenchError(ValueError):
    """Raised when a high-risk judgment dossier lacks method or evidence context."""


def load_appraisal_adapter(path: Path) -> dict[str, Any]:
    try:
        adapter = validate_json_file(path, "appraisal_framework_adapter")
    except (OSError, SchemaValidationError) as exc:
        raise JudgmentWorkbenchError(str(exc)) from exc
    if adapter["status"] == "retired":
        raise JudgmentWorkbenchError(f"Appraisal adapter is retired: {adapter['adapter_id']}")
    return adapter


def _role_ready(role: dict[str, Any], *, opposition: bool = False) -> bool:
    return bool(
        role.get("actor_id")
        and (role.get("counter_judgment") if opposition else role.get("judgment"))
        and role.get("rationale")
    )


def build_appraisal_dossier(
    adapter: dict[str, Any],
    candidate: dict[str, Any],
    *,
    created_at_utc: str | None = None,
) -> dict[str, Any]:
    """Compile a model/human proposal into a non-final evidence dossier."""

    try:
        validate_document(adapter, "appraisal_framework_adapter")
    except SchemaValidationError as exc:
        raise JudgmentWorkbenchError(str(exc)) from exc
    review_family = str(candidate.get("review_family") or "")
    if review_family not in adapter["supported_review_families"]:
        raise JudgmentWorkbenchError(
            f"Adapter {adapter['adapter_id']} does not support review family {review_family!r}"
        )
    target = candidate.get("target")
    if not isinstance(target, dict) or target.get("type") != adapter["target_granularity"]:
        raise JudgmentWorkbenchError(
            f"Adapter target must be {adapter['target_granularity']}"
        )
    supplied_domains = candidate.get("domains")
    if not isinstance(supplied_domains, list):
        raise JudgmentWorkbenchError("candidate.domains must be a list")
    by_id = {item.get("domain_id"): item for item in supplied_domains if isinstance(item, dict)}
    if len(by_id) != len(supplied_domains):
        raise JudgmentWorkbenchError("Domain IDs must be present and unique")

    domains: list[dict[str, Any]] = []
    missing: list[str] = []
    for definition in adapter["domains"]:
        item = by_id.get(definition["domain_id"])
        if item is None:
            missing.append(f"domain:{definition['domain_id']}")
            continue
        questions = item.get("signaling_questions")
        if not isinstance(questions, list):
            raise JudgmentWorkbenchError(
                f"Domain {definition['domain_id']} signaling_questions must be a list"
            )
        question_ids = [question.get("question_id") for question in questions if isinstance(question, dict)]
        unknown = sorted(set(question_ids) - set(definition["signaling_question_ids"]))
        absent = sorted(set(definition["signaling_question_ids"]) - set(question_ids))
        if unknown:
            raise JudgmentWorkbenchError(
                f"Domain {definition['domain_id']} has unknown signaling question IDs: {', '.join(unknown)}"
            )
        missing.extend(f"question:{definition['domain_id']}:{question_id}" for question_id in absent)
        for question in questions:
            if question.get("answer") not in adapter["allowed_answers"]:
                raise JudgmentWorkbenchError(
                    f"Unsupported answer for {question.get('question_id')}: {question.get('answer')}"
                )
        domains.append({
            "domain_id": definition["domain_id"],
            "label": definition["label"],
            "signaling_questions": questions,
            "supporting_anchor_ids": list(item.get("supporting_anchor_ids") or []),
            "counterevidence_anchor_ids": list(item.get("counterevidence_anchor_ids") or []),
            "proposal": str(item.get("proposal") or "Unresolved"),
            "rationale": str(item.get("rationale") or "Insufficient evidence for a domain proposal."),
        })
    extra = sorted(set(by_id) - {item["domain_id"] for item in adapter["domains"]})
    if extra:
        raise JudgmentWorkbenchError("Unknown appraisal domains: " + ", ".join(extra))

    proposal = copy.deepcopy(candidate.get("overall_proposal") or {
        "actor_id": "", "judgment": "", "rationale": ""
    })
    opposition = copy.deepcopy(candidate.get("opposition") or {
        "actor_id": "", "counter_judgment": "", "anchor_ids": [], "rationale": ""
    })
    judge = copy.deepcopy(candidate.get("judge_recommendation") or {
        "actor_id": "", "judgment": "", "reason_codes": ["judgment_not_run"],
        "confidence": None, "abstained": True,
    })
    evidence_nodes = list(candidate.get("evidence_node_ids") or [])
    ready = bool(
        not missing
        and evidence_nodes
        and _role_ready(proposal)
        and _role_ready(opposition, opposition=True)
        and judge.get("actor_id")
        and judge.get("judgment")
    )
    now = created_at_utc or datetime.now(timezone.utc).isoformat()
    dossier = {
        "schema_version": "1.0",
        "dossier_id": str(candidate.get("dossier_id") or ""),
        "dossier_type": str(candidate.get("dossier_type") or "risk_of_bias"),
        "target": target,
        "framework": {
            **adapter["framework"],
            "adapter_version": adapter["adapter_version"],
        },
        "evidence_node_ids": evidence_nodes,
        "domains": domains,
        "overall_proposal": proposal,
        "opposition": opposition,
        "judge_recommendation": judge,
        "missing_information": sorted(set(list(candidate.get("missing_information") or []) + missing)),
        "status": "ready_for_adjudication" if ready else "draft",
        "final_judgment": None,
        "human_signature": {
            "status": "pending", "signed_by": "", "signed_at_utc": None, "notes": "",
        },
        "created_at_utc": now,
        "updated_at_utc": now,
    }
    try:
        validate_document(dossier, "appraisal_dossier")
    except SchemaValidationError as exc:
        raise JudgmentWorkbenchError(str(exc)) from exc
    return dossier


def build_missing_evidence_matrix(candidate: dict[str, Any], *, created_at_utc: str | None = None) -> dict[str, Any]:
    """Validate a study-by-synthesis availability audit without finalizing ROB-ME/MEN."""

    output = copy.deepcopy(candidate)
    now = created_at_utc or datetime.now(timezone.utc).isoformat()
    output.setdefault("schema_version", "1.0")
    output.setdefault("study_level_flags", [])
    output.setdefault("proposal", {
        "actor_id": "", "judgment": "", "reason_codes": ["proposal_not_run"],
        "anchor_ids": [], "rationale": "", "abstained": True,
    })
    output.setdefault("opposition", {
        "actor_id": "", "judgment": "", "reason_codes": ["opposition_not_run"],
        "anchor_ids": [], "rationale": "", "abstained": True,
    })
    output.setdefault("judge_recommendation", {
        "actor_id": "", "judgment": "", "reason_codes": ["judge_not_run"],
        "anchor_ids": [], "rationale": "", "abstained": True,
    })
    roles_ready = all(
        output[name].get("actor_id") and output[name].get("judgment") and output[name].get("rationale")
        for name in ("proposal", "opposition", "judge_recommendation")
    )
    if output.get("status") == "final":
        raise JudgmentWorkbenchError("The builder cannot create a final missing-evidence judgment")
    output["status"] = "ready_for_adjudication" if roles_ready else "draft"
    output["final_judgment"] = None
    output["human_signature"] = {
        "status": "pending", "signed_by": "", "signed_at_utc": None, "notes": "",
    }
    output.setdefault("created_at_utc", now)
    output["updated_at_utc"] = now
    try:
        validate_document(output, "missing_evidence_matrix")
    except SchemaValidationError as exc:
        raise JudgmentWorkbenchError(str(exc)) from exc
    return output


def locate_interval_against_threshold(
    estimate: float,
    ci_lower: float,
    ci_upper: float,
    threshold: float,
) -> dict[str, Any]:
    """Locate an interval geometrically; do not infer a GRADE judgment."""

    numbers = [float(value) for value in (estimate, ci_lower, ci_upper, threshold)]
    if not all(value == value and abs(value) != float("inf") for value in numbers):
        raise JudgmentWorkbenchError("Threshold geometry requires finite numbers")
    if ci_lower > ci_upper:
        raise JudgmentWorkbenchError("ci_lower cannot exceed ci_upper")
    if ci_upper < threshold:
        relation = "entire_interval_below"
    elif ci_lower > threshold:
        relation = "entire_interval_above"
    elif ci_lower == ci_upper == threshold:
        relation = "point_at_threshold"
    else:
        relation = "interval_crosses_threshold"
    return {
        "estimate": estimate,
        "ci_lower": ci_lower,
        "ci_upper": ci_upper,
        "threshold": threshold,
        "relation": relation,
        "grade_judgment": None,
        "requires_context": [
            "outcome importance", "effect direction", "absolute effects",
            "decision thresholds", "clinical context", "human adjudication",
        ],
    }
