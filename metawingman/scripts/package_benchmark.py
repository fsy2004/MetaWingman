#!/usr/bin/env python3
"""Build or lock a blind published-review reconstruction benchmark."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from metawingman_core.benchmark_packager import (
    BenchmarkPackageError,
    build_benchmark_package,
    lock_benchmark_run,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build")
    build.add_argument("candidate", type=Path)
    build.add_argument("--out", type=Path, required=True)
    lock = sub.add_parser("lock")
    lock.add_argument("package", type=Path)
    lock.add_argument("run", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "build":
            output = build_benchmark_package(
                json.loads(args.candidate.read_text(encoding="utf-8")), args.out
            )
        else:
            output = lock_benchmark_run(
                args.package, json.loads(args.run.read_text(encoding="utf-8"))
            )
    except (OSError, json.JSONDecodeError, BenchmarkPackageError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        return 1
    print(json.dumps({"ok": True, "result": output}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
