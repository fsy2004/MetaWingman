from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RECEIPT = ROOT / "research/protocol-agent-distillation-training-receipt-v1.json"
REPORT = ROOT / "docs/architecture/protocol-agent-distillation-bootstrap-results-2026-08-22.md"
SHA256 = re.compile(r"^[a-f0-9]{64}$")


class ProtocolAgentTrainingReceiptTests(unittest.TestCase):
    def test_public_receipt_is_consistent_and_development_bounded(self) -> None:
        value = json.loads(RECEIPT.read_text(encoding="utf-8"))
        self.assertEqual(value["status"], "completed_development_bootstrap")
        self.assertEqual(
            value["scientific_claim_status"],
            "development_only_student_gain_not_generalization",
        )
        seeds = value["evaluation"]["seeds"]
        self.assertEqual([row["seed"] for row in seeds], [20260822, 20260823, 20260824])
        base = sum(row["baseline_complete_action_accuracy"] for row in seeds) / len(seeds)
        student = sum(row["student_complete_action_accuracy"] for row in seeds) / len(seeds)
        self.assertEqual(value["evaluation"]["baseline_mean_complete_action_accuracy"], base)
        self.assertEqual(value["evaluation"]["student_mean_complete_action_accuracy"], student)
        self.assertGreater(student, base)
        for row in seeds:
            self.assertRegex(row["receipt_sha256"], SHA256)
            self.assertRegex(row["adapter_sha256"], SHA256)
        serialized = RECEIPT.read_text(encoding="utf-8")
        self.assertNotIn("/root/", serialized)
        self.assertNotRegex(serialized, r"(?i)[A-Z]:\\Users\\")
        self.assertTrue(REPORT.is_file())


if __name__ == "__main__":
    unittest.main()
