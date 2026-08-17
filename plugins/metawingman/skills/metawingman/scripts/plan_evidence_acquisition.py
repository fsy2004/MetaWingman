#!/usr/bin/env python3
"""Plan the next search, retrieval, or screening action from claim-impact risk."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from metawingman_core.evidence_acquisition import EvidenceAcquisitionError, plan_evidence_acquisition


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("state", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    try:
        state = json.loads(args.state.read_text(encoding="utf-8"))
        decision = plan_evidence_acquisition(state)
    except (OSError, json.JSONDecodeError, EvidenceAcquisitionError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, indent=2))
        return 1
    payload = json.dumps(decision, indent=2, ensure_ascii=False) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")
    return 0 if decision["status"] != "abstain" else 2


if __name__ == "__main__":
    raise SystemExit(main())
