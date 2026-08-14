from __future__ import annotations

import sys
import unittest
from copy import deepcopy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "metawingman/scripts"
sys.path.insert(0, str(SCRIPTS))

from metawingman_core.causal_replay import (  # noqa: E402
    CausalReplayError,
    evaluate_causal_replay,
)


TIMESTAMP = "2026-08-13T00:00:00Z"
A = "a" * 64
B = "b" * 64
C = "c" * 64
D = "d" * 64


def node(node_id: str, base: str | None, counterfactual: str | None) -> dict[str, object]:
    return {
        "node_id": node_id,
        "base_artifact_sha256": base,
        "counterfactual_artifact_sha256": counterfactual,
        "abstained": False,
        "abstention_reason": None,
    }


def counterfactual_case() -> dict[str, object]:
    expected = [
        {
            "node_id": "study:s1",
            "node_type": "study",
            "expected_status": "removed",
            "gold_basis": "dual_adjudicated",
            "anchor_ids": ["anchor:eligibility"],
        },
        {
            "node_id": "result:r1",
            "node_type": "result",
            "expected_status": "removed",
            "gold_basis": "dual_adjudicated",
            "anchor_ids": ["anchor:result"],
        },
        {
            "node_id": "claim:c1",
            "node_type": "claim",
            "expected_status": "changed",
            "gold_basis": "dual_adjudicated",
            "anchor_ids": ["anchor:claim"],
        },
    ]
    replay_nodes = [
        node("study:s1", A, None),
        node("result:r1", B, None),
        node("claim:c1", C, D),
    ]
    return {
        "schema_version": "1.0",
        "case_id": "cf-case-001",
        "review_id": "review-001",
        "review_family_id": "intervention",
        "split": "test",
        "protocol": {
            "base_version": "1.0",
            "counterfactual_version": "1.0-cf1",
            "base_sha256": A,
            "counterfactual_sha256": B,
        },
        "intervention": {
            "intervention_id": "cf1",
            "target_type": "eligibility_criterion",
            "target_id": "population-age",
            "json_pointer": "/criteria/population/maximum_age",
            "operation": "replace",
            "base_value": 75,
            "counterfactual_value": 65,
            "single_change_verified": True,
            "rationale": "Tests propagation of one frozen population criterion.",
        },
        "boundary": {
            "run_context": "historical_reconstruction",
            "source_corpus_sha256": C,
            "source_corpus_frozen": True,
            "answers_sealed": True,
            "post_cutoff_evidence_sealed": True,
            "protocol_variants_frozen_before_run": True,
            "leakage_audit": "passed",
            "notes": "Fixture boundary only.",
        },
        "expected_node_deltas": expected,
        "observed_node_deltas": [
            node("study:s1", A, A),
            node("result:r1", B, B),
            node("claim:c1", C, C),
        ],
        "event_trace": [
            {
                "event_id": "screen:e1",
                "sequence": 1,
                "stage": 3,
                "verification_status": "failed",
                "affected_node_ids": ["study:s1", "result:r1"],
                "predecessor_event_ids": [],
                "output_sha256": A,
            },
            {
                "event_id": "analyse:e2",
                "sequence": 2,
                "stage": 6,
                "verification_status": "passed",
                "affected_node_ids": ["result:r1"],
                "predecessor_event_ids": ["screen:e1"],
                "output_sha256": B,
            },
            {
                "event_id": "claim:e3",
                "sequence": 3,
                "stage": 8,
                "verification_status": "failed",
                "affected_node_ids": ["claim:c1"],
                "predecessor_event_ids": ["analyse:e2"],
                "output_sha256": C,
            },
        ],
        "replay_interventions": [
            {
                "replay_id": "replay-order-a",
                "event_id": "screen:e1",
                "event_order_variant": "canonical",
                "replacement_source": "adjudicated",
                "replacement_verified": True,
                "replacement_output_sha256": D,
                "downstream_replay_complete": True,
                "resulting_node_deltas": replay_nodes,
            },
            {
                "replay_id": "replay-order-b",
                "event_id": "screen:e1",
                "event_order_variant": "independent-branches-reversed",
                "replacement_source": "adjudicated",
                "replacement_verified": True,
                "replacement_output_sha256": D,
                "downstream_replay_complete": True,
                "resulting_node_deltas": deepcopy(replay_nodes),
            },
        ],
        "created_at_utc": TIMESTAMP,
    }


