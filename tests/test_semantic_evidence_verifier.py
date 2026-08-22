from __future__ import annotations

import copy
import unittest

from metawingman.scripts.metawingman_core.evidence_semantic_verifier import (
    EvidenceSemanticVerifierError,
    verify_evidence_bindings,
)


def record() -> dict:
    return {
        "id": "report-1",
        "title": "Example diagnostic accuracy report",
        "doi": "10.1000/example.1",
        "version_id": "journal-v1",
        "study_family_id": "study-family-1",
        "cutoff_verification": {
            "status": "passed",
            "conservative_latest_date": "2020-06-01",
        },
        "results": [{
            "result_id": "result-sensitivity-7d",
            "arm": "index-test-positive",
            "comparator_arm": "reference-standard-positive",
            "timepoint": "7-days-since-symptom-onset",
            "effect_measure": "sensitivity",
            "effect_value": 0.84,
            "numerator": 84,
            "denominator": 100,
            "source_span_sha256": "b" * 64,
        }],
    }


def binding(binding_id: str = "binding-correct") -> dict:
    source = record()
    return {
        "binding_id": binding_id,
        "record_id": source["id"],
        "identity": {
            "title": source["title"],
            "doi": source["doi"],
            "version_id": source["version_id"],
            "study_family_id": source["study_family_id"],
        },
        "result": copy.deepcopy(source["results"][0]),
    }


class SemanticEvidenceVerifierTests(unittest.TestCase):
    def test_correct_identity_version_lineage_and_result_are_accepted(self) -> None:
        report = verify_evidence_bindings([record()], [binding()], cutoff="2020-06-07")
        self.assertEqual(report["accepted_binding_ids"], ["binding-correct"])
        self.assertEqual(report["audit"]["accepted"], 1)
        self.assertEqual(report["audit"]["rejected"], 0)

    def test_identity_and_version_counterfactuals_are_rejected_separately(self) -> None:
        variants = []
        for field, value in (
            ("doi", "10.1000/collision"),
            ("title", "A colliding but different report"),
            ("version_id", "preprint-v1"),
            ("study_family_id", "wrong-study-family"),
        ):
            item = binding(f"wrong-{field}")
            item["identity"][field] = value
            variants.append(item)
        report = verify_evidence_bindings([record()], variants, cutoff="2020-06-07")
        self.assertEqual(report["accepted_binding_ids"], [])
        self.assertEqual(
            report["audit"]["reason_counts"],
            {
                "doi_mismatch": 1,
                "study_family_mismatch": 1,
                "title_mismatch": 1,
                "version_mismatch": 1,
            },
        )

    def test_wrong_sign_denominator_timepoint_arm_and_span_are_rejected(self) -> None:
        changes = (
            ("effect_value", -0.84, "effect_value_mismatch"),
            ("denominator", 84, "denominator_mismatch"),
            ("timepoint", "30-days", "timepoint_mismatch"),
            ("arm", "wrong-arm", "arm_mismatch"),
            ("source_span_sha256", "c" * 64, "source_span_mismatch"),
        )
        variants = []
        for field, value, _reason in changes:
            item = binding(f"wrong-{field}")
            item["result"][field] = value
            variants.append(item)
        report = verify_evidence_bindings([record()], variants, cutoff="2020-06-07")
        self.assertEqual(report["accepted_binding_ids"], [])
        self.assertEqual(
            report["audit"]["reason_counts"],
            {reason: 1 for _field, _value, reason in changes},
        )

    def test_unknown_and_postcutoff_records_fail_closed(self) -> None:
        unknown = binding("unknown")
        unknown["record_id"] = "absent"
        late_record = record()
        late_record["id"] = "late"
        late_record["cutoff_verification"]["conservative_latest_date"] = "2020-06-08"
        late = binding("late")
        late["record_id"] = "late"
        report = verify_evidence_bindings(
            [record(), late_record], [unknown, late], cutoff="2020-06-07"
        )
        self.assertEqual(
            report["audit"]["reason_counts"],
            {"post_cutoff": 1, "unknown_record": 1},
        )

    def test_duplicate_binding_ids_are_rejected(self) -> None:
        with self.assertRaisesRegex(EvidenceSemanticVerifierError, "binding_id"):
            verify_evidence_bindings(
                [record()], [binding(), binding()], cutoff="2020-06-07"
            )


if __name__ == "__main__":
    unittest.main()
