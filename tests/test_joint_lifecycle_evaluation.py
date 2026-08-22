from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
import unittest
from pathlib import Path

from metawingman.scripts.metawingman_core.joint_lifecycle_evaluation import (
    audit_joint_lifecycle_plan,
)
from metawingman.scripts.metawingman_core.schema_guard import validate_document


ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = ROOT / "research/joint-lifecycle-evaluation-plan-v1.json"
SCHEMA_PATH = ROOT / "metawingman/schemas/joint_lifecycle_evaluation_plan.schema.json"
CLI_PATH = ROOT / "metawingman/scripts/audit_joint_lifecycle_plan.py"

STAGES = [
    "topic_feasibility",
    "protocol_registration",
    "search_retrieval",
    "selection",
    "data_lineage",
    "appraisal",
    "freeze_synthesis",
    "certainty_interpretation",
    "reporting_review",
    "living_update",
]
SEEDS = [20260820, 20260821, 20260822]


def _load_plan(testcase: unittest.TestCase) -> dict:
    testcase.assertTrue(PLAN_PATH.is_file(), "preregistered plan is missing")
    return json.loads(PLAN_PATH.read_text(encoding="utf-8"))


def _resource_usage(*, provider_calls: int = 1, cost_status: str = "unknown") -> dict:
    return {
        "provider_calls": {"status": "observed", "value": provider_calls},
        "input_tokens": {"status": "observed", "value": 100},
        "output_tokens": {"status": "observed", "value": 20},
        "wall_seconds": {"status": "observed", "value": 1.5},
        "cost": {"status": cost_status, "value": None, "currency": None},
    }


def _lock_all_stage_receipts(plan: dict) -> None:
    digest = "a" * 64
    plan["stage_receipts"] = [
        {
            "case_slot_id": case["case_slot_id"],
            "arm_id": arm["arm_id"],
            "seed": seed,
            "stage_id": stage["stage_id"],
            "status": "locked",
            "checkpoint_sha256": digest,
            "input_manifest_sha256": digest,
            "output_manifest_sha256": digest,
            "resource_usage": _resource_usage(),
        }
        for case in plan["cases"]
        for arm in plan["evaluation_design"]["arms"]
        for seed in plan["seeds"]
        for stage in plan["lifecycle_stages"]
    ]
    for index, (case, closure) in enumerate(
        zip(plan["cases"], plan["family_closures"], strict=True), start=1,
    ):
        family_id = f"heldout-family-{index}"
        case["review_family_id"] = family_id
        closure.update({
            "review_family_id": family_id,
            "status": "locked",
            "training_family_manifest_sha256": digest,
            "dependency_closure_sha256": digest,
            "closed_at_utc": "2026-08-22T12:00:00Z",
        })


