#!/usr/bin/env python3
"""Create an auditable systematic-review project scaffold."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from metawingman_core.biomedical_domain import load_domain_packs, resolve_context
from metawingman_core.provenance_graph import ProvenanceGraph
from metawingman_core.schema_guard import validate_document


PROFILES = {
    "intervention", "network", "diagnostic", "prognostic", "prediction-model",
    "etiology", "prevalence", "incidence", "harms", "dose-response", "ipd", "measurement",
    "scoping", "qualitative", "mixed-methods", "economic", "umbrella", "rapid",
    "living", "prospective", "other",
}
OPERATING_MODES = {"assurance", "evaluation", "rapid"}
SCAFFOLD_VERSION = "1.1"
DOMAIN_PACK_DIR = Path(__file__).resolve().parents[1] / "references" / "domain-packs"


def slugify(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip()).strip("-.")
    return slug or "systematic-review"


def write_csv(path: Path, headers: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        csv.writer(handle).writerow(headers)


def write_json(path: Path, document: dict[str, object], schema_name: str | None = None) -> None:
    if schema_name:
        validate_document(document, schema_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(document, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def independent_review_rules(mode: str) -> list[dict[str, object]]:
    minimums = {
        "title_abstract_screening": 2,
        "full_text_eligibility": 2,
        "outcome_data_extraction": 2,
        "risk_of_bias": 2,
        "certainty": 2,
        "poolability": 2,
        "final_conclusion": 1,
    }
    if mode == "rapid":
        minimums = {task: 1 for task in minimums}
    return [
        {
            "task_type": task,
            "independent_human_required": True,
            "minimum_independent_humans": minimum,
            "ai_may_prepare": True,
            "ai_may_replace_human": mode == "evaluation" and task != "final_conclusion",
            "required_ai_exposure_order": "recorded",
            "adjudication_rule": "human_lead" if task == "final_conclusion" else "consensus",
        }
        for task, minimum in minimums.items()
    ]


def draft_biomedical_context(
    context_id: str,
    review_family: str,
    specialties: list[str],
    now: str,
    *,
    specialty_was_declared: bool,
) -> dict[str, object]:
    context = resolve_context(
        {
            "context_id": context_id,
            "review_family": review_family,
            "source_text": "",
            "declared_specialties": specialties,
        },
        load_domain_packs(DOMAIN_PACK_DIR),
        now,
    )
    reason_codes = ["source_text_not_reviewed"]
    if not specialty_was_declared:
        reason_codes.insert(0, "specialty_not_declared")
    context["ood_assessment"] = {
        "status": "uncertain",
        "reason_codes": reason_codes,
        **(
            {"routing_confidence": 0.0}
            if "routing_confidence" in context["ood_assessment"]
            else {}
        ),
    }
    validate_document(context, "biomedical_context")
    return context


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", required=True, help="Human-readable review title")
    parser.add_argument("--root", required=True, type=Path, help="Parent directory")
    parser.add_argument("--slug", help="Project folder name")
    parser.add_argument("--profile", required=True, choices=sorted(PROFILES))
    parser.add_argument(
        "--specialty",
        action="append",
        help="Declared specialty ID; repeat for secondary specialties",
    )
    parser.add_argument("--mode", choices=sorted(OPERATING_MODES), default="assurance")
    parser.add_argument("--git", action="store_true", help="Initialize a local Git repository")
    args = parser.parse_args()

    root = args.root.expanduser().resolve()
    slug = args.slug or slugify(args.name)
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", slug) or slug in {".", ".."}:
        raise SystemExit("--slug must be one safe directory name using letters, numbers, dot, underscore, or hyphen")
    target = (root / slug).resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise SystemExit("Review project path escapes --root") from exc
    if target.exists() and any(target.iterdir()):
        raise SystemExit(f"Refusing to overwrite non-empty directory: {target}")
    now = datetime.now(timezone.utc).isoformat()
    biomedical_context = draft_biomedical_context(
        f"{target.name}-biomedical-context",
        args.profile,
        args.specialty or ["general-medicine"],
        now,
        specialty_was_declared=bool(args.specialty),
    )
    target.mkdir(parents=True, exist_ok=True)

    dirs = [
        "00_admin/pipelines", "00_admin/security",
        "00_topic/landscapes", "00_topic/candidates", "00_topic/decisions",
        "01_protocol",
        "02_search/queries", "02_search/exports/raw", "02_search/retrieval/full_text",
        "02_search/acquisition",
        "02_search/retrieval/documents", "03_screening/assessments", "04_extraction",
        "05_appraisal/dossiers", "06_analysis/input", "06_analysis/code",
        "06_analysis/output", "07_reporting", "08_review",
        "09_update/snapshots", "09_update/deltas", "10_benchmark",
    ]
    for item in dirs:
        (target / item).mkdir(parents=True, exist_ok=True)

    project = {
        "scaffold_version": SCAFFOLD_VERSION,
        "title": args.name,
        "profile": args.profile,
        "operating_mode": args.mode,
        "created_at_utc": now,
        "stage": 0,
        "protocol_version": "0.1-draft",
        "registration": {"registry": "", "id": "", "url": ""},
        "human_lead": "",
        "notes": "Technical scaffold only; no scientific gate is complete at creation.",
    }
    write_json(target / "00_admin/project.json", project)
    gates = {str(i): {"status": "not_started", "verified_by": "", "verified_at": "", "evidence": []} for i in range(10)}
    write_json(target / "00_admin/gate_status.json", gates)

    (target / "00_admin/decision_log.md").write_text(
        "# Decision log\n\n| Date | Stage | Decision | Rationale | Prospective/post hoc | Owner |\n|---|---|---|---|---|---|\n",
        encoding="utf-8",
    )
    protocol = f"""# Protocol: {args.name}

