#!/usr/bin/env python3
"""Run a minimal DeepSeek provider probe and emit content-free telemetry by default."""

from __future__ import annotations

import argparse
import json

from metawingman_core.deepseek_provider import DeepSeekProvider, ProviderRequestError


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model")
    parser.add_argument("--list-models", action="store_true")
    parser.add_argument("--include-content", action="store_true")
    args = parser.parse_args()
    try:
        provider = DeepSeekProvider(model=args.model)
        if args.list_models:
            print(json.dumps({"provider": "deepseek", "models": provider.list_models()}, indent=2))
            return 0
        result = provider.chat(
            [
                {"role": "system", "content": "Return valid JSON only."},
                {"role": "user", "content": "Return {\"status\":\"ok\"}."},
            ],
            thinking=False,
            max_tokens=32,
            json_output=True,
        )
        payload = result.audit_record(include_content=args.include_content)
        if args.include_content:
            try:
                payload["content_json_valid"] = isinstance(json.loads(result.content), dict)
            except json.JSONDecodeError:
                payload["content_json_valid"] = False
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0
    except ProviderRequestError as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
