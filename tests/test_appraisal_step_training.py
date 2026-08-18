"""Tests for appraisal-step training helpers (no torch import at module level)."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "metawingman" / "scripts"))

from run_appraisal_step_training import (  # noqa: E402
    DOMAIN_LABELS,
    _inverse_frequency_weights,
    load_candidates,
    records_to_pairs,
    split_records,
)


def make_candidates() -> list[dict]:
    return [
        {"split": "train", "weak_label": "selection_bias", "text": "allocation concealment adequate"},
        {"split": "train", "weak_label": "other", "text": "risk of bias discussed"},
        {"split": "train", "weak_label": "other", "text": "quality of studies"},
        {"split": "development", "weak_label": "attrition_bias", "text": "lost to follow-up"},
        {"split": "development", "weak_label": "abstain", "text": "unrelated prose"},
    ]


class AppraisalStepTrainingTests(unittest.TestCase):
    def test_split_records(self) -> None:
        train, dev = split_records(make_candidates())
        self.assertEqual(len(train), 3)
        self.assertEqual(len(dev), 2)

    def test_records_to_pairs_maps_labels_and_skips_abstain(self) -> None:
        pairs = records_to_pairs(make_candidates())
        self.assertEqual(len(pairs), 4)
        self.assertEqual(pairs[0]["label"], 0)  # selection_bias
        self.assertNotIn("abstain", [p["label"] for p in pairs])

    def test_inverse_frequency_weights(self) -> None:
        weights = _inverse_frequency_weights([0, 1, 1, 1])
        self.assertAlmostEqual(weights[0], 2.0, places=6)
        self.assertAlmostEqual(weights[1], 2.0 / 3, places=6)

    def test_load_candidates_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "candidates.jsonl"
            path.write_text("\n".join(json.dumps(c) for c in make_candidates()), encoding="utf-8")
            loaded = load_candidates(path)
            self.assertEqual(len(loaded), 5)

    def test_domain_labels_order(self) -> None:
        self.assertEqual(len(DOMAIN_LABELS), 6)
        self.assertEqual(DOMAIN_LABELS[-1], "other")


if __name__ == "__main__":
    unittest.main()