class CounterfactualProtocolReplayTests(unittest.TestCase):
    def test_full_recovery_supports_stable_event_responsibility(self) -> None:
        report = evaluate_causal_replay(counterfactual_case(), created_at_utc=TIMESTAMP)
        self.assertTrue(report["valid_case"])
        self.assertEqual(report["protocol_adherence_status"], "failed")
        self.assertEqual(report["earliest_candidate_event"]["event_id"], "screen:e1")
        self.assertEqual(report["causal_attribution_status"], "supported")
        self.assertEqual(report["stability_status"], "stable")
        self.assertEqual(report["node_metrics"]["delta_accuracy"], 0)
        self.assertTrue(all(item["recovery_rate"] == 1 for item in report["replay_results"]))

    def test_correct_protocol_delta_needs_no_replay(self) -> None:
        case = counterfactual_case()
        case["observed_node_deltas"] = deepcopy(
            case["replay_interventions"][0]["resulting_node_deltas"]
        )
        case["event_trace"] = []
        case["replay_interventions"] = []
        report = evaluate_causal_replay(case, created_at_utc=TIMESTAMP)
        self.assertEqual(report["protocol_adherence_status"], "passed")
        self.assertEqual(report["causal_attribution_status"], "not_needed")
        self.assertEqual(report["node_metrics"]["delta_accuracy"], 1)

    def test_partial_replay_is_not_full_attribution(self) -> None:
        case = counterfactual_case()
        for replay in case["replay_interventions"]:
            replay["resulting_node_deltas"] = [node("study:s1", A, None)]
        report = evaluate_causal_replay(case, created_at_utc=TIMESTAMP)
        self.assertEqual(report["causal_attribution_status"], "partial")
        self.assertEqual(report["stability_status"], "stable")
        self.assertAlmostEqual(report["replay_results"][0]["recovery_rate"], 1 / 3)

    def test_single_complete_replay_does_not_establish_order_stability(self) -> None:
        case = counterfactual_case()
        case["replay_interventions"] = case["replay_interventions"][:1]
        report = evaluate_causal_replay(case, created_at_utc=TIMESTAMP)
        self.assertEqual(report["causal_attribution_status"], "partial")
        self.assertEqual(report["stability_status"], "not_tested")
        self.assertIn("event_order_stability_not_tested", report["reason_codes"])

    def test_order_variant_disagreement_is_unstable(self) -> None:
        case = counterfactual_case()
        case["replay_interventions"][1]["resulting_node_deltas"] = [
            node("study:s1", A, None)
        ]
        report = evaluate_causal_replay(case, created_at_utc=TIMESTAMP)
        self.assertEqual(report["causal_attribution_status"], "partial")
        self.assertEqual(report["stability_status"], "unstable")

    def test_unsealed_historical_answers_invalidate_attribution(self) -> None:
        case = counterfactual_case()
        case["boundary"]["answers_sealed"] = False
        report = evaluate_causal_replay(case, created_at_utc=TIMESTAMP)
        self.assertFalse(report["valid_case"])
        self.assertEqual(report["protocol_adherence_status"], "invalid")
        self.assertEqual(report["causal_attribution_status"], "invalid")
        self.assertIn("historical_answers_not_sealed", report["reason_codes"])

    def test_non_prior_predecessor_is_rejected(self) -> None:
        case = counterfactual_case()
        case["event_trace"][0]["predecessor_event_ids"] = ["analyse:e2"]
        with self.assertRaises(CausalReplayError):
            evaluate_causal_replay(case, created_at_utc=TIMESTAMP)

    def test_duplicate_order_variant_is_rejected(self) -> None:
        case = counterfactual_case()
        case["replay_interventions"][1]["event_order_variant"] = "canonical"
        with self.assertRaises(CausalReplayError):
            evaluate_causal_replay(case, created_at_utc=TIMESTAMP)

    def test_real_gold_node_requires_evidence_anchor(self) -> None:
        case = counterfactual_case()
        case["expected_node_deltas"][0]["anchor_ids"] = []
        with self.assertRaises(CausalReplayError):
            evaluate_causal_replay(case, created_at_utc=TIMESTAMP)

    def test_abstention_requires_a_reason(self) -> None:
        case = counterfactual_case()
        case["observed_node_deltas"][0].update({
            "abstained": True,
            "abstention_reason": None,
        })
        with self.assertRaises(CausalReplayError):
            evaluate_causal_replay(case, created_at_utc=TIMESTAMP)


if __name__ == "__main__":
    unittest.main()
