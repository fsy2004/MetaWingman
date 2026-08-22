from __future__ import annotations

import unittest

from metawingman.scripts.metawingman_core.topic_proposal_subgraph import (
    build_topic_proposal_subgraph,
)


class TopicProposalSubgraphTests(unittest.TestCase):
    def test_deterministic_stratified_subgraph_is_schema_valid_and_bounded(self) -> None:
        nodes = []
        edges = []
        for index in range(12):
            node_id = f"publication-{index}"
            nodes.append({
                "node_id": node_id, "node_type": "publication", "label": f"Study {index}",
                "domain_ids": ["mental-health"], "observed_at": "2023-01-01",
                "source_ids": [f"pmid:{index}"], "provenance_status": "verified",
            })
            concept_id = "concept-a" if index % 2 == 0 else "concept-b"
            edges.append({
                "edge_id": f"edge-{index}", "source_node_id": node_id,
                "target_node_id": concept_id, "relation": "mentions",
                "observed_at": "2023-01-01", "source_ids": [f"pmid:{index}"],
            })
        for concept_id in ("concept-a", "concept-b"):
            nodes.append({
                "node_id": concept_id, "node_type": "concept", "label": concept_id,
                "domain_ids": ["mental-health"], "observed_at": "2023-01-01",
                "source_ids": [f"pmid:{index}" for index in range(12)],
                "provenance_status": "machine_extracted",
            })
        landscape = {
            "schema_version": "1.0", "landscape_id": "landscape-full",
            "run_context": "historical_rediscovery", "domain_ids": ["mental-health"],
            "corpus_boundary": {
                "cutoff_date": "2023-06-03", "target_identity_status": "sealed",
                "target_descendants_status": "sealed", "post_cutoff_evidence_status": "sealed",
                "leakage_audit": "passed", "excluded_identity_fields": ["authors", "doi"],
            },
            "nodes": nodes, "edges": edges,
            "selection_policy": {
                "policy_version": "topic-policy-v1",
                "weights": {"decision_relevance": .2, "unresolved_uncertainty": .15, "feasibility": .15, "evidence_maturity": .1, "nonduplication": .15, "update_need": .1, "equity_priority": .1, "cross_domain_value": .05},
                "minimum_primary_studies": 3, "minimum_source_families": 2,
                "minimum_known_item_recall": .8, "maximum_review_overlap": .6,
                "maximum_contamination_risk": .2, "maximum_ambiguity_risk": .3,
                "minimum_utility_score": .5, "maximum_portfolio_size": 3,
                "diversity_penalty": .1, "allow_update_topics": True,
            },
            "created_at_utc": "2026-08-22T06:00:00Z",
        }
        first = build_topic_proposal_subgraph(
            landscape, seed=20260820, maximum_publications=4,
            created_at_utc="2026-08-22T06:30:00Z",
        )
        second = build_topic_proposal_subgraph(
            landscape, seed=20260820, maximum_publications=4,
            created_at_utc="2026-08-22T06:30:00Z",
        )
        self.assertEqual(first, second)
        publications = [node for node in first["landscape"]["nodes"] if node["node_type"] == "publication"]
        self.assertEqual(len(publications), 4)
        self.assertEqual(first["audit"]["full_publications"], 12)
        self.assertTrue(all(len(node["source_ids"]) <= 4 for node in first["landscape"]["nodes"]))


if __name__ == "__main__":
    unittest.main()
