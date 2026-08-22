"""Apply a frozen conservative evaluation rubric and compile support-bounded claims."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .claim_compiler import ClaimCompileError, compile_claim
from .joint_lifecycle_runner import AtomicStageBudgetMeter, JointLifecycleRunError
from .schema_guard import SchemaValidationError, validate_document
from .state_store import atomic_write_json


LEVELS = ["very_low", "low", "moderate", "high"]


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _bound(binding: dict[str, Any], label: str) -> Path:
    path = Path(str(binding.get("path") or "")).resolve(strict=True)
    if _sha(path) != binding.get("sha256"):
        raise JointLifecycleRunError(f"{label} hash drift")
    return path


def _previous(request: dict[str, Any]) -> tuple[dict[str, Any], Path]:
    manifest = Path(str(request.get("previous_output_manifest_path") or "")).resolve(strict=True)
    if _sha(manifest) != request.get("previous_output_manifest_sha256"):
        raise JointLifecycleRunError("synthesis output manifest hash drift")
    try:
        value = json.loads(manifest.read_text(encoding="utf-8"))["stage_output"]
        rows = [item for item in value["artifacts"] if item["artifact_id"] == value["state_artifact_id"]]
        if len(rows) != 1:
            raise KeyError("synthesis state")
        path = Path(rows[0]["path"]).resolve(strict=True)
        if _sha(path) != rows[0]["sha256"]:
            raise JointLifecycleRunError("synthesis state hash drift")
        state = json.loads(path.read_text(encoding="utf-8"))
        validate_document(state, "joint_synthesis_stage_state")
    except (OSError, json.JSONDecodeError, KeyError, SchemaValidationError) as exc:
        raise JointLifecycleRunError(f"invalid synthesis state: {exc}") from exc
    return state, path


def _downgrade(initial: str, domains: list[dict[str, Any]]) -> tuple[str, int]:
    index = LEVELS.index(initial)
    total = min(index, sum(int(item["levels"]) for item in domains))
    return LEVELS[index - total], total


def certainty_claims_stage_adapter(request: dict[str, Any], meter: AtomicStageBudgetMeter) -> dict[str, Any]:
    if request.get("stage_id") != "certainty_interpretation" or request.get("ordinal") != 7:
        raise JointLifecycleRunError("certainty adapter can execute only canonical stage seven")
    if request.get("published_reference_accessed") is not False:
        raise JointLifecycleRunError("certainty adapter refuses published-reference access")
    config = request.get("config")
    try:
        validate_document(config, "joint_certainty_stage_config")
    except SchemaValidationError as exc:
        raise JointLifecycleRunError(str(exc)) from exc
    synthesis, synthesis_path = _previous(request)
    appraisal_path = _bound(synthesis["appraisal_state_artifact"], "appraisal state")
    appraisal = json.loads(appraisal_path.read_text(encoding="utf-8"))
    lineage_path = _bound(appraisal["lineage_state_artifact"], "lineage state")
    lineage = json.loads(lineage_path.read_text(encoding="utf-8"))
    adverse = any(
        dossier.get("judge_recommendation", {}).get("judgment") != "low_concern_candidate"
        for dossier in appraisal["appraisal_dossiers"]
    )
    missing = bool(appraisal["missing_evidence_matrix"]["judge_recommendation"]["abstained"])
    summary = synthesis["synthesis_result"].get("summary", {})
    i2 = summary.get("I2")
    inconsistency = isinstance(i2, (int, float)) and i2 > config["inconsistency_i2_threshold"]
    ci_lower, ci_upper = summary.get("ci_lower"), summary.get("ci_upper")
    threshold = config["decision_threshold"]
    imprecise = not (
        isinstance(ci_lower, (int, float)) and isinstance(ci_upper, (int, float))
    ) or ci_lower <= threshold <= ci_upper
    indirect = any(
        not all(str(estimand.get(key) or "").strip() for key in ("population", "contrast", "outcome", "time_window"))
        for estimand in lineage["estimands"]
    )
    domains = [
        {"domain": "risk_of_bias", "levels": 1 if adverse else 0, "basis": "conservative result-level appraisal dossiers"},
        {"domain": "inconsistency", "levels": 1 if inconsistency else 0, "basis": "frozen I2 threshold; unavailable for non-pooled synthesis"},
        {"domain": "indirectness", "levels": 1 if indirect else 0, "basis": "estimand completeness gate"},
        {"domain": "imprecision", "levels": 1 if imprecise else 0, "basis": "decision-threshold interval geometry or absence of a pooled interval"},
        {"domain": "missing_evidence", "levels": 1 if missing else 0, "basis": "observed availability audit with unobserved-study opposition"},
    ]
    judgment, total = _downgrade(config["initial_certainty"], domains)
    certainty = {
        "framework": config["framework_label"], "judgment": judgment,
        "initial_certainty": config["initial_certainty"], "downgrade_levels": total,
        "domains": domains, "evaluation_only": True,
        "production_finalization_requires_human_responsibility": True,
    }
    first_estimand = lineage["estimands"][0]
    scope = {
        "synthesis_id": "synthesis-01", "population": first_estimand["population"],
        "contrast": first_estimand["contrast"], "outcome": first_estimand["outcome"],
        "time_window": first_estimand["time_window"],
        "applicability_limits": [
            "Only lawfully retrieved, pre-cutoff, source-span-verified evidence was considered.",
            "Production scientific responsibility remains pending.",
        ],
    }
    numeric_support: list[dict[str, float]] = []
    if synthesis["executed_route_id"] == "pairwise_random_effects":
        estimate = float(summary["estimate"])
        lower = float(summary["ci_lower"])
        upper = float(summary["ci_upper"])
        numeric_support = [{"value": value, "tolerance": 1e-9} for value in (estimate, lower, upper, 0.95)]
        text = f"The verified synthesis estimated {estimate:.12g} (95% CI {lower:.12g} to {upper:.12g}) for the frozen estimand."
    else:
        text = "Verified source-bound results were observed, but quantitative pooling was not performed under the frozen compatibility and evidence-completeness rules."
    candidate = {
        "claim_id": f"claim-{request['case_id']}-{request['arm_id']}-{request['seed']}",
        "claim_type": "observation", "text": text, "scope": scope,
        "certainty": {"framework": config["framework_label"], "judgment": judgment, "dossier_id": None},
        "evidence_node_ids": [item["result_id"] for item in lineage["results"]],
        "assertion_ids": [], "analysis_output_ids": [synthesis_path.name],
        "counterevidence_node_ids": [item["dossier_id"] for item in appraisal["appraisal_dossiers"] if item.get("judge_recommendation", {}).get("abstained")],
        "numeric_support": numeric_support, "allowed_verbs": ["estimated", "observed"],
        "evidence_design": "association", "scope_verified": True,
        "support_verifier_id": "deterministic-lineage-numeric-scope-verifier-v1",
        "created_by": {"type": "tool", "id": "joint-certainty-claim-compiler", "version": "1.0"},
    }
    try:
        claim = compile_claim(candidate, created_at_utc=request["created_at_utc"])
    except ClaimCompileError as exc:
        raise JointLifecycleRunError(f"claim compilation failed: {exc}") from exc
    state = {
        "schema_version": "1.0", "stage_id": "certainty_interpretation", "case_id": request["case_id"],
        "arm_id": request["arm_id"], "seed": request["seed"],
        "synthesis_state_artifact": {"path": str(synthesis_path), "sha256": _sha(synthesis_path)},
        "certainty_assessment": certainty, "claims": [claim],
        "production_human_responsibility_pending": True, "published_reference_accessed": False,
    }
    output_dir = Path(request["stage_output_dir"]).resolve(strict=True)
    state_path = output_dir / "certainty-claims-state.json"
    atomic_write_json(state_path, state, "joint_certainty_stage_state")
    artifacts = [{"artifact_id": "certainty_claims_state", "path": str(state_path), "sha256": _sha(state_path), "media_type": "application/json", "role": "stage_state"}]
    output = {
        "schema_version": "1.0", "stage_id": "certainty_interpretation", "status": "completed",
        "state_artifact_id": "certainty_claims_state", "artifacts": artifacts,
        "scientific_checks": [{"check_id": "certainty_and_claims_complete", "status": "passed", "evidence_artifact_ids": ["certainty_claims_state"]}],
        "terminal_reason": None,
    }
    validate_document(output, "joint_lifecycle_stage_output")
    return output