class JointLifecycleEvaluationTests(unittest.TestCase):
    def test_joint_plan_has_an_executable_semantic_auditor(self) -> None:
        self.assertTrue(
            callable(audit_joint_lifecycle_plan),
            "joint lifecycle semantic auditor has not been implemented",
        )

    def test_current_plan_is_schema_valid_but_scientifically_blocked(self) -> None:
        self.assertTrue(SCHEMA_PATH.is_file(), "joint lifecycle schema is missing")
        plan = _load_plan(self)
        validate_document(plan, "joint_lifecycle_evaluation_plan")
        result = audit_joint_lifecycle_plan(plan, repository_root=ROOT)
        self.assertTrue(result["schema_valid"])
        self.assertFalse(result["scientifically_ready"])
        self.assertEqual(result["status"], "blocked_not_run")
        self.assertEqual(result["stage_receipts"]["expected"], 240)
        self.assertEqual(result["stage_receipts"]["locked"], 0)
        self.assertFalse(result["published_reference_gate"]["unlock_allowed"])
        for blocker in (
            "topic_protocol_input_unlocked:temporal_evidence_landscape",
            "scientific_prerequisite_blocked:topic_signal_construct_validity",
            "scientific_prerequisite_blocked:new_confirmatory_family_freeze",
            "matched_resource_budget_unfrozen",
            "checkpoint_records_incomplete",
            "case_version_graph_unbound:confirmatory-heldout-slot-01",
            "family_closures_open",
            "stage_receipts_incomplete:0/240",
            "published_reference_unlock_gate_not_satisfied",
        ):
            self.assertIn(blocker, result["scientific_blockers"])

    def test_exact_ten_stage_order_and_three_seed_order_are_semantic_hard_gates(self) -> None:
        plan = _load_plan(self)
        plan["lifecycle_stages"][0], plan["lifecycle_stages"][1] = (
            plan["lifecycle_stages"][1], plan["lifecycle_stages"][0]
        )
        with self.assertRaisesRegex(ValueError, "canonical order"):
            audit_joint_lifecycle_plan(plan, repository_root=ROOT)

        plan = _load_plan(self)
        plan["seeds"] = list(reversed(SEEDS))
        with self.assertRaisesRegex(ValueError, "frozen seeds"):
            audit_joint_lifecycle_plan(plan, repository_root=ROOT)

    def test_missing_topic_hashes_are_blockers_not_schema_failures(self) -> None:
        plan = _load_plan(self)
        validate_document(plan, "joint_lifecycle_evaluation_plan")
        result = audit_joint_lifecycle_plan(plan, repository_root=ROOT)
        self.assertEqual(
            [item["binding_id"] for item in plan["topic_protocol_inputs"]],
            [
                "temporal_evidence_landscape",
                "topic_generation_protocol",
                "topic_signal_audit_protocol",
                "topic_scoring_protocol",
            ],
        )
        for binding_id in (
            "temporal_evidence_landscape",
            "topic_generation_protocol",
            "topic_signal_audit_protocol",
            "topic_scoring_protocol",
        ):
            self.assertIn(
                f"topic_protocol_input_unlocked:{binding_id}",
                result["scientific_blockers"],
            )
        self.assertFalse({
            "topic_candidate_set", "topic_proposal_batch", "independent_topic_signal_audit",
        } & {item["binding_id"] for item in plan["topic_protocol_inputs"]})

    def test_candidate_generator_and_both_controllers_are_real_hash_bindings(self) -> None:
        plan = _load_plan(self)
        result = audit_joint_lifecycle_plan(plan, repository_root=ROOT)
        self.assertEqual(
            result["mechanism_bindings"]["verified"],
            [
                "topic_candidate_generator",
                "topic_opportunity_controller",
                "conclusion_risk_impact_controller",
            ],
        )

        drifted = copy.deepcopy(plan)
        drifted["mechanism_bindings"][0]["cli"]["sha256"] = "0" * 64
        result = audit_joint_lifecycle_plan(drifted, repository_root=ROOT)
        self.assertIn(
            "file_hash_drift:mechanism:topic_candidate_generator:cli",
            result["scientific_blockers"],
        )

    def test_risk_impact_binding_is_the_real_action_replan_loop_not_one_shot_planner(self) -> None:
        plan = _load_plan(self)
        binding = next(
            item for item in plan["mechanism_bindings"]
            if item["binding_id"] == "conclusion_risk_impact_controller"
        )
        self.assertEqual(
            binding["cli"]["path"],
            "metawingman/scripts/run_evidence_acquisition_loop.py",
        )
        self.assertEqual(
            binding["implementation"]["path"],
            "metawingman/scripts/metawingman_core/evidence_acquisition_loop.py",
        )
        self.assertIn("--executor", binding["command_template"])
        self.assertEqual(
            hashlib.sha256((ROOT / binding["cli"]["path"]).read_bytes()).hexdigest(),
            binding["cli"]["sha256"],
        )
        self.assertEqual(
            hashlib.sha256((ROOT / binding["implementation"]["path"]).read_bytes()).hexdigest(),
            binding["implementation"]["sha256"],
        )

    def test_shared_candidate_reranking_cannot_count_as_a_direct_baseline(self) -> None:
        plan = _load_plan(self)
        plan["evaluation_design"]["candidate_comparison_scope"] = "shared_candidate_reranking"
        result = audit_joint_lifecycle_plan(plan, repository_root=ROOT)
        self.assertIn(
            "shared_candidate_reranking_is_not_direct_baseline",
            result["scientific_blockers"],
        )

    def test_case_version_graph_binds_cutoff_corpus_workbook_article_and_conclusions(self) -> None:
        plan = _load_plan(self)
        result = audit_joint_lifecycle_plan(plan, repository_root=ROOT)
        expected_roles = [
            "historical_cutoff",
            "operational_corpus",
            "screening_workbook",
            "published_article",
            "published_conclusions",
        ]
        for case in plan["cases"]:
            self.assertEqual(
                [node["role"] for node in case["version_graph"]["nodes"]],
                expected_roles,
            )
            self.assertIn(
                f"case_version_graph_unbound:{case['case_slot_id']}",
                result["scientific_blockers"],
            )
            self.assertTrue(all(node["sha256"] is None for node in case["version_graph"]["nodes"]))

    def test_published_reference_cannot_unseal_before_receipt_and_family_lock(self) -> None:
        plan = _load_plan(self)
        plan["published_reference_gate"].update({
            "state": "unsealed",
            "unsealed_at_utc": "2026-08-22T12:00:00Z",
        })
        result = audit_joint_lifecycle_plan(plan, repository_root=ROOT)
        self.assertFalse(result["published_reference_gate"]["unlock_allowed"])
        self.assertIn(
            "premature_published_reference_unseal",
            result["scientific_blockers"],
        )

    def test_exact_receipt_grid_and_family_closure_satisfy_the_unseal_gate(self) -> None:
        plan = _load_plan(self)
        _lock_all_stage_receipts(plan)
        result = audit_joint_lifecycle_plan(plan, repository_root=ROOT)
        self.assertEqual(result["stage_receipts"]["expected"], 240)
        self.assertEqual(result["stage_receipts"]["locked"], 240)
        self.assertTrue(result["published_reference_gate"]["unlock_allowed"])
        self.assertNotIn(
            "published_reference_unlock_gate_not_satisfied",
            result["scientific_blockers"],
        )

    def test_nonzero_provider_use_cannot_mark_cost_not_applicable(self) -> None:
        plan = _load_plan(self)
        receipt = {
            "case_slot_id": plan["cases"][0]["case_slot_id"],
            "arm_id": plan["evaluation_design"]["arms"][0]["arm_id"],
            "seed": plan["seeds"][0],
            "stage_id": plan["lifecycle_stages"][0]["stage_id"],
            "status": "locked",
            "checkpoint_sha256": "a" * 64,
            "input_manifest_sha256": "a" * 64,
            "output_manifest_sha256": "a" * 64,
            "resource_usage": _resource_usage(cost_status="not_applicable"),
        }
        plan["stage_receipts"] = [receipt]
        result = audit_joint_lifecycle_plan(plan, repository_root=ROOT)
        identity = (
            "confirmatory-heldout-slot-01/"
            "generic-topic__fixed-acquisition/20260820/topic_feasibility"
        )
        self.assertIn(
            f"resource_cost_not_applicable_with_provider_calls:{identity}",
            result["scientific_blockers"],
        )

    def test_innovation_ledger_is_hash_referenced_not_duplicated(self) -> None:
        plan = _load_plan(self)
        self.assertNotIn("evidence_items", plan)
        binding = plan["innovation_ledger_reference"]
        ledger_path = ROOT / binding["path"]
        self.assertEqual(
            hashlib.sha256(ledger_path.read_bytes()).hexdigest(),
            binding["sha256"],
        )
        result = audit_joint_lifecycle_plan(plan, repository_root=ROOT)
        self.assertTrue(result["innovation_ledger_reference"]["verified"])

    def test_cli_returns_machine_readable_blocked_status(self) -> None:
        self.assertTrue(CLI_PATH.is_file(), "joint lifecycle audit CLI is missing")
        completed = subprocess.run(
            [sys.executable, str(CLI_PATH), str(PLAN_PATH), "--repository-root", str(ROOT)],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 2, completed.stderr or completed.stdout)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["status"], "blocked_not_run")
        self.assertFalse(payload["scientifically_ready"])
        self.assertEqual(payload["stage_receipts"]["expected"], 240)


if __name__ == "__main__":
    unittest.main()
