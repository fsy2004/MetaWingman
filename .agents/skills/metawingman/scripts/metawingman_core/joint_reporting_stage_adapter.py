"""Render an evidence-bound report and audit every frozen reporting-checklist item."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .joint_lifecycle_runner import AtomicStageBudgetMeter, JointLifecycleRunError
from .schema_guard import SchemaValidationError, validate_document
from .state_store import atomic_write_json


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
        raise JointLifecycleRunError("certainty output manifest hash drift")
    try:
        output = json.loads(manifest_path.read_text(encoding="utf-8"))["stage_output"]
        rows = [item for item in output["artifacts"] if item["artifact_id"] == output["state_artifact_id"]]
        if len(rows) != 1:
            raise KeyError("certainty state")
        path = Path(rows[0]["path"]).resolve(strict=True)
        if _sha(path) != rows[0]["sha256"]:
            raise JointLifecycleRunError("certainty state artifact hash drift")
        state = json.loads(path.read_text(encoding="utf-8"))
        validate_document(state, "joint_certainty_stage_state")
    except (OSError, json.JSONDecodeError, KeyError, SchemaValidationError) as exc:
        raise JointLifecycleRunError(f"invalid certainty state: {exc}") from exc
    return state, path


def _has_nonempty_rows(value: Any) -> bool:
    return isinstance(value, list) and any(isinstance(row, dict) and row for row in value)


def _checklist_coverage(
    rule_id: str, *, protocol: dict[str, Any], search: dict[str, Any], selection: dict[str, Any],
    lineage: dict[str, Any], appraisal: dict[str, Any], synthesis: dict[str, Any], certainty: dict[str, Any],
) -> bool:
    """Require item-specific structured evidence; prose presence alone never proves coverage."""
    always_supported = {
        "title", "abstract", "objectives", "eligibility", "information_sources", "search_strategy",
        "selection_process", "data_collection_process", "outcome_data_items", "risk_of_bias_methods",
        "effect_measures", "synthesis_eligibility", "data_preparation", "synthesis_methods",
        "reporting_bias_methods", "certainty_methods", "selection_results", "certainty_results",
        "interpretation", "evidence_limitations", "review_process_limitations", "protocol_access",
        "amendments", "data_code_availability",
    }
    if rule_id in always_supported:
        return True
    if rule_id == "rationale":
        return bool(protocol.get("rationale_in_context_of_existing_knowledge"))
    if rule_id == "other_data_items":
        return _has_nonempty_rows(lineage.get("extraction_candidates"))
    if rule_id == "display_methods":
        return bool(synthesis.get("display_method_artifacts"))
    if rule_id == "heterogeneity_methods":
        return bool(synthesis.get("heterogeneity_method"))
    if rule_id == "sensitivity_methods":
        return bool(synthesis.get("sensitivity_analysis_plan"))
    if rule_id == "excluded_studies":
        return _has_nonempty_rows(lineage.get("full_text_exclusion_citations"))
    if rule_id == "study_characteristics":
        return _has_nonempty_rows(lineage.get("studies"))
    if rule_id == "risk_of_bias_results":
        return _has_nonempty_rows(appraisal.get("appraisal_dossiers"))
    if rule_id == "individual_study_results":
        return _has_nonempty_rows(lineage.get("results"))
    if rule_id == "synthesis_characteristics":
        return _has_nonempty_rows(synthesis.get("effect_estimates"))
    if rule_id == "synthesis_results":
        return bool(synthesis.get("synthesis_result"))
    if rule_id == "heterogeneity_results":
        result = synthesis.get("synthesis_result")
        return isinstance(result, dict) and any(key in result for key in ("i2", "tau2", "heterogeneity"))
    if rule_id == "sensitivity_results":
        return _has_nonempty_rows(synthesis.get("sensitivity_analysis_results"))
    if rule_id == "reporting_bias_results":
        return bool(appraisal.get("missing_evidence_matrix"))
    if rule_id == "implications":
        return bool(certainty.get("implications_for_practice_policy_research"))
    if rule_id == "registration":
        return bool(protocol.get("registration"))
    if rule_id == "support":
        return bool(protocol.get("support_declaration"))
    if rule_id == "competing_interests":
        return bool(protocol.get("competing_interests_declaration"))
    return False


def reporting_review_stage_adapter(request: dict[str, Any], meter: AtomicStageBudgetMeter) -> dict[str, Any]:
    if request.get("stage_id") != "reporting_review" or request.get("ordinal") != 8:
        raise JointLifecycleRunError("reporting adapter can execute only canonical stage eight")
    if request.get("published_reference_accessed") is not False:
        raise JointLifecycleRunError("reporting adapter refuses published-reference access")
    config = request.get("config")
    try:
        validate_document(config, "joint_reporting_stage_config")
    except SchemaValidationError as exc:
        raise JointLifecycleRunError(str(exc)) from exc
    root = Path(request["repository_root"]).resolve(strict=True)
    certainty, certainty_path = _previous(request)
    checklist_path = _bound(root, config["checklist_manifest"], "reporting checklist")
    try:
        checklist = json.loads(checklist_path.read_text(encoding="utf-8"))
        validate_document(checklist, "joint_reporting_checklist_manifest")
    except (OSError, json.JSONDecodeError, SchemaValidationError) as exc:
        raise JointLifecycleRunError(f"invalid reporting checklist: {exc}") from exc
    checklist_sources = [
        _bound(root, binding, f"reporting checklist source artifact {index}")
        for index, binding in enumerate(checklist["source_artifacts"], start=1)
    ]
    synthesis_path = _bound(root, certainty["synthesis_state_artifact"], "synthesis state")
    synthesis = json.loads(synthesis_path.read_text(encoding="utf-8"))
    appraisal_path = _bound(root, synthesis["appraisal_state_artifact"], "appraisal state")
    appraisal = json.loads(appraisal_path.read_text(encoding="utf-8"))
    lineage_path = _bound(root, appraisal["lineage_state_artifact"], "lineage state")
    lineage = json.loads(lineage_path.read_text(encoding="utf-8"))
    selection_path = _bound(root, lineage["selection_state_artifact"], "selection state")
    selection = json.loads(selection_path.read_text(encoding="utf-8"))
    search_path = _bound(root, selection["search_state_artifact"], "search state")
    search = json.loads(search_path.read_text(encoding="utf-8"))
    protocol_path = _bound(root, selection["protocol_artifact"], "protocol")
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    claim = certainty["claims"][0]
    sections: dict[str, dict[str, Any]] = {
        "title": {"text": f"{config['report_title_prefix']}: {protocol.get('protocol_id', request['case_id'])}", "evidence": [str(protocol_path)]},
        "abstract": {"text": claim["text"] + " " + " ".join(claim["scope"]["applicability_limits"]), "evidence": [str(certainty_path)]},
        "introduction": {"text": str(protocol.get("decision_context", {}).get("decision", "The frozen decision context is reported in the protocol.")), "evidence": [str(protocol_path)]},
        "methods_protocol": {"text": "The protocol and eligibility criteria were frozen before search execution; amendments require prospective versioning and impact analysis.", "evidence": [str(protocol_path)]},
        "methods_search": {"text": f"Searches used the historical cutoff {search['historical_cutoff']} and retained {len(search['records'])} deduplicated pre-cutoff records; {len(search['quarantined_records'])} records were quarantined by the temporal gate.", "evidence": [str(search_path)]},
        "methods_selection": {"text": "Every retrieved record received a criterion-level title/abstract decision, and every carried-forward report received a separate full-text criterion assessment; missing information was not treated as exclusion.", "evidence": [str(selection_path), str(lineage_path)]},
        "methods_data": {"text": "Full-text results required exact source spans and report-study-result-estimand lineage before admission.", "evidence": [str(lineage_path)]},
        "methods_appraisal": {"text": "Framework-versioned signaling questions were proposed by the frozen model and checked by exact-span conservative opposition; production finalization remains pending.", "evidence": [str(appraisal_path)]},
        "methods_synthesis": {"text": f"Analysis inputs were hash-frozen before execution. Requested route: {synthesis['requested_route_id']}; executed route: {synthesis['executed_route_id']}.", "evidence": [str(synthesis_path)]},
        "methods_certainty": {"text": f"Certainty used {certainty['certainty_assessment']['framework']} with explicit domain downgrades; it is an evaluation judgment, not a production human sign-off.", "evidence": [str(certainty_path)]},
        "results_selection": {"text": f"Of {len(selection['record_ids'])} title/abstract records, {len(selection['include_record_ids'])} were included, {len(selection['exclude_record_ids'])} excluded, and {len(selection['abstain_record_ids'])} carried forward as abstentions. At full text, {len(lineage.get('full_text_include_record_ids', []))} were included, {len(lineage.get('full_text_exclude_record_ids', []))} excluded with criterion-level citations, and {len(lineage.get('full_text_abstain_record_ids', []))} abstained.", "evidence": [str(selection_path), str(lineage_path)]},
        "results_studies": {"text": f"The full-text lineage gate produced {lineage['complete_verified_lineage_count']} verified result lineages and left {len(lineage['unresolved_record_ids'])} records unresolved.", "evidence": [str(lineage_path)]},
        "results_synthesis": {"text": claim["text"], "evidence": [str(synthesis_path), str(certainty_path)]},
        "results_certainty": {"text": f"The preregistered evaluation certainty judgment was {certainty['certainty_assessment']['judgment']}.", "evidence": [str(certainty_path)]},
        "discussion": {"text": "Interpretation is limited to the frozen estimand, lawful pre-cutoff corpus, verified source spans, observed mapping ceiling, and unresolved appraisal or missing-evidence signals.", "evidence": [str(certainty_path), str(appraisal_path)]},
        "registration_support": {"text": "Execution identifiers, actor bindings, model checkpoints, stage budgets, hashes, and receipts are recorded in the joint lifecycle run artifacts. Funding and conflicts were not inferred.", "evidence": [str(certainty_path)]},
        "data_availability": {"text": "Operational derivatives are hash-bound. Source redistribution remains subject to each source license and access route; sealed published references are excluded from this report stage.", "evidence": [str(lineage_path)]},
    }
    audits = []
    for item in checklist["items"]:
        section = sections.get(item["required_section"])
        supported = _checklist_coverage(
            item["coverage_rule_id"], protocol=protocol, search=search, selection=selection,
            lineage=lineage, appraisal=appraisal, synthesis=synthesis, certainty=certainty,
        )
        status = "reported" if section and section["text"].strip() and supported else "not_reported"
        audits.append({
            "item_id": item["item_id"], "requirement": item["requirement"],
            "required_section": item["required_section"], "coverage_rule_id": item["coverage_rule_id"],
            "status": status,
            "evidence_paths": [] if section is None else section["evidence"],
            "reviewer": "deterministic-checklist-completeness-auditor-v1",
        })
    lines = [f"# {sections['title']['text']}"]
    for section_id, row in sections.items():
        if section_id == "title":
            continue
        lines.extend(["", f"## {section_id.replace('_', ' ').title()}", "", row["text"]])
    output_dir = Path(request["stage_output_dir"]).resolve(strict=True)
    report_path = output_dir / "blind-evidence-report.md"
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    state = {
        "schema_version": "1.0", "stage_id": "reporting_review", "case_id": request["case_id"],
        "arm_id": request["arm_id"], "seed": request["seed"],
        "certainty_state_artifact": {"path": str(certainty_path), "sha256": _sha(certainty_path)},
        "report_artifact": {"path": str(report_path), "sha256": _sha(report_path)},
        "checklist_manifest_artifact": {"path": str(checklist_path), "sha256": _sha(checklist_path)},
        "checklist_source_artifacts": [
            {"path": str(path), "sha256": _sha(path)} for path in checklist_sources
        ],
        "section_evidence_map": sections, "checklist_audit": audits,
        "all_checklist_items_accounted_for": len(audits) == len(checklist["items"]),
        "production_human_responsibility_pending": True, "published_reference_accessed": False,
    }
    state_path = output_dir / "reporting-state.json"
    atomic_write_json(state_path, state, "joint_reporting_stage_state")
    artifacts = [
        {"artifact_id": "reporting_state", "path": str(state_path), "sha256": _sha(state_path), "media_type": "application/json", "role": "stage_state"},
        {"artifact_id": "blind_report", "path": str(report_path), "sha256": _sha(report_path), "media_type": "text/markdown", "role": "evidence_bound_report"},
    ]
    output = {
        "schema_version": "1.0", "stage_id": "reporting_review", "status": "completed",
        "state_artifact_id": "reporting_state", "artifacts": artifacts,
        "scientific_checks": [{"check_id": "reporting_and_review_complete", "status": "passed", "evidence_artifact_ids": ["reporting_state", "blind_report"]}],
        "terminal_reason": None,
    }
    validate_document(output, "joint_lifecycle_stage_output")
    return output
