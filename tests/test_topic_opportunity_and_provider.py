from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
import subprocess
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
from metawingman_core.openai_compatible_provider import (  # noqa: E402
    OpenAICompatibleProvider,
)
from metawingman_core.provider_factory import build_provider  # noqa: E402
from metawingman_core.schema_guard import validate_document  # noqa: E402
from metawingman_core.structured_candidate_runner import (  # noqa: E402
    StructuredCandidateError,
    run_structured_candidate,
)
from metawingman_core.structured_batch import run_structured_batch  # noqa: E402
from metawingman_core.topic_opportunity import (  # noqa: E402
    TopicOpportunityError,
    select_topic_portfolio,
)
from metawingman_core.topic_rediscovery import (  # noqa: E402
    TopicRediscoveryError,
    _set_similarity,
    evaluate_topic_rediscovery,
)
from metawingman_core.topic_opportunity_controls import (  # noqa: E402
    evaluate_topic_control_arms,
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

    def test_direct_controls_expose_overlap_and_diversity_mechanisms(self) -> None:
        target = candidate("target", "drug alpha", 0.84)
        saturated = candidate("saturated", "drug beta", 0.99)
        saturated["feasibility_evidence"]["primary_study_count"] = 50
        saturated["overlap_evidence"]["maximum_existing_review_overlap"] = 0.95
        duplicate = candidate("target-copy", "drug alpha", 0.80)
        result = evaluate_topic_control_arms(
            landscape(),
            [saturated, target, duplicate],
            target_candidate_ids={"target"},
            false_opportunity_candidate_ids={"saturated"},
            created_at_utc=TIMESTAMP,
        )
        self.assertEqual(result["arms"]["full-decision-aware"]["selected_candidate_ids"], ["target"])
        self.assertEqual(result["arms"]["bibliometric-count"]["selected_candidate_ids"][0], "saturated")
        self.assertIn("saturated", result["arms"]["without-overlap-opposition"]["selected_candidate_ids"])
        self.assertEqual(result["arms"]["full-decision-aware"]["false_opportunity_rate"], 0.0)
        self.assertGreater(result["arms"]["without-overlap-opposition"]["false_opportunity_rate"], 0.0)
        self.assertEqual(result["provider_calls"], 0)

    def test_direct_control_cli_writes_a_replayable_report(self) -> None:
        target = candidate("target", "drug alpha", 0.84)
        saturated = candidate("saturated", "drug beta", 0.99)
        saturated["overlap_evidence"]["maximum_existing_review_overlap"] = 0.95
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            landscape_path = root / "landscape.json"
            candidates_path = root / "candidates.json"
            labels_path = root / "labels.json"
            output_path = root / "report.json"
            landscape_path.write_text(json.dumps(landscape()), encoding="utf-8")
            candidates_path.write_text(json.dumps([saturated, target]), encoding="utf-8")
            labels_path.write_text(json.dumps({
                "target_candidate_ids": ["target"],
                "false_opportunity_candidate_ids": ["saturated"],
            }), encoding="utf-8")
            script = ROOT / "metawingman/scripts/evaluate_topic_opportunity_controls.py"
            completed = subprocess.run([
                sys.executable, str(script), str(landscape_path), str(candidates_path),
                str(labels_path), "--out", str(output_path),
            ], capture_output=True, text=True)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            report = json.loads(output_path.read_text(encoding="utf-8"))
        self.assertEqual(report["provider_calls"], 0)
        self.assertIn("full-decision-aware", report["arms"])


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
    def test_field_similarity_is_order_invariant_within_framework_terms(self) -> None:
        self.assertEqual(
            _set_similarity(["adults with depression"], ["depression in adults"]),
            1.0,
        )

    def test_prefrozen_accepted_terms_handle_hierarchy_without_title_matching(self) -> None:
        case = rediscovery_case()
        case["ranked_predictions"][1]["question_framework"]["intervention_or_exposure"] = ["portable digital devices"]
        case["sealed_reference"]["question_framework"]["intervention_or_exposure"] = ["screen media access or use"]
        case["sealed_reference"]["accepted_term_sets"] = {
            "population": ["adults"],
            "intervention_or_exposure": ["portable digital devices"],
            "comparator": ["usual care"],
            "outcome": ["mortality"],
            "study_design": ["randomized trial"],
            "synthesis_route": ["pairwise meta-analysis"],
        }
        report = evaluate_topic_rediscovery(case)
        self.assertEqual(report["best_field_similarities"]["intervention_or_exposure"], 1.0)

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


class OpenAICompatibleProviderTests(unittest.TestCase):
    @staticmethod
    def _config() -> dict[str, object]:
        return {
            "schema_version": "1.0",
            "provider_id": "generic-test",
            "adapter": "openai_compatible",
            "display_name": "Generic Test",
            "base_url": "https://models.example.test/v1",
            "model": "model-a",
            "api_key_required": True,
            "api_key_env": "GENERIC_TEST_API_KEY",
            "credential_target": None,
            "allow_local_http": False,
            "features": {
                "json_output": True,
                "reasoning_effort": False,
                "deepseek_thinking": False,
            },
        }

    def test_factory_builds_secret_free_generic_configuration(self) -> None:
        config = self._config()
        validate_document(config, "provider_config")
        with patch.dict(os.environ, {"GENERIC_TEST_API_KEY": "unit-test-secret"}):
            provider = build_provider(config)
        self.assertIsInstance(provider, OpenAICompatibleProvider)
        self.assertEqual(provider.provider_name, "Generic Test")
        self.assertEqual(provider.credential_source, "environment:GENERIC_TEST_API_KEY")

    def test_chat_uses_common_payload_without_vendor_thinking_fields(self) -> None:
        provider = OpenAICompatibleProvider(
            provider_name="Generic Test",
            base_url="https://models.example.test/v1",
            model="model-a",
            api_key="unit-test-secret",
            credential_source="test",
        )
        response = {
            "model": "model-a-2026-08",
            "choices": [{"finish_reason": "stop", "message": {"content": "{}"}}],
            "usage": {"prompt_tokens": 4, "completion_tokens": 1, "total_tokens": 5},
        }
        with patch.object(provider, "_request", return_value=response) as request:
            result = provider.chat(
                [{"role": "user", "content": "Return JSON."}],
                max_tokens=16,
                json_output=True,
            )
        payload = request.call_args.args[2]
        self.assertEqual(payload["response_format"], {"type": "json_object"})
        self.assertNotIn("thinking", payload)
        self.assertNotIn("reasoning_effort", payload)
        self.assertEqual(result.provider, "Generic Test")

    def test_local_keyless_endpoint_requires_explicit_loopback_opt_in(self) -> None:
        provider = OpenAICompatibleProvider(
            provider_name="Local Runtime",
            base_url="http://127.0.0.1:8000/v1",
            model="local-model",
            api_key_required=False,
            allow_local_http=True,
            credential_source="none",
        )
        self.assertEqual(provider.credential_source, "none")
        with self.assertRaises(ProviderRequestError):
            OpenAICompatibleProvider(
                provider_name="Unsafe Runtime",
                base_url="http://192.168.1.20:8000/v1",
                model="local-model",
                api_key_required=False,
                allow_local_http=True,
            )


class StructuredCandidateRunnerTests(unittest.TestCase):
    @staticmethod
    def _result(content: dict[str, object] | str) -> ProviderResult:
        text = content if isinstance(content, str) else json.dumps(content)
        return ProviderResult(
            provider="generic-test",
            model="model-a",
            finish_reason="stop",
            content=text,
            content_sha256="d" * 64,
            prompt_tokens=20,
            completion_tokens=10,
            total_tokens=30,
            reasoning_tokens=None,
            system_fingerprint=None,
            credential_source="test",
        )

    @staticmethod
    def _abstention() -> dict[str, object]:
        return {
            "schema_version": "1.0",
            "abstention_id": "abstain-1",
            "timestamp_utc": TIMESTAMP,
            "stage": 3,
            "affected_decision": "full-text eligibility",
            "reason_code": "missing.full_text",
            "risk_signals": ["No lawful full text is available"],
            "required_human_role": "review_lead",
            "status": "open",
            "resolution": {
                "decision": "",
                "resolved_by": "",
                "resolved_at_utc": "",
                "rationale": "",
            },
        }

    def test_valid_candidate_is_schema_gated_and_not_accepted_state(self) -> None:
        provider = unittest.mock.Mock()
        provider.chat.return_value = self._result(self._abstention())
        run = run_structured_candidate(
            task_id="task-1",
            instruction="Create an abstention record from the supplied evidence.",
            input_document={"full_text": None},
            output_schema="abstention",
            provider=provider,
            created_at_utc=TIMESTAMP,
        )
        self.assertEqual(run["status"], "candidate_generated")
        self.assertEqual(run["attempts"], 1)
        self.assertEqual(run["usage_totals"]["total_tokens"], 30)
        self.assertEqual(run["request_budget"]["max_tokens_per_call"], 4096)
        self.assertEqual(run["acceptance_boundary"], "candidate_only_requires_workflow_gate")
        self.assertEqual(run["validation_diagnostics"], [])
        self.assertNotIn("content", run["provider_provenance"])

    def test_invalid_candidate_repairs_once_then_abstains(self) -> None:
        provider = unittest.mock.Mock()
        provider.chat.side_effect = [self._result({"wrong": True}), self._result("still invalid")]
        run = run_structured_candidate(
            task_id="task-2",
            instruction="Create an abstention record.",
            input_document={"full_text": None},
            output_schema="abstention",
            provider=provider,
            created_at_utc=TIMESTAMP,
        )
        self.assertEqual(run["status"], "abstain")
        self.assertEqual(run["attempts"], 2)
        self.assertEqual(run["usage_totals"]["total_tokens"], 60)
        self.assertIsNone(run["candidate"])
        self.assertIn("provider_output_failed_schema_after_repair", run["reason_codes"])
        self.assertEqual([item["phase"] for item in run["validation_diagnostics"]], ["initial_generation", "schema_repair"])
        self.assertIn("missing_required_property", run["validation_diagnostics"][0]["error_codes"])

    def test_large_transfer_is_refused_before_provider_call(self) -> None:
        provider = unittest.mock.Mock()
        with self.assertRaisesRegex(StructuredCandidateError, "transfer limit"):
            run_structured_candidate(
                task_id="task-3",
                instruction="Create an abstention record.",
                input_document={"text": "x" * 100},
                output_schema="abstention",
                provider=provider,
                maximum_input_characters=20,
            )
        provider.chat.assert_not_called()

    def test_batch_reserves_repair_budget_and_resumes_checkpoint(self) -> None:
        tasks = [
            {
                "schema_version": "1.0",
                "task_id": f"batch-{index}",
                "instruction": "Create an abstention record.",
                "input_document": {"record": index},
                "output_schema": "abstention",
                "max_tokens": 32,
                "thinking": False,
            }
            for index in (1, 2)
        ]
        provider = unittest.mock.Mock()
        provider.chat.side_effect = [
            self._result(self._abstention()),
            self._result({**self._abstention(), "abstention_id": "abstain-2"}),
        ]
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "runs.jsonl"
            first = run_structured_batch(
                tasks,
                provider=provider,
                output_path=output,
                maximum_provider_calls=2,
                maximum_reserved_output_tokens=128,
            )
            self.assertEqual(first["status"], "budget_stopped")
            self.assertEqual(first["processed"], 1)
            second = run_structured_batch(
                tasks,
                provider=provider,
                output_path=output,
                maximum_provider_calls=4,
                maximum_reserved_output_tokens=128,
            )
            self.assertEqual(second["status"], "completed")
            self.assertEqual(second["resumed"], 1)
            self.assertEqual(second["processed"], 1)
            self.assertEqual(len(output.read_text(encoding="utf-8").splitlines()), 2)

    def test_failed_request_is_charged_at_worst_case_and_stops_batch(self) -> None:
        tasks = [
            {
                "schema_version": "1.0",
                "task_id": f"failure-{index}",
                "instruction": "Create an abstention record.",
                "input_document": {"record": index},
                "output_schema": "abstention",
                "max_tokens": 32,
                "thinking": False,
            }
            for index in (1, 2)
        ]
        provider = unittest.mock.Mock()
        provider.chat.side_effect = ProviderRequestError("request failed")
        with tempfile.TemporaryDirectory() as directory:
            summary = run_structured_batch(
                tasks,
                provider=provider,
                output_path=Path(directory) / "runs.jsonl",
                maximum_provider_calls=2,
                maximum_reserved_output_tokens=64,
            )
        self.assertEqual(summary["status"], "budget_stopped")
        self.assertEqual(summary["provider_calls_in_checkpoint"], 2)
        self.assertEqual(len(summary["dead_letters"]), 1)
        self.assertEqual(provider.chat.call_count, 1)


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

    def test_generic_direct_generation_uses_an_independent_non_decision_prompt(self) -> None:
        proposal = self._proposal()
        proposal["generation_method"] = "model_proposal"
        provider = unittest.mock.Mock(spec=DeepSeekProvider)
        provider.chat.return_value = self._provider_result({"proposals": [proposal]})
        batch = propose_topics(
            landscape(), provider, generation_mode="generic_direct",
            created_at_utc=TIMESTAMP,
        )
        self.assertEqual(batch["status"], "proposals_generated")
        self.assertIn("generic_direct_generation_baseline", batch["reason_codes"])
        prompt = json.loads(provider.chat.call_args.args[0][1]["content"])
        self.assertEqual(prompt["output_contract"]["generation_methods"], ["model_proposal"])
        self.assertNotIn("decision value", prompt["task"].casefold())
        self.assertNotIn("cross-domain", prompt["task"].casefold())

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
        repair_messages = provider.chat.call_args_list[1].args[0]
        self.assertEqual(len(repair_messages), 2)
        self.assertIn("allowed_node_ids", repair_messages[1]["content"])
        self.assertNotIn('"edges"', repair_messages[1]["content"])

    def test_retains_valid_proposals_when_a_sibling_references_unknown_nodes(self) -> None:
        invalid = self._proposal()
        invalid["evidence_node_ids"] = ["unknown-study"]
        provider = unittest.mock.Mock(spec=DeepSeekProvider)
        provider.chat.return_value = self._provider_result(
            {"proposals": [self._proposal(), invalid]}
        )
        batch = propose_topics(landscape(), provider, created_at_utc=TIMESTAMP)
        self.assertEqual(batch["status"], "proposals_generated")
        self.assertEqual(len(batch["proposals"]), 1)
        self.assertEqual(batch["model_provenance"]["call_count"], 1)
        self.assertIn("provider_invalid_proposals_dropped", batch["reason_codes"])
        self.assertIn("provider_repair_failed_unknown_node", batch["reason_codes"])

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
