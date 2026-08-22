import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from metawingman.scripts.metawingman_core.end_to_end_reconstruction import (
    EndToEndReconstructionError,
    unlock_reference,
    validate_execution_plan,
    validate_lock_set,
)
from metawingman.scripts.metawingman_core.end_to_end_runner import (
    _shape_signature,
    execute_reconstruction_slot,
    normalize_question_framework,
    score_reconstruction_output,
)
from metawingman.scripts.metawingman_core.deepseek_provider import ProviderResult


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class EndToEndReconstructionContractTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.operational = self.root / "operational"
        self.sealed = self.root / "sealed"
        self.operational.mkdir()
        self.sealed.mkdir()
        self.case_paths = []
        for split, family in (("development", "family-a"), ("calibration", "family-b")):
            path = self.operational / f"{split}.json"
            path.write_text(
                json.dumps({
                    "schema_version": "1.0",
                    "case_id": f"case-{split}",
                    "review_family_id": family,
                    "dependency_family_ids": [],
                    "split": split,
                    "historical_cutoff_at_utc": "2022-01-01T00:00:00Z",
                    "license": {"status": "verified", "redistribution": "metadata_and_derived_only"},
                    "reproduction_ceiling": "bounded_review_reconstruction",
                    "visible_material": [{"anchor_id": f"anchor-{split}", "text": "visible source"}],
                }),
                encoding="utf-8",
            )
            self.case_paths.append(path)
        self.reference = self.sealed / "reference.json"
        self.reference.write_text(
            json.dumps({"published_expert_reference": {"decision": "include"}}),
            encoding="utf-8",
        )
        self.provider_config = self.operational / "provider.json"
        self.provider_config.write_text(json.dumps({
            "schema_version": "1.0", "provider_id": "deepseek-development",
            "adapter": "deepseek", "display_name": "DeepSeek",
            "base_url": "https://api.deepseek.com", "model": "deepseek-v4-flash",
            "api_key_required": True, "api_key_env": "DEEPSEEK_API_KEY",
            "credential_target": "MetaWingman/DeepSeek", "allow_local_http": False,
            "features": {"json_output": True, "reasoning_effort": True, "deepseek_thinking": True},
        }), encoding="utf-8")
        self.prompt_file = self.operational / "prompt.txt"
        self.prompt_file.write_text("frozen end-to-end review prompt", encoding="utf-8")
        self.tool_file = self.operational / "tool.json"
        self.tool_file.write_text(json.dumps({"tool": "pubmed-search", "version": "1"}), encoding="utf-8")
        configs = [
            "generic-fixed-acquisition",
            "decision-aware-topic-control",
            "conclusion-directed-acquisition",
            "full-metawingman",
        ]
        seeds = [20260820, 20260821, 20260822]
        self.plan = {
            "schema_version": "1.0",
            "plan_id": "direct-evidence-v1",
            "frozen_at_utc": "2026-08-21T00:00:00Z",
            "operational_root": str(self.operational),
            "sealed_root": str(self.sealed),
            "runtime": {
                "model_id": "deepseek-v4-flash",
                "provider_config_path": str(self.provider_config),
                "provider_config_sha256": _sha(self.provider_config),
                "prompt_files": [{"path": str(self.prompt_file), "sha256": _sha(self.prompt_file)}],
                "tool_files": [{"path": str(self.tool_file), "sha256": _sha(self.tool_file)}],
                "matched_budget": {"max_model_calls": 8, "max_input_tokens": 32000, "max_output_tokens": 8192, "retry_limit": 0, "wall_seconds": 900},
                "command_argv": ["python", "run_end_to_end_reconstruction.py", "execute", "FROZEN.json"]
            },
            "cases": [
                {
                    "case_id": json.loads(path.read_text())["case_id"],
                    "review_family_id": json.loads(path.read_text())["review_family_id"],
                    "split": json.loads(path.read_text())["split"],
                    "operational_path": str(path),
                    "operational_sha256": _sha(path),
                    "sealed_reference_path": str(self.reference),
                    "sealed_reference_sha256": _sha(self.reference),
                }
                for path in self.case_paths
            ],
            "configurations": [
                {
                    "configuration_id": config,
                    "topic_opportunity_control": config in {"decision-aware-topic-control", "full-metawingman"},
                    "conclusion_directed_acquisition": config in {"conclusion-directed-acquisition", "full-metawingman"},
                }
                for config in configs
            ],
            "seeds": seeds,
            "slots": [
                {"case_id": f"case-{split}", "configuration_id": config, "seed": seed}
                for split in ("development", "calibration")
                for config in configs
                for seed in seeds
            ],
        }

    def tearDown(self):
        self.tempdir.cleanup()

    def test_valid_plan_freezes_two_innovation_factorial(self):
        result = validate_execution_plan(self.plan)
        self.assertEqual(result["expected_slots"], 24)
        self.assertEqual(result["review_families"], 2)

    def test_runtime_model_prompt_tool_and_budget_freeze_is_required(self):
        self.plan.pop("runtime")
        with self.assertRaisesRegex(EndToEndReconstructionError, "runtime"):
            validate_execution_plan(self.plan)

    def test_prompt_hash_drift_fails_closed(self):
        self.prompt_file.write_text("changed prompt", encoding="utf-8")
        with self.assertRaisesRegex(EndToEndReconstructionError, "runtime hash drift"):
            validate_execution_plan(self.plan)

    def test_provider_model_mismatch_fails_closed(self):
        provider = json.loads(self.provider_config.read_text(encoding="utf-8"))
        provider["model"] = "another-model"
        self.provider_config.write_text(json.dumps(provider), encoding="utf-8")
        self.plan["runtime"]["provider_config_sha256"] = _sha(self.provider_config)
        with self.assertRaisesRegex(EndToEndReconstructionError, "provider model"):
            validate_execution_plan(self.plan)

    def test_missing_cartesian_slot_fails_closed(self):
        self.plan["slots"].pop()
        with self.assertRaisesRegex(EndToEndReconstructionError, "exact Cartesian"):
            validate_execution_plan(self.plan)

    def test_unknown_plan_field_fails_closed(self):
        self.plan["unexpected_unfrozen_setting"] = True
        with self.assertRaisesRegex(EndToEndReconstructionError, "unexpected_unfrozen_setting|Additional properties"):
            validate_execution_plan(self.plan)

    def test_duplicate_family_across_splits_fails_closed(self):
        self.plan["cases"][1]["review_family_id"] = "family-a"
        case = json.loads(self.case_paths[1].read_text(encoding="utf-8"))
        case["review_family_id"] = "family-a"
        self.case_paths[1].write_text(json.dumps(case), encoding="utf-8")
        self.plan["cases"][1]["operational_sha256"] = _sha(self.case_paths[1])
        with self.assertRaisesRegex(EndToEndReconstructionError, "crosses splits"):
            validate_execution_plan(self.plan)

    def test_operational_hash_drift_fails_closed(self):
        self.case_paths[0].write_text("drift", encoding="utf-8")
        with self.assertRaisesRegex(EndToEndReconstructionError, "operational hash drift"):
            validate_execution_plan(self.plan)

    def test_operational_material_cannot_contain_answer_or_secret(self):
        case = json.loads(self.case_paths[0].read_text(encoding="utf-8"))
        case["metadata"] = {"published_expert_reference": {"answer": "hidden"}}
        self.case_paths[0].write_text(json.dumps(case), encoding="utf-8")
        self.plan["cases"][0]["operational_sha256"] = _sha(self.case_paths[0])
        with self.assertRaisesRegex(EndToEndReconstructionError, "sensitive or sealed"):
            validate_execution_plan(self.plan)

    def test_unverified_license_or_missing_reproduction_ceiling_fails(self):
        case = json.loads(self.case_paths[0].read_text(encoding="utf-8"))
        case["license"]["status"] = "unverified"
        case.pop("reproduction_ceiling")
        self.case_paths[0].write_text(json.dumps(case), encoding="utf-8")
        self.plan["cases"][0]["operational_sha256"] = _sha(self.case_paths[0])
        with self.assertRaisesRegex(EndToEndReconstructionError, "license|reproduction ceiling"):
            validate_execution_plan(self.plan)

    def test_reference_cannot_be_unsealed_before_all_receipts_lock(self):
        validate_execution_plan(self.plan)
        receipts = [
            {**slot, "plan_id": self.plan["plan_id"], "status": "completed", "output_sha256": "a" * 64}
            for slot in self.plan["slots"][:-1]
        ]
        with self.assertRaisesRegex(EndToEndReconstructionError, "lock set incomplete"):
            validate_lock_set(self.plan, receipts)
        with self.assertRaisesRegex(EndToEndReconstructionError, "lock set incomplete"):
            unlock_reference(self.plan, receipts, self.plan["cases"][0]["case_id"])

    def test_complete_hash_bound_lock_allows_reference_read(self):
        validate_execution_plan(self.plan)
        receipts = [
            {**slot, "plan_id": self.plan["plan_id"], "status": "completed", "output_sha256": "a" * 64}
            for slot in self.plan["slots"]
        ]
        lock = validate_lock_set(self.plan, receipts)
        self.assertEqual(lock["locked_slots"], 24)
        reference = unlock_reference(self.plan, receipts, self.plan["cases"][0]["case_id"])
        self.assertIn("published_expert_reference", reference)

    def test_ai_slot_is_three_stage_verified_and_scoreable(self):
        class Provider:
            model = "deepseek-v4-flash"

            def __init__(self):
                self.responses = iter([
                    {"question_framework": {"population": ["adults"], "intervention_or_exposure": ["test"], "comparator": ["reference"], "outcome": ["accuracy"], "study_design": ["diagnostic"], "synthesis_route": "diagnostic meta-analysis"}, "eligibility_criteria": ["diagnostic studies"]},
                    {"included_candidate_ids": ["r1", "invented"], "extractions": [{"candidate_id": "r1", "finding": "sensitivity varied", "certainty": "low"}]},
                    {"claims": [{"statement": "Sensitivity varied across settings.", "supporting_candidate_ids": ["r1"], "certainty": "low"}], "limitations": ["abstract-only evidence"]},
                ])

            def chat(self, *_args, **_kwargs):
                content = json.dumps(next(self.responses))
                return ProviderResult(
                    provider="test", model=self.model, finish_reason="stop",
                    content=content, content_sha256="c" * 64,
                    prompt_tokens=10, completion_tokens=5, total_tokens=15,
                    reasoning_tokens=0, system_fingerprint="test", credential_source="test",
                )

        result = execute_reconstruction_slot(
            plan_id="plan",
            case={"case_id": "case", "operational_question": "test accuracy", "eligibility_criteria": ["diagnostic studies"], "historical_cutoff_at_utc": "2021-08-31T23:59:59Z"},
            configuration={"configuration_id": "full-metawingman", "topic_opportunity_control": True, "conclusion_directed_acquisition": True},
            seed=20260820,
            provider=Provider(),
            records=[{"id": "r1", "title": "Study", "abstract": "Sensitivity varied."}],
            acquisition_output={"retrieval_candidate_ids": ["r1"]},
        )
        self.assertEqual(result["provider_calls"], 3)
        self.assertEqual(result["protocol"]["status"], "completed")
        self.assertEqual(result["screening"]["included_candidate_ids"], ["r1"])
        self.assertEqual(result["screening"]["verification_audit"]["unknown_ids"], ["invented"])
        score = score_reconstruction_output(result, {
            "question_framework": result["protocol"]["question_framework"],
            "included_candidate_ids": ["r1"],
            "conclusion_axes": [{"axis_id": "variation", "required_terms_any": ["varied", "heterogeneity"]}],
        })
        self.assertEqual(score["screening_recall"], 1.0)
        self.assertEqual(score["conclusion_axis_coverage"], 1.0)
        self.assertEqual(score["end_to_end_min_stage_score"], 1.0)

    def test_generated_protocol_is_the_screening_contract_not_the_supplied_oracle_question(self):
        class Provider:
            model = "deepseek-v4-flash"

            def __init__(self):
                self.payloads = []
                self.responses = iter([
                    {"question_framework": {"population": ["adults"], "intervention_or_exposure": ["intervention"], "comparator": ["usual care"], "outcome": ["mortality"], "study_design": ["randomized trials"], "synthesis_route": "pairwise meta-analysis"}, "eligibility_criteria": ["generated protocol criterion"]},
                    {"included_candidate_ids": [], "extractions": []},
                    {"claims": [], "limitations": ["no included evidence"]},
                ])

            def chat(self, messages, **_kwargs):
                self.payloads.append(json.loads(messages[-1]["content"]))
                content = json.dumps(next(self.responses))
                return ProviderResult(
                    provider="test", model=self.model, finish_reason="stop",
                    content=content, content_sha256="c" * 64,
                    prompt_tokens=10, completion_tokens=5, total_tokens=15,
                    reasoning_tokens=0, system_fingerprint="test", credential_source="test",
                )

        provider = Provider()
        execute_reconstruction_slot(
            plan_id="plan",
            case={"case_id": "case", "operational_question": "oracle wording must not drive screening", "eligibility_criteria": ["supplied oracle criterion"], "historical_cutoff_at_utc": "2021-08-31T23:59:59Z"},
            configuration={"configuration_id": "generic", "topic_opportunity_control": False, "conclusion_directed_acquisition": False},
            seed=20260820,
            provider=provider,
            records=[{"id": "r1", "title": "Study", "abstract": "Trial."}],
            acquisition_output={"retrieval_candidate_ids": ["r1"]},
        )
        screening_payload = provider.payloads[1]
        self.assertEqual(screening_payload["protocol_question_framework"]["outcome"], ["mortality"])
        self.assertEqual(screening_payload["eligibility_criteria"], ["generated protocol criterion"])
        self.assertNotIn("question", screening_payload)

    def test_synthesis_claims_without_verified_support_are_rejected(self):
        class Provider:
            model = "deepseek-v4-flash"

            def __init__(self):
                self.responses = iter([
                    {"question_framework": {"population": ["adults"], "intervention_or_exposure": ["test"], "comparator": ["reference"], "outcome": ["accuracy"], "study_design": ["diagnostic studies"], "synthesis_route": "diagnostic meta-analysis"}, "eligibility_criteria": ["diagnostic studies"]},
                    {"included_candidate_ids": ["r1"], "extractions": [{"candidate_id": "r1", "finding": "specificity was high", "certainty": "low"}]},
                    {"claims": [
                        {"statement": "Specificity was high.", "supporting_candidate_ids": ["r1"], "certainty": "low"},
                        {"statement": "Mortality improved.", "supporting_candidate_ids": ["invented"], "certainty": "high"},
                    ], "limitations": ["abstract-only evidence"]},
                ])

            def chat(self, *_args, **_kwargs):
                content = json.dumps(next(self.responses))
                return ProviderResult(
                    provider="test", model=self.model, finish_reason="stop",
                    content=content, content_sha256="c" * 64,
                    prompt_tokens=10, completion_tokens=5, total_tokens=15,
                    reasoning_tokens=0, system_fingerprint="test", credential_source="test",
                )

        result = execute_reconstruction_slot(
            plan_id="plan",
            case={"case_id": "case", "operational_question": "test accuracy", "eligibility_criteria": ["diagnostic studies"], "historical_cutoff_at_utc": "2021-08-31T23:59:59Z"},
            configuration={"configuration_id": "generic", "topic_opportunity_control": False, "conclusion_directed_acquisition": False},
            seed=20260820,
            provider=Provider(),
            records=[{"id": "r1", "title": "Study", "abstract": "Specificity was high."}],
            acquisition_output={"retrieval_candidate_ids": ["r1"]},
        )
        self.assertEqual(result["synthesis"]["conclusion_statements"], ["Specificity was high."])
        self.assertEqual(result["synthesis"]["verification_audit"]["unsupported_claims"], 1)

    def test_score_separates_acquisition_ceiling_from_conditional_screening_recall(self):
        output = {
            "case_id": "case", "configuration_id": "config", "seed": 1,
            "protocol": {"question_framework": {
                "population": ["adults"], "intervention_or_exposure": ["test"],
                "comparator": ["reference"], "outcome": ["accuracy"],
                "study_design": ["diagnostic"], "synthesis_route": "diagnostic meta-analysis",
            }},
            "screening": {
                "visible_candidate_ids": ["r1", "r2"],
                "included_candidate_ids": ["r1"],
            },
            "synthesis": {"conclusion_statements": ["Accuracy varied."]},
        }
        reference = {
            "question_framework": output["protocol"]["question_framework"],
            "included_candidate_ids": ["r1", "r2", "r3", "r4"],
            "conclusion_axes": [{"axis_id": "accuracy", "required_terms_any": ["accuracy"]}],
        }
        score = score_reconstruction_output(output, reference)
        self.assertEqual(score["acquisition_recall"], 0.5)
        self.assertEqual(score["screening_recall_conditional_on_visible"], 0.5)
        self.assertEqual(score["screening_recall"], 0.25)

    def test_framework_score_uses_frozen_token_dice_not_whole_phrase_equality(self):
        output = {
            "case_id": "case", "configuration_id": "config", "seed": 1,
            "protocol": {"question_framework": {
                "population": ["adult patients"], "intervention_or_exposure": ["rapid antigen test"],
                "comparator": ["PCR reference standard"], "outcome": ["diagnostic sensitivity"],
                "study_design": ["accuracy study"], "synthesis_route": "diagnostic meta-analysis",
            }},
            "screening": {"included_candidate_ids": ["r1"]},
            "synthesis": {"conclusion_statements": ["Sensitivity was variable."]},
        }
        reference = {
            "question_framework": {
                "population": ["adults"], "intervention_or_exposure": ["antigen rapid diagnostic tests"],
                "comparator": ["RT PCR"], "outcome": ["sensitivity"],
                "study_design": ["diagnostic accuracy studies"], "synthesis_route": "diagnostic meta-analysis",
            },
            "included_candidate_ids": ["r1"],
            "conclusion_axes": [{"axis_id": "sensitivity", "required_terms_any": ["sensitivity"]}],
        }
        score = score_reconstruction_output(output, reference)
        self.assertGreater(score["framework_similarity"], 0.4)
        self.assertLess(score["framework_similarity"], 1.0)

    def test_framework_normalizer_handles_schema_equivalent_provider_shapes(self):
        normalized, changed = normalize_question_framework({
            "population": "adults", "intervention_or_exposure": "test",
            "comparator": ["reference"], "outcome": "accuracy",
            "study_design": ["diagnostic"], "synthesis_route": ["diagnostic meta-analysis"],
            "decision_context": "clinical triage",
        })
        self.assertTrue(changed)
        self.assertEqual(normalized["population"], ["adults"])
        self.assertEqual(normalized["synthesis_route"], "diagnostic meta-analysis")
        self.assertNotIn("decision_context", normalized)

    def test_protocol_and_synthesis_each_get_one_bounded_schema_repair(self):
        class Provider:
            model = "deepseek-v4-flash"

            def __init__(self):
                self.payloads = []
                self.responses = iter([
                    {"question_framework": "wrong shape", "eligibility_criteria": []},
                    {"question_framework": {"population": ["adults"], "intervention_or_exposure": ["test"], "comparator": ["reference"], "outcome": ["accuracy"], "study_design": ["diagnostic"], "synthesis_route": "diagnostic meta-analysis"}, "eligibility_criteria": ["diagnostic studies"]},
                    {"included_candidate_ids": ["r1"], "extractions": [{"candidate_id": "r1", "finding": "accuracy varied", "certainty": "low"}]},
                    {"claims": "wrong shape", "limitations": "wrong shape"},
                    {"claims": [{"statement": "Accuracy varied.", "supporting_candidate_ids": ["r1"], "certainty": "low"}], "limitations": ["abstract only"]},
                ])

            def chat(self, messages, **_kwargs):
                self.payloads.append(json.loads(messages[-1]["content"]))
                content = json.dumps(next(self.responses))
                return ProviderResult(
                    provider="test", model=self.model, finish_reason="stop",
                    content=content, content_sha256=hashlib.sha256(content.encode()).hexdigest(),
                    prompt_tokens=10, completion_tokens=5, total_tokens=15,
                    reasoning_tokens=0, system_fingerprint="test", credential_source="test",
                )

        provider = Provider()
        result = execute_reconstruction_slot(
            plan_id="plan",
            case={"case_id": "case", "operational_question": "test accuracy", "eligibility_criteria": ["diagnostic studies"], "historical_cutoff_at_utc": "2021-08-31T23:59:59Z"},
            configuration={"configuration_id": "generic", "topic_opportunity_control": False, "conclusion_directed_acquisition": False},
            seed=20260820,
            provider=provider,
            records=[{"id": "r1", "title": "Study", "abstract": "Accuracy varied."}],
            acquisition_output={"retrieval_candidate_ids": ["r1"]},
        )
        self.assertEqual(result["provider_calls"], 5)
        self.assertEqual(result["protocol"]["status"], "completed_after_schema_repair")
        self.assertEqual(result["synthesis"]["status"], "completed_after_schema_repair")
        self.assertEqual(provider.payloads[1]["stage"], "protocol_schema_repair")
        self.assertEqual(provider.payloads[4]["stage"], "synthesis_schema_repair")
        self.assertEqual(result["schema_diagnostics"]["protocol"]["repair_attempted"], True)
        self.assertEqual(result["schema_diagnostics"]["synthesis"]["repair_attempted"], True)

    def test_shape_signature_records_structure_without_semantic_text(self):
        signature = _shape_signature({
            "question_framework": "secret semantic answer",
            "claims": [{"statement": "another secret", "supporting_candidate_ids": ["r1"]}],
        })
        encoded = json.dumps(signature, sort_keys=True)
        self.assertIn("question_framework", encoded)
        self.assertIn("statement", encoded)
        self.assertNotIn("secret semantic answer", encoded)
        self.assertNotIn("another secret", encoded)
        self.assertNotIn("r1", encoded)


if __name__ == "__main__":
    unittest.main()
