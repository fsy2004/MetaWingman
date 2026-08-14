"""Build checksummed living-review snapshots, deltas, and graph impact plans."""

from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Any

from .provenance_graph import GraphError, ProvenanceGraph
from .schema_guard import SchemaValidationError, validate_document
from .state_store import sha256_json


class LivingUpdateError(ValueError):
    """Raised when living-review snapshots are invalid or incomparable."""


def _snapshot_payload(snapshot: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in snapshot.items() if key != "snapshot_sha256"}


def build_snapshot(candidate: dict[str, Any]) -> dict[str, Any]:
    output = copy.deepcopy(candidate)
    output.setdefault("schema_version", "1.0")
    records = output.get("records")
    if not isinstance(records, list):
        raise LivingUpdateError("snapshot.records must be a list")
    canonical_ids = [item.get("canonical_id") for item in records if isinstance(item, dict)]
    if len(canonical_ids) != len(records) or len(set(canonical_ids)) != len(canonical_ids):
        raise LivingUpdateError("snapshot canonical_id values must be present and unique")
    output["records"] = sorted(records, key=lambda item: item["canonical_id"])
    output["snapshot_sha256"] = sha256_json(_snapshot_payload(output))
    try:
        validate_document(output, "living_snapshot")
    except SchemaValidationError as exc:
        raise LivingUpdateError(str(exc)) from exc
    return output


def verify_snapshot(snapshot: dict[str, Any]) -> None:
    try:
        validate_document(snapshot, "living_snapshot")
    except SchemaValidationError as exc:
        raise LivingUpdateError(str(exc)) from exc
    expected = sha256_json(_snapshot_payload(snapshot))
    if snapshot["snapshot_sha256"] != expected:
        raise LivingUpdateError(f"Snapshot hash mismatch: {snapshot['snapshot_id']}")


def compare_snapshots(
    previous: dict[str, Any],
    current: dict[str, Any],
    *,
    delta_id: str,
    graph: ProvenanceGraph | None = None,
    created_at_utc: str | None = None,
) -> dict[str, Any]:
    verify_snapshot(previous)
    verify_snapshot(current)
    for field in ("project_id", "source_id", "query_sha256"):
        if previous[field] != current[field]:
            raise LivingUpdateError(f"Snapshots differ in {field}; create a protocol/query amendment instead")
    if previous["snapshot_id"] == current["snapshot_id"]:
        raise LivingUpdateError("Snapshot IDs must differ")
    prior = {item["canonical_id"]: item for item in previous["records"]}
    present = {item["canonical_id"]: item for item in current["records"]}
    changes: list[dict[str, Any]] = []
    for canonical_id in sorted(set(prior) | set(present)):
        old, new = prior.get(canonical_id), present.get(canonical_id)
        if old is None:
            change_type, reasons = "new", ["canonical_record_new"]
        elif new is None:
            change_type, reasons = "removed", ["canonical_record_absent_from_current_snapshot"]
        else:
            reasons = []
            if old["status"] != new["status"]:
                reasons.append("publication_status_changed")
            if old["metadata_sha256"] != new["metadata_sha256"] or old["version"] != new["version"]:
                reasons.append("metadata_or_version_changed")
            if old["status"] in {"removed", "withdrawn"} and new["status"] == "active":
                change_type = "restored"
                reasons.append("record_restored")
            elif "publication_status_changed" in reasons:
                change_type = "status_changed"
            elif reasons:
                change_type = "metadata_changed"
            else:
                continue
        changes.append({
            "canonical_id": canonical_id,
            "change_type": change_type,
            "previous_record": old,
            "current_record": new,
            "reason_codes": sorted(set(reasons)),
        })

    impact: list[dict[str, Any]] = []
    for change in changes:
        record = change["current_record"] or change["previous_record"]
        node = record.get("provenance_node") if record else None
        if graph is None:
            impact.append({
                "canonical_id": change["canonical_id"], "source_node": node,
                "affected_nodes": [], "impact_status": "graph_unavailable",
                "notes": "Run graph impact after importing the record node.",
            })
            continue
        if node is None or graph.get_node(node["type"], node["id"]) is None:
            impact.append({
                "canonical_id": change["canonical_id"], "source_node": node,
                "affected_nodes": [], "impact_status": "not_in_graph",
                "notes": "New or unresolved record requires screening and lineage before downstream impact is known.",
            })
            continue
        try:
            affected = graph.impact(node["type"], node["id"])
        except GraphError as exc:
            raise LivingUpdateError(str(exc)) from exc
        impact.append({
            "canonical_id": change["canonical_id"], "source_node": node,
            "affected_nodes": affected,
            "impact_status": "downstream_nodes_found" if affected else "no_downstream_nodes",
            "notes": "Accepted graph edges determine the current impact scope.",
        })

    actions: set[str] = set()
    for change in changes:
        if change["change_type"] in {"new", "restored"}:
            actions.update(("screen_new_records", "human_triage"))
        else:
            actions.update(("recheck_report_identity", "human_triage"))
    affected_types = {
        item["node"]["type"]
        for impact_item in impact
        for item in impact_item["affected_nodes"]
        if isinstance(item, dict) and isinstance(item.get("node"), dict)
    }
    if affected_types & {"study", "trial", "cohort", "arm", "result"}:
        actions.update(("rerun_lineage", "rerun_extraction", "rerun_appraisal"))
    if affected_types & {"synthesis", "analysis", "analysis_output"}:
        actions.update(("rerun_analysis", "reassess_certainty"))
    if affected_types & {"certainty", "claim"}:
        actions.update(("reassess_certainty", "recompile_claims"))
    order = (
        "screen_new_records", "recheck_report_identity", "rerun_lineage", "rerun_extraction",
        "rerun_appraisal", "rerun_analysis", "reassess_certainty", "recompile_claims",
        "human_triage",
    )
    required_actions = [action for action in order if action in actions]
    now = created_at_utc or datetime.now(timezone.utc).isoformat()
    output = {
        "schema_version": "1.0",
        "delta_id": delta_id,
        "project_id": current["project_id"],
        "source_id": current["source_id"],
        "previous_snapshot_id": previous["snapshot_id"],
        "current_snapshot_id": current["snapshot_id"],
        "changes": changes,
        "impact": impact,
        "required_actions": required_actions,
        "status": "no_change" if not changes else "ready_for_human",
        "human_review": {
            "status": "not_required" if not changes else "pending",
            "reviewed_by": "", "reviewed_at_utc": None, "decision": None, "notes": "",
        },
        "created_at_utc": now,
    }
    try:
        validate_document(output, "living_delta")
    except SchemaValidationError as exc:
        raise LivingUpdateError(str(exc)) from exc
    return output
