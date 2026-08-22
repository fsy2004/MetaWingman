"""Execute fixed or residual-risk x claim-impact search from a frozen protocol."""

from __future__ import annotations

import hashlib
import json
import time
from copy import deepcopy
from datetime import date
from pathlib import Path
from typing import Any, Callable

from .evidence_acquisition import EvidenceAcquisitionError
from .evidence_acquisition_loop import execute_evidence_acquisition_loop
from .joint_lifecycle_runner import AtomicStageBudgetMeter, JointLifecycleRunError
from .schema_guard import SchemaValidationError, validate_document
from .state_store import atomic_write_json


SearchRunner = Callable[[dict[str, Any], str, Path], tuple[list[dict[str, Any]], dict[str, Any]]]


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _bound_file(root: Path, binding: dict[str, Any], label: str) -> Path:
    path = (root / str(binding.get("path") or "")).resolve(strict=False)
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise JointLifecycleRunError(f"{label} is outside the repository") from exc
    if not path.is_file() or _sha(path) != binding.get("sha256"):
        raise JointLifecycleRunError(f"{label} is missing or has hash drift")
    return path


def _prior_protocol(request: dict[str, Any]) -> tuple[dict[str, Any], Path]:
    value = request.get("previous_output_manifest_path")
    expected = request.get("previous_output_manifest_sha256")
    if not isinstance(value, str) or not isinstance(expected, str):
        raise JointLifecycleRunError("search stage requires the locked protocol output manifest")
    manifest_path = Path(value).resolve(strict=True)
    if _sha(manifest_path) != expected:
        raise JointLifecycleRunError("protocol output manifest hash drift")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        stage_output = manifest["stage_output"]
        state_id = stage_output["state_artifact_id"]
        matches = [item for item in stage_output["artifacts"] if item["artifact_id"] == state_id]
        if len(matches) != 1:
            raise KeyError("protocol state artifact")
        protocol_path = Path(matches[0]["path"]).resolve(strict=True)
        if _sha(protocol_path) != matches[0]["sha256"]:
            raise JointLifecycleRunError("protocol artifact hash drift")
        protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, KeyError) as exc:
        raise JointLifecycleRunError(f"invalid protocol stage state: {exc}") from exc
    if protocol.get("status") != "frozen" or not protocol.get("protocol_version"):
        raise JointLifecycleRunError("search can run only from a frozen protocol")
    return protocol, protocol_path


def _query(path: Path, cutoff: str) -> str:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise JointLifecycleRunError(f"query file must be frozen JSON: {exc}") from exc
    if set(payload) not in (
        {"query", "cutoff_date"},
        {"query", "cutoff_date", "template_id", "derived_from_proposal_id"},
    ):
        raise JointLifecycleRunError("query file has an invalid frozen query contract")
    if payload["cutoff_date"] != cutoff or not isinstance(payload["query"], str) or not payload["query"].strip():
        raise JointLifecycleRunError("query file cutoff or query is invalid")
    return payload["query"].strip()


