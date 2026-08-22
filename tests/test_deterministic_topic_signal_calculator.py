from __future__ import annotations

import unittest

from metawingman.scripts.metawingman_core.deterministic_topic_signal_audit import (
    DeterministicTopicAuditError,
    build_deterministic_topic_signal_audit,
)


class DeterministicTopicSignalCalculatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.landscape = {
            "schema_version": "1.0", "landscape_id": "landscape-1",
            "run_context": "historical_rediscovery", "domain_ids": ["mental-health"],
            "corpus_boundary": {
                "cutoff_date": "2023-06-03", "target_identity_status": "sealed",
                "target_descendants_status": "sealed", "post_cutoff_evidence_status": "sealed",
                "leakage_audit": "passed",
                "excluded_identity_fields": ["title", "authors", "doi", "pmid", "journal", "abstract", "keywords", "citations", "descendants"],
            },
            "nodes": [
                {"node_id": "pub-1", "node_type": "publication", "label": "Exercise trial for depression", "domain_ids": ["mental-health"], "domain_assignment_status": "explicit_record", "observed_at": "2022-01-01", "source_ids": ["pmid:1"], "source_family_ids": ["study:trial-a"], "provenance_status": "verified"},
                {"node_id": "pub-2", "node_type": "publication", "label": "Exercise review for depression", "domain_ids": ["mental-health"], "domain_assignment_status": "explicit_record", "observed_at": "2021-01-01", "source_ids": ["pmid:2"], "source_family_ids": ["source:review-a"], "provenance_status": "verified"},
                {"node_id": "guideline-1", "node_type": "guideline", "label": "Depression treatment guideline", "domain_ids": ["mental-health"], "domain_assignment_status": "explicit_record", "observed_at": "2020-01-01", "source_ids": ["guideline:1"], "source_family_ids": ["source:guideline-a"], "provenance_status": "verified"},
                {"node_id": "concept-exercise", "node_type": "intervention_or_exposure", "label": "exercise", "domain_ids": ["mental-health"], "domain_assignment_status": "derived_from_explicit_records", "observed_at": "2021-01-01", "source_ids": ["pmid:1", "pmid:2"], "source_family_ids": ["study:trial-a", "source:review-a"], "provenance_status": "machine_extracted"},
            ],
            "edges": [],
            "selection_policy": {
                "policy_version": "v1", "weights": {"decision_relevance": .2, "unresolved_uncertainty": .15, "feasibility": .15, "evidence_maturity": .1, "nonduplication": .15, "update_need": .1, "equity_priority": .1, "cross_domain_value": .05},
                "minimum_primary_studies": 1, "minimum_source_families": 1, "minimum_known_item_recall": .8,
                "maximum_review_overlap": .6, "maximum_contamination_risk": .2, "maximum_ambiguity_risk": .3,
                "minimum_utility_score": .5, "maximum_portfolio_size": 3, "diversity_penalty": .1, "allow_update_topics": True,
            },
            "created_at_utc": "2026-08-22T00:00:00Z",
        }
        self.proposal = {
            "proposal_id": "proposal-1", "generation_method": "model_proposal",
            "question_framework": {
                "population": ["adults with depression"], "intervention_or_exposure": ["exercise"],
                "comparator": ["usual care"], "outcome": ["depressive symptoms"],
                "study_design": ["randomised trials"], "synthesis_route": "network meta-analysis",
            },
            "concept_node_ids": ["concept-exercise"], "evidence_node_ids": ["pub-1", "pub-2", "guideline-1"],
            "evidence_interpretations": [
                {"node_id": "pub-1", "role": "uncertainty", "interpretation": "Comparative uncertainty remains."},
                {"node_id": "guideline-1", "role": "decision_need", "interpretation": "Guideline identifies a treatment choice."},
            ],
            "disconfirmation_queries": [{"check_type": "existing_review_overlap", "query": "exercise depression systematic review"}],
            "status": "requires_independent_signal_audit",
        }
        self.receipt = {
            "schema_version": "1.0", "status": "completed", "engine": "ncbi_pubmed_eutils",
            "cutoff_date": "2023-06-03", "provider_calls": 0,
            "query_sha256s": ["a" * 64], "primary_study_node_ids": ["pub-1"],
            "primary_study_family_ids": {"pub-1": "trial-a"},
            "proposal_evidence_recall": 1.0,
            "review_matches": [{"node_id": "pub-2", "framework_overlap": 0.5}],
            "protocol_matches": [], "protocol_result_count": 1,
            "newest_primary_date": "2022-01-01", "newest_review_date": "2021-01-01",
        }

    def test_builds_replayable_heuristic_audit_without_model_self_scores(self) -> None:
        audit = build_deterministic_topic_signal_audit(
            self.proposal, self.landscape, self.receipt,
            proposal_provider_id="deepseek-v4-flash", auditor_id="ncbi-audit-v1",
        )
        self.assertEqual(audit["auditor_kind"], "deterministic_external_search")
        self.assertEqual(audit["feasibility_evidence"]["primary_study_count"], 1)
        self.assertEqual(audit["feasibility_evidence"]["known_item_recall"], 1.0)
        self.assertEqual(audit["operationalization"]["status"], "complete")
        self.assertEqual(audit["overlap_evidence"]["maximum_existing_review_overlap"], 0.5)
        self.assertEqual(audit["signals"]["nonduplication"]["value"], 0.5)
        self.assertEqual(audit["signals"]["update_need"]["value"], 1.0)
        self.assertEqual(audit["signals"]["decision_relevance"]["value"], 0.25)
        self.assertTrue(audit["overlap_evidence"]["active_protocol_overlap"])
        self.assertTrue(all(item["calibration_status"] == "heuristic" for item in audit["signals"].values()))

    def test_rejects_provider_calls_or_unknown_external_nodes(self) -> None:
        receipt = dict(self.receipt, provider_calls=1)
        with self.assertRaisesRegex(DeterministicTopicAuditError, "zero provider calls"):
            build_deterministic_topic_signal_audit(self.proposal, self.landscape, receipt, proposal_provider_id="deepseek-v4-flash", auditor_id="ncbi-audit-v1")
        receipt = dict(self.receipt, primary_study_node_ids=["unknown"])
        with self.assertRaisesRegex(DeterministicTopicAuditError, "unknown nodes"):
            build_deterministic_topic_signal_audit(self.proposal, self.landscape, receipt, proposal_provider_id="deepseek-v4-flash", auditor_id="ncbi-audit-v1")


if __name__ == "__main__":
    unittest.main()
