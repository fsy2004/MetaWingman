from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from metawingman.scripts.metawingman_core.joint_lifecycle_runner import (
    AtomicStageBudgetMeter,
)
from metawingman.scripts.metawingman_core.joint_topic_stage_adapter import (
    execute_topic_feasibility_stage,
)
from metawingman.scripts.metawingman_core.model_provider import ProviderResult
from metawingman.scripts.metawingman_core.schema_guard import validate_document


ROOT = Path(__file__).resolve().parents[1]
TIMESTAMP = "2026-08-22T12:00:00Z"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def _landscape() -> dict:
    return {
        "schema_version": "1.0", "landscape_id": "landscape-1",
        "run_context": "historical_rediscovery", "domain_ids": ["mental-health"],
        "corpus_boundary": {
            "cutoff_date": "2023-06-03", "target_identity_status": "sealed",
            "target_descendants_status": "sealed", "post_cutoff_evidence_status": "sealed",
            "leakage_audit": "passed",
            "excluded_identity_fields": [
                "title", "authors", "doi", "pmid", "journal", "abstract",
                "keywords", "citations", "descendants",
            ],
        },
        "nodes": [
            {"node_id": "pub-1", "node_type": "publication", "label": "Exercise trial for depression", "domain_ids": ["mental-health"], "domain_assignment_status": "explicit_record", "observed_at": "2022-01-01", "source_ids": ["pmid:1"], "source_family_ids": ["study:trial-a"], "provenance_status": "verified"},
            {"node_id": "pub-2", "node_type": "publication", "label": "Exercise review for depression", "domain_ids": ["mental-health"], "domain_assignment_status": "explicit_record", "observed_at": "2021-01-01", "source_ids": ["pmid:2"], "source_family_ids": ["source:review-a"], "provenance_status": "verified"},
            {"node_id": "guideline-1", "node_type": "guideline", "label": "Depression treatment guideline", "domain_ids": ["mental-health"], "domain_assignment_status": "explicit_record", "observed_at": "2020-01-01", "source_ids": ["guideline:1"], "source_family_ids": ["source:guideline-a"], "provenance_status": "verified"},
            {"node_id": "concept-exercise", "node_type": "intervention_or_exposure", "label": "exercise", "domain_ids": ["mental-health"], "domain_assignment_status": "derived_from_explicit_records", "observed_at": "2021-01-01", "source_ids": ["pmid:1", "pmid:2"], "source_family_ids": ["study:trial-a", "source:review-a"], "provenance_status": "machine_extracted"},
        ],
        "edges": [],
        "selection_policy": {
            "policy_version": "v1",
            "weights": {"decision_relevance": .2, "unresolved_uncertainty": .15, "feasibility": .15, "evidence_maturity": .1, "nonduplication": .15, "update_need": .1, "equity_priority": .1, "cross_domain_value": .05},
            "minimum_primary_studies": 1, "minimum_source_families": 1,
            "minimum_known_item_recall": .8, "maximum_review_overlap": .6,
            "maximum_contamination_risk": .2, "maximum_ambiguity_risk": .3,
            "minimum_utility_score": .4, "maximum_portfolio_size": 3,
            "diversity_penalty": .1, "allow_update_topics": True,
        },
        "created_at_utc": TIMESTAMP,
    }


def _proposal(method: str) -> dict:
    return {
        "generation_method": method,
        "question_framework": {
            "population": ["adults with depression"],
            "intervention_or_exposure": ["exercise"],
            "comparator": ["usual care"],
            "outcome": ["depressive symptoms"],
            "study_design": ["randomised trials"],
            "synthesis_route": "network meta-analysis",
        },
        "concept_node_ids": ["concept-exercise"],
        "evidence_node_ids": ["pub-1", "pub-2", "guideline-1"],
        "evidence_interpretations": [
            {"node_id": "pub-1", "role": "uncertainty", "interpretation": "Comparative uncertainty remains."},
            {"node_id": "guideline-1", "role": "decision_need", "interpretation": "A treatment choice is unresolved."},
        ],
        "disconfirmation_queries": [
            {"check_type": "existing_review_overlap", "query": "exercise depression systematic review"},
        ],
    }


class FakeProvider:
    credential_source = "test-secret-store"

    def __init__(self, method: str):
        self.method = method

    def chat(self, messages: list[dict], **kwargs: object) -> ProviderResult:
        content = json.dumps({"proposals": [_proposal(self.method)]})
        return ProviderResult(
            provider="deepseek", model="deepseek-v4-flash", finish_reason="stop",
            content=content, content_sha256=hashlib.sha256(content.encode()).hexdigest(),
            prompt_tokens=100, completion_tokens=80, total_tokens=180,
            reasoning_tokens=0, system_fingerprint="test",
            credential_source=self.credential_source,
        )