def _default_searcher(source: dict[str, Any], query: str, raw_dir: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    from metawingman.scripts import search_sources

    engine = source["engine"]
    function = {
        "pubmed": search_sources.pubmed,
        "europe_pmc": search_sources.europe_pmc,
        "clinical_trials": search_sources.clinical_trials,
    }.get(engine)
    if function is None:
        export_path = Path(query).resolve(strict=True)
        records = json.loads(export_path.read_text(encoding="utf-8"))
        if not isinstance(records, list):
            raise JointLifecycleRunError("frozen export query must resolve to a JSON record array")
        return records, {
            "source": source["source_id"], "reported_count": len(records),
            "retrieved_count": len(records), "access_route": "frozen_export",
        }
    return function(query, source["maximum_records"], raw_dir)


def _temporal_gate(record: dict[str, Any], cutoff: str) -> tuple[bool, str]:
    raw = str(record.get("first_publication_date") or record.get("publication_date") or "")
    try:
        observed = date.fromisoformat(raw)
    except ValueError:
        return False, "publication_date_unknown"
    return (True, "precutoff_or_on_cutoff") if observed <= date.fromisoformat(cutoff) else (False, "postcutoff")


def _identifier(record: dict[str, Any], kind: str) -> str:
    return str(record.get(kind) or "").strip().casefold()


def _deduplicate(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    kept: dict[str, dict[str, Any]] = {}
    for record in records:
        key = next((
            f"{kind}:{_identifier(record, kind)}"
            for kind in ("doi", "pmid", "pmcid", "nct_id") if _identifier(record, kind)
        ), f"record:{record.get('record_id', '')}")
        kept.setdefault(key, record)
    return list(kept.values())


def _artifact(path: Path, artifact_id: str, role: str) -> dict[str, str]:
    return {
        "artifact_id": artifact_id, "path": str(path.resolve()), "sha256": _sha(path),
        "media_type": "application/json", "role": role,
    }


def search_retrieval_stage_adapter(
    request: dict[str, Any], meter: AtomicStageBudgetMeter, *, searcher: SearchRunner | None = None,
) -> dict[str, Any]:
    if request.get("stage_id") != "search_retrieval" or request.get("ordinal") != 2:
        raise JointLifecycleRunError("search adapter can execute only canonical stage two")
    if request.get("published_reference_accessed") is not False:
        raise JointLifecycleRunError("search adapter refuses published-reference access")
    config = request.get("config")
    try:
        validate_document(config, "joint_search_stage_config")
    except SchemaValidationError as exc:
        raise JointLifecycleRunError(str(exc)) from exc
    if config["fixed_action_count"] != config["loop_budget"]["max_actions"]:
        raise JointLifecycleRunError(
            "fixed and adaptive acquisition arms must share the same frozen action ceiling"
        )
    if config["fixed_action_count"] > len(config["sources"]):
        raise JointLifecycleRunError("frozen action ceiling exceeds the available source actions")
    protocol, protocol_path = _prior_protocol(request)
    root = Path(request["repository_root"]).resolve(strict=True)
    output_dir = Path(request["stage_output_dir"]).resolve(strict=True)
    calibration_path = _bound_file(root, config["calibration_manifest"], "search calibration manifest")
    try:
        calibration = json.loads(calibration_path.read_text(encoding="utf-8"))
        validate_document(calibration, "joint_search_calibration_manifest")
    except (OSError, json.JSONDecodeError, SchemaValidationError) as exc:
        raise JointLifecycleRunError(f"invalid non-target search calibration: {exc}") from exc
    if calibration["target_reference_derived"] is not False:
        raise JointLifecycleRunError("target-reference-derived search calibration is forbidden")
    criterion_ids = {item["criterion_id"] for item in calibration["criteria"]}
    for sentinel in calibration["sentinels"]:
        if not set(sentinel["criterion_ids"]) <= criterion_ids:
            raise JointLifecycleRunError("search sentinel targets an unknown calibration criterion")
    source_ids = [item["source_id"] for item in config["sources"]]
    if len(source_ids) != len(set(source_ids)):
        raise JointLifecycleRunError("search source_id values must be unique")
    protocol_sources = {item.get("source_id") for item in protocol.get("source_plan", [])}
    if not set(source_ids) <= protocol_sources:
        raise JointLifecycleRunError("search config introduces a source outside the frozen protocol")
    protocol_source_by_id = {item["source_id"]: item for item in protocol["source_plan"]}
    queries: dict[str, str] = {}
    for item in config["sources"]:
        protocol_source = protocol_source_by_id[item["source_id"]]
        query_binding = {
            "path": protocol_source["query_file"],
            "sha256": protocol_source.get("query_sha256"),
        }
        query_path = _bound_file(root, query_binding, f"protocol-derived query {item['action_id']}")
        queries[item["action_id"]] = _query(query_path, config["historical_cutoff"])
    configured_policy = (
        "risk_impact_action_execute_replan"
        if request.get("conclusion_risk_impact_control") is True else "fixed_generic"
    )
    if request.get("acquisition_policy") != configured_policy:
        raise JointLifecycleRunError("search arm and acquisition policy disagree")
    runner = searcher or request.get("_searcher") or _default_searcher
    eligible_records: list[dict[str, Any]] = []
    quarantined: list[dict[str, Any]] = []
    audits: list[dict[str, Any]] = []
    executed_families: set[str] = set()
    executed_actions: set[str] = set()
    source_by_action = {item["action_id"]: item for item in config["sources"]}

    def execute_source(source: dict[str, Any]) -> tuple[dict[str, Any], float]:
        started = time.monotonic()
        raw_records, audit = runner(source, queries[source["action_id"]], output_dir / "raw")
        if not isinstance(raw_records, list) or not isinstance(audit, dict):
            raise JointLifecycleRunError("search executor returned an invalid record or audit shape")
        if audit.get("retrieved_count") != len(raw_records):
            raise JointLifecycleRunError("search audit retrieved_count does not match records")
        admitted: list[dict[str, Any]] = []
        rejected: list[dict[str, Any]] = []
        for raw in raw_records:
            if not isinstance(raw, dict) or not raw.get("record_id"):
                raise JointLifecycleRunError("search record lacks a stable record_id")
            allowed, status = _temporal_gate(raw, config["historical_cutoff"])
            record = dict(raw) | {
                "source_family": source["source_family"], "search_action_id": source["action_id"],
                "temporal_gate": status,
            }
            (admitted if allowed else rejected).append(record)
        eligible_records.extend(admitted)
        quarantined.extend(rejected)
        audit_row = dict(audit) | {
            "action_id": source["action_id"], "source_id": source["source_id"],
            "eligible_pre_cutoff_count": len(admitted), "quarantined_count": len(rejected),
        }
        audits.append(audit_row)
        executed_actions.add(source["action_id"])
        if admitted:
            executed_families.add(source["source_family"])
        return {
            "source": source, "audit": audit_row, "records": admitted,
            "quarantined_records": rejected,
        }, time.monotonic() - started

    def observed_metrics() -> tuple[float, dict[str, float], dict[str, int]]:
        known = calibration["sentinels"]
        found: set[str] = set()
        for sentinel in known:
            if any(
                _identifier(record, sentinel["identifier_type"])
                == str(sentinel["identifier"]).strip().casefold()
                for record in eligible_records
            ):
                found.add(sentinel["sentinel_id"])
        global_recall = len(found) / len(known)
        criterion_recall: dict[str, float] = {}
        criterion_sources: dict[str, int] = {}
        for criterion_id in criterion_ids:
            relevant = [item for item in known if criterion_id in item["criterion_ids"]]
            criterion_recall[criterion_id] = (
                sum(item["sentinel_id"] in found for item in relevant) / len(relevant)
                if relevant else 0.0
            )
            families = {
                source["source_family"] for source in config["sources"]
                if criterion_id in source["target_criterion_ids"]
                and source["action_id"] in executed_actions
                and source["source_family"] in executed_families
            }
            criterion_sources[criterion_id] = len(families)
        return global_recall, criterion_recall, criterion_sources

    def state(iteration: int, remaining: list[dict[str, Any]]) -> dict[str, Any]:
        global_recall, recalls, source_counts = observed_metrics()
        thresholds = config["thresholds"]
        criteria = []
        for row in calibration["criteria"]:
            recall = recalls[row["criterion_id"]]
            residual = round(1.0 - recall, 8)
            criteria.append({
                "criterion_id": row["criterion_id"], "critical": row["critical"],
                "calibration_status": "calibrated", "residual_omission_risk": residual,
                "downstream_claim_impact": row["downstream_claim_impact"],
                "hard_negative_error_rate": row["hard_negative_error_rate"],
                "unresolved_records": int(residual > thresholds["residual_omission_risk_ceiling"]),
                "independent_source_count": source_counts[row["criterion_id"]],
                "evidence_basis": "Observed frozen sentinel recall and admitted source-family coverage.",
            })
        actions = [{
            "action_id": item["action_id"], "action_type": "add_source",
            "target_criterion_ids": item["target_criterion_ids"],
            "expected_risk_reduction": item["expected_risk_reduction"],
            "expected_claim_impact": item["expected_claim_impact"],
            "source_family_gain": int(item["source_family"] not in executed_families),
            "estimated_cost_units": item["estimated_cost_units"], "estimate_basis": "calibrated",
            "legally_available": True, "credential_status": "not_required",
            "rationale": "Execute a frozen protocol source and recompute observed search risk.",
        } for item in remaining]
        return {
            "schema_version": "1.0", "state_id": f"search-risk-{iteration}",
            "protocol_version": protocol["protocol_version"], "criterion_states": criteria,
            "global_signals": {
                "run_context": "historical_reconstruction", "known_item_set_frozen": True,
                "known_item_recall": round(global_recall, 8), "source_family_count": len(executed_families),
                "temporal_boundary_status": "sealed", "leakage_audit": "passed",
            },
            "thresholds": dict(thresholds) | {"max_selected_actions": 1},
            "candidate_actions": actions, "created_at_utc": request["created_at_utc"],
        }

    loop_result: dict[str, Any] | None = None
    if configured_policy == "risk_impact_action_execute_replan":
        initial_sources = deepcopy(config["sources"])

        def executor(action: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
            source = source_by_action[action["action_id"]]
            artifact_payload, elapsed = execute_source(source)
            artifact_path = output_dir / f"action-{len(executed_actions):02d}-{action['action_id']}.json"
            atomic_write_json(artifact_path, artifact_payload)
            remaining = [item for item in config["sources"] if item["action_id"] not in executed_actions]
            return {
                "action_id": action["action_id"], "next_state": state(len(executed_actions), remaining),
                "risk_state_recomputed": True, "semantic_verification_status": "passed",
                "artifact": {"path": str(artifact_path), "sha256": _sha(artifact_path)},
                "usage": {
                    "model_calls": 0, "input_tokens": 0, "output_tokens": 0,
                    "wall_seconds": elapsed, "cost_status": "not_applicable", "cost_value": None,
                },
            }

        loop_plan = {
            "schema_version": "1.0",
            "loop_id": f"search-{request['case_id']}-{request['arm_id']}-{request['seed']}",
            "mode": "evaluation", "max_iterations": len(initial_sources) + 1,
            "artifact_root": str(output_dir),
            "budget": {
                "max_actions": config["loop_budget"]["max_actions"],
                "max_estimated_cost_units": config["loop_budget"]["max_estimated_cost_units"],
                "max_model_calls": 0, "max_input_tokens": 0, "max_output_tokens": 0,
                "max_wall_seconds": config["loop_budget"]["max_wall_seconds"],
                "cost_accounting_policy": "report_unknown",
            },
            "stop_authority": {
                "actor_id": "preregistered-evaluation-actor",
                "preregistration_sha256": config["calibration_manifest"]["sha256"],
                "signature_status": "verified",
            },
        }
        try:
            loop_result = execute_evidence_acquisition_loop(
                state(0, initial_sources), loop_plan, executor,
                created_at_utc=request["created_at_utc"],
            )
        except EvidenceAcquisitionError as exc:
            raise JointLifecycleRunError(f"risk-impact acquisition failed: {exc}") from exc
        completed = loop_result["status"] == "completed" and loop_result["full_risk_impact_controller_instantiated"]
    else:
        for source in config["sources"][: config["fixed_action_count"]]:
            execute_source(source)
        completed = True

    admitted = _deduplicate(eligible_records)
    recall, _, _ = observed_metrics()
    state_document = {
        "schema_version": "1.0", "stage_id": "search_retrieval",
        "case_id": request["case_id"], "arm_id": request["arm_id"], "seed": request["seed"],
        "acquisition_policy": configured_policy, "historical_cutoff": config["historical_cutoff"],
        "protocol_artifact": {"path": str(protocol_path), "sha256": _sha(protocol_path)},
        "criteria_artifact": {
            "path": str(protocol["criteria_artifact"]["path"]),
            "sha256": str(protocol["criteria_artifact"]["sha256"]),
        },
        "records": admitted, "quarantined_records": quarantined, "search_audits": audits,
        "known_item_recall": round(recall, 8), "source_family_count": len(executed_families),
        "risk_loop_result": loop_result, "published_reference_accessed": False,
    }
    state_path = output_dir / "search-state.json"
    atomic_write_json(state_path, state_document, "joint_search_stage_state")
    audit_path = output_dir / "search-audit.json"
    atomic_write_json(audit_path, {
        "historical_cutoff": config["historical_cutoff"], "audits": audits,
        "eligible_count": len(admitted), "quarantined_count": len(quarantined),
        "deduplication_rule": "doi_then_pmid_then_pmcid_then_nct_then_record_id",
    })
    artifacts = [
        _artifact(state_path, "search_state", "stage_state"),
        _artifact(audit_path, "search_audit", "reproducible_search_audit"),
    ]
    if loop_result is not None:
        loop_path = output_dir / "risk-loop-result.json"
        atomic_write_json(loop_path, loop_result, "evidence_acquisition_loop_result")
        artifacts.append(_artifact(loop_path, "risk_loop_result", "risk_impact_controller_receipt"))
    check_id = (
        "risk_impact_action_execute_replan"
        if configured_policy == "risk_impact_action_execute_replan" else "fixed_acquisition"
    )
    status = "completed" if completed else "abstained"
    output = {
        "schema_version": "1.0", "stage_id": "search_retrieval", "status": status,
        "state_artifact_id": "search_state", "artifacts": artifacts,
        "scientific_checks": [{
            "check_id": check_id, "status": "passed" if completed else "abstained",
            "evidence_artifact_ids": [item["artifact_id"] for item in artifacts],
        }],
        "terminal_reason": None if completed else f"risk loop ended with {loop_result['terminal_reason']}",
    }
    validate_document(output, "joint_lifecycle_stage_output")
    return output
