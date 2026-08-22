import unittest

from metawingman.scripts.metawingman_core.acquisition_scoring import (
    ScoringError,
    extract_screening_reference_rows,
    validate_exact_receipt_slots,
)
from metawingman.scripts.metawingman_core.conclusion_directed_acquisition import (
    CONFIGURATIONS,
)


class LivingReviewScoringTests(unittest.TestCase):
    def test_screening_gold_uses_expert_include_only(self):
        rows = [
            ["title", "link", "initial_decision", "expert_decision"],
            ["Included title", "https://pubmed.ncbi.nlm.nih.gov/12345678/", "Exclude", "Include"],
            ["Excluded title", "https://doi.org/10.1000/excluded", "Include", "Exclude"],
            ["Pending title", "", "Include", ""],
        ]
        extracted, audit = extract_screening_reference_rows(rows)
        self.assertEqual(extracted, [{"doi": "", "pmid": "12345678", "title": "included title", "study": ""}])
        self.assertEqual(audit["expert_included_rows"], 1)
        self.assertEqual(audit["expert_excluded_rows"], 1)
        self.assertEqual(audit["expert_unresolved_rows"], 1)

    def test_exact_receipt_slots_reject_unregistered_seed(self):
        receipts = [
            {
                "configuration_id": configuration,
                "seed": seed,
                "plan_id": "plan",
                "case_id": "case",
                "corpus_sha256": "a" * 64,
                "status": "completed",
            }
            for configuration in CONFIGURATIONS
            for seed in (20260820, 20260821, 20260822)
        ]
        validate_exact_receipt_slots(
            receipts,
            plan_id="plan",
            case_id="case",
            corpus_sha256="a" * 64,
        )
        receipts[-1] = {**receipts[-1], "seed": 99999999}
        with self.assertRaisesRegex(ScoringError, "exact frozen Cartesian"):
            validate_exact_receipt_slots(
                receipts,
                plan_id="plan",
                case_id="case",
                corpus_sha256="a" * 64,
            )


if __name__ == "__main__":
    unittest.main()
