#!/usr/bin/env python3
"""Run the typed risk-impact acquisition loop with a frozen executor adapter."""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from pathlib import Path
from typing import Any, Callable

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from metawingman_core.evidence_acquisition import EvidenceAcquisitionError  # noqa: E402
from metawingman_core.evidence_acquisition_loop import (  # noqa: E402
    execute_evidence_acquisition_loop,
)
from metawingman_core.state_store import atomic_write_json  # noqa: E402


def _load_executor(reference: str) -> Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]]:
    module_name, separator, attribute = reference.partition(":")
    if not separator or not module_name or not attribute:
        raise EvidenceAcquisitionError("executor must use the frozen module:function form")
    module = importlib.import_module(module_name)
    executor = getattr(module, attribute, None)
    if not callable(executor):
        raise EvidenceAcquisitionError("executor binding is not callable")
    return executor


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("initial_state", type=Path)
    parser.add_argument("plan", type=Path)
    parser.add_argument("--executor", required=True, help="Frozen importable module:function adapter")
    parser.add_argument("--created-at-utc", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise EvidenceAcquisitionError("refusing to overwrite an existing acquisition loop result")
    state = json.loads(args.initial_state.read_text(encoding="utf-8"))
    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    result = execute_evidence_acquisition_loop(
        state,
        plan,
        _load_executor(args.executor),
        created_at_utc=args.created_at_utc,
    )
    atomic_write_json(args.out, result, "evidence_acquisition_loop_result")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["status"] == "completed" else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (EvidenceAcquisitionError, ImportError, OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False))
        raise SystemExit(1) from None
