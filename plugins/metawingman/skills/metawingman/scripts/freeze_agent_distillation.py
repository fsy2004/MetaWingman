#!/usr/bin/env python3
"""Freeze governed trajectory candidates; this does not train a student model."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from metawingman_core.agent_distillation import DistillationError, freeze_distillation_examples


def _atomic_create_json(path: Path, document: dict[str, object]) -> None:
    """Create a complete export atomically and never replace an existing one."""
    payload = (json.dumps(document, indent=2, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary_path, path)
        except FileExistsError as exc:
            raise DistillationError(f"refusing to overwrite existing export: {path}") from exc
    finally:
        temporary_path.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("traces", type=Path)
    parser.add_argument("--case-registry", type=Path, required=True)
    parser.add_argument("--revocations", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--created-at-utc")
    args = parser.parse_args()
    try:
        traces = [json.loads(line) for line in args.traces.read_text(encoding="utf-8").splitlines() if line.strip()]
        case_registry = json.loads(args.case_registry.read_text(encoding="utf-8"))
        revocation_manifest = (
            json.loads(args.revocations.read_text(encoding="utf-8"))
            if args.revocations is not None
            else None
        )
        result = freeze_distillation_examples(
            traces,
            case_registry=case_registry,
            created_at_utc=args.created_at_utc or datetime.now(timezone.utc).isoformat(),
            revocation_manifest=revocation_manifest,
        )
        _atomic_create_json(args.out, result)
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError, DistillationError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}))
        return 1
    print(json.dumps({"status": "completed", "out": str(args.out), "summary": result["summary"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
