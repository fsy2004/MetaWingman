from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from metawingman.scripts.metawingman_core.innovation_evidence import (
    InnovationEvidenceError,
    audit_innovation_evidence,
)
from metawingman.scripts.metawingman_core.schema_guard import (
    SchemaValidationError,
    validate_document,
)


STAGES = [
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
]


def _resource_audit() -> dict:
    return {
        "provider_calls": 1,
        "input_tokens": 100,
        "output_tokens": 20,
        "wall_seconds": 1.5,
        "cost": None,
        "cost_status": "unknown",
    }


class InnovationEvidenceLedgerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.ledger = {
            "schema_version": "1.0",
            "ledger_id": "dual-innovation-evidence-v1",
            "assessed_at_utc": "2026-08-22T12:00:00Z",
            "policy": {
                "policy_provenance": "project_calibrated_not_normative",
                "journal_prestige_is_admission_only": True,
                "same_provider_is_not_independent": True,
                "negative_results_must_be_retained": True,
                "full_lifecycle_requires_same_case": True,
                "required_profile_strata": [
                    "intervention_network",
                    "diagnostic_accuracy",
                    "public_health_exposure",
                    "living_review",
                ],
            },
            "lifecycle_stages": [
                {
                    "stage_id": stage,
                    "implementation_level": "workflow_integrated",
                    "highest_direct_evidence": "fixture",
                    "artifact_paths": ["README.md"],
                }
                for stage in STAGES
            ],
            "cases": [
                {
                    "case_id": "development-dta",
                    "review_family_id": "family-development-dta",
                    "split": "development",
                    "profile_strata": ["diagnostic_accuracy", "living_review"],
                    "authority_identity_verified": True,
                    "broad_decision_relevance": True,
                    "common_or_high_burden": True,
                    "representativeness_sources": ["https://example.org/dta"],
                    "training_use": "stage_verified_only",
                },
                {
                    "case_id": "held-topic-network",
                    "review_family_id": "family-held-topic-network",
                    "split": "held_out",
                    "profile_strata": ["intervention_network"],
                    "authority_identity_verified": True,
                    "broad_decision_relevance": True,
                    "common_or_high_burden": True,
                    "representativeness_sources": ["https://example.org/network"],
                    "training_use": "forbidden",
                },
                {
                    "case_id": "development-public-health",
                    "review_family_id": "family-development-public-health",
                    "split": "development",
                    "profile_strata": ["public_health_exposure", "living_review"],
                    "authority_identity_verified": True,
                    "broad_decision_relevance": True,
                    "common_or_high_burden": True,
                    "representativeness_sources": ["https://example.org/public-health"],
                    "training_use": "stage_verified_only",
                },
            ],
            "evidence_items": [
                {
                    "evidence_id": "topic-heldout-positive",
                    "claim_ids": ["topic_opportunity_control"],
                    "evaluation_kind": "historical_held_out",
                    "result_direction": "positive",
                    "case_ids": ["held-topic-network"],
                    "review_family_ids": ["family-held-topic-network"],
                    "covered_stage_ids": ["topic_feasibility"],
                    "construct_validity_status": "confirmed",
                    "full_mechanism_executed": True,
                    "direct_baseline_passed": True,
                    "predicted_ablation_degradation_observed": False,
                    "frozen_before_reference": True,
                    "reference_opened_after_complete_lock": True,
                    "provider_relation": "same_provider_roles",
                    "independent_verification_claimed": False,
                    "same_case_full_lifecycle": False,
                    "artifact_paths": ["README.md"],
                    "resource_audit": _resource_audit(),
                    "limitations": ["one held-out family"],
                },
                {
                    "evidence_id": "acquisition-two-case-negative",
                    "claim_ids": ["conclusion_directed_acquisition"],
                    "evaluation_kind": "historical_held_out",
                    "result_direction": "negative",
                    "case_ids": ["development-dta", "development-public-health"],
                    "review_family_ids": [
                        "family-development-dta",
                        "family-development-public-health",
                    ],
                    "covered_stage_ids": ["search_retrieval"],
                    "full_mechanism_executed": True,
                    "direct_baseline_passed": False,
                    "predicted_ablation_degradation_observed": False,
                    "frozen_before_reference": True,
                    "reference_opened_after_complete_lock": True,
                    "provider_relation": "same_provider_roles",
                    "independent_verification_claimed": False,
                    "same_case_full_lifecycle": False,
                    "artifact_paths": ["README.md"],
                    "resource_audit": _resource_audit(),
                    "limitations": ["generic fixed acquisition performed better"],
                },
                {
                    "evidence_id": "partial-pipeline-reconstruction",
                    "claim_ids": ["joint_lifecycle_control"],
                    "evaluation_kind": "partial_pipeline_reconstruction",
                    "result_direction": "negative",
                    "case_ids": ["development-dta", "development-public-health"],
                    "review_family_ids": [
                        "family-development-dta",
                        "family-development-public-health",
                    ],
                    "covered_stage_ids": [
                        "protocol_registration",
                        "search_retrieval",
                        "selection",
                    ],
                    "full_mechanism_executed": False,
                    "direct_baseline_passed": False,
                    "predicted_ablation_degradation_observed": False,
                    "frozen_before_reference": True,
                    "reference_opened_after_complete_lock": True,
                    "provider_relation": "same_provider_roles",
                    "independent_verification_claimed": False,
                    "same_case_full_lifecycle": False,
                    "artifact_paths": ["README.md"],
                    "resource_audit": _resource_audit(),
                    "limitations": ["does not execute all ten lifecycle stages"],
                },
                {
                    "evidence_id": "distillation-governance",
                    "claim_ids": ["agent_distillation"],
                    "evaluation_kind": "governance_contract",
                    "result_direction": "diagnostic",
                    "case_ids": ["development-dta"],
                    "review_family_ids": ["family-development-dta"],
                    "covered_stage_ids": ["topic_feasibility"],
                    "full_mechanism_executed": True,
                    "direct_baseline_passed": False,
                    "predicted_ablation_degradation_observed": False,
                    "frozen_before_reference": True,
                    "reference_opened_after_complete_lock": False,
                    "provider_relation": "deterministic_external_verifier",
                    "independent_verification_claimed": True,
                    "same_case_full_lifecycle": False,
                    "artifact_paths": ["README.md"],
                    "resource_audit": _resource_audit(),
                    "limitations": ["no student evaluation"],
                },
            ],
        }

    def test_current_evidence_has_separate_honest_claim_ceilings(self) -> None:
        result = audit_innovation_evidence(self.ledger)
        self.assertTrue(result["valid"])
        self.assertEqual(
            result["claim_ceilings"],
            {
                "topic_opportunity_control": "single_held_out_family_positive",
                "conclusion_directed_acquisition": "direct_benefit_not_supported",
                "joint_lifecycle_control": "not_evaluated_full_lifecycle",
                "agent_distillation": "governance_only_no_student_gain",
            },
        )
        self.assertFalse(result["joint_lifecycle"]["complete"])
        self.assertEqual(
            result["joint_lifecycle"]["missing_stage_ids"],
            ["topic_feasibility", "data_lineage", "appraisal", "freeze_synthesis",
             "certainty_interpretation", "reporting_review", "living_update"],
        )

    def test_development_student_gain_is_not_collapsed_into_governance_only(self) -> None:
        ledger = copy.deepcopy(self.ledger)
        ledger["evidence_items"].append({
            "evidence_id": "development-student-comparison",
            "claim_ids": ["agent_distillation"],
            "evaluation_kind": "student_comparison",
            "result_direction": "positive",
            "case_ids": ["development-dta"],
            "review_family_ids": ["family-development-dta"],
            "covered_stage_ids": ["protocol_registration"],
            "full_mechanism_executed": True,
            "direct_baseline_passed": True,
            "predicted_ablation_degradation_observed": False,
            "frozen_before_reference": True,
            "reference_opened_after_complete_lock": False,
            "provider_relation": "deterministic_external_verifier",
            "independent_verification_claimed": True,
            "same_case_full_lifecycle": False,
            "artifact_paths": ["README.md"],
            "resource_audit": _resource_audit(),
            "limitations": ["single development family"],
        })
        result = audit_innovation_evidence(ledger)
        self.assertEqual(
            result["claim_ceilings"]["agent_distillation"],
            "development_only_student_gain_not_generalization",
        )

    def test_completed_development_student_comparison_without_gain_is_reported(self) -> None:
        ledger = copy.deepcopy(self.ledger)
        comparison = copy.deepcopy(ledger["evidence_items"][-1])
        comparison.update({
            "evidence_id": "development-student-comparison-negative",
            "evaluation_kind": "student_comparison",
            "result_direction": "negative",
            "direct_baseline_passed": False,
            "covered_stage_ids": ["protocol_registration"],
        })
        ledger["evidence_items"].append(comparison)
        result = audit_innovation_evidence(ledger)
        self.assertEqual(
            result["claim_ceilings"]["agent_distillation"],
            "development_student_comparison_no_gain",
        )

    def test_same_provider_roles_cannot_claim_independent_verification(self) -> None:
        ledger = copy.deepcopy(self.ledger)
        ledger["evidence_items"][0]["independent_verification_claimed"] = True
        with self.assertRaisesRegex(InnovationEvidenceError, "same-provider"):
            audit_innovation_evidence(ledger)

    def test_held_out_case_cannot_enter_training(self) -> None:
        ledger = copy.deepcopy(self.ledger)
        ledger["cases"][1]["training_use"] = "stage_verified_only"
        with self.assertRaisesRegex(InnovationEvidenceError, "held-out.*training"):
            audit_innovation_evidence(ledger)

    def test_all_ten_lifecycle_stages_are_required_exactly_once(self) -> None:
        ledger = copy.deepcopy(self.ledger)
        ledger["lifecycle_stages"].pop()
        with self.assertRaisesRegex(InnovationEvidenceError, "exact ten-stage"):
            audit_innovation_evidence(ledger)

    def test_full_lifecycle_flag_requires_all_stages_on_one_case(self) -> None:
        ledger = copy.deepcopy(self.ledger)
        ledger["evidence_items"][2]["same_case_full_lifecycle"] = True
        with self.assertRaisesRegex(InnovationEvidenceError, "all ten stages"):
            audit_innovation_evidence(ledger)

    def test_second_positive_held_out_family_without_ablation_is_replication_not_mechanism_identification(self) -> None:
        ledger = copy.deepcopy(self.ledger)
        second_case = copy.deepcopy(ledger["cases"][1])
        second_case.update({
            "case_id": "held-topic-network-2",
            "review_family_id": "family-held-topic-network-2",
        })
        ledger["cases"].append(second_case)
        second = copy.deepcopy(ledger["evidence_items"][0])
        second.update({
            "evidence_id": "topic-heldout-positive-2",
            "case_ids": ["held-topic-network-2"],
            "review_family_ids": ["family-held-topic-network-2"],
        })
        ledger["evidence_items"].append(second)
        result = audit_innovation_evidence(ledger)
        self.assertEqual(
            result["claim_ceilings"]["topic_opportunity_control"],
            "replicated_held_out_families_integrated_mechanism_only",
        )
        self.assertIn("component necessity remains unresolved", result["claim_blockers"])

    def test_positive_candidate_control_does_not_upgrade_full_topic_discovery(self) -> None:
        ledger = copy.deepcopy(self.ledger)
        ledger["evidence_items"][0]["full_mechanism_executed"] = False
        result = audit_innovation_evidence(ledger)
        self.assertEqual(
            result["claim_ceilings"]["topic_opportunity_control"],
            "single_held_out_candidate_control_positive_not_discovery",
        )
        self.assertIn(
            "topic candidate control did not execute unbiased candidate generation",
            result["claim_blockers"],
        )

    def test_pre_construct_fix_positive_is_legacy_not_current_controller_evidence(self) -> None:
        ledger = copy.deepcopy(self.ledger)
        topic = ledger["evidence_items"][0]
        topic["full_mechanism_executed"] = False
        topic["construct_validity_status"] = "failed_current_contract"
        result = audit_innovation_evidence(ledger)
        self.assertEqual(
            result["claim_ceilings"]["topic_opportunity_control"],
            "pre_construct_fix_shared_candidate_positive_not_confirmatory",
        )
        self.assertIn(
            "topic evidence predates and fails the current construct-validity contract",
            result["claim_blockers"],
        )

    def test_schema_rejects_unknown_construct_validity_status(self) -> None:
        ledger = copy.deepcopy(self.ledger)
        ledger["evidence_items"][0]["construct_validity_status"] = "looks_good"
        with self.assertRaises(SchemaValidationError):
            validate_document(ledger, "innovation_evidence_ledger")

    def test_negative_axis_prompt_proxy_does_not_falsify_full_acquisition_controller(self) -> None:
        ledger = copy.deepcopy(self.ledger)
        ledger["evidence_items"][1]["full_mechanism_executed"] = False
        result = audit_innovation_evidence(ledger)
        self.assertEqual(
            result["claim_ceilings"]["conclusion_directed_acquisition"],
            "axis_prompt_proxy_negative_not_full_controller",
        )
        self.assertIn(
            "the full risk-times-impact acquisition controller has not been directly evaluated",
            result["claim_blockers"],
        )

    def test_missing_representative_profile_is_a_scientific_blocker_not_schema_failure(self) -> None:
        ledger = copy.deepcopy(self.ledger)
        ledger["cases"] = [case for case in ledger["cases"] if "public_health_exposure" not in case["profile_strata"]]
        ledger["evidence_items"] = [
            item for item in ledger["evidence_items"]
            if "development-public-health" not in item["case_ids"]
        ]
        result = audit_innovation_evidence(ledger)
        self.assertTrue(result["valid"])
        self.assertFalse(result["portfolio"]["representative_profile_coverage_complete"])
        self.assertEqual(result["portfolio"]["missing_profile_strata"], ["public_health_exposure"])

    def test_schema_rejects_untracked_claim_fields(self) -> None:
        validate_document(self.ledger, "innovation_evidence_ledger")
        ledger = copy.deepcopy(self.ledger)
        ledger["untracked_claim"] = "overstated"
        with self.assertRaises(SchemaValidationError):
            validate_document(ledger, "innovation_evidence_ledger")

    def test_cli_emits_derived_claim_ceilings(self) -> None:
        script = Path(__file__).resolve().parents[1] / "metawingman/scripts/audit_innovation_evidence.py"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ledger.json"
            path.write_text(json.dumps(self.ledger), encoding="utf-8")
            completed = subprocess.run(
                [sys.executable, str(script), str(path)],
                check=False,
                capture_output=True,
                text=True,
            )
        self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)
        payload = json.loads(completed.stdout)
        self.assertEqual(
            payload["claim_ceilings"]["joint_lifecycle_control"],
            "not_evaluated_full_lifecycle",
        )

    def test_cli_fails_closed_on_a_missing_evidence_artifact(self) -> None:
        script = Path(__file__).resolve().parents[1] / "metawingman/scripts/audit_innovation_evidence.py"
        ledger = copy.deepcopy(self.ledger)
        ledger["evidence_items"][0]["artifact_paths"] = ["docs/does-not-exist.json"]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ledger.json"
            path.write_text(json.dumps(ledger), encoding="utf-8")
            completed = subprocess.run(
                [sys.executable, str(script), str(path)],
                check=False,
                capture_output=True,
                text=True,
            )
        self.assertEqual(completed.returncode, 1)
        self.assertIn("missing evidence artifact", completed.stdout)

    def test_zero_call_deterministic_verifier_allows_not_applicable_cost(self) -> None:
        ledger = copy.deepcopy(self.ledger)
        resources = ledger["evidence_items"][3]["resource_audit"]
        resources.update({
            "provider_calls": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "cost": None,
            "cost_status": "not_applicable",
        })
        result = audit_innovation_evidence(ledger)
        self.assertTrue(result["valid"])

    def test_repository_ledger_is_hash_bound_to_the_canonical_case_registry(self) -> None:
        root = Path(__file__).resolve().parents[1]
        ledger = json.loads((root / "research/innovation-evidence-ledger-v1.json").read_text(encoding="utf-8"))
        result = audit_innovation_evidence(ledger, repository_root=root)
        self.assertTrue(result["canonical_case_registry"]["bound"])
        self.assertEqual(
            result["canonical_case_registry"]["path"],
            "research/direct-evidence-case-registry-v1.json",
        )

        drifted = copy.deepcopy(ledger)
        drifted["cases"][0]["split"] = "diagnostic_only"
        drifted["cases"][0]["training_use"] = "audit_only"
        with self.assertRaisesRegex(InnovationEvidenceError, "canonical case registry mismatch"):
            audit_innovation_evidence(drifted, repository_root=root)


if __name__ == "__main__":
    unittest.main()
