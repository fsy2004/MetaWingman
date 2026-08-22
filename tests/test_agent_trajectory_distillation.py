from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from metawingman.scripts.metawingman_core.agent_distillation import (
    DistillationError,
    build_topic_proposal_traces,
    freeze_distillation_examples,
)
from metawingman.scripts.metawingman_core.schema_guard import validate_document


class AgentTrajectoryDistillationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_root = Path(self.temp_dir.name)
        self.source_artifact = self.temp_root / "source.json"
        self.audit_artifact = self.temp_root / "audit.json"
        self.source_artifact.write_text('{"source":"locked"}\n', encoding="utf-8")
        self.audit_artifact.write_text('{"audit":"verified"}\n', encoding="utf-8")
        self.registry = {
            "schema_version": "1.0",
            "cases": [{
                "case_id": "bmj-covid-therapies-living-nma",
                "review_family_id": "covid-therapeutics-living-nma",
                "split": "development",
                "execution_status": "run_ready",
            }],
        }
        self.trace = {
            "trace_id": "trace-1",
            "case_id": "bmj-covid-therapies-living-nma",
            "review_family_id": "covid-therapeutics-living-nma",
            "split": "development",
            "teacher_provider_id": "deepseek-v4-flash",
            "teacher_identity": {
                "provider_id": "deepseek",
                "model_id": "deepseek-v4-flash",
            },
            "stage": "evidence_acquisition",
            "input_state": {"question_framework": {"population": ["people with covid-19"]}},
            "action": {"type": "retrieve", "candidate_id": "pmid-1"},
            "decision": {"status": "accept", "reason_codes": ["source_supported"]},
            "source_anchors": [{"source_id": "pmid-1", "anchor": "title_abstract"}],
            "verification": {
                "status": "verified",
                "verifier_kind": "deterministic_guard",
                "verifier_id": "cutoff-and-id-guard-v1",
                "checks": ["candidate_exists", "pre_cutoff", "anchor_present"]
            },
            "artifact_bindings": {
                "source_artifacts": [{
                    "path": str(self.source_artifact),
                    "sha256": self._sha256(self.source_artifact),
                }],
                "audit_artifacts": [{
                    "path": str(self.audit_artifact),
                    "sha256": self._sha256(self.audit_artifact),
                }],
            },
            "reproducibility_bindings": {
                "dataset_sha256": hashlib.sha256(b"dataset-v1").hexdigest(),
                "prompt_sha256": hashlib.sha256(b"prompt-v1").hexdigest(),
                "tool_sha256": hashlib.sha256(b"tool-v1").hexdigest(),
                "checkpoint_sha256": hashlib.sha256(b"checkpoint-v1").hexdigest(),
            },
            "outcome": "success"
        }

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    @staticmethod
    def _sha256(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def test_verified_decision_trajectory_is_exported_with_lineage(self) -> None:
        result = freeze_distillation_examples(
            [self.trace], case_registry=self.registry,
            created_at_utc="2026-08-22T02:30:00Z",
        )
        self.assertEqual(result["summary"]["examples"], 1)
        self.assertEqual(result["summary"]["failures_retained"], 0)
        self.assertEqual(result["summary"]["trainable_examples"], 1)
        self.assertEqual(result["summary"]["quarantined_examples"], 0)
        self.assertEqual(result["examples"][0]["label_authority"], "verified_teacher_trajectory_not_gold")
        self.assertEqual(result["examples"][0]["training_disposition"], "positive_demonstration")
        self.assertEqual(result["examples"][0]["source_anchors"][0]["source_id"], "pmid-1")
        self.assertEqual(result["governance_status"], "governance_only_no_student_trained")
        validate_document(result, "agent_distillation_export")

    def test_nested_forbidden_key_and_value_aliases_are_rejected(self) -> None:
        nested_key = copy.deepcopy(self.trace)
        nested_key["input_state"]["notes"] = [{"Target-DOI": "hidden"}]
        with self.assertRaisesRegex(DistillationError, "sealed target identity or answer"):
            freeze_distillation_examples(
                [nested_key], case_registry=self.registry,
                created_at_utc="2026-08-22T02:30:00Z",
            )

        nested_value = copy.deepcopy(self.trace)
        nested_value["input_state"]["notes"] = [{"kind": "Published-Expert Reference"}]
        with self.assertRaisesRegex(DistillationError, "sealed target identity or answer"):
            freeze_distillation_examples(
                [nested_value], case_registry=self.registry,
                created_at_utc="2026-08-22T02:30:00Z",
            )

    def test_source_and_audit_artifacts_are_hash_verified_and_exported(self) -> None:
        result = freeze_distillation_examples(
            [self.trace], case_registry=self.registry,
            created_at_utc="2026-08-22T02:30:00Z",
        )
        self.assertEqual(
            result["examples"][0]["artifact_bindings"],
            self.trace["artifact_bindings"],
        )

        tampered = copy.deepcopy(self.trace)
        self.audit_artifact.write_text('{"audit":"tampered"}\n', encoding="utf-8")
        with self.assertRaisesRegex(DistillationError, "artifact SHA-256 mismatch"):
            freeze_distillation_examples(
                [tampered], case_registry=self.registry,
                created_at_utc="2026-08-22T02:30:00Z",
            )

    def test_reproducibility_hashes_are_independently_bound_in_export(self) -> None:
        result = freeze_distillation_examples(
            [self.trace], case_registry=self.registry,
            created_at_utc="2026-08-22T02:30:00Z",
        )
        self.assertEqual(
            result["examples"][0]["reproducibility_bindings"],
            self.trace["reproducibility_bindings"],
        )
        self.assertTrue(result["policy"]["reproducibility_hashes_required_for_training"])

    def test_positive_demonstration_rejects_each_missing_reproducibility_hash(self) -> None:
        for field in (
            "dataset_sha256", "prompt_sha256", "tool_sha256", "checkpoint_sha256",
        ):
            with self.subTest(field=field):
                trace = copy.deepcopy(self.trace)
                del trace["reproducibility_bindings"][field]
                with self.assertRaisesRegex(
                    DistillationError,
                    "positive demonstration requires complete reproducibility bindings",
                ):
                    freeze_distillation_examples(
                        [trace], case_registry=self.registry,
                        created_at_utc="2026-08-22T02:30:00Z",
                    )

    def test_missing_reproducibility_hashes_are_retained_only_as_audit_quarantine(self) -> None:
        trace = copy.deepcopy(self.trace)
        trace["trace_id"] = "trace-unbound-quarantine"
        trace["outcome"] = "failure"
        trace["decision"] = {
            "status": "quarantine",
            "reason_codes": ["infrastructure_failure"],
        }
        del trace["reproducibility_bindings"]
        result = freeze_distillation_examples(
            [trace], case_registry=self.registry,
            created_at_utc="2026-08-22T02:30:00Z",
        )
        example = result["examples"][0]
        self.assertEqual(example["training_disposition"], "audit_only_quarantine")
        self.assertEqual(
            example["reproducibility_bindings"],
            {
                "dataset_sha256": None,
                "prompt_sha256": None,
                "tool_sha256": None,
                "checkpoint_sha256": None,
            },
        )
        self.assertEqual(result["summary"]["trainable_examples"], 0)

    def test_unbound_negative_and_abstention_examples_are_demoted_to_audit_only(self) -> None:
        for outcome, decision_status in (("failure", "reject"), ("abstention", "abstain")):
            with self.subTest(outcome=outcome):
                trace = copy.deepcopy(self.trace)
                trace["trace_id"] = f"trace-unbound-{outcome}"
                trace["outcome"] = outcome
                trace["decision"] = {
                    "status": decision_status,
                    "reason_codes": ["bounded_nonpositive_example"],
                }
                del trace["reproducibility_bindings"]
                result = freeze_distillation_examples(
                    [trace], case_registry=self.registry,
                    created_at_utc="2026-08-22T02:30:00Z",
                )
                self.assertEqual(
                    result["examples"][0]["training_disposition"],
                    "audit_only_quarantine",
                )
                self.assertEqual(result["summary"]["trainable_examples"], 0)

    def test_missing_source_or_audit_artifact_binding_is_rejected(self) -> None:
        for missing in ("source_artifacts", "audit_artifacts"):
            with self.subTest(missing=missing):
                trace = copy.deepcopy(self.trace)
                trace["artifact_bindings"][missing] = []
                with self.assertRaisesRegex(DistillationError, "source and audit artifact bindings"):
                    freeze_distillation_examples(
                        [trace], case_registry=self.registry,
                        created_at_utc="2026-08-22T02:30:00Z",
                    )

    def test_canonical_provider_identity_blocks_alias_self_verification(self) -> None:
        trace = copy.deepcopy(self.trace)
        trace["teacher_identity"] = {
            "provider_id": "DeepSeek API",
            "model_id": "deepseek/deepseek-v4-flash",
        }
        trace["verification"] = {
            "status": "verified",
            "verifier_kind": "provider",
            "verifier_id": "independent-looking-label",
            "provider_identity": {
                "provider_id": "https://api.deepseek.com/v1",
                "model_id": "deepseek-v4-flash-verifier",
            },
            "checks": ["source_anchor_checked"],
        }
        with self.assertRaisesRegex(DistillationError, "same-provider"):
            freeze_distillation_examples(
                [trace], case_registry=self.registry,
                created_at_utc="2026-08-22T02:30:00Z",
            )

        punctuation_alias = copy.deepcopy(trace)
        punctuation_alias["teacher_identity"]["provider_id"] = "Deep-Seek"
        with self.assertRaisesRegex(DistillationError, "same-provider"):
            freeze_distillation_examples(
                [punctuation_alias], case_registry=self.registry,
                created_at_utc="2026-08-22T02:30:00Z",
            )

    def test_independent_provider_identity_is_canonicalized_in_export(self) -> None:
        trace = copy.deepcopy(self.trace)
        trace["verification"] = {
            "status": "verified",
            "verifier_kind": "provider",
            "verifier_id": "external-verifier-v1",
            "provider_identity": {
                "provider_id": "Independent Lab API",
                "model_id": "Verifier/Model-V1",
            },
            "checks": ["source_anchor_checked"],
        }
        result = freeze_distillation_examples(
            [trace], case_registry=self.registry,
            created_at_utc="2026-08-22T02:30:00Z",
        )
        example = result["examples"][0]
        self.assertEqual(example["teacher_identity"]["canonical_provider_id"], "deepseek")
        self.assertEqual(
            example["verification"]["provider_identity"]["canonical_provider_id"],
            "independent-lab",
        )

    def test_all_ten_canonical_review_stages_are_exportable(self) -> None:
        canonical_stages = (
            "topic_feasibility",
            "protocol_registration",
            "search_retrieval",
            "selection",
            "data_lineage",
            "appraisal",
            "freeze_synthesis",
            "certainty_interpretation",
            "reporting_review",
            "living_update",
        )
        traces = []
        for index, stage in enumerate(canonical_stages):
            trace = copy.deepcopy(self.trace)
            trace["trace_id"] = f"canonical-stage-{index}"
            trace["stage"] = stage
            traces.append(trace)
        try:
            result = freeze_distillation_examples(
                traces, case_registry=self.registry,
                created_at_utc="2026-08-22T02:30:00Z",
            )
        except DistillationError as exc:
            self.fail(f"canonical ten-stage lifecycle was rejected: {exc}")
        self.assertEqual(
            {item["canonical_stage"] for item in result["examples"]},
            set(canonical_stages),
        )

    def test_revocation_manifest_is_registry_bound_and_blocks_revoked_trace(self) -> None:
        registry_sha256 = hashlib.sha256(
            json.dumps(self.registry, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        ).hexdigest()
        manifest = {
            "schema_version": "1.0",
            "revision": "rev-2026-08-22-1",
            "case_registry_sha256": registry_sha256,
            "revoked_trace_ids": ["trace-1"],
            "forbidden_value_aliases": [],
        }
        try:
            with self.assertRaisesRegex(DistillationError, "revoked"):
                freeze_distillation_examples(
                    [self.trace], case_registry=self.registry,
                    created_at_utc="2026-08-22T02:30:00Z",
                    revocation_manifest=manifest,
                )
        except TypeError as exc:
            self.fail(f"revocation binding is not implemented: {exc}")

        manifest["revoked_trace_ids"] = []
        manifest["case_registry_sha256"] = "0" * 64
        try:
            with self.assertRaisesRegex(DistillationError, "registry SHA-256"):
                freeze_distillation_examples(
                    [self.trace], case_registry=self.registry,
                    created_at_utc="2026-08-22T02:30:00Z",
                    revocation_manifest=manifest,
                )
        except TypeError as exc:
            self.fail(f"revocation binding is not implemented: {exc}")

    def test_empty_revocation_state_is_canonically_bound_in_export(self) -> None:
        result = freeze_distillation_examples(
            [self.trace], case_registry=self.registry,
            created_at_utc="2026-08-22T02:30:00Z",
        )
        self.assertEqual(
            result["canonical_case_registry_sha256"],
            result["case_registry_sha256"],
        )
        self.assertEqual(
            result["revocation_binding"]["case_registry_sha256"],
            result["case_registry_sha256"],
        )
        self.assertEqual(result["revocation_binding"]["revision"], "implicit-empty-v1")

    def test_freeze_cli_atomically_refuses_to_overwrite_existing_export(self) -> None:
        traces_path = self.temp_root / "traces.jsonl"
        registry_path = self.temp_root / "registry.json"
        output_path = self.temp_root / "frozen-export.json"
        traces_path.write_text(json.dumps(self.trace) + "\n", encoding="utf-8")
        registry_path.write_text(json.dumps(self.registry), encoding="utf-8")
        script = Path(__file__).resolve().parents[1] / "metawingman/scripts/freeze_agent_distillation.py"
        command = [
            sys.executable,
            str(script),
            str(traces_path),
            "--case-registry", str(registry_path),
            "--out", str(output_path),
            "--created-at-utc", "2026-08-22T02:30:00Z",
        ]
        first = subprocess.run(command, capture_output=True, text=True, check=False)
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        first_bytes = output_path.read_bytes()
        second = subprocess.run(command, capture_output=True, text=True, check=False)
        self.assertEqual(second.returncode, 1, second.stdout + second.stderr)
        self.assertEqual(output_path.read_bytes(), first_bytes)

    def test_unverified_teacher_output_is_rejected(self) -> None:
        trace = copy.deepcopy(self.trace)
        trace["verification"]["status"] = "not_run"
        with self.assertRaisesRegex(DistillationError, "independent verification"):
            freeze_distillation_examples(
                [trace], case_registry=self.registry,
                created_at_utc="2026-08-22T02:30:00Z",
            )

    def test_same_provider_self_verification_is_rejected(self) -> None:
        trace = copy.deepcopy(self.trace)
        trace["verification"] = {
            "status": "verified", "verifier_kind": "provider",
            "verifier_id": "deepseek-v4-flash", "checks": ["looks_good"]
        }
        with self.assertRaisesRegex(DistillationError, "same-provider"):
            freeze_distillation_examples(
                [trace], case_registry=self.registry,
                created_at_utc="2026-08-22T02:30:00Z",
            )

    def test_held_out_family_cannot_enter_distillation(self) -> None:
        trace = copy.deepcopy(self.trace)
        trace["split"] = "held_out"
        with self.assertRaisesRegex(DistillationError, "development split"):
            freeze_distillation_examples(
                [trace], case_registry=self.registry,
                created_at_utc="2026-08-22T02:30:00Z",
            )

    def test_failure_trajectory_is_retained_and_target_identity_is_forbidden(self) -> None:
        failed = copy.deepcopy(self.trace)
        failed["trace_id"] = "trace-failure"
        failed["outcome"] = "failure"
        failed["decision"] = {"status": "reject", "reason_codes": ["post_cutoff"]}
        result = freeze_distillation_examples(
            [failed], case_registry=self.registry,
            created_at_utc="2026-08-22T02:30:00Z",
        )
        self.assertEqual(result["summary"]["failures_retained"], 1)
        self.assertEqual(result["examples"][0]["training_disposition"], "negative_decision")
        leaked = copy.deepcopy(self.trace)
        leaked["input_state"]["published_expert_reference"] = {"answer": "hidden"}
        with self.assertRaisesRegex(DistillationError, "sealed target identity or answer"):
            freeze_distillation_examples(
                [leaked], case_registry=self.registry,
                created_at_utc="2026-08-22T02:30:00Z",
            )

    def test_trace_cannot_spoof_registry_split_or_family(self) -> None:
        heldout_registry = copy.deepcopy(self.registry)
        heldout_registry["cases"][0]["split"] = "held_out"
        heldout_registry["cases"][0]["execution_status"] = "held_out_candidate"
        with self.assertRaisesRegex(DistillationError, "registry development split"):
            freeze_distillation_examples(
                [self.trace], case_registry=heldout_registry,
                created_at_utc="2026-08-22T02:30:00Z",
            )
        wrong_family = copy.deepcopy(self.trace)
        wrong_family["review_family_id"] = "spoofed-family"
        with self.assertRaisesRegex(DistillationError, "family does not match"):
            freeze_distillation_examples(
                [wrong_family], case_registry=self.registry,
                created_at_utc="2026-08-22T02:30:00Z",
            )

    def test_non_ready_development_case_cannot_be_distilled(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["cases"][0]["execution_status"] = "blocked_material_audit"
        with self.assertRaisesRegex(DistillationError, "run_ready"):
            freeze_distillation_examples(
                [self.trace], case_registry=registry,
                created_at_utc="2026-08-22T02:30:00Z",
            )

    def test_stage_scoped_verified_materials_allow_only_that_stage(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["cases"][0]["execution_status"] = "methods_only"
        registry["cases"][0]["training_stage_readiness"] = {
            "protocol": {"status": "verified", "sources": ["https://example.org/protocol"]},
            "evidence_acquisition": {"status": "blocked", "sources": []},
        }
        protocol_trace = copy.deepcopy(self.trace)
        protocol_trace["stage"] = "protocol"
        result = freeze_distillation_examples(
            [protocol_trace], case_registry=registry,
            created_at_utc="2026-08-22T02:30:00Z",
        )
        self.assertEqual(result["examples"][0]["stage"], "protocol")
        with self.assertRaisesRegex(DistillationError, "stage is not verified"):
            freeze_distillation_examples(
                [self.trace], case_registry=registry,
                created_at_utc="2026-08-22T02:30:00Z",
            )

    def test_topic_proposal_traces_use_hard_gates_not_published_target(self) -> None:
        landscape = {
            "landscape_id": "landscape-1",
            "corpus_boundary": {"cutoff_date": "2023-06-03"},
            "selection_policy": {
                "minimum_primary_studies": 2,
                "minimum_source_families": 1,
                "minimum_known_item_recall": 0.5,
                "maximum_review_overlap": 0.8,
                "allow_update_topics": True,
                "maximum_contamination_risk": 0.0,
                "maximum_ambiguity_risk": 0.25,
            },
        }
        proposal = {
            "proposal_id": "p1", "generation_method": "model_proposal",
            "question_framework": {"population": ["adults with depression"]},
            "concept_node_ids": ["concept-depression"],
            "evidence_node_ids": ["pmid-1"],
            "disconfirmation_queries": [{"check_type": "existing_review_overlap", "query": "depression review"}],
        }
        batch = {
            "status": "proposals_generated", "landscape_id": "landscape-1",
            "model_provenance": {"model": "deepseek-v4-flash"}, "proposals": [proposal],
        }
        signals = {
            name: {"value": value}
            for name, value in {
                "decision_relevance": 1.0, "unresolved_uncertainty": 0.5,
                "feasibility": 1.0, "evidence_maturity": 1.0,
                "nonduplication": 1.0, "update_need": 0.0,
                "equity_priority": 0.0, "cross_domain_value": 0.0,
                "contamination_risk": 0.0, "ambiguity_risk": 0.0,
            }.items()
        }
        candidate = {
            "candidate_id": "candidate-p1", "signals": signals,
            "operationalization": {"status": "complete"},
            "feasibility_evidence": {
                "primary_study_count": 3, "independent_source_families": 1,
                "known_item_recall": 1.0,
            },
            "overlap_evidence": {
                "maximum_existing_review_overlap": 0.2,
                "active_protocol_overlap": False, "update_justification": "",
            },
            "leakage_checks": {
                "audit_status": "passed", "target_title_seen": False,
                "target_authors_seen": False, "target_identifier_seen": False,
                "target_descendant_seen": False, "post_cutoff_source_seen": False,
            },
        }
        traces = build_topic_proposal_traces(
            batch, landscape, {"p1": candidate}, {}, case_id="bmj-exercise-depression-nma",
            review_family_id="adult-depression-exercise-treatment", seed=20260820,
        )
        self.assertEqual(traces[0]["outcome"], "success")
        self.assertEqual(traces[0]["decision"]["status"], "accept")
        self.assertNotIn("target", repr(traces[0]).casefold())
        candidate["feasibility_evidence"]["primary_study_count"] = 0
        rejected = build_topic_proposal_traces(
            batch, landscape, {"p1": candidate}, {}, case_id="bmj-exercise-depression-nma",
            review_family_id="adult-depression-exercise-treatment", seed=20260820,
        )
        self.assertEqual(rejected[0]["outcome"], "failure")
        self.assertIn("insufficient_primary_studies", rejected[0]["decision"]["reason_codes"])

    def test_topic_proposal_trace_retains_pipeline_failure_as_quarantine(self) -> None:
        batch = {
            "status": "proposals_generated", "landscape_id": "landscape-1",
            "model_provenance": {"model": "deepseek-v4-flash"},
            "proposals": [{
                "proposal_id": "p1", "generation_method": "model_proposal",
                "question_framework": {"population": ["adults"]},
                "concept_node_ids": ["c1"], "evidence_node_ids": ["pmid-1"],
                "disconfirmation_queries": [{"check_type": "source_coverage", "query": "adults"}],
            }],
        }
        landscape = {
            "landscape_id": "landscape-1", "corpus_boundary": {"cutoff_date": "2023-06-03"},
            "selection_policy": {},
        }
        traces = build_topic_proposal_traces(
            batch, landscape, {}, {"p1": {"stage": "run_topic_external_search.py", "returncode": 1}},
            case_id="bmj-exercise-depression-nma",
            review_family_id="adult-depression-exercise-treatment", seed=20260820,
        )
        self.assertEqual(traces[0]["outcome"], "failure")
        self.assertEqual(traces[0]["decision"]["status"], "quarantine")
        self.assertIn("pipeline_failure_recorded", traces[0]["verification"]["checks"])
        traces[0]["artifact_bindings"] = copy.deepcopy(self.trace["artifact_bindings"])
        export = freeze_distillation_examples(
            traces,
            case_registry={"schema_version": "1.0", "cases": [{
                "case_id": "bmj-exercise-depression-nma",
                "review_family_id": "adult-depression-exercise-treatment",
                "split": "development", "execution_status": "run_ready",
            }]},
            created_at_utc="2026-08-22T02:30:00Z",
        )
        self.assertEqual(export["examples"][0]["training_disposition"], "audit_only_quarantine")
        self.assertEqual(export["summary"]["trainable_examples"], 0)
        self.assertEqual(export["summary"]["quarantined_examples"], 1)


if __name__ == "__main__":
    unittest.main()
