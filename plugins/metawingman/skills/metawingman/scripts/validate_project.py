#!/usr/bin/env python3
"""Validate scientific gate evidence, hashes, counts, and secret hygiene."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from pathlib import Path

from metawingman_core.method_contract import inspect_method_contract
from metawingman_core.provenance_graph import ProvenanceGraph
from metawingman_core.schema_guard import SchemaValidationError, validate_json_file, validate_jsonl_file
from metawingman_core.state_store import EventLedger


REQUIRED = {
    0: [
        "00_admin/project.json",
        "00_admin/decision_log.md",
        "00_topic/topic_decision.md",
        "00_topic/candidates/topic_candidates.jsonl",
        "00_topic/candidates/topic_proposal_batches.jsonl",
        "00_topic/decisions/topic_opportunity_decisions.jsonl",
    ],
    1: [
        "01_protocol/protocol.md",
        "01_protocol/review_profile.json",
        "01_protocol/protocol.json",
        "01_protocol/protocol_criteria.json",
        "01_protocol/amendments.csv",
    ],
    2: [
        "02_search/search_log.csv",
        "02_search/acquisition/evidence_acquisition_states.jsonl",
        "02_search/acquisition/evidence_acquisition_decisions.jsonl",
    ],
    3: [
        "03_screening/screening_decisions.csv",
        "03_screening/full_text_exclusions.csv",
        "03_screening/screening_assessments.jsonl",
    ],
    4: [
        "04_extraction/report_study_map.csv",
        "04_extraction/results.csv",
        "04_extraction/evidence_anchors.jsonl",
        "04_extraction/lineage_edges.jsonl",
        "04_extraction/extraction_candidates.jsonl",
        "04_extraction/effect_estimates.jsonl",
    ],
    5: [
        "05_appraisal/risk_of_bias.csv",
        "05_appraisal/appraisal_dossiers.jsonl",
        "05_appraisal/missing_evidence_matrices.jsonl",
    ],
    6: ["06_analysis/freeze_manifest.json", "06_analysis/analysis_manifests.jsonl"],
    7: ["05_appraisal/certainty.csv", "05_appraisal/poolability_matrices.jsonl"],
    8: [
        "07_reporting/manuscript.md",
        "07_reporting/claim_evidence_ledger.csv",
        "07_reporting/claims.jsonl",
        "08_review/reviewer_findings.csv",
    ],
    9: ["09_update/update_log.csv", "09_update/living_snapshots.jsonl", "09_update/living_deltas.jsonl"],
}
SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|token|password|secret)\s*[:=]\s*['\"]?[A-Za-z0-9_\-]{12,}"),
    re.compile(r"gh[opusr]_[A-Za-z0-9]{20,}"),
]


def data_rows(path: Path) -> int:
    if path.suffix.lower() != ".csv" or not path.exists(): return 0
    with path.open(encoding="utf-8-sig", newline="") as handle: return sum(1 for _ in csv.DictReader(handle))


def safe_project_path(root: Path, relative: object) -> Path:
    if not isinstance(relative, str) or not relative.strip():
        raise ValueError("artifact path must be a non-empty string")
    raw = Path(relative)
    if raw.is_absolute():
        raise ValueError(f"artifact path must be project-relative: {relative}")
    candidate = (root / raw).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"artifact path escapes project root: {relative}") from exc
    return candidate


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("project", type=Path); args = parser.parse_args(); root = args.project.resolve()
    issues, warnings = [], []
    gate_file = root / "00_admin/gate_status.json"
    try: gates = json.loads(gate_file.read_text(encoding="utf-8"))
    except Exception as exc: gates = {}; issues.append(f"Cannot read gate_status.json: {exc}")

    schema_files = {
        "00_admin/review_state.json": "review_state",
        "00_admin/model_registry.json": "model_registry",
        "00_admin/credential_capabilities.json": "credential_capabilities",
        "01_protocol/review_profile.json": "review_profile",
        "01_protocol/protocol.json": "protocol",
        "01_protocol/protocol_criteria.json": "protocol_criteria",
        "10_benchmark/ai_only_evaluation_plan.json": "ai_only_evaluation_plan",
    }
    validated = {}
    for rel, schema_name in schema_files.items():
        path = root / rel
        if not path.exists():
            warnings.append(f"AI control-plane file is missing (legacy project): {rel}")
            continue
        try:
            validated[rel] = validate_json_file(path, schema_name)
        except SchemaValidationError as exc:
            issues.append(str(exc))
    jsonl_files = {
        "00_admin/event_ledger.jsonl": "event_ledger",
        "00_admin/abstentions.jsonl": "abstention",
        "00_topic/candidates/topic_candidates.jsonl": "topic_candidate",
        "00_topic/candidates/topic_proposal_batches.jsonl": "topic_proposal_batch",
        "00_topic/decisions/topic_opportunity_decisions.jsonl": "topic_opportunity_decision",
        "01_protocol/reviewer_assignments.jsonl": "reviewer_assignment",
        "01_protocol/protocol_deviations.jsonl": "protocol_deviation",
        "02_search/retrieval/document_state.jsonl": "document_state",
        "02_search/acquisition/evidence_acquisition_states.jsonl": "evidence_acquisition_state",
        "02_search/acquisition/evidence_acquisition_decisions.jsonl": "evidence_acquisition_decision",
        "03_screening/screening_assessments.jsonl": "screening_assessment",
        "04_extraction/evidence_anchors.jsonl": "evidence_anchor",
        "04_extraction/evidence_assertions.jsonl": "evidence_assertion",
        "04_extraction/lineage_edges.jsonl": "lineage_edge",
        "04_extraction/extraction_candidates.jsonl": "extraction_candidate",
        "04_extraction/effect_estimates.jsonl": "effect_estimate",
        "05_appraisal/appraisal_dossiers.jsonl": "appraisal_dossier",
        "05_appraisal/missing_evidence_matrices.jsonl": "missing_evidence_matrix",
        "05_appraisal/poolability_matrices.jsonl": "poolability_matrix",
        "06_analysis/analysis_manifests.jsonl": "analysis_manifest",
        "07_reporting/claims.jsonl": "claim",
        "09_update/living_snapshots.jsonl": "living_snapshot",
        "09_update/living_deltas.jsonl": "living_delta",
        "10_benchmark/ai_only_runs.jsonl": "ai_only_run_record",
        "10_benchmark/protocol_counterfactual_cases.jsonl": "protocol_counterfactual_case",
        "10_benchmark/causal_replay_reports.jsonl": "causal_replay_report",
        "10_benchmark/topic_rediscovery_cases.jsonl": "topic_rediscovery_case",
        "10_benchmark/topic_rediscovery_reports.jsonl": "topic_rediscovery_report",
    }
    validated_streams = {}
    for rel, schema_name in jsonl_files.items():
        path = root / rel
        if not path.exists():
            warnings.append(f"AI control-plane file is missing (legacy project): {rel}")
            continue
        try:
            validated_streams[rel] = validate_jsonl_file(path, schema_name)
        except SchemaValidationError as exc:
            issues.append(str(exc))
    event_ledger = root / "00_admin/event_ledger.jsonl"
    if event_ledger.exists():
        issues.extend(f"Event ledger: {message}" for message in EventLedger(event_ledger).verify())
    graph_path = root / "00_admin/provenance.sqlite3"
    if graph_path.exists():
        try:
            with ProvenanceGraph(graph_path) as graph:
                issues.extend(f"Provenance graph: {message}" for message in graph.verify())
        except Exception as exc:
            issues.append(f"Cannot validate provenance graph: {exc}")
    else:
        warnings.append("AI control-plane file is missing (legacy project): 00_admin/provenance.sqlite3")
    review_state = validated.get("00_admin/review_state.json")
    if review_state and review_state.get("gates") != gates:
        issues.append("review_state.json gates diverge from gate_status.json")
    contract_documents = {
        schema_name: validated[rel]
        for rel, schema_name in schema_files.items()
        if rel in validated
    }
    contract_streams = {
        schema_name: validated_streams[rel]
        for rel, schema_name in jsonl_files.items()
        if rel in validated_streams
    }
    issues.extend(
        f"Method contract: {message}"
        for message in inspect_method_contract(root, contract_documents, contract_streams, gates)
    )
    for stage, paths in REQUIRED.items():
        status = gates.get(str(stage), {}).get("status", "not_started")
        for rel in paths:
            path = root / rel
            if status == "complete" and (not path.exists() or path.stat().st_size == 0): issues.append(f"Stage {stage} marked complete but missing/empty: {rel}")
        if status == "complete" and not gates.get(str(stage), {}).get("verified_by"): issues.append(f"Stage {stage} complete without verified_by")
    freeze = root / "06_analysis/freeze_manifest.json"
    if freeze.exists():
        try:
            manifest = json.loads(freeze.read_text(encoding="utf-8"))
            if manifest.get("status") == "frozen":
                seen_frozen_paths: set[str] = set()
                for item in manifest.get("files", []):
                    relative = item.get("path") if isinstance(item, dict) else None
                    if relative in seen_frozen_paths:
                        issues.append(f"Duplicate frozen file path: {relative}")
                        continue
                    if isinstance(relative, str):
                        seen_frozen_paths.add(relative)
                    try:
                        path = safe_project_path(root, relative)
                    except ValueError as exc:
                        issues.append(f"Invalid frozen file path: {exc}")
                        continue
                    if not path.exists(): issues.append(f"Frozen file missing: {item['path']}"); continue
                    expected = item.get("sha256")
                    if not isinstance(expected, str) or not re.fullmatch(r"[a-f0-9]{64}", expected):
                        issues.append(f"Invalid frozen SHA-256: {item['path']}")
                        continue
                    actual = hashlib.sha256(path.read_bytes()).hexdigest()
                    if actual != expected: issues.append(f"Frozen hash mismatch: {item['path']}")
        except Exception as exc: issues.append(f"Invalid freeze manifest: {exc}")
    for path in root.rglob("*"):
        if not path.is_file() or path.stat().st_size > 5_000_000 or any(part == ".git" for part in path.parts): continue
        try: content = path.read_text(encoding="utf-8", errors="ignore")
        except Exception: continue
        if path.name == ".env": issues.append(".env file exists inside project; keep secrets outside versioned project")
        for pattern in SECRET_PATTERNS:
            if pattern.search(content): issues.append(f"Possible embedded secret: {path.relative_to(root)}"); break
    screening = data_rows(root / "03_screening/screening_decisions.csv")
    results = data_rows(root / "04_extraction/results.csv")
    rob = data_rows(root / "05_appraisal/risk_of_bias.csv")
    if gates.get("5", {}).get("status") == "complete" and results and not rob: issues.append("Appraisal complete but no risk-of-bias rows")
    if gates.get("6", {}).get("status") == "complete" and not results: issues.append("Synthesis complete but extraction results are empty")
    if screening == 0: warnings.append("No screening decisions yet")
    report = {"project": str(root), "issues": issues, "warnings": warnings, "row_counts": {"screening": screening, "results": results, "risk_of_bias": rob}, "valid": not issues}
    print(json.dumps(report, indent=2)); return 1 if issues else 0


if __name__ == "__main__": raise SystemExit(main())
