from __future__ import annotations

import json
import unittest

from metawingman.scripts.metawingman_core.design_selection import (
    ESTIMAND_TEMPLATES,
    PROFILE_STRATA,
    SYNTHESIS_ROUTES,
    DesignSelectionError,
    derive_review_design,
)


# Representative (question, landscape) -> expected profile, mirroring the 8-strata
# representative-case registry gold.
CASES = [
    (
        {"type": "intervention", "intervention_count": 6, "is_living_or_update": True},
        {"arms_per_study": 3, "comparator_count": 8, "is_update": True},
        "intervention_network", True,
    ),  # like BMJ exercise-depression living NMA
    (
        {"type": "intervention", "intervention_count": 2, "is_living_or_update": False},
        {"arms_per_study": 2, "comparator_count": 1},
        "intervention_pairwise", False,
    ),  # like Nature psychological wellbeing pairwise
    (
        {"type": "diagnostic", "has_index_test_reference": True},
        {"has_reference_standard": True, "n_nodes_assessed": True},
        "diagnostic_accuracy", False,
    ),  # like Ag-RDT diagnostic test accuracy
    (
        {"type": "prediction", "has_prediction_model": True},
        {"has_prediction_model": True, "n_nodes_assessed": True},
        "prognostic_prediction", False,
    ),  # like BMJ type-2-diabetes risk models
    (
        {"type": "prevalence", "intervention_count": 0},
        {"outcome_unit": "proportion", "n_nodes_assessed": True},
        "prevalence_incidence", False,
    ),  # like JAMA global child obesity prevalence
    (
        {"type": "exposure", "is_public_health_exposure": True},
        {"exposure_outcome_design": "observational", "has_geographic_dose_heterogeneity": True},
        "public_health_exposure", False,
    ),  # like heat maternal-neonatal
    (
        {"type": "exposure", "is_public_health_exposure": True, "is_living_or_update": True},
        {"exposure_outcome_design": "observational", "is_update": True},
        "public_health_exposure", True,
    ),  # like suicide self-harm living review
]


class DesignSelectionTests(unittest.TestCase):
    def test_all_eight_strata_are_defined(self) -> None:
        self.assertEqual(len(PROFILE_STRATA), 8)
        for strata in PROFILE_STRATA:
            self.assertIn(strata, ESTIMAND_TEMPLATES)
            self.assertIn(strata, SYNTHESIS_ROUTES)

    def test_routes_to_correct_profile_and_living_flag(self) -> None:
        for question, landscape, expected, expected_living in CASES:
            with self.subTest(expected=expected):
                decision = derive_review_design(question, landscape)
                self.assertFalse(decision.abstain, decision.abstain_reason)
                self.assertEqual(decision.profile, expected)
                self.assertEqual(decision.living, expected_living)
                self.assertTrue(decision.estimand)
                self.assertTrue(decision.synthesis_route)
                self.assertTrue(decision.decision_tension)
                self.assertGreater(decision.confidence, 0.5)

    def test_estimand_synthesis_route_are_profile_consistent(self) -> None:
        decision = derive_review_design(
            {"type": "diagnostic", "has_index_test_reference": True},
            {"has_reference_standard": True, "n_nodes_assessed": True},
        )
        self.assertEqual(decision.estimand, ESTIMAND_TEMPLATES["diagnostic_accuracy"])
        self.assertIn("bivariate", decision.synthesis_route.lower())

    def test_abstains_on_ambiguous_question(self) -> None:
        decision = derive_review_design({"type": "unknown", "intervention_count": 0}, {})
        self.assertTrue(decision.abstain)
        self.assertIsNotNone(decision.abstain_reason)

    def test_abstains_on_conflicting_signals(self) -> None:
        # diagnostic + prediction both strong, neither dominates -> abstain
        decision = derive_review_design(
            {"type": "diagnostic", "has_index_test_reference": True, "has_prediction_model": True},
            {"has_reference_standard": True, "has_prediction_model": True},
        )
        self.assertTrue(decision.abstain)

    def test_to_dict_is_serializable_and_complete(self) -> None:
        decision = derive_review_design(
            {"type": "intervention", "intervention_count": 2},
            {"arms_per_study": 2, "comparator_count": 1},
        )
        data = decision.to_dict()
        json.dumps(data)  # must be JSON-serializable
        for key in (
            "profile", "estimand", "synthesis_route", "justification", "confidence",
            "decision_tension", "minimal_decisive_question", "disconfirmation_design",
            "abstain",
        ):
            self.assertIn(key, data)


if __name__ == "__main__":
    unittest.main()
