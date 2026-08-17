#!/usr/bin/env python3
"""Score a locked time-split review-topic rediscovery run."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from metawingman_core.topic_rediscovery import TopicRediscoveryError, evaluate_topic_rediscovery


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    try:
        case = json.loads(args.case.read_text(encoding="utf-8"))
        report = evaluate_topic_rediscovery(case)
    except (OSError, json.JSONDecodeError, TopicRediscoveryError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, indent=2))
        return 1
    payload = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
