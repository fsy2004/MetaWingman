#!/usr/bin/env python3
"""Build a bounded observation and report prompt-injection security signals."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from metawingman_core.agent_interface import AgentInterfaceError, build_observation


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifact", type=Path)
    parser.add_argument("--observation-id", required=True)
    parser.add_argument("--task-id", required=True)
    parser.add_argument(
        "--source-type",
        choices=(
            "system_state", "frozen_protocol", "user_artifact", "public_retrieval",
            "licensed_retrieval", "untrusted_document", "tool_output",
        ),
        default="untrusted_document",
    )
    parser.add_argument("--tool", default="local-file-reader")
    parser.add_argument("--tool-version", default="1.0")
    parser.add_argument("--uri")
    parser.add_argument("--media-type", default="text/plain")
    parser.add_argument("--max-bytes", type=int, default=100_000)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    try:
        observation = build_observation(
            observation_id=args.observation_id,
            task_id=args.task_id,
            content=args.artifact.read_bytes(),
            source_type=args.source_type,
            tool=args.tool,
            tool_version=args.tool_version,
            uri=args.uri,
            media_type=args.media_type,
            max_bytes=args.max_bytes,
        )
    except (OSError, AgentInterfaceError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        return 1
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(observation, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(observation, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
