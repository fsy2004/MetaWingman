#!/usr/bin/env python3
"""Append one validated event to a MetaWingman review ledger."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from metawingman_core.state_store import EventLedger, LedgerError


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ledger", type=Path)
    parser.add_argument("event", type=Path)
    args = parser.parse_args()
    try:
        event = json.loads(args.event.read_text(encoding="utf-8"))
        result = EventLedger(args.ledger).append(event)
    except (OSError, json.JSONDecodeError, LedgerError) as exc:
        print(json.dumps({"recorded": False, "error": str(exc)}, indent=2))
        return 1
    print(json.dumps({"recorded": result.appended, "event": result.event}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
