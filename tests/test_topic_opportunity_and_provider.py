from __future__ import annotations

import json
import sys
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "metawingman/scripts"
sys.path.insert(0, str(SCRIPTS))

from metawingman_core.deepseek_provider import (  # noqa: E402
    DeepSeekProvider,
    ProviderRequestError,
    ProviderResult,
)
from metawingman_core.topic_opportunity import (  # noqa: E402
    TopicOpportunityError,
    select_topic_portfolio,
)
from metawingman_core.topic_rediscovery import (  # noqa: E402
    TopicRediscoveryError,
    evaluate_topic_rediscovery,
)
from metawingman_core.topic_proposer import (  # noqa: E402
    TopicProposalError,
    propose_topics,
)


TIMESTAMP = "2026-08-13T00:00:00Z"


def landscape() -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "landscape_id": "landscape-001",
        "run_context": "historical_rediscovery",
        "domain_ids": ["cardiology", "neurology"],
        "corpus_boundary": {
            "cutoff_date": "2020-12-31",
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
                "node_id": "study-1",
                "node_type": "primary_study",
                "label": "Study one",
                "domain_ids": ["cardiology"],
                "observed_at": "2019-01-01",
                "source_ids": ["pubmed"],
                "provenance_status": "verified",
            },
            {
                "node_id": "study-2",
                "node_type": "primary_study",
                "label": "Study two",
                "domain_ids": ["neurology"],
                "observed_at": "2020-01-01",
                "source_ids": ["registry"],
                "provenance_status": "verified",
            },
            {
                "node_id": "concept-a",
                "node_type": "concept",
                "label": "Shared inflammation",
                "domain_ids": ["cardiology", "neurology"],
                "observed_at": "2020-06-01",
                "source_ids": ["pubmed", "registry"],
                "provenance_status": "machine_extracted",
            },
        ],
        "edges": [
            {
                "edge_id": "edge-1",
                "source_node_id": "study-1",
                "target_node_id": "concept-a",
                "relation": "mentions",
                "observed_at": "2019-01-01",
                "source_ids": ["pubmed"],
            }
        ],
        "selection_policy": {
            "policy_version": "topic-policy-1",
            "weights": {
                "decision_relevance": 0.2,
                "unresolved_uncertainty": 0.15,
                "feasibility": 0.15,
                "evidence_maturity": 0.1,
                "nonduplication": 0.15,
                "update_need": 0.05,
                "equity_priority": 0.1,
                "cross_domain_value": 0.1,
            },
            "minimum_primary_studies": 2,
            "minimum_source_families": 2,
            "minimum_known_item_recall": 0.9,
            "maximum_review_overlap": 0.5,
            "maximum_contamination_risk": 0.1,
            "maximum_ambiguity_risk": 0.2,
            "minimum_utility_score": 0.5,
            "maximum_portfolio_size": 2,
            "diversity_penalty": 0.3,
            "allow_update_topics": True,
        },
        "created_at_utc": TIMESTAMP,
    }


def _signal(value: float, node: str = "study-1") -> dict[str, object]:
    return {
        "value": value,
        "calibration_status": "heuristic",
        "basis": "Fixture evidence signal.",
        "evidence_node_ids": [node],
    }


def candidate(candidate_id: str, intervention: str, value: float = 0.9) -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "candidate_id": candidate_id,
        "landscape_id": "landscape-001",
        "generation_method": "cross_domain_bridge",
        "question_framework": {
            "population": ["adults"],
            "intervention_or_exposure": [intervention],
            "comparator": ["usual care"],
            "outcome": ["mortality"],
            "study_design": ["randomized trial"],
            "synthesis_route": "pairwise",
        },
        "concept_node_ids": ["concept-a"],
        "evidence_node_ids": ["study-1", "study-2"],
        "source_family_ids": ["pubmed", "registry"],
        "signals": {
            "decision_relevance": _signal(value),
            "unresolved_uncertainty": _signal(value),
            "feasibility": _signal(value),
            "evidence_maturity": _signal(value),
            "nonduplication": _signal(value),
            "update_need": _signal(0.0),
            "equity_priority": _signal(value),
            "cross_domain_value": _signal(value, "concept-a"),
            "contamination_risk": _signal(0.01),
            "ambiguity_risk": _signal(0.02),
        },
        "feasibility_evidence": {
            "primary_study_count": 5,
            "independent_source_families": 2,
            "known_item_recall": 0.95,
            "full_text_access_fraction": 0.9,
            "extractable_result_fraction": 0.8,
        },
        "overlap_evidence": {
            "maximum_existing_review_overlap": 0.1,
            "active_protocol_overlap": False,
            "update_justification": "",
        },
        "leakage_checks": {
            "audit_status": "passed",
            "target_title_seen": False,
            "target_authors_seen": False,
            "target_identifier_seen": False,
            "target_descendant_seen": False,
            "post_cutoff_source_seen": False,
        },
        "operationalization": {
            "status": "complete",
            "missing_fields": [],
            "rationale": "All review-question fields are explicit.",
        },
        "created_at_utc": TIMESTAMP,
    }


