#!/usr/bin/env python3
"""Run a frozen joint clinical-question and synthesis design configuration."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from metawingman_core.provider_factory import build_provider, load_provider_config
from metawingman_core.question_synthesis_design import design_review_question
from metawingman_core.state_store import atomic_write_json
from metawingman_core.synthesis_method_router import load_method_registry


def _read(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    provider_config = load_provider_config(Path(config["provider_config"]))
    result = design_review_question(
        provider=build_provider(provider_config),
        landscape=_read(config["landscape"]),
        context=_read(config["context"]),
        routes=load_method_registry(Path(config["method_registry"])),
        budget=config["budget"],
        model=provider_config["model"],
        max_tokens=int(config.get("max_tokens", 4096)),
        created_at_utc=config.get("created_at_utc") or datetime.now(timezone.utc).isoformat(),
        role_sequence=list(config.get("role_sequence") or ["proposer", "opposition", "judge"]),
    )
    output = Path(config["output"])
    atomic_write_json(output, result)
    print(json.dumps({"status": result["status"], "output": str(output), "role_calls": len(result.get("role_runs", []))}, indent=2))
    return 0 if result["status"] == "selected" else 2


if __name__ == "__main__":
    raise SystemExit(main())
