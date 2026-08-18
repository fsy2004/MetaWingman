"""Tests for the rule-based appraisal step verifier (R6)."""
from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "metawingman" / "scripts"))

from verify_appraisal_steps import verify_appraisal_steps  # noqa: E402


def make_dossier() -> dict:
    return {
        "schema_version": "1.0",
        "dossier_id": "dossier-test-1",
        "dossier_type": "risk_of_bias",
        "target": {"type": "study", "id": "s1", "study_id": "s1", "result_id": None, "synthesis_id": None},
        "framework": {
            "name": "RoB 2",
            "version": "2019",
            "organization": "Cochrane",
            "source_url": "https://www.riskofbias.info",
            "verified_at_utc": "2026-08-18T00:00:00Z",
            "adapter_version": "1.0",
        },
        "evidence_node_ids": ["n1"],
        "domains": [
            {
                "domain_id": "d1",
                "label": "randomization",
                "signaling_questions": [
                    {"question_id": "q1", "question": "was allocation concealed?", "answer": "yes", "anchor_ids": ["a1"], "rationale": "report states concealed allocation"},
                ],
                "supporting_anchor_ids": ["a1"],
                "counterevidence_anchor_ids": [],
                "proposal": "low risk",
                "rationale": "anchored judgment",
            }
        ],
        "overall_proposal": {"actor_id": "ai", "judgment": "low risk", "rationale": "single low-risk domain"},
        "opposition": {"actor_id": "devil", "counter_judgment": "some concerns", "anchor_ids": ["a2"], "rationale": "selective reporting possible"},
        "judge_recommendation": {"actor_id": "judge", "judgment": "low risk", "reason_codes": ["r1"], "confidence": 0.9, "abstained": False},
        "missing_information": ["protocol unavailable"],
        "status": "final",
        "final_judgment": "low risk",
        "human_signature": {"status": "approved", "signed_by": "human", "signed_at_utc": "2026-08-18T00:00:00Z", "notes": ""},
        "created_at_utc": "2026-08-18T00:00:00Z",
        "updated_at_utc": "2026-08-18T00:00:00Z",
    }


class AppraisalStepVerifierTests(unittest.TestCase):
    def test_complete_dossier_passes_all_steps(self) -> None:
        report = verify_appraisal_steps(make_dossier())
        self.assertEqual(report["summary"]["steps_total"], report["summary"]["steps_passed"], report)
        self.assertFalse(report["summary"]["abstain_required"])
        self.assertFalse(report["summary"]["human_window_required"])

    def test_unanchored_signal_fails_and_abstains(self) -> None:
        dossier = make_dossier()
        dossier["domains"][0]["signaling_questions"][0]["anchor_ids"] = []
        report = verify_appraisal_steps(dossier)
        self.assertFalse(any(s["id"] == "signaling_anchors" and s["passed"] for s in report["steps"]))
        self.assertTrue(report["summary"]["abstain_required"])

    def test_unanswered_signal_cannot_exist_at_dossier_layer(self) -> None:
        # The dossier schema enforces the answer enum, so this state is
        # rejected before the step verifier runs.
        dossier = make_dossier()
        dossier["domains"][0]["signaling_questions"][0]["answer"] = ""
        with self.assertRaises(Exception):
            verify_appraisal_steps(dossier)

    def test_unknown_framework_flags_step(self) -> None:
        dossier = make_dossier()
        dossier["framework"]["name"] = "made-up-tool"
        report = verify_appraisal_steps(dossier)
        self.assertFalse(any(s["id"] == "framework_known" and s["passed"] for s in report["steps"]))

    def test_pending_human_signature_requires_window(self) -> None:
        dossier = make_dossier()
        dossier["status"] = "ready_for_adjudication"
        dossier["human_signature"]["status"] = "pending"
        dossier["final_judgment"] = None
        report = verify_appraisal_steps(dossier)
        self.assertTrue(report["summary"]["human_window_required"])
        self.assertTrue(report["summary"]["abstain_required"])

    def test_missing_final_judgment_abstains(self) -> None:
        dossier = make_dossier()
        dossier["status"] = "ready_for_adjudication"
        dossier["final_judgment"] = None
        report = verify_appraisal_steps(dossier)
        self.assertTrue(report["summary"]["abstain_required"])


if __name__ == "__main__":
    unittest.main()
