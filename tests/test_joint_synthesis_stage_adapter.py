from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from metawingman.scripts.metawingman_core.joint_lifecycle_runner import AtomicStageBudgetMeter
from metawingman.scripts.metawingman_core.joint_synthesis_stage_adapter import analysis_freeze_synthesis_stage_adapter
from metawingman.scripts.metawingman_core.schema_guard import validate_document


ROOT = Path(__file__).resolve().parents[1]
TIMESTAMP = "2026-08-22T12:00:00Z"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


class JointSynthesisStageAdapterTests(unittest.TestCase):
    def test_freezes_inputs_and_uses_structured_no_pooling_when_verified_effect_shape_is_insufficient(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            root = Path(tmp)
            protocol_path = root / "protocol.json"
            _write(protocol_path, {"status": "frozen"})
            candidate = {
                "schema_version": "1.0", "candidate_id": "candidate-1", "document_id": "document-1",
                "report_id": "report-1", "study_id": "study-1", "result_id": "result-1",
                "field": "events_intervention", "value": {"raw": 10, "normalized": 10, "data_type": "integer"},
                "unit": None, "anchor_ids": ["anchor-1"], "channel": "native_text",
                "created_by": {"type": "model", "id": "deepseek-v4-flash", "version": "frozen"},
                "confidence": 0.9, "derivation": {"method": "direct", "formula_or_rule": "direct", "input_candidate_ids": [], "tool": "fixture", "tool_version": "1"},
                "status": "accepted", "verification": {"method": "source_recheck", "status": "passed", "verified_by": "fixture", "independently_derived": False, "verified_at_utc": TIMESTAMP, "discrepancy": ""},
                "created_at_utc": TIMESTAMP,
            }
            lineage = {
                "schema_version": "1.0", "stage_id": "data_lineage", "case_id": "case-1", "arm_id": "arm-1", "seed": 1,
                "selection_state_artifact": {"path": str(protocol_path), "sha256": _sha(protocol_path)},
                "protocol_artifact": {"path": str(protocol_path), "sha256": _sha(protocol_path)},
                "documents": [], "anchors": [], "reports": [], "studies": [{"study_id": "study-1"}],
                "results": [{"result_id": "result-1", "study_id": "study-1", "estimand_id": "estimand-1"}],
                "estimands": [{"estimand_id": "estimand-1", "outcome": "response"}],
                "extraction_candidates": [candidate], "lineage_edges": [], "unresolved_record_ids": [],
                "complete_verified_lineage_count": 1, "model_provenance": [], "published_reference_accessed": False,
            }
            lineage_path = root / "lineage.json"
            _write(lineage_path, lineage)
            appraisal = {
                "schema_version": "1.0", "stage_id": "appraisal", "case_id": "case-1", "arm_id": "arm-1", "seed": 1,
                "lineage_state_artifact": {"path": str(lineage_path), "sha256": _sha(lineage_path)},
                "protocol_artifact": {"path": str(protocol_path), "sha256": _sha(protocol_path)},
                "framework_adapter_sha256": "a" * 64, "appraisal_dossiers": [{"dossier_id": "dossier-1"}],
                "missing_evidence_matrix": {"matrix_id": "matrix-1", "judge_recommendation": {"abstained": False}},
                "deterministic_opposition_policy": "exact-span-plus-conservative-domain-logic-v1",
                "ready_dossier_count": 1, "published_reference_accessed": False,
            }
            appraisal_path = root / "appraisal.json"
            _write(appraisal_path, appraisal)
            prior = {"stage_output": {"state_artifact_id": "appraisal_state", "artifacts": [{"artifact_id": "appraisal_state", "path": str(appraisal_path), "sha256": _sha(appraisal_path), "media_type": "application/json", "role": "stage_state"}]}}
            prior_path = root / "prior.json"
            _write(prior_path, prior)
            r_path = ROOT / "metawingman/scripts/r/adapters/run_verified_effects.R"
            manifest_path = root / "toolkit-manifest.json"
            _write(manifest_path, {"fixture": True})
            bind = lambda path: {"path": path.relative_to(ROOT).as_posix(), "sha256": _sha(path)}
            config = {
                "schema_version": "1.0", "stage_id": "freeze_synthesis", "adapter_id": "joint-analysis-freeze-synthesis-v1",
                "route_id": "pairwise_random_effects", "effect_measure": "log_risk_ratio",
                "direction": "higher_favors_intervention", "minimum_effects_for_pooling": 2,
                "method": "REML", "knha": True, "r_adapter": bind(r_path), "toolkit_manifest": bind(manifest_path),
            }
            output_dir = root / "synthesis"
            output_dir.mkdir()
            calls = []
            request = {"case_id": "case-1", "arm_id": "arm-1", "seed": 1, "stage_id": "freeze_synthesis", "ordinal": 6,
                "repository_root": str(ROOT), "stage_output_dir": str(output_dir), "previous_output_manifest_path": str(prior_path),
                "previous_output_manifest_sha256": _sha(prior_path), "created_at_utc": TIMESTAMP, "config": config,
                "published_reference_accessed": False}
            output = analysis_freeze_synthesis_stage_adapter(
                request, AtomicStageBudgetMeter({"max_provider_calls": 0, "max_input_tokens": 0, "max_output_tokens": 0, "wall_seconds": 10}),
                analysis_executor=lambda *args: calls.append(args),
            )
            validate_document(output, "joint_lifecycle_stage_output")
            self.assertEqual(calls, [])
            state_path = next(Path(x["path"]) for x in output["artifacts"] if x["artifact_id"] == "synthesis_state")
            state = json.loads(state_path.read_text())
            validate_document(state, "joint_synthesis_stage_state")
            self.assertTrue(state["analysis_input_frozen_before_execution"])
            self.assertEqual(state["executed_route_id"], "swim_structured_synthesis")
            self.assertIsNone(state["synthesis_result"]["pooled_effect"])


if __name__ == "__main__":
    unittest.main()
