#!/usr/bin/env python3
"""Inspect or mutate a MetaWingman provenance graph through typed JSON."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from metawingman_core.provenance_graph import GraphError, ProvenanceGraph


def _read_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object in {path}")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("database", type=Path)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("init")
    add_node = subparsers.add_parser("add-node")
    add_node.add_argument("document", type=Path)
    add_edge = subparsers.add_parser("add-edge")
    add_edge.add_argument("document", type=Path)
    node = subparsers.add_parser("node")
    node.add_argument("node_type")
    node.add_argument("node_id")
    neighbors = subparsers.add_parser("neighbors")
    neighbors.add_argument("node_type")
    neighbors.add_argument("node_id")
    neighbors.add_argument("--direction", choices=("in", "out", "both"), default="both")
    neighbors.add_argument("--status", action="append", default=[])
    neighbors.add_argument("--relationship")
    path = subparsers.add_parser("path")
    path.add_argument("source_type")
    path.add_argument("source_id")
    path.add_argument("target_type")
    path.add_argument("target_id")
    path.add_argument("--direction", choices=("in", "out", "both"), default="out")
    path.add_argument("--max-depth", type=int, default=20)
    impact = subparsers.add_parser("impact")
    impact.add_argument("node_type")
    impact.add_argument("node_id")
    impact.add_argument("--max-depth", type=int, default=20)
    subparsers.add_parser("stats")
    subparsers.add_parser("verify")
    args = parser.parse_args()

    try:
        with ProvenanceGraph(args.database) as graph:
            if args.command == "init":
                result = {"initialized": True, "database": str(graph.path)}
            elif args.command == "add-node":
                result = graph.add_node(_read_json(args.document)).__dict__
            elif args.command == "add-edge":
                result = graph.add_edge(_read_json(args.document)).__dict__
            elif args.command == "node":
                result = graph.get_node(args.node_type, args.node_id)
                if result is None:
                    raise GraphError(f"Unknown node: {args.node_type}:{args.node_id}")
            elif args.command == "neighbors":
                result = graph.neighbors(
                    args.node_type,
                    args.node_id,
                    args.direction,
                    args.status or ("accepted",),
                    args.relationship,
                )
            elif args.command == "path":
                result = graph.shortest_path(
                    args.source_type,
                    args.source_id,
                    args.target_type,
                    args.target_id,
                    args.direction,
                    max_depth=args.max_depth,
                )
            elif args.command == "impact":
                result = graph.impact(args.node_type, args.node_id, args.max_depth)
            elif args.command == "stats":
                result = graph.statistics()
            else:
                issues = graph.verify()
                result = {"valid": not issues, "issues": issues, **graph.statistics()}
                print(json.dumps(result, indent=2, ensure_ascii=False))
                return 0 if not issues else 2
    except (OSError, ValueError, json.JSONDecodeError, GraphError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2, ensure_ascii=False))
        return 1
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
