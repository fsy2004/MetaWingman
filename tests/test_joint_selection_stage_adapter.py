from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from metawingman.scripts.metawingman_core.joint_lifecycle_runner import AtomicStageBudgetMeter
from metawingman.scripts.metawingman_core.joint_selection_stage_adapter import complete_record_selection_stage_adapter
from metawingman.scripts.metawingman_core.model_provider import ProviderResult
from metawingman.scripts.metawingman_core.protocol_compiler import compile_protocol
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
        rows = [
            {"record_id": "include", "criteria": [{
                "criterion_id": "population-01", "decision": "met",
                "evidence_quote": "adults with depression", "confidence": 0.95,
            }]},
            {"record_id": "exclude", "criteria": [{
                "criterion_id": "population-01", "decision": "not_met",
                "evidence_quote": "children with anxiety", "confidence": 0.95,
            }]},
            {"record_id": "unclear", "criteria": [{
                "criterion_id": "population-01", "decision": "not_reported",
                "evidence_quote": "", "confidence": 0.5,
            }]},
        ]
        content = json.dumps({"records": rows})
        return ProviderResult(
            provider="fixture", model="deepseek-v4-flash", finish_reason="stop",
            content=content, content_sha256=hashlib.sha256(content.encode()).hexdigest(),
            prompt_tokens=200, completion_tokens=100, total_tokens=300,
            reasoning_tokens=0, system_fingerprint=None, credential_source="test",
        )


class JointSelectionStageAdapterTests(unittest.TestCase):
    def test_all_records_receive_anchored_include_exclude_or_abstain_decisions(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            root = Path(tmp)
            criteria_candidate = {
                "protocol_version": "1.0", "status": "frozen", "criteria": [{
                    "criterion_id": "population-01", "domain": "population",
                    "label": "Adults with depression", "predicate": {
                        "field": "population", "operator": "contains",
                        "value": "adults with depression", "unit": None,
                        "normalization": "casefold_whitespace",
                    }, "missing_policy": "unclear", "full_text_required": False,
                    "source_section": "frozen protocol",
                }],
            }
            compiled = compile_protocol(criteria_candidate)
            self.assertTrue(compiled.ready_to_freeze)
            criteria_path = root / "criteria.json"
            _write(criteria_path, compiled.document)
            protocol_path = root / "protocol.json"
            _write(protocol_path, {"status": "frozen", "protocol_version": "1.0"})
            search_state = {
                "schema_version": "1.0", "stage_id": "search_retrieval", "case_id": "case-1",
                "arm_id": "arm-1", "seed": 20260820, "acquisition_policy": "fixed_generic",
                "historical_cutoff": "2020-06-07",
                "protocol_artifact": {"path": str(protocol_path), "sha256": _sha(protocol_path)},
                "criteria_artifact": {"path": str(criteria_path), "sha256": _sha(criteria_path)},
                "records": [
                    {"record_id": "include", "title": "Trial in adults with depression", "abstract": "Exercise was tested."},
                    {"record_id": "exclude", "title": "Study in children with anxiety", "abstract": "An observational report."},
                    {"record_id": "unclear", "title": "Exercise trial", "abstract": "Population was not stated."},
                ],
                "quarantined_records": [], "search_audits": [], "known_item_recall": 1.0,
                "source_family_count": 1, "risk_loop_result": None,
                "published_reference_accessed": False,
            }
            search_path = root / "search-state.json"
            _write(search_path, search_state)
            validate_document(search_state, "joint_search_stage_state")
            prior = {"stage_output": {"state_artifact_id": "search_state", "artifacts": [{
                "artifact_id": "search_state", "path": str(search_path), "sha256": _sha(search_path),
                "media_type": "application/json", "role": "stage_state",
            }]}}
            prior_path = root / "prior.json"
            _write(prior_path, prior)
            provider_config_path = root / "provider.json"
            _write(provider_config_path, {"fixture": True})
            config = {
                "schema_version": "1.0", "stage_id": "selection",
                "adapter_id": "joint-complete-record-selection-v1",
                "provider_config": {
                    "path": provider_config_path.relative_to(ROOT).as_posix(),
                    "sha256": _sha(provider_config_path),
                },
                "batch_size": 10, "confidence_floor": 0.8,
                "maximum_input_tokens_per_call": 1000,
                "maximum_output_tokens_per_call": 500, "thinking": False,
            }
            output_dir = root / "selection"
            output_dir.mkdir()
            request = {
                "case_id": "case-1", "arm_id": "arm-1", "seed": 20260820,
                "stage_id": "selection", "ordinal": 3, "repository_root": str(ROOT),
                "stage_output_dir": str(output_dir), "previous_output_manifest_path": str(prior_path),
                "previous_output_manifest_sha256": _sha(prior_path), "created_at_utc": TIMESTAMP,
                "config": config, "published_reference_accessed": False,
            }
            output = complete_record_selection_stage_adapter(
                request,
                AtomicStageBudgetMeter({"max_provider_calls": 1, "max_input_tokens": 1000, "max_output_tokens": 500, "wall_seconds": 10}),
                provider_builder=lambda _: FakeProvider(),
            )
            validate_document(output, "joint_lifecycle_stage_output")
            state_path = next(Path(x["path"]) for x in output["artifacts"] if x["artifact_id"] == "selection_state")
            state = json.loads(state_path.read_text())
            validate_document(state, "joint_selection_stage_state")
            self.assertEqual(state["include_record_ids"], ["include"])
            self.assertEqual(state["exclude_record_ids"], ["exclude"])
            self.assertEqual(state["abstain_record_ids"], ["unclear"])
            self.assertTrue(state["all_records_accounted_for"])


if __name__ == "__main__":
    unittest.main()
