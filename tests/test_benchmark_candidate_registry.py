from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "metawingman/scripts"))

from metawingman_core.schema_guard import validate_document  # noqa: E402


class BenchmarkCandidateRegistryTests(unittest.TestCase):
    def test_registry_validates_and_has_no_end_to_end_overclaim(self) -> None:
        registry = json.loads(
            (ROOT / "research/benchmark-candidate-registry.json").read_text(encoding="utf-8")
        )
        validate_document(registry, "benchmark_candidate_registry")
        for candidate in registry["candidates"]:
            if "end_to_end" in candidate["supported_scopes"]:
                coverage = candidate["material_coverage"]
                self.assertEqual(coverage["search_export"], "present")
                self.assertEqual(coverage["screening_labels"], "present")
                self.assertEqual(coverage["extraction"], "present")
                self.assertEqual(coverage["analysis_code"], "present")
                self.assertNotEqual(candidate["license_status"], "review_required")

    def test_candidate_and_family_ids_are_unique(self) -> None:
        registry = json.loads(
            (ROOT / "research/benchmark-candidate-registry.json").read_text(encoding="utf-8")
        )
        candidate_ids = [item["candidate_id"] for item in registry["candidates"]]
        family_ids = [item["review_family_id"] for item in registry["candidates"]]
        self.assertEqual(len(candidate_ids), len(set(candidate_ids)))
        self.assertEqual(len(family_ids), len(set(family_ids)))

    def test_verified_publications_have_doi_and_primary_url(self) -> None:
        registry = json.loads(
            (ROOT / "research/benchmark-candidate-registry.json").read_text(encoding="utf-8")
        )
        for candidate in registry["candidates"]:
            publication = candidate["publication"]
            if publication["identity_status"] == "verified_primary":
                self.assertTrue(publication["doi"].startswith("10."))
                self.assertIn(
                    "pmc.ncbi.nlm.nih.gov/articles/PMC", publication["url"]
                )
                source_types = {
                    item["source_type"] for item in candidate["verification_sources"]
                }
                self.assertIn("primary_publication", source_types)
                self.assertIn("repository", source_types)


if __name__ == "__main__":
    unittest.main()
