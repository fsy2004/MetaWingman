from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import threading
import unittest
from datetime import datetime, timezone
from pathlib import Path

from jsonschema import Draft202012Validator


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = REPO_ROOT / "metawingman" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from metawingman_core.action_guard import evaluate_action  # noqa: E402
from metawingman_core.capability_router import route_models  # noqa: E402
from metawingman_core.method_contract import inspect_method_contract  # noqa: E402
from metawingman_core.protocol_compiler import compile_protocol  # noqa: E402
from metawingman_core.schema_guard import SchemaValidationError, validate_document  # noqa: E402
from metawingman_core.state_store import (  # noqa: E402
    EventLedger,
    StateStoreError,
    append_jsonl_record,
    sha256_json,
)


ZERO_HASH = "0" * 64


def registry(model_count: int = 3, providers: tuple[str, ...] = ("alpha", "beta", "gamma")) -> dict[str, object]:
    models = []
    for index in range(model_count):
        models.append({
            "model_id": f"model-{index + 1}",
            "provider": providers[index % len(providers)],
            "model": f"model-{index + 1}",
            "version": "2026-01-01",
            "capabilities": ["screening"],
            "modalities": ["text", "pdf"],
            "context_tokens": 100000,
            "allowed_tools": ["evidence_lookup"],
            "cost": {"input_per_million": 1.0, "output_per_million": 2.0, "currency": "USD"},
            "latency_class": "standard",
            "calibration": {
                "dataset_id": "screening-v1",
                "evaluated_at": "2026-01-01T00:00:00Z",
                "metrics": {
                    "accuracy": 0.85 + index * 0.01,
                    "recall": 0.86 + index * 0.01,
                    "precision": 0.84 + index * 0.01,
                    "critical_error_free": 0.90 + index * 0.01,
                    "counterevidence_recall": 0.80 + index * 0.02,
                },
            },
        })
    return {"schema_version": "1.0", "models": models}


def action_request(action_type: str = "read_public_metadata", **overrides: object) -> dict[str, object]:
    action: dict[str, object] = {
        "schema_version": "1.0",
        "action_id": "action-001",
        "action_type": action_type,
        "stage": 0,
        "risk_class": "low",
        "instruction_source": "agent",
        "requested_by": {"type": "model", "id": "planner"},
        "input_sha256": ZERO_HASH,
        "idempotency_key": "topic-search-001",
        "evidence_anchor_ids": [],
        "human_approval": {"status": "not_required", "approved_by": "", "approved_at_utc": "", "scope": ""},
    }
    action.update(overrides)
    return action


def ledger_event(event_id: str = "event-001", key: str = "search-001") -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "event_id": event_id,
        "idempotency_key": key,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "action_type": "read_public_metadata",
        "actor": {"type": "tool", "id": "pubmed", "version": "1"},
        "status": "completed",
        "input": {"sha256": ZERO_HASH, "media_type": "application/json", "reference": "query.json"},
        "output": {"sha256": "1" * 64, "media_type": "application/json", "reference": "results.json"},
        "execution": {"prompt_sha256": None, "retry_count": 0, "retry_budget": 2, "latency_ms": 25, "cost_usd": 0},
        "evidence_anchor_ids": [],
        "reason_codes": [],
        "previous_event_hash": None,
        "event_hash": ZERO_HASH,
    }


