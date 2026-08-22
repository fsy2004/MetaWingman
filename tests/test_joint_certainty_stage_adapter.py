from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from metawingman.scripts.metawingman_core.joint_certainty_stage_adapter import certainty_claims_stage_adapter
from metawingman.scripts.metawingman_core.joint_lifecycle_runner import AtomicStageBudgetMeter
from metawingman.scripts.metawingman_core.schema_guard import validate_document


ROOT = Path(__file__).resolve().parents[1]
TIMESTAMP = "2026-08-22T12:00:00Z"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


class JointCertaintyStageAdapterTests(unittest.TestCase):
    def test_nonpooled_result_is_conservatively_downgraded_and_claim_remains_human_pending(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            root = Path(tmp)
            lineage = {
                "estimands": [{"estimand_id": "e1", "population": "adults", "contrast": "A versus B", "outcome": "response", "time_window": "8 weeks"}],
                "results": [{"result_id": "r1"}],
            }
            lineage_path = root / "lineage.json"
            _write(lineage_path, lineage)
            appraisal = {
                "lineage_state_artifact": {"path": str(lineage_path), "sha256": _sha(lineage_path)},
                "appraisal_dossiers": [{"dossier_id": "d1", "judge_recommendation": {"judgment": "low_concern_candidate", "abstained": False}}],
                "missing_evidence_matrix": {"judge_recommendation": {"abstained": False}},
            }
            appraisal_path = root / "appraisal.json"
            _write(appraisal_path, appraisal)
            input_path = root / "analysis-input.json"
            _write(input_path, {"frozen": True})
            synthesis = {
                "schema_version": "1.0", "stage_id": "freeze_synthesis", "case_id": "case-1", "arm_id": "arm-1", "seed": 1,
                "appraisal_state_artifact": {"path": str(appraisal_path), "sha256": _sha(appraisal_path)},
                "protocol_artifact": {"path": str(input_path), "sha256": _sha(input_path)},
                "analysis_input_artifact": {"path": str(input_path), "sha256": _sha(input_path)},
                "analysis_input_frozen_before_execution": True, "requested_route_id": "pairwise_random_effects",
                "executed_route_id": "swim_structured_synthesis", "effect_estimates": [],
                "synthesis_result": {"status": "structured_without_pooling", "pooled_effect": None},
                "software_bindings": {}, "published_reference_accessed": False,
            }
            synthesis_path = root / "synthesis.json"
            _write(synthesis_path, synthesis)
            validate_document(synthesis, "joint_synthesis_stage_state")
            prior = {"stage_output": {"state_artifact_id": "synthesis_state", "artifacts": [{"artifact_id": "synthesis_state", "path": str(synthesis_path), "sha256": _sha(synthesis_path), "media_type": "application/json", "role": "stage_state"}]}}
            prior_path = root / "prior.json"
            _write(prior_path, prior)
            config = {
                "schema_version": "1.0", "stage_id": "certainty_interpretation",
                "adapter_id": "joint-conservative-certainty-claims-v1", "initial_certainty": "high",
                "inconsistency_i2_threshold": 60, "decision_threshold": 0,
                "framework_label": "GRADE-informed preregistered evaluation rubric v1",
            }
            output_dir = root / "certainty"
            output_dir.mkdir()
            request = {"case_id": "case-1", "arm_id": "arm-1", "seed": 1,
                "stage_id": "certainty_interpretation", "ordinal": 7, "stage_output_dir": str(output_dir),
                "previous_output_manifest_path": str(prior_path), "previous_output_manifest_sha256": _sha(prior_path),
                "created_at_utc": TIMESTAMP, "config": config, "published_reference_accessed": False}
            output = certainty_claims_stage_adapter(
                request, AtomicStageBudgetMeter({"max_provider_calls": 0, "max_input_tokens": 0, "max_output_tokens": 0, "wall_seconds": 10})
            )
            validate_document(output, "joint_lifecycle_stage_output")
            state_path = next(Path(x["path"]) for x in output["artifacts"] if x["artifact_id"] == "certainty_claims_state")
            state = json.loads(state_path.read_text())
            validate_document(state, "joint_certainty_stage_state")
            self.assertEqual(state["certainty_assessment"]["judgment"], "moderate")
            self.assertEqual(state["claims"][0]["status"], "accepted")
            self.assertEqual(state["claims"][0]["human_responsibility"]["status"], "pending")


if __name__ == "__main__":
    unittest.main()
