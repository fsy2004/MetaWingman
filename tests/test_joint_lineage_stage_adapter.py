from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from metawingman.scripts.metawingman_core.joint_lifecycle_runner import AtomicStageBudgetMeter
from metawingman.scripts.metawingman_core.joint_lineage_stage_adapter import report_study_result_lineage_stage_adapter
from metawingman.scripts.metawingman_core.model_provider import ProviderResult
from metawingman.scripts.metawingman_core.schema_guard import validate_document


ROOT = Path(__file__).resolve().parents[1]
TIMESTAMP = "2026-08-22T12:00:00Z"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


class FakeProvider:
    credential_source = "test"

    def chat(self, messages, **kwargs):
        content = json.dumps({
            "eligibility": {
                "decision": "include",
                "criterion_assessments": [{
                    "criterion_id": "population-01", "status": "pass",
                    "evidence_quote": "participants responded to exercise", "rationale": "Eligible population and intervention are reported.",
                }],
            },
            "report": {"report_id": "report-1"}, "study": {"study_id": "study-1"},
            "result": {"result_id": "result-1"},
            "estimand": {
                "estimand_id": "estimand-1", "population": "adults with depression",
                "contrast": "exercise versus usual care", "outcome": "response",
                "time_window": "8 weeks", "effect_measure": "risk ratio",
            },
            "extractions": [{
                "field": "events_intervention", "raw": 10, "normalized": 10,
                "data_type": "integer", "unit": None,
                "evidence_quote": "10 of 40 participants responded", "confidence": 0.95,
            }],
        })
        return ProviderResult(
            provider="fixture", model="deepseek-v4-flash", finish_reason="stop",
            content=content, content_sha256=hashlib.sha256(content.encode()).hexdigest(),
            prompt_tokens=300, completion_tokens=140, total_tokens=440, reasoning_tokens=0,
            system_fingerprint=None, credential_source="test",
        )


class FakeExclusionProvider(FakeProvider):
    def chat(self, messages, **kwargs):
        content = json.dumps({
            "eligibility": {
                "decision": "exclude",
                "criterion_assessments": [{
                    "criterion_id": "population-01", "status": "fail",
                    "evidence_quote": "participants were healthy volunteers",
                    "rationale": "The frozen population criterion is not met.",
                }],
            },
            "report": None, "study": None, "result": None, "estimand": None,
            "extractions": [],
        })
        return ProviderResult(
            provider="fixture", model="deepseek-v4-flash", finish_reason="stop",
            content=content, content_sha256=hashlib.sha256(content.encode()).hexdigest(),
            prompt_tokens=250, completion_tokens=80, total_tokens=330, reasoning_tokens=0,
            system_fingerprint=None, credential_source="test",
        )


