"""Tests for the Review Question Certificate generator (pipeline is injected,
no live provider calls)."""
from __future__ import annotations

import hashlib
import json
import sys
import unittest
from pathlib import Path
from typing import Any, Sequence

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "metawingman" / "scripts"))

from metawingman_core.model_provider import ProviderResult  # noqa: E402
from generate_review_question_certificate import (  # noqa: E402
    hard_gate,
    generate_certificate,
)

STAGE_PAYLOADS: dict[str, dict[str, Any]] = {
    "primitives": {
        "population": "adults with early diffuse cutaneous systemic sclerosis",
        "intervention": "anti-IL-6 therapy",
        "comparator": "placebo or standard care",
        "outcomes": [{"name": "modified Rodnan skin score change", "level": "patient_important", "timepoint": "48 weeks"}],
        "study_designs": ["RCT"],
    },
    "assumptions": {
        "first_principle_assumptions": [
            {"statement": "skin fibrosis progression is measurable within 48 weeks", "justification": "established trial endpoints use mRSS at 24-52 weeks"},
        ]
    },
    "mechanism": {
        "exposure": "IL-6 blockade",
        "outcome": "skin fibrosis",
        "pathway_nodes": ["IL-6 signalling", "fibroblast activation", "collagen deposition"],
        "moderators": ["disease duration"],
        "summary": "IL-6 blockade reduces fibroblast activation and collagen deposition in skin.",
    },
    "tension": {
        "type": "direction_inconsistency",
        "description": "trial effect directions vary across studies",
        "evidence_sources": [{"url_or_doi": "10.0000/example", "fetched": False}],
    },
    "question_hypothesis": {
        "research_question": "In adults with early dcSSc, does anti-IL-6 therapy reduce skin fibrosis at 48 weeks versus placebo?",
        "hypothesis": {
            "claim_mode": "hypothesis_test",
            "direction": "anti-IL-6 reduces mRSS versus placebo",
            "magnitude": "MCID-level reduction",
            "falsifiable_statement": "no mRSS improvement at 48 weeks in at least two high-quality RCTs rejects the hypothesis",
            "answerability_criterion": "the eligible RCT evidence permits an interpretable 48-week effect estimate",
            "heterogeneity_pattern": "effect larger in early disease",
        },
    },
    "test_update": {
        "minimal_decisive_test": {
            "description": "pool mRSS change at 48 weeks from placebo-controlled RCTs",
            "rejection_observation": "pooled mean difference crossing zero with narrow CI",
            "evidence_required": [">=2 RCTs with 48-week mRSS"],
        },
        "expected_observations": ["pooled MD favoring anti-IL-6"],
        "failure_update_rule": {
            "negative_result_action": "subgroup_refocus",
            "description": "refocus on early-disease subgroup if overall null",
        },
    },
    "scores": {
        "clinical_relevance": 4,
        "method_fit": 5,
        "traceability": 4,
        "explainability": 4,
        "reproducibility": 5,
    },
}


def _stub_result(stage: str, payloads: dict[str, dict[str, Any]]) -> ProviderResult:
    body = json.dumps(payloads[stage], ensure_ascii=False)
    return ProviderResult(
        provider="stub", model="stub", finish_reason="stop", content=body,
        content_sha256=hashlib.sha256(body.encode()).hexdigest(),
        prompt_tokens=1, completion_tokens=1, total_tokens=2, reasoning_tokens=None,
        system_fingerprint=None, credential_source="test",
    )


class _StubProvider:
    provider_name = "stub"
    model = "stub"
    credential_source = "test"

    def __init__(self, payloads: dict[str, dict[str, Any]] | None = None):
        self.payloads = payloads or STAGE_PAYLOADS

    def list_models(self) -> list[str]:
        return ["stub"]

    def chat(self, messages: Sequence[dict[str, Any]], **kwargs: Any) -> ProviderResult:
        content = messages[-1]["content"]
        for stage in ("primitives", "assumptions", "mechanism", "tension", "question_hypothesis", "test_update", "scores"):
            if f"STAGE: {stage}" in content:
                return _stub_result(stage, self.payloads)
        raise AssertionError(f"unexpected stage prompt: {content[:80]}")


class ReviewQuestionCertificateTests(unittest.TestCase):
    def test_pipeline_generates_valid_certificate_and_passes_gate(self):
        cert = generate_certificate("Systemic sclerosis; anti-IL-6 therapy", _StubProvider(), lambda _t: [], created_at_utc="2026-08-18T00:00:00Z")
        self.assertTrue(cert["certificate_id"].startswith("rqc:"))
        self.assertTrue(cert["gate"]["passed"], cert["gate"])
        self.assertEqual(cert["quality_scores"]["provenance"], "model_proposed_unvalidated")
        self.assertFalse(cert["gate"]["scientific_release_ready"])
        self.assertEqual(cert["gate"]["scope"], "candidate_structure_only")
        self.assertIn("prompt_sha256s", cert["audit"])

    def test_novelty_verdict_covered_fails_gate(self):
        cert = generate_certificate("Systemic sclerosis; anti-IL-6 therapy", _StubProvider(), lambda _t: [{"title": "anti-IL-6 therapy for systemic sclerosis review", "source": "europepmc", "identifier": "1"}], created_at_utc="2026-08-18T00:00:00Z")
        self.assertEqual(cert["novelty_gate"]["verdict"], "covered")
        self.assertFalse(cert["gate"]["passed"])
        self.assertIn("novelty_verdict_covered", cert["gate"]["hard_failures"])

    def test_estimation_question_does_not_require_falsifiable_statement(self):
        payloads = dict(STAGE_PAYLOADS)
        payloads["question_hypothesis"] = {
            **STAGE_PAYLOADS["question_hypothesis"],
            "hypothesis": {
                **STAGE_PAYLOADS["question_hypothesis"]["hypothesis"],
                "claim_mode": "estimation",
                "direction": "",
                "falsifiable_statement": "",
            },
        }
        cert = generate_certificate("topic", _StubProvider(payloads), lambda _t: [], created_at_utc="2026-08-18T00:00:00Z")
        self.assertTrue(cert["gate"]["passed"], cert["gate"])

    def test_hypothesis_test_requires_falsifiable_statement(self):
        payloads = dict(STAGE_PAYLOADS)
        payloads["question_hypothesis"] = {
            **STAGE_PAYLOADS["question_hypothesis"],
            "hypothesis": {
                **STAGE_PAYLOADS["question_hypothesis"]["hypothesis"],
                "falsifiable_statement": "",
            },
        }
        cert = generate_certificate("topic", _StubProvider(payloads), lambda _t: [], created_at_utc="2026-08-18T00:00:00Z")
        self.assertFalse(cert["gate"]["passed"])
        self.assertIn("falsifiable_statement_empty", cert["gate"]["hard_failures"])

    def test_unvalidated_model_scores_cannot_be_a_scientific_hard_gate(self):
        cert = generate_certificate("topic", _StubProvider(), lambda _t: [], created_at_utc="2026-08-18T00:00:00Z")
        low = dict(cert)
        low["quality_scores"] = {**cert["quality_scores"], "method_fit": 2, "average": 4.0}
        gate = hard_gate(low)
        self.assertTrue(gate.passed)
        self.assertNotIn("method_fit_score_2_below_3", gate.hard_failures)
        self.assertIn("method_fit_model_score_low_requires_external_verification", gate.soft_repairs)


if __name__ == "__main__":
    unittest.main()
