#!/usr/bin/env python3
"""Fetch immutable benchmark files without exposing sealed answers by default."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
import urllib.error
import urllib.request
from pathlib import Path, PurePosixPath
from typing import Any

from metawingman_core.schema_guard import validate_document
from metawingman_core.network_security import (
    PublicNetworkError,
    public_https_opener,
    validate_public_https_url,
)


class MaterialFetchError(ValueError):
    """Raised when a material plan or fetched artifact is unsafe or inconsistent."""


DEFAULT_MAX_BYTES = 20 * 1024 * 1024
SAFE_ROLES = {"operational_input", "documentation"}
RUN_HASH_FIELDS = {"operational_tree_sha256", "output_sha256", "prompt_sha256"}


def _safe_destination(root: Path, relative: str) -> Path:
    posix = PurePosixPath(relative)
    if posix.is_absolute() or ".." in posix.parts or not posix.parts:
        raise MaterialFetchError(f"unsafe destination path: {relative}")
    destination = (root / Path(*posix.parts)).resolve()
    try:
        destination.relative_to(root.resolve())
    except ValueError as exc:
        raise MaterialFetchError(f"destination escapes output root: {relative}") from exc
    return destination


def select_artifacts(plan: dict[str, Any], unlock_sealed: bool = False) -> list[dict[str, Any]]:
    validate_document(plan, "benchmark_material_plan")
    selected: list[dict[str, Any]] = []
    for artifact in plan["artifacts"]:
        _safe_destination(Path("."), artifact["destination"])
        if artifact["retrieval_policy"] == "fetch_by_default":
            if artifact["role"] not in SAFE_ROLES or artifact["contains_answer"]:
                raise MaterialFetchError(
                    f"{artifact['artifact_id']}: default retrieval cannot expose an answer-bearing or sealed artifact"
                )
            selected.append(artifact)
        elif artifact["retrieval_policy"] == "requires_run_lock" and unlock_sealed:
            selected.append(artifact)
    return selected


def _fetch_one(artifact: dict[str, Any], output_root: Path, max_bytes: int) -> dict[str, Any]:
    expected_bytes = artifact["expected_bytes"]
    if expected_bytes > max_bytes:
        raise MaterialFetchError(
            f"{artifact['artifact_id']}: expected size {expected_bytes} exceeds limit {max_bytes}"
        )
    destination = _safe_destination(output_root, artifact["destination"])
    try:
        source_url = validate_public_https_url(artifact["source_url"])
    except PublicNetworkError as exc:
        raise MaterialFetchError(f"{artifact['artifact_id']}: unsafe retrieval URL: {exc}") from exc
    request = urllib.request.Request(
        source_url, headers={"User-Agent": "MetaWingman-benchmark-fetch/1.0"}
    )
    digest = hashlib.sha256()
    total = 0
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None
    try:
        with public_https_opener().open(request, timeout=60) as response:
            validate_public_https_url(response.geturl())
            with tempfile.NamedTemporaryFile(
                mode="wb", dir=destination.parent, prefix=f".{destination.name}.", delete=False
            ) as handle:
                temp_path = Path(handle.name)
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > max_bytes:
                        raise MaterialFetchError(
                            f"{artifact['artifact_id']}: download exceeded limit {max_bytes}"
                        )
                    digest.update(chunk)
                    handle.write(chunk)
        actual_sha256 = digest.hexdigest()
        if total != expected_bytes:
            raise MaterialFetchError(
                f"{artifact['artifact_id']}: byte mismatch, expected {expected_bytes}, got {total}"
            )
        if actual_sha256 != artifact["expected_sha256"]:
            raise MaterialFetchError(
                f"{artifact['artifact_id']}: SHA-256 mismatch, expected {artifact['expected_sha256']}, got {actual_sha256}"
            )
        os.replace(temp_path, destination)
        temp_path = None
    except (OSError, urllib.error.URLError, PublicNetworkError) as exc:
        raise MaterialFetchError(f"{artifact['artifact_id']}: retrieval failed: {exc}") from exc
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
    return {
        "artifact_id": artifact["artifact_id"],
        "path": str(destination),
        "bytes": total,
        "sha256": artifact["expected_sha256"],
        "role": artifact["role"],
    }


def fetch_plan(
    plan: dict[str, Any], output_root: Path, *, unlock_sealed: bool = False,
    run_boundary: dict[str, Any] | None = None,
    max_bytes: int = DEFAULT_MAX_BYTES, dry_run: bool = False,
) -> dict[str, Any]:
    if max_bytes < 1:
        raise MaterialFetchError("max_bytes must be positive")
    if unlock_sealed:
        if run_boundary is None:
            raise MaterialFetchError("sealed retrieval requires a validated run boundary")
        validate_completed_run_boundary_document(run_boundary, plan)
    selected = select_artifacts(plan, unlock_sealed=unlock_sealed)
    if dry_run:
        return {
            "pack_id": plan["pack_id"],
            "dry_run": True,
            "selected": [item["artifact_id"] for item in selected],
            "sealed_unlocked": unlock_sealed,
        }
    records = [_fetch_one(item, output_root, max_bytes) for item in selected]
    receipt = {
        "schema_version": "1.0",
        "pack_id": plan["pack_id"],
        "sealed_unlocked": unlock_sealed,
        "artifacts": records,
    }
    receipt_path = output_root / plan["pack_id"] / "fetch-receipt.json"
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return receipt


def validate_completed_run_boundary_document(
    boundary: dict[str, Any], plan: dict[str, Any]
) -> dict[str, Any]:
    if not isinstance(boundary, dict) or boundary.get("run_state") != "locked":
        raise MaterialFetchError("sealed retrieval requires a fully locked RUN_BOUNDARY.json")
    benchmark_id = boundary.get("benchmark_id")
    if benchmark_id not in plan.get("candidate_ids", []):
        raise MaterialFetchError("run-lock benchmark_id is not registered in this material plan")
    expected = boundary.get("expected_runs")
    locks = boundary.get("run_locks")
    if not isinstance(expected, int) or expected < 1 or not isinstance(locks, list):
        raise MaterialFetchError("run-lock boundary has invalid expected_runs or run_locks")
    if len(locks) != expected:
        raise MaterialFetchError("all preregistered runs must be locked before sealed retrieval")
    seen: set[tuple[str, int]] = set()
    for lock in locks:
        if not isinstance(lock, dict):
            raise MaterialFetchError("run-lock entry must be an object")
        if lock.get("execution_mode") != "ai_only" or lock.get("human_interventions") != 0:
            raise MaterialFetchError("run-lock entry violates the AI-only execution boundary")
        key = (str(lock.get("configuration_id") or ""), lock.get("repetition_index"))
        if not key[0] or not isinstance(key[1], int) or key in seen:
            raise MaterialFetchError("run-lock entries need unique configuration repetitions")
        seen.add(key)
        for field in RUN_HASH_FIELDS:
            value = lock.get(field)
            if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
                raise MaterialFetchError(f"run-lock entry has invalid {field}")
        if not lock.get("model_versions") or not lock.get("tool_versions"):
            raise MaterialFetchError("run-lock entry must identify model and tool versions")
    return boundary


def validate_completed_run_boundary(path: Path, plan: dict[str, Any]) -> dict[str, Any]:
    try:
        boundary = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MaterialFetchError(f"invalid run-lock boundary: {exc}") from exc
    return validate_completed_run_boundary_document(boundary, plan)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--unlock-sealed", action="store_true")
    parser.add_argument("--run-lock", type=Path)
    parser.add_argument("--max-bytes", type=int, default=DEFAULT_MAX_BYTES)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        plan = json.loads(args.plan.read_text(encoding="utf-8"))
        run_boundary = None
        if args.unlock_sealed:
            if args.run_lock is None or not args.run_lock.is_file():
                raise MaterialFetchError("--unlock-sealed requires an existing --run-lock artifact")
            run_boundary = validate_completed_run_boundary(args.run_lock, plan)
        result = fetch_plan(
            plan, args.out.resolve(), unlock_sealed=args.unlock_sealed,
            run_boundary=run_boundary,
            max_bytes=args.max_bytes, dry_run=args.dry_run,
        )
    except (OSError, json.JSONDecodeError, MaterialFetchError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        return 1
    print(json.dumps({"ok": True, "result": result}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
