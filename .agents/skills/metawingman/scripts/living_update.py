#!/usr/bin/env python3
"""Build or compare local living-review source snapshots."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from metawingman_core.living_update import LivingUpdateError, build_snapshot, compare_snapshots
from metawingman_core.provenance_graph import ProvenanceGraph


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("snapshot")
    build.add_argument("candidate", type=Path)
    build.add_argument("--out", type=Path, required=True)
    delta = sub.add_parser("delta")
    delta.add_argument("previous", type=Path)
    delta.add_argument("current", type=Path)
    delta.add_argument("--delta-id", required=True)
    delta.add_argument("--graph", type=Path)
    delta.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "snapshot":
            output = build_snapshot(json.loads(args.candidate.read_text(encoding="utf-8")))
        else:
            previous = json.loads(args.previous.read_text(encoding="utf-8"))
            current = json.loads(args.current.read_text(encoding="utf-8"))
            if args.graph:
                with ProvenanceGraph(args.graph) as graph:
                    output = compare_snapshots(previous, current, delta_id=args.delta_id, graph=graph)
            else:
                output = compare_snapshots(previous, current, delta_id=args.delta_id)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    except (OSError, json.JSONDecodeError, LivingUpdateError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        return 1
    print(json.dumps({"ok": True, "status": output.get("status"), "out": str(args.out)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
