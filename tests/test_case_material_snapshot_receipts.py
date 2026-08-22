from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

from metawingman.scripts.metawingman_core.schema_guard import validate_document


ROOT = Path(__file__).resolve().parents[1]


class CaseMaterialSnapshotReceiptTests(unittest.TestCase):
    def test_representative_case_snapshots_are_hash_bound_and_non_promotional(self) -> None:
        receipt = json.loads(
            (ROOT / "research/case-material-snapshots-v1.json").read_text(encoding="utf-8")
        )
        validate_document(receipt, "case_material_snapshot_receipt")
        registry = json.loads(
            (ROOT / "research/direct-evidence-case-registry-v1.json").read_text(encoding="utf-8")
        )
        cases = {case["case_id"]: case for case in registry["cases"]}
        self.assertEqual(len(receipt["snapshots"]), 3)
        self.assertEqual(
            receipt["correct_server_host_key_prefix"], "7d79b1266d43faef"
        )
        for snapshot in receipt["snapshots"]:
            case = cases[snapshot["case_id"]]
            self.assertEqual(case["split"], "development")
            self.assertNotEqual(case["split"], "held_out")
            self.assertNotEqual(case["execution_status"], "run_ready")
            binding = case["material_snapshot_receipt"]
            bound_path = ROOT / binding["path"]
            self.assertEqual(
                hashlib.sha256(bound_path.read_bytes()).hexdigest(), binding["sha256"]
            )
            self.assertEqual(snapshot["verification_status"], "created_and_reverified")
            self.assertTrue(snapshot["scientific_boundary"])
            self.assertRegex(snapshot["files"]["oa_package"]["sha256"], r"^[0-9a-f]{64}$")
            self.assertTrue(any(item["path"].endswith(".nxml") for item in snapshot["archive_members"]))
            self.assertTrue(any(item["path"].endswith(".pdf") for item in snapshot["archive_members"]))
        exercise = next(row for row in receipt["snapshots"] if row["case_id"] == "bmj-exercise-depression-nma")
        self.assertEqual(exercise["external_repositories"][0]["license_status"], "no_license_selected")
        names = {row["name"] for row in exercise["external_repositories"][0]["files"]}
        self.assertIn("S1 Search Strategy Exercise Depression Network Meta.docx", names)
        self.assertIn("S2 Consensus reasons for exclusion.xlsx", names)
        self.assertIn("depression_data_analysis.Rmd", names)


if __name__ == "__main__":
    unittest.main()