def _request(root: Path, *, decision: bool) -> dict:
    landscape_path = root / "landscape.json"
    provider_path = root / "provider.json"
    _write(landscape_path, _landscape())
    _write(provider_path, {"fixture": True})
    output_dir = root / ("decision" if decision else "generic")
    output_dir.mkdir()
    config = {
        "schema_version": "1.0",
        "stage_id": "topic_feasibility",
        "adapter_id": "joint-topic-feasibility-v1",
        "provider_config": {
            "path": provider_path.relative_to(ROOT).as_posix(),
            "sha256": _sha(provider_path),
        },
        "maximum_input_tokens_per_call": 1000,
        "maximum_proposals": 3,
        "maximum_prompt_characters": 100000,
        "thinking": False,
        "external_search_lower_date": "2010-01-01",
        "external_search_maximum_records": 100,
        "auditor_id": "ncbi-pubmed-deterministic-topic-audit-v1",
    }
    validate_document(config, "joint_topic_stage_config")
    return {
        "execution_id": "topic-stage-test", "case_slot_id": "slot-1",
        "case_id": "case-1", "review_family_id": "family-1",
        "arm_id": "decision" if decision else "generic", "seed": 20260820,
        "stage_id": "topic_feasibility", "ordinal": 0,
        "stage_output_dir": str(output_dir), "repository_root": str(ROOT),
        "created_at_utc": TIMESTAMP, "config": config,
        "topic_inputs": [{
            "binding_id": "temporal_evidence_landscape",
            "path": landscape_path.relative_to(ROOT).as_posix(),
            "sha256": _sha(landscape_path),
        }],
        "topic_opportunity_control": decision,
        "conclusion_risk_impact_control": False,
        "candidate_generation_mode": (
            "decision_aware_direct_generation" if decision else "generic_direct_generation"
        ),
        "acquisition_mode": "fixed_generic",
        "published_reference_accessed": False,
    }


class JointTopicStageAdapterTests(unittest.TestCase):
    def test_generic_arm_generates_its_own_candidates_and_uses_llm_order(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            root = Path(tmp)
            request = _request(root, decision=False)
            meter = AtomicStageBudgetMeter({
                "max_provider_calls": 2, "max_input_tokens": 2000,
                "max_output_tokens": 10000, "wall_seconds": 10,
            })
            output = execute_topic_feasibility_stage(
                request, meter,
                provider_builder=lambda config: FakeProvider("model_proposal"),
                external_searcher=lambda *args, **kwargs: self.fail("generic arm must not use decision audits"),
            )
            validate_document(output, "joint_lifecycle_stage_output")
            self.assertEqual(output["status"], "completed")
            self.assertEqual(
                {item["check_id"] for item in output["scientific_checks"]},
                {"direct_candidate_generation", "generic_candidate_generation"},
            )
            state = json.loads(next(
                Path(item["path"]).read_text() for item in output["artifacts"]
                if item["artifact_id"] == "topic_state"
            ))
            self.assertEqual(state["selection_policy"], "generic_llm_order")
            self.assertEqual(len(state["selected_proposals"]), 1)

    def test_decision_arm_runs_external_opposition_audit_and_frozen_control(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            root = Path(tmp)
            request = _request(root, decision=True)
            meter = AtomicStageBudgetMeter({
                "max_provider_calls": 2, "max_input_tokens": 2000,
                "max_output_tokens": 10000, "wall_seconds": 10,
            })

            def external_searcher(proposal: dict, landscape: dict, **kwargs: object) -> dict:
                return {
                    "primary_studies": {"query": "primary frozen query", "pmids": ["1"]},
                    "reviews": {"query": "review frozen query", "pmids": ["2"]},
                    "protocols": {"query": "protocol frozen query", "pmids": []},
                }

            output = execute_topic_feasibility_stage(
                request, meter,
                provider_builder=lambda config: FakeProvider("cross_domain_bridge"),
                external_searcher=external_searcher,
            )
            validate_document(output, "joint_lifecycle_stage_output")
            self.assertEqual(output["status"], "completed")
            self.assertEqual(
                {item["check_id"] for item in output["scientific_checks"]},
                {"direct_candidate_generation", "decision_opportunity_control"},
            )
            artifact_ids = {item["artifact_id"] for item in output["artifacts"]}
            self.assertTrue({
                "proposal_batch", "external_search_receipts", "signal_audits",
                "topic_candidates", "topic_decision", "topic_state",
            }.issubset(artifact_ids))


if __name__ == "__main__":
    unittest.main()
