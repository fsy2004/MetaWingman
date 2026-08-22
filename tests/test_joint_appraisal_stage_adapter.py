from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from metawingman.scripts.metawingman_core.joint_appraisal_stage_adapter import appraisal_missing_evidence_stage_adapter
from metawingman.scripts.metawingman_core.joint_lifecycle_runner import AtomicStageBudgetMeter
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
            "domains": [{
                "domain_id": "domain-1", "questions": [{
                    "question_id": "q-1", "answer": "yes",
                    "evidence_quote": "computer-generated random sequence", "rationale": "Random sequence reported.",
                }], "proposal": "low concern", "rationale": "Anchored randomization evidence.",
            }], "overall_judgment": "low concern", "overall_rationale": "All available signals were favorable.",
        })
        return ProviderResult(
            provider="fixture", model="deepseek-v4-flash", finish_reason="stop", content=content,
            content_sha256=hashlib.sha256(content.encode()).hexdigest(), prompt_tokens=200,
            completion_tokens=80, total_tokens=280, reasoning_tokens=0,
            system_fingerprint=None, credential_source="test",
        )


class JointAppraisalStageAdapterTests(unittest.TestCase):
    def test_exact_questions_model_proposal_and_deterministic_opposition_form_ready_dossier(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            root = Path(tmp)
            protocol_path = root / "protocol.json"
            _write(protocol_path, {"status": "frozen"})
            fulltext_path = root / "fulltext.txt"
            fulltext_path.write_text("Allocation used a computer-generated random sequence.", encoding="utf-8")
            lineage = {
                "schema_version": "1.0", "stage_id": "data_lineage", "case_id": "case-1", "arm_id": "arm-1", "seed": 1,
                "selection_state_artifact": {"path": str(protocol_path), "sha256": _sha(protocol_path)},
                "protocol_artifact": {"path": str(protocol_path), "sha256": _sha(protocol_path)},
                "documents": [{"record_id": "record-1", "status": "resolved", "normalized_text_artifact": {"path": str(fulltext_path), "sha256": _sha(fulltext_path), "truncated": False}}],
                "anchors": [{"anchor_id": "anchor-1"}], "reports": [{"report_id": "report-1", "record_id": "record-1"}],
                "studies": [{"study_id": "study-1"}], "results": [{"result_id": "result-1", "study_id": "study-1", "estimand_id": "estimand-1"}],
                "estimands": [{"estimand_id": "estimand-1", "population": "adults", "contrast": "A versus B", "outcome": "response", "time_window": "8 weeks", "effect_measure": "risk ratio"}],
                "extraction_candidates": [{"candidate_id": "candidate-1", "result_id": "result-1", "anchor_ids": ["anchor-1"]}],
                "lineage_edges": [],
                "full_text_assessments": [{"record_id": "record-1", "decision": "include", "criterion_assessments": []}],
                "full_text_include_record_ids": ["record-1"], "full_text_exclude_record_ids": [],
                "full_text_abstain_record_ids": [], "full_text_exclusion_citations": [],
                "all_full_text_records_accounted_for": True,
                "unresolved_record_ids": [], "complete_verified_lineage_count": 1,
                "model_provenance": [], "published_reference_accessed": False,
            }
            lineage_path = root / "lineage.json"
            _write(lineage_path, lineage)
            validate_document(lineage, "joint_lineage_stage_state")
            prior = {"stage_output": {"state_artifact_id": "lineage_state", "artifacts": [{"artifact_id": "lineage_state", "path": str(lineage_path), "sha256": _sha(lineage_path), "media_type": "application/json", "role": "stage_state"}]}}
            prior_path = root / "prior.json"
            _write(prior_path, prior)
            framework = {
                "schema_version": "1.0", "adapter_id": "fixture-rob", "adapter_version": "1.0",
                "framework": {"name": "Fixture RoB", "version": "1", "organization": "Fixture", "source_url": "https://example.org/rob", "verified_at_utc": TIMESTAMP},
                "supported_review_families": ["intervention"], "target_granularity": "result",
                "domains": [{"domain_id": "domain-1", "label": "Randomization", "signaling_question_ids": ["q-1"], "notes": "fixture"}],
                "allowed_answers": ["yes", "probably_yes", "probably_no", "no", "no_information", "not_applicable"],
                "final_human_signature_required": True, "status": "verified",
            }
            framework_path = root / "framework.json"
            _write(framework_path, framework)
            question_manifest = {"schema_version": "1.0", "manifest_id": "fixture-questions", "framework_adapter_id": "fixture-rob", "license_or_permission": "test fixture", "questions": [{"question_id": "q-1", "question": "Was allocation randomized?"}]}
            question_path = root / "questions.json"
            _write(question_path, question_manifest)
            provider_path = root / "provider.json"
            _write(provider_path, {"fixture": True})
            bind = lambda path: {"path": path.relative_to(ROOT).as_posix(), "sha256": _sha(path)}
            config = {
                "schema_version": "1.0", "stage_id": "appraisal", "adapter_id": "joint-appraisal-missing-evidence-v1",
                "provider_config": bind(provider_path), "framework_adapter": bind(framework_path), "question_manifest": bind(question_path),
                "review_family": "intervention", "maximum_input_tokens_per_call": 1000,
                "maximum_output_tokens_per_call": 500, "thinking": False,
            }
            output_dir = root / "appraisal"
            output_dir.mkdir()
            request = {"case_id": "case-1", "arm_id": "arm-1", "seed": 1, "stage_id": "appraisal", "ordinal": 5,
                "repository_root": str(ROOT), "stage_output_dir": str(output_dir), "previous_output_manifest_path": str(prior_path),
                "previous_output_manifest_sha256": _sha(prior_path), "created_at_utc": TIMESTAMP, "config": config,
                "published_reference_accessed": False}
            output = appraisal_missing_evidence_stage_adapter(
                request, AtomicStageBudgetMeter({"max_provider_calls": 1, "max_input_tokens": 1000, "max_output_tokens": 500, "wall_seconds": 10}),
                provider_builder=lambda _: FakeProvider(),
            )
            validate_document(output, "joint_lifecycle_stage_output")
            self.assertEqual(output["status"], "completed")
            state_path = next(Path(x["path"]) for x in output["artifacts"] if x["artifact_id"] == "appraisal_state")
            state = json.loads(state_path.read_text())
            validate_document(state, "joint_appraisal_stage_state")
            self.assertEqual(state["ready_dossier_count"], 1)
            self.assertEqual(state["appraisal_dossiers"][0]["opposition"]["actor_id"], "exact-span-conservative-opposition-v1")


if __name__ == "__main__":
    unittest.main()
