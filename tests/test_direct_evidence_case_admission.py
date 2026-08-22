from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from metawingman.scripts.metawingman_core.case_admission import (
    CaseAdmissionError,
    validate_case_registry,
)


ROOT = Path(__file__).resolve().parents[1]


class DirectEvidenceCaseAdmissionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.path = ROOT / "research/direct-evidence-case-registry-v1.json"
        self.registry = json.loads(self.path.read_text(encoding="utf-8"))

    def test_registry_passes_representativeness_authority_and_split_gates(self) -> None:
        result = validate_case_registry(self.registry)
        self.assertGreaterEqual(result["development_candidates"], 2)
        self.assertEqual(result["held_out_candidates"], 0)
        self.assertEqual(result["locked_execution_ready"], 0)
        self.assertTrue(self.registry["selection_policy"]["authority_is_admission_only"])
        self.assertTrue(self.registry["selection_policy"]["authority_is_never_a_score_feature"])
        self.assertIn("diagnostic_accuracy", result["represented_profile_strata"])
        self.assertIn("structured_no_pooling", result["represented_profile_strata"])
        self.assertIn("prognostic_prediction", result["represented_profile_strata"])
        self.assertIn("prevalence_incidence", result["represented_profile_strata"])
        self.assertEqual(result["missing_profile_strata"], [])

    def test_registry_binds_training_corpus_and_has_no_heldout_identity_overlap(self) -> None:
        result = validate_case_registry(self.registry)
        self.assertTrue(result["training_corpus_binding_verified"])
        self.assertEqual(result["held_out_training_identity_overlaps"], [])

    def test_exact_training_doi_cannot_be_admitted_as_heldout(self) -> None:
        registry = copy.deepcopy(self.registry)
        contaminated = next(
            case for case in registry["cases"]
            if case["case_id"] == "nature-heat-maternal-neonatal"
        )
        contaminated["split"] = "held_out"
        contaminated["training_use"] = "forbidden"
        with self.assertRaisesRegex(CaseAdmissionError, "held-out identity overlaps training corpus"):
            validate_case_registry(registry)

    def test_new_representative_profile_cases_are_stage_limited_development_only(self) -> None:
        by_id = {case["case_id"]: case for case in self.registry["cases"]}
        for case_id in (
            "bmj-type2-diabetes-risk-models-2011",
            "jama-global-child-obesity-prevalence-2024",
        ):
            case = by_id[case_id]
            self.assertEqual(case["split"], "development")
            self.assertEqual(case["training_use"], "audit_only")
            self.assertEqual(case["execution_status"], "blocked_material_audit")
            self.assertNotEqual(case["operational_materials"]["screening_reference"], "verified")

    def test_material_snapshot_receipt_hash_drift_fails_closed(self) -> None:
        registry = copy.deepcopy(self.registry)
        case = next(
            item for item in registry["cases"]
            if item["case_id"] == "bmj-type2-diabetes-risk-models-2011"
        )
        case["material_snapshot_receipt"]["sha256"] = "0" * 64
        with self.assertRaisesRegex(CaseAdmissionError, "material snapshot receipt hash mismatch"):
            validate_case_registry(registry)

    def test_authoritative_stress_cases_are_development_not_held_out(self) -> None:
        by_id = {case["case_id"]: case for case in self.registry["cases"]}
        ag = by_id["ag-rdt-living-dta"]
        suicide = by_id["covid-suicide-self-harm-living"]
        self.assertEqual(ag["split"], "development")
        self.assertEqual(suicide["split"], "development")
        self.assertEqual(ag["evidence_scale"]["route"], "diagnostic_accuracy_review")
        self.assertEqual(suicide["evidence_scale"]["route"], "structured_narrative_review")
        self.assertEqual(ag["reference_version_graph"]["target_version_id"], "ag-rdt-2022-update")
        self.assertEqual(suicide["reference_version_graph"]["target_version_id"], "suicide-lsr-june7-v1")
        self.assertEqual(
            by_id["nature-heat-maternal-neonatal"]["split"], "diagnostic_only"
        )
        self.assertEqual(
            by_id["lancet-antidepressants-acute-mdd-nma"]["split"], "diagnostic_only"
        )

    def test_held_out_case_is_forbidden_from_training(self) -> None:
        registry = copy.deepcopy(self.registry)
        held_out = next(
            case for case in registry["cases"]
            if case["case_id"] == "lancet-antidepressants-acute-mdd-nma"
        )
        held_out["split"] = "held_out"
        held_out["training_use"] = "stage_verified_only"
        with self.assertRaisesRegex(CaseAdmissionError, "held-out.*training"):
            validate_case_registry(registry)

    def test_living_run_ready_case_requires_a_resolved_version_graph(self) -> None:
        registry = copy.deepcopy(self.registry)
        case = next(case for case in registry["cases"] if case["case_id"] == "ag-rdt-living-dta")
        case["execution_status"] = "run_ready"
        case["reference_version_graph"]["binding_status"] = "version_mixed_invalid"
        case["operational_materials"] = {key: "verified" for key in case["operational_materials"]}
        with self.assertRaisesRegex(CaseAdmissionError, "resolved reference version graph"):
            validate_case_registry(registry)

    def test_small_niche_case_cannot_enter_development(self) -> None:
        registry = copy.deepcopy(self.registry)
        case = registry["cases"][0]
        case["evidence_scale"] = {"route": "network_or_living_nma", "studies": 7, "participants": 900, "countries": 1}
        with self.assertRaisesRegex(CaseAdmissionError, "representativeness floor"):
            validate_case_registry(registry)

    def test_run_ready_case_requires_exact_cutoff_and_complete_operational_materials(self) -> None:
        registry = copy.deepcopy(self.registry)
        case = registry["cases"][0]
        case["execution_status"] = "run_ready"
        with self.assertRaisesRegex(CaseAdmissionError, "exact historical cutoff|operational materials"):
            validate_case_registry(registry)

    def test_review_family_cannot_cross_development_and_held_out(self) -> None:
        registry = copy.deepcopy(self.registry)
        held_out = next(
            case for case in registry["cases"]
            if case["case_id"] == "lancet-antidepressants-acute-mdd-nma"
        )
        held_out["split"] = "held_out"
        held_out["training_use"] = "forbidden"
        held_out["review_family_id"] = registry["cases"][0]["review_family_id"]
        with self.assertRaisesRegex(CaseAdmissionError, "crosses development and held-out"):
            validate_case_registry(registry)

    def test_prestige_or_authority_cannot_be_used_as_a_score(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["selection_policy"]["authority_is_never_a_score_feature"] = False
        with self.assertRaisesRegex(CaseAdmissionError, "score feature"):
            validate_case_registry(registry)


if __name__ == "__main__":
    unittest.main()
