#!/usr/bin/env python3
"""Audit MetaWingman's lifecycle, review-profile, and synthesis-route coverage."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from metawingman_core.coverage_audit import CoverageAuditError, audit_capability_matrix
from metawingman_core.schema_guard import SchemaValidationError


def main() -> int:
    skill_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "matrix",
        nargs="?",
        type=Path,
        default=skill_root / "references/system-capability-matrix.json",
    )
    parser.add_argument("--skill-root", type=Path, default=skill_root)
    args = parser.parse_args()

    try:
        matrix = json.loads(args.matrix.read_text(encoding="utf-8"))
        result = audit_capability_matrix(matrix, args.skill_root)
    except (OSError, json.JSONDecodeError, CoverageAuditError, SchemaValidationError) as exc:
        result = {"valid": False, "issues": [str(exc)]}

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
