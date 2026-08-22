#!/usr/bin/env python3
"""Audit the dual-innovation evidence ledger and derive safe claim ceilings."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from metawingman_core.innovation_evidence import (  # noqa: E402
    InnovationEvidenceError,
    audit_innovation_evidence,
)
from metawingman_core.schema_guard import (  # noqa: E402
    SchemaValidationError,
    validate_document,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ledger", type=Path)
    args = parser.parse_args()
    try:
        ledger = json.loads(args.ledger.read_text(encoding="utf-8"))
        validate_document(ledger, "innovation_evidence_ledger")
        result = audit_innovation_evidence(
            ledger, repository_root=Path(__file__).resolve().parents[2],
        )
    except (OSError, json.JSONDecodeError, SchemaValidationError, InnovationEvidenceError) as exc:
        print(json.dumps({"valid": False, "error": str(exc)}, indent=2, ensure_ascii=False))
        return 1
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
