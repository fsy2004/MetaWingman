#!/usr/bin/env python3
"""Probe a configured external provider while emitting content-free telemetry."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from metawingman_core.model_provider import ProviderRequestError
from metawingman_core.provider_factory import build_provider, load_provider_config


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path)
    parser.add_argument("--list-models", action="store_true")
    args = parser.parse_args()
    try:
        provider = build_provider(load_provider_config(args.config))
        if args.list_models:
            payload = {"models": provider.list_models()}
        else:
            result = provider.chat(
                [
                    {"role": "system", "content": "Return valid JSON only."},
                    {"role": "user", "content": "Return {\"status\":\"ok\"}."},
                ],
                max_tokens=32,
                json_output=True,
            )
            payload = result.audit_record()
    except ProviderRequestError as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, indent=2))
        return 1
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
