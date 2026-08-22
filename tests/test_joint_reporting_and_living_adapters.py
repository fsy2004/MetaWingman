from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from metawingman.scripts.metawingman_core.joint_lifecycle_runner import AtomicStageBudgetMeter
from metawingman.scripts.metawingman_core.joint_living_stage_adapter import living_update_stage_adapter
from metawingman.scripts.metawingman_core.joint_reporting_stage_adapter import reporting_review_stage_adapter
from metawingman.scripts.metawingman_core.schema_guard import validate_document


ROOT = Path(__file__).resolve().parents[1]
TIMESTAMP = "2026-08-22T12:00:00Z"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def _binding(path: Path) -> dict[str, str]:
    return {"path": str(path), "sha256": _sha(path)}


class JointReportingAndLivingAdapterTests(unittest.TestCase):
    def _chain(self, root: Path) -> tuple[Path, Path]:
        query_path = root / "historical-pubmed-query.json"
        _write(query_path, {
            "query": '("treatment" AND "response") AND ("1900-01-01"[Date - Publication] : "2020-06-07"[Date - Publication])',
            "cutoff_date": "2020-06-07", "template_id": "pubmed_pico_date_v1", "derived_from_proposal_id": "proposal-1",
        })
        protocol_path = root / "protocol.json"
        _write(protocol_path, {
            "protocol_id": "protocol-1", "decision_context": {"decision": "Whether treatment A improves response."},
            "source_plan": [{"source_id": "pubmed", "query_file": str(query_path), "query_sha256": _sha(query_path)}],
        })
        search_path = root / "search.json"
        _write(search_path, {
            "historical_cutoff": "2020-06-07",
            "protocol_artifact": _binding(protocol_path),
            "records": [{
                "record_id": "old-1", "source": "pubmed", "source_record_id": "1",
                "pmid": "1", "doi": "10.1/old", "first_publication_date": "2020-06-01",
            }],
            "quarantined_records": [],
        })
        selection_path = root / "selection.json"
        _write(selection_path, {
            "record_ids": ["old-1"], "include_record_ids": ["old-1"],
            "exclude_record_ids": [], "abstain_record_ids": [],
            "search_state_artifact": _binding(search_path), "protocol_artifact": _binding(protocol_path),
        })
        lineage_path = root / "lineage.json"
        _write(lineage_path, {
            "complete_verified_lineage_count": 1, "unresolved_record_ids": [],
            "full_text_include_record_ids": ["old-1"], "full_text_exclude_record_ids": ["old-2"],
            "full_text_abstain_record_ids": [], "all_full_text_records_accounted_for": True,
            "full_text_exclusion_citations": [{
                "record_id": "old-2", "title": "Ineligible report", "criterion_id": "population-01",
                "evidence_quote": "healthy volunteers", "rationale": "Population criterion failed.",
            }],
            "selection_state_artifact": _binding(selection_path),
        })
        appraisal_path = root / "appraisal.json"
        _write(appraisal_path, {"lineage_state_artifact": _binding(lineage_path)})
        synthesis_path = root / "synthesis.json"
        _write(synthesis_path, {
            "requested_route_id": "pairwise_random_effects", "executed_route_id": "swim_structured_synthesis",
            "appraisal_state_artifact": _binding(appraisal_path),
        })
        certainty = {
            "schema_version": "1.0", "stage_id": "certainty_interpretation", "case_id": "case-1",
            "arm_id": "arm-1", "seed": 1, "synthesis_state_artifact": _binding(synthesis_path),
            "certainty_assessment": {"framework": "GRADE-informed preregistered evaluation rubric v1", "judgment": "low"},
            "claims": [{
                "text": "Evidence was insufficient for a pooled effect.",
                "scope": {"applicability_limits": ["One source family was searched."]},
            }],
            "production_human_responsibility_pending": True, "published_reference_accessed": False,
        }
        certainty_path = root / "certainty.json"
        _write(certainty_path, certainty)
        validate_document(certainty, "joint_certainty_stage_state")
        prior_path = root / "certainty-output.json"
        _write(prior_path, {"stage_output": {"state_artifact_id": "certainty_claims_state", "artifacts": [
            {"artifact_id": "certainty_claims_state", **_binding(certainty_path), "media_type": "application/json", "role": "stage_state"}
        ]}})
        return prior_path, search_path

    def test_reporting_accounts_for_every_frozen_item_without_reference_access(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            root = Path(tmp)
            prior_path, _ = self._chain(root)
            checklist_path = root / "checklist.json"
            checklist = {
                "schema_version": "1.0", "manifest_id": "reporting-fixture-v1", "guideline": "licensed fixture",
                "version": "1", "source_url": "https://example.org/checklist", "license_or_permission": "test fixture",
                "source_artifacts": [{"path": "certainty.json", "sha256": _sha(root / "certainty.json")}],
                "items": [
                    {"item_id": "title", "required_section": "title", "requirement": "Report a title.", "coverage_rule_id": "title"},
                    {"item_id": "search", "required_section": "methods_search", "requirement": "Report the search.", "coverage_rule_id": "search_strategy"},
                    {"item_id": "data", "required_section": "data_availability", "requirement": "Report data availability.", "coverage_rule_id": "data_code_availability"},
                    {"item_id": "excluded", "required_section": "results_selection", "requirement": "Cite excluded reports.", "coverage_rule_id": "excluded_studies"},
                    {"item_id": "funding", "required_section": "registration_support", "requirement": "Report support.", "coverage_rule_id": "support"},
                ],
            }
            _write(checklist_path, checklist)
            out_dir = root / "reporting"
            out_dir.mkdir()
            request = {
                "repository_root": str(root), "case_id": "case-1", "arm_id": "arm-1", "seed": 1,
                "stage_id": "reporting_review", "ordinal": 8, "stage_output_dir": str(out_dir),
                "previous_output_manifest_path": str(prior_path), "previous_output_manifest_sha256": _sha(prior_path),
                "config": {"schema_version": "1.0", "stage_id": "reporting_review", "adapter_id": "joint-reporting-review-v1",
                           "checklist_manifest": {"path": "checklist.json", "sha256": _sha(checklist_path)},
                           "report_title_prefix": "Blind evidence report"},
                "published_reference_accessed": False,
            }
            output = reporting_review_stage_adapter(request, AtomicStageBudgetMeter({"max_provider_calls": 0, "max_input_tokens": 0, "max_output_tokens": 0, "wall_seconds": 10}))
            validate_document(output, "joint_lifecycle_stage_output")
            state_path = next(Path(row["path"]) for row in output["artifacts"] if row["artifact_id"] == "reporting_state")
            state = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertTrue(state["all_checklist_items_accounted_for"])
            statuses = {row["item_id"]: row["status"] for row in state["checklist_audit"]}
            self.assertEqual(statuses, {"title": "reported", "search": "reported", "data": "reported", "excluded": "reported", "funding": "not_reported"})
            self.assertEqual(state["checklist_manifest_artifact"]["sha256"], _sha(checklist_path))
            self.assertEqual(state["checklist_source_artifacts"][0]["sha256"], _sha(root / "certainty.json"))
            self.assertFalse(state["published_reference_accessed"])

    def test_living_update_admits_only_exact_interval_and_quarantines_unknown_date(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            root = Path(tmp)
            certainty_output_path, _ = self._chain(root)
            checklist_path = root / "checklist.json"
            _write(checklist_path, {
                "schema_version": "1.0", "manifest_id": "reporting-fixture-v1", "guideline": "licensed fixture",
                "version": "1", "source_url": "https://example.org/checklist", "license_or_permission": "test fixture",
                "source_artifacts": [{"path": "certainty.json", "sha256": _sha(root / "certainty.json")}],
                "items": [{"item_id": "title", "required_section": "title", "requirement": "Report a title.", "coverage_rule_id": "title"}],
            })
            report_dir = root / "reporting"
            report_dir.mkdir()
            report_output = reporting_review_stage_adapter({
                "repository_root": str(root), "case_id": "case-1", "arm_id": "arm-1", "seed": 1,
                "stage_id": "reporting_review", "ordinal": 8, "stage_output_dir": str(report_dir),
                "previous_output_manifest_path": str(certainty_output_path), "previous_output_manifest_sha256": _sha(certainty_output_path),
                "config": {"schema_version": "1.0", "stage_id": "reporting_review", "adapter_id": "joint-reporting-review-v1",
                           "checklist_manifest": {"path": "checklist.json", "sha256": _sha(checklist_path)}, "report_title_prefix": "Blind report"},
                "published_reference_accessed": False,
            }, AtomicStageBudgetMeter({"max_provider_calls": 0, "max_input_tokens": 0, "max_output_tokens": 0, "wall_seconds": 10}))
            report_manifest_path = root / "reporting-output.json"
            _write(report_manifest_path, {"stage_output": report_output})
            living_dir = root / "living"
            living_dir.mkdir()

            def searcher(engine: str, query: str, maximum: int, raw_dir: Path):
                self.assertIn('"2020-06-08"[Date - Publication] : "2020-07-01"[Date - Publication]', query)
                return ([
                    {"record_id": "new-1", "source": "pubmed", "source_record_id": "2", "pmid": "2", "first_publication_date": "2020-06-30"},
                    {"record_id": "late-1", "source": "pubmed", "source_record_id": "3", "pmid": "3", "first_publication_date": "2020-07-02"},
                    {"record_id": "unknown-1", "source": "pubmed", "source_record_id": "4", "pmid": "4", "first_publication_date": None},
                ], {"provider_calls": 1})

            output = living_update_stage_adapter({
                "repository_root": str(root), "case_id": "case-1", "arm_id": "arm-1", "seed": 1,
                "stage_id": "living_update", "ordinal": 9, "stage_output_dir": str(living_dir), "created_at_utc": TIMESTAMP,
                "previous_output_manifest_path": str(report_manifest_path), "previous_output_manifest_sha256": _sha(report_manifest_path),
                "config": {"schema_version": "1.0", "stage_id": "living_update", "adapter_id": "joint-living-update-v1",
                           "source_id": "pubmed", "engine": "pubmed",
                           "update_cutoff": "2020-07-01", "maximum_records": 100},
                "published_reference_accessed": False,
            }, AtomicStageBudgetMeter({"max_provider_calls": 1, "max_input_tokens": 0, "max_output_tokens": 0, "wall_seconds": 10}), searcher=searcher)
            state_path = next(Path(row["path"]) for row in output["artifacts"] if row["artifact_id"] == "living_update_state")
            state = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(state["update_search_audit"]["admitted_count"], 1)
            self.assertEqual(state["update_search_audit"]["quarantined_count"], 2)
            self.assertEqual([row["canonical_id"] for row in state["delta"]["changes"]], ["pmid:2"])
            self.assertEqual(state["delta"]["required_actions"], ["screen_new_records", "human_triage"])


if __name__ == "__main__":
    unittest.main()
