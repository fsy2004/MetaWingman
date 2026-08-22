from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from metawingman.scripts.metawingman_core.joint_lifecycle_runner import AtomicStageBudgetMeter
from metawingman.scripts.metawingman_core.joint_protocol_stage_adapter import (
    protocol_registration_stage_adapter,
)
from metawingman.scripts.metawingman_core.protocol_compiler import compile_full_protocol
from metawingman.scripts.metawingman_core.schema_guard import validate_document


ROOT = Path(__file__).resolve().parents[1]
TIMESTAMP = "2026-08-22T12:00:00Z"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


class JointProtocolStageAdapterTests(unittest.TestCase):
    def test_compiles_selected_topic_into_a_frozen_operational_protocol(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            root = Path(tmp)
            prior_dir = root / "prior"
            prior_dir.mkdir()
            topic_state = {
                "schema_version": "1.0", "stage_id": "topic_feasibility",
                "case_id": "case-1", "arm_id": "generic", "seed": 20260820,
                "generation_mode": "generic_direct_generation",
                "proposal_batch_sha256": "a" * 64,
                "selection_policy": "generic_llm_order",
                "selected_proposals": [{
                    "proposal_id": "proposal-1", "candidate_id": None,
                    "question_framework": {
                        "population": ["adults with depression"],
                        "intervention_or_exposure": ["exercise"],
                        "comparator": ["usual care"],
                        "outcome": ["depressive symptoms"],
                        "study_design": ["randomised trials"],
                        "synthesis_route": "pairwise random-effects meta-analysis",
                    },
                    "evidence_node_ids": ["pub-1"],
                    "selection_basis": "generic_llm_order",
                }],
                "status": "selected", "reason_codes": ["selected"],
                "published_reference_accessed": False,
            }
            topic_path = prior_dir / "topic-state.json"
            _write(topic_path, topic_state)
            prior_manifest = {
                "stage_output": {
                    "state_artifact_id": "topic_state",
                    "artifacts": [{
                        "artifact_id": "topic_state", "path": str(topic_path),
                        "sha256": _sha(topic_path), "media_type": "application/json",
                        "role": "stage_state",
                    }],
                }
            }
            prior_path = prior_dir / "output-manifest.json"
            _write(prior_path, prior_manifest)
            query_path = root / "pubmed-query.txt"
            query_path.write_text("depression AND exercise\n", encoding="utf-8")
            config = {
                "schema_version": "1.0", "stage_id": "protocol_registration",
                "adapter_id": "joint-protocol-registration-v1",
                "profile_id": "intervention_pairwise",
                "historical_cutoff": "2020-06-07",
                "allowed_synthesis_routes": ["pairwise random-effects meta-analysis"],
                "decision_context": {
                    "decision": "Choose whether exercise should be used for depressive symptoms.",
                    "stakeholders": ["patients", "clinicians"],
                    "setting": "clinical and community care",
                    "intended_use": "treatment decision support",
                },
                "effect_measure": "standardized mean difference",
                "time_window": "post-intervention",
                "population_summary": "average effect among eligible participants",
                "analysis_unit": "participant",
                "decision_threshold": {
                    "threshold_id": "minimal-important-effect", "type": "minimal_importance",
                    "value": 0.2, "unit": "standard deviation", "direction": "greater",
                    "rationale": "Frozen generic minimally important standardized effect.",
                },
                "poolability_rule": "Pool only clinically compatible estimands and report heterogeneity.",
                "source_plan": [{
                    "source_id": "pubmed", "source_type": "bibliographic_database",
                    "database": "MEDLINE", "platform": "PubMed", "access_route": "public_api",
                    "required": True,
                    "query_template_id": "pubmed_pico_date_v1",
                    "coverage": "title, abstract, identifiers, and publication dates",
                }],
                "amendment_policy": {
                    "freeze_trigger": "before any search execution",
                    "prospective_change_rule": "version and justify every change before rerun",
                    "post_hoc_label_required": True,
                    "rerun_impact_analysis": True,
                },
            }
            validate_document(config, "joint_protocol_stage_config")
            output_dir = root / "protocol"
            output_dir.mkdir()
            request = {
                "case_id": "case-1", "arm_id": "generic", "seed": 20260820,
                "stage_id": "protocol_registration", "ordinal": 1,
                "repository_root": str(ROOT), "stage_output_dir": str(output_dir),
                "previous_output_manifest_path": str(prior_path),
                "previous_output_manifest_sha256": _sha(prior_path),
                "created_at_utc": TIMESTAMP, "config": config,
                "published_reference_accessed": False,
            }
            meter = AtomicStageBudgetMeter({
                "max_provider_calls": 0, "max_input_tokens": 0,
                "max_output_tokens": 0, "wall_seconds": 5,
            })
            output = protocol_registration_stage_adapter(request, meter)
            validate_document(output, "joint_lifecycle_stage_output")
            self.assertEqual(output["status"], "completed")
            protocol_path = next(
                Path(item["path"]) for item in output["artifacts"]
                if item["artifact_id"] == "protocol"
            )
            protocol = json.loads(protocol_path.read_text())
            validate_document(protocol, "protocol")
            self.assertTrue(compile_full_protocol(protocol).ready_to_freeze)
            self.assertEqual(protocol["status"], "frozen")
            self.assertEqual(protocol["frozen_by"], "preregistered-evaluation-actor")
            generated_query = ROOT / protocol["source_plan"][0]["query_file"]
            query_document = json.loads(generated_query.read_text())
            self.assertIn("adults with depression", query_document["query"])
            self.assertIn("2020-06-07", query_document["query"])
            self.assertEqual(protocol["source_plan"][0]["query_sha256"], _sha(generated_query))


if __name__ == "__main__":
    unittest.main()
