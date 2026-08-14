#!/usr/bin/env python3
"""Verify every file and the aggregate hash in a MetaWingman skill bundle."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any


IGNORED_FILES = {".metawingman-generated", "release-manifest.json"}


class BundleVerificationError(ValueError):
    """Raised when a release bundle does not match its manifest."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_path(bundle: Path, relative: str) -> Path:
    candidate = (bundle / relative).resolve()
    try:
        candidate.relative_to(bundle)
    except ValueError as exc:
        raise BundleVerificationError(f"Manifest path escapes bundle: {relative}") from exc
    return candidate


def _reject_links(root: Path) -> None:
    for path in root.rglob("*"):
        is_junction = bool(getattr(os.path, "isjunction", lambda _: False)(path))
        if path.is_symlink() or is_junction:
            raise BundleVerificationError(
                f"Bundle contains a link or junction: {path.relative_to(root).as_posix()}"
            )


def verify_bundle(bundle_path: Path) -> dict[str, Any]:
    bundle = bundle_path.expanduser().resolve()
    manifest_path = bundle / "release-manifest.json"
    if not manifest_path.is_file():
        raise BundleVerificationError("release-manifest.json is missing")
    _reject_links(bundle)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    entries = manifest.get("files")
    if not isinstance(entries, list):
        raise BundleVerificationError("Manifest files must be an array")

    verified_entries: list[dict[str, Any]] = []
    declared: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
            raise BundleVerificationError("Every manifest file needs a string path")
        relative = entry["path"]
        if relative in declared:
            raise BundleVerificationError(f"Duplicate manifest path: {relative}")
        declared.add(relative)
        path = _safe_path(bundle, relative)
        if not path.is_file():
            raise BundleVerificationError(f"Missing bundle file: {relative}")
        actual_hash = _sha256(path)
        actual_bytes = path.stat().st_size
        if actual_hash != entry.get("sha256") or actual_bytes != entry.get("bytes"):
            raise BundleVerificationError(f"Bundle file differs from manifest: {relative}")
        verified_entries.append({"path": relative, "sha256": actual_hash, "bytes": actual_bytes})

    actual_files = {
        path.relative_to(bundle).as_posix()
        for path in bundle.rglob("*")
        if path.is_file() and path.name not in IGNORED_FILES
    }
    undeclared = sorted(actual_files - declared)
    if undeclared:
        raise BundleVerificationError(f"Undeclared bundle files: {', '.join(undeclared)}")

    aggregate = hashlib.sha256(
        json.dumps(verified_entries, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    if aggregate != manifest.get("source_tree_sha256"):
        raise BundleVerificationError("Aggregate source_tree_sha256 differs from manifest")
    return {
        "valid": True,
        "bundle": str(bundle),
        "files": len(verified_entries),
        "source_tree_sha256": aggregate,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    args = parser.parse_args()
    try:
        result = verify_bundle(args.bundle)
    except (OSError, json.JSONDecodeError, BundleVerificationError) as exc:
        print(json.dumps({"valid": False, "error": str(exc)}, indent=2))
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