class TopicOpportunityTests(unittest.TestCase):
    def test_selects_high_value_diverse_topics_deterministically(self) -> None:
        candidates = [
            candidate("topic-a", "drug alpha"),
            candidate("topic-a-copy", "drug alpha", 0.88),
            candidate("topic-b", "behavioral intervention", 0.86),
        ]
        first = select_topic_portfolio(landscape(), candidates, created_at_utc=TIMESTAMP)
        second = select_topic_portfolio(landscape(), list(reversed(candidates)), created_at_utc=TIMESTAMP)
        self.assertEqual(first, second)
        self.assertEqual(first["status"], "portfolio_selected")
        self.assertEqual(first["selected_candidate_ids"], ["topic-a", "topic-b"])
        self.assertEqual(first["oversight_boundary"]["mode"], "post_run_reference_only")

    def test_blocks_unjustified_duplicate_review(self) -> None:
        duplicate = candidate("duplicate", "drug alpha")
        duplicate["overlap_evidence"]["maximum_existing_review_overlap"] = 0.9
        decision = select_topic_portfolio(landscape(), [duplicate], created_at_utc=TIMESTAMP)
        self.assertEqual(decision["status"], "abstain")
        self.assertIn(
            "existing_review_overlap_above_ceiling",
            decision["ranked_candidates"][0]["reason_codes"],
        )

    def test_historical_identity_leakage_is_a_hard_failure(self) -> None:
        leaked = candidate("leaked", "drug alpha")
        leaked["leakage_checks"]["target_title_seen"] = True
        leaked["leakage_checks"]["audit_status"] = "failed"
        with self.assertRaises(TopicOpportunityError):
            select_topic_portfolio(landscape(), [leaked], created_at_utc=TIMESTAMP)

    def test_post_cutoff_node_is_rejected(self) -> None:
        state = landscape()
        state["nodes"][0]["observed_at"] = "2021-01-01"
        with self.assertRaises(TopicOpportunityError):
            select_topic_portfolio(state, [candidate("topic", "drug alpha")])


def rediscovery_case() -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "case_id": "rediscovery-001",
        "review_family_id": "family-001",
        "split": "test",
        "cutoff_date": "2020-12-31",
        "run_lock": {
            "locked": True,
            "locked_at_utc": TIMESTAMP,
            "artifact_sha256": "a" * 64,
        },
        "exposure_audit": {
            "status": "passed",
            "target_identity_exposed": False,
            "target_descendants_exposed": False,
            "post_cutoff_evidence_exposed": False,
        },
        "model_memory_boundary": {
            "model_version_frozen": True,
            "training_cutoff_status": "unknown",
            "memorization_probe": "inconclusive",
            "contamination_risk": "unquantifiable",
            "prospective_run_registered_before_reference": False,
        },
        "ranked_predictions": [
            {
                "rank": 1,
                "candidate_id": "wrong",
                "question_framework": {
                    "population": ["children"],
                    "intervention_or_exposure": ["drug beta"],
                    "comparator": ["placebo"],
                    "outcome": ["pain"],
                    "study_design": ["cohort"],
                    "synthesis_route": "pairwise",
                },
            },
            {
                "rank": 2,
                "candidate_id": "match",
                "question_framework": {
                    "population": ["Adults"],
                    "intervention_or_exposure": ["Drug alpha"],
                    "comparator": ["Usual care"],
                    "outcome": ["Mortality"],
                    "study_design": ["Randomized trial"],
                    "synthesis_route": "pairwise",
                },
            },
        ],
        "sealed_reference": {
            "reference_status": "published_expert_reference",
            "published_identity_sha256": "b" * 64,
            "venue_stratum": "top_general",
            "question_framework": {
                "population": ["adults"],
                "intervention_or_exposure": ["drug alpha"],
                "comparator": ["usual care"],
                "outcome": ["mortality"],
                "study_design": ["randomized trial"],
                "synthesis_route": "pairwise",
            },
        },
        "evaluation_policy": {
            "top_k": [1, 3, 10],
            "minimum_framework_similarity": 0.8,
            "field_weights": {
                "population": 0.2,
                "intervention_or_exposure": 0.2,
                "comparator": 0.15,
                "outcome": 0.2,
                "study_design": 0.15,
                "synthesis_route": 0.1,
            },
        },
    }


