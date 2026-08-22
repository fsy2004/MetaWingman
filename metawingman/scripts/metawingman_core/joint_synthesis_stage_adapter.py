"""Freeze verified result inputs, recompute effects, and execute or abstain from pooling."""

from __future__ import annotations

import csv
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any, Callable

from .effect_recalculator import EffectCalculationError, calculate_effect
from .joint_lifecycle_runner import AtomicStageBudgetMeter, JointLifecycleRunError
from .schema_guard import SchemaValidationError, validate_document
from .state_store import atomic_write_json


AnalysisExecutor = Callable[[Path, Path, dict[str, Any], Path, Path], dict[str, Any]]


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
    manifest_path = Path(str(request.get("previous_output_manifest_path") or "")).resolve(strict=True)
    if _sha(manifest_path) != request.get("previous_output_manifest_sha256"):
        raise JointLifecycleRunError("appraisal output manifest hash drift")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        output = manifest["stage_output"]
        matches = [item for item in output["artifacts"] if item["artifact_id"] == output["state_artifact_id"]]
        if len(matches) != 1:
            raise KeyError("appraisal state")
        state_path = Path(matches[0]["path"]).resolve(strict=True)
        if _sha(state_path) != matches[0]["sha256"]:
            raise JointLifecycleRunError("appraisal state artifact hash drift")
        state = json.loads(state_path.read_text(encoding="utf-8"))
        validate_document(state, "joint_appraisal_stage_state")
    except (OSError, json.JSONDecodeError, KeyError, SchemaValidationError) as exc:
        raise JointLifecycleRunError(f"invalid appraisal state: {exc}") from exc
    return state, state_path


def _default_analysis_executor(
    csv_path: Path, output_dir: Path, config: dict[str, Any], r_adapter: Path, toolkit_root: Path,
) -> dict[str, Any]:
    analysis_dir = output_dir / "r-analysis"
    command = [
        "Rscript", str(r_adapter), "--input", str(csv_path), "--outdir", str(analysis_dir),
        "--method", config["method"], "--knha", "true" if config["knha"] else "false",
    ]
    completed = subprocess.run(
        command, cwd=toolkit_root, capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=3600, check=False,
    )
    if completed.returncode != 0:
        raise JointLifecycleRunError(
            "verified-effects R analysis failed: " + completed.stderr[-2000:]
        )
    summary_path = analysis_dir / "synthesis-summary.csv"
    if not summary_path.is_file():
        raise JointLifecycleRunError("R analysis did not produce synthesis-summary.csv")
    rows = list(csv.DictReader(summary_path.open(encoding="utf-8")))
    if len(rows) != 1:
        raise JointLifecycleRunError("R analysis summary must contain exactly one row")
    numeric = {key: float(value) for key, value in rows[0].items() if key not in {"method", "test"} and value not in {"", "NA"}}
    return {
        "status": "pooled", "summary": numeric | {"method": rows[0]["method"], "test": rows[0]["test"]},
        "artifact": {"path": str(summary_path), "sha256": _sha(summary_path)},
        "stdout_sha256": hashlib.sha256(completed.stdout.encode()).hexdigest(),
        "stderr_sha256": hashlib.sha256(completed.stderr.encode()).hexdigest(),
    }


