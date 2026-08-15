#!/usr/bin/env python3
"""Resolve an auditable draft biomedical context without hidden clinical inference."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from metawingman_core.biomedical_domain import BiomedicalDomainError, load_domain_packs, resolve_context
from metawingman_core.state_store import atomic_write_json


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("seed", type=Path)
    parser.add_argument("--packs", type=Path, default=Path(__file__).resolve().parents[1] / "references" / "domain-packs")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--created-at-utc")
    args = parser.parse_args()
    now = args.created_at_utc or datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    try:
        seed = json.loads(args.seed.read_text(encoding="utf-8"))
        result = resolve_context(seed, load_domain_packs(args.packs), now)
        atomic_write_json(args.out, result, "biomedical_context")
    except (OSError, json.JSONDecodeError, BiomedicalDomainError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, indent=2))
        return 1
    print(json.dumps({"status": "written", "out": str(args.out), "context_id": result["context_id"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
