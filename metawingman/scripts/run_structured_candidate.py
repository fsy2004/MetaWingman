#!/usr/bin/env python3
"""Run one provider-neutral, schema-gated external-agent candidate task."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from metawingman_core.model_provider import ProviderRequestError
from metawingman_core.provider_factory import build_provider, load_provider_config
from metawingman_core.structured_candidate_runner import (
    StructuredCandidateError,
    run_structured_candidate,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--provider-config", required=True, type=Path)
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--instruction", required=True)
    parser.add_argument("--output-schema", required=True)
    parser.add_argument("--max-input-characters", type=int, default=250_000)
    parser.add_argument("--max-tokens", type=int, default=4096)
    parser.add_argument("--thinking", action="store_true")
    parser.add_argument("--allow-hosted-data-transfer", action="store_true")
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    if not args.allow_hosted_data_transfer:
        print(json.dumps({
            "status": "error",
            "error": "hosted data transfer requires --allow-hosted-data-transfer",
        }, indent=2))
        return 1
    try:
        input_document = json.loads(args.input.read_text(encoding="utf-8"))
        provider = build_provider(load_provider_config(args.provider_config))
        run = run_structured_candidate(
            task_id=args.task_id,
            instruction=args.instruction,
            input_document=input_document,
            output_schema=args.output_schema,
            provider=provider,
            maximum_input_characters=args.max_input_characters,
            max_tokens=args.max_tokens,
            thinking=args.thinking,
        )
    except (OSError, json.JSONDecodeError, ProviderRequestError, StructuredCandidateError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, indent=2))
        return 1
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(run, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": run["status"],
        "task_id": run["task_id"],
        "attempts": run["attempts"],
        "provider_provenance": run["provider_provenance"],
        "out": str(args.out),
    }, indent=2, ensure_ascii=False))
    return 0 if run["status"] == "candidate_generated" else 2


if __name__ == "__main__":
    raise SystemExit(main())
