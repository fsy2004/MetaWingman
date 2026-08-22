from __future__ import annotations

import copy
import unittest

from metawingman.scripts.metawingman_core.deterministic_topic_signal_audit import (
    DeterministicTopicAuditError,
    build_deterministic_topic_signal_audit,
)
from metawingman.scripts.metawingman_core.landscape_builder import (
    build_broad_temporal_landscape,
)


class TopicSignalConstructValidityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = {
            "policy_version": "topic-policy-v1",
            "weights": {
                "decision_relevance": 0.2,
                "unresolved_uncertainty": 0.15,
                "feasibility": 0.15,
                "evidence_maturity": 0.1,
                "nonduplication": 0.15,
                "update_need": 0.1,
                "equity_priority": 0.1,
                "cross_domain_value": 0.05,
            },
            "minimum_primary_studies": 2,
            "minimum_source_families": 1,
            "minimum_known_item_recall": 0.8,
            "maximum_review_overlap": 0.6,
            "maximum_contamination_risk": 0.2,
            "maximum_ambiguity_risk": 0.3,
            "minimum_utility_score": 0.5,
            "maximum_portfolio_size": 3,
            "diversity_penalty": 0.1,
            "allow_update_topics": True,
        }

    def _handcrafted_case(self) -> tuple[dict, dict, dict]:
        landscape = {
            "schema_version": "1.0",
            "landscape_id": "construct-landscape",
            "run_context": "historical_rediscovery",
            "domain_ids": ["mental-health", "public-health"],
            "corpus_boundary": {
                "cutoff_date": "2023-06-03",
                "target_identity_status": "sealed",
                "target_descendants_status": "sealed",
                "post_cutoff_evidence_status": "sealed",
                "leakage_audit": "passed",
                "excluded_identity_fields": [
                    "title", "authors", "doi", "pmid", "journal", "abstract",
                    "keywords", "citations", "descendants",
                ],
            },
            "nodes": [
                {
                    "node_id": "guideline-1", "node_type": "guideline",
                    "label": "National depression treatment guideline",
                    "domain_ids": ["mental-health"], "observed_at": "2020-01-01",
                    "source_ids": ["guideline:national-2020"],
                    "provenance_status": "verified",
                },
                {
                    "node_id": "pub-1", "node_type": "publication",
                    "label": "Depression intervention trial report",
                    "domain_ids": ["mental-health"], "observed_at": "2022-01-01",
                    "source_ids": ["pmid:1"], "provenance_status": "verified",
                },
                {
                    "node_id": "pub-2", "node_type": "publication",
                    "label": "Companion public-health report",
                    "domain_ids": ["public-health"], "observed_at": "2022-02-01",
                    "source_ids": ["pmid:2"], "provenance_status": "verified",
                },
                {
                    "node_id": "review-1", "node_type": "publication",
                    "label": "Earlier depression review",
                    "domain_ids": ["mental-health"], "observed_at": "2021-01-01",
                    "source_ids": ["pmid:3"], "provenance_status": "verified",
                },
                {
                    "node_id": "concept-depression", "node_type": "concept",
                    "label": "depression", "domain_ids": ["mental-health"],
                    "observed_at": "2020-01-01",
                    "source_ids": ["pmid:1", "pmid:2"],
                    "provenance_status": "machine_extracted",
                },
            ],
            "edges": [],
            "selection_policy": copy.deepcopy(self.policy),
            "created_at_utc": "2026-08-22T00:00:00Z",
        }
        proposal = {
            "proposal_id": "construct-proposal",
            "generation_method": "model_proposal",
            "question_framework": {
                "population": ["adults with depression"],
                "intervention_or_exposure": ["active treatment"],
                "comparator": ["usual care"],
                "outcome": ["depressive symptoms"],
                "study_design": ["randomised trials"],
                "synthesis_route": "pairwise meta-analysis",
            },
            "concept_node_ids": ["concept-depression"],
            "evidence_node_ids": ["guideline-1", "pub-1", "pub-2"],
            "evidence_interpretations": [
                {
                    "node_id": "guideline-1", "role": "decision_need",
                    "interpretation": "The guideline identifies a treatment decision.",
                },
                {
                    "node_id": "pub-1", "role": "uncertainty",
                    "interpretation": "Comparative uncertainty remains.",
                },
            ],
            "disconfirmation_queries": [
                {"check_type": "existing_review_overlap", "query": "depression review"}
            ],
            "status": "requires_independent_signal_audit",
        }
        receipt = {
            "schema_version": "1.0", "status": "completed",
            "engine": "ncbi_pubmed_eutils", "cutoff_date": "2023-06-03",
            "provider_calls": 0, "query_sha256s": ["a" * 64],
            "primary_study_node_ids": ["pub-1", "pub-2"],
            "primary_study_family_ids": {
                "pub-1": "trial-a", "pub-2": "trial-a",
            },
            "proposal_evidence_recall": 1.0,
            "review_matches": [{"node_id": "review-1", "framework_overlap": 0.5}],
            "protocol_matches": [], "protocol_result_count": 0,
            "newest_primary_date": "2022-02-01",
            "newest_review_date": "2021-01-01",
        }
        return landscape, proposal, receipt

    def _audit(self, landscape: dict, proposal: dict, receipt: dict) -> dict:
        return build_deterministic_topic_signal_audit(
            proposal, landscape, receipt,
            proposal_provider_id="deepseek-v4-flash",
            auditor_id="ncbi-audit-v1",
        )

    def _built_case(self, *, second_domain: str | None, family: str | None) -> tuple[dict, dict, dict]:
        records = [
            {
                "id": "pmid:11", "title": "Depression intervention trial",
                "abstract": "Depression symptoms improved.",
                "first_publication_date": "2022-01-01",
                "domain_ids": ["mental-health"],
                **({"study_family_id": family} if family else {}),
            },
            {
                "id": "pmid:12", "title": "Depression companion report",
                "abstract": "Depression outcomes in community care.",
                "first_publication_date": "2022-02-01",
                **({"domain_ids": [second_domain]} if second_domain else {}),
                **({"study_family_id": family} if family else {}),
            },
            {
                "id": "pmid:13", "title": "Earlier depression review",
                "abstract": "A systematic review of depression care.",
                "first_publication_date": "2021-01-01",
                "domain_ids": ["mental-health"],
                "source_family_id": "review-family-a",
            },
        ]
        spec = {
            "landscape_id": "builder-construct-landscape",
            "run_context": "historical_rediscovery",
            "domain_ids": ["mental-health", "public-health"],
            "cutoff_date": "2023-06-03",
            "query_class": "broad_non_target_domain_query",
            "query_text": "depression care",
            "minimum_records": 3,
            "concepts": [
                {
                    "node_id": "concept-depression", "node_type": "concept",
                    "label": "depression", "patterns": ["depression"],
                }
            ],
            "selection_policy": copy.deepcopy(self.policy),
        }
        landscape = build_broad_temporal_landscape(
            records, spec, ["sealed target"], created_at_utc="2026-08-22T00:00:00Z",
        )
        publications = {
            node["source_ids"][0]: node
            for node in landscape["nodes"] if node["node_type"] == "publication"
        }
        primary_ids = [publications["pmid:11"]["node_id"], publications["pmid:12"]["node_id"]]
        review_id = publications["pmid:13"]["node_id"]
        proposal = {
            "proposal_id": "builder-construct-proposal",
            "generation_method": "model_proposal",
            "question_framework": {
                "population": ["adults with depression"],
                "intervention_or_exposure": ["active treatment"],
                "comparator": ["usual care"],
                "outcome": ["depressive symptoms"],
                "study_design": ["randomised trials"],
                "synthesis_route": "pairwise meta-analysis",
            },
            "concept_node_ids": ["concept-depression"],
            "evidence_node_ids": primary_ids,
            "evidence_interpretations": [
                {
                    "node_id": primary_ids[0], "role": "uncertainty",
                    "interpretation": "Comparative uncertainty remains.",
                }
            ],
            "disconfirmation_queries": [
                {"check_type": "existing_review_overlap", "query": "depression review"}
            ],
            "status": "requires_independent_signal_audit",
        }
        receipt = {
            "schema_version": "1.0", "status": "completed",
            "engine": "ncbi_pubmed_eutils", "cutoff_date": "2023-06-03",
            "provider_calls": 0, "query_sha256s": ["b" * 64],
            "primary_study_node_ids": primary_ids,
            "proposal_evidence_recall": 1.0,
            "review_matches": [{"node_id": review_id, "framework_overlap": 0.25}],
            "protocol_matches": [], "protocol_result_count": 0,
            "newest_primary_date": "2022-02-01",
            "newest_review_date": "2021-01-01",
        }
        return landscape, proposal, receipt

    def test_removing_decision_anchor_makes_decision_relevance_unavailable(self) -> None:
        landscape, proposal, receipt = self._handcrafted_case()
        anchored = self._audit(landscape, proposal, receipt)
        self.assertEqual(anchored["signals"]["decision_relevance"]["value"], 0.25)
        self.assertEqual(
            anchored["construct_validity"]["decision_relevance"]["anchor_node_ids"],
            ["guideline-1"],
        )

        unanchored_landscape = copy.deepcopy(landscape)
        unanchored_landscape["nodes"] = [
            node for node in unanchored_landscape["nodes"]
            if node["node_id"] != "guideline-1"
        ]
        unanchored_proposal = copy.deepcopy(proposal)
        unanchored_proposal["evidence_node_ids"].remove("guideline-1")
        unanchored_proposal["evidence_interpretations"] = [
            item for item in unanchored_proposal["evidence_interpretations"]
            if item["node_id"] != "guideline-1"
        ]
        unanchored = self._audit(unanchored_landscape, unanchored_proposal, receipt)
        signal = unanchored["signals"]["decision_relevance"]
        self.assertIsNone(signal["value"])
        self.assertEqual(signal["calibration_status"], "unavailable")
        self.assertEqual(unanchored["operationalization"]["status"], "incomplete")
        self.assertIn(
            "decision_relevance_anchor",
            unanchored["operationalization"]["missing_fields"],
        )
        self.assertEqual(
            unanchored["legacy_diagnostics"]["framework_completeness_fraction"], 1.0,
        )

    def test_postcutoff_decision_anchor_fails_closed(self) -> None:
        landscape, proposal, receipt = self._handcrafted_case()
        next(node for node in landscape["nodes"] if node["node_id"] == "guideline-1")[
            "observed_at"
        ] = "2024-01-01"
        with self.assertRaisesRegex(DeterministicTopicAuditError, "decision anchor.*cutoff"):
            self._audit(landscape, proposal, receipt)

    def test_removing_node_domain_changes_cross_domain_intermediate_state(self) -> None:
        broad_landscape, broad_proposal, broad_receipt = self._built_case(
            second_domain="public-health", family="trial-a",
        )
        narrow_landscape, narrow_proposal, narrow_receipt = self._built_case(
            second_domain=None, family="trial-a",
        )
        broad = self._audit(broad_landscape, broad_proposal, broad_receipt)
        narrow = self._audit(narrow_landscape, narrow_proposal, narrow_receipt)
        self.assertEqual(broad["signals"]["cross_domain_value"]["value"], 0.5)
        self.assertNotEqual(
            broad["signals"]["cross_domain_value"],
            narrow["signals"]["cross_domain_value"],
        )
        self.assertIsNone(narrow["signals"]["cross_domain_value"]["value"])
        self.assertEqual(
            narrow["signals"]["cross_domain_value"]["calibration_status"],
            "unavailable",
        )
        self.assertEqual(narrow["operationalization"]["status"], "incomplete")
        self.assertNotEqual(
            broad["construct_validity"]["cross_domain"],
            narrow["construct_validity"]["cross_domain"],
        )

    def test_removing_family_cluster_changes_source_diversity_intermediate_state(self) -> None:
        clustered_landscape, clustered_proposal, clustered_receipt = self._built_case(
            second_domain="public-health", family="trial-a",
        )
        bare_landscape, bare_proposal, bare_receipt = self._built_case(
            second_domain="public-health", family=None,
        )
        clustered = self._audit(clustered_landscape, clustered_proposal, clustered_receipt)
        bare = self._audit(bare_landscape, bare_proposal, bare_receipt)
        self.assertEqual(clustered["source_family_ids"], ["study:trial-a"])
        self.assertEqual(clustered["feasibility_evidence"]["independent_source_families"], 1)
        self.assertEqual(bare["source_family_ids"], [])
        self.assertEqual(
            bare["construct_validity"]["source_diversity"]["status"], "unavailable",
        )
        self.assertEqual(bare["operationalization"]["status"], "incomplete")
        self.assertGreater(
            bare["legacy_diagnostics"]["record_identifier_count"],
            bare["feasibility_evidence"]["independent_source_families"],
        )

    def test_partial_family_assignment_is_unavailable_not_undercounted(self) -> None:
        landscape, proposal, receipt = self._built_case(
            second_domain="public-health", family="trial-a",
        )
        second_primary = receipt["primary_study_node_ids"][1]
        next(
            node for node in landscape["nodes"] if node["node_id"] == second_primary
        )["source_family_ids"] = []

        audit = self._audit(landscape, proposal, receipt)

        self.assertEqual(audit["source_family_ids"], [])
        self.assertEqual(
            audit["construct_validity"]["source_diversity"]["status"],
            "unavailable",
        )
        self.assertEqual(audit["operationalization"]["status"], "incomplete")
        self.assertIn(
            second_primary,
            audit["construct_validity"]["source_diversity"]["unassigned_node_ids"],
        )


if __name__ == "__main__":
    unittest.main()
