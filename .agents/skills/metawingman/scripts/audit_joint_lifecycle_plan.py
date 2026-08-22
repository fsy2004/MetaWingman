#!/usr/bin/env python3
"""Audit a blind joint ten-stage evaluation plan without opening references."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from metawingman_core.joint_lifecycle_evaluation import (  # noqa: E402
    JointLifecyclePlanError,
    audit_joint_lifecycle_plan,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument(
        "--repository-root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
    )
    args = parser.parse_args()
    try:
        plan = json.loads(args.plan.read_text(encoding="utf-8"))
        result = audit_joint_lifecycle_plan(
            plan, repository_root=args.repository_root,
        )
    except (OSError, json.JSONDecodeError, JointLifecyclePlanError) as exc:
        print(json.dumps({
            "schema_valid": False,
            "scientifically_ready": False,
            "status": "invalid",
            "error": str(exc),
        }, indent=2, ensure_ascii=False))
        return 1
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["scientifically_ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
