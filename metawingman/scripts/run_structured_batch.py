#!/usr/bin/env python3
"""Run checkpointed provider-neutral structured tasks from a JSONL file."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from metawingman_core.model_provider import ProviderRequestError
from metawingman_core.provider_factory import build_provider, load_provider_config
from metawingman_core.structured_batch import StructuredBatchError, run_structured_batch


def _read_tasks(path: Path) -> list[dict]:
    tasks = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            tasks.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise StructuredBatchError(f"line {line_number}: invalid JSON") from exc
    return tasks


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tasks", type=Path)
    parser.add_argument("--provider-config", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--max-provider-calls", required=True, type=int)
    parser.add_argument("--max-reserved-output-tokens", required=True, type=int)
    parser.add_argument("--max-input-characters", type=int, default=250_000)
    parser.add_argument("--delay-seconds", type=float, default=0.0)
    parser.add_argument("--allow-hosted-data-transfer", action="store_true")
    args = parser.parse_args()
    if not args.allow_hosted_data_transfer:
        print(json.dumps({
            "status": "error",
            "error": "hosted data transfer requires --allow-hosted-data-transfer",
        }, indent=2))
        return 1
    try:
        provider = build_provider(load_provider_config(args.provider_config))
        summary = run_structured_batch(
            _read_tasks(args.tasks),
            provider=provider,
            output_path=args.out,
            maximum_provider_calls=args.max_provider_calls,
            maximum_reserved_output_tokens=args.max_reserved_output_tokens,
            maximum_input_characters=args.max_input_characters,
            delay_seconds=args.delay_seconds,
        )
    except (OSError, ProviderRequestError, StructuredBatchError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, indent=2))
        return 1
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0 if summary["status"] == "completed" and not summary["dead_letters"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
