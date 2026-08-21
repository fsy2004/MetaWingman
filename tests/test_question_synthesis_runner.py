from __future__ import annotations

import hashlib
import importlib
import json
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "metawingman/scripts"))

from metawingman_core.model_provider import ProviderResult
from metawingman_core.question_synthesis_design import design_review_question

HASH_A = "a" * 64
HASH_B = "b" * 64
CONFIGURATION_IDS = [
    "general-model-baseline",
    "generic-retrieval",
    "biomedical-schema",
    "biomedical-routing",
    "full-biomedical-stack",
]
SEEDS = [20260820, 20260821, 20260822]


def prompt_hashes() -> dict[str, str]:
    return {
        configuration_id: hashlib.sha256(
            runner_module().PROMPT_TEMPLATES[configuration_id].encode("utf-8")
        ).hexdigest()
        for configuration_id in CONFIGURATION_IDS
    }


def runner_module():
    try:
        return importlib.import_module("metawingman_core.question_synthesis_runner")
    except ModuleNotFoundError as exc:
        raise AssertionError("executable question-synthesis runner is missing") from exc


def write_json(path: Path, document: object) -> str:
    raw = json.dumps(document, sort_keys=True).encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()


def operational_case() -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "case_id": "case-1",
        "split": "development",
        "clinical_context": {
            "context_id": "context-1",
            "decision_problem": "Which intervention is preferable?",
            "candidate_actions": ["choose an intervention"],
            "patient_important_outcomes": ["mortality"],
        },
        "visible_material": [
            {
                "material_id": "material-2",
                "text": "Placebo controlled trial reports mortality.",
                "source_node_ids": ["evidence-1"],
                "document_state": "verified_native_text",
            },
            {
                "material_id": "material-1",
                "text": "Randomized intervention evidence is available.",
                "source_node_ids": ["evidence-2"],
                "document_state": "verified_native_text",
            },
        ],
        "method_routes": [
            {
                "route_id": "pairwise_random_effects",
                "review_families": ["intervention"],
                "required_checks": [],
            }
        ],
    }


def execution_plan(root: Path, *, case_count: int = 1) -> dict[str, object]:
    provider_config = root / "provider.json"
    provider_sha = write_json(
        provider_config,
        {
            "schema_version": "1.0",
            "provider_id": "fixture",
            "adapter": "openai_compatible",
            "display_name": "Fixture",
            "base_url": "https://example.invalid/v1",
            "model": "deepseek-v4-flash",
            "api_key_required": False,
            "api_key_env": "FIXTURE_API_KEY",
            "credential_target": None,
            "timeout_seconds": 60,
            "allow_local_http": False,
            "features": {"json_output": True, "reasoning_effort": False, "deepseek_thinking": False},
        },
    )
    tool_hashes = {}
    for relative in (
        "metawingman/scripts/metawingman_core/question_synthesis_runner.py",
        "metawingman/scripts/metawingman_core/question_synthesis_design.py",
    ):
        source = ROOT / relative
        destination = root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(source.read_bytes())
        tool_hashes[relative] = hashlib.sha256(destination.read_bytes()).hexdigest()
    registry_relative = "metawingman/references/question-synthesis-methods.json"
    registry_source = ROOT / registry_relative
    registry_path = root / registry_relative
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_bytes(registry_source.read_bytes())
    source_hashes = {registry_relative: hashlib.sha256(registry_path.read_bytes()).hexdigest()}
    cases = []
    for index in range(case_count):
        case = operational_case()
        case["case_id"] = f"case-{index + 1}"
        path = root / "operational" / f"case-{index + 1}.json"
        cases.append(
            {
                "case_id": case["case_id"],
                "operational_case_path": path.relative_to(root).as_posix(),
                "sha256": write_json(path, case),
            }
        )
    slots = [
        {
            "case_id": case["case_id"],
            "configuration_id": configuration_id,
            "seed": seed,
            "output_path": f"outputs/{case['case_id']}/{configuration_id}/{seed}.json",
            "receipt_path": f"receipts/{case['case_id']}/{configuration_id}/{seed}.json",
        }
        for case in cases
        for configuration_id in CONFIGURATION_IDS
        for seed in SEEDS
    ]
    return {
        "schema_version": "1.0",
        "plan_id": "question-synthesis-dev-v1",
        "split": "development",
        "status": "frozen",
        "cases": cases,
        "configuration_ids": CONFIGURATION_IDS,
        "seeds": SEEDS,
        "model_reference": "deepseek-v4-flash",
        "provider_config_path": provider_config.relative_to(root).as_posix(),
        "provider_config_sha256": provider_sha,
        "provider_seed_supported": False,
        "seed_scope": "orchestration_order_and_tie_breaks",
        "same_provider_roles_are_independent_evidence": False,
        "prompt_sha256_by_configuration": prompt_hashes(),
        "tool_version_sha256": tool_hashes,
        "source_version_sha256": source_hashes,
        "matched_budget": {
            "max_model_calls": 3,
            "max_input_tokens": 12000,
            "max_output_tokens": 4096,
            "retry_budget": 0,
            "wall_time_ceiling_seconds": 300,
        },
        "budget_enforcement": {
            "provider_timeout_seconds": 60,
            "retry_policy": "no_retries",
            "wall_time_scope": "pre_call_between_call_and_post_hoc",
            "single_call_overrun_policy": "block_after_provider_returns",
        },
        "failure_policy": {"max_systemic_provider_failures": 1, "scientific_failures_may_lock": True},
        "slots": slots,
        "command_argv": ["python", "metawingman/scripts/run_question_synthesis_benchmark.py", "execute", "PLAN"],
        "frozen_at_utc": "2026-08-20T00:00:00Z",
    }