class JointLineageStageAdapterTests(unittest.TestCase):
    def _fixture(self, root: Path, provider) -> tuple[dict, AtomicStageBudgetMeter]:
        criteria_path = root / "criteria.json"
        _write(criteria_path, {
            "schema_version": "1.0", "protocol_version": "1.0", "status": "frozen",
            "criteria": [{
                "criterion_id": "population-01", "domain": "population", "label": "Adults with depression",
                "predicate": {"field": "population", "operator": "contains", "value": "depression", "unit": None, "normalization": "casefold"},
                "missing_policy": "unclear", "full_text_required": True, "status": "operational", "source_section": "eligibility",
            }],
        })
        protocol_path = root / "protocol.json"
        _write(protocol_path, {"status": "frozen", "protocol_version": "1.0"})
        search_state = {
                "schema_version": "1.0", "stage_id": "search_retrieval", "case_id": "case-1",
                "arm_id": "arm-1", "seed": 20260820, "acquisition_policy": "fixed_generic",
                "historical_cutoff": "2020-06-07",
                "protocol_artifact": {"path": str(protocol_path), "sha256": _sha(protocol_path)},
                "criteria_artifact": {"path": str(criteria_path), "sha256": _sha(criteria_path)},
                "records": [{"record_id": "record-1", "title": "Trial", "abstract": "", "pmcid": "PMC1"}],
                "quarantined_records": [], "search_audits": [], "known_item_recall": 1.0,
                "source_family_count": 1, "risk_loop_result": None, "published_reference_accessed": False,
        }
        search_path = root / "search.json"
        _write(search_path, search_state)
        selection_state = {
                "schema_version": "1.0", "stage_id": "selection", "case_id": "case-1",
                "arm_id": "arm-1", "seed": 20260820,
                "search_state_artifact": {"path": str(search_path), "sha256": _sha(search_path)},
                "protocol_artifact": {"path": str(protocol_path), "sha256": _sha(protocol_path)},
                "criteria_artifact": {"path": str(criteria_path), "sha256": _sha(criteria_path)},
                "record_ids": ["record-1"], "assessments": [], "include_record_ids": ["record-1"],
                "exclude_record_ids": [], "abstain_record_ids": [], "all_records_accounted_for": True,
                "model_provenance": [], "published_reference_accessed": False,
        }
        selection_path = root / "selection.json"
        _write(selection_path, selection_state)
        prior = {"stage_output": {"state_artifact_id": "selection_state", "artifacts": [{
                "artifact_id": "selection_state", "path": str(selection_path), "sha256": _sha(selection_path),
                "media_type": "application/json", "role": "stage_state",
        }]}}
        prior_path = root / "prior.json"
        _write(prior_path, prior)
        provider_path = root / "provider.json"
        _write(provider_path, {"fixture": True})
        config = {
                "schema_version": "1.0", "stage_id": "data_lineage",
                "adapter_id": "joint-report-study-result-estimand-v1",
                "provider_config": {"path": provider_path.relative_to(ROOT).as_posix(), "sha256": _sha(provider_path)},
                "maximum_fulltext_characters": 10000, "maximum_input_tokens_per_call": 1000,
                "maximum_output_tokens_per_call": 500, "thinking": False,
        }
        output_dir = root / "lineage"
        output_dir.mkdir()
        request = {
                "case_id": "case-1", "arm_id": "arm-1", "seed": 20260820,
                "stage_id": "data_lineage", "ordinal": 4, "repository_root": str(ROOT),
                "stage_output_dir": str(output_dir), "previous_output_manifest_path": str(prior_path),
                "previous_output_manifest_sha256": _sha(prior_path), "created_at_utc": TIMESTAMP,
                "config": config, "published_reference_accessed": False,
        }

        def resolver(record, outdir):
            return "At 8 weeks, 10 of 40 participants responded to exercise.", {
                "record_id": record["record_id"], "status": "resolved", "access_route": "fixture",
            }

        request["_provider"] = provider
        request["_resolver"] = resolver
        return request, AtomicStageBudgetMeter({"max_provider_calls": 1, "max_input_tokens": 1000, "max_output_tokens": 500, "wall_seconds": 10})

    def test_fulltext_exact_span_builds_verified_report_study_result_estimand_chain(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            root = Path(tmp)
            request, meter = self._fixture(root, FakeProvider())
            output = report_study_result_lineage_stage_adapter(
                request, meter, provider_builder=lambda _: request["_provider"], fulltext_resolver=request["_resolver"],
            )
            validate_document(output, "joint_lifecycle_stage_output")
            self.assertEqual(output["status"], "completed")
            state_path = next(Path(x["path"]) for x in output["artifacts"] if x["artifact_id"] == "lineage_state")
            state = json.loads(state_path.read_text())
            validate_document(state, "joint_lineage_stage_state")
            self.assertEqual(state["complete_verified_lineage_count"], 1)
            self.assertEqual(state["full_text_include_record_ids"], ["record-1"])
            self.assertTrue(state["all_full_text_records_accounted_for"])
            self.assertEqual(len(state["lineage_edges"]), 2)
            self.assertEqual(state["extraction_candidates"][0]["verification"]["verified_by"], "exact-span-value-verifier-v1")

    def test_fulltext_exclusion_requires_exact_quote_and_never_builds_lineage(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            root = Path(tmp)
            request, meter = self._fixture(root, FakeExclusionProvider())

            def resolver(record, outdir):
                return "The participants were healthy volunteers without depression.", {
                    "record_id": record["record_id"], "status": "resolved", "access_route": "fixture",
                }

            output = report_study_result_lineage_stage_adapter(
                request, meter, provider_builder=lambda _: request["_provider"], fulltext_resolver=resolver,
            )
            state_path = next(Path(x["path"]) for x in output["artifacts"] if x["artifact_id"] == "lineage_state")
            state = json.loads(state_path.read_text())
            self.assertEqual(state["full_text_exclude_record_ids"], ["record-1"])
            self.assertEqual(state["full_text_include_record_ids"], [])
            self.assertEqual(state["reports"], [])
            self.assertEqual(state["extraction_candidates"], [])
            self.assertEqual(state["full_text_exclusion_citations"][0]["criterion_id"], "population-01")
            self.assertIn("healthy volunteers", state["full_text_exclusion_citations"][0]["evidence_quote"])
            self.assertTrue(state["all_full_text_records_accounted_for"])


if __name__ == "__main__":
    unittest.main()
