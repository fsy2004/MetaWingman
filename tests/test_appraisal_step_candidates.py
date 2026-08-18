"""Tests for the appraisal-step weak-supervision candidate builder."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "metawingman" / "scripts"))

from build_appraisal_step_candidates import build_candidates, classify_domain  # noqa: E402


class AppraisalStepCandidateTests(unittest.TestCase):
    def test_classify_domain_rules(self) -> None:
        self.assertEqual(classify_domain("allocation concealment was adequate"), "selection_bias")
        self.assertEqual(classify_domain("outcome assessors were blinded"), "detection_bias")
        self.assertEqual(classify_domain("no mention of risk of bias"), "other")
        self.assertEqual(classify_domain("the sky is blue"), "abstain")

    def test_build_candidates_writes_only_appraisal(self) -> None:
        examples = [
            {"task": "section_role_classification", "target": {"section_role": "appraisal"}, "example_id": "e1", "family_id": "f1", "split": "train", "input_text": "blinding of participants was performed"},
            {"task": "section_role_classification", "target": {"section_role": "search"}, "example_id": "e2", "family_id": "f2", "split": "train", "input_text": "blinding of participants"},
            {"task": "section_role_classification", "target": {"section_role": "appraisal"}, "example_id": "e3", "family_id": "f3", "split": "train", "input_text": "unrelated prose"},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "examples.jsonl"
            src.write_text("\n".join(json.dumps(e) for e in examples), encoding="utf-8")
            out = Path(tmp) / "candidates.jsonl"
            stats = build_candidates(src, out, Path(tmp) / "stats.json")
            self.assertEqual(stats["written"], 1)
            self.assertEqual(stats["label_counts"], {"performance_bias": 1, "abstain": 1})

    def test_weak_label_status_is_declared(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "examples.jsonl"
            src.write_text(json.dumps({"task": "section_role_classification", "target": {"section_role": "appraisal"}, "example_id": "e1", "family_id": "f1", "split": "train", "input_text": "selective reporting suspected"}), encoding="utf-8")
            out = Path(tmp) / "candidates.jsonl"
            build_candidates(src, out, Path(tmp) / "stats.json")
            candidate = json.loads(out.read_text(encoding="utf-8").strip())
            self.assertEqual(candidate["label_status"], "deterministic_weak_supervision_requires_independent_validation")
            self.assertEqual(candidate["weak_label"], "reporting_bias")


if __name__ == "__main__":
    unittest.main()