Status: draft
Version: 0.1
Review profile: {args.profile}

## Decision problem and rationale

## Objectives and question framework

## Eligibility criteria

## Outcomes, measures, timepoints, and hierarchy

## Information sources and search strategy

## Record management, screening, and retrieval

## Data items, extraction, and study/report/result lineage

## Risk of bias and reporting bias

## Synthesis groups, effect measures, and statistical methods

## Heterogeneity, dependency, missing data, subgroups, and sensitivity analyses

## Certainty, applicability, and interpretation

## Registration, amendments, data/code sharing, conflicts, funding, and AI use
"""
    (target / "01_protocol/protocol.md").write_text(protocol, encoding="utf-8")

    review_state = {
        "schema_version": "1.0",
        "project_id": target.name,
        "title": args.name,
        "profile": args.profile,
        "stage": 0,
        "protocol": {
            "version": "0.1-draft",
            "status": "draft",
            "sha256": hashlib.sha256(protocol.encode("utf-8")).hexdigest(),
            "registration": {"registry": "", "id": "", "url": ""},
        },
        "gates": gates,
        "unresolved_risks": [],
        "freezes": [],
        "updated_at_utc": now,
    }
    (target / "00_admin/event_ledger.jsonl").touch()
    (target / "00_admin/abstentions.jsonl").touch()
    (target / "00_topic/landscapes/README.md").write_text(
        "# Temporal evidence landscapes\n\n"
        "Store cutoff-bounded, source-traceable landscape JSON here. For historical "
        "rediscovery, seal the target identity, descendants, and post-cutoff evidence "
        "before any candidate generation.\n",
        encoding="utf-8",
    )
    (target / "00_topic/candidates/topic_candidates.jsonl").touch()
    (target / "00_topic/candidates/topic_proposal_batches.jsonl").touch()
    (target / "00_topic/decisions/topic_opportunity_decisions.jsonl").touch()
    (target / "00_topic/topic_decision.md").write_text(
        "# Topic decision\n\n"
        "Status: not started\n\n"
        "## Decision need and stakeholders\n\n"
        "## Existing reviews, protocols, and update status\n\n"
        "## Evidence landscape and feasibility\n\n"
        "## Candidate portfolio, opposition, and abstentions\n\n"
        "## Accountable final decision\n",
        encoding="utf-8",
    )
    model_registry = {"schema_version": "1.0", "models": []}
    write_json(target / "00_admin/model_registry.json", model_registry, "model_registry")
    credential_capabilities = {
        "schema_version": "1.0",
        "secret_storage_policy": "environment_or_user_approved_secret_store_only",
        "capabilities": [
            {
                "capability_id": "pubmed-eutilities",
                "provider": "NCBI",
                "purpose": "PubMed/MEDLINE search and PMC link retrieval",
                "access_class": "optional_api_key",
                "status": "unconfigured",
                "required_environment_variables": [],
                "optional_environment_variables": ["NCBI_EMAIL", "NCBI_API_KEY"],
                "credential_owner": "",
                "last_tested_at_utc": None,
                "notes": "Works without a key at the public rate; identify the tool and contact email for production use.",
            },
            {
                "capability_id": "europe-pmc",
                "provider": "Europe PMC",
                "purpose": "Biomedical metadata and lawful open full-text XML",
                "access_class": "public_no_account",
                "status": "available",
                "required_environment_variables": [],
                "optional_environment_variables": [],
                "credential_owner": "",
                "last_tested_at_utc": None,
                "notes": "Public REST service; still record request and data timestamps.",
            },
            {
                "capability_id": "clinicaltrials-gov",
                "provider": "ClinicalTrials.gov",
                "purpose": "Trial registry search and structured public records",
                "access_class": "public_no_account",
                "status": "available",
                "required_environment_variables": [],
                "optional_environment_variables": [],
                "credential_owner": "",
                "last_tested_at_utc": None,
                "notes": "Public API v2; capture the live API and data timestamp for each run.",
            },
            {
                "capability_id": "crossref-rest",
                "provider": "Crossref",
                "purpose": "DOI identity and metadata verification",
                "access_class": "contact_email",
                "status": "unconfigured",
                "required_environment_variables": [],
                "optional_environment_variables": ["CROSSREF_EMAIL"],
                "credential_owner": "",
                "last_tested_at_utc": None,
                "notes": "Public REST access needs no account; a real contact email is preferred for the polite pool.",
            },
            {
                "capability_id": "unpaywall",
                "provider": "Unpaywall",
                "purpose": "Resolve verified open-access locations",
                "access_class": "contact_email",
                "status": "unconfigured",
                "required_environment_variables": ["UNPAYWALL_EMAIL"],
                "optional_environment_variables": [],
                "credential_owner": "",
                "last_tested_at_utc": None,
                "notes": "The current API requires an email parameter; this is contact identification, not a secret.",
            },
            {
                "capability_id": "licensed-databases",
                "provider": "Institutional library or database vendor",
                "purpose": "Embase, CENTRAL, Web of Science, Scopus, and topic-specific databases",
                "access_class": "institutional_handoff",
                "status": "unconfigured",
                "required_environment_variables": [],
                "optional_environment_variables": [],
                "credential_owner": "",
                "last_tested_at_utc": None,
                "notes": "Use the institution-approved interactive interface and user export; never store passwords, cookies, or licensed session state.",
            },
        ],
    }
    write_json(
        target / "00_admin/credential_capabilities.json",
        credential_capabilities,
        "credential_capabilities",
    )
    with ProvenanceGraph(target / "00_admin/provenance.sqlite3"):
        pass

    profile_id = f"{target.name}-profile"
    review_profile = {
        "schema_version": "1.0",
        "profile_id": profile_id,
        "review_family": args.profile,
        "status": "draft",
        "operating_mode": {
            "name": args.mode,
            "replacement_claim": "",
            "evaluation_plan_id": None,
            "declared_by": "",
            "declared_at_utc": now,
        },
        "authorities": [],
        "independent_review": independent_review_rules(args.mode),
        "created_at_utc": now,
        "updated_at_utc": now,
    }
    write_json(target / "01_protocol/review_profile.json", review_profile, "review_profile")
    write_json(
        target / "01_protocol/biomedical_context.json",
        biomedical_context,
        "biomedical_context",
    )
    protocol_criteria = {
        "schema_version": "1.0",
        "protocol_version": "0.1-draft",
        "status": "draft",
        "criteria": [],
    }
    write_json(target / "01_protocol/protocol_criteria.json", protocol_criteria, "protocol_criteria")

    typed_protocol = {
        "schema_version": "1.0",
        "protocol_id": f"{target.name}-protocol",
        "protocol_version": "0.1-draft",
        "status": "draft",
        "profile_id": profile_id,
        "decision_context": {
            "decision": "",
            "stakeholders": [],
            "setting": "",
            "intended_use": "",
        },
        "review_questions": [],
        "synthesis_questions": [],
        "outcome_hierarchy": [],
        "criteria_artifact": {
            "path": "01_protocol/protocol_criteria.json",
            "schema": "protocol_criteria",
            "status": "draft",
            "sha256": None,
        },
        "source_plan": [],
        "amendment_policy": {
            "freeze_trigger": "Human lead approves the complete typed protocol and profile.",
            "prospective_change_rule": "Record and approve changes before examining affected results.",
            "post_hoc_label_required": True,
            "rerun_impact_analysis": True,
        },
        "created_at_utc": now,
        "frozen_at_utc": None,
        "frozen_by": None,
    }
    write_json(target / "01_protocol/protocol.json", typed_protocol, "protocol")
    review_state["protocol"]["sha256"] = hashlib.sha256(
        (target / "01_protocol/protocol.json").read_bytes()
    ).hexdigest()
    write_json(target / "00_admin/review_state.json", review_state, "review_state")

    evaluation_plan = json.loads(
        (Path(__file__).resolve().parents[1] / "references/ai-only-evaluation-plan.template.json")
        .read_text(encoding="utf-8")
    )
    evaluation_plan["plan_id"] = f"{target.name}-ai-only-evaluation"
    write_json(
        target / "10_benchmark/ai_only_evaluation_plan.json",
        evaluation_plan,
        "ai_only_evaluation_plan",
    )

    jsonl_streams = [
        "01_protocol/reviewer_assignments.jsonl",
        "01_protocol/protocol_deviations.jsonl",
        "02_search/retrieval/document_state.jsonl",
        "02_search/acquisition/evidence_acquisition_states.jsonl",
        "02_search/acquisition/evidence_acquisition_decisions.jsonl",
        "03_screening/screening_assessments.jsonl",
        "04_extraction/evidence_anchors.jsonl",
        "04_extraction/evidence_assertions.jsonl",
        "04_extraction/lineage_edges.jsonl",
        "04_extraction/extraction_candidates.jsonl",
        "04_extraction/effect_estimates.jsonl",
        "05_appraisal/appraisal_dossiers.jsonl",
        "05_appraisal/missing_evidence_matrices.jsonl",
        "05_appraisal/poolability_matrices.jsonl",
        "06_analysis/analysis_manifests.jsonl",
        "07_reporting/claims.jsonl",
        "09_update/living_snapshots.jsonl",
        "09_update/living_deltas.jsonl",
        "10_benchmark/ai_only_runs.jsonl",
        "10_benchmark/protocol_counterfactual_cases.jsonl",
        "10_benchmark/causal_replay_reports.jsonl",
        "10_benchmark/topic_rediscovery_cases.jsonl",
        "10_benchmark/topic_rediscovery_reports.jsonl",
    ]
    for relative in jsonl_streams:
        (target / relative).touch()

    tables = {
        "00_admin/credential_capabilities.csv": ["provider", "account_owner", "approved_scope", "rate_limit", "expiry_or_rotation", "last_tested", "status", "notes"],
        "00_admin/ai_use_log.csv": ["timestamp", "stage", "tool_model", "task", "input_scope", "output_artifact", "human_verifier", "verification_status", "notes"],
        "01_protocol/amendments.csv": ["amendment_id", "date", "protocol_version", "section", "old_rule", "new_rule", "rationale", "prospective_or_posthoc", "approved_by"],
        "02_search/search_log.csv": ["search_id", "database", "platform", "query_file", "coverage", "executed_at", "timezone", "limits", "result_count", "export_file", "sha256", "searcher", "notes"],
        "03_screening/screening_decisions.csv": ["record_id", "report_id", "stage", "reviewer", "timestamp", "decision", "reason_code", "evidence_note", "conflict", "adjudicator", "final_decision"],
        "03_screening/full_text_exclusions.csv": ["report_id", "citation", "primary_reason", "secondary_note", "reviewer_1", "reviewer_2", "adjudicator", "date"],
        "03_screening/dedup_candidates.csv": ["candidate_id", "record_id_a", "record_id_b", "match_basis", "similarity", "reviewer_decision", "reviewer", "date"],
        "04_extraction/report_study_map.csv": ["record_id", "report_id", "study_id", "result_ids", "relationship", "registry_ids", "notes", "verified_by"],
        "04_extraction/study_characteristics.csv": ["study_id", "report_id", "design", "country", "setting", "recruitment_dates", "population", "n", "intervention_or_exposure", "comparator", "follow_up", "funding", "conflicts", "source_anchor", "extractor", "verifier"],
        "04_extraction/results.csv": ["result_id", "study_id", "report_id", "synthesis_id", "outcome", "definition", "measure", "direction", "timepoint", "population", "comparison", "raw_data", "effect", "se", "ci_lower", "ci_upper", "adjustment_set", "model", "source_anchor", "extractor", "verifier", "status"],
        "05_appraisal/risk_of_bias.csv": ["result_id", "study_id", "tool", "tool_version", "domain", "signaling_answer", "judgment", "rationale", "source_anchor", "reviewer", "second_reviewer", "adjudication"],
        "05_appraisal/certainty.csv": ["synthesis_id", "outcome", "comparison", "framework", "starting_level", "risk_of_bias", "inconsistency", "indirectness", "imprecision", "publication_bias", "upgrades", "final_certainty", "rationale", "reviewers"],
        "07_reporting/claim_evidence_ledger.csv": ["claim_id", "manuscript_location", "claim", "evidence_state", "reference_id", "supporting_location", "verifier", "date", "notes"],
        "07_reporting/prisma_counts.csv": ["stage", "source", "count", "derived_from", "verified_by", "date"],
        "08_review/reviewer_findings.csv": ["finding_id", "reviewer_lens", "severity", "artifact", "evidence_anchor", "problem", "consequence", "correction", "verification_test", "status", "owner"],
        "08_review/revision_trace.csv": ["finding_id", "author_response", "changed_artifact", "diff_or_patch", "changed_output", "verdict", "verified_by", "date", "notes"],
        "09_update/update_log.csv": ["update_id", "search_started", "search_completed", "sources", "new_records", "new_included_studies", "conclusion_changed", "version", "status", "notes"],
    }
    for rel, headers in tables.items():
        write_csv(target / rel, headers)

    (target / "07_reporting/manuscript.md").write_text(f"# {args.name}\n\n## Abstract\n\n## Introduction\n\n## Methods\n\n## Results\n\n## Discussion\n\n## Declarations\n", encoding="utf-8")
    (target / "07_reporting/supplement.md").write_text("# Supplement\n\n## Full search strategies\n\n## Excluded full-text reports\n\n## Additional methods and analyses\n", encoding="utf-8")
    (target / "06_analysis/freeze_manifest.json").write_text(json.dumps({"status": "not_frozen", "created_at": "", "files": []}, indent=2) + "\n", encoding="utf-8")
    (target / ".gitignore").write_text(
        ".env\n*.key\n*.pem\n__pycache__/\n.venv/\n*.sqlite3-wal\n*.sqlite3-shm\n"
        "*.jsonl.lock\n"
        "02_search/retrieval/full_text/*\n!02_search/retrieval/full_text/.gitkeep\n",
        encoding="utf-8",
    )
    (target / "02_search/retrieval/full_text/.gitkeep").touch()

    if args.git:
        subprocess.run(["git", "init", str(target)], check=True)
    print(target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
