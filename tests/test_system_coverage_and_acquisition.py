from __future__ import annotations

import json
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "metawingman/scripts"
sys.path.insert(0, str(SCRIPTS))

from metawingman_core.coverage_audit import (  # noqa: E402
    audit_biomedical_coverage,
    audit_capability_matrix,
)
from metawingman_core.evidence_acquisition import (  # noqa: E402
    EvidenceAcquisitionError,
    plan_evidence_acquisition,
)


TIMESTAMP = "2026-08-13T00:00:00Z"


def acquisition_state() -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "state_id": "search-state-001",
        "protocol_version": "1.0-frozen",
        "criterion_states": [
            {
                "criterion_id": "population",
                "critical": True,
                "calibration_status": "calibrated",
                "residual_omission_risk": 0.2,
                "downstream_claim_impact": 0.9,
                "hard_negative_error_rate": 0.12,
                "unresolved_records": 4,
                "independent_source_count": 1,
                "evidence_basis": "Held-out hard-negative calibration and source audit.",
            },
            {
                "criterion_id": "outcome",
                "critical": False,
                "calibration_status": "calibrated",
                "residual_omission_risk": 0.03,
                "downstream_claim_impact": 0.2,
                "hard_negative_error_rate": 0.02,
                "unresolved_records": 0,
                "independent_source_count": 3,
                "evidence_basis": "Held-out outcome criterion calibration.",
            },
        ],
        "global_signals": {
            "run_context": "production",
            "known_item_set_frozen": True,
            "known_item_recall": 0.88,
            "source_family_count": 2,
            "temporal_boundary_status": "not_applicable",
            "leakage_audit": "not_applicable",
        },
        "thresholds": {
            "known_item_recall_floor": 0.95,
            "residual_omission_risk_ceiling": 0.05,
            "downstream_claim_impact_ceiling": 0.25,
            "hard_negative_error_ceiling": 0.05,
            "minimum_independent_sources": 2,
            "minimum_source_families": 3,
            "max_selected_actions": 2,
        },
        "candidate_actions": [
            {
                "action_id": "add-registry",
                "action_type": "registry_search",
                "target_criterion_ids": ["population"],
                "expected_risk_reduction": 0.5,
                "expected_claim_impact": 0.8,
                "source_family_gain": 1,
                "estimated_cost_units": 2.0,
                "estimate_basis": "heuristic",
                "legally_available": True,
                "credential_status": "not_required",
                "rationale": "Adds an independent prospective-trial source.",
            },
            {
                "action_id": "query-expand",
                "action_type": "query_expansion",
                "target_criterion_ids": ["population"],
                "expected_risk_reduction": 0.3,
                "expected_claim_impact": 0.7,
                "source_family_gain": 0,
                "estimated_cost_units": 1.0,
                "estimate_basis": "heuristic",
                "legally_available": True,
                "credential_status": "not_required",
                "rationale": "Targets criterion-specific synonyms and hard negatives.",
            },
            {
                "action_id": "licensed-export",
                "action_type": "add_source",
                "target_criterion_ids": ["population"],
                "expected_risk_reduction": 0.8,
                "expected_claim_impact": 0.9,
                "source_family_gain": 1,
                "estimated_cost_units": 1.0,
                "estimate_basis": "historical",
                "legally_available": True,
                "credential_status": "human_handoff",
                "rationale": "Requires an institutional database export.",
            },
        ],
        "created_at_utc": TIMESTAMP,
    }


class SystemCoverageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.matrix_path = ROOT / "metawingman/references/system-capability-matrix.json"
        cls.matrix = json.loads(cls.matrix_path.read_text(encoding="utf-8"))

    def test_matrix_covers_exact_lifecycle_profile_catalog_and_routes(self) -> None:
        report = audit_capability_matrix(self.matrix, ROOT / "metawingman")
        self.assertTrue(report["valid"], report["issues"])
        self.assertEqual(report["coverage"]["lifecycle_stages_declared"], 10)
        self.assertEqual(report["coverage"]["review_profiles_declared"], 21)
        self.assertGreaterEqual(report["coverage"]["synthesis_routes_declared"], 19)
        self.assertEqual(report["advanced_validation_claims"], 0)

    def test_biomedical_matrix_freezes_pack_and_capability_evidence_contract(self) -> None:
        self.assertIn("biomedical_coverage", self.matrix)
        biomedical = self.matrix["biomedical_coverage"]
        self.assertEqual(
            biomedical["scientific_claim_ceiling"],
            "implemented_not_scientifically_validated",
        )
        self.assertEqual(len(biomedical["pack_inventory"]), 6)
        self.assertGreaterEqual(len(biomedical["capability_evidence"]), 8)

    def test_biomedical_coverage_is_conservative_and_explicit(self) -> None:
        report = audit_biomedical_coverage(
            ROOT / "metawingman/references/domain-packs",
            self.matrix,
        )
        self.assertTrue(report["valid"], report["issues"])
        diagnostic = next(
            item for item in report["profiles"] if item["id"] == "diagnostic"
        )
        self.assertNotEqual(diagnostic["validation_level"], "externally_validated")
        self.assertEqual(
            diagnostic["scientific_claim_level"],
            "implemented_not_scientifically_validated",
        )
        self.assertIn("unsupported_combinations", report)
        self.assertEqual(report["unsupported_combinations"], [])

    def test_domain_pack_hash_drift_fails_closed(self) -> None:
        matrix = deepcopy(self.matrix)
        matrix["biomedical_coverage"]["pack_inventory"][0]["content_sha256"] = "0" * 64
        report = audit_biomedical_coverage(
            ROOT / "metawingman/references/domain-packs", matrix
        )
        self.assertFalse(report["valid"])
        self.assertIn("domain_pack_hash_changed", {
            item["code"] for item in report["issues"]
        })

    def test_terminology_release_drift_fails_closed(self) -> None:
        matrix = deepcopy(self.matrix)
        matrix["biomedical_coverage"]["pack_inventory"][0]["terminology_releases"] = [{
            "system": "SNOMED CT",
            "release": "2099-01-01",
            "content_sha256": "1" * 64,
        }]
        report = audit_biomedical_coverage(
            ROOT / "metawingman/references/domain-packs", matrix
        )
        self.assertFalse(report["valid"])
        self.assertIn("terminology_release_changed", {
            item["code"] for item in report["issues"]
        })

    def test_missing_biomedical_capability_evidence_fails_closed(self) -> None:
        matrix = deepcopy(self.matrix)
        matrix["biomedical_coverage"]["capability_evidence"][0]["evidence_paths"] = [
            "references/not-real.md"
        ]
        report = audit_biomedical_coverage(
            ROOT / "metawingman/references/domain-packs", matrix
        )
        self.assertFalse(report["valid"])
        self.assertIn("missing_capability_evidence", {
            item["code"] for item in report["issues"]
        })

    def test_missing_profile_is_rejected_even_when_schema_is_valid(self) -> None:
        matrix = deepcopy(self.matrix)
        matrix["review_profiles"] = matrix["review_profiles"][:-1]
        report = audit_capability_matrix(matrix, ROOT / "metawingman")
        self.assertFalse(report["valid"])
        self.assertTrue(any("review profile mismatch" in issue for issue in report["issues"]))

    def test_advanced_validation_requires_evidence(self) -> None:
        matrix = deepcopy(self.matrix)
        matrix["lifecycle_stages"][0]["validation_level"] = "prospective_passed"
        matrix["lifecycle_stages"][0]["validation_evidence"] = []
        report = audit_capability_matrix(matrix, ROOT / "metawingman")
        self.assertFalse(report["valid"])
        self.assertTrue(any("advanced validation without evidence" in issue for issue in report["issues"]))

    def test_missing_evidence_path_is_rejected(self) -> None:
        matrix = deepcopy(self.matrix)
        matrix["lifecycle_stages"][0]["evidence_paths"] = ["references/not-real.md"]
        report = audit_capability_matrix(matrix, ROOT / "metawingman")
        self.assertFalse(report["valid"])
        self.assertTrue(any("missing evidence path" in issue for issue in report["issues"]))


