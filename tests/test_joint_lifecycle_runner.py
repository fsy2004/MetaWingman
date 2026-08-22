from __future__ import annotations

import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from metawingman.scripts.metawingman_core.joint_lifecycle_runner import (
    AtomicStageBudgetMeter,
    JointLifecycleRunError,
    MeteredModelProvider,
    assemble_joint_lifecycle_receipts,
    execute_joint_lifecycle_slot,
)
from metawingman.scripts.metawingman_core.model_provider import ProviderResult
from metawingman.scripts.metawingman_core.schema_guard import validate_document


ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = ROOT / "research/joint-lifecycle-evaluation-plan-v1.json"
RUNNER_PATH = ROOT / "metawingman/scripts/run_joint_lifecycle_slot.py"
STAGES = (
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
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def _relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def _prepare_plan(root: Path) -> tuple[dict, Path, Path, Path]:
    plan = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
    artifact = root / "operational.json"
    checkpoint = root / "checkpoint.bin"
    adapter_path = root / "stage_adapter.py"
    config_path = root / "stage_config.json"
    _write_json(artifact, {"operational": True})
    checkpoint.write_bytes(b"checkpoint")
    adapter_path.write_text("# frozen stage adapter\n", encoding="utf-8")
    _write_json(config_path, {"mode": "test", "published_reference_access": False})

    plan["plan_status"] = "ready_to_execute"
    plan["innovation_ledger_reference"]["sha256"] = _sha(
        ROOT / plan["innovation_ledger_reference"]["path"]
    )
    for binding in plan["topic_protocol_inputs"]:
        binding.update({
            "status": "locked",
            "path": _relative(artifact),
            "sha256": _sha(artifact),
        })
    for prerequisite in plan["scientific_prerequisites"]:
        prerequisite["status"] = "satisfied"
        prerequisite["basis"] = "test fixture satisfies the frozen prerequisite"
    plan["evaluation_design"]["matched_budget"].update({
        "status": "frozen",
        "max_provider_calls": 20,
        "max_input_tokens": 2000,
        "max_output_tokens": 1000,
        "wall_seconds": 60,
    })
    for arm in plan["evaluation_design"]["arms"]:
        arm["runner_binding"] = {
            "status": "locked",
            "path": "metawingman/scripts/run_joint_lifecycle_slot.py",
            "sha256": _sha(RUNNER_PATH),
        }
    for record in plan["checkpoint_records"]:
        record.update({
            "status": "locked",
            "artifact_path": _relative(checkpoint),
            "artifact_sha256": _sha(checkpoint),
            "training_manifest_sha256": "1" * 64,
            "family_manifest_sha256": "2" * 64,
        })
    for index, case in enumerate(plan["cases"], start=1):
        family = f"test-family-{index}"
        case.update({
            "case_id": f"test-case-{index}",
            "review_family_id": family,
            "admission_status": "admitted",
            "profile_strata": [f"profile-{index}"],
            "authority_status": "verified_primary",
            "representativeness_status": "verified",
            "prior_target_exposure_status": "none",
        })
        case["version_graph"]["status"] = "locked"
        for node in case["version_graph"]["nodes"]:
            if node["role"] == "historical_cutoff":
                node.update({
                    "status": "operational_locked",
                    "path": _relative(artifact),
                    "sha256": _sha(artifact),
                    "cutoff_value": "2020-01-01",
                    "cutoff_exact": True,
                })
            elif node["role"] in {"operational_corpus", "screening_workbook"}:
                node.update({
                    "status": "operational_locked",
                    "path": _relative(artifact),
                    "sha256": _sha(artifact),
                })
            else:
                node.update({
                    "status": "sealed_locked",
                    "path": None,
                    "sha256": str(index) * 64,
                })
        closure = plan["family_closures"][index - 1]
        closure.update({
            "review_family_id": family,
            "status": "locked",
            "training_family_manifest_sha256": "3" * 64,
            "dependency_closure_sha256": "4" * 64,
            "closed_at_utc": "2026-08-22T12:00:00Z",
        })
    plan["declared_blockers"] = []
    plan_path = root / "ready-plan.json"
    _write_json(plan_path, plan)
    return plan, plan_path, adapter_path, config_path


def _run_spec(plan_path: Path, adapter_path: Path, config_path: Path) -> dict:
    return {
        "schema_version": "1.0",
        "execution_id": "joint-slot-test-1",
        "evaluation_plan": {"path": _relative(plan_path), "sha256": _sha(plan_path)},
        "case_slot_id": "confirmatory-heldout-slot-01",
        "arm_id": "generic-topic__fixed-acquisition",
        "seed": 20260820,
        "created_at_utc": "2026-08-22T12:00:00Z",
        "stages": [
            {
                "ordinal": ordinal,
                "stage_id": stage_id,
                "adapter": {
                    "module_function": "tests.test_joint_lifecycle_runner:stage_adapter",
                    "path": _relative(adapter_path),
                    "sha256": _sha(adapter_path),
                },
                "config": {"path": _relative(config_path), "sha256": _sha(config_path)},
                "budget_allocation": {
                    "max_provider_calls": 2,
                    "max_input_tokens": 200,
                    "max_output_tokens": 100,
                    "wall_seconds": 5,
                },
            }
            for ordinal, stage_id in enumerate(STAGES)
        ],
    }


def stage_adapter(request: dict, meter: object) -> dict:
    stage_id = request["stage_id"]
    artifact = Path(request["stage_output_dir"]) / "state.json"
    _write_json(artifact, {
        "stage_id": stage_id,
        "previous_output_manifest_sha256": request["previous_output_manifest_sha256"],
    })
    required_checks = {
        "topic_feasibility": [
            "direct_candidate_generation",
            (
                "decision_opportunity_control"
                if request["topic_opportunity_control"]
                else "generic_candidate_generation"
            ),
        ],
        "protocol_registration": ["protocol_frozen"],
        "search_retrieval": [
            (
                "risk_impact_action_execute_replan"
                if request["conclusion_risk_impact_control"]
                else "fixed_acquisition"
            ),
            "search_reproducible",
        ],
        "selection": ["selection_complete"],
        "data_lineage": ["report_study_result_lineage_complete"],
        "appraisal": ["appraisal_and_missing_evidence_complete"],
        "freeze_synthesis": ["analysis_freeze_and_synthesis_complete"],
        "certainty_interpretation": ["certainty_and_claims_complete"],
        "reporting_review": ["reporting_and_review_complete"],
        "living_update": ["living_update_plan_complete"],
    }[stage_id]
    return {
        "schema_version": "1.0",
        "stage_id": stage_id,
        "status": "completed",
        "state_artifact_id": "stage_state",
        "artifacts": [{
            "artifact_id": "stage_state",
            "path": str(artifact),
            "sha256": _sha(artifact),
            "media_type": "application/json",
            "role": "stage_state",
        }],
        "scientific_checks": [
            {
                "check_id": check_id,
                "status": "passed",
                "evidence_artifact_ids": ["stage_state"],
            }
            for check_id in required_checks
        ],
        "terminal_reason": None,
    }


class JointLifecycleRunnerTests(unittest.TestCase):
    def test_model_provider_wrapper_meters_each_call_before_network_delegate(self) -> None:
        events: list[str] = []

        class FakeProvider:
            credential_source = "test-secret-store"

            def chat(self, messages: list[dict], **kwargs: object) -> ProviderResult:
                events.append("delegate_called")
                return ProviderResult(
                    provider="fake", model="deepseek-v4-flash", finish_reason="stop",
                    content="{}", content_sha256=hashlib.sha256(b"{}").hexdigest(),
                    prompt_tokens=7, completion_tokens=3, total_tokens=10,
                    reasoning_tokens=None, system_fingerprint=None,
                    credential_source=self.credential_source,
                )

        meter = AtomicStageBudgetMeter({
            "max_provider_calls": 1, "max_input_tokens": 20,
            "max_output_tokens": 10, "wall_seconds": 5,
        })
        wrapped = MeteredModelProvider(
            FakeProvider(), meter, max_input_tokens_per_call=20,
        )
        result = wrapped.chat([{"role": "user", "content": "hello"}], max_tokens=10)
        self.assertEqual(result.content, "{}")
        self.assertEqual(events, ["delegate_called"])
        usage = meter.resource_usage(0.1)
        self.assertEqual(usage["provider_calls"]["value"], 1)
        self.assertEqual(usage["input_tokens"]["value"], 7)
        self.assertEqual(usage["cost"]["status"], "unknown")

    def test_executes_exact_ten_stage_chain_and_emits_locked_receipts(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            root = Path(tmp)
            plan, plan_path, adapter_path, config_path = _prepare_plan(root)
            spec = _run_spec(plan_path, adapter_path, config_path)
            validate_document(spec, "joint_lifecycle_slot_execution")
            result = execute_joint_lifecycle_slot(
                spec, repository_root=ROOT, output_root=root / "outputs",
                adapter_loader=lambda _: stage_adapter,
            )
            validate_document(result, "joint_lifecycle_slot_result")
            self.assertEqual(result["status"], "completed")
            self.assertEqual([item["stage_id"] for item in result["stage_results"]], list(STAGES))
            self.assertTrue(all(item["receipt"]["status"] == "locked" for item in result["stage_results"]))
            for index in range(1, len(result["stage_results"])):
                current = json.loads(Path(result["stage_results"][index]["input_manifest_path"]).read_text())
                self.assertEqual(
                    current["previous_output_manifest_sha256"],
                    result["stage_results"][index - 1]["output_manifest_sha256"],
                )
            self.assertFalse(result["published_reference_accessed"])

    def test_reference_locator_in_config_fails_before_adapter_execution(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            root = Path(tmp)
            _, plan_path, adapter_path, config_path = _prepare_plan(root)
            _write_json(config_path, {"published_expert_reference": "sealed/reference.bin"})
            spec = _run_spec(plan_path, adapter_path, config_path)
            calls: list[str] = []
            with self.assertRaisesRegex(JointLifecycleRunError, "sealed reference"):
                execute_joint_lifecycle_slot(
                    spec, repository_root=ROOT, output_root=root / "outputs",
                    adapter_loader=lambda _: lambda request, meter: calls.append(request["stage_id"]),
                )
            self.assertEqual(calls, [])

    def test_claim_only_blocker_does_not_prevent_a_scoped_execution(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            root = Path(tmp)
            plan, plan_path, adapter_path, config_path = _prepare_plan(root)
            claim_only = next(
                item for item in plan["scientific_prerequisites"]
                if item["required_for"] == "confirmatory_claim"
            )
            claim_only["status"] = "blocked"
            claim_only["basis"] = "claim remains bounded while the blind run is still executable"
            _write_json(plan_path, plan)
            spec = _run_spec(plan_path, adapter_path, config_path)
            result = execute_joint_lifecycle_slot(
                spec, repository_root=ROOT, output_root=root / "outputs",
                adapter_loader=lambda _: stage_adapter,
            )
            self.assertEqual(result["status"], "completed")

            execution_blocked = copy.deepcopy(plan)
            both = next(
                item for item in execution_blocked["scientific_prerequisites"]
                if item["required_for"] == "both"
            )
            both["status"] = "blocked"
            _write_json(plan_path, execution_blocked)
            blocked_spec = _run_spec(plan_path, adapter_path, config_path)
            with self.assertRaisesRegex(JointLifecycleRunError, "execution prerequisites"):
                execute_joint_lifecycle_slot(
                    blocked_spec, repository_root=ROOT, output_root=root / "blocked-outputs",
                    adapter_loader=lambda _: stage_adapter,
                )

    def test_budget_meter_blocks_second_call_before_provider_side_effect(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            root = Path(tmp)
            _, plan_path, adapter_path, config_path = _prepare_plan(root)
            spec = _run_spec(plan_path, adapter_path, config_path)
            spec["stages"][0]["budget_allocation"]["max_provider_calls"] = 1
            provider_side_effects: list[int] = []

            def overspending_adapter(request: dict, meter: object) -> dict:
                lease = meter.before_provider_call(max_input_tokens=10, max_output_tokens=10)
                provider_side_effects.append(1)
                meter.after_provider_call(
                    lease, input_tokens=4, output_tokens=3,
                    cost_status="unknown", cost_value=None, currency=None,
                )
                meter.before_provider_call(max_input_tokens=10, max_output_tokens=10)
                provider_side_effects.append(2)
                return stage_adapter(request, meter)

            result = execute_joint_lifecycle_slot(
                spec, repository_root=ROOT, output_root=root / "outputs",
                adapter_loader=lambda _: overspending_adapter,
            )
            self.assertEqual(provider_side_effects, [1])
            self.assertEqual(result["status"], "failed")
            self.assertEqual(result["stage_results"][0]["receipt"]["status"], "failed")
            self.assertEqual(len(result["stage_results"]), 1)

    def test_unsettled_provider_lease_cannot_be_reported_as_zero_usage(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            root = Path(tmp)
            _, plan_path, adapter_path, config_path = _prepare_plan(root)
            spec = _run_spec(plan_path, adapter_path, config_path)

            def interrupted_adapter(request: dict, meter: object) -> dict:
                meter.before_provider_call(max_input_tokens=10, max_output_tokens=10)
                raise RuntimeError("provider transport interrupted after reservation")

            with self.assertRaisesRegex(JointLifecycleRunError, "unsettled provider"):
                execute_joint_lifecycle_slot(
                    spec, repository_root=ROOT, output_root=root / "outputs",
                    adapter_loader=lambda _: interrupted_adapter,
                )

    def test_abstention_stops_downstream_stages_and_is_not_locked(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            root = Path(tmp)
            _, plan_path, adapter_path, config_path = _prepare_plan(root)
            spec = _run_spec(plan_path, adapter_path, config_path)

            def abstaining_adapter(request: dict, meter: object) -> dict:
                value = stage_adapter(request, meter)
                value["status"] = "abstained"
                value["terminal_reason"] = "insufficient_source_coverage"
                return value

            result = execute_joint_lifecycle_slot(
                spec, repository_root=ROOT, output_root=root / "outputs",
                adapter_loader=lambda _: abstaining_adapter,
            )
            self.assertEqual(result["status"], "abstained")
            self.assertEqual(len(result["stage_results"]), 1)
            self.assertEqual(result["stage_results"][0]["receipt"]["status"], "abstained")

    def test_stage_cannot_lock_without_its_scientific_completion_checks(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            root = Path(tmp)
            _, plan_path, adapter_path, config_path = _prepare_plan(root)
            spec = _run_spec(plan_path, adapter_path, config_path)

            def shape_only_adapter(request: dict, meter: object) -> dict:
                value = stage_adapter(request, meter)
                value["scientific_checks"] = [{
                    "check_id": "shape_only",
                    "status": "passed",
                    "evidence_artifact_ids": ["stage_state"],
                }]
                return value

            result = execute_joint_lifecycle_slot(
                spec, repository_root=ROOT, output_root=root / "outputs",
                adapter_loader=lambda _: shape_only_adapter,
            )
            self.assertEqual(result["status"], "failed")
            self.assertIn("required scientific checks", result["terminal_reason"])

    def test_adapter_or_config_hash_drift_is_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            root = Path(tmp)
            _, plan_path, adapter_path, config_path = _prepare_plan(root)
            spec = _run_spec(plan_path, adapter_path, config_path)
            spec["stages"][3]["adapter"]["sha256"] = "0" * 64
            with self.assertRaisesRegex(JointLifecycleRunError, "hash drift"):
                execute_joint_lifecycle_slot(
                    spec, repository_root=ROOT, output_root=root / "outputs",
                    adapter_loader=lambda _: stage_adapter,
                )

    def test_slot_results_assemble_into_a_derived_plan_without_unsealing(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            root = Path(tmp)
            _, plan_path, adapter_path, config_path = _prepare_plan(root)
            spec = _run_spec(plan_path, adapter_path, config_path)
            result = execute_joint_lifecycle_slot(
                spec, repository_root=ROOT, output_root=root / "outputs",
                adapter_loader=lambda _: stage_adapter,
            )
            result_path = root / "slot-result.json"
            _write_json(result_path, result)
            derived = assemble_joint_lifecycle_receipts(
                plan_path, [result_path], repository_root=ROOT,
            )
            validate_document(derived, "joint_lifecycle_evaluation_plan")
            self.assertEqual(derived["plan_status"], "execution_in_progress")
            self.assertEqual(len(derived["stage_receipts"]), 10)
            self.assertTrue(all(item["status"] == "locked" for item in derived["stage_receipts"]))
            self.assertEqual(derived["published_reference_gate"]["state"], "sealed")
            self.assertIsNone(derived["published_reference_gate"]["unsealed_at_utc"])

    def test_receipt_assembly_rehashes_manifests_and_rejects_duplicates(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            root = Path(tmp)
            _, plan_path, adapter_path, config_path = _prepare_plan(root)
            spec = _run_spec(plan_path, adapter_path, config_path)
            result = execute_joint_lifecycle_slot(
                spec, repository_root=ROOT, output_root=root / "outputs",
                adapter_loader=lambda _: stage_adapter,
            )
            result_path = root / "slot-result.json"
            _write_json(result_path, result)
            with self.assertRaisesRegex(JointLifecycleRunError, "duplicate slot"):
                assemble_joint_lifecycle_receipts(
                    plan_path, [result_path, result_path], repository_root=ROOT,
                )

            input_manifest = Path(result["stage_results"][0]["input_manifest_path"])
            input_manifest.write_text("{}\n", encoding="utf-8")
            with self.assertRaisesRegex(JointLifecycleRunError, "manifest hash drift"):
                assemble_joint_lifecycle_receipts(
                    plan_path, [result_path], repository_root=ROOT,
                )


if __name__ == "__main__":
    unittest.main()
