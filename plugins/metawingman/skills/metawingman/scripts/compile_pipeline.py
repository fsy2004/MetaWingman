#!/usr/bin/env python3
"""Compile a model-pipeline candidate into an immutable local specification."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from metawingman_core.pipeline_compiler import PipelineCompileError, compile_pipeline


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    try:
        candidate = json.loads(args.candidate.read_text(encoding="utf-8"))
        spec = compile_pipeline(candidate, args.root)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(spec, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    except (OSError, json.JSONDecodeError, PipelineCompileError) as exc:
        print(json.dumps({"compiled": False, "error": str(exc)}, indent=2))
        return 1
    print(json.dumps({"compiled": True, "out": str(args.out), "pipeline": spec}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
