#!/usr/bin/env python3
"""Execute one hash-bound case-arm-seed slot through the ten review stages."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from metawingman_core.joint_lifecycle_runner import (  # noqa: E402
    JointLifecycleRunError,
    execute_joint_lifecycle_slot,
)
from metawingman_core.state_store import atomic_write_json  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("spec", type=Path)
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise JointLifecycleRunError("refusing to overwrite an existing slot result")
    spec = json.loads(args.spec.read_text(encoding="utf-8"))
    result = execute_joint_lifecycle_slot(
        spec,
        repository_root=args.repository_root,
        output_root=args.output_root,
    )
    atomic_write_json(args.out, result, "joint_lifecycle_slot_result")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["status"] == "completed" else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (JointLifecycleRunError, OSError, json.JSONDecodeError, ImportError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False))
        raise SystemExit(1) from None
