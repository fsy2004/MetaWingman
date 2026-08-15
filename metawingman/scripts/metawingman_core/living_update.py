"""Build checksummed living-review snapshots, deltas, and graph impact plans."""

from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Any

from .biomedical_domain import validate_pack_integrity
from .provenance_graph import GraphError, ProvenanceGraph
from .schema_guard import SchemaValidationError, validate_document
from .state_store import sha256_json


class LivingUpdateError(ValueError):
    """Raised when living-review snapshots are invalid or incomparable."""


def _require_sha256(value: Any, field: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(
        character not in "0123456789abcdef" for character in value
    ):
        raise LivingUpdateError(f"{field} must be a lowercase SHA-256 digest")
    return value


def _domain_state_payload(snapshot: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in snapshot.items()
        if key != "domain_state_sha256"
    }


def _canonical_terminology_releases(values: Any) -> list[dict[str, str]]:
    if not isinstance(values, list):
        raise LivingUpdateError("terminology_releases must be a list")
    releases: list[dict[str, str]] = []
    for item in values:
        if not isinstance(item, dict):
            raise LivingUpdateError("terminology release entries must be objects")
        try:
            release = {
                "pack_id": str(item["pack_id"]),
                "system": str(item["system"]),
                "release": str(item["release"]),
                "content_sha256": _require_sha256(
                    item["content_sha256"], "terminology release content_sha256"
                ),
            }
        except KeyError as exc:
            raise LivingUpdateError(
                f"terminology release is missing {exc.args[0]}"
            ) from exc
        if not all(release[field] for field in ("pack_id", "system", "release")):
            raise LivingUpdateError("terminology release identifiers must not be empty")
        releases.append(release)
    identities = [
        (item["pack_id"], item["system"], item["release"])
        for item in releases
    ]
    if len(identities) != len(set(identities)):
        raise LivingUpdateError("terminology release identities must be unique")
    return sorted(
        releases,
        key=lambda item: (
            item["pack_id"], item["system"], item["release"], item["content_sha256"]
        ),
    )


def build_domain_state_snapshot(
    packs: list[dict[str, Any]],
    *,
    snapshot_id: str,
    affected_evidence: list[str] | None = None,
    affected_claims: list[str] | None = None,
) -> dict[str, Any]:
    """Capture active domain pack and terminology state for a living run."""
    active = []
    pack_ids: set[str] = set()
    terminology_releases: list[dict[str, str]] = []
    for pack in packs:
        validate_pack_integrity(pack)
        if pack["status"] != "active":
            continue
        if pack["pack_id"] in pack_ids:
            raise LivingUpdateError(f"duplicate active domain pack: {pack['pack_id']}")
        pack_ids.add(pack["pack_id"])
        active.append({
            "pack_id": pack["pack_id"],
            "version": pack["version"],
            "content_sha256": pack["content_sha256"],
        })
        terminology_releases.extend({
            "pack_id": pack["pack_id"],
            "system": item["system"],
            "release": item["release"],
            "content_sha256": item["content_sha256"],
        } for item in pack["terminology_releases"])
    if not active:
        raise LivingUpdateError("at least one active domain pack is required")
    active.sort(key=lambda item: item["pack_id"])
    output = {
        "schema_version": "1.0",
        "snapshot_id": snapshot_id,
        "active_pack_ids": [item["pack_id"] for item in active],
        "active_packs": active,
        "domain_pack_hash": sha256_json(active),
        "terminology_releases": _canonical_terminology_releases(terminology_releases),
        "affected_evidence": sorted(set(affected_evidence or [])),
        "affected_claims": sorted(set(affected_claims or [])),
    }
    output["domain_state_sha256"] = sha256_json(_domain_state_payload(output))
    return output


def _verify_domain_state_snapshot(snapshot: dict[str, Any]) -> None:
    if "domain_state_sha256" not in snapshot:
        return
    expected = sha256_json(_domain_state_payload(snapshot))
    if _require_sha256(snapshot["domain_state_sha256"], "domain_state_sha256") != expected:
        raise LivingUpdateError("domain state snapshot hash mismatch")
    active_packs = snapshot.get("active_packs")
    if not isinstance(active_packs, list) or not active_packs:
        raise LivingUpdateError("domain state active_packs must be a non-empty list")
    computed_pack_hash = sha256_json(active_packs)
    if snapshot.get("domain_pack_hash") != computed_pack_hash:
        raise LivingUpdateError("domain state pack aggregate hash mismatch")
    if snapshot.get("active_pack_ids") != [item.get("pack_id") for item in active_packs]:
        raise LivingUpdateError("active_pack_ids do not match active_packs")
    _canonical_terminology_releases(snapshot.get("terminology_releases", []))


def _pack_drift_codes(
    previous: dict[str, Any],
    current: dict[str, Any] | None,
) -> list[str]:
    if current is None or "active_packs" not in previous:
        return []
    prior = {item["pack_id"]: item for item in previous["active_packs"]}
    present = {item["pack_id"]: item for item in current["active_packs"]}
    codes: list[str] = []
    if set(prior) != set(present):
        codes.append("domain_pack_set_changed")
    common = set(prior) & set(present)
    if any(prior[item]["version"] != present[item]["version"] for item in common):
        codes.append("domain_pack_version_changed")
    if any(
        prior[item]["content_sha256"] != present[item]["content_sha256"]
        for item in common
    ):
        codes.append("domain_pack_hash_changed")
    return codes


def plan_living_update(
    previous_domain_snapshot: dict[str, Any],
    *,
    current_pack_hash: str | None = None,
    current_domain_snapshot: dict[str, Any] | None = None,
    current_terminology_releases: list[dict[str, str]] | None = None,
    migration_event: dict[str, Any] | None = None,
    affected_evidence: list[str] | None = None,
    affected_claims: list[str] | None = None,
) -> dict[str, Any]:
    """Fail closed on domain drift until a matching non-model migration is explicit."""
    _verify_domain_state_snapshot(previous_domain_snapshot)
    if current_domain_snapshot is not None:
        _verify_domain_state_snapshot(current_domain_snapshot)
    previous_pack_hash = _require_sha256(
        previous_domain_snapshot.get("domain_pack_hash"), "previous domain_pack_hash"
    )
    if current_domain_snapshot is not None:
        observed_current_hash = _require_sha256(
            current_domain_snapshot.get("domain_pack_hash"), "current domain_pack_hash"
        )
        if current_pack_hash is not None and current_pack_hash != observed_current_hash:
            raise LivingUpdateError(
                "current_pack_hash does not match current_domain_snapshot"
            )
        current_pack_hash = observed_current_hash
    current_pack_hash = _require_sha256(
        current_pack_hash, "current domain_pack_hash"
    )

    previous_terms = _canonical_terminology_releases(
        previous_domain_snapshot.get("terminology_releases", [])
    )
    if current_domain_snapshot is not None:
        current_terms = _canonical_terminology_releases(
            current_domain_snapshot.get("terminology_releases", [])
        )
        if current_terminology_releases is not None:
            supplied_terms = _canonical_terminology_releases(
                current_terminology_releases
            )
            if supplied_terms != current_terms:
                raise LivingUpdateError(
                    "current terminology releases do not match current_domain_snapshot"
                )
    elif current_terminology_releases is None:
        current_terms = previous_terms
    else:
        current_terms = _canonical_terminology_releases(
            current_terminology_releases
        )

    reason_codes = _pack_drift_codes(
        previous_domain_snapshot, current_domain_snapshot
    )
    if previous_pack_hash != current_pack_hash:
        reason_codes.append("domain_pack_hash_changed")
    if previous_terms != current_terms:
        reason_codes.append("terminology_release_changed")
    reason_codes = sorted(set(reason_codes))

    previous_state_hash = previous_domain_snapshot.get(
        "domain_state_sha256", previous_pack_hash
    )
    current_state_hash = (
        current_domain_snapshot.get("domain_state_sha256", current_pack_hash)
        if current_domain_snapshot is not None else current_pack_hash
    )
    migration_accepted = False
    if reason_codes and migration_event is not None:
        actor_type = migration_event.get("actor_type")
        if actor_type == "model":
            reason_codes.append("model_response_cannot_authorize_domain_migration")
        elif (
            migration_event.get("event_type") == "domain_migration"
            and actor_type in {"human", "tool"}
            and migration_event.get("approved") is True
            and migration_event.get("from_domain_state_sha256") == previous_state_hash
            and migration_event.get("to_domain_state_sha256") == current_state_hash
        ):
            migration_accepted = True
        else:
            reason_codes.append("invalid_domain_migration_event")

    drift = bool(reason_codes)
    if not drift:
        status = "ready_for_living_update"
    elif migration_accepted:
        status = "ready_after_domain_migration"
    else:
        status = "blocked_pending_domain_migration"
    evidence = affected_evidence
    if evidence is None:
        evidence = previous_domain_snapshot.get("affected_evidence", [])
    claims = affected_claims
    if claims is None:
        claims = previous_domain_snapshot.get("affected_claims", [])
    return {
        "status": status,
        "migration_required": drift and not migration_accepted,
        "reason_codes": sorted(set(reason_codes)),
        "previous_domain_pack_hash": previous_pack_hash,
        "current_domain_pack_hash": current_pack_hash,
        "previous_terminology_releases": previous_terms,
        "current_terminology_releases": current_terms,
        "affected_evidence": sorted(set(evidence)),
        "affected_claims": sorted(set(claims)),
        "migration_event": copy.deepcopy(migration_event) if migration_accepted else None,
    }


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