class ConclusionDirectedAcquisitionTests(unittest.TestCase):
    def test_high_impact_gap_continues_and_ranks_legal_actions(self) -> None:
        decision = plan_evidence_acquisition(acquisition_state(), created_at_utc=TIMESTAMP)
        self.assertEqual(decision["status"], "continue")
        self.assertFalse(decision["stop_allowed"])
        self.assertEqual(decision["selected_actions"][0]["action_id"], "add-registry")
        self.assertEqual(decision["selected_actions"][0]["action_type"], "registry_search")
        self.assertEqual(decision["selected_actions"][0]["target_criterion_ids"], ["population"])
        self.assertGreater(
            decision["selected_actions"][0]["utility_score"],
            decision["selected_actions"][1]["utility_score"],
        )
        self.assertIn("licensed-export", decision["blocked_action_ids"])
        self.assertEqual(decision["high_impact_criterion_ids"], ["population"])
        self.assertFalse(decision["human_review"]["required"])

    def test_controller_can_prefer_compute_verifier_action_for_high_harm_claim_gap(self) -> None:
        state = acquisition_state()
        state["candidate_actions"].append({
            "action_id": "recompute-pooled-effect",
            "action_type": "recompute_synthesis",
            "target_criterion_ids": ["population"],
            "expected_risk_reduction": 0.2,
            "expected_claim_impact": 0.95,
            "source_family_gain": 0,
            "estimated_cost_units": 0.5,
            "estimate_basis": "heuristic",
            "legally_available": True,
            "credential_status": "not_required",
            "rationale": "Recompute the claim-critical synthesis to reduce asymmetric harm from a misleading conclusion.",
        })
        decision = plan_evidence_acquisition(state, created_at_utc=TIMESTAMP)
        self.assertEqual(decision["status"], "continue")
        self.assertEqual(decision["selected_actions"][0]["action_id"], "recompute-pooled-effect")
        self.assertEqual(decision["selected_actions"][0]["action_type"], "recompute_synthesis")
        self.assertIn("asymmetric_harm_weighted", decision["selected_actions"][0]["reason_codes"])
        self.assertIn("compute_or_verifier_action", decision["selected_actions"][0]["reason_codes"])

    def test_stop_requires_all_frozen_risk_and_impact_thresholds(self) -> None:
        state = acquisition_state()
        state["criterion_states"][0].update({
            "residual_omission_risk": 0.02,
            "hard_negative_error_rate": 0.01,
            "unresolved_records": 0,
            "independent_source_count": 3,
        })
        state["global_signals"].update({"known_item_recall": 0.99, "source_family_count": 4})
        decision = plan_evidence_acquisition(state, created_at_utc=TIMESTAMP)
        self.assertEqual(decision["status"], "stop_candidate")
        self.assertTrue(decision["stop_allowed"])
        self.assertTrue(decision["human_review"]["required"])
        self.assertEqual(decision["human_review"]["status"], "pending")

    def test_uncalibrated_critical_gap_without_legal_action_abstains(self) -> None:
        state = acquisition_state()
        state["criterion_states"][0].update({
            "calibration_status": "unavailable",
            "residual_omission_risk": None,
            "downstream_claim_impact": None,
        })
        for action in state["candidate_actions"]:
            action["legally_available"] = False
            action["credential_status"] = "unavailable"
        decision = plan_evidence_acquisition(state, created_at_utc=TIMESTAMP)
        self.assertEqual(decision["status"], "abstain")
        self.assertFalse(decision["stop_allowed"])
        self.assertIn("population", decision["uncalibrated_criterion_ids"])
        self.assertIn("no_executable_evidence_action", decision["reason_codes"])
        self.assertIn("lawful_access_unavailable", decision["reason_codes"])

    def test_historical_reconstruction_abstains_on_leakage(self) -> None:
        state = acquisition_state()
        state["global_signals"].update({
            "run_context": "historical_reconstruction",
            "temporal_boundary_status": "contaminated",
            "leakage_audit": "failed",
        })
        decision = plan_evidence_acquisition(state, created_at_utc=TIMESTAMP)
        self.assertEqual(decision["status"], "abstain")
        self.assertIn("historical_temporal_boundary_not_sealed", decision["reason_codes"])
        self.assertIn("historical_leakage_audit_not_passed", decision["reason_codes"])

    def test_unknown_target_criterion_is_rejected(self) -> None:
        state = acquisition_state()
        state["candidate_actions"][0]["target_criterion_ids"] = ["unknown"]
        with self.assertRaises(EvidenceAcquisitionError):
            plan_evidence_acquisition(state, created_at_utc=TIMESTAMP)

    def test_deterministic_state_hash_and_ranking(self) -> None:
        first = plan_evidence_acquisition(acquisition_state(), created_at_utc=TIMESTAMP)
        second = plan_evidence_acquisition(acquisition_state(), created_at_utc=TIMESTAMP)
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