class TopicRediscoveryTests(unittest.TestCase):
    def test_reports_top_k_framework_concordance_not_human_superiority(self) -> None:
        report = evaluate_topic_rediscovery(rediscovery_case())
        self.assertFalse(report["top_k_hits"]["1"])
        self.assertTrue(report["top_k_hits"]["3"])
        self.assertEqual(report["first_matching_rank"], 2)
        self.assertTrue(report["exact_framework_hit"])
        self.assertEqual(report["independence_claim_status"], "not_supported")
        self.assertIn("published_expert_reference_is_not_an_oracle", report["reason_codes"])
        self.assertIn("model_memory_contamination_not_excluded", report["reason_codes"])

    def test_requires_contiguous_ranks(self) -> None:
        case = rediscovery_case()
        case["ranked_predictions"][1]["rank"] = 3
        with self.assertRaises(TopicRediscoveryError):
            evaluate_topic_rediscovery(case)


class DeepSeekProviderTests(unittest.TestCase):
    def test_chat_builds_bounded_request_and_redacts_content_from_audit(self) -> None:
        provider = DeepSeekProvider(api_key="unit-test-secret", credential_source="test")
        response = {
            "model": "deepseek-v4-flash",
            "system_fingerprint": "fp-test",
            "choices": [
                {"finish_reason": "stop", "message": {"content": '{"status":"ok"}'}}
            ],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 4,
                "total_tokens": 14,
                "completion_tokens_details": {"reasoning_tokens": 0},
            },
        }
        with patch.object(provider, "_request", return_value=response) as request:
            result = provider.chat(
                [{"role": "user", "content": "Return JSON."}],
                thinking=False,
                max_tokens=32,
                json_output=True,
            )
        payload = request.call_args.args[2]
        self.assertEqual(payload["model"], "deepseek-v4-flash")
        self.assertEqual(payload["thinking"]["type"], "disabled")
        self.assertEqual(payload["response_format"], {"type": "json_object"})
        self.assertNotIn("content", result.audit_record())
        self.assertEqual(result.total_tokens, 14)

    def test_rejects_non_https_base_url(self) -> None:
        with self.assertRaises(ProviderRequestError):
            DeepSeekProvider(api_key="unit-test-secret", base_url="http://example.test")


