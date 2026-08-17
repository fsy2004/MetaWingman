from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "metawingman/scripts"))

from metawingman_core.schema_guard import validate_document  # noqa: E402


class TopicTargetRegistryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = json.loads(
            (ROOT / "research/topic-rediscovery-target-registry.json").read_text(
                encoding="utf-8"
            )
        )

    def test_registry_validates_and_spans_domains(self) -> None:
        validate_document(self.registry, "topic_target_registry")
        targets = self.registry["targets"]
        self.assertGreaterEqual(len(targets), 15)
        domains = {domain for target in targets for domain in target["domain_ids"]}
        self.assertGreaterEqual(len(domains), 12)
        self.assertTrue(
            {"obstetrics", "ecology", "economics", "psychology", "education"}.issubset(domains)
        )

    def test_identity_and_family_keys_are_unique(self) -> None:
        targets = self.registry["targets"]
        for field in ("target_id", "review_family_id"):
            values = [target[field] for target in targets]
            self.assertEqual(len(values), len(set(values)))
        dois = [target["publication"]["doi"].casefold() for target in targets]
        self.assertEqual(len(dois), len(set(dois)))

    def test_broad_intake_is_not_mislabeled_as_blind_test(self) -> None:
        targets = self.registry["targets"]
        self.assertTrue(self.registry["admission_policy"]["strict_blind_test_is_separate"])
        self.assertNotIn("sealed_case_ready", {target["strict_test_status"] for target in targets})
        for target in targets:
            if target["strict_test_status"] == "boundary_ready":
                self.assertEqual(
                    target["historical_boundary"]["status"],
                    "publisher_methods_verified",
                )

    def test_every_target_has_integrity_action_and_corrections_are_bound(self) -> None:
        targets = self.registry["targets"]
        corrected = [
            target for target in targets
            if target["publication_integrity"]["status"] == "publisher_correction"
        ]
        self.assertGreaterEqual(len(corrected), 2)
        for target in targets:
            integrity = target["publication_integrity"]
            self.assertIn(
                integrity["benchmark_action"],
                {"use_current_version", "use_corrected_version_only", "exclude_until_integrity_resolved", "exclude"},
            )
            if integrity["status"] == "publisher_correction":
                self.assertTrue(integrity["related_notices"])
                self.assertEqual(integrity["benchmark_action"], "use_corrected_version_only")


if __name__ == "__main__":
    unittest.main()
