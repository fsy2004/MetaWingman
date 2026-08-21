"""Persistent stage-gated review-case state transitions."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from .schema_guard import validate_document
from .state_store import atomic_write_json, canonical_json, sha256_json


class ReviewCaseError(ValueError):
    """Raised when a review-case transition would skip or corrupt a gate."""


STAGE_ORDER = (
    "topic", "protocol", "search", "screening", "documents", "extraction",
    "appraisal", "analysis", "certainty", "writing", "review", "living",
)


def case_path(project: Path) -> Path:
    return project / "00_admin" / "review_case_state.json"


def read_case_state(project: Path) -> dict[str, Any]:
    path = case_path(project)
    if not path.is_file():
        raise ReviewCaseError(f"review case state is missing: {path}")
    state = json.loads(path.read_text(encoding="utf-8"))
    validate_document(state, "review_case_state")
    return state


def initialize_review_case(project: Path, candidate: dict[str, Any], *, created_at_utc: str) -> dict[str, Any]:
    validate_document(candidate, "question_synthesis_candidate")
    state = {
        "schema_version": "1.0",
        "case_id": f"review-case-{sha256_json(candidate)[:20]}",
        "active_stage": "topic",
        "completed_gates": [],
        "selected_joint_design": copy.deepcopy(candidate),
        "protocol_sha256": None,
        "lineage_node_ids": {key: [] for key in ("record", "report", "study", "arm", "result", "estimand", "synthesis", "certainty", "claim")},
        "unresolved_conflicts": [],
        "abstentions": [],
        "pending_permissions": [],
        "budget": {},
        "revision": 0,
        "created_at_utc": created_at_utc,
        "updated_at_utc": created_at_utc,
    }
    atomic_write_json(case_path(project), state, "review_case_state")
    return state


def _append_event(project: Path, before: dict[str, Any], after: dict[str, Any], action: dict[str, Any], observation: dict[str, Any]) -> None:
    path = project / "00_admin" / "review_case_events.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    event = {"before_sha256": sha256_json(before), "after_sha256": sha256_json(after), "action": action, "observation": observation}
    with path.open("ab") as handle:
        handle.write(canonical_json(event) + b"\n")


def transition_review_case(
    project: Path,
    action: dict[str, Any],
    observation: dict[str, Any],
    *,
    updated_at_utc: str,
) -> dict[str, Any]:
    state = read_case_state(project)
    if int(action.get("expected_revision", -1)) != state["revision"]:
        raise ReviewCaseError("action revision is stale")
    target = str(action.get("stage") or "")
    if target not in STAGE_ORDER:
        raise ReviewCaseError("unknown target stage")
    current_index = STAGE_ORDER.index(state["active_stage"])
    target_index = STAGE_ORDER.index(target)
    if target_index > current_index + 1:
        raise ReviewCaseError("review case cannot skip a stage gate")
    if observation.get("status") != "verified" or observation.get("external") is not True:
        raise ReviewCaseError("accepted state transition requires an external verified observation")
    result = copy.deepcopy(state)
    if target_index == current_index + 1:
        result["completed_gates"].append(state["active_stage"])
        result["active_stage"] = target
    for kind, ids in (observation.get("lineage_node_ids") or {}).items():
        if kind not in result["lineage_node_ids"]:
            raise ReviewCaseError(f"unknown lineage node type: {kind}")
        result["lineage_node_ids"][kind] = sorted(set(result["lineage_node_ids"][kind]) | set(ids))
    result["revision"] += 1
    result["updated_at_utc"] = updated_at_utc
    validate_document(result, "review_case_state")
    atomic_write_json(case_path(project), result, "review_case_state")
    _append_event(project, state, result, action, observation)
    return result
