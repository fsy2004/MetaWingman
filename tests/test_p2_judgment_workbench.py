from __future__ import annotations

import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = REPO_ROOT / "metawingman" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from metawingman_core.claim_compiler import ClaimCompileError, compile_claim  # noqa: E402
from metawingman_core.judgment_workbench import (  # noqa: E402
    JudgmentWorkbenchError,
    build_appraisal_dossier,
    build_missing_evidence_matrix,
    load_appraisal_adapter,
    locate_interval_against_threshold,
)
from metawingman_core.poolability import build_poolability_matrix  # noqa: E402


TIMESTAMP = "2026-08-13T00:00:00Z"


def complete_rob2_candidate() -> dict[str, object]:
    adapter = load_appraisal_adapter(
        REPO_ROOT / "metawingman/references/appraisal-adapters/rob2-2019.json"
    )
    domains = []
    for definition in adapter["domains"]:
        questions = [
            {
                "question_id": question_id,
                "question": f"Official question {question_id}; consult pinned form.",
                "answer": "yes",
                "anchor_ids": [f"anchor-{question_id}"],
                "rationale": "The anchored methods text supports this answer.",
            }
            for question_id in definition["signaling_question_ids"]
        ]
        domains.append({
            "domain_id": definition["domain_id"],
            "signaling_questions": questions,
            "supporting_anchor_ids": [f"anchor-{definition['domain_id']}"],
            "counterevidence_anchor_ids": [],
            "proposal": "low risk",
            "rationale": "The signaling answers support the proposal.",
        })
    return {
        "dossier_id": "rob2-result-1",
        "dossier_type": "risk_of_bias",
        "review_family": "intervention",
        "target": {
            "type": "result", "id": "result-1", "study_id": "study-1",
            "result_id": "result-1", "synthesis_id": "synthesis-1",
        },
        "evidence_node_ids": ["result-1"],
        "domains": domains,
        "overall_proposal": {
            "actor_id": "proposal-model", "judgment": "low risk",
            "rationale": "All domain proposals were considered.",
        },
        "opposition": {
            "actor_id": "opposition-model", "counter_judgment": "some concerns",
            "anchor_ids": ["anchor-counter"],
            "rationale": "A plausible concern was actively sought.",
        },
        "judge_recommendation": {
            "actor_id": "judge-model", "judgment": "low risk",
            "reason_codes": ["algorithm_consistent"], "confidence": 0.9, "abstained": False,
        },
        "missing_information": [],
    }


def estimand(**updates: object) -> dict[str, object]:
    value = {
        "population": "eligible adults",
        "contrast": "treatment versus placebo",
        "outcome": "clinical event",
        "time_horizon": "12 weeks",
        "effect_measure": "risk ratio",
        "analysis_unit": "participant",
        "conditioning_set": [],
    }
    value.update(updates)
    return value


def claim_candidate(text: str = "The synthesis estimated a risk ratio of 0.80.") -> dict[str, object]:
    return {
        "claim_id": "claim-1",
        "claim_type": "observation",
        "text": text,
        "scope": {
            "synthesis_id": "synthesis-1", "population": "Adults",
            "contrast": "Treatment versus placebo", "outcome": "Clinical event",
            "time_window": "12 weeks", "applicability_limits": [],
        },
        "certainty": {"framework": "GRADE", "judgment": "low", "dossier_id": "grade-1"},
        "evidence_node_ids": ["synthesis-1"],
        "assertion_ids": [],
        "analysis_output_ids": ["analysis-output-1"],
        "counterevidence_node_ids": [],
        "created_by": {"type": "model", "id": "writer", "version": "fixture-1"},
        "support_verifier_id": "claim-verifier",
        "scope_verified": True,
        "numeric_support": [{"value": 0.8, "tolerance": 0.0001}],
    }


