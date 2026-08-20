from __future__ import annotations

import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "metawingman/references/human-methodology-training-registry.json"
SCHEMA = ROOT / "metawingman/schemas/human_methodology_training_registry.schema.json"


class HumanMethodologyGroundingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
        cls.schema = json.loads(SCHEMA.read_text(encoding="utf-8"))

    def test_registry_matches_schema(self) -> None:
        errors = sorted(
            Draft202012Validator(self.schema).iter_errors(self.registry),
            key=lambda error: list(error.absolute_path),
        )
        self.assertEqual([], errors, "\n".join(error.message for error in errors))

    def test_core_professional_authorities_are_present(self) -> None:
        source_ids = {source["source_id"] for source in self.registry["sources"]}
        self.assertTrue(
            {
                "cochrane-handbook-ch01",
                "cochrane-handbook-ch02",
                "cochrane-handbook-ch03",
                "cochrane-handbook-ch04",
                "cochrane-handbook-ch09",
                "cochrane-handbook-ch10",
                "mecir-2023-revised-2024",
                "jbi-manual-2024-live",
                "prisma-2020",
                "prisma-p-2015",
                "prisma-s-2021",
                "prisma-lsr-2024",
                "swim-2020",
                "amstar-2-2017",
                "robins-i-2016",
                "probast-ai-2025",
                "grade-book-live-2026-08-20",
                "ai-evidence-synthesis-position-2025",
            }.issubset(source_ids)
        )

    def test_threshold_provenance_cannot_promote_placeholders(self) -> None:
        provenance = self.registry["threshold_provenance"]
        self.assertEqual(
            {
                "normative_requirement",
                "primary_study_empirical",
                "project_calibrated",
                "engineering_placeholder",
            },
            set(provenance),
        )
        self.assertFalse(provenance["engineering_placeholder"]["may_support_scientific_release"])
        self.assertTrue(provenance["project_calibrated"]["requires_frozen_calibration_record"])

    def test_full_text_is_not_bundled_and_every_rule_is_anchored(self) -> None:
        self.assertFalse(self.registry["distribution_policy"]["full_text_bundled"])
        allowed = set(self.registry["threshold_provenance"])
        rule_count = 0
        for source in self.registry["sources"]:
            for artifact in source["local_artifacts"]:
                self.assertFalse(artifact["bundled"])
                self.assertRegex(artifact["sha256"], r"^[0-9a-f]{64}$")
            for rule in source["supported_rules"]:
                rule_count += 1
                self.assertIn(rule["provenance"], allowed)
                self.assertTrue(rule["anchors"])
                self.assertNotEqual("engineering_placeholder", rule["provenance"])
        self.assertGreaterEqual(rule_count, 20)

    def test_agent_sources_cannot_override_human_methodology(self) -> None:
        self.assertEqual(
            "engineering_candidates_only",
            self.registry["agent_literature_role"],
        )
        self.assertEqual(
            "human_methodology_and_frozen_protocol",
            self.registry["method_authority"],
        )


if __name__ == "__main__":
    unittest.main()
