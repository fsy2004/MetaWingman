from __future__ import annotations

import sys
import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "metawingman" / "scripts"
if str(CORE) not in sys.path:
    sys.path.insert(0, str(CORE))

from metawingman_core.clinical_question import compile_clinical_decision_context
from metawingman_core.synthesis_method_router import (
    enumerate_synthesis_routes,
    load_method_registry,
)
from metawingman_core.question_synthesis_search import (
    QuestionSynthesisSearchError,
    apply_candidate_mutation,
    select_frontier_node,
    start_question_synthesis_search,
)
from metawingman_core.model_provider import ProviderResult
from metawingman_core.question_synthesis_agents import run_question_role
from metawingman_core.question_synthesis_design import design_review_question
from metawingman_core.question_synthesis_verifier import QuestionSynthesisVerificationError
from metawingman_core.question_synthesis_verifier import verify_question_candidate
from test_question_synthesis_contracts import candidate_fixture


TIMESTAMP = "2026-08-20T00:00:00Z"
REGISTRY = ROOT / "metawingman" / "references" / "question-synthesis-methods.json"


class ClinicalQuestionCompilerTests(unittest.TestCase):
    def test_compiler_preserves_raw_wording_and_marks_missing_decision(self) -> None:
        context = compile_clinical_decision_context(
            {"population": "adults with resistant hypertension"},
            created_at_utc=TIMESTAMP,
        )
        self.assertEqual(context["status"], "incomplete")
        self.assertEqual(context["source_anchors"][0]["verbatim"], "adults with resistant hypertension")

    def test_compiler_does_not_invent_actions_or_outcomes(self) -> None:
        context = compile_clinical_decision_context(
            {"decision_problem": "Which treatment should be selected?"},
            created_at_utc=TIMESTAMP,
        )
        self.assertEqual(context["candidate_actions"], [])
        self.assertEqual(context["patient_important_outcomes"], [])


class SynthesisMethodRouterTests(unittest.TestCase):
    def test_router_rejects_network_route_without_connected_comparators(self) -> None:
        candidate = candidate_fixture()
        candidate["review_family"] = "network"
        candidate["synthesis_route"] = "network_random_effects"
        candidate["assumption_checks"] = [
            {"check_id": "network_connectivity", "status": "failed", "reason": "Disconnected comparator graph."}
        ]
        context = compile_clinical_decision_context(
            {
                "decision_problem": "Which intervention is preferable?",
                "candidate_actions": ["choose an intervention"],
                "outcomes": ["mortality"],
            },
            created_at_utc=TIMESTAMP,
        )
        candidate["context_id"] = context["context_id"]
        decision = enumerate_synthesis_routes(
            context,
            candidate,
            load_method_registry(REGISTRY),
            created_at_utc=TIMESTAMP,
        )
        rejected = {item["route_id"]: item for item in decision["rejected_routes"]}
        self.assertIn("network_random_effects", rejected)
        self.assertIn("network_connectivity", rejected["network_random_effects"]["failed_checks"])

    def test_router_never_uses_registry_order_to_choose_multiple_routes(self) -> None:
        context = compile_clinical_decision_context(
            {
                "decision_problem": "Which intervention is preferable?",
                "candidate_actions": ["choose an intervention"],
                "outcomes": ["mortality"],
            },
            created_at_utc=TIMESTAMP,
        )
        candidate = candidate_fixture()
        candidate["context_id"] = context["context_id"]
        decision = enumerate_synthesis_routes(
            context,
            candidate,
            load_method_registry(REGISTRY),
            created_at_utc=TIMESTAMP,
        )
        if len(decision["compatible_routes"]) > 1:
            self.assertIsNone(decision["selected_route_id"])
            self.assertEqual(decision["status"], "requires_choice")


