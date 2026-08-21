from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "metawingman" / "scripts"
if str(CORE) not in sys.path:
    sys.path.insert(0, str(CORE))

from metawingman_core.schema_guard import SchemaValidationError, validate_document


REGISTRY = ROOT / "metawingman" / "references" / "question-synthesis-methods.json"
R_MANIFESTS = ROOT / "metawingman" / "scripts" / "r" / "manifests"


def candidate_fixture() -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "candidate_id": "candidate-1",
        "context_id": "context-1",
        "parent_candidate_id": None,
        "mutation": {"type": "seed", "rationale": "Frozen seed."},
        "question_framework": {
            "population": ["adults"],
            "intervention_or_exposure": ["intervention"],
            "comparator": ["usual care"],
            "outcome": ["mortality"],
            "study_design": ["randomized trial"],
        },
        "review_family": "intervention",
        "estimand": {
            "population": "eligible randomized participants",
            "treatment_condition": "assignment to intervention versus usual care",
            "variable": "all-cause mortality",
            "population_summary": "risk ratio at longest follow-up",
            "intercurrent_event_strategy": "treatment policy",
        },
        "synthesis_route": "pairwise_random_effects",
        "data_requirements": ["events", "denominators"],
        "evidence_anchor_ids": ["evidence-1"],
        "assumption_checks": [{"check_id": "effect_measure", "status": "passed", "reason": "Binary outcome."}],
        "feasibility": {"status": "verified", "reasons": ["eligible studies available"]},
        "overlap": {"status": "not_duplicative", "reasons": ["scope differs"]},
        "uncertainty": {"level": "moderate", "reasons": ["event sparsity"]},
        "disposition": "frontier",
        "created_at_utc": "2026-08-20T00:00:00Z",
    }


class QuestionSynthesisContractTests(unittest.TestCase):
    def test_candidate_requires_clinical_estimand_and_method(self) -> None:
        candidate = candidate_fixture()
        validate_document(candidate, "question_synthesis_candidate")
        del candidate["estimand"]
        with self.assertRaises(SchemaValidationError):
            validate_document(candidate, "question_synthesis_candidate")

    def test_candidate_contract_is_closed(self) -> None:
        candidate = candidate_fixture()
        candidate["model_score"] = 0.99
        with self.assertRaises(SchemaValidationError):
            validate_document(candidate, "question_synthesis_candidate")

    def test_registry_contains_no_pooling_and_swim_routes(self) -> None:
        payload = json.loads(REGISTRY.read_text(encoding="utf-8"))
        route_ids = {item["route_id"] for item in payload["routes"]}
        self.assertIn("no_pooling", route_ids)
        self.assertIn("swim_structured_synthesis", route_ids)

    def test_registry_adapters_resolve_to_current_manifests(self) -> None:
        payload = json.loads(REGISTRY.read_text(encoding="utf-8"))
        manifest_ids = {
            json.loads(path.read_text(encoding="utf-8"))["id"]
            for path in R_MANIFESTS.glob("*.json")
        }
        unknown = {
            item["r_adapter"]
            for item in payload["routes"]
            if item["r_adapter"] is not None and item["r_adapter"] not in manifest_ids
        }
        self.assertEqual(unknown, set())


if __name__ == "__main__":
    unittest.main()
