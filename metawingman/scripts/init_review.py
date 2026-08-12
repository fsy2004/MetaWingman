#!/usr/bin/env python3
"""Create an auditable systematic-review project scaffold."""

from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path


PROFILES = {
    "intervention", "network", "diagnostic", "prognostic", "prediction-model",
    "etiology", "prevalence", "harms", "dose-response", "ipd", "measurement",
    "scoping", "qualitative", "mixed-methods", "economic", "umbrella", "rapid",
    "living", "prospective", "other",
}


def slugify(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip()).strip("-.")
    return slug or "systematic-review"


def write_csv(path: Path, headers: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        csv.writer(handle).writerow(headers)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", required=True, help="Human-readable review title")
    parser.add_argument("--root", required=True, type=Path, help="Parent directory")
    parser.add_argument("--slug", help="Project folder name")
    parser.add_argument("--profile", required=True, choices=sorted(PROFILES))
    parser.add_argument("--git", action="store_true", help="Initialize a local Git repository")
    args = parser.parse_args()

    target = (args.root.expanduser().resolve() / (args.slug or slugify(args.name))).resolve()
    if target.exists() and any(target.iterdir()):
        raise SystemExit(f"Refusing to overwrite non-empty directory: {target}")
    target.mkdir(parents=True, exist_ok=True)

    dirs = [
        "00_admin", "01_protocol", "02_search/queries", "02_search/exports/raw",
        "02_search/retrieval/full_text", "03_screening", "04_extraction",
        "05_appraisal", "06_analysis/input", "06_analysis/code", "06_analysis/output",
        "07_reporting", "08_review", "09_update",
    ]
    for item in dirs:
        (target / item).mkdir(parents=True, exist_ok=True)

    now = datetime.now(timezone.utc).isoformat()
    project = {
        "title": args.name,
        "profile": args.profile,
        "created_at_utc": now,
        "stage": 0,
        "protocol_version": "0.1-draft",
        "registration": {"registry": "", "id": "", "url": ""},
        "human_lead": "",
        "notes": "Technical scaffold only; no scientific gate is complete at creation.",
    }
    (target / "00_admin/project.json").write_text(json.dumps(project, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    gates = {str(i): {"status": "not_started", "verified_by": "", "verified_at": "", "evidence": []} for i in range(10)}
    (target / "00_admin/gate_status.json").write_text(json.dumps(gates, indent=2) + "\n", encoding="utf-8")

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
    (target / ".gitignore").write_text(".env\n*.key\n*.pem\n__pycache__/\n.venv/\n02_search/retrieval/full_text/*\n!02_search/retrieval/full_text/.gitkeep\n", encoding="utf-8")
    (target / "02_search/retrieval/full_text/.gitkeep").touch()

    if args.git:
        subprocess.run(["git", "init", str(target)], check=True)
    print(target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
