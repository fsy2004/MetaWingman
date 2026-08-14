"""Compile a versioned pipeline manifest with immutable local artifacts."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .schema_guard import SchemaValidationError, load_schema, validate_document
from .state_store import sha256_json


COMPILER_VERSION = "1.0"
DEFAULT_LOSS_WEIGHTS = {
    "false_exclusion": 20.0,
    "false_inclusion": 2.0,
    "unsupported_value": 15.0,
    "incorrect_value": 10.0,
    "unanchored_claim": 15.0,
    "unauthorized_action": 25.0,
    "missed_required_abstention": 12.0,
    "unnecessary_abstention": 1.0,
}
DEFAULT_RELEASE_GATES = {
    "max_mean_loss": 1.0,
    "max_critical_error_rate": 0.0,
    "repeat_k": 3,
    "min_pass_power_k": 0.90,
    "max_position_gap": 0.05,
    "max_judge_order_disagreement": 0.05,
}


class PipelineCompileError(ValueError):
    """Raised when a pipeline cannot be compiled without leakage or drift."""


def _resolve_artifact(root: Path, value: str) -> tuple[str, str]:
    path = (root / value).resolve()
    try:
        relative = path.relative_to(root)
    except ValueError as exc:
        raise PipelineCompileError(f"Pipeline artifact escapes project root: {value}") from exc
    if not path.is_file():
        raise PipelineCompileError(f"Pipeline artifact is missing: {relative.as_posix()}")
    return relative.as_posix(), hashlib.sha256(path.read_bytes()).hexdigest()


def _validate_split_policy(policy: dict[str, Any]) -> None:
    split_sets = {
        name: set(policy[f"{name}_family_ids"])
        for name in ("train", "dev", "test")
    }
    for first, second in (("train", "dev"), ("train", "test"), ("dev", "test")):
        overlap = sorted(split_sets[first] & split_sets[second])
        if overlap:
            raise PipelineCompileError(
                f"review-family leakage between {first} and {second}: {', '.join(overlap)}"
            )
    if not split_sets["dev"] or not split_sets["test"]:
        raise PipelineCompileError("dev and test review-family splits must both be non-empty")


def compile_pipeline(candidate: dict[str, Any], root: Path) -> dict[str, Any]:
    root = root.resolve()
    modules = candidate.get("modules")
    if not isinstance(modules, list) or not modules:
        raise PipelineCompileError("candidate.modules must be a non-empty list")
    policy = candidate.get("split_policy")
    if not isinstance(policy, dict):
        raise PipelineCompileError("candidate.split_policy must be an object")
    policy = {"unit": "review_family_id", **policy}
    _validate_split_policy(policy)
    train = set(policy["train_family_ids"])
    held_out = set(policy["dev_family_ids"]) | set(policy["test_family_ids"])

    compiled_modules: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for raw in modules:
        if not isinstance(raw, dict):
            raise PipelineCompileError("Every pipeline module must be an object")
        module_id = str(raw.get("module_id") or "")
        if not module_id or module_id in seen_ids:
            raise PipelineCompileError(f"Missing or duplicate module_id: {module_id!r}")
        seen_ids.add(module_id)
        prompt_path, prompt_hash = _resolve_artifact(root, str(raw.get("prompt_path") or ""))
        config_value = raw.get("config_path")
        if config_value:
            config_path, config_hash = _resolve_artifact(root, str(config_value))
        else:
            config_path, config_hash = None, None
        optimization_ids = list(raw.get("optimization_family_ids") or [])
        leaked = sorted(set(optimization_ids) & held_out)
        unknown = sorted(set(optimization_ids) - train)
        if leaked:
            raise PipelineCompileError(
                f"module {module_id} optimization uses held-out review families: {', '.join(leaked)}"
            )
        if unknown:
            raise PipelineCompileError(
                f"module {module_id} optimization families are not assigned to train: {', '.join(unknown)}"
            )
        for schema_name in (raw.get("input_schema"), raw.get("output_schema")):
            try:
                load_schema(str(schema_name))
            except FileNotFoundError as exc:
                raise PipelineCompileError(str(exc)) from exc
        compiled_modules.append({
            "module_id": module_id,
            "version": str(raw.get("version") or ""),
            "compiler_version": COMPILER_VERSION,
            "prompt_path": prompt_path,
            "prompt_sha256": prompt_hash,
            "config_path": config_path,
            "config_sha256": config_hash,
            "input_schema": str(raw["input_schema"]),
            "output_schema": str(raw["output_schema"]),
            "model_capability": str(raw.get("model_capability") or ""),
            "optimization_family_ids": optimization_ids,
        })

    spec = {
        "schema_version": "1.0",
        "pipeline_id": str(candidate.get("pipeline_id") or ""),
        "pipeline_version": str(candidate.get("pipeline_version") or ""),
        "task_type": str(candidate.get("task_type") or ""),
        "modules": compiled_modules,
        "split_policy": policy,
        "loss_weights": {**DEFAULT_LOSS_WEIGHTS, **(candidate.get("loss_weights") or {})},
        "release_gates": {**DEFAULT_RELEASE_GATES, **(candidate.get("release_gates") or {})},
        "compiler": {
            "name": "metawingman-pipeline-compiler",
            "version": COMPILER_VERSION,
            "candidate_sha256": sha256_json(candidate),
        },
        "created_at_utc": str(candidate.get("created_at_utc") or datetime.now(timezone.utc).isoformat()),
    }
    try:
        validate_document(spec, "pipeline_spec")
    except SchemaValidationError as exc:
        raise PipelineCompileError(str(exc)) from exc
    return spec
