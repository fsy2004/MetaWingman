"""Tests for the Socratic checklist checker."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "metawingman" / "scripts"))

from check_socratic_checklist import check_answers, _load_checklist  # noqa: E402


class SocraticChecklistTests(unittest.TestCase):
    def setUp(self) -> None:
        self.skill_root = REPO / "metawingman"

    def test_all_three_checklists_load(self) -> None:
        for stage in ("screening", "appraisal", "analysis"):
            checklist = _load_checklist(stage, self.skill_root)
            self.assertGreaterEqual(len(checklist["items"]), 8, stage)

    def test_full_answers_pass(self) -> None:
        for stage in ("screening", "appraisal", "analysis"):
            checklist = _load_checklist(stage, self.skill_root)
            answers = {item["id"]: f"answered-{item['id']}" for item in checklist["items"]}
            report = check_answers(stage, answers, self.skill_root)
            self.assertTrue(report["passed"], (stage, report))

    def test_missing_required_fails(self) -> None:
        report = check_answers("screening", {"screening-01": "yes"}, self.skill_root)
        self.assertFalse(report["passed"])
        self.assertIn("screening-02", report["missing_required"])

    def test_optional_missing_passes_unless_strict(self) -> None:
        checklist = _load_checklist("screening", self.skill_root)
        answers = {item["id"]: "x" for item in checklist["items"] if item["gate"] == "required"}
        self.assertTrue(check_answers("screening", answers, self.skill_root)["passed"])
        self.assertFalse(check_answers("screening", answers, self.skill_root, strict=True)["passed"])


if __name__ == "__main__":
    unittest.main()
