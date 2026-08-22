#!/usr/bin/env python3
"""Assemble verified slot results into a derived joint-lifecycle plan state."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from metawingman_core.joint_lifecycle_runner import (  # noqa: E402
    JointLifecycleRunError,
    assemble_joint_lifecycle_receipts,
)
from metawingman_core.state_store import atomic_write_json  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evaluation_plan", type=Path)
    parser.add_argument("slot_results", nargs="+", type=Path)
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise JointLifecycleRunError("refusing to overwrite an existing derived plan")
    derived = assemble_joint_lifecycle_receipts(
        args.evaluation_plan,
        args.slot_results,
        repository_root=args.repository_root,
    )
    atomic_write_json(args.out, derived, "joint_lifecycle_evaluation_plan")
    print(json.dumps({
        "status": derived["plan_status"],
        "stage_receipts": len(derived["stage_receipts"]),
        "published_reference_gate": derived["published_reference_gate"]["state"],
        "out": str(args.out),
    }, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (JointLifecycleRunError, OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False))
        raise SystemExit(1) from None