class AppraisalDossierTests(unittest.TestCase):
    def test_rob2_adapter_builds_non_final_ready_dossier(self) -> None:
        adapter = load_appraisal_adapter(
            REPO_ROOT / "metawingman/references/appraisal-adapters/rob2-2019.json"
        )
        dossier = build_appraisal_dossier(adapter, complete_rob2_candidate(), created_at_utc=TIMESTAMP)
        self.assertEqual(dossier["status"], "ready_for_adjudication")
        self.assertIsNone(dossier["final_judgment"])
        self.assertEqual(dossier["human_signature"]["status"], "pending")

    def test_missing_domain_keeps_dossier_draft(self) -> None:
        adapter = load_appraisal_adapter(
            REPO_ROOT / "metawingman/references/appraisal-adapters/rob2-2019.json"
        )
        candidate = complete_rob2_candidate()
        candidate["domains"].pop()
        dossier = build_appraisal_dossier(adapter, candidate, created_at_utc=TIMESTAMP)
        self.assertEqual(dossier["status"], "draft")
        self.assertTrue(dossier["missing_information"])

    def test_missing_evidence_builder_cannot_finalize(self) -> None:
        candidate = {
            "matrix_id": "missing-1", "synthesis_id": "synthesis-1",
            "framework": {
                "name": "ROB-ME", "version": "BMJ 2023 tool",
                "source_url": "https://www.bmj.com/content/383/bmj-2023-076754",
                "verified_at_utc": TIMESTAMP,
            },
            "expected_results": [{
                "study_id": "study-1", "result_key": "outcome-12w", "outcome": "Clinical event",
                "timepoint": "12 weeks", "contrast": "Treatment versus placebo",
                "planned_source_ids": ["registry-1"], "availability": "unavailable",
                "identified_result_ids": [], "included_result_ids": [], "anchor_ids": ["anchor-registry"],
                "reason": "Prespecified outcome was not reported.", "selective_nonreporting_signal": "possible",
            }],
            "status": "final",
        }
        with self.assertRaises(JudgmentWorkbenchError):
            build_missing_evidence_matrix(candidate, created_at_utc=TIMESTAMP)


class PoolabilityTests(unittest.TestCase):
    def test_exact_estimand_is_included_but_not_finalized(self) -> None:
        matrix = build_poolability_matrix({
            "matrix_id": "pool-1", "synthesis_id": "synthesis-1",
            "target_estimand": estimand(),
            "results": [{
                "result_id": "result-1", "study_id": "study-1", "estimand": estimand(),
                "anchor_ids": ["anchor-result"],
            }],
        }, created_at_utc=TIMESTAMP)
        self.assertEqual(matrix["results"][0]["recommendation"], "include")
        self.assertEqual(matrix["status"], "draft")
        self.assertIsNone(matrix["final_decision"])

    def test_difference_is_incompatible_without_anchored_override(self) -> None:
        matrix = build_poolability_matrix({
            "matrix_id": "pool-2", "synthesis_id": "synthesis-1",
            "target_estimand": estimand(),
            "results": [{
                "result_id": "result-2", "study_id": "study-2",
                "estimand": estimand(time_horizon="52 weeks"), "anchor_ids": ["anchor-result"],
            }],
        }, created_at_utc=TIMESTAMP)
        self.assertEqual(matrix["results"][0]["recommendation"], "exclude")

    def test_compatible_override_requires_rationale_and_anchor(self) -> None:
        matrix = build_poolability_matrix({
            "matrix_id": "pool-3", "synthesis_id": "synthesis-1",
            "target_estimand": estimand(),
            "results": [{
                "result_id": "result-3", "study_id": "study-3",
                "estimand": estimand(population="adults aged at least 18 years"),
                "anchor_ids": ["anchor-population"],
                "alignment_overrides": {
                    "population": {
                        "status": "compatible", "rationale": "Operational definitions are identical.",
                        "anchor_ids": ["anchor-population"],
                    }
                },
            }],
        }, created_at_utc=TIMESTAMP)
        self.assertEqual(matrix["results"][0]["recommendation"], "include")


class GradeAndClaimTests(unittest.TestCase):
    def test_threshold_geometry_does_not_invent_grade_judgment(self) -> None:
        result = locate_interval_against_threshold(0.8, 0.7, 0.95, 0.9)
        self.assertEqual(result["relation"], "interval_crosses_threshold")
        self.assertIsNone(result["grade_judgment"])

    def test_claim_compiler_accepts_supported_nonfinal_wording(self) -> None:
        claim = compile_claim(claim_candidate(), created_at_utc=TIMESTAMP)
        self.assertEqual(claim["status"], "accepted")
        self.assertEqual(claim["human_responsibility"]["status"], "pending")

    def test_claim_compiler_rejects_unsupported_number_and_absolute_wording(self) -> None:
        with self.assertRaises(ClaimCompileError):
            compile_claim(claim_candidate("The synthesis estimated a risk ratio of 0.42."), created_at_utc=TIMESTAMP)
        with self.assertRaises(ClaimCompileError):
            compile_claim(claim_candidate("The synthesis conclusively demonstrates a risk ratio of 0.80."), created_at_utc=TIMESTAMP)


if __name__ == "__main__":
    unittest.main()
