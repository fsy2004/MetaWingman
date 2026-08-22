from __future__ import annotations

import copy
import unittest

from metawingman.scripts.metawingman_core.topic_signal_audit import (
    TopicSignalAuditError,
    landscape_node_ids,
    promote_proposal_after_independent_audit,
)


SIGNALS = [
    "decision_relevance", "unresolved_uncertainty", "feasibility", "evidence_maturity",
    "nonduplication", "update_need", "equity_priority", "cross_domain_value",
    "contamination_risk", "ambiguity_risk",
]


class TopicSignalAuditTests(unittest.TestCase):
    def setUp(self) -> None:
        self.proposal = {
            "proposal_id": "proposal-1", "generation_method": "model_proposal",
            "question_framework": {"population": ["adults"], "intervention_or_exposure": ["support"], "comparator": ["usual care"], "outcome": ["wellbeing"], "study_design": ["controlled studies"], "synthesis_route": "pairwise meta-analysis"},
            "concept_node_ids": ["concept-1"], "evidence_node_ids": ["study-1"],
            "status": "requires_independent_signal_audit"
        }
        self.audit = {
            "proposal_id": "proposal-1", "proposal_provider_id": "deepseek-v4-flash",
            "auditor_kind": "deterministic_external_search", "auditor_id": "topic-audit-v1",
            "signals": {name: {"value": 0.5, "calibration_status": "heuristic", "basis": "frozen deterministic calculation", "evidence_node_ids": ["study-1"], "calculation_id": f"calc-{name}"} for name in SIGNALS},
            "source_family_ids": ["pubmed", "registry"],
            "feasibility_evidence": {"primary_study_count": 12, "independent_source_families": 2, "known_item_recall": 0.9, "full_text_access_fraction": 0.7, "extractable_result_fraction": 0.6},
            "overlap_evidence": {"maximum_existing_review_overlap": 0.2, "active_protocol_overlap": False, "update_justification": ""},
            "leakage_checks": {"audit_status": "passed", "target_title_seen": False, "target_authors_seen": False, "target_identifier_seen": False, "target_descendant_seen": False, "post_cutoff_source_seen": False},
            "operationalization": {"status": "complete", "missing_fields": [], "rationale": "all framework fields explicit"}
        }
        self.nodes = {"concept-1", "study-1"}

    def test_independent_audit_promotes_schema_valid_candidate(self) -> None:
        candidate = promote_proposal_after_independent_audit(self.proposal, self.audit, proposal_provider_id="deepseek-v4-flash", landscape_id="landscape-1", landscape_node_ids=self.nodes, created_at_utc="2026-08-22T03:30:00Z")
        self.assertEqual(candidate["candidate_id"], "candidate-proposal-1")
        self.assertNotIn("calculation_id", candidate["signals"]["feasibility"])

    def test_proposer_cannot_score_its_own_topic(self) -> None:
        audit = copy.deepcopy(self.audit)
        audit["auditor_kind"] = "provider"
        audit["auditor_id"] = "deepseek-v4-flash"
        with self.assertRaisesRegex(TopicSignalAuditError, "self-score"):
            promote_proposal_after_independent_audit(self.proposal, audit, proposal_provider_id="deepseek-v4-flash", landscape_id="landscape-1", landscape_node_ids=self.nodes, created_at_utc="2026-08-22T03:30:00Z")

    def test_audit_cannot_spoof_the_proposal_provider_identity(self) -> None:
        audit = copy.deepcopy(self.audit)
        audit["proposal_provider_id"] = "another-provider"
        with self.assertRaisesRegex(TopicSignalAuditError, "provider binding"):
            promote_proposal_after_independent_audit(
                self.proposal, audit, proposal_provider_id="deepseek-v4-flash", landscape_id="landscape-1",
                landscape_node_ids=self.nodes, created_at_utc="2026-08-22T03:30:00Z",
            )

    def test_every_signal_requires_a_replayable_calculation_and_known_evidence(self) -> None:
        audit = copy.deepcopy(self.audit)
        audit["signals"]["feasibility"].pop("calculation_id")
        with self.assertRaisesRegex(TopicSignalAuditError, "calculation"):
            promote_proposal_after_independent_audit(self.proposal, audit, proposal_provider_id="deepseek-v4-flash", landscape_id="landscape-1", landscape_node_ids=self.nodes, created_at_utc="2026-08-22T03:30:00Z")
        audit = copy.deepcopy(self.audit)
        audit["signals"]["feasibility"]["evidence_node_ids"] = ["unknown"]
        with self.assertRaisesRegex(TopicSignalAuditError, "unknown evidence"):
            promote_proposal_after_independent_audit(self.proposal, audit, proposal_provider_id="deepseek-v4-flash", landscape_id="landscape-1", landscape_node_ids=self.nodes, created_at_utc="2026-08-22T03:30:00Z")

    def test_landscape_node_ids_uses_the_canonical_nodes_array(self) -> None:
        self.assertEqual(
            landscape_node_ids({"nodes": [{"node_id": "concept-1"}, {"node_id": "study-1"}]}),
            {"concept-1", "study-1"},
        )


if __name__ == "__main__":
    unittest.main()