def analysis_freeze_synthesis_stage_adapter(
    request: dict[str, Any], meter: AtomicStageBudgetMeter, *, analysis_executor: AnalysisExecutor = _default_analysis_executor,
) -> dict[str, Any]:
    if request.get("stage_id") != "freeze_synthesis" or request.get("ordinal") != 6:
        raise JointLifecycleRunError("synthesis adapter can execute only canonical stage six")
    if request.get("published_reference_accessed") is not False:
        raise JointLifecycleRunError("synthesis adapter refuses published-reference access")
    config = request.get("config")
    try:
        validate_document(config, "joint_synthesis_stage_config")
    except SchemaValidationError as exc:
        raise JointLifecycleRunError(str(exc)) from exc
    root = Path(request["repository_root"]).resolve(strict=True)
    appraisal, appraisal_path = _previous(request)
    lineage_path = _bound(root, appraisal["lineage_state_artifact"], "lineage state")
    protocol_path = _bound(root, appraisal["protocol_artifact"], "protocol")
    r_adapter = _bound(root, config["r_adapter"], "verified-effects R adapter")
    toolkit_manifest = _bound(root, config["toolkit_manifest"], "toolkit manifest")
    lineage = json.loads(lineage_path.read_text(encoding="utf-8"))
    candidates_by_result: dict[str, list[dict[str, Any]]] = {}
    for candidate in lineage["extraction_candidates"]:
        if candidate.get("status") == "accepted" and candidate.get("verification", {}).get("status") == "passed":
            candidates_by_result.setdefault(str(candidate["result_id"]), []).append(candidate)
    effects: list[dict[str, Any]] = []
    calculation_failures: list[dict[str, str]] = []
    for result in lineage["results"]:
        rows = candidates_by_result.get(result["result_id"], [])
        if not rows:
            continue
        try:
            effects.append(calculate_effect(
                rows, effect_id=f"effect-{result['result_id']}", result_id=result["result_id"],
                measure=config["effect_measure"], direction=config["direction"],
                created_at_utc=request["created_at_utc"],
            ))
        except EffectCalculationError as exc:
            calculation_failures.append({"result_id": result["result_id"], "reason": str(exc)})
    analysis_input = {
        "schema_version": "1.0", "case_id": request["case_id"], "arm_id": request["arm_id"],
        "seed": request["seed"], "requested_route_id": config["route_id"],
        "effect_measure": config["effect_measure"], "effect_estimates": effects,
        "verified_result_ids": [item["result_id"] for item in lineage["results"]],
        "calculation_failures": calculation_failures,
        "appraisal_dossier_ids": [item["dossier_id"] for item in appraisal["appraisal_dossiers"]],
        "missing_evidence_matrix_id": appraisal["missing_evidence_matrix"]["matrix_id"],
    }
    output_dir = Path(request["stage_output_dir"]).resolve(strict=True)
    input_path = output_dir / "analysis-input-frozen.json"
    atomic_write_json(input_path, analysis_input)
    frozen_hash = _sha(input_path)
    csv_path = output_dir / "verified-effects.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["study_id", "result_id", "yi", "vi"])
        writer.writeheader()
        for effect in effects:
            result = next(item for item in lineage["results"] if item["result_id"] == effect["result_id"])
            writer.writerow({"study_id": result["study_id"], "result_id": effect["result_id"], "yi": effect["estimate"], "vi": effect["variance"]})
    if _sha(input_path) != frozen_hash:
        raise JointLifecycleRunError("analysis input changed before synthesis execution")
    pool_allowed = (
        config["route_id"] == "pairwise_random_effects"
        and len(effects) >= config["minimum_effects_for_pooling"]
        and not appraisal["missing_evidence_matrix"]["judge_recommendation"]["abstained"]
    )
    if pool_allowed:
        synthesis_result = analysis_executor(csv_path, output_dir, config, r_adapter, root / "toolkit")
        executed_route = "pairwise_random_effects"
    else:
        executed_route = "swim_structured_synthesis" if lineage["results"] else "no_pooling"
        synthesis_result = {
            "status": "structured_without_pooling", "reason_codes": [
                "insufficient_verified_compatible_effects" if len(effects) < config["minimum_effects_for_pooling"] else "missing_evidence_uncertainty",
            ],
            "result_summaries": [{
                "result_id": result["result_id"], "study_id": result["study_id"],
                "estimand_id": result["estimand_id"],
                "verified_candidate_ids": [item["candidate_id"] for item in candidates_by_result.get(result["result_id"], [])],
            } for result in lineage["results"]],
            "pooled_effect": None,
        }
    state = {
        "schema_version": "1.0", "stage_id": "freeze_synthesis", "case_id": request["case_id"],
        "arm_id": request["arm_id"], "seed": request["seed"],
        "appraisal_state_artifact": {"path": str(appraisal_path), "sha256": _sha(appraisal_path)},
        "protocol_artifact": {"path": str(protocol_path), "sha256": _sha(protocol_path)},
        "analysis_input_artifact": {"path": str(input_path), "sha256": frozen_hash},
        "analysis_input_frozen_before_execution": True, "requested_route_id": config["route_id"],
        "executed_route_id": executed_route, "effect_estimates": effects, "synthesis_result": synthesis_result,
        "software_bindings": {"r_adapter_sha256": _sha(r_adapter), "toolkit_manifest_sha256": _sha(toolkit_manifest), "method": config["method"], "knha": config["knha"]},
        "published_reference_accessed": False,
    }
    state_path = output_dir / "synthesis-state.json"
    atomic_write_json(state_path, state, "joint_synthesis_stage_state")
    artifacts = [
        {"artifact_id": "synthesis_state", "path": str(state_path), "sha256": _sha(state_path), "media_type": "application/json", "role": "stage_state"},
        {"artifact_id": "analysis_input", "path": str(input_path), "sha256": frozen_hash, "media_type": "application/json", "role": "frozen_analysis_input"},
        {"artifact_id": "verified_effects", "path": str(csv_path), "sha256": _sha(csv_path), "media_type": "text/csv", "role": "analysis_table"},
    ]
    output = {
        "schema_version": "1.0", "stage_id": "freeze_synthesis", "status": "completed",
        "state_artifact_id": "synthesis_state", "artifacts": artifacts,
        "scientific_checks": [{"check_id": "analysis_freeze_and_synthesis_complete", "status": "passed", "evidence_artifact_ids": [item["artifact_id"] for item in artifacts]}],
        "terminal_reason": None,
    }
    validate_document(output, "joint_lifecycle_stage_output")
    return output