class QuestionSynthesisSearchTests(unittest.TestCase):
    def _context(self) -> dict[str, object]:
        return compile_clinical_decision_context(
            {
                "decision_problem": "Which intervention is preferable?",
                "candidate_actions": ["choose an intervention"],
                "outcomes": ["mortality"],
            },
            created_at_utc=TIMESTAMP,
        )

    def _candidates(self, context_id: str) -> list[dict[str, object]]:
        first = candidate_fixture()
        first["candidate_id"] = "candidate-b"
        first["context_id"] = context_id
        second = candidate_fixture()
        second["candidate_id"] = "candidate-a"
        second["context_id"] = context_id
        return [first, second]

    def test_frontier_selection_is_order_invariant(self) -> None:
        context = self._context()
        landscape = {"landscape_id": "landscape-1", "nodes": [{"node_id": "evidence-1"}]}
        candidates = self._candidates(str(context["context_id"]))
        budget = {"max_nodes": 8, "max_model_calls": 8, "max_verifier_calls": 16, "max_rounds": 4}
        first = start_question_synthesis_search(landscape, context, list(reversed(candidates)), budget, created_at_utc=TIMESTAMP)
        second = start_question_synthesis_search(landscape, context, candidates, budget, created_at_utc=TIMESTAMP)
        self.assertEqual(select_frontier_node(first), select_frontier_node(second))

    def test_mutation_cannot_reference_unknown_evidence(self) -> None:
        context = self._context()
        search = start_question_synthesis_search(
            {"landscape_id": "landscape-1", "nodes": [{"node_id": "evidence-1"}]},
            context,
            self._candidates(str(context["context_id"])),
            {"max_nodes": 8, "max_model_calls": 8, "max_verifier_calls": 16, "max_rounds": 4},
            created_at_utc=TIMESTAMP,
        )
        with self.assertRaises(QuestionSynthesisSearchError):
            apply_candidate_mutation(
                search,
                {"type": "request_evidence", "parent_candidate_id": "candidate-a"},
                {"evidence_anchor_ids": ["missing-node"], "verifier_id": "source"},
                updated_at_utc=TIMESTAMP,
            )


class FixtureProvider:
    credential_source = "fixture"

    def __init__(self, payload: dict[str, object]):
        self.payload = payload

    def list_models(self) -> list[str]:
        return ["fixture"]

    def chat(self, messages, *, model=None, thinking=False, reasoning_effort="low", max_tokens=128, json_output=False):
        content = json.dumps(self.payload)
        return ProviderResult(
            provider="fixture",
            model=model or "fixture",
            finish_reason="stop",
            content=content,
            content_sha256=hashlib.sha256(content.encode()).hexdigest(),
            prompt_tokens=10,
            completion_tokens=20,
            total_tokens=30,
            reasoning_tokens=0,
            system_fingerprint="fixture-v1",
            credential_source="fixture",
        )


class QuestionSynthesisAgentTests(unittest.TestCase):
    def test_model_self_score_is_discarded(self) -> None:
        payload = candidate_fixture()
        payload["score"] = 0.99
        result = run_question_role(
            FixtureProvider(payload),
            "proposer",
            {"context": {"context_id": "context-1"}},
            model="fixture",
            max_tokens=800,
        )
        self.assertNotIn("score", result["document"])
        self.assertNotIn("content", result["provider_receipt"])

    def test_external_verifier_blocks_failed_route(self) -> None:
        candidate = candidate_fixture()
        route_decision = {
            "status": "abstained",
            "selected_route_id": None,
            "compatible_routes": [{"route_id": "no_pooling", "failed_checks": []}],
            "rejected_routes": [{"route_id": "pairwise_random_effects", "failed_checks": ["effect_measure"]}],
        }
        observations = verify_question_candidate(
            candidate,
            {"nodes": [{"node_id": "evidence-1"}], "corpus_boundary": {"cutoff_date": "2026-08-20"}},
            route_decision,
        )
        by_id = {item["verifier_id"]: item for item in observations}
        self.assertEqual(by_id["synthesis_route"]["status"], "failed")

    def test_orchestrator_cannot_select_candidate_with_failed_route(self) -> None:
        context = compile_clinical_decision_context(
            {
                "decision_problem": "Which intervention is preferable?",
                "candidate_actions": ["choose an intervention"],
                "outcomes": ["mortality"],
            },
            created_at_utc=TIMESTAMP,
        )
        candidate = candidate_fixture()
        candidate["context_id"] = context["context_id"]
        candidate["review_family"] = "network"
        candidate["synthesis_route"] = "network_random_effects"
        candidate["assumption_checks"] = [
            {"check_id": "network_connectivity", "status": "failed", "reason": "Disconnected comparator graph."}
        ]
        with self.assertRaises(QuestionSynthesisVerificationError):
            design_review_question(
                provider=FixtureProvider(candidate),
                landscape={"landscape_id": "landscape-1", "nodes": [{"node_id": "evidence-1"}], "corpus_boundary": {"cutoff_date": "2026-08-20"}},
                context=context,
                routes=load_method_registry(REGISTRY),
                budget={"max_nodes": 8, "max_model_calls": 8, "max_verifier_calls": 16, "max_rounds": 4},
                model="fixture",
                max_tokens=800,
                created_at_utc=TIMESTAMP,
                role_sequence=["proposer"],
            )


if __name__ == "__main__":
    unittest.main()
