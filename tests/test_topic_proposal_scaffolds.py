from __future__ import annotations

import unittest

from metawingman.scripts.metawingman_core.topic_proposal_scaffolds import (
    build_exhaustive_topic_proposal_shards,
    build_topic_proposal_scaffolds,
)

from test_topic_opportunity_and_provider import landscape


class TopicProposalScaffoldTests(unittest.TestCase):
    def test_scaffolds_are_deterministic_bounded_and_schema_valid(self) -> None:
        state = landscape()
        first = build_topic_proposal_scaffolds(
            state, seed=20260826, maximum_scaffolds=3, maximum_publications=2,
            created_at_utc="2026-08-22T12:00:00Z",
        )
        second = build_topic_proposal_scaffolds(
            state, seed=20260826, maximum_scaffolds=3, maximum_publications=2,
            created_at_utc="2026-08-22T12:00:00Z",
        )
        self.assertEqual(first, second)
        self.assertGreaterEqual(len(first["scaffolds"]), 1)
        self.assertEqual(
            first["scaffolds"][0]["audit"]["selection_method"],
            "uniform_evidence_then_degree_seeded_cooccurrence_scaffolds_v2",
        )
        for scaffold in first["scaffolds"]:
            publications = [node for node in scaffold["landscape"]["nodes"] if node["node_type"] != "concept"]
            self.assertLessEqual(len(publications), 2)
            self.assertTrue(scaffold["audit"]["target_identity_used"] is False)
            self.assertIn("scaffold", scaffold["landscape"]["landscape_id"])

    def test_requires_concepts_and_publications(self) -> None:
        state = landscape()
        state["nodes"] = [node for node in state["nodes"] if node["node_type"] != "concept"]
        state["edges"] = []
        with self.assertRaisesRegex(ValueError, "concept"):
            build_topic_proposal_scaffolds(
                state, seed=1, maximum_scaffolds=2, maximum_publications=2,
                created_at_utc="2026-08-22T12:00:00Z",
            )

    def test_exhaustive_shards_cover_each_publication_exactly_once(self) -> None:
        state = landscape()
        result = build_exhaustive_topic_proposal_shards(
            state, seed=20260829, maximum_publications=1, maximum_shards=10,
            created_at_utc="2026-08-22T15:00:00Z",
        )
        observed = []
        for item in result["scaffolds"]:
            publications = [n["node_id"] for n in item["landscape"]["nodes"] if n["node_type"] != "concept"]
            self.assertLessEqual(len(publications), 1)
            observed.extend(publications)
        expected = sorted(n["node_id"] for n in state["nodes"] if n["node_type"] != "concept")
        self.assertEqual(sorted(observed), expected)
        self.assertEqual(result["audit"]["coverage_fraction"], 1.0)


if __name__ == "__main__":
    unittest.main()
