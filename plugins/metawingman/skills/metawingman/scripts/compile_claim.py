#!/usr/bin/env python3
"""Compile one evidence-bounded non-final claim candidate."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from metawingman_core.claim_compiler import ClaimCompileError, compile_claim


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    try:
        output = compile_claim(json.loads(args.candidate.read_text(encoding="utf-8")))
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    except (OSError, json.JSONDecodeError, ClaimCompileError) as exc:
        print(json.dumps({"compiled": False, "error": str(exc)}, indent=2))
        return 1
    print(json.dumps({"compiled": True, "status": output["status"], "out": str(args.out)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
