#!/usr/bin/env python3
"""Audit whether frozen agent trajectories are safe to enter student training."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from metawingman_core.distillation_readiness import (  # noqa: E402
    DistillationReadinessError,
    audit_distillation_readiness,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--export", dest="exports", type=Path, action="append", default=[],
        help="Frozen agent-distillation export; repeat for multiple exports.",
    )
    parser.add_argument("--case-registry", type=Path, required=True)
    parser.add_argument("--lineage-manifest", type=Path)
    parser.add_argument("--revocation-manifest", type=Path)
    parser.add_argument(
        "--artifact-root", type=Path,
        help="Root for all relative and absolute artifact bindings (defaults to registry directory).",
    )
    args = parser.parse_args()
    try:
        report = audit_distillation_readiness(
            export_paths=args.exports,
            case_registry_path=args.case_registry,
            lineage_manifest_path=args.lineage_manifest,
            revocation_manifest_path=args.revocation_manifest,
            artifact_root=args.artifact_root,
        )
    except DistillationReadinessError as exc:
        print(json.dumps({
            "audit_status": "invalid",
            "ready_for_student_training": False,
            "error": str(exc),
        }, indent=2, ensure_ascii=False))
        return 1
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["ready_for_student_training"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
