#!/usr/bin/env python3
"""Audit governed biomedical domain packs against the capability matrix."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from metawingman_core.coverage_audit import audit_biomedical_coverage
from metawingman_core.schema_guard import SchemaValidationError


def main() -> int:
    skill_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--packs",
        type=Path,
        default=skill_root / "references/domain-packs",
    )
    parser.add_argument(
        "--matrix",
        type=Path,
        default=skill_root / "references/system-capability-matrix.json",
    )
    args = parser.parse_args()

    try:
        matrix = json.loads(args.matrix.read_text(encoding="utf-8"))
        result = audit_biomedical_coverage(args.packs, matrix)
    except (OSError, json.JSONDecodeError, SchemaValidationError, ValueError) as exc:
        result = {
            "valid": False,
            "profiles": [],
            "specialties": [],
            "unsupported_combinations": [],
            "issues": [{
                "severity": "error",
                "code": "coverage_audit_failed",
                "message": str(exc),
            }],
        }

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
