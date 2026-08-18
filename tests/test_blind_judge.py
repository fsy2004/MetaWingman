"""Tests for the double-judge blind certificate scoring."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from typing import Any, Sequence

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "metawingman" / "scripts"))

from blind_judge_certificates import (  # noqa: E402
    blind_certificate,
    build_report,
    judge_scores,
    _pearson,
)


def make_cert() -> dict:
    return {
        "schema_version": "1.0",
        "certificate_id": "rqc:" + "a" * 64,
        "created_at_utc": "2026-08-18T00:00:00Z",
        "topic": {"domain": "x", "working_title": "t", "candidate_question_text": "q"},
        "primitives": {},
        "first_principle_assumptions": [],
        "mechanism_model": {},
        "tension": {},
        "research_question": "R?",
        "hypothesis": {"falsifiable_statement": "f"},
        "minimal_decisive_test": {},
        "expected_observations": [],
        "failure_update_rule": {},
        "novelty_gate": {"existing_reviews": [], "gap_statement": "g", "verdict": "novel"},
        "quality_scores": {"derivation": 5, "falsifiability": 5, "mechanism_clarity": 5, "novelty": 5, "experimentability": 5, "average": 5.0},
        "gate": {"passed": True, "hard_failures": [], "soft_repairs": []},
        "audit": {"provider": "secret-generator", "model": "m", "prompt_sha256s": {}, "provider_content_sha256": "h"},
    }


class _StubJudge:
    provider_name = "stub-judge"
    model = "stub"
    credential_source = "test"

    def __init__(self, scores: dict[str, int]):
        self.scores = scores

    def list_models(self) -> list[str]:
        return ["stub"]

    def chat(self, messages: Sequence[dict[str, Any]], **kwargs: Any) -> Any:
        return type("R", (), {
            "content": json.dumps({"scores": self.scores, "overall": 4, "rationale": "ok"}),
            "content_sha256": "x",
        })()


class BlindJudgeTests(unittest.TestCase):
    def test_blinding_strips_metadata(self) -> None:
        blinded = blind_certificate(make_cert())
        for key in ("audit", "quality_scores", "gate", "certificate_id", "created_at_utc", "schema_version"):
            self.assertNotIn(key, blinded)

    def test_judge_scores_parses(self) -> None:
        scores = judge_scores(_StubJudge({"derivation": 4, "falsifiability": 5, "mechanism_clarity": 4, "novelty": 3, "experimentability": 5}), make_cert())
        self.assertEqual(scores["scores"]["derivation"], 4)

    def test_report_ranking_and_agreement(self) -> None:
        a1 = {"scores": {"derivation": 4, "falsifiability": 4, "mechanism_clarity": 4, "novelty": 4, "experimentability": 4}, "overall": 4, "rationale": ""}
        a2 = {"scores": {"derivation": 2, "falsifiability": 2, "mechanism_clarity": 2, "novelty": 2, "experimentability": 2}, "overall": 2, "rationale": ""}
        b1 = {"scores": {"derivation": 5, "falsifiability": 5, "mechanism_clarity": 5, "novelty": 5, "experimentability": 5}, "overall": 5, "rationale": ""}
        b2 = {"scores": {"derivation": 1, "falsifiability": 1, "mechanism_clarity": 1, "novelty": 1, "experimentability": 1}, "overall": 1, "rationale": ""}
        report = build_report(["c1", "c2"], [a1, a2], [b1, b2])
        self.assertEqual(report["ranking"], ["c1", "c2"])
        self.assertAlmostEqual(report["inter_judge_pearson"], 1.0, places=3)

    def test_pearson(self) -> None:
        self.assertAlmostEqual(_pearson([1, 2, 3], [2, 4, 6]), 1.0, places=6)
        self.assertAlmostEqual(_pearson([1, 2, 3], [3, 2, 1]), -1.0, places=6)


if __name__ == "__main__":
    unittest.main()
