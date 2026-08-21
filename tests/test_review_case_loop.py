from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "metawingman" / "scripts"
if str(CORE) not in sys.path:
    sys.path.insert(0, str(CORE))

from metawingman_core.reflection_engine import reflect_on_assertion
from metawingman_core.review_case import ReviewCaseError, initialize_review_case, transition_review_case
from test_question_synthesis_contracts import candidate_fixture


TIMESTAMP = "2026-08-20T00:00:00Z"


class ReviewCaseLoopTests(unittest.TestCase):
    def test_case_cannot_skip_protocol_gate(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            project = Path(folder)
            initialize_review_case(project, candidate_fixture(), created_at_utc=TIMESTAMP)
            with self.assertRaises(ReviewCaseError):
                transition_review_case(
                    project,
                    {"action_id": "analysis-1", "stage": "analysis", "expected_revision": 0},
                    {"status": "verified", "external": True, "node_ids": ["analysis-1"]},
                    updated_at_utc=TIMESTAMP,
                )

    def test_reflection_without_external_observation_cannot_change_state(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            project = Path(folder)
            initialize_review_case(project, candidate_fixture(), created_at_utc=TIMESTAMP)
            report = reflect_on_assertion(
                project,
                {
                    "schema_version": "1.0",
                    "reflection_id": "reflection-1",
                    "assertion_id": "assertion-1",
                    "proposed_change": {"field": "active_stage", "value": "analysis"},
                    "external_tests": [],
                    "created_at_utc": TIMESTAMP,
                },
                {},
            )
            self.assertEqual(report["disposition"], "abstained")
            self.assertFalse(report["state_changed"])


if __name__ == "__main__":
    unittest.main()
