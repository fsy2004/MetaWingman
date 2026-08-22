from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = REPO_ROOT / "metawingman" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from metawingman_core.distillation_readiness import (  # noqa: E402
    audit_distillation_readiness,
)


def sha256_json(value: object) -> str:
    payload = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class DistillationReadinessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.case_id = "development-case"
        self.family_id = "development-family"
        self.registry = {
            "schema_version": "1.0",
            "cases": [{
                "case_id": self.case_id,
                "review_family_id": self.family_id,
                "split": "development",
                "execution_status": "methods_only",
                "training_use": "stage_verified_only",
                "training_stage_readiness": {
                    "protocol": {"status": "verified", "sources": ["https://example.org/protocol"]},
                },
            }],
        }
        self.registry_path = self.root / "case-registry.json"
        self.registry_path.write_text(json.dumps(self.registry), encoding="utf-8")
        self.registry_sha = sha256_json(self.registry)

        self.paths: dict[str, Path] = {}
        for name in (
            "source", "audit", "dataset", "prompt", "tool", "checkpoint", "family-closure",
        ):
            path = self.root / f"{name}.txt"
            path.write_text(f"frozen {name} artifact\n", encoding="utf-8")
            self.paths[name] = path

        self.revocation = {
            "schema_version": "1.0",
            "revision": "rev-1",
            "case_registry_sha256": self.registry_sha,
            "revoked_trace_ids": [],
            "forbidden_value_aliases": [],
        }
        self.revocation_path = self.root / "revocation.json"
        self.revocation_path.write_text(json.dumps(self.revocation), encoding="utf-8")

        self.lineage = {
            "schema_version": "1.0",
            "manifest_id": "lineage-1",
            "case_registry_sha256": self.registry_sha,
            "dataset_bindings": [self._artifact_binding("dataset", "dataset-1")],
            "prompt_bindings": [self._artifact_binding("prompt", "prompt-1")],
            "tool_bindings": [self._artifact_binding("tool", "tool-1")],
            "checkpoint_bindings": [{
                **self._artifact_binding("checkpoint", "checkpoint-1"),
                "teacher_identity": {
                    "provider_id": "DeepSeek API",
                    "model_id": "deepseek/deepseek-v4-flash",
                    "canonical_provider_id": "deepseek",
                    "canonical_model_id": "deepseek-v4-flash",
                },
                "training_family_ids": ["unrelated-training-family"],
                "family_closure": {
                    "status": "verified_target_family_absent",
                    "case_registry_sha256": self.registry_sha,
                    "artifact_path": self.paths["family-closure"].name,
                    "sha256": sha256_file(self.paths["family-closure"]),
                },
            }],
        }
        self.lineage_path = self.root / "lineage.json"
        self.lineage_path.write_text(json.dumps(self.lineage), encoding="utf-8")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _artifact_binding(self, name: str, binding_id: str) -> dict[str, object]:
        return {
            "binding_id": binding_id,
            "artifact_path": self.paths[name].name,
            "sha256": sha256_file(self.paths[name]),
            "case_ids": [self.case_id],
            "family_ids": [self.family_id],
            "stages": ["protocol_registration"],
        }

    def _example(
        self,
        example_id: str = "distill-example-1",
        *,
        outcome: str = "success",
        disposition: str = "positive_demonstration",
        decision_status: str = "accept",
    ) -> dict[str, object]:
        return {
            "schema_version": "1.0",
            "example_id": example_id,
            "case_id": self.case_id,
            "family_id": self.family_id,
            "split": "train",
            "stage": "protocol",
            "canonical_stage": "protocol_registration",
            "input_state": {"question": "bounded pre-cutoff state"},
            "target_action": {"type": "draft_protocol"},
            "target_decision": {"status": decision_status, "reason_codes": ["verified"]},
            "source_anchors": [{"source_id": "source-1", "anchor": "row:1"}],
            "artifact_bindings": {
                "source_artifacts": [{
                    "path": self.paths["source"].name,
                    "sha256": sha256_file(self.paths["source"]),
                }],
                "audit_artifacts": [{
                    "path": self.paths["audit"].name,
                    "sha256": sha256_file(self.paths["audit"]),
                }],
            },
            "reproducibility_bindings": {
                "dataset_sha256": sha256_file(self.paths["dataset"]),
                "prompt_sha256": sha256_file(self.paths["prompt"]),
                "tool_sha256": sha256_file(self.paths["tool"]),
                "checkpoint_sha256": sha256_file(self.paths["checkpoint"]),
            },
            "verification": {
                "status": "verified",
                "verifier_kind": "deterministic_guard",
                "verifier_id": "independent-replay-v1",
                "checks": ["source_anchor_checked"],
            },
            "outcome": outcome,
            "training_disposition": disposition,
            "label_authority": "verified_teacher_trajectory_not_gold",
            "teacher_provider_id": "DeepSeek API",
            "teacher_identity": {
                "provider_id": "DeepSeek API",
                "model_id": "deepseek/deepseek-v4-flash",
                "canonical_provider_id": "deepseek",
                "canonical_model_id": "deepseek-v4-flash",
            },
            "created_at_utc": "2026-08-22T02:30:00Z",
        }

    def _write_export(self, examples: list[dict[str, object]], name: str = "export.json") -> Path:
        document = {
            "schema_version": "1.0",
            "created_at_utc": "2026-08-22T02:30:00Z",
            "governance_status": "governance_only_no_student_trained",
            "policy": {
                key: True for key in (
                    "case_registry_bound", "run_ready_or_verified_stage_only",
                    "development_families_only", "held_out_disabled",
                    "source_anchors_required", "independent_verification_required",
                    "same_provider_self_verification_forbidden",
                    "failed_and_abstained_trajectories_retained",
                    "journal_features_forbidden", "published_reference_is_not_gold",
                    "artifact_hash_binding_required", "canonical_identity_required",
                    "revocation_binding_required", "canonical_ten_stage_lifecycle",
                    "governance_only_no_student_claim",
                    "reproducibility_hashes_required_for_training",
                )
            },
            "case_registry_sha256": self.registry_sha,
            "canonical_case_registry_sha256": self.registry_sha,
            "revocation_binding": {
                "revision": self.revocation["revision"],
                "case_registry_sha256": self.registry_sha,
                "manifest_sha256": sha256_json(self.revocation),
                "revoked_trace_ids_sha256": sha256_json([]),
                "forbidden_value_aliases_sha256": sha256_json([]),
            },
            "summary": {
                "examples": len(examples),
                "families": len({str(item["family_id"]) for item in examples}),
                "failures_retained": sum(item["outcome"] == "failure" for item in examples),
                "abstentions_retained": sum(item["outcome"] == "abstention" for item in examples),
                "trainable_examples": sum(
                    item["training_disposition"] != "audit_only_quarantine" for item in examples
                ),
                "quarantined_examples": sum(
                    item["training_disposition"] == "audit_only_quarantine" for item in examples
                ),
            },
            "examples": examples,
            "examples_sha256": sha256_json(examples),
        }
        path = self.root / name
        path.write_text(json.dumps(document), encoding="utf-8")
        return path

    def _audit(self, exports: list[Path], **overrides: object) -> dict[str, object]:
        arguments = {
            "export_paths": exports,
            "case_registry_path": self.registry_path,
            "lineage_manifest_path": self.lineage_path,
            "revocation_manifest_path": self.revocation_path,
            "artifact_root": self.root,
        }
        arguments.update(overrides)
        return audit_distillation_readiness(**arguments)

    def test_no_real_export_fails_closed_with_zero_trainable_examples(self) -> None:
        report = self._audit([])
        self.assertFalse(report["ready_for_student_training"])
        self.assertEqual(report["counts"]["candidates"]["total"], 0)
        self.assertEqual(report["counts"]["trainable"]["total"], 0)
        self.assertIn("no_frozen_trajectory_exports", report["blockers"])

    def test_fully_bound_positive_example_is_ready(self) -> None:
        report = self._audit([self._write_export([self._example()])])
        self.assertTrue(report["ready_for_student_training"], report["blockers"])
        self.assertEqual(report["counts"]["trainable"]["positive"], 1)
        self.assertEqual(report["counts"]["trainable"]["total"], 1)
        self.assertEqual(report["family_closure"]["verified_families"], [self.family_id])
        self.assertEqual(report["checkpoint_closure"]["verified_checkpoints"], 1)

    def test_counts_positive_negative_abstention_audit_only_and_quarantine(self) -> None:
        audit_only = self._example(
            "distill-audit-only", outcome="failure",
            disposition="audit_only_quarantine", decision_status="reject",
        )
        audit_only["reproducibility_bindings"] = {
            "dataset_sha256": None, "prompt_sha256": None,
            "tool_sha256": None, "checkpoint_sha256": None,
        }
        quarantine = self._example(
            "distill-quarantine", outcome="failure",
            disposition="audit_only_quarantine", decision_status="quarantine",
        )
        quarantine["reproducibility_bindings"] = copy.deepcopy(
            audit_only["reproducibility_bindings"]
        )
        examples = [
            self._example("distill-positive"),
            self._example(
                "distill-negative", outcome="failure",
                disposition="negative_decision", decision_status="reject",
            ),
            self._example(
                "distill-abstention", outcome="abstention",
                disposition="abstention_demonstration", decision_status="abstain",
            ),
            audit_only,
            quarantine,
        ]
        report = self._audit([self._write_export(examples)])
        self.assertEqual(report["counts"]["candidates"], {
            "positive": 1, "negative": 1, "abstention": 1,
            "audit_only": 1, "quarantine": 1, "total": 5,
        })
        self.assertEqual(report["counts"]["trainable"], {
            "positive": 1, "negative": 1, "abstention": 1,
            "audit_only": 0, "quarantine": 0, "total": 3,
        })

    def test_registry_training_use_and_heldout_split_are_enforced(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["cases"][0]["split"] = "held_out"
        registry["cases"][0]["training_use"] = "forbidden"
        self.registry_path.write_text(json.dumps(registry), encoding="utf-8")
        self.registry_sha = sha256_json(registry)
        example = self._example()
        export = self._write_export([example])
        report = self._audit([export])
        self.assertFalse(report["ready_for_student_training"])
        self.assertEqual(report["counts"]["trainable"]["total"], 0)
        self.assertTrue(any("held_out_case_forbidden" in item for item in report["blockers"]))

    def test_negative_or_abstention_only_case_blocks_positive(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["cases"][0]["training_use"] = "negative_or_abstention_only"
        registry["cases"][0].pop("training_stage_readiness")
        self.registry_path.write_text(json.dumps(registry), encoding="utf-8")
        self.registry_sha = sha256_json(registry)
        self._rebind_inputs_to_registry()
        positive = self._write_export([self._example()], "positive.json")
        report = self._audit([positive])
        self.assertFalse(report["ready_for_student_training"])
        self.assertEqual(report["counts"]["trainable"]["positive"], 0)
        self.assertTrue(any("positive_training_forbidden" in item for item in report["blockers"]))

        negative = self._example(
            "distill-negative", outcome="failure",
            disposition="negative_decision", decision_status="reject",
        )
        negative_export = self._write_export([negative], "negative.json")
        negative_report = self._audit([negative_export])
        self.assertTrue(negative_report["ready_for_student_training"], negative_report["blockers"])
        self.assertEqual(negative_report["counts"]["trainable"]["negative"], 1)

    def _rebind_inputs_to_registry(self) -> None:
        self.revocation["case_registry_sha256"] = self.registry_sha
        self.revocation_path.write_text(json.dumps(self.revocation), encoding="utf-8")
        self.lineage["case_registry_sha256"] = self.registry_sha
        for checkpoint in self.lineage["checkpoint_bindings"]:
            checkpoint["family_closure"]["case_registry_sha256"] = self.registry_sha
        self.lineage_path.write_text(json.dumps(self.lineage), encoding="utf-8")

    def test_missing_hash_binding_or_checkpoint_family_overlap_blocks_training(self) -> None:
        export = self._write_export([self._example()])
        lineage = copy.deepcopy(self.lineage)
        lineage["prompt_bindings"] = []
        self.lineage_path.write_text(json.dumps(lineage), encoding="utf-8")
        report = self._audit([export])
        self.assertFalse(report["ready_for_student_training"])
        self.assertTrue(any("prompt_hash_unbound" in item for item in report["blockers"]))

        lineage = copy.deepcopy(self.lineage)
        lineage["checkpoint_bindings"][0]["training_family_ids"] = [self.family_id]
        self.lineage_path.write_text(json.dumps(lineage), encoding="utf-8")
        overlap = self._audit([export])
        self.assertFalse(overlap["ready_for_student_training"])
        self.assertTrue(any("checkpoint_family_overlap" in item for item in overlap["blockers"]))

    def test_provider_model_and_source_audit_artifact_hashes_are_rechecked(self) -> None:
        export = self._write_export([self._example()])
        lineage = copy.deepcopy(self.lineage)
        lineage["checkpoint_bindings"][0]["teacher_identity"]["canonical_model_id"] = "other-model"
        self.lineage_path.write_text(json.dumps(lineage), encoding="utf-8")
        report = self._audit([export])
        self.assertFalse(report["ready_for_student_training"])
        self.assertTrue(any("checkpoint_model_mismatch" in item for item in report["blockers"]))

        self.lineage_path.write_text(json.dumps(self.lineage), encoding="utf-8")
        self.paths["audit"].write_text("drifted audit artifact\n", encoding="utf-8")
        drift = self._audit([export])
        self.assertFalse(drift["ready_for_student_training"])
        self.assertTrue(any("audit_artifact_hash_mismatch" in item for item in drift["blockers"]))

    def test_stage_disposition_and_verifier_provider_cannot_be_spoofed(self) -> None:
        stage_spoof = self._example()
        stage_spoof["canonical_stage"] = "data_lineage"
        export = self._write_export([stage_spoof], "stage-spoof.json")
        report = self._audit([export])
        self.assertFalse(report["ready_for_student_training"])
        self.assertTrue(any("stage_canonicalization_mismatch" in item for item in report["blockers"]))

        disposition_spoof = self._example()
        disposition_spoof["outcome"] = "failure"
        disposition_export = self._write_export([disposition_spoof], "disposition-spoof.json")
        disposition_report = self._audit([disposition_export])
        self.assertFalse(disposition_report["ready_for_student_training"])
        self.assertTrue(any("disposition_outcome_mismatch" in item for item in disposition_report["blockers"]))

        self_verified = self._example()
        self_verified["verification"] = {
            "status": "verified",
            "verifier_kind": "provider",
            "verifier_id": "alias-verifier",
            "provider_identity": {
                "provider_id": "https://api.deepseek.com/v1",
                "model_id": "deepseek-v4-flash-verifier",
                "canonical_provider_id": "deepseek",
                "canonical_model_id": "deepseek-v4-flash-verifier",
            },
            "checks": ["source_anchor_checked"],
        }
        self_verified_export = self._write_export([self_verified], "self-verified.json")
        self_verified_report = self._audit([self_verified_export])
        self.assertFalse(self_verified_report["ready_for_student_training"])
        self.assertTrue(any(
            "same_provider_self_verification" in item
            for item in self_verified_report["blockers"]
        ))

    def test_revocation_and_published_answer_markers_fail_closed(self) -> None:
        example = self._example()
        example["input_state"] = {"nested": {"published_answer": "sealed conclusion"}}
        export = self._write_export([example])
        report = self._audit([export])
        self.assertFalse(report["ready_for_student_training"])
        self.assertTrue(any("published_answer_marker_present" in item for item in report["blockers"]))

        clean = self._write_export([self._example()], "clean.json")
        revoked = copy.deepcopy(self.revocation)
        revoked["revoked_trace_ids"] = ["example-1"]
        self.revocation_path.write_text(json.dumps(revoked), encoding="utf-8")
        revoked_report = self._audit([clean])
        self.assertFalse(revoked_report["ready_for_student_training"])
        self.assertTrue(any("revocation_manifest_hash_mismatch" in item for item in revoked_report["blockers"]))

    def test_cli_reports_zero_when_repository_has_no_export_argument(self) -> None:
        script = REPO_ROOT / "metawingman" / "scripts" / "audit_distillation_readiness.py"
        result = subprocess.run(
            [
                sys.executable, str(script),
                "--case-registry", str(self.registry_path),
                "--artifact-root", str(self.root),
            ],
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        report = json.loads(result.stdout)
        self.assertFalse(report["ready_for_student_training"])
        self.assertEqual(report["counts"]["trainable"]["total"], 0)


if __name__ == "__main__":
    unittest.main()