class TopicProposerTests(unittest.TestCase):
    @staticmethod
    def _provider_result(content: dict[str, object]) -> ProviderResult:
        text = json.dumps(content)
        return ProviderResult(
            provider="deepseek",
            model="deepseek-v4-flash",
            finish_reason="stop",
            content=text,
            content_sha256="c" * 64,
            prompt_tokens=100,
            completion_tokens=80,
            total_tokens=180,
            reasoning_tokens=0,
            system_fingerprint="fp-test",
            credential_source="test",
        )

    @staticmethod
    def _proposal() -> dict[str, object]:
        return {
            "generation_method": "cross_domain_bridge",
            "question_framework": {
                "population": ["adults"],
                "intervention_or_exposure": ["shared inflammation"],
                "comparator": ["lower inflammatory activity"],
                "outcome": ["mortality"],
                "study_design": ["comparative primary studies"],
                "synthesis_route": "pairwise",
            },
            "concept_node_ids": ["concept-a"],
            "evidence_node_ids": ["study-1", "study-2"],
            "evidence_interpretations": [
                {
                    "node_id": "concept-a",
                    "role": "cross_domain",
                    "interpretation": "The supplied concept links both represented domains.",
                }
            ],
            "disconfirmation_queries": [
                {
                    "check_type": "existing_review_overlap",
                    "query": "Search reviews and protocols for the complete framework.",
                }
            ],
        }

    def test_generates_evidence_bound_proposals_without_signal_scores(self) -> None:
        provider = unittest.mock.Mock(spec=DeepSeekProvider)
        provider.chat.return_value = self._provider_result(
            {"proposals": [self._proposal()]}
        )
        batch = propose_topics(
            landscape(),
            provider,
            maximum_proposals=2,
            created_at_utc=TIMESTAMP,
        )
        self.assertEqual(batch["status"], "proposals_generated")
        self.assertEqual(len(batch["proposals"]), 1)
        self.assertNotIn("signals", batch["proposals"][0])
        self.assertEqual(
            batch["proposals"][0]["status"],
            "requires_independent_signal_audit",
        )
        self.assertEqual(
            batch["generation_policy"]["model_memory_boundary"],
            "unquantifiable",
        )
        self.assertEqual(batch["model_provenance"]["call_count"], 1)
        self.assertFalse(batch["model_provenance"]["repair_attempted"])
        sent = provider.chat.call_args.args[0]
        self.assertIn("numeric_scores_prohibited", sent[1]["content"])

    def test_abstains_when_unknown_evidence_node_survives_repair(self) -> None:
        proposal = self._proposal()
        proposal["evidence_node_ids"] = ["study-1", "unknown-study"]
        provider = unittest.mock.Mock(spec=DeepSeekProvider)
        provider.chat.return_value = self._provider_result({"proposals": [proposal]})
        batch = propose_topics(landscape(), provider, created_at_utc=TIMESTAMP)
        self.assertEqual(batch["status"], "abstain")
        self.assertEqual(batch["model_provenance"]["call_count"], 2)
        self.assertIn("provider_output_failed_schema_after_repair", batch["reason_codes"])
        self.assertIn("provider_repair_failed_unknown_node", batch["reason_codes"])

    def test_repairs_model_output_with_numeric_self_score(self) -> None:
        proposal = self._proposal()
        proposal["opportunity_score"] = 0.99
        provider = unittest.mock.Mock(spec=DeepSeekProvider)
        provider.chat.side_effect = [
            self._provider_result({"proposals": [proposal]}),
            self._provider_result({"proposals": [self._proposal()]}),
        ]
        batch = propose_topics(landscape(), provider, created_at_utc=TIMESTAMP)
        self.assertEqual(batch["status"], "proposals_generated")
        self.assertEqual(batch["model_provenance"]["call_count"], 2)
        self.assertTrue(batch["model_provenance"]["repair_attempted"])
        self.assertNotIn("opportunity_score", batch["proposals"][0])

    def test_refuses_implicit_large_hosted_transfer(self) -> None:
        provider = unittest.mock.Mock(spec=DeepSeekProvider)
        with self.assertRaisesRegex(TopicProposalError, "transfer limit"):
            propose_topics(
                landscape(),
                provider,
                maximum_prompt_characters=20,
                created_at_utc=TIMESTAMP,
            )
        provider.chat.assert_not_called()

    def test_development_batch_does_not_claim_prospective_independence(self) -> None:
        state = landscape()
        state["run_context"] = "development"
        state["corpus_boundary"].update({
            "target_identity_status": "not_applicable",
            "target_descendants_status": "not_applicable",
            "post_cutoff_evidence_status": "not_applicable",
            "leakage_audit": "not_applicable",
            "excluded_identity_fields": [],
        })
        provider = unittest.mock.Mock(spec=DeepSeekProvider)
        provider.chat.return_value = self._provider_result(
            {"proposals": [self._proposal()]}
        )
        batch = propose_topics(state, provider, created_at_utc=TIMESTAMP)
        self.assertEqual(
            batch["generation_policy"]["model_memory_boundary"],
            "not_a_discovery_claim",
        )


if __name__ == "__main__":
    unittest.main()
