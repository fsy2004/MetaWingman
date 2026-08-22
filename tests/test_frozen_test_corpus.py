from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from metawingman.scripts.build_frozen_test_corpus import _family_ids, select_test_records


class FrozenTestCorpusTests(unittest.TestCase):
    def test_select_test_records_is_deterministic_and_excludes_existing_families(self) -> None:
        records = []
        for index in range(12):
            records.append(
                {
                    "record_id": f"r{index}",
                    "family_id": f"family-{index}",
                    "pmcid": f"PMC{index}",
                    "declared_license": "cc by",
                    "title": "Systematic review",
                }
            )
        # families 0-4 are used by the existing train/dev corpus and must be excluded.
        excluded = {f"family-{index}" for index in range(5)}
        first = select_test_records(records, excluded, max_test_articles=5)
        second = select_test_records(list(reversed(records)), excluded, max_test_articles=5)
        self.assertEqual([row["record_id"] for row in first], [row["record_id"] for row in second])
        self.assertEqual(len(first), 5)
        self.assertTrue(all(row["family_id"] not in excluded for row in first))

    def test_family_ids_reads_existing_jsonl(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "train.jsonl"
            path.write_text(
                json.dumps({"family_id": "a"}) + "\n" + json.dumps({"family_id": "b"}) + "\n",
                encoding="utf-8",
            )
            self.assertEqual(_family_ids(path), {"a", "b"})

    def test_license_gate_excludes_non_permissive_articles(self) -> None:
        records = [
            {"record_id": "ok", "family_id": "f1", "pmcid": "PMC1", "declared_license": "cc by", "title": "R"},
            {"record_id": "bad", "family_id": "f2", "pmcid": "PMC2", "declared_license": "all rights reserved", "title": "R"},
            {"record_id": "nopmc", "family_id": "f3", "pmcid": "", "declared_license": "cc by", "title": "R"},
        ]
        selected = select_test_records(records, set(), max_test_articles=10)
        self.assertEqual([row["record_id"] for row in selected], ["ok"])


if __name__ == "__main__":
    unittest.main()
