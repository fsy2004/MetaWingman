from __future__ import annotations

import copy
import hashlib
import tempfile
import unittest
from pathlib import Path

from metawingman.scripts.metawingman_core.evidence_acquisition import EvidenceAcquisitionError
from metawingman.scripts.metawingman_core.evidence_acquisition_loop import (
    execute_evidence_acquisition_loop,
)


TIMESTAMP = "2026-08-22T00:00:00Z"


def state(*, state_id: str = "risk-state-0", risk: float = 0.4) -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "state_id": state_id,
        "protocol_version": "protocol-locked-v1",
        "criterion_states": [{
            "criterion_id": "critical-outcome",
            "critical": True,
            "calibration_status": "calibrated",
            "residual_omission_risk": risk,
            "downstream_claim_impact": 0.9,
            "hard_negative_error_rate": 0.01,
            "unresolved_records": 1 if risk > 0.05 else 0,
            "independent_source_count": 1 if risk > 0.05 else 3,
            "evidence_basis": "Frozen held-out calibration and source audit.",
        }],
        "global_signals": {
            "run_context": "historical_reconstruction",
            "known_item_set_frozen": True,
            "known_item_recall": 0.8 if risk > 0.05 else 1.0,
            "source_family_count": 1 if risk > 0.05 else 3,
            "temporal_boundary_status": "sealed",
            "leakage_audit": "passed",
        },
        "thresholds": {
            "known_item_recall_floor": 0.95,
            "residual_omission_risk_ceiling": 0.05,
            "downstream_claim_impact_ceiling": 0.25,
            "hard_negative_error_ceiling": 0.05,
            "minimum_independent_sources": 2,
            "minimum_source_families": 2,
            "max_selected_actions": 1,
        },
        "candidate_actions": [{
            "action_id": "retrieve-priority-fulltext",
            "action_type": "retrieve_full_text",
            "target_criterion_ids": ["critical-outcome"],
            "expected_risk_reduction": 0.8,
            "expected_claim_impact": 0.9,
            "source_family_gain": 1,
            "estimated_cost_units": 1.0,
            "estimate_basis": "calibrated",
            "legally_available": True,
            "credential_status": "not_required",
            "rationale": "Resolve the highest-impact missing full text.",
        }],
        "created_at_utc": TIMESTAMP,
    }


def loop_plan(root: Path, *, mode: str = "evaluation") -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "loop_id": "claim-risk-loop-001",
        "mode": mode,
        "max_iterations": 3,
        "artifact_root": str(root),
        "budget": {
            "max_actions": 3,
            "max_estimated_cost_units": 3.0,
            "max_model_calls": 3,
            "max_input_tokens": 3000,
            "max_output_tokens": 1000,
            "max_wall_seconds": 60.0,
            "cost_accounting_policy": "report_unknown",
        },
        "stop_authority": {
            "actor_id": "preregistered-evaluation-actor",
            "preregistration_sha256": "a" * 64,
            "signature_status": "verified" if mode == "evaluation" else "pending",
        },
    }


class EvidenceAcquisitionLoopTests(unittest.TestCase):
    def test_selected_action_is_executed_then_risk_is_replanned_to_stop(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            artifact = root / "retrieval.json"
            artifact.write_text("{}\n", encoding="utf-8")

            def executor(action: dict, current: dict) -> dict:
                next_state = state(state_id="risk-state-1", risk=0.01)
                return {
                    "action_id": action["action_id"],
                    "next_state": next_state,
                    "risk_state_recomputed": True,
                    "semantic_verification_status": "passed",
                    "artifact": {
                        "path": str(artifact),
                        "sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
                    },
                    "usage": {
                        "model_calls": 1,
                        "input_tokens": 700,
                        "output_tokens": 120,
                        "wall_seconds": 2.5,
                        "cost_status": "unknown",
                        "cost_value": None,
                    },
                }

            result = execute_evidence_acquisition_loop(
                state(), loop_plan(root), executor, created_at_utc=TIMESTAMP
            )
            self.assertEqual(result["status"], "completed")
            self.assertEqual(result["terminal_reason"], "stop_authority_verified")
            self.assertEqual(len(result["action_receipts"]), 1)
            self.assertEqual([item["status"] for item in result["decisions"]], ["continue", "stop_candidate"])
            self.assertEqual(result["usage_totals"]["model_calls"], 1)
            self.assertEqual(result["usage_totals"]["cost_status"], "unknown")
            self.assertTrue(result["full_risk_impact_controller_instantiated"])

    def test_budget_is_checked_before_executor_call(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            plan = loop_plan(Path(tmp))
            plan["budget"]["max_estimated_cost_units"] = 0.5
            calls = []

            def executor(action: dict, current: dict) -> dict:
                calls.append(action)
                raise AssertionError("executor must not be called")

            result = execute_evidence_acquisition_loop(
                state(), plan, executor, created_at_utc=TIMESTAMP
            )
            self.assertEqual(result["status"], "abstained")
            self.assertEqual(result["terminal_reason"], "budget_precheck_failed")
            self.assertEqual(calls, [])

    def test_executor_cannot_return_unchanged_or_unverified_risk_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            artifact = root / "receipt.json"
            artifact.write_text("{}\n", encoding="utf-8")

            def executor(action: dict, current: dict) -> dict:
                return {
                    "action_id": action["action_id"],
                    "next_state": copy.deepcopy(current),
                    "risk_state_recomputed": False,
                    "semantic_verification_status": "not_applicable",
                    "artifact": {"path": str(artifact), "sha256": hashlib.sha256(artifact.read_bytes()).hexdigest()},
                    "usage": {"model_calls": 0, "input_tokens": 0, "output_tokens": 0, "wall_seconds": 0.1, "cost_status": "not_applicable", "cost_value": None},
                }

            with self.assertRaisesRegex(EvidenceAcquisitionError, "recomputed|change"):
                execute_evidence_acquisition_loop(
                    state(), loop_plan(root), executor, created_at_utc=TIMESTAMP
                )

    def test_receipt_artifact_hash_and_root_are_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as outside:
            root = Path(tmp)
            artifact = Path(outside) / "outside.json"
            artifact.write_text("{}\n", encoding="utf-8")

            def executor(action: dict, current: dict) -> dict:
                return {
                    "action_id": action["action_id"],
                    "next_state": state(state_id="risk-state-1", risk=0.01),
                    "risk_state_recomputed": True,
                    "semantic_verification_status": "passed",
                    "artifact": {"path": str(artifact), "sha256": "0" * 64},
                    "usage": {"model_calls": 0, "input_tokens": 0, "output_tokens": 0, "wall_seconds": 0.1, "cost_status": "not_applicable", "cost_value": None},
                }

            with self.assertRaisesRegex(EvidenceAcquisitionError, "artifact"):
                execute_evidence_acquisition_loop(
                    state(), loop_plan(root), executor, created_at_utc=TIMESTAMP
                )

    def test_production_stop_remains_pending_without_human_signature(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = execute_evidence_acquisition_loop(
                state(risk=0.01), loop_plan(Path(tmp), mode="production"),
                lambda action, current: {}, created_at_utc=TIMESTAMP,
            )
            self.assertEqual(result["status"], "awaiting_stop_authority")
            self.assertEqual(result["terminal_reason"], "stop_authority_pending")
            self.assertFalse(result["full_risk_impact_controller_instantiated"])


if __name__ == "__main__":
    unittest.main()