class NeverCalledProviderFactory:
    def __init__(self) -> None:
        self.calls = 0

    def __call__(self, config):
        self.calls += 1
        raise AssertionError("validate-only must not build or call a provider")


class FixtureProvider:
    credential_source = "fixture"
    timeout_seconds = 60

    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload
        self.calls = 0
        self.messages: list[object] = []

    def list_models(self) -> list[str]:
        return ["deepseek-v4-flash"]

    def chat(self, messages, *, model=None, thinking=False, reasoning_effort="low", max_tokens=128, json_output=False):
        self.calls += 1
        self.messages.append(messages)
        content = json.dumps(self.payload, sort_keys=True)
        return ProviderResult(
            provider="fixture",
            model=model or "deepseek-v4-flash",
            finish_reason="stop",
            content=content,
            content_sha256=hashlib.sha256(content.encode()).hexdigest(),
            prompt_tokens=11,
            completion_tokens=7,
            total_tokens=18,
            reasoning_tokens=None,
            system_fingerprint="fixture-v1",
            credential_source="fixture",
        )


class SequenceProvider(FixtureProvider):
    def __init__(self, payloads: list[dict[str, object]]) -> None:
        super().__init__(payloads[0])
        self.payloads = payloads

    def chat(self, messages, **kwargs):
        self.payload = self.payloads[self.calls]
        return super().chat(messages, **kwargs)


class FailingProvider(FixtureProvider):
    def __init__(self) -> None:
        super().__init__({})

    def chat(self, messages, **kwargs):
        self.calls += 1
        raise RuntimeError("sensitive-provider-detail-must-not-be-persisted")


class PartialFailingProvider(FixtureProvider):
    def chat(self, messages, **kwargs):
        if self.calls:
            raise RuntimeError("provider credential failure after one billed call")
        return super().chat(messages, **kwargs)


class SlowProvider(FixtureProvider):
    def chat(self, messages, **kwargs):
        time.sleep(0.02)
        return super().chat(messages, **kwargs)


class WrongModelProvider(FixtureProvider):
    def chat(self, messages, **kwargs):
        result = super().chat(messages, **kwargs)
        return ProviderResult(
            provider=result.provider,
            model="unexpected-model",
            finish_reason=result.finish_reason,
            content=result.content,
            content_sha256=result.content_sha256,
            prompt_tokens=result.prompt_tokens,
            completion_tokens=result.completion_tokens,
            total_tokens=result.total_tokens,
            reasoning_tokens=result.reasoning_tokens,
            system_fingerprint=result.system_fingerprint,
            credential_source=result.credential_source,
        )


class FirstInvalidThenValidProvider(FixtureProvider):
    def __init__(self, payload: dict[str, object]) -> None:
        super().__init__(payload)

    def chat(self, messages, **kwargs):
        if self.calls == 0:
            self.calls += 1
            self.messages.append(messages)
            content = "not-json"
            return ProviderResult(
                provider="fixture", model=kwargs.get("model") or "deepseek-v4-flash",
                finish_reason="stop", content=content,
                content_sha256=hashlib.sha256(content.encode()).hexdigest(),
                prompt_tokens=11, completion_tokens=2, total_tokens=13,
                reasoning_tokens=None, system_fingerprint="fixture-v1",
                credential_source="fixture",
            )
        return super().chat(messages, **kwargs)


