#!/usr/bin/env python3
"""Rank evidence-grounded review topics under a frozen temporal policy."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from metawingman_core.topic_opportunity import TopicOpportunityError, select_topic_portfolio


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("landscape", type=Path)
    parser.add_argument("candidates", type=Path, help="JSON array or JSONL topic candidates")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    try:
        landscape = json.loads(args.landscape.read_text(encoding="utf-8"))
        text = args.candidates.read_text(encoding="utf-8")
        if args.candidates.suffix.casefold() == ".jsonl":
            candidates = [json.loads(line) for line in text.splitlines() if line.strip()]
        else:
            candidates = json.loads(text)
        if not isinstance(candidates, list):
            raise TopicOpportunityError("candidate input must be a JSON array or JSONL")
        decision = select_topic_portfolio(landscape, candidates)
    except (OSError, json.JSONDecodeError, TopicOpportunityError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, indent=2))
        return 1
    payload = json.dumps(decision, indent=2, ensure_ascii=False) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")
    return 0 if decision["status"] == "portfolio_selected" else 2


if __name__ == "__main__":
    raise SystemExit(main())
