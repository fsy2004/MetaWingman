"""Run a post-cutoff update search and produce an immutable living-review delta."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Callable

from .joint_lifecycle_runner import AtomicStageBudgetMeter, JointLifecycleRunError
from .living_update import LivingUpdateError, build_snapshot, compare_snapshots
from .schema_guard import SchemaValidationError, validate_document
from .state_store import atomic_write_json, sha256_json


SearchRunner = Callable[[str, str, int, Path], tuple[list[dict[str, Any]], dict[str, Any]]]


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _bound(root: Path, binding: dict[str, Any], label: str) -> Path:
    raw = Path(str(binding.get("path") or ""))
    path = raw.resolve(strict=False) if raw.is_absolute() else (root / raw).resolve(strict=False)
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise JointLifecycleRunError(f"{label} is outside the repository") from exc
    if not path.is_file() or _sha(path) != binding.get("sha256"):
        raise JointLifecycleRunError(f"{label} is missing or has hash drift")
    return path


def _previous(request: dict[str, Any]) -> tuple[dict[str, Any], Path]:
    manifest = Path(str(request.get("previous_output_manifest_path") or "")).resolve(strict=True)
    if _sha(manifest) != request.get("previous_output_manifest_sha256"):
        raise JointLifecycleRunError("reporting output manifest hash drift")
    try:
        output = json.loads(manifest.read_text(encoding="utf-8"))["stage_output"]
        rows = [item for item in output["artifacts"] if item["artifact_id"] == output["state_artifact_id"]]
        if len(rows) != 1:
            raise KeyError("reporting state")
        path = Path(rows[0]["path"]).resolve(strict=True)
        if _sha(path) != rows[0]["sha256"]:
            raise JointLifecycleRunError("reporting state artifact hash drift")
        state = json.loads(path.read_text(encoding="utf-8"))
        validate_document(state, "joint_reporting_stage_state")
    except (OSError, json.JSONDecodeError, KeyError, SchemaValidationError) as exc:
        raise JointLifecycleRunError(f"invalid reporting state: {exc}") from exc
    return state, path


def _default_searcher(engine: str, query: str, maximum: int, raw_dir: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    from metawingman.scripts import search_sources
    function = {"pubmed": search_sources.pubmed, "europe_pmc": search_sources.europe_pmc}[engine]
    return function(query, maximum, raw_dir)


def _canonical(record: dict[str, Any]) -> str:
    for key in ("doi", "pmid", "pmcid", "nct_id", "record_id"):
        value = str(record.get(key) or "").strip().casefold()
        if value:
            return f"{key}:{value}"
    raise JointLifecycleRunError("living snapshot record has no canonical identifier")


def _snapshot_record(record: dict[str, Any]) -> dict[str, Any]:
    canonical = _canonical(record)
    return {
        "record_id": str(record["record_id"]), "canonical_id": canonical,
        "source_record_id": str(record.get("source_record_id") or record["record_id"]),
        "metadata_sha256": sha256_json(record), "status": "active", "version": None,
        "published_at": str(record.get("first_publication_date") or "") or None,
        "provenance_node": {"type": "record", "id": str(record["record_id"])},
    }


def _compile_update_query(
    payload: dict[str, Any], *, engine: str, historical_cutoff: str, start: str, end: str,
) -> str:
    if payload.get("cutoff_date") != historical_cutoff or not isinstance(payload.get("query"), str):
        raise JointLifecycleRunError("protocol-derived living query has a mismatched historical cutoff")
    query = payload["query"].strip()
    if engine == "pubmed" and payload.get("template_id") == "pubmed_pico_date_v1":
        pattern = re.compile(
            r'\s+AND\s+\("1900-01-01"\[Date - Publication\]\s*:\s*"\d{4}-\d{2}-\d{2}"\[Date - Publication\]\)\s*$'
        )
        concept_query, count = pattern.subn("", query)
        if count != 1:
            raise JointLifecycleRunError("PubMed protocol query lacks one canonical historical date window")
        return f'({concept_query}) AND ("{start}"[Date - Publication] : "{end}"[Date - Publication])'
    if engine == "europe_pmc" and payload.get("template_id") == "europe_pmc_pico_date_v1":
        pattern = re.compile(r"\s+AND\s+FIRST_PDATE:\[1900-01-01 TO \d{4}-\d{2}-\d{2}\]\s*$")
        concept_query, count = pattern.subn("", query)
        if count != 1:
            raise JointLifecycleRunError("Europe PMC protocol query lacks one canonical historical date window")
        return f"({concept_query}) AND FIRST_PDATE:[{start} TO {end}]"
    raise JointLifecycleRunError("living engine does not match the frozen protocol query template")


def living_update_stage_adapter(
    request: dict[str, Any], meter: AtomicStageBudgetMeter, *, searcher: SearchRunner = _default_searcher,
) -> dict[str, Any]:
    if request.get("stage_id") != "living_update" or request.get("ordinal") != 9:
        raise JointLifecycleRunError("living adapter can execute only canonical stage nine")
    if request.get("published_reference_accessed") is not False:
        raise JointLifecycleRunError("living adapter refuses published-reference access")
    config = request.get("config")
    try:
        validate_document(config, "joint_living_stage_config")
    except SchemaValidationError as exc:
        raise JointLifecycleRunError(str(exc)) from exc
    root = Path(request["repository_root"]).resolve(strict=True)
    reporting, reporting_path = _previous(request)
    certainty_path = _bound(root, reporting["certainty_state_artifact"], "certainty state")
    certainty = json.loads(certainty_path.read_text(encoding="utf-8"))
    synthesis_path = _bound(root, certainty["synthesis_state_artifact"], "synthesis state")
    synthesis = json.loads(synthesis_path.read_text(encoding="utf-8"))
    appraisal_path = _bound(root, synthesis["appraisal_state_artifact"], "appraisal state")
    appraisal = json.loads(appraisal_path.read_text(encoding="utf-8"))
    lineage_path = _bound(root, appraisal["lineage_state_artifact"], "lineage state")
    lineage = json.loads(lineage_path.read_text(encoding="utf-8"))
    selection_path = _bound(root, lineage["selection_state_artifact"], "selection state")
    selection = json.loads(selection_path.read_text(encoding="utf-8"))
    search_path = _bound(root, selection["search_state_artifact"], "historical search state")
    historical = json.loads(search_path.read_text(encoding="utf-8"))
    protocol_path = _bound(root, historical["protocol_artifact"], "historical protocol")
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    start = date.fromisoformat(historical["historical_cutoff"]) + timedelta(days=1)
    end = date.fromisoformat(config["update_cutoff"])
    if end < start:
        raise JointLifecycleRunError("living update cutoff must be after the historical cutoff")
    source_rows = [row for row in protocol.get("source_plan", []) if row.get("source_id") == config["source_id"]]
    if len(source_rows) != 1:
        raise JointLifecycleRunError("living source must match exactly one frozen protocol source")
    source_row = source_rows[0]
    query_path = _bound(
        root, {"path": source_row.get("query_file"), "sha256": source_row.get("query_sha256")},
        "protocol-derived living query",
    )
    try:
        query_payload = json.loads(query_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise JointLifecycleRunError(f"invalid protocol-derived living query: {exc}") from exc
    query = _compile_update_query(
        query_payload, engine=config["engine"], historical_cutoff=historical["historical_cutoff"],
        start=start.isoformat(), end=end.isoformat(),
    )
    output_dir = Path(request["stage_output_dir"]).resolve(strict=True)
    new_records, audit = searcher(config["engine"], query, config["maximum_records"], output_dir / "raw")
    admitted: list[dict[str, Any]] = []
    quarantined: list[dict[str, Any]] = []
    for record in new_records:
        raw_date = str(record.get("first_publication_date") or "")
        try:
            observed = date.fromisoformat(raw_date)
        except ValueError:
            quarantined.append(dict(record) | {"living_gate": "publication_date_unknown"})
            continue
        if start <= observed <= end:
            admitted.append(record)
        else:
            quarantined.append(dict(record) | {"living_gate": "outside_update_interval"})
    query_hash = _sha(query_path)
    previous_records = [_snapshot_record(item) for item in historical["records"] if item.get("source") == config["source_id"] or item.get("source_family") == config["source_id"]]
    current_by_id = {item["canonical_id"]: item for item in previous_records}
    for item in admitted:
        current_by_id[_canonical(item)] = _snapshot_record(item)
    previous = build_snapshot({
        "snapshot_id": f"snapshot-{request['case_id']}-historical", "project_id": request["case_id"],
        "source_id": config["source_id"], "query_sha256": query_hash,
        "search_completed_at_utc": request["created_at_utc"], "source_data_timestamp": historical["historical_cutoff"],
        "records": previous_records,
    })
    current = build_snapshot({
        "snapshot_id": f"snapshot-{request['case_id']}-{config['update_cutoff']}", "project_id": request["case_id"],
        "source_id": config["source_id"], "query_sha256": query_hash,
        "search_completed_at_utc": request["created_at_utc"], "source_data_timestamp": config["update_cutoff"],
        "records": list(current_by_id.values()),
    })
    try:
        delta = compare_snapshots(previous, current, delta_id=f"delta-{request['case_id']}-{request['seed']}", created_at_utc=request["created_at_utc"])
    except LivingUpdateError as exc:
        raise JointLifecycleRunError(f"living delta failed: {exc}") from exc
    state = {
        "schema_version": "1.0", "stage_id": "living_update", "case_id": request["case_id"],
        "arm_id": request["arm_id"], "seed": request["seed"],
        "reporting_state_artifact": {"path": str(reporting_path), "sha256": _sha(reporting_path)},
        "previous_snapshot": previous, "current_snapshot": current, "delta": delta,
        "update_search_audit": dict(audit) | {
            "historical_protocol_query_sha256": query_hash,
            "update_query_sha256": hashlib.sha256(query.encode()).hexdigest(),
            "admitted_count": len(admitted), "quarantined_count": len(quarantined),
            "quarantined_records": quarantined,
        },
        "published_reference_accessed": False,
    }
    state_path = output_dir / "living-update-state.json"
    atomic_write_json(state_path, state, "joint_living_stage_state")
    artifacts = [{"artifact_id": "living_update_state", "path": str(state_path), "sha256": _sha(state_path), "media_type": "application/json", "role": "stage_state"}]
    output = {
        "schema_version": "1.0", "stage_id": "living_update", "status": "completed",
        "state_artifact_id": "living_update_state", "artifacts": artifacts,
        "scientific_checks": [{"check_id": "living_update_complete", "status": "passed", "evidence_artifact_ids": ["living_update_state"]}],
        "terminal_reason": None,
    }
    validate_document(output, "joint_lifecycle_stage_output")
    return output
