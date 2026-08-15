"""Checkpointed, budget-bounded batch execution for structured Agent candidates."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Callable, Iterable

from .model_provider import ModelProvider
from .schema_guard import SchemaValidationError, validate_document, validate_jsonl_file
from .state_store import StateStoreError, append_jsonl_record, sha256_json
from .structured_candidate_runner import StructuredCandidateError, run_structured_candidate


class StructuredBatchError(ValueError):
    """Raised when a batch definition or checkpoint is invalid."""


def run_structured_batch(
    tasks: Iterable[dict[str, Any]],
    *,
    provider: ModelProvider,
    output_path: Path,
    maximum_provider_calls: int,
    maximum_reserved_output_tokens: int,
    maximum_input_characters: int = 250_000,
    delay_seconds: float = 0.0,
    sleeper: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    """Resume a JSONL batch while reserving worst-case repair calls and output tokens."""
    if maximum_provider_calls < 2 or maximum_reserved_output_tokens < 2:
        raise StructuredBatchError("batch budgets must permit one initial call and one repair")
    if delay_seconds < 0:
        raise StructuredBatchError("delay_seconds must be non-negative")
    task_list = list(tasks)
    task_ids: set[str] = set()
    for task in task_list:
        try:
            validate_document(task, "external_agent_batch_task")
        except SchemaValidationError as exc:
            raise StructuredBatchError(str(exc)) from exc
        if task["task_id"] in task_ids:
            raise StructuredBatchError(f"duplicate task_id in batch: {task['task_id']}")
        task_ids.add(task["task_id"])
    try:
        existing = validate_jsonl_file(output_path, "external_agent_candidate_run")
    except SchemaValidationError as exc:
        raise StructuredBatchError(str(exc)) from exc
    completed_ids = {run["task_id"] for run in existing}
    provider_calls = sum(run["attempts"] for run in existing)
    reserved_output_consumed = sum(
        run["attempts"] * run["request_budget"]["max_tokens_per_call"]
        for run in existing
    )
    maximum_reserved_output_tokens -= reserved_output_consumed
    if maximum_reserved_output_tokens < 0:
        raise StructuredBatchError("existing checkpoint exceeds reserved output-token budget")
    observed_total_tokens: int | None = 0
    for run in existing:
        value = run["usage_totals"]["total_tokens"]
        if value is None or observed_total_tokens is None:
            observed_total_tokens = None
        else:
            observed_total_tokens += value
    processed = 0
    resumed = sum(task["task_id"] in completed_ids for task in task_list)
    dead_letters: list[dict[str, Any]] = []
    stop_reason = "completed"
    for task in task_list:
        if task["task_id"] in completed_ids:
            continue
        reserved_calls = 2
        reserved_output = 2 * task["max_tokens"]
        if provider_calls + reserved_calls > maximum_provider_calls:
            stop_reason = "provider_call_budget_reserved"
            break
        if reserved_output > maximum_reserved_output_tokens:
            stop_reason = "output_token_budget_reserved"
            break
        run: dict[str, Any] | None = None
        try:
            run = run_structured_candidate(
                task_id=task["task_id"],
                instruction=task["instruction"],
                input_document=task["input_document"],
                output_schema=task["output_schema"],
                provider=provider,
                maximum_input_characters=maximum_input_characters,
                max_tokens=task["max_tokens"],
                thinking=task["thinking"],
            )
            append_jsonl_record(
                output_path,
                run,
                "external_agent_candidate_run",
                unique_fields=("task_id",),
            )
        except (StructuredCandidateError, StateStoreError) as exc:
            charged_attempts = run["attempts"] if run is not None else reserved_calls
            provider_calls += charged_attempts
            maximum_reserved_output_tokens -= charged_attempts * task["max_tokens"]
            dead_letters.append({
                "task_id": task["task_id"],
                "task_sha256": sha256_json(task),
                "error_type": type(exc).__name__,
            })
            continue
        provider_calls += run["attempts"]
        maximum_reserved_output_tokens -= run["attempts"] * task["max_tokens"]
        total_tokens = run["usage_totals"]["total_tokens"]
        if observed_total_tokens is not None and total_tokens is not None:
            observed_total_tokens += total_tokens
        else:
            observed_total_tokens = None
        completed_ids.add(task["task_id"])
        processed += 1
        if delay_seconds and processed < len(task_list) - resumed:
            sleeper(delay_seconds)
    return {
        "status": "completed" if stop_reason == "completed" else "budget_stopped",
        "stop_reason": stop_reason,
        "tasks": len(task_list),
        "processed": processed,
        "resumed": resumed,
        "dead_letters": dead_letters,
        "provider_calls_in_checkpoint": provider_calls,
        "observed_total_tokens": observed_total_tokens,
        "remaining_reserved_output_tokens": maximum_reserved_output_tokens,
    }