class ActionGuardTests(unittest.TestCase):
    def test_low_risk_reversible_action_is_allowed(self) -> None:
        self.assertTrue(evaluate_action(action_request()).allowed)

    def test_untrusted_document_cannot_authorize_action(self) -> None:
        decision = evaluate_action(action_request(instruction_source="untrusted_document"))
        self.assertEqual(decision.status, "blocked")
        self.assertIn("untrusted_content_cannot_authorize_actions", decision.reason_codes)

    def test_high_risk_action_abstains_without_human_approval(self) -> None:
        decision = evaluate_action(action_request(
            "finalize_exclusion",
            risk_class="high",
            evidence_anchor_ids=["anchor-1"],
            human_approval={"status": "pending", "approved_by": "", "approved_at_utc": "", "scope": ""},
        ))
        self.assertEqual(decision.status, "abstained")
        self.assertIn("human_approval_required", decision.reason_codes)

    def test_claim_without_anchor_abstains(self) -> None:
        decision = evaluate_action(action_request("draft_claim", risk_class="medium"))
        self.assertEqual(decision.status, "abstained")
        self.assertIn("evidence_anchor_required", decision.reason_codes)

    def test_model_cannot_understate_action_risk(self) -> None:
        decision = evaluate_action(action_request("freeze_protocol", risk_class="low"))
        self.assertEqual(decision.status, "blocked")
        self.assertIn("risk_class_understated", decision.reason_codes)

    def test_high_risk_approval_requires_timestamp_with_timezone(self) -> None:
        decision = evaluate_action(action_request(
            "freeze_protocol",
            risk_class="high",
            human_approval={"status": "approved", "approved_by": "lead", "approved_at_utc": "2026-08-12", "scope": "freeze_protocol"},
        ))
        self.assertEqual(decision.status, "blocked")
        self.assertIn("invalid_human_approval_record", decision.reason_codes)

    def test_protocol_freeze_requires_project_context(self) -> None:
        decision = evaluate_action(action_request(
            "freeze_protocol",
            risk_class="high",
            human_approval={
                "status": "approved",
                "approved_by": "lead",
                "approved_at_utc": "2026-08-12T00:00:00Z",
                "scope": "action-001",
            },
        ))
        self.assertEqual(decision.status, "abstained")
        self.assertIn("project_context_required", decision.reason_codes)

    def test_high_risk_approval_must_be_bound_to_exact_action(self) -> None:
        for unsafe_scope in ("*", "finalize_exclusion"):
            with self.subTest(scope=unsafe_scope):
                decision = evaluate_action(action_request(
                    "finalize_exclusion",
                    risk_class="high",
                    evidence_anchor_ids=["anchor-1"],
                    human_approval={
                        "status": "approved",
                        "approved_by": "lead",
                        "approved_at_utc": "2026-08-12T00:00:00Z",
                        "scope": unsafe_scope,
                    },
                ))
                self.assertEqual(decision.status, "blocked")
                self.assertIn("human_approval_scope_mismatch", decision.reason_codes)


class ProtocolCompilerTests(unittest.TestCase):
    def test_operational_criterion_is_ready(self) -> None:
        result = compile_protocol({
            "protocol_version": "1.0",
            "status": "draft",
            "criteria": [{
                "criterion_id": "age",
                "domain": "population",
                "label": "Adults",
                "predicate": {"field": "mean_age", "operator": "gte", "value": 18, "unit": "years", "normalization": "years"},
                "missing_policy": "unclear",
                "full_text_required": True,
                "source_section": "Eligibility criteria",
            }],
        })
        self.assertTrue(result.ready_to_freeze)

    def test_ambiguous_numeric_rule_cannot_freeze(self) -> None:
        result = compile_protocol({
            "protocol_version": "1.0",
            "status": "frozen",
            "criteria": [{"criterion_id": "age", "domain": "population", "label": "Older adults", "operator": "gte", "value": 65}],
        })
        self.assertFalse(result.ready_to_freeze)
        self.assertEqual(result.document["status"], "draft")
        self.assertEqual(result.document["criteria"][0]["status"], "needs_human_definition")
        self.assertGreaterEqual(len(result.issues), 2)


class CapabilityRouterTests(unittest.TestCase):
    def test_low_risk_uses_one_capable_executor(self) -> None:
        decision = route_models(registry(), "screening", {"text"}, "low")
        self.assertEqual(decision.status, "routed")
        self.assertEqual(set(decision.assignments), {"executor"})
        self.assertEqual(decision.test_time_calls, 1)

    def test_high_risk_uses_diverse_proposal_opposition_judge(self) -> None:
        decision = route_models(registry(), "screening", {"pdf"}, "high", {"evidence_lookup"})
        self.assertEqual(decision.status, "routed")
        self.assertEqual(set(decision.assignments), {"proposal", "opposition", "judge"})
        self.assertEqual(len(set(decision.assignments.values())), 3)
        self.assertTrue(decision.requires_human_signature)

    def test_high_risk_abstains_without_provider_diversity(self) -> None:
        decision = route_models(registry(providers=("alpha",)), "screening", {"text"}, "high")
        self.assertEqual(decision.status, "abstained")
        self.assertIn("insufficient_provider_diversity", decision.reason_codes)


