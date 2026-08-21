"""Enumerate compatible synthesis routes for a frozen candidate."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from metawingman_core.state_store import atomic_write_json
from metawingman_core.synthesis_method_router import enumerate_synthesis_routes, load_method_registry


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("context", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--registry", type=Path, default=ROOT / "references" / "question-synthesis-methods.json")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--created-at-utc")
    args = parser.parse_args()
    decision = enumerate_synthesis_routes(
        json.loads(args.context.read_text(encoding="utf-8")),
        json.loads(args.candidate.read_text(encoding="utf-8")),
        load_method_registry(args.registry),
        created_at_utc=args.created_at_utc or datetime.now(timezone.utc).isoformat(),
    )
    atomic_write_json(args.out, decision, "method_route_decision")
    print(json.dumps({"status": decision["status"], "decision_id": decision["decision_id"], "output": str(args.out)}, indent=2))
    return 0 if decision["status"] != "abstained" else 2


if __name__ == "__main__":
    raise SystemExit(main())
