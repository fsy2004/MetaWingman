from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "metawingman/scripts"))

from metawingman_core.schema_guard import validate_document  # noqa: E402


class BenchmarkDiscoveryCatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = json.loads(
            (ROOT / "research/meta-reproduction-discovery-catalog.json").read_text(
                encoding="utf-8"
            )
        )

    def test_catalog_validates_and_is_broad(self) -> None:
        validate_document(self.catalog, "benchmark_discovery_catalog")
        self.assertGreaterEqual(len(self.catalog["candidates"]), 15)
        review_types = {item["review_type"] for item in self.catalog["candidates"]}
        self.assertTrue({"living_network", "living_diagnostic", "ipd", "diagnostic", "meta_regression"}.issubset(review_types))

    def test_identities_are_unique_and_primary_urls_match_pmcid(self) -> None:
        ids = [item["candidate_id"] for item in self.catalog["candidates"]]
        dois = [item["publication"]["doi"].lower() for item in self.catalog["candidates"]]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(len(dois), len(set(dois)))
        for item in self.catalog["candidates"]:
            publication = item["publication"]
            self.assertIn(publication["pmcid"], publication["url"])

    def test_end_to_end_ceiling_is_not_assigned_by_discovery_alone(self) -> None:
        self.assertNotIn(
            "end_to_end_candidate",
            {item["reproduction_ceiling"] for item in self.catalog["candidates"]},
        )

    def test_catalog_exports_every_identity_for_live_citation_verification(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "citations.csv"
            completed = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "metawingman/scripts/export_benchmark_citations.py"),
                    str(ROOT / "research/meta-reproduction-discovery-catalog.json"),
                    str(output),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertIn('"exported": 18', completed.stdout)
            self.assertEqual(len(output.read_text(encoding="utf-8-sig").splitlines()), 19)


if __name__ == "__main__":
    unittest.main()
