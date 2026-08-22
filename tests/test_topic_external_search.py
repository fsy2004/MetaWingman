from __future__ import annotations

import unittest

from metawingman.scripts.metawingman_core.topic_external_search import (
    build_topic_audit_queries,
    compile_topic_external_search_receipt,
)


class TopicExternalSearchTests(unittest.TestCase):
    def test_builds_bounded_queries_and_maps_only_landscape_pmids(self) -> None:
        proposal = {
            "proposal_id": "proposal-1",
            "evidence_node_ids": ["pub-1", "pub-2"],
            "question_framework": {
                "population": ["adults with depression"],
                "intervention_or_exposure": ["exercise", "walking"],
                "comparator": ["usual care"], "outcome": ["depressive symptoms"],
                "study_design": ["randomised trials"], "synthesis_route": "network meta-analysis",
            },
        }
        queries = build_topic_audit_queries(proposal, cutoff_date="2023-06-03", lower_date="2021-01-01")
        self.assertEqual(set(queries), {"primary_studies", "reviews", "protocols"})
        self.assertIn('"2023/06/03"[Date - Publication]', queries["reviews"])
        self.assertIn('"depression"[Title/Abstract]', queries["reviews"])
        landscape = {
            "corpus_boundary": {"cutoff_date": "2023-06-03"},
            "nodes": [
                {"node_id": "pub-1", "node_type": "publication", "label": "Exercise randomized trial for adults with depression", "observed_at": "2022-06-01", "source_ids": ["pmid:1"], "domain_ids": ["mental-health"]},
                {"node_id": "pub-2", "node_type": "publication", "label": "Exercise meta-analysis for depression", "observed_at": "2021-06-01", "source_ids": ["pmid:2"], "domain_ids": ["mental-health"]},
            ],
        }
        raw = {
            "primary_studies": {"query": queries["primary_studies"], "pmids": ["1", "999"]},
            "reviews": {"query": queries["reviews"], "pmids": ["2"]},
            "protocols": {"query": queries["protocols"], "pmids": ["777"]},
        }
        receipt = compile_topic_external_search_receipt(proposal, landscape, raw)
        self.assertEqual(receipt["primary_study_node_ids"], ["pub-1"])
        self.assertEqual(receipt["review_matches"][0]["node_id"], "pub-2")
        self.assertEqual(receipt["protocol_result_count"], 1)
        self.assertEqual(receipt["proposal_evidence_recall"], 1.0)
        self.assertEqual(receipt["unmapped_pmids"], ["777", "999"])
        self.assertEqual(receipt["provider_calls"], 0)

    def test_primary_search_adapts_to_observational_study_design(self) -> None:
        proposal = {
            "question_framework": {
                "population": ["children"], "intervention_or_exposure": ["screen time"],
                "outcome": ["sleep duration"],
                "study_design": ["prospective cohort studies", "cross-sectional studies"],
            }
        }
        query = build_topic_audit_queries(
            proposal, cutoff_date="2015-06-15", lower_date="2011-01-01",
        )["primary_studies"]
        self.assertIn("cohort studies[MeSH Terms]", query)
        self.assertIn("cross-sectional studies[MeSH Terms]", query)
        self.assertNotIn("randomized controlled trial[Publication Type]", query)

    def test_evidence_anchor_labels_expand_synonyms_without_identifiers(self) -> None:
        proposal = {
            "evidence_node_ids": ["pub-tv"],
            "question_framework": {
                "population": ["children"], "intervention_or_exposure": ["screen time"],
                "outcome": ["sleep duration"], "study_design": ["cohort studies"],
            },
        }
        landscape = {"nodes": [{
            "node_id": "pub-tv", "node_type": "publication",
            "label": "Hours of television viewing and sleep duration in children",
            "source_ids": ["pmid:24615283"],
        }]}
        query = build_topic_audit_queries(
            proposal, cutoff_date="2015-06-15", lower_date="2011-01-01",
            landscape=landscape,
        )["primary_studies"]
        self.assertIn('"television"[Title/Abstract]', query)
        self.assertNotIn("24615283", query)
        self.assertNotIn("Hours of television viewing and sleep duration in children", query)


if __name__ == "__main__":
    unittest.main()
