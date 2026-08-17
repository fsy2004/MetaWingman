#!/usr/bin/env python3
"""Route a validated biomedical context through local governed domain packs."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from metawingman_core.biomedical_domain import BiomedicalDomainError, load_domain_packs, route_domain_packs
from metawingman_core.schema_guard import SchemaValidationError, validate_document
from metawingman_core.state_store import atomic_write_json


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("context", type=Path)
    parser.add_argument("--task-type", required=True)
    parser.add_argument("--risk-class", choices=("low", "moderate", "high", "critical"), required=True)
    parser.add_argument("--packs", type=Path, default=Path(__file__).resolve().parents[1] / "references" / "domain-packs")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--created-at-utc")
    args = parser.parse_args()
    now = args.created_at_utc or datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    try:
        context = json.loads(args.context.read_text(encoding="utf-8"))
        validate_document(context, "biomedical_context")
        result = route_domain_packs(context, load_domain_packs(args.packs), args.task_type, args.risk_class, now)
        atomic_write_json(args.out, result, "domain_routing_decision")
    except (OSError, json.JSONDecodeError, SchemaValidationError, BiomedicalDomainError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, indent=2))
        return 1
    print(json.dumps({"status": result["status"], "out": str(args.out), "decision_id": result["decision_id"]}, indent=2))
    return 2 if result["status"] == "abstained" else 0


if __name__ == "__main__":
    raise SystemExit(main())
