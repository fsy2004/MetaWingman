#!/usr/bin/env python3
"""Freeze, validate, execute, resume, or lock a five-arm question-synthesis plan."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from metawingman_core.question_synthesis_runner import (
    QuestionSynthesisRunError,
    execute_plan,
    freeze_execution_plan,
    lock_split,
)


def _read(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise QuestionSynthesisRunError(f"cannot read plan JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise QuestionSynthesisRunError("plan must be a JSON object")
    return value


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    freeze = commands.add_parser("freeze", help="freeze a complete draft without provider calls")
    freeze.add_argument("plan", type=Path)
    freeze.add_argument("--out", type=Path, required=True)
    freeze.add_argument("--frozen-at-utc")
    validate = commands.add_parser("validate-only", help="verify hashes, slots, and boundaries only")
    validate.add_argument("plan", type=Path)
    execute = commands.add_parser("execute", help="execute or safely resume every frozen slot")
    execute.add_argument("plan", type=Path)
    lock = commands.add_parser("lock", help="lock a split after every 15-slot case is complete")
    lock.add_argument("plan", type=Path)
    lock.add_argument("--out", type=Path, required=True)
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        if args.command == "freeze":
            plan = freeze_execution_plan(
                args.plan,
                args.out,
                frozen_at_utc=args.frozen_at_utc,
            )
            result = {"status": plan["status"], "out": str(args.out)}
        elif args.command == "lock":
            result = lock_split(args.plan, args.out)
        else:
            plan = _read(args.plan)
            root = args.plan.resolve().parent
            if args.command == "validate-only":
                result = execute_plan(plan, root=root, validate_only=True)
            else:
                from metawingman_core.provider_factory import build_provider

                result = execute_plan(
                    plan,
                    root=root,
                    validate_only=False,
                    provider_factory=build_provider,
                )
    except QuestionSynthesisRunError as exc:
        print(json.dumps({"status": "blocked", "error": str(exc)}, indent=2))
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
