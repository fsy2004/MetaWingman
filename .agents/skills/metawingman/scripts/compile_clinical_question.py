"""Compile a source-preserving clinical decision context from JSON."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from metawingman_core.clinical_question import compile_clinical_decision_context
from metawingman_core.state_store import atomic_write_json


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--created-at-utc")
    args = parser.parse_args()
    raw = json.loads(args.input.read_text(encoding="utf-8"))
    compiled = compile_clinical_decision_context(
        raw,
        created_at_utc=args.created_at_utc or datetime.now(timezone.utc).isoformat(),
    )
    atomic_write_json(args.out, compiled, "clinical_decision_context")
    print(json.dumps({"status": compiled["status"], "context_id": compiled["context_id"], "output": str(args.out)}, indent=2))
    return 0 if compiled["status"] == "complete" else 2


if __name__ == "__main__":
    raise SystemExit(main())
