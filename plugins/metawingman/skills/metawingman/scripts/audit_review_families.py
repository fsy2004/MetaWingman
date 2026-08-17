#!/usr/bin/env python3
"""Audit review-family candidate edges with human decisions and emit held-out candidates."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from metawingman_core.review_family import ReviewFamilyError, audit_review_families
from metawingman_core.state_store import atomic_write_json


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("registry", type=Path)
    parser.add_argument("corpus", type=Path)
    parser.add_argument("--decisions", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    try:
        registry = json.loads(args.registry.read_text(encoding="utf-8"))
        corpus = json.loads(args.corpus.read_text(encoding="utf-8"))
        decisions = [
            json.loads(line)
            for line in args.decisions.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        report = audit_review_families(registry, corpus, decisions)
    except (OSError, json.JSONDecodeError, ReviewFamilyError, ValueError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        return 1
    atomic_write_json(args.out, report, "family_audit_report")
    print(json.dumps({"ok": True, "out": str(args.out), "summary": report["summary"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
