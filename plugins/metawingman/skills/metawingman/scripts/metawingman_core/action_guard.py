"""Authorize typed scientific actions and route unsafe work to abstention."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from .method_contract import inspect_protocol_freeze_readiness
from .schema_guard import SchemaValidationError, validate_document, validate_json_file


DecisionStatus = Literal["allowed", "blocked", "abstained"]

RISK_ORDER = {"low": 0, "medium": 1, "high": 2, "irreversible": 3}
MINIMUM_RISK = {
    "read_public_metadata": "low",
    "import_user_artifact": "low",
    "retrieve_open_access": "low",
    "rank_records": "low",
    "propose_screening": "medium",
    "propose_extraction": "medium",
    "run_analysis": "medium",
    "draft_claim": "medium",
    "credentialed_browser_handoff": "high",
    "finalize_exclusion": "high",
    "freeze_protocol": "high",
    "finalize_risk_of_bias": "high",
    "finalize_grade": "high",
    "decide_poolability": "high",
    "submit_external": "irreversible",
}
EVIDENCE_REQUIRED = {
    "propose_screening",
    "propose_extraction",
    "draft_claim",
    "finalize_exclusion",
    "finalize_risk_of_bias",
    "finalize_grade",
    "decide_poolability",
}


def _is_timezone_aware_datetime(value: str) -> bool:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None


@dataclass(frozen=True)
class ActionDecision:
    status: DecisionStatus
    reason_codes: tuple[str, ...]
    required_human_role: str

    @property
    def allowed(self) -> bool:
        return self.status == "allowed"


def _protocol_freeze_decision(action: dict[str, Any], project_root: Path | None) -> ActionDecision | None:
    if action["action_type"] != "freeze_protocol":
        return None
    if project_root is None:
        return ActionDecision("abstained", ("project_context_required",), "human_lead")
    root = project_root.resolve()
    files = {
        "review_profile": ("01_protocol/review_profile.json", "review_profile"),
        "protocol": ("01_protocol/protocol.json", "protocol"),
        "protocol_criteria": ("01_protocol/protocol_criteria.json", "protocol_criteria"),
        "review_state": ("00_admin/review_state.json", "review_state"),
    }
    documents: dict[str, dict[str, Any]] = {}
    try:
        for label, (relative, schema_name) in files.items():
            path = root / relative
            if not path.is_file():
                return ActionDecision(
                    "abstained",
                    ("protocol_context_incomplete", f"missing:{relative}"),
                    "human_lead",
                )
            documents[label] = validate_json_file(path, schema_name)
    except SchemaValidationError as exc:
        return ActionDecision(
            "blocked",
            ("protocol_context_schema_invalid", *exc.errors),
            "runtime_operator",
        )
    reasons = inspect_protocol_freeze_readiness(
        root,
        documents["review_profile"],
        documents["protocol"],
        documents["protocol_criteria"],
        documents["review_state"],
        action["input_sha256"],
    )
    if not reasons:
        return None
    status: DecisionStatus = (
        "blocked"
        if any("input_sha256 does not match" in reason for reason in reasons)
        else "abstained"
    )
    return ActionDecision(status, ("protocol_not_ready_to_freeze", *reasons), "human_lead")


def evaluate_action(action: dict[str, Any], project_root: Path | None = None) -> ActionDecision:
    try:
        validate_document(action, "scientific_action")
    except SchemaValidationError as exc:
        return ActionDecision("blocked", ("schema_validation_failed", *exc.errors), "runtime_operator")

    action_type = action["action_type"]
    minimum_risk = MINIMUM_RISK[action_type]
    if RISK_ORDER[action["risk_class"]] < RISK_ORDER[minimum_risk]:
        return ActionDecision("blocked", ("risk_class_understated",), "runtime_operator")

    if action["instruction_source"] == "untrusted_document":
        return ActionDecision(
            "blocked",
            ("untrusted_content_cannot_authorize_actions",),
            "runtime_operator",
        )

    if action_type in EVIDENCE_REQUIRED and not action["evidence_anchor_ids"]:
        return ActionDecision(
            "abstained",
            ("evidence_anchor_required",),
            "domain_reviewer",
        )

    approval = action["human_approval"]
    approval_required = RISK_ORDER[minimum_risk] >= RISK_ORDER["high"]
    if approval_required:
        if approval["status"] == "rejected":
            return ActionDecision("blocked", ("human_approval_rejected",), "human_lead")
        if approval["status"] == "approved" and (
            not approval["approved_by"]
            or not _is_timezone_aware_datetime(approval["approved_at_utc"])
        ):
            return ActionDecision("blocked", ("invalid_human_approval_record",), "human_lead")
        if approval["status"] == "approved" and approval["scope"] != action["action_id"]:
            return ActionDecision("blocked", ("human_approval_scope_mismatch",), "human_lead")
    elif approval["status"] == "rejected":
        return ActionDecision("blocked", ("human_approval_rejected",), "human_lead")

    project_decision = _protocol_freeze_decision(action, project_root)
    if project_decision is not None:
        return project_decision

    if approval_required and approval["status"] != "approved":
        return ActionDecision("abstained", ("human_approval_required",), "human_lead")

    return ActionDecision("allowed", (), "")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", type=Path, help="Scientific action request JSON")
    parser.add_argument("--project", type=Path, help="Review project root for context-dependent gates")
    args = parser.parse_args()
    try:
        action = json.loads(args.action.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "blocked", "reason_codes": [f"invalid_json: {exc}"]}, indent=2))
        return 1
    decision = evaluate_action(action, args.project)
    print(json.dumps(asdict(decision), indent=2))
    return 0 if decision.allowed else 2


if __name__ == "__main__":
    raise SystemExit(main())