class EventLedgerTests(unittest.TestCase):
    def test_idempotency_prevents_duplicate_events(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            ledger = EventLedger(Path(directory) / "events.jsonl")
            first = ledger.append(ledger_event())
            second = ledger.append(ledger_event(event_id="event-002"))
            self.assertTrue(first.appended)
            self.assertFalse(second.appended)
            self.assertEqual(len(ledger.read()), 1)
            self.assertEqual(ledger.verify(), [])

    def test_generic_jsonl_appends_serialize_unique_keys(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "records.jsonl"
            errors: list[Exception] = []

            def append(index: int) -> None:
                try:
                    event = ledger_event(
                        event_id=f"generic-{index:03d}",
                        key=f"generic-key-{index:03d}",
                    )
                    event["previous_event_hash"] = None
                    event["event_hash"] = "0" * 64
                    append_jsonl_record(
                        path,
                        event,
                        "event_ledger",
                        unique_fields=("event_id", "idempotency_key"),
                    )
                except Exception as exc:  # pragma: no cover - assertion reports race
                    errors.append(exc)

            threads = [threading.Thread(target=append, args=(index,)) for index in range(12)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            self.assertEqual(errors, [])
            self.assertEqual(len(path.read_text(encoding="utf-8").splitlines()), len(threads))
            with self.assertRaises(StateStoreError):
                append_jsonl_record(
                    path,
                    json.loads(path.read_text(encoding="utf-8").splitlines()[0]),
                    "event_ledger",
                    unique_fields=("event_id",),
                )

    def test_missing_completed_output_hash_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            ledger = EventLedger(Path(directory) / "events.jsonl")
            event = ledger_event()
            event["output"] = {"sha256": None, "media_type": "application/json", "reference": "results.json"}
            with self.assertRaises(ValueError):
                ledger.append(event)

    def test_tampering_breaks_hash_chain(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "events.jsonl"
            ledger = EventLedger(path)
            ledger.append(ledger_event())
            stored = json.loads(path.read_text(encoding="utf-8"))
            stored["output"]["reference"] = "tampered.json"
            path.write_text(json.dumps(stored) + "\n", encoding="utf-8")
            self.assertTrue(any("event_hash mismatch" in issue for issue in ledger.verify()))

    def test_schema_rejects_unknown_fields(self) -> None:
        event = ledger_event()
        event["unexpected"] = True
        with self.assertRaises(SchemaValidationError):
            validate_document(event, "event_ledger")

    def test_concurrent_appends_preserve_one_hash_chain(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            ledger = EventLedger(Path(directory) / "events.jsonl")
            errors: list[Exception] = []

            def append(index: int) -> None:
                try:
                    ledger.append(ledger_event(
                        event_id=f"event-{index:03d}",
                        key=f"concurrent-{index:03d}",
                    ))
                except Exception as exc:  # pragma: no cover - assertion reports captured race
                    errors.append(exc)

            threads = [threading.Thread(target=append, args=(index,)) for index in range(1, 17)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            self.assertEqual(errors, [])
            self.assertEqual(len(ledger.read()), len(threads))
            self.assertEqual(ledger.verify(), [])


class SchemaDefinitionTests(unittest.TestCase):
    def test_all_bundled_schemas_are_valid_draft_2020_12(self) -> None:
        for path in sorted((REPO_ROOT / "metawingman" / "schemas").glob("*.schema.json")):
            with self.subTest(schema=path.name):
                Draft202012Validator.check_schema(json.loads(path.read_text(encoding="utf-8")))

    def test_model_cannot_count_as_required_independent_human(self) -> None:
        assignment = {
            "schema_version": "1.0",
            "assignment_id": "assignment-1",
            "task_type": "full_text_eligibility",
            "artifact_ids": ["report-1"],
            "round": 1,
            "actor": {"type": "model", "id": "review-model", "version": "2026-08-12"},
            "role": "reviewer",
            "independence_group": "model-group-1",
            "independent_human_required": True,
            "counts_toward_independent_human_requirement": True,
            "ai_exposure": {"order": "not_applicable", "exposed_to_ai_output_ids": [], "recorded_at_utc": None},
            "conflict_of_interest": {"status": "none_declared", "details": "", "managed_by": ""},
            "status": "assigned",
            "assigned_at_utc": "2026-08-12T00:00:00Z",
            "completed_at_utc": None,
            "decision_ref": None,
        }
        with self.assertRaises(SchemaValidationError):
            validate_document(assignment, "reviewer_assignment")

    def test_final_claim_requires_human_responsibility(self) -> None:
        claim = {
            "schema_version": "1.0",
            "claim_id": "claim-1",
            "claim_type": "observation",
            "text": "The prespecified synthesis estimated an effect.",
            "scope": {
                "synthesis_id": "synthesis-1",
                "population": "Adults",
                "contrast": "Intervention versus control",
                "outcome": "Outcome 1",
                "time_window": "12 weeks",
                "applicability_limits": [],
            },
            "certainty": {"framework": "GRADE", "judgment": "low", "dossier_id": "grade-1"},
            "allowed_verbs": ["estimated"],
            "evidence_node_ids": ["synthesis-1"],
            "assertion_ids": [],
            "analysis_output_ids": [],
            "counterevidence_node_ids": [],
            "status": "final",
            "created_by": {"type": "model", "id": "writer", "version": "2026-08-12"},
            "verification": {
                "status": "passed",
                "support_check": True,
                "numeric_check": True,
                "scope_check": True,
                "verified_by": "claim-verifier",
                "verified_at_utc": "2026-08-12T00:00:00Z",
                "notes": "",
            },
            "human_responsibility": {"status": "pending", "responsible_by": "", "accepted_at_utc": None},
            "created_at_utc": "2026-08-12T00:00:00Z",
            "updated_at_utc": "2026-08-12T00:00:00Z",
        }
        with self.assertRaises(SchemaValidationError):
            validate_document(claim, "claim")

    def test_accepted_extraction_requires_passed_verification(self) -> None:
        candidate = {
            "schema_version": "1.0",
            "candidate_id": "candidate-1",
            "document_id": "document-1",
            "report_id": "report-1",
            "study_id": "study-1",
            "result_id": "result-1",
            "field": "events_intervention",
            "value": {"raw": "10", "normalized": 10, "data_type": "integer"},
            "unit": "participants",
            "anchor_ids": ["anchor-1"],
            "channel": "table",
            "created_by": {"type": "model", "id": "extractor", "version": "2026-08-12"},
            "confidence": 0.9,
            "derivation": {
                "method": "direct",
                "formula_or_rule": "",
                "input_candidate_ids": [],
                "tool": "",
                "tool_version": "",
            },
            "status": "accepted",
            "verification": {
                "method": "independent_extraction",
                "status": "pending",
                "verified_by": "",
                "independently_derived": True,
                "verified_at_utc": None,
                "discrepancy": "",
            },
            "created_at_utc": "2026-08-12T00:00:00Z",
        }
        with self.assertRaises(SchemaValidationError):
            validate_document(candidate, "extraction_candidate")


class MethodContractTests(unittest.TestCase):
    def test_pinned_profile_rejects_placeholder_authority_version(self) -> None:
        profile = {
            "schema_version": "1.0",
            "profile_id": "profile-1",
            "review_family": "intervention",
            "status": "pinned",
            "operating_mode": {
                "name": "assurance",
                "replacement_claim": "",
                "evaluation_plan_id": None,
                "declared_by": "lead",
                "declared_at_utc": "2026-08-12T00:00:00Z",
            },
            "authorities": [
                {
                    "authority_id": f"authority-{role}",
                    "role": role,
                    "title": f"{role.title()} standard",
                    "organization": "Standards body",
                    "version": "current",
                    "source_url": "https://example.org/standard",
                    "verified_at_utc": "2026-08-12T00:00:00Z",
                    "applicability": "applicable",
                    "rationale": "Selected for this review.",
                }
                for role in ("conduct", "reporting", "appraisal", "certainty")
            ],
            "independent_review": [],
            "created_at_utc": "2026-08-12T00:00:00Z",
            "updated_at_utc": "2026-08-12T00:00:00Z",
        }
        validate_document(profile, "review_profile")
        issues = inspect_method_contract(Path.cwd(), {"review_profile": profile}, {}, {})
        self.assertTrue(any("needs an exact version" in issue for issue in issues))

    def test_evaluation_mode_can_record_preregistered_model_replacement(self) -> None:
        profile = {
            "schema_version": "1.0",
            "profile_id": "profile-evaluation",
            "review_family": "intervention",
            "status": "draft",
            "operating_mode": {
                "name": "evaluation",
                "replacement_claim": "Test model replacement of one full-text reviewer.",
                "evaluation_plan_id": "evaluation-plan-1",
                "declared_by": "human-lead",
                "declared_at_utc": "2026-08-12T00:00:00Z",
            },
            "authorities": [],
            "independent_review": [{
                "task_type": "full_text_eligibility",
                "independent_human_required": True,
                "minimum_independent_humans": 2,
                "ai_may_prepare": True,
                "ai_may_replace_human": True,
                "required_ai_exposure_order": "recorded",
                "adjudication_rule": "human_lead",
            }],
            "created_at_utc": "2026-08-12T00:00:00Z",
            "updated_at_utc": "2026-08-12T00:00:00Z",
        }
        assignment = {
            "schema_version": "1.0",
            "assignment_id": "assignment-evaluation",
            "task_type": "full_text_eligibility",
            "artifact_ids": ["report-1"],
            "round": 1,
            "actor": {"type": "model", "id": "screen-model", "version": "2026-08-12"},
            "role": "reviewer",
            "independence_group": "model-group-1",
            "independent_human_required": True,
            "counts_toward_independent_human_requirement": False,
            "ai_exposure": {
                "order": "not_applicable",
                "exposed_to_ai_output_ids": [],
                "recorded_at_utc": None,
            },
            "conflict_of_interest": {
                "status": "none_declared",
                "details": "",
                "managed_by": "",
            },
            "status": "completed",
            "assigned_at_utc": "2026-08-12T00:00:00Z",
            "completed_at_utc": "2026-08-12T00:01:00Z",
            "decision_ref": "decision-1",
        }
        validate_document(profile, "review_profile")
        validate_document(assignment, "reviewer_assignment")
        gates = {
            str(stage): {
                "status": "complete" if stage <= 3 else "not_started",
                "verified_by": "human-lead" if stage <= 3 else "",
                "verified_at": "2026-08-12T00:00:00Z" if stage <= 3 else "",
                "evidence": [],
            }
            for stage in range(10)
        }
        issues = inspect_method_contract(
            Path.cwd(),
            {"review_profile": profile},
            {"reviewer_assignment": [assignment]},
            gates,
        )
        self.assertFalse(any("qualifying independent humans" in issue for issue in issues))

    def test_verified_analysis_and_human_responsible_claim_form_valid_chain(self) -> None:
        timestamp = "2026-08-12T00:00:00Z"
        gates = {
            str(stage): {
                "status": "not_started",
                "verified_by": "",
                "verified_at": "",
                "evidence": [],
            }
            for stage in range(10)
        }
        protocol = {
            "schema_version": "1.0",
            "protocol_id": "protocol-1",
            "protocol_version": "1.0",
            "status": "frozen",
            "profile_id": "profile-1",
            "decision_context": {
                "decision": "Estimate benefit for a clinical decision.",
                "stakeholders": ["patients", "clinicians"],
                "setting": "Outpatient care",
                "intended_use": "Guideline decision support",
            },
            "review_questions": [{
                "question_id": "question-1",
                "objective": "Estimate the intervention effect.",
                "framework": "PICO",
                "dimensions": [{
                    "name": "population",
                    "value": "Adults",
                    "operational_definition": "Participants aged 18 years or older.",
                }],
            }],
            "synthesis_questions": [{
                "synthesis_id": "synthesis-1",
                "review_question_ids": ["question-1"],
                "population": "Adults",
                "contrast": "Intervention versus control",
                "outcome_id": "outcome-1",
                "time_window": "12 weeks",
                "effect_measure": "risk ratio",
                "estimand": {
                    "estimand_id": "estimand-1",
                    "target_population": "Eligible adults",
                    "contrast": "Assignment to intervention versus control",
                    "outcome": "Participants with the event",
                    "time_horizon": "12 weeks",
                    "population_summary": "Average risk ratio",
                    "analysis_unit": "randomized participant",
                    "conditioning_set": [],
                },
                "decision_thresholds": [{
                    "threshold_id": "threshold-1",
                    "type": "minimal_importance",
                    "value": 0.9,
                    "unit": "risk ratio",
                    "direction": "less",
                    "rationale": "Prespecified clinically important benefit.",
                }],
                "poolability_rule": "Pool only sufficiently aligned estimands.",
            }],
            "outcome_hierarchy": [{
                "outcome_id": "outcome-1",
                "label": "Clinical event",
                "role": "primary",
                "construct": "Participants with the event",
                "preferred_measures": ["risk ratio"],
                "time_windows": ["12 weeks"],
                "result_selection_rule": "Use the prespecified intention-to-treat result.",
            }],
            "criteria_artifact": {
                "path": "01_protocol/protocol_criteria.json",
                "schema": "protocol_criteria",
                "status": "frozen",
                "sha256": ZERO_HASH,
            },
            "source_plan": [{
                "source_id": "source-1",
                "source_type": "bibliographic_database",
                "database": "Example database",
                "platform": "Example platform",
                "access_route": "user_export",
                "required": True,
                "query_file": "02_search/queries/example.txt",
                "coverage": "Inception to protocol freeze",
            }],
            "amendment_policy": {
                "freeze_trigger": "Human approval",
                "prospective_change_rule": "Record before affected results are inspected.",
                "post_hoc_label_required": True,
                "rerun_impact_analysis": True,
            },
            "created_at_utc": timestamp,
            "frozen_at_utc": timestamp,
            "frozen_by": "human-lead",
        }
        dossier = {
            "schema_version": "1.0",
            "dossier_id": "certainty-1",
            "dossier_type": "certainty",
            "target": {
                "type": "synthesis",
                "id": "synthesis-1",
                "study_id": None,
                "result_id": None,
                "synthesis_id": "synthesis-1",
            },
            "framework": {
                "name": "GRADE",
                "version": "2025 handbook release",
                "organization": "GRADE Working Group",
                "source_url": "https://www.gradeworkinggroup.org/",
                "verified_at_utc": timestamp,
                "adapter_version": "1.0",
            },
            "evidence_node_ids": ["synthesis-1"],
            "domains": [{
                "domain_id": "risk-of-bias",
                "label": "Risk of bias",
                "signaling_questions": [],
                "supporting_anchor_ids": [],
                "counterevidence_anchor_ids": [],
                "proposal": "Serious limitation",
                "rationale": "The accepted appraisal dossiers support downgrading.",
            }],
            "overall_proposal": {
                "actor_id": "proposal-model",
                "judgment": "low",
                "rationale": "One-level downgrade from the starting certainty.",
            },
            "opposition": {
                "actor_id": "opposition-model",
                "counter_judgment": "moderate",
                "anchor_ids": [],
                "rationale": "A plausible less severe interpretation was considered.",
            },
            "judge_recommendation": {
                "actor_id": "judge-model",
                "judgment": "low",
                "reason_codes": ["risk_of_bias"],
                "confidence": 0.9,
                "abstained": False,
            },
            "missing_information": [],
            "status": "final",
            "final_judgment": "low",
            "human_signature": {
                "status": "approved",
                "signed_by": "human-lead",
                "signed_at_utc": timestamp,
                "notes": "Reviewed against the evidence dossier.",
            },
            "created_at_utc": timestamp,
            "updated_at_utc": timestamp,
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            input_path = root / "06_analysis/input/frozen.csv"
            output_path = root / "06_analysis/output/result.json"
            input_path.parent.mkdir(parents=True)
            output_path.parent.mkdir(parents=True)
            input_path.write_text("study,effect,se\nA,0.8,0.1\n", encoding="utf-8")
            output_path.write_text('{"estimate": 0.8}\n', encoding="utf-8")
            input_hash = hashlib.sha256(input_path.read_bytes()).hexdigest()
            output_hash = hashlib.sha256(output_path.read_bytes()).hexdigest()
            review_state = {
                "schema_version": "1.0",
                "project_id": "valid-chain",
                "title": "Valid method-contract chain",
                "profile": "intervention",
                "stage": 0,
                "protocol": {
                    "version": "1.0",
                    "status": "frozen",
                    "sha256": ZERO_HASH,
                    "registration": {"registry": "", "id": "", "url": ""},
                },
                "gates": gates,
                "unresolved_risks": [],
                "freezes": [
                    {
                        "freeze_id": "protocol-freeze-1",
                        "kind": "protocol",
                        "sha256": ZERO_HASH,
                        "created_at_utc": timestamp,
                        "approved_by": "human-lead",
                    },
                    {
                        "freeze_id": "data-freeze-1",
                        "kind": "data",
                        "sha256": input_hash,
                        "created_at_utc": timestamp,
                        "approved_by": "human-lead",
                    },
                ],
                "updated_at_utc": timestamp,
            }
            manifest = {
                "schema_version": "1.0",
                "analysis_id": "analysis-1",
                "synthesis_id": "synthesis-1",
                "protocol": {
                    "version": "1.0",
                    "sha256": ZERO_HASH,
                    "freeze_id": "protocol-freeze-1",
                },
                "estimand_id": "estimand-1",
                "effect_measure": "risk ratio",
                "inputs": [{
                    "artifact_path": "06_analysis/input/frozen.csv",
                    "sha256": input_hash,
                    "schema_or_columns": ["study", "effect", "se"],
                    "freeze_id": "data-freeze-1",
                }],
                "dependency_policy": "One independent effect per study.",
                "missing_data_policy": "No unplanned imputation.",
                "model": {
                    "family": "random_effects",
                    "estimator": "REML",
                    "variance": "inverse_variance",
                    "heterogeneity": "tau_squared",
                    "confidence_level": 0.95,
                    "prediction_interval": True,
                    "options": {},
                },
                "software": [{"name": "R", "version": "4.5.1", "source": "R Project"}],
                "seed": 20260812,
                "planned_analyses": [{
                    "analysis_step_id": "primary-1",
                    "type": "primary",
                    "prespecified": True,
                    "parameters": {},
                    "output_ids": ["analysis-output-1"],
                }],
                "status": "verified",
                "outputs": [{
                    "output_id": "analysis-output-1",
                    "artifact_path": "06_analysis/output/result.json",
                    "sha256": output_hash,
                    "media_type": "application/json",
                }],
                "verification": {
                    "status": "passed",
                    "clean_run": True,
                    "numeric_checks": ["estimate_exact_match"],
                    "verified_by": "analysis-verifier",
                    "verified_at_utc": timestamp,
                },
                "created_at_utc": timestamp,
                "executed_at_utc": timestamp,
            }
            claim = {
                "schema_version": "1.0",
                "claim_id": "claim-1",
                "claim_type": "observation",
                "text": "The synthesis estimated a risk ratio of 0.8.",
                "scope": {
                    "synthesis_id": "synthesis-1",
                    "population": "Adults",
                    "contrast": "Intervention versus control",
                    "outcome": "Clinical event",
                    "time_window": "12 weeks",
                    "applicability_limits": [],
                },
                "certainty": {
                    "framework": "GRADE",
                    "judgment": "low",
                    "dossier_id": "certainty-1",
                },
                "allowed_verbs": ["estimated"],
                "evidence_node_ids": ["synthesis-1"],
                "assertion_ids": [],
                "analysis_output_ids": ["analysis-output-1"],
                "counterevidence_node_ids": [],
                "status": "final",
                "created_by": {"type": "model", "id": "writer", "version": "2026-08-12"},
                "verification": {
                    "status": "passed",
                    "support_check": True,
                    "numeric_check": True,
                    "scope_check": True,
                    "verified_by": "claim-verifier",
                    "verified_at_utc": timestamp,
                    "notes": "Checked against the verified analysis output.",
                },
                "human_responsibility": {
                    "status": "accepted",
                    "responsible_by": "human-lead",
                    "accepted_at_utc": timestamp,
                },
                "created_at_utc": timestamp,
                "updated_at_utc": timestamp,
            }
            for document, schema in (
                (protocol, "protocol"),
                (review_state, "review_state"),
                (dossier, "appraisal_dossier"),
                (manifest, "analysis_manifest"),
                (claim, "claim"),
            ):
                validate_document(document, schema)
            issues = inspect_method_contract(
                root,
                {"protocol": protocol, "review_state": review_state},
                {
                    "appraisal_dossier": [dossier],
                    "analysis_manifest": [manifest],
                    "claim": [claim],
                },
                gates,
            )
            self.assertEqual(issues, [])


class ProjectIntegrationTests(unittest.TestCase):
    def test_new_project_contains_valid_control_plane(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            init_result = subprocess.run(
                [sys.executable, str(SCRIPTS / "init_review.py"), "--name", "Control Plane Test", "--root", directory, "--profile", "intervention"],
                check=True,
                capture_output=True,
                text=True,
            )
            project = Path(init_result.stdout.strip())
            self.assertTrue((project / "00_admin/review_state.json").is_file())
            self.assertTrue((project / "00_admin/event_ledger.jsonl").is_file())
            self.assertTrue((project / "00_admin/provenance.sqlite3").is_file())
            self.assertTrue((project / "00_admin/credential_capabilities.json").is_file())
            self.assertTrue((project / "00_topic/landscapes/README.md").is_file())
            self.assertTrue((project / "00_topic/candidates/topic_candidates.jsonl").is_file())
            self.assertTrue((project / "00_topic/candidates/topic_proposal_batches.jsonl").is_file())
            self.assertTrue((project / "00_topic/decisions/topic_opportunity_decisions.jsonl").is_file())
            self.assertTrue((project / "00_topic/topic_decision.md").is_file())
            self.assertTrue((project / "01_protocol/review_profile.json").is_file())
            self.assertTrue((project / "01_protocol/protocol.json").is_file())
            self.assertTrue((project / "02_search/retrieval/document_state.jsonl").is_file())
            self.assertTrue((project / "03_screening/screening_assessments.jsonl").is_file())
            self.assertTrue((project / "04_extraction/lineage_edges.jsonl").is_file())
            self.assertTrue((project / "04_extraction/effect_estimates.jsonl").is_file())
            self.assertTrue((project / "05_appraisal/appraisal_dossiers.jsonl").is_file())
            self.assertTrue((project / "05_appraisal/missing_evidence_matrices.jsonl").is_file())
            self.assertTrue((project / "05_appraisal/poolability_matrices.jsonl").is_file())
            self.assertTrue((project / "06_analysis/analysis_manifests.jsonl").is_file())
            self.assertTrue((project / "07_reporting/claims.jsonl").is_file())
            self.assertTrue((project / "09_update/living_snapshots.jsonl").is_file())
            self.assertTrue((project / "09_update/living_deltas.jsonl").is_file())
            self.assertTrue((project / "10_benchmark/topic_rediscovery_cases.jsonl").is_file())
            self.assertTrue((project / "10_benchmark/topic_rediscovery_reports.jsonl").is_file())
            validation = subprocess.run(
                [sys.executable, str(SCRIPTS / "validate_project.py"), str(project)],
                check=False,
                capture_output=True,
                text=True,
            )
            report = json.loads(validation.stdout)
            self.assertEqual(validation.returncode, 0, validation.stdout + validation.stderr)
            self.assertTrue(report["valid"])

    def test_new_project_protocol_cannot_freeze_before_method_contract_is_ready(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            init_result = subprocess.run(
                [sys.executable, str(SCRIPTS / "init_review.py"), "--name", "Freeze Test", "--root", directory, "--profile", "intervention"],
                check=True,
                capture_output=True,
                text=True,
            )
            project = Path(init_result.stdout.strip())
            protocol_hash = hashlib.sha256(
                (project / "01_protocol/protocol.json").read_bytes()
            ).hexdigest()
            action = action_request(
                "freeze_protocol",
                risk_class="high",
                input_sha256=protocol_hash,
                human_approval={
                    "status": "approved",
                    "approved_by": "lead",
                    "approved_at_utc": "2026-08-12T00:00:00Z",
                    "scope": "action-001",
                },
            )
            decision = evaluate_action(action, project)
            self.assertEqual(decision.status, "abstained")
            self.assertIn("protocol_not_ready_to_freeze", decision.reason_codes)
            self.assertTrue(any("review_profile is not pinned" in reason for reason in decision.reason_codes))


if __name__ == "__main__":
    unittest.main()
