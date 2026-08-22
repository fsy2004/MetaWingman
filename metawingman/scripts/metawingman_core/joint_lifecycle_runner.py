"""Execute one frozen case-arm-seed slot through all ten review stages.

The preregistration auditor proves that a receipt grid is complete.  This module
is the complementary execution boundary: it loads hash-bound scientific stage
adapters, keeps sealed reference locators out of their requests, meters every
provider call before the side effect, chains stage manifests, and stops at the
first failed or abstained stage.
"""

from __future__ import annotations

import copy
import hashlib
import importlib
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .joint_lifecycle_evaluation import CANONICAL_STAGE_IDS
from .model_provider import ProviderRequestError, ProviderResult
from .schema_guard import SchemaValidationError, validate_document
from .state_store import atomic_write_json, sha256_json


StageAdapter = Callable[[dict[str, Any], "AtomicStageBudgetMeter"], dict[str, Any]]
AdapterLoader = Callable[[str], StageAdapter]


class JointLifecycleRunError(ValueError):
    """Raised before execution when a frozen binding or safety gate is invalid."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _resolve_bound_file(root: Path, binding: dict[str, Any], label: str) -> Path:
    value = binding.get("path")
    expected = binding.get("sha256")
    if not isinstance(value, str) or not isinstance(expected, str):
        raise JointLifecycleRunError(f"{label} binding is incomplete")
    path = (root / value).resolve(strict=False)
    try:
        path.relative_to(root.resolve(strict=False))
    except ValueError as exc:
        raise JointLifecycleRunError(f"{label} path is outside the repository") from exc
    if not path.is_file():
        raise JointLifecycleRunError(f"{label} file is missing")
    if _sha256(path) != expected:
        raise JointLifecycleRunError(f"{label} hash drift")
    return path


def _load_adapter(reference: str) -> StageAdapter:
    module_name, separator, attribute = reference.partition(":")
    if not separator or not module_name or not attribute:
        raise JointLifecycleRunError("stage adapter must use module:function form")
    module = importlib.import_module(module_name)
    adapter = getattr(module, attribute, None)
    if not callable(adapter):
        raise JointLifecycleRunError(f"stage adapter is not callable: {reference}")
    return adapter


def _forbidden_reference_locator(value: Any) -> bool:
    forbidden_keys = {
        "published_expert_reference",
        "published_reference_path",
        "sealed_reference_path",
        "reference_locator",
        "published_answer",
        "target_doi",
        "target_title",
        "target_authors",
    }
    forbidden_path_fragments = ("sealed_reference", "published_reference")
    if isinstance(value, dict):
        for key, item in value.items():
            normalized = str(key).strip().lower().replace("-", "_")
            if normalized in forbidden_keys:
                return True
            if _forbidden_reference_locator(item):
                return True
        return False
    if isinstance(value, list):
        return any(_forbidden_reference_locator(item) for item in value)
    if isinstance(value, str):
        normalized = value.replace("\\", "/").lower()
        return any(fragment in normalized for fragment in forbidden_path_fragments)
    return False


@dataclass(frozen=True)
class _ProviderLease:
    lease_id: int
    max_input_tokens: int
    max_output_tokens: int


class AtomicStageBudgetMeter:
    """Reserve call and token capacity before an adapter performs a provider call."""

    def __init__(self, allocation: dict[str, Any]):
        self._limits = dict(allocation)
        self._next_lease = 1
        self._open: dict[int, _ProviderLease] = {}
        self._calls = 0
        self._input_tokens = 0
        self._output_tokens = 0
        self._reserved_input = 0
        self._reserved_output = 0
        self._cost_statuses: list[str] = []
        self._cost_values: list[float] = []
        self._currency: str | None = None

    @staticmethod
    def _nonnegative_int(value: Any, label: str) -> int:
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise JointLifecycleRunError(f"{label} must be a non-negative integer")
        return value

    def before_provider_call(
        self, *, max_input_tokens: int, max_output_tokens: int,
    ) -> _ProviderLease:
        """Atomically reserve the worst-case call budget before the side effect."""
        max_input_tokens = self._nonnegative_int(max_input_tokens, "max_input_tokens")
        max_output_tokens = self._nonnegative_int(max_output_tokens, "max_output_tokens")
        if self._calls + len(self._open) + 1 > self._limits["max_provider_calls"]:
            raise JointLifecycleRunError("provider-call budget precheck failed")
        if self._input_tokens + self._reserved_input + max_input_tokens > self._limits["max_input_tokens"]:
            raise JointLifecycleRunError("input-token budget precheck failed")
        if self._output_tokens + self._reserved_output + max_output_tokens > self._limits["max_output_tokens"]:
            raise JointLifecycleRunError("output-token budget precheck failed")
        lease = _ProviderLease(self._next_lease, max_input_tokens, max_output_tokens)
        self._next_lease += 1
        self._open[lease.lease_id] = lease
        self._reserved_input += max_input_tokens
        self._reserved_output += max_output_tokens
        return lease

    def after_provider_call(
        self,
        lease: _ProviderLease,
        *,
        input_tokens: int,
        output_tokens: int,
        cost_status: str,
        cost_value: float | int | None,
        currency: str | None,
    ) -> None:
        """Settle one reserved call using observed provider telemetry."""
        current = self._open.get(getattr(lease, "lease_id", -1))
        if current != lease:
            raise JointLifecycleRunError("provider lease is unknown or already settled")
        input_tokens = self._nonnegative_int(input_tokens, "input_tokens")
        output_tokens = self._nonnegative_int(output_tokens, "output_tokens")
        if input_tokens > lease.max_input_tokens or output_tokens > lease.max_output_tokens:
            raise JointLifecycleRunError("observed tokens exceed the pre-call reservation")
        if cost_status not in {"known", "unknown"}:
            raise JointLifecycleRunError("provider call cost must be known or explicitly unknown")
        if cost_status == "known":
            if isinstance(cost_value, bool) or not isinstance(cost_value, (int, float)) or cost_value < 0:
                raise JointLifecycleRunError("known provider cost requires a non-negative value")
            if not isinstance(currency, str) or len(currency) != 3 or currency.upper() != currency:
                raise JointLifecycleRunError("known provider cost requires an ISO currency")
            if self._currency is not None and self._currency != currency:
                raise JointLifecycleRunError("one stage cannot aggregate multiple cost currencies")
            self._currency = currency
            self._cost_values.append(float(cost_value))
        elif cost_value is not None or currency is not None:
            raise JointLifecycleRunError("unknown provider cost must keep value and currency null")
        self._open.pop(lease.lease_id)
        self._reserved_input -= lease.max_input_tokens
        self._reserved_output -= lease.max_output_tokens
        self._calls += 1
        self._input_tokens += input_tokens
        self._output_tokens += output_tokens
        self._cost_statuses.append(cost_status)

    def resource_usage(self, wall_seconds: float) -> dict[str, Any]:
        if self._open:
            raise JointLifecycleRunError("provider call lease was not settled")
        if self._calls == 0:
            cost = {"status": "not_applicable", "value": None, "currency": None}
        elif "unknown" in self._cost_statuses:
            cost = {"status": "unknown", "value": None, "currency": None}
        else:
            cost = {
                "status": "known",
                "value": round(sum(self._cost_values), 8),
                "currency": self._currency,
            }
        return {
            "provider_calls": {"status": "observed", "value": self._calls},
            "input_tokens": {"status": "observed", "value": self._input_tokens},
            "output_tokens": {"status": "observed", "value": self._output_tokens},
            "wall_seconds": {"status": "observed", "value": round(max(0.0, wall_seconds), 8)},
            "cost": cost,
        }


class MeteredModelProvider:
    """Wrap a provider so every chat call is reserved before network execution."""

    def __init__(
        self,
        delegate: Any,
        meter: AtomicStageBudgetMeter,
        *,
        max_input_tokens_per_call: int,
    ):
        if max_input_tokens_per_call < 1:
            raise JointLifecycleRunError("max_input_tokens_per_call must be positive")
        self._delegate = delegate
        self._meter = meter
        self._max_input_tokens_per_call = max_input_tokens_per_call
        self.credential_source = getattr(delegate, "credential_source", "unknown")

    def list_models(self) -> list[str]:
        raise ProviderRequestError("model discovery is prohibited inside a frozen stage run")

    def chat(
        self,
        messages: Any,
        *,
        model: str | None = None,
        thinking: bool = False,
        reasoning_effort: str = "low",
        max_tokens: int = 128,
        json_output: bool = False,
    ) -> ProviderResult:
        lease = self._meter.before_provider_call(
            max_input_tokens=self._max_input_tokens_per_call,
            max_output_tokens=max_tokens,
        )
        # An exception deliberately leaves the lease open.  The slot runner then
        # aborts without inventing zero usage for an indeterminate network call.
        result = self._delegate.chat(
            messages,
            model=model,
            thinking=thinking,
            reasoning_effort=reasoning_effort,
            max_tokens=max_tokens,
            json_output=json_output,
        )
        if (
            isinstance(result.prompt_tokens, bool)
            or not isinstance(result.prompt_tokens, int)
            or result.prompt_tokens < 0
            or isinstance(result.completion_tokens, bool)
            or not isinstance(result.completion_tokens, int)
            or result.completion_tokens < 0
        ):
            raise JointLifecycleRunError(
                "provider response lacks observed prompt/completion token counts"
            )
        self._meter.after_provider_call(
            lease,
            input_tokens=result.prompt_tokens,
            output_tokens=result.completion_tokens,
            cost_status="unknown",
            cost_value=None,
            currency=None,
        )
        return result


def _verify_plan_preconditions(
    plan: dict[str, Any], *, root: Path, case_slot_id: str, arm_id: str, seed: int,
) -> tuple[
    dict[str, Any], dict[str, Any], str, list[dict[str, str]], list[dict[str, str]],
]:
    try:
        validate_document(plan, "joint_lifecycle_evaluation_plan")
    except SchemaValidationError as exc:
        raise JointLifecycleRunError(str(exc)) from exc
    if plan["published_reference_gate"]["state"] != "sealed":
        raise JointLifecycleRunError("published reference must remain sealed during execution")
    if plan["published_reference_gate"]["reference_locator_in_operational_plan"] is not False:
        raise JointLifecycleRunError("published reference locator is exposed")
    if tuple(item["stage_id"] for item in plan["lifecycle_stages"]) != CANONICAL_STAGE_IDS:
        raise JointLifecycleRunError("evaluation plan does not use the canonical ten-stage order")
    execution_blockers = [
        item["prerequisite_id"] for item in plan["scientific_prerequisites"]
        if item["required_for"] in {"execution", "both"}
        and item["status"] != "satisfied"
    ]
    if execution_blockers:
        raise JointLifecycleRunError(
            "scientific execution prerequisites are not satisfied: "
            + ",".join(execution_blockers)
        )
    budget = plan["evaluation_design"]["matched_budget"]
    if budget["status"] != "frozen" or any(
        budget[field] is None or budget[field] <= 0
        for field in ("max_provider_calls", "max_input_tokens", "max_output_tokens", "wall_seconds")
    ):
        raise JointLifecycleRunError("matched execution budget is not frozen")

    topic_inputs: list[dict[str, str]] = []
    for binding in plan["topic_protocol_inputs"]:
        if binding["status"] != "locked":
            raise JointLifecycleRunError(f"topic input is not locked: {binding['binding_id']}")
        path = _resolve_bound_file(root, binding, f"topic input {binding['binding_id']}")
        topic_inputs.append({
            "binding_id": binding["binding_id"],
            "path": path.relative_to(root).as_posix(),
            "sha256": binding["sha256"],
        })

    case = next((item for item in plan["cases"] if item["case_slot_id"] == case_slot_id), None)
    if case is None or case["admission_status"] != "admitted":
        raise JointLifecycleRunError("case slot is not admitted")
    if case["prior_target_exposure_status"] != "none":
        raise JointLifecycleRunError("case target-exposure closure is not clean")
    if case["version_graph"]["status"] != "locked":
        raise JointLifecycleRunError("case version graph is not locked")
    operational_inputs: list[dict[str, str]] = []
    for node in case["version_graph"]["nodes"]:
        role = node["role"]
        if role in {"published_article", "published_conclusions"}:
            if node["status"] != "sealed_locked" or node["path"] is not None:
                raise JointLifecycleRunError("sealed reference locator is exposed in the case graph")
            continue
        binding = {"path": node["path"], "sha256": node["sha256"]}
        path = _resolve_bound_file(root, binding, f"case operational input {role}")
        operational_inputs.append({
            "role": role,
            "path": path.relative_to(root).as_posix(),
            "sha256": node["sha256"],
        })

    closure = next(
        (item for item in plan["family_closures"] if item["case_slot_id"] == case_slot_id), None,
    )
    if (
        closure is None or closure["status"] != "locked"
        or closure["review_family_id"] != case["review_family_id"]
        or closure["dependency_closure_sha256"] is None
    ):
        raise JointLifecycleRunError("review-family closure is not locked")

    arm = next((item for item in plan["evaluation_design"]["arms"] if item["arm_id"] == arm_id), None)
    if arm is None:
        raise JointLifecycleRunError("evaluation arm is not registered")
    if arm["runner_binding"]["status"] != "locked":
        raise JointLifecycleRunError("evaluation arm runner is not locked")
    _resolve_bound_file(root, arm["runner_binding"], f"arm runner {arm_id}")
    if seed not in plan["seeds"]:
        raise JointLifecycleRunError("seed is not preregistered")
    checkpoints = sorted(
        (item for item in plan["checkpoint_records"] if item["seed"] == seed),
        key=lambda item: item["role"],
    )
    if len(checkpoints) != 2 or any(item["status"] != "locked" for item in checkpoints):
        raise JointLifecycleRunError("seed-specific checkpoints are not locked")
    checkpoint_manifest: list[dict[str, str]] = []
    for item in checkpoints:
        path = _resolve_bound_file(
            root,
            {"path": item["artifact_path"], "sha256": item["artifact_sha256"]},
            f"checkpoint {item['checkpoint_id']}",
        )
        checkpoint_manifest.append({
            "role": item["role"], "path": path.relative_to(root).as_posix(),
            "sha256": item["artifact_sha256"],
            "training_manifest_sha256": item["training_manifest_sha256"],
            "family_manifest_sha256": item["family_manifest_sha256"],
        })
    return case, arm, sha256_json(checkpoint_manifest), operational_inputs, topic_inputs


def _validate_stage_bindings(
    spec: dict[str, Any], *, root: Path, matched_budget: dict[str, Any],
) -> list[tuple[dict[str, Any], Path, Path, dict[str, Any]]]:
    stages = spec["stages"]
    if tuple(item["stage_id"] for item in stages) != CANONICAL_STAGE_IDS:
        raise JointLifecycleRunError("slot execution must use the canonical ten-stage order")
    if tuple(item["ordinal"] for item in stages) != tuple(range(10)):
        raise JointLifecycleRunError("slot execution ordinals must be zero through nine")
    totals = {
        field: sum(item["budget_allocation"][field] for item in stages)
        for field in ("max_provider_calls", "max_input_tokens", "max_output_tokens", "wall_seconds")
    }
    plan_fields = {
        "max_provider_calls": "max_provider_calls",
        "max_input_tokens": "max_input_tokens",
        "max_output_tokens": "max_output_tokens",
        "wall_seconds": "wall_seconds",
    }
    for field, plan_field in plan_fields.items():
        if totals[field] > matched_budget[plan_field]:
            raise JointLifecycleRunError(f"stage allocations exceed matched budget: {field}")

    verified: list[tuple[dict[str, Any], Path, Path, dict[str, Any]]] = []
    for stage in stages:
        adapter_path = _resolve_bound_file(
            root, stage["adapter"], f"stage adapter {stage['stage_id']}",
        )
        config_path = _resolve_bound_file(
            root, stage["config"], f"stage config {stage['stage_id']}",
        )
        try:
            config = json.loads(config_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise JointLifecycleRunError(f"stage config is not valid JSON: {stage['stage_id']}") from exc
        if _forbidden_reference_locator(config):
            raise JointLifecycleRunError(
                f"stage config exposes a sealed reference locator: {stage['stage_id']}"
            )
        verified.append((stage, adapter_path, config_path, config))
    return verified


def _verify_stage_output(
    raw: dict[str, Any], *, stage_id: str, stage_dir: Path,
    required_check_ids: set[str],
) -> dict[str, Any]:
    try:
        validate_document(raw, "joint_lifecycle_stage_output")
    except SchemaValidationError as exc:
        raise JointLifecycleRunError(str(exc)) from exc
    if raw["stage_id"] != stage_id:
        raise JointLifecycleRunError("stage adapter returned the wrong stage_id")
    artifact_ids: set[str] = set()
    artifacts: list[dict[str, Any]] = []
    for binding in raw["artifacts"]:
        artifact_id = binding["artifact_id"]
        if artifact_id in artifact_ids:
            raise JointLifecycleRunError("stage adapter returned duplicate artifact_id")
        path = Path(binding["path"]).resolve(strict=False)
        try:
            path.relative_to(stage_dir.resolve(strict=False))
        except ValueError as exc:
            raise JointLifecycleRunError("stage artifact is outside the stage output directory") from exc
        if not path.is_file() or _sha256(path) != binding["sha256"]:
            raise JointLifecycleRunError("stage artifact is missing or has hash drift")
        artifact_ids.add(artifact_id)
        artifacts.append({**binding, "path": str(path)})
    if raw["state_artifact_id"] not in artifact_ids:
        raise JointLifecycleRunError("state_artifact_id is not bound to a stage artifact")
    for check in raw["scientific_checks"]:
        if not set(check["evidence_artifact_ids"]).issubset(artifact_ids):
            raise JointLifecycleRunError("scientific check references an unknown artifact")
    observed_check_ids = {check["check_id"] for check in raw["scientific_checks"]}
    missing_checks = sorted(required_check_ids - observed_check_ids)
    if missing_checks:
        raise JointLifecycleRunError(
            "required scientific checks are missing: " + ",".join(missing_checks)
        )
    if raw["status"] == "completed" and any(
        check["status"] != "passed" for check in raw["scientific_checks"]
    ):
        raise JointLifecycleRunError("completed stage has a failed or abstained scientific check")
    return {**raw, "artifacts": artifacts}


def _required_scientific_checks(stage_id: str, arm: dict[str, Any]) -> set[str]:
    if stage_id == "topic_feasibility":
        return {
            "direct_candidate_generation",
            (
                "decision_opportunity_control"
                if arm["topic_opportunity_control"]
                else "generic_candidate_generation"
            ),
        }
    if stage_id == "search_retrieval":
        return {
            "search_reproducible",
            (
                "risk_impact_action_execute_replan"
                if arm["conclusion_risk_impact_control"]
                else "fixed_acquisition"
            ),
        }
    check_id = {
        "protocol_registration": "protocol_frozen",
        "selection": "selection_complete",
        "data_lineage": "report_study_result_lineage_complete",
        "appraisal": "appraisal_and_missing_evidence_complete",
        "freeze_synthesis": "analysis_freeze_and_synthesis_complete",
        "certainty_interpretation": "certainty_and_claims_complete",
        "reporting_review": "reporting_and_review_complete",
        "living_update": "living_update_plan_complete",
    }[stage_id]
    return {check_id}


def _resource_totals(stage_results: list[dict[str, Any]]) -> dict[str, Any]:
    usages = [item["receipt"]["resource_usage"] for item in stage_results]
    cost_records = [item["cost"] for item in usages]
    if any(item["status"] == "unknown" for item in cost_records):
        cost = {"status": "unknown", "value": None, "currency": None}
    else:
        known = [item for item in cost_records if item["status"] == "known"]
        if known:
            currencies = {item["currency"] for item in known}
            if len(currencies) != 1:
                raise JointLifecycleRunError("slot cannot aggregate multiple cost currencies")
            cost = {
                "status": "known",
                "value": round(sum(float(item["value"]) for item in known), 8),
                "currency": next(iter(currencies)),
            }
        else:
            cost = {"status": "not_applicable", "value": None, "currency": None}
    return {
        "provider_calls": sum(item["provider_calls"]["value"] for item in usages),
        "input_tokens": sum(item["input_tokens"]["value"] for item in usages),
        "output_tokens": sum(item["output_tokens"]["value"] for item in usages),
        "wall_seconds": round(sum(item["wall_seconds"]["value"] for item in usages), 8),
        "cost": cost,
    }


def execute_joint_lifecycle_slot(
    spec: dict[str, Any],
    *,
    repository_root: Path,
    output_root: Path,
    adapter_loader: AdapterLoader | None = None,
) -> dict[str, Any]:
    """Run exactly one preregistered case-arm-seed slot and return stage receipts."""
    try:
        validate_document(spec, "joint_lifecycle_slot_execution")
    except SchemaValidationError as exc:
        raise JointLifecycleRunError(str(exc)) from exc
    if _forbidden_reference_locator(spec):
        raise JointLifecycleRunError("slot specification exposes a sealed reference locator")
    root = repository_root.resolve(strict=True)
    plan_path = _resolve_bound_file(root, spec["evaluation_plan"], "evaluation plan")
    try:
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise JointLifecycleRunError("evaluation plan is not valid JSON") from exc
    case, arm, checkpoint_sha256, operational_inputs, topic_inputs = _verify_plan_preconditions(
        plan,
        root=root,
        case_slot_id=spec["case_slot_id"],
        arm_id=spec["arm_id"],
        seed=spec["seed"],
    )
    stages = _validate_stage_bindings(
        spec,
        root=root,
        matched_budget=plan["evaluation_design"]["matched_budget"],
    )
    execution_root = output_root.resolve(strict=False) / spec["execution_id"]
    if execution_root.exists():
        raise JointLifecycleRunError("refusing to overwrite an existing slot execution")
    execution_root.mkdir(parents=True)
    loader = adapter_loader or _load_adapter
    stage_results: list[dict[str, Any]] = []
    previous_output_sha: str | None = None
    previous_output_path: Path | None = None

    for stage, adapter_path, config_path, config in stages:
        stage_id = stage["stage_id"]
        stage_dir = execution_root / f"{stage['ordinal']:02d}-{stage_id}"
        stage_dir.mkdir()
        input_manifest = {
            "schema_version": "1.0",
            "execution_id": spec["execution_id"],
            "case_slot_id": spec["case_slot_id"],
            "case_id": case["case_id"],
            "review_family_id": case["review_family_id"],
            "arm_id": spec["arm_id"],
            "seed": spec["seed"],
            "stage_id": stage_id,
            "ordinal": stage["ordinal"],
            "evaluation_plan_sha256": spec["evaluation_plan"]["sha256"],
            "checkpoint_sha256": checkpoint_sha256,
            "adapter_sha256": stage["adapter"]["sha256"],
            "config_sha256": stage["config"]["sha256"],
            "previous_output_manifest_sha256": previous_output_sha,
            "operational_inputs": operational_inputs,
            "topic_inputs": topic_inputs,
            "topic_opportunity_control": arm["topic_opportunity_control"],
            "conclusion_risk_impact_control": arm["conclusion_risk_impact_control"],
            "candidate_generation_mode": arm["candidate_generation_mode"],
            "acquisition_mode": arm["acquisition_mode"],
            "published_reference_accessed": False,
        }
        input_path = stage_dir / "input-manifest.json"
        atomic_write_json(input_path, input_manifest)
        input_sha = _sha256(input_path)
        meter = AtomicStageBudgetMeter(stage["budget_allocation"])
        request = {
            "execution_id": spec["execution_id"],
            "case_slot_id": spec["case_slot_id"],
            "case_id": case["case_id"],
            "review_family_id": case["review_family_id"],
            "arm_id": spec["arm_id"],
            "seed": spec["seed"],
            "stage_id": stage_id,
            "ordinal": stage["ordinal"],
            "stage_output_dir": str(stage_dir),
            "repository_root": str(root),
            "created_at_utc": spec["created_at_utc"],
            "input_manifest_path": str(input_path),
            "input_manifest_sha256": input_sha,
            "previous_output_manifest_sha256": previous_output_sha,
            "previous_output_manifest_path": (
                str(previous_output_path) if previous_output_path is not None else None
            ),
            "config_path": str(config_path),
            "config": config,
            "operational_inputs": operational_inputs,
            "topic_inputs": topic_inputs,
            "topic_opportunity_control": arm["topic_opportunity_control"],
            "conclusion_risk_impact_control": arm["conclusion_risk_impact_control"],
            "candidate_generation_mode": arm["candidate_generation_mode"],
            "acquisition_mode": arm["acquisition_mode"],
            "published_reference_accessed": False,
        }
        started = time.monotonic()
        output_path: Path | None = None
        output_sha: str | None = None
        try:
            raw = loader(stage["adapter"]["module_function"])(request, meter)
            elapsed = time.monotonic() - started
            usage = meter.resource_usage(elapsed)
            if elapsed > stage["budget_allocation"]["wall_seconds"]:
                raise JointLifecycleRunError("stage wall-time budget exceeded")
            verified_output = _verify_stage_output(
                raw,
                stage_id=stage_id,
                stage_dir=stage_dir,
                required_check_ids=_required_scientific_checks(stage_id, arm),
            )
            output_manifest = {
                "schema_version": "1.0",
                "execution_id": spec["execution_id"],
                "stage_id": stage_id,
                "ordinal": stage["ordinal"],
                "input_manifest_sha256": input_sha,
                "adapter_path": str(adapter_path),
                "adapter_sha256": stage["adapter"]["sha256"],
                "config_sha256": stage["config"]["sha256"],
                "stage_output": verified_output,
                "resource_usage": usage,
                "published_reference_accessed": False,
            }
            output_path = stage_dir / "output-manifest.json"
            atomic_write_json(output_path, output_manifest)
            output_sha = _sha256(output_path)
            stage_status = "locked" if verified_output["status"] == "completed" else verified_output["status"]
            terminal_reason = verified_output["terminal_reason"]
        except Exception as exc:
            elapsed = time.monotonic() - started
            try:
                usage = meter.resource_usage(elapsed)
            except JointLifecycleRunError as meter_error:
                raise JointLifecycleRunError(
                    "unsettled provider lease prevents truthful resource accounting"
                ) from meter_error
            stage_status = "failed"
            terminal_reason = f"adapter_error:{exc}"

        receipt = {
            "case_slot_id": spec["case_slot_id"],
            "arm_id": spec["arm_id"],
            "seed": spec["seed"],
            "stage_id": stage_id,
            "status": stage_status,
            "checkpoint_sha256": checkpoint_sha256,
            "input_manifest_sha256": input_sha,
            "output_manifest_sha256": output_sha,
            "resource_usage": usage,
        }
        stage_result = {
            "ordinal": stage["ordinal"],
            "stage_id": stage_id,
            "status": stage_status,
            "terminal_reason": terminal_reason,
            "input_manifest_path": str(input_path),
            "input_manifest_sha256": input_sha,
            "output_manifest_path": str(output_path) if output_path is not None else None,
            "output_manifest_sha256": output_sha,
            "receipt": receipt,
        }
        stage_results.append(stage_result)
        if stage_status != "locked":
            break
        previous_output_sha = output_sha
        previous_output_path = output_path

    final_status = (
        "completed" if len(stage_results) == 10 and stage_results[-1]["status"] == "locked"
        else "abstained" if stage_results[-1]["status"] == "abstained"
        else "failed"
    )
    result = {
        "schema_version": "1.0",
        "execution_id": spec["execution_id"],
        "evaluation_plan_sha256": spec["evaluation_plan"]["sha256"],
        "case_slot_id": spec["case_slot_id"],
        "arm_id": spec["arm_id"],
        "seed": spec["seed"],
        "status": final_status,
        "terminal_reason": None if final_status == "completed" else stage_results[-1]["terminal_reason"],
        "stage_results": stage_results,
        "resource_totals": _resource_totals(stage_results),
        "published_reference_accessed": False,
        "created_at_utc": spec["created_at_utc"],
    }
    try:
        validate_document(result, "joint_lifecycle_slot_result")
    except SchemaValidationError as exc:
        raise JointLifecycleRunError(str(exc)) from exc
    return result


def assemble_joint_lifecycle_receipts(
    evaluation_plan_path: Path,
    slot_result_paths: list[Path],
    *,
    repository_root: Path,
) -> dict[str, Any]:
    """Verify immutable slot manifests and assemble a new plan state.

    The frozen preregistration file is an input only.  Callers must write the
    returned document to a distinct path, so accumulating receipts cannot alter
    the preregistered scientific decisions or expose a sealed reference.
    """
    root = repository_root.resolve(strict=True)
    plan_path = evaluation_plan_path.resolve(strict=True)
    try:
        plan_path.relative_to(root)
    except ValueError as exc:
        raise JointLifecycleRunError("evaluation plan is outside the repository") from exc
    try:
        base_plan = json.loads(plan_path.read_text(encoding="utf-8"))
        validate_document(base_plan, "joint_lifecycle_evaluation_plan")
    except (OSError, json.JSONDecodeError, SchemaValidationError) as exc:
        raise JointLifecycleRunError(f"cannot load the frozen evaluation plan: {exc}") from exc
    if base_plan["stage_receipts"]:
        raise JointLifecycleRunError("receipt assembly requires the immutable zero-receipt base plan")
    if base_plan["published_reference_gate"]["state"] != "sealed":
        raise JointLifecycleRunError("receipt assembly cannot start from an unsealed plan")
    base_sha = _sha256(plan_path)
    case_order = {item["case_slot_id"]: index for index, item in enumerate(base_plan["cases"])}
    arm_order = {
        item["arm_id"]: index
        for index, item in enumerate(base_plan["evaluation_design"]["arms"])
    }
    seed_order = {seed: index for index, seed in enumerate(base_plan["seeds"])}
    stage_order = {stage_id: index for index, stage_id in enumerate(CANONICAL_STAGE_IDS)}
    expected_slots = {
        (case_id, arm_id, seed)
        for case_id in case_order for arm_id in arm_order for seed in seed_order
    }
    seen_slots: set[tuple[str, str, int]] = set()
    receipts: list[dict[str, Any]] = []

    for result_path in slot_result_paths:
        try:
            result = json.loads(result_path.read_text(encoding="utf-8"))
            validate_document(result, "joint_lifecycle_slot_result")
        except (OSError, json.JSONDecodeError, SchemaValidationError) as exc:
            raise JointLifecycleRunError(f"invalid slot result {result_path}: {exc}") from exc
        if result["evaluation_plan_sha256"] != base_sha:
            raise JointLifecycleRunError("slot result does not bind the frozen evaluation plan")
        slot = (result["case_slot_id"], result["arm_id"], result["seed"])
        if slot not in expected_slots:
            raise JointLifecycleRunError("slot result identity is not preregistered")
        if slot in seen_slots:
            raise JointLifecycleRunError("duplicate slot result")
        seen_slots.add(slot)
        stage_results = result["stage_results"]
        observed_stage_ids = tuple(item["stage_id"] for item in stage_results)
        if observed_stage_ids != CANONICAL_STAGE_IDS[:len(stage_results)]:
            raise JointLifecycleRunError("slot result stages are not a canonical prefix")
        if tuple(item["ordinal"] for item in stage_results) != tuple(range(len(stage_results))):
            raise JointLifecycleRunError("slot result ordinals are not canonical")
        if result["status"] == "completed" and not (
            len(stage_results) == 10 and all(item["status"] == "locked" for item in stage_results)
        ):
            raise JointLifecycleRunError("completed slot does not contain ten locked stages")
        if result["status"] != "completed" and (
            stage_results[-1]["status"] != result["status"]
            or any(item["status"] != "locked" for item in stage_results[:-1])
        ):
            raise JointLifecycleRunError("terminal slot status is inconsistent with its stage prefix")

        for stage_result in stage_results:
            input_path = Path(stage_result["input_manifest_path"])
            if not input_path.is_file() or _sha256(input_path) != stage_result["input_manifest_sha256"]:
                raise JointLifecycleRunError("slot input manifest hash drift")
            output_value = stage_result["output_manifest_path"]
            output_sha = stage_result["output_manifest_sha256"]
            if output_value is None:
                if output_sha is not None or stage_result["status"] == "locked":
                    raise JointLifecycleRunError("locked stage is missing its output manifest")
            else:
                output_path = Path(output_value)
                if not output_path.is_file() or _sha256(output_path) != output_sha:
                    raise JointLifecycleRunError("slot output manifest hash drift")
            receipt = copy.deepcopy(stage_result["receipt"])
            if (
                receipt["case_slot_id"] != slot[0]
                or receipt["arm_id"] != slot[1]
                or receipt["seed"] != slot[2]
                or receipt["stage_id"] != stage_result["stage_id"]
                or receipt["status"] != stage_result["status"]
                or receipt["input_manifest_sha256"] != stage_result["input_manifest_sha256"]
                or receipt["output_manifest_sha256"] != output_sha
            ):
                raise JointLifecycleRunError("stage receipt does not match the verified slot manifest")
            receipts.append(receipt)

    receipts.sort(key=lambda item: (
        case_order[item["case_slot_id"]],
        arm_order[item["arm_id"]],
        seed_order[item["seed"]],
        stage_order[item["stage_id"]],
    ))
    expected_receipt_count = len(expected_slots) * len(CANONICAL_STAGE_IDS)
    all_locked = (
        len(receipts) == expected_receipt_count
        and len(seen_slots) == len(expected_slots)
        and all(item["status"] == "locked" for item in receipts)
    )
    derived = copy.deepcopy(base_plan)
    derived["stage_receipts"] = receipts
    derived["plan_status"] = (
        "all_stage_receipts_locked" if all_locked else "execution_in_progress"
    )
    # Receipt assembly never performs the separate controller-only unseal action.
    derived["published_reference_gate"]["state"] = "sealed"
    derived["published_reference_gate"]["unsealed_at_utc"] = None
    try:
        validate_document(derived, "joint_lifecycle_evaluation_plan")
    except SchemaValidationError as exc:
        raise JointLifecycleRunError(str(exc)) from exc
    return derived
