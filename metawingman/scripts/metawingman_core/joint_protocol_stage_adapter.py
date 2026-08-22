"""Compile an arm-selected topic into a frozen operational review protocol."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from .joint_lifecycle_runner import AtomicStageBudgetMeter, JointLifecycleRunError
from .protocol_compiler import compile_full_protocol, compile_protocol
from .schema_guard import SchemaValidationError, validate_document
from .state_store import atomic_write_json


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _identifier(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-.")
    return normalized or "value"


def _or_terms(values: list[str]) -> str:
    return "(" + " OR ".join(f'\"{value.replace(chr(34), "")}\"' for value in values) + ")"


def _compile_query(source: dict[str, Any], framework: dict[str, Any], cutoff: str) -> str:
    concepts = [
        _or_terms(framework["population"]),
        _or_terms(framework["intervention_or_exposure"]),
        _or_terms(framework["outcome"]),
        _or_terms(framework["study_design"]),
    ]
    base = " AND ".join(concepts)
    template = source["query_template_id"]
    if template == "pubmed_pico_date_v1":
        return f'({base}) AND (\"1900-01-01\"[Date - Publication] : \"{cutoff}\"[Date - Publication])'
    if template == "europe_pmc_pico_date_v1":
        return f"({base}) AND FIRST_PDATE:[1900-01-01 TO {cutoff}]"
    if template == "clinical_trials_pico_v1":
        return " AND ".join((_or_terms(framework["population"]), _or_terms(framework["intervention_or_exposure"])))
    raise JointLifecycleRunError("unsupported frozen query template")


def _bound_file(root: Path, binding: dict[str, Any], label: str) -> Path:
    path = (root / str(binding.get("path") or "")).resolve(strict=False)
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise JointLifecycleRunError(f"{label} is outside the repository") from exc
    if not path.is_file() or _sha(path) != binding.get("sha256"):
        raise JointLifecycleRunError(f"{label} is missing or has hash drift")
    return path


def _prior_state(request: dict[str, Any]) -> dict[str, Any]:
    value = request.get("previous_output_manifest_path")
    expected = request.get("previous_output_manifest_sha256")
    if not isinstance(value, str) or not isinstance(expected, str):
        raise JointLifecycleRunError("protocol stage requires the locked topic output manifest")
    path = Path(value).resolve(strict=True)
    if _sha(path) != expected:
        raise JointLifecycleRunError("topic output manifest hash drift")
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
        stage_output = manifest["stage_output"]
        state_id = stage_output["state_artifact_id"]
        bindings = [item for item in stage_output["artifacts"] if item["artifact_id"] == state_id]
        if len(bindings) != 1:
            raise KeyError("state artifact")
        state_path = Path(bindings[0]["path"]).resolve(strict=True)
        if _sha(state_path) != bindings[0]["sha256"]:
            raise JointLifecycleRunError("topic state artifact hash drift")
        state = json.loads(state_path.read_text(encoding="utf-8"))
        validate_document(state, "joint_topic_stage_state")
        return state
    except (OSError, json.JSONDecodeError, KeyError, SchemaValidationError) as exc:
        raise JointLifecycleRunError(f"invalid topic stage state: {exc}") from exc


def _criteria_candidate(framework: dict[str, Any]) -> dict[str, Any]:
    dimensions = (
        ("population", "population", framework["population"]),
        ("intervention", "intervention", framework["intervention_or_exposure"]),
        ("comparator", "comparator", framework["comparator"]),
        ("outcome", "outcome", framework["outcome"]),
        ("design", "design", framework["study_design"]),
    )
    criteria: list[dict[str, Any]] = []
    for index, (criterion_id, domain, values) in enumerate(dimensions, start=1):
        criteria.append({
            "criterion_id": f"{criterion_id}-{index:02d}",
            "domain": domain,
            "label": f"Eligible {criterion_id}: " + "; ".join(values),
            "predicate": {
                "field": criterion_id,
                "operator": "contains",
                "value": "; ".join(values),
                "unit": None,
                "normalization": "casefold_whitespace",
            },
            "missing_policy": "unclear",
            "full_text_required": criterion_id in {"outcome", "design"},
            "source_section": "locked AI-selected question framework",
        })
    return {"protocol_version": "1.0", "status": "frozen", "criteria": criteria}


def protocol_registration_stage_adapter(
    request: dict[str, Any], meter: AtomicStageBudgetMeter,
) -> dict[str, Any]:
    if request.get("stage_id") != "protocol_registration" or request.get("ordinal") != 1:
        raise JointLifecycleRunError("protocol adapter can execute only canonical stage one")
    if request.get("published_reference_accessed") is not False:
        raise JointLifecycleRunError("protocol adapter refuses published-reference access")
    config = request.get("config")
    try:
        validate_document(config, "joint_protocol_stage_config")
    except SchemaValidationError as exc:
        raise JointLifecycleRunError(str(exc)) from exc
    topic_state = _prior_state(request)
    if topic_state["status"] != "selected" or len(topic_state["selected_proposals"]) != 1:
        raise JointLifecycleRunError("one and only one selected topic is required for one review slot")
    selected = topic_state["selected_proposals"][0]
    framework = selected["question_framework"]
    if framework["synthesis_route"] not in config["allowed_synthesis_routes"]:
        raise JointLifecycleRunError("selected synthesis route is outside the frozen profile template")
    root = Path(request["repository_root"]).resolve(strict=True)
    output_dir = Path(request["stage_output_dir"]).resolve(strict=True)
    source_plan: list[dict[str, Any]] = []
    query_artifacts: list[dict[str, str]] = []
    for source in config["source_plan"]:
        query_path = output_dir / f"query-{source['source_id']}.json"
        atomic_write_json(query_path, {
            "query": _compile_query(source, framework, config["historical_cutoff"]),
            "cutoff_date": config["historical_cutoff"],
            "template_id": source["query_template_id"],
            "derived_from_proposal_id": selected["proposal_id"],
        })
        source_plan.append({
            key: source[key]
            for key in (
                "source_id", "source_type", "database", "platform", "access_route",
                "required", "coverage",
            )
        } | {"query_file": query_path.relative_to(root).as_posix(), "query_sha256": _sha(query_path)})
        query_artifacts.append({
            "artifact_id": _identifier(f"query_{source['source_id']}"), "path": str(query_path),
            "sha256": _sha(query_path), "media_type": "application/json", "role": "frozen_search_query",
        })

    criteria_result = compile_protocol(_criteria_candidate(framework))
    if not criteria_result.ready_to_freeze:
        raise JointLifecycleRunError("selected topic did not compile to operational eligibility criteria")
    criteria_path = output_dir / "protocol-criteria.json"
    atomic_write_json(criteria_path, criteria_result.document, "protocol_criteria")
    outcome_rows: list[dict[str, Any]] = []
    synthesis_rows: list[dict[str, Any]] = []
    population = "; ".join(framework["population"])
    contrast = (
        "; ".join(framework["intervention_or_exposure"])
        + " versus " + "; ".join(framework["comparator"])
    )
    for index, outcome in enumerate(framework["outcome"], start=1):
        outcome_id = f"outcome-{index:02d}"
        outcome_rows.append({
            "outcome_id": outcome_id,
            "label": outcome,
            "role": "primary" if index == 1 else "secondary",
            "construct": outcome,
            "preferred_measures": [config["effect_measure"]],
            "time_windows": [config["time_window"]],
            "result_selection_rule": (
                "Select the prespecified time window and effect measure; retain all eligible "
                "result lineage before choosing one synthesis input."
            ),
        })
        synthesis_rows.append({
            "synthesis_id": f"synthesis-{index:02d}",
            "review_question_ids": ["review-question-01"],
            "population": population,
            "contrast": contrast,
            "outcome_id": outcome_id,
            "time_window": config["time_window"],
            "effect_measure": config["effect_measure"],
            "estimand": {
                "estimand_id": f"estimand-{index:02d}",
                "target_population": population,
                "contrast": contrast,
                "outcome": outcome,
                "time_horizon": config["time_window"],
                "population_summary": config["population_summary"],
                "analysis_unit": config["analysis_unit"],
                "conditioning_set": [],
            },
            "decision_thresholds": [config["decision_threshold"]],
            "poolability_rule": config["poolability_rule"],
        })
    dimensions = [
        {"name": "population", "value": population, "operational_definition": "Match the locked population eligibility predicate."},
        {"name": "intervention", "value": "; ".join(framework["intervention_or_exposure"]), "operational_definition": "Match the locked intervention or exposure predicate."},
        {"name": "comparator", "value": "; ".join(framework["comparator"]), "operational_definition": "Match the locked comparator predicate."},
        {"name": "outcome", "value": "; ".join(framework["outcome"]), "operational_definition": "Map reported results to the frozen outcome hierarchy."},
    ]
    protocol = {
        "schema_version": "1.0",
        "protocol_id": _identifier(f"protocol-{request['case_id']}-{request['arm_id']}-{request['seed']}"),
        "protocol_version": "1.0",
        "status": "frozen",
        "profile_id": config["profile_id"],
        "decision_context": config["decision_context"],
        "review_questions": [{
            "question_id": "review-question-01",
            "objective": (
                "Evaluate " + "; ".join(framework["intervention_or_exposure"])
                + " for " + population + " on " + "; ".join(framework["outcome"])
                + " compared with " + "; ".join(framework["comparator"]) + "."
            ),
            "framework": "PICO",
            "dimensions": dimensions,
        }],
        "synthesis_questions": synthesis_rows,
        "outcome_hierarchy": outcome_rows,
        "criteria_artifact": {
            "path": str(criteria_path), "schema": "protocol_criteria",
            "status": "frozen", "sha256": _sha(criteria_path),
        },
        "source_plan": source_plan,
        "amendment_policy": config["amendment_policy"],
        "created_at_utc": request["created_at_utc"],
        "frozen_at_utc": request["created_at_utc"],
        "frozen_by": "preregistered-evaluation-actor",
    }
    compiled = compile_full_protocol(protocol)
    if not compiled.ready_to_freeze or compiled.document["status"] != "frozen":
        details = ",".join(issue.code for issue in compiled.issues)
        raise JointLifecycleRunError(f"protocol cannot pass the freeze gate: {details}")
    protocol_path = output_dir / "protocol.json"
    atomic_write_json(protocol_path, compiled.document, "protocol")
    artifacts = [
        {"artifact_id": "protocol_criteria", "path": str(criteria_path), "sha256": _sha(criteria_path), "media_type": "application/json", "role": "eligibility_criteria"},
        {"artifact_id": "protocol", "path": str(protocol_path), "sha256": _sha(protocol_path), "media_type": "application/json", "role": "stage_state"},
    ] + query_artifacts
    output = {
        "schema_version": "1.0", "stage_id": "protocol_registration",
        "status": "completed", "state_artifact_id": "protocol",
        "artifacts": artifacts,
        "scientific_checks": [{
            "check_id": "protocol_frozen", "status": "passed",
            "evidence_artifact_ids": ["protocol_criteria", "protocol"],
        }],
        "terminal_reason": None,
    }
    validate_document(output, "joint_lifecycle_stage_output")
    return output