class QuestionSynthesisRunnerContractTests(unittest.TestCase):
    def test_design_abstention_carries_configuration_seed_and_nonindependent_receipt(self) -> None:
        provider = FixtureProvider({})
        result = design_review_question(
            provider=provider,
            landscape={"landscape_id": "landscape-1", "nodes": []},
            context={"context_id": "context-1"},
            routes=[],
            budget={"max_nodes": 1, "max_model_calls": 3, "max_verifier_calls": 2, "max_rounds": 1},
            model="deepseek-v4-flash",
            max_tokens=128,
            created_at_utc="2026-08-20T00:00:00Z",
            configuration_id="full-biomedical-stack",
            seed=20260820,
        )
        self.assertEqual(result["status"], "abstained")
        self.assertEqual(result["configuration_id"], "full-biomedical-stack")
        self.assertEqual(result["seed"], 20260820)
        self.assertEqual(
            result["execution_receipt"],
            {
                "configuration_id": "full-biomedical-stack",
                "seed": 20260820,
                "provider_seed_supported": False,
                "seed_scope": "orchestration_order_and_tie_breaks",
                "model_reference": "deepseek-v4-flash",
                "model_calls": 2,
                "status": "abstained",
                "same_provider_roles_are_independent_evidence": False,
            },
        )

    def test_design_reverifies_each_revision_and_selects_the_judge_candidate(self) -> None:
        proposer = {"candidate_id": "proposal", "context_id": "context-1"}
        opposed = {"candidate_id": "opposed", "context_id": "context-1"}
        judged = {"candidate_id": "judged", "context_id": "context-1"}
        role_runs = [
            {"status": "candidate_generated", "document": proposer, "reason_codes": [], "attempts": 1},
            {"status": "candidate_generated", "document": {"candidate": opposed}, "reason_codes": [], "attempts": 1},
            {"status": "candidate_generated", "document": {"candidate": judged}, "reason_codes": [], "attempts": 1},
        ]
        observed_candidates: list[str] = []

        def fake_route(context, candidate, routes, *, created_at_utc):
            observed_candidates.append(candidate["candidate_id"])
            return {"status": "selected", "selected_route_id": "pairwise_random_effects"}

        with (
            patch("metawingman_core.question_synthesis_design.run_question_role", side_effect=role_runs),
            patch("metawingman_core.question_synthesis_design.enumerate_synthesis_routes", side_effect=fake_route),
            patch("metawingman_core.question_synthesis_design.verify_question_candidate", return_value=[]),
            patch("metawingman_core.question_synthesis_design.require_hard_verifiers"),
            patch("metawingman_core.question_synthesis_design.start_question_synthesis_search", return_value={"search_id": "s"}),
            patch("metawingman_core.question_synthesis_design.finalize_question_portfolio", return_value={"status": "complete"}),
        ):
            result = design_review_question(
                provider=FixtureProvider({}),
                landscape={"landscape_id": "landscape-1", "nodes": []},
                context={"context_id": "context-1"},
                routes=[],
                budget={"max_nodes": 1, "max_model_calls": 3, "max_verifier_calls": 2, "max_rounds": 1},
                model="deepseek-v4-flash",
                max_tokens=128,
                created_at_utc="2026-08-20T00:00:00Z",
            )
        self.assertEqual(result["status"], "selected")
        self.assertEqual(result["candidate"]["candidate_id"], "judged")
        self.assertEqual(observed_candidates, ["proposal", "opposed", "judged", "judged"])

    def test_design_abstains_when_bounded_role_cannot_return_a_revised_candidate(self) -> None:
        role_runs = [
            {"status": "candidate_generated", "document": {"candidate_id": "proposal", "context_id": "context-1"}, "reason_codes": [], "attempts": 1},
            {"status": "candidate_generated", "document": {"action_type": "draft_claim"}, "reason_codes": [], "attempts": 1},
        ]
        with (
            patch("metawingman_core.question_synthesis_design.run_question_role", side_effect=role_runs),
            patch("metawingman_core.question_synthesis_design.enumerate_synthesis_routes", return_value={"status": "selected"}),
            patch("metawingman_core.question_synthesis_design.verify_question_candidate", return_value=[]),
        ):
            result = design_review_question(
                provider=FixtureProvider({}),
                landscape={"landscape_id": "landscape-1", "nodes": []},
                context={"context_id": "context-1"},
                routes=[],
                budget={"max_nodes": 1, "max_model_calls": 3, "max_verifier_calls": 2, "max_rounds": 1},
                model="deepseek-v4-flash",
                max_tokens=128,
                created_at_utc="2026-08-20T00:00:00Z",
            )
        self.assertEqual(result["status"], "abstained")
        self.assertIn("opposition_candidate_missing", result["reason_codes"])

    def test_freeze_is_exclusive_and_validate_only_cli_makes_no_provider_call(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            draft = execution_plan(root)
            draft["status"] = "draft"
            draft["frozen_at_utc"] = None
            draft_path = root / "draft.json"
            write_json(draft_path, draft)
            frozen_path = root / "frozen.json"
            frozen = runner_module().freeze_execution_plan(
                draft_path,
                frozen_path,
                frozen_at_utc="2026-08-20T01:02:03Z",
            )
            self.assertEqual(frozen["status"], "frozen")
            self.assertEqual(frozen["frozen_at_utc"], "2026-08-20T01:02:03Z")
            with self.assertRaisesRegex(runner_module().QuestionSynthesisRunError, "already exists"):
                runner_module().freeze_execution_plan(draft_path, frozen_path)
            completed = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "metawingman/scripts/run_question_synthesis_benchmark.py"),
                    "validate-only",
                    str(frozen_path),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)
            self.assertEqual(json.loads(completed.stdout)["provider_calls"], 0)

    def test_five_arms_build_materially_distinct_capability_inputs(self) -> None:
        case = operational_case()
        observed = {
            configuration_id: runner_module().prepare_arm_input(configuration_id, case, seed=SEEDS[0])["capabilities"]
            for configuration_id in CONFIGURATION_IDS
        }
        self.assertEqual(
            observed,
            {
                "general-model-baseline": {
                    "generic_retrieval": False, "biomedical_schema": False,
                    "terminology_retrieval": False, "deterministic_routing": False,
                    "evidence_graph": False, "document_state": False,
                    "external_verifier": False, "opposition_judge": False, "abstention": False,
                },
                "generic-retrieval": {
                    "generic_retrieval": True, "biomedical_schema": False,
                    "terminology_retrieval": False, "deterministic_routing": False,
                    "evidence_graph": False, "document_state": False,
                    "external_verifier": False, "opposition_judge": True, "abstention": False,
                },
                "biomedical-schema": {
                    "generic_retrieval": True, "biomedical_schema": True,
                    "terminology_retrieval": False, "deterministic_routing": False,
                    "evidence_graph": False, "document_state": False,
                    "external_verifier": False, "opposition_judge": False, "abstention": False,
                },
                "biomedical-routing": {
                    "generic_retrieval": True, "biomedical_schema": True,
                    "terminology_retrieval": True, "deterministic_routing": True,
                    "evidence_graph": False, "document_state": False,
                    "external_verifier": False, "opposition_judge": False, "abstention": False,
                },
                "full-biomedical-stack": {
                    "generic_retrieval": True, "biomedical_schema": True,
                    "terminology_retrieval": True, "deterministic_routing": True,
                    "evidence_graph": True, "document_state": True,
                    "external_verifier": True, "opposition_judge": True, "abstention": True,
                },
            },
        )

    def test_operational_case_derives_context_retrieval_routes_document_state_and_verifier_inputs(self) -> None:
        case = {
            "schema_version": "1.0",
            "case_id": "case-live",
            "source_query": {"broad_topic_seed": "intervention efficacy"},
            "visible_material": [
                {"material_id": "brief", "text": json.dumps({"task": "Which review question is feasible?"}), "source_id": "source-brief"},
                {"material_id": "terminology", "text": "Therapy improves survival.", "source_id": "source-term"},
            ],
        }
        generic = runner_module().prepare_arm_input("generic-retrieval", case, seed=SEEDS[0])
        routed = runner_module().prepare_arm_input("biomedical-routing", case, seed=SEEDS[0])
        full = runner_module().prepare_arm_input("full-biomedical-stack", case, seed=SEEDS[0])
        self.assertEqual(generic["payload"]["clinical_context"]["decision_problem"], "intervention efficacy")
        self.assertEqual(
            {item["material_id"] for item in generic["payload"]["retrieved_visible_material"]},
            {"brief", "terminology"},
        )
        self.assertEqual(routed["payload"]["retrieved_visible_material"][0]["material_id"], "terminology")
        self.assertEqual(routed["payload"]["deterministic_route"], "pairwise_random_effects")
        self.assertTrue(any(
            item["route_id"] == "pairwise_random_effects" and item["r_adapter"] == "meta_pw_summary"
            for item in routed["payload"]["executable_method_registry"]
        ))
        self.assertEqual(full["payload"]["required_output_schema"]["evidence_anchor_ids"], "array[string]")
        self.assertEqual(full["payload"]["document_states"]["brief"], "derived_visible_material")
        candidate = {
            "candidate_id": "candidate-live", "review_family": "intervention",
            "synthesis_route": "pairwise_random_effects", "evidence_anchor_ids": ["source-term"],
        }
        provider = SequenceProvider([candidate, {"critique": "check"}, {"candidate": candidate}])
        result = runner_module().run_configuration(
            "full-biomedical-stack", case, seed=SEEDS[0], provider=provider,
            model="deepseek-v4-flash", max_output_tokens=4096,
        )
        self.assertEqual(result["status"], "selected")

    def test_full_stack_verifies_candidate_route_from_public_registry_when_context_is_ambiguous(self) -> None:
        case = {
            "schema_version": "1.0",
            "case_id": "opaque-case",
            "split": "development",
            "source_query": {"broad_topic_seed": "severe pneumonia outcomes"},
            "visible_material": [
                {"material_id": "source", "text": "Cohort outcome evidence.", "source_id": "source-1"},
            ],
        }
        self.assertIsNone(runner_module()._deterministic_route(case))
        observations = runner_module()._hard_verifier_observations(
            {
                "review_family": "prognostic",
                "synthesis_route": "prognostic_factor_meta",
                "evidence_anchor_ids": ["source-1"],
            },
            case,
        )
        self.assertEqual(
            {item["verifier_id"]: item["status"] for item in observations},
            {"source": "passed", "executable": "passed"},
        )

    def test_validation_recomputes_prompt_and_relative_file_hashes_and_rejects_nested_sensitive_values(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = execution_plan(root)
            plan["prompt_sha256_by_configuration"]["general-model-baseline"] = HASH_A
            with self.assertRaisesRegex(runner_module().QuestionSynthesisRunError, "prompt template SHA-256 drift"):
                runner_module().validate_execution_plan(plan, root=root)
            plan = execution_plan(root)
            plan["tool_version_sha256"] = {"C:/absolute/tool.py": HASH_A}
            with self.assertRaisesRegex(runner_module().QuestionSynthesisRunError, "path escapes"):
                runner_module().validate_execution_plan(plan, root=root)
            plan = execution_plan(root)
            provider_path = root / plan["provider_config_path"]
            provider = json.loads(provider_path.read_text(encoding="utf-8"))
            provider["nested"] = {"api_secret": "must-not-be-accepted"}
            plan["provider_config_sha256"] = write_json(provider_path, provider)
            with self.assertRaisesRegex(runner_module().QuestionSynthesisRunError, "secret"):
                runner_module().validate_execution_plan(plan, root=root)
            plan = execution_plan(root)
            provider_path = root / plan["provider_config_path"]
            provider = json.loads(provider_path.read_text(encoding="utf-8"))
            provider["nested"] = {"credentials": {"api_key": "must-not-be-accepted"}}
            plan["provider_config_sha256"] = write_json(provider_path, provider)
            with self.assertRaisesRegex(runner_module().QuestionSynthesisRunError, "secret"):
                runner_module().validate_execution_plan(plan, root=root)
            plan = execution_plan(root)
            provider_path = root / plan["provider_config_path"]
            provider = json.loads(provider_path.read_text(encoding="utf-8"))
            provider["note"] = "sk-live-123456"
            plan["provider_config_sha256"] = write_json(provider_path, provider)
            with self.assertRaisesRegex(runner_module().QuestionSynthesisRunError, "provider configuration schema"):
                runner_module().validate_execution_plan(plan, root=root)
            for field, value in (
                ("display_name", "sk-live-1234567890abcdef"),
                ("base_url", "https://example.invalid/v1?api_key=literal-credential"),
            ):
                plan = execution_plan(root)
                provider_path = root / plan["provider_config_path"]
                provider = json.loads(provider_path.read_text(encoding="utf-8"))
                provider[field] = value
                plan["provider_config_sha256"] = write_json(provider_path, provider)
                with self.subTest(secret_field=field), self.assertRaisesRegex(
                    runner_module().QuestionSynthesisRunError, "literal secret"
                ):
                    runner_module().validate_execution_plan(plan, root=root)
            plan = execution_plan(root)
            plan["cases"][0]["operational_case_path"] = "operational/%73ealed/answer.json"
            with self.assertRaisesRegex(runner_module().QuestionSynthesisRunError, "sensitive"):
                runner_module().validate_execution_plan(plan, root=root)
            plan = execution_plan(root)
            case_path = root / plan["cases"][0]["operational_case_path"]
            case = json.loads(case_path.read_text(encoding="utf-8"))
            case["nested"] = {"published_answer": "sealed result"}
            plan["cases"][0]["sha256"] = write_json(case_path, case)
            with self.assertRaisesRegex(runner_module().QuestionSynthesisRunError, "hidden or sealed"):
                runner_module().validate_execution_plan(plan, root=root)

    def test_validation_requires_actual_runner_design_and_method_registry_hash_closure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = execution_plan(root)
            plan["tool_version_sha256"] = {"tools/dummy.txt": write_json(root / "tools/dummy.txt", {"dummy": True})}
            with self.assertRaisesRegex(runner_module().QuestionSynthesisRunError, "tool hash closure"):
                runner_module().validate_execution_plan(plan, root=root)
            plan = execution_plan(root)
            plan["source_version_sha256"] = {"sources/dummy.txt": write_json(root / "sources/dummy.txt", {"dummy": True})}
            with self.assertRaisesRegex(runner_module().QuestionSynthesisRunError, "method registry hash closure"):
                runner_module().validate_execution_plan(plan, root=root)

    def test_validation_requires_each_operational_case_to_declare_the_plan_split(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = execution_plan(root)
            case_path = root / plan["cases"][0]["operational_case_path"]
            case = json.loads(case_path.read_text(encoding="utf-8"))
            case.pop("split")
            plan["cases"][0]["sha256"] = write_json(case_path, case)
            with self.assertRaisesRegex(runner_module().QuestionSynthesisRunError, "case split"):
                runner_module().validate_execution_plan(plan, root=root)

    def test_lock_rejects_draft_plan_before_inspecting_receipts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = execution_plan(root)
            plan["status"] = "draft"
            plan["frozen_at_utc"] = None
            plan_path = root / "draft.json"
            write_json(plan_path, plan)
            with self.assertRaisesRegex(runner_module().QuestionSynthesisRunError, "frozen"):
                runner_module().lock_split(plan_path, root / "split.lock.json")

    def test_execute_slot_writes_auditable_receipt_and_matching_resume_makes_no_new_call(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = execution_plan(root)
            provider = FixtureProvider({"answer": "candidate"})
            slot = plan["slots"][0]
            first = runner_module().execute_slot(plan, slot, root=root, provider=provider)
            self.assertEqual(first["status"], "completed")
            self.assertEqual(provider.calls, 1)
            receipt = first["receipt"]
            self.assertEqual(receipt["configuration_id"], "general-model-baseline")
            self.assertEqual(receipt["seed"], 20260820)
            self.assertFalse(receipt["provider_seed_supported"])
            self.assertEqual(receipt["seed_scope"], "orchestration_order_and_tie_breaks")
            self.assertIsNone(receipt["provider_cost"])
            self.assertEqual(receipt["provider_cost_status"], "unknown")
            self.assertEqual(receipt["model_calls"], 1)
            self.assertEqual(receipt["input_tokens"], 11)
            self.assertEqual(receipt["output_tokens"], 7)
            self.assertEqual(receipt["budget_enforcement"], plan["budget_enforcement"])
            self.assertEqual(
                receipt["storage_growth_bytes"],
                (root / slot["output_path"]).stat().st_size
                + (root / slot["receipt_path"]).stat().st_size,
            )
            second = runner_module().execute_slot(plan, slot, root=root, provider=provider)
            self.assertEqual(second["status"], "already_completed")
            self.assertEqual(provider.calls, 1)

    def test_provider_failure_is_receipted_without_persisting_sensitive_error_text(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = execution_plan(root)
            provider = FailingProvider()
            slot = plan["slots"][0]
            completed = runner_module().execute_slot(plan, slot, root=root, provider=provider)
            self.assertEqual(completed["status"], "completed")
            self.assertEqual(completed["receipt"]["status"], "failed")
            self.assertIn("provider_execution_failed", completed["receipt"]["reason_codes"])
            persisted = (root / slot["output_path"]).read_text(encoding="utf-8")
            persisted += (root / slot["receipt_path"]).read_text(encoding="utf-8")
            self.assertNotIn("sensitive-provider-detail", persisted)

    def test_invalid_json_is_a_scientific_slot_failure_and_does_not_stop_the_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = execution_plan(root)
            candidate = {
                "candidate_id": "candidate-1", "review_family": "intervention",
                "synthesis_route": "pairwise_random_effects", "evidence_anchor_ids": ["evidence-1"],
            }
            provider = FirstInvalidThenValidProvider({"candidate": candidate})
            summary = runner_module().execute_plan(plan, root=root, provider_factory=lambda _: provider)
            self.assertFalse(summary["systemic_stop"])
            self.assertEqual(summary["slots"], 15)
            self.assertEqual(summary["failed"], 1)
            first_receipt = json.loads((root / plan["slots"][0]["receipt_path"]).read_text(encoding="utf-8"))
            self.assertEqual(first_receipt["reason_codes"], ["provider_output_invalid"])
            self.assertNotIn("provider_execution_failed", first_receipt["reason_codes"])

    def test_partial_provider_failure_keeps_consumed_usage_and_stops_systemically(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = execution_plan(root)
            slot = next(item for item in plan["slots"] if item["configuration_id"] == "full-biomedical-stack")
            result = runner_module().execute_slot(plan, slot, root=root, provider=PartialFailingProvider({"candidate_id": "x"}))
            self.assertEqual(result["receipt"]["status"], "failed")
            self.assertEqual(result["receipt"]["model_calls"], 1)
            self.assertEqual(result["receipt"]["input_tokens"], 11)
            summary = runner_module().execute_plan(plan, root=root, provider_factory=lambda _: FailingProvider())
            self.assertTrue(summary["systemic_stop"])
            self.assertEqual(summary["successful"], 0)
            self.assertGreaterEqual(summary["failed"], 1)

    def test_wrong_actual_model_failure_preserves_billed_usage_and_stops_systemically(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = execution_plan(root)
            slot = plan["slots"][0]
            provider = WrongModelProvider({"answer": "candidate"})
            result = runner_module().execute_slot(plan, slot, root=root, provider=provider)
            self.assertEqual(provider.calls, 1)
            self.assertEqual(result["receipt"]["status"], "failed")
            self.assertEqual(result["receipt"]["model_calls"], 1)
            self.assertEqual(result["receipt"]["input_tokens"], 11)
            self.assertEqual(result["receipt"]["output_tokens"], 7)
            self.assertIn("provider_model_mismatch", result["receipt"]["reason_codes"])
            summary_plan = execution_plan(root)
            summary = runner_module().execute_plan(
                summary_plan, root=root, provider_factory=lambda _: WrongModelProvider({"answer": "candidate"})
            )
            self.assertTrue(summary["systemic_stop"])

    def test_resume_rejects_minimal_receipt_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = execution_plan(root)
            slot = plan["slots"][0]
            output_sha = write_json(root / slot["output_path"], {"status": "selected"})
            write_json(root / slot["receipt_path"], {"output_sha256": output_sha})
            with self.assertRaisesRegex(runner_module().QuestionSynthesisRunError, "receipt contract"):
                runner_module().resume_slot(plan, slot, root=root)

    def test_full_stack_runs_bounded_same_provider_roles_and_requires_deterministic_hard_verifiers(self) -> None:
        candidate = {
            "candidate_id": "candidate-1",
            "review_family": "intervention",
            "synthesis_route": "pairwise_random_effects",
            "evidence_anchor_ids": ["evidence-1"],
        }
        provider = SequenceProvider([candidate, {"critique": "check"}, {"candidate": candidate}])
        result = runner_module().run_configuration(
            "full-biomedical-stack", operational_case(), seed=SEEDS[0], provider=provider,
            model="deepseek-v4-flash", max_output_tokens=4096,
        )
        self.assertEqual(result["status"], "selected")
        self.assertEqual(provider.calls, 3)
        self.assertEqual(
            {item["verifier_id"]: item["status"] for item in result["verifier_observations"]},
            {"source": "passed", "executable": "passed"},
        )
        self.assertFalse(result["same_provider_roles_are_independent_evidence"])
        bad_candidate = {**candidate, "evidence_anchor_ids": ["not-visible"]}
        bad_provider = SequenceProvider([bad_candidate, {"critique": "check"}, {"candidate": bad_candidate}])
        blocked = runner_module().run_configuration(
            "full-biomedical-stack", operational_case(), seed=SEEDS[0], provider=bad_provider,
            model="deepseek-v4-flash", max_output_tokens=4096,
        )
        self.assertEqual(blocked["status"], "blocked")

    def test_full_stack_does_not_resend_full_material_to_opposition_and_judge(self) -> None:
        case = operational_case()
        case["visible_material"][0]["text"] = "large visible evidence " * 2000
        candidate = {
            "candidate_id": "candidate-1", "review_family": "intervention",
            "synthesis_route": "pairwise_random_effects", "evidence_anchor_ids": ["evidence-1"],
        }
        provider = SequenceProvider([candidate, {"critique": "check"}, {"candidate": candidate}])
        result = runner_module().run_configuration(
            "full-biomedical-stack", case, seed=SEEDS[0], provider=provider,
            model="deepseek-v4-flash", max_output_tokens=4096,
        )
        self.assertEqual(result["status"], "selected")
        user_documents = [json.loads(messages[1]["content"]) for messages in provider.messages]
        self.assertIn("retrieved_visible_material", user_documents[0]["payload"])
        for document in user_documents[1:]:
            self.assertNotIn("retrieved_visible_material", json.dumps(document))
            self.assertIn("proposal_candidate", document)
        self.assertIn("opposition", user_documents[2])
        self.assertLess(
            sum(len(messages[1]["content"]) for messages in provider.messages[1:]),
            len(provider.messages[0][1]["content"]) // 4,
        )

    def test_generic_retrieval_is_call_matched_to_full_stack_deliberation(self) -> None:
        candidate = {"candidate_id": "generic-candidate", "question": "What is the effect?"}
        provider = SequenceProvider([candidate, {"critique": ["check scope"]}, {"candidate": candidate}])
        result = runner_module().run_configuration(
            "generic-retrieval", operational_case(), seed=SEEDS[0], provider=provider,
            model="deepseek-v4-flash", max_output_tokens=4096,
        )
        self.assertEqual(result["status"], "selected")
        self.assertEqual(provider.calls, 3)
        role_documents = [json.loads(messages[1]["content"]) for messages in provider.messages]
        self.assertEqual([document["role"] for document in role_documents], ["proposal", "opposition", "judge"])
        self.assertEqual(
            role_documents[2]["required_response_shape"],
            {"candidate": "complete revised candidate object"},
        )

    def test_full_stack_judge_output_changes_the_candidate_that_hard_verifiers_check(self) -> None:
        proposal = {
            "candidate_id": "candidate-1",
            "review_family": "intervention",
            "synthesis_route": "pairwise_random_effects",
            "evidence_anchor_ids": ["evidence-1"],
        }
        opposition = {"critique": ["route may be unsupported"]}
        judge = {"candidate": {**proposal, "synthesis_route": "unregistered-route"}}
        provider = SequenceProvider([proposal, opposition, judge])
        result = runner_module().run_configuration(
            "full-biomedical-stack", operational_case(), seed=SEEDS[0], provider=provider,
            model="deepseek-v4-flash", max_output_tokens=4096,
        )
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(provider.calls, 3)
        self.assertEqual(
            {item["verifier_id"]: item["status"] for item in result["verifier_observations"]}["executable"],
            "failed",
        )

    def test_full_stack_blocks_when_judge_does_not_return_a_candidate(self) -> None:
        proposal = {
            "candidate_id": "proposal", "review_family": "intervention",
            "synthesis_route": "pairwise_random_effects", "evidence_anchor_ids": ["evidence-1"],
        }
        provider = SequenceProvider([proposal, {"critique": "reject"}, {"decision": "reject"}])
        result = runner_module().run_configuration(
            "full-biomedical-stack", operational_case(), seed=SEEDS[0], provider=provider,
            model="deepseek-v4-flash", max_output_tokens=4096,
        )
        self.assertEqual(provider.calls, 3)
        self.assertEqual(result["status"], "blocked")
        self.assertIn("judge_candidate_missing", result["reason_codes"])

    def test_executed_system_prompt_is_the_frozen_prompt_template(self) -> None:
        provider = FixtureProvider({"answer": "candidate"})
        runner_module().run_configuration(
            "general-model-baseline", operational_case(), seed=SEEDS[0], provider=provider,
            model="deepseek-v4-flash", max_output_tokens=4096,
        )
        self.assertEqual(
            provider.messages[0][0]["content"],
            runner_module().PROMPT_TEMPLATES["general-model-baseline"],
        )

    def test_validate_only_accepts_exact_five_arms_and_never_calls_provider(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = execution_plan(root)
            factory = NeverCalledProviderFactory()
            result = runner_module().execute_plan(plan, root=root, validate_only=True, provider_factory=factory)
            self.assertEqual(result["status"], "validated")
            self.assertEqual(result["slots"], 15)
            self.assertEqual(factory.calls, 0)

    def test_nonzero_retry_budget_is_rejected_until_retries_are_implemented(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = execution_plan(root)
            plan["matched_budget"]["retry_budget"] = 1
            with self.assertRaisesRegex(runner_module().QuestionSynthesisRunError, "retry budget"):
                runner_module().validate_execution_plan(plan, root=root)

    def test_provider_timeout_must_match_the_frozen_enforcement_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = execution_plan(root)
            provider = FixtureProvider({"candidate": {"answer": "x"}})
            provider.timeout_seconds = 30
            with self.assertRaisesRegex(runner_module().QuestionSynthesisRunError, "provider timeout"):
                runner_module().execute_plan(
                    plan, root=root, provider_factory=lambda _: provider
                )
            plan = execution_plan(root)
            provider_path = root / plan["provider_config_path"]
            provider_config = json.loads(provider_path.read_text(encoding="utf-8"))
            provider_config["timeout_seconds"] = 90
            plan["provider_config_sha256"] = write_json(provider_path, provider_config)
            with self.assertRaisesRegex(runner_module().QuestionSynthesisRunError, "configuration timeout"):
                runner_module().validate_execution_plan(plan, root=root)

    def test_provider_factory_failure_is_redacted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = execution_plan(root)

            def fail_factory(config):
                raise RuntimeError("sk-live-sensitive-provider-detail")

            with self.assertRaises(runner_module().QuestionSynthesisRunError) as caught:
                runner_module().execute_plan(plan, root=root, provider_factory=fail_factory)
            self.assertEqual(str(caught.exception), "provider initialization failed")

    def test_full_stack_stops_between_calls_when_wall_budget_is_exhausted(self) -> None:
        provider = SlowProvider({
            "candidate_id": "candidate-1",
            "review_family": "intervention",
            "synthesis_route": "pairwise_random_effects",
            "evidence_anchor_ids": ["evidence-1"],
        })
        result = runner_module().run_configuration(
            "full-biomedical-stack", operational_case(), seed=SEEDS[0], provider=provider,
            model="deepseek-v4-flash", max_output_tokens=4096,
            max_model_calls=3, wall_time_ceiling_seconds=0.005,
        )
        self.assertEqual(provider.calls, 1)
        self.assertEqual(result["status"], "blocked")
        self.assertIn("wall_time_budget_exhausted_before_call", result["reason_codes"])

    def test_validation_rejects_configuration_seed_duplicate_and_missing_slots(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for mutation, message in (("duplicate", "duplicate"), ("missing", "missing")):
                with self.subTest(mutation=mutation):
                    plan = execution_plan(root)
                    if mutation == "duplicate":
                        plan["slots"].append(dict(plan["slots"][0]))
                    else:
                        plan["slots"].pop()
                    with self.assertRaisesRegex(runner_module().QuestionSynthesisRunError, message):
                        runner_module().validate_execution_plan(plan, root=root)

    def test_validation_rejects_case_hash_drift_and_any_sealed_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = execution_plan(root)
            case_path = root / plan["cases"][0]["operational_case_path"]
            case_path.write_text("{}", encoding="utf-8")
            with self.assertRaisesRegex(runner_module().QuestionSynthesisRunError, "case SHA-256 drift"):
                runner_module().validate_execution_plan(plan, root=root)
            plan = execution_plan(root)
            plan["cases"][0]["sealed_case_path"] = "sealed/answer.json"
            with self.assertRaises(runner_module().QuestionSynthesisRunError):
                runner_module().validate_execution_plan(plan, root=root)

    def test_provider_seed_limitation_and_same_provider_nonindependence_are_frozen(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = execution_plan(root)
            runner_module().validate_execution_plan(plan, root=root)
            self.assertFalse(plan["provider_seed_supported"])
            self.assertEqual(plan["seed_scope"], "orchestration_order_and_tie_breaks")
            self.assertFalse(plan["same_provider_roles_are_independent_evidence"])

    def test_lock_requires_all_fifteen_slots_per_case(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = execution_plan(root)
            plan_path = root / "plan.json"
            write_json(plan_path, plan)
            with self.assertRaisesRegex(runner_module().QuestionSynthesisRunError, "15 completed slots"):
                runner_module().lock_split(plan_path, root / "split.lock.json")

    def test_full_stack_failed_source_or_executable_verifier_blocks_without_model_agreement_override(self) -> None:
        result = runner_module().enforce_full_stack_verification(
            {
                "status": "selected",
                "candidate": {"candidate_id": "candidate-1"},
                "verifier_observations": [
                    {"verifier_id": "model_agreement", "status": "passed"},
                    {"verifier_id": "source", "status": "failed"},
                    {"verifier_id": "executable", "status": "passed"},
                ],
            }
        )
        self.assertEqual(result["status"], "blocked")
        self.assertIn("full_stack_hard_verifier_failed", result["reason_codes"])

    def test_ablated_arm_cannot_inherit_full_stack_verifier_evidence(self) -> None:
        result = runner_module().sanitize_arm_result(
            "biomedical-routing",
            {"status": "selected", "verifier_observations": [{"verifier_id": "source", "status": "passed"}]},
        )
        self.assertNotIn("verifier_observations", result)
        self.assertTrue(result["is_ablation"])

    def test_resume_accepts_matching_receipt_but_hash_conflict_never_overwrites(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = execution_plan(root)
            slot = plan["slots"][0]
            output_path = root / slot["output_path"]
            runner_module().execute_slot(plan, slot, root=root, provider=FixtureProvider({"answer": "candidate"}))
            resumed = runner_module().resume_slot(plan, slot, root=root)
            self.assertEqual(resumed["status"], "already_completed")
            output_path.write_text("drift", encoding="utf-8")
            with self.assertRaisesRegex(runner_module().QuestionSynthesisRunError, "output SHA-256 drift"):
                runner_module().resume_slot(plan, slot, root=root)

    def test_resume_rejects_tampered_frozen_execution_constants(self) -> None:
        mutations = {
            "provider_seed_supported": True,
            "seed_scope": "provider_seed",
            "matched_budget": {"max_model_calls": 999},
            "command_argv": ["other"],
        }
        for field, value in mutations.items():
            with self.subTest(field=field), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                plan = execution_plan(root)
                slot = plan["slots"][0]
                runner_module().execute_slot(plan, slot, root=root, provider=FixtureProvider({"answer": "candidate"}))
                receipt_path = root / slot["receipt_path"]
                receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
                receipt[field] = value
                write_json(receipt_path, receipt)
                with self.assertRaisesRegex(runner_module().QuestionSynthesisRunError, "receipt slot/hash drift"):
                    runner_module().resume_slot(plan, slot, root=root)


if __name__ == "__main__":
    unittest.main()
