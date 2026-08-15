#!/usr/bin/env python3
"""Build identical repo-scoped and plugin MetaWingman skill bundles."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any


BUILDER_VERSION = "1.0"
GENERATED_MARKER = ".metawingman-generated"
EXCLUDED_NAMES = {
    "__pycache__", ".DS_Store", "release-manifest.json", GENERATED_MARKER,
    "validation-output",
}
EXCLUDED_SUFFIXES = {".pyc", ".pyo", ".tmp"}
SKILL_EXCLUDED_PATHS = {
    "references/deepseek-provider-config.json",
    "references/deepseek-model-registry.template.json",
    "references/provider-config.template.json",
    "scripts/configure_provider_secret.py",
    "scripts/probe_deepseek.py",
    "scripts/probe_provider.py",
    "scripts/propose_topics.py",
    "scripts/run_structured_candidate.py",
    "scripts/run_structured_batch.py",
    "scripts/metawingman_core/deepseek_provider.py",
    "scripts/metawingman_core/model_provider.py",
    "scripts/metawingman_core/openai_compatible_provider.py",
    "scripts/metawingman_core/provider_factory.py",
    "scripts/metawingman_core/provider_secrets.py",
    "scripts/metawingman_core/structured_candidate_runner.py",
    "scripts/metawingman_core/structured_batch.py",
    "scripts/metawingman_core/topic_proposer.py",
}
TEXT_SUFFIXES = {
    "", ".cff", ".csv", ".json", ".md", ".py", ".r", ".txt", ".yaml", ".yml",
}
SECRET_PATTERNS = (
    re.compile(r"(?i)(api[_-]?key|token|password|secret)\s*[:=]\s*['\"]?[A-Za-z0-9_\-]{12,}"),
    re.compile(r"gh[opusr]_[A-Za-z0-9]{20,}"),
)
AUTHOR_PATH_PATTERNS = (
    re.compile(r"(?i)[A-Z]:\\Users\\[^\\\s]+\\"),
    re.compile(r"/Users/[^/\s]+/"),
    re.compile(r"/home/[^/\s]+/"),
)


class BundleBuildError(ValueError):
    """Raised when a bundle cannot be built without unsafe or drifting content."""


def _assert_source_tree_safe(source: Path) -> None:
    root = source.resolve()
    for path in source.rglob("*"):
        is_junction = bool(getattr(os.path, "isjunction", lambda _: False)(path))
        if path.is_symlink() or is_junction:
            raise BundleBuildError(f"source tree contains a link or junction: {path.relative_to(source)}")
        try:
            path.resolve().relative_to(root)
        except ValueError as exc:
            raise BundleBuildError(f"source path escapes canonical tree: {path}") from exc


def _ignore(_: str, names: list[str]) -> set[str]:
    return {
        name for name in names
        if name in EXCLUDED_NAMES or Path(name).suffix.casefold() in EXCLUDED_SUFFIXES
    }


def _hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _files(root: Path) -> list[dict[str, Any]]:
    output = []
    for path in sorted((item for item in root.rglob("*") if item.is_file()), key=lambda item: item.relative_to(root).as_posix()):
        if path.name in {"release-manifest.json", GENERATED_MARKER}:
            continue
        output.append({
            "path": path.relative_to(root).as_posix(),
            "sha256": _hash(path),
            "bytes": path.stat().st_size,
        })
    return output


def _scan_text(root: Path) -> None:
    issues: list[str] = []
    for path in (item for item in root.rglob("*") if item.is_file() and item.stat().st_size <= 5_000_000):
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        relative = path.relative_to(root).as_posix()
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                issues.append(f"possible secret in {relative}")
                break
        for pattern in AUTHOR_PATH_PATTERNS:
            match = pattern.search(text)
            if match and "<" not in match.group(0):
                issues.append(f"author-specific absolute path in {relative}: {match.group(0)}")
                break
    if issues:
        raise BundleBuildError("; ".join(issues))


def _normalise_text_files(root: Path) -> None:
    """Make generated text payloads byte-stable across Git checkout settings."""
    for path in (item for item in root.rglob("*") if item.is_file()):
        if path.suffix.casefold() not in TEXT_SUFFIXES:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        path.write_text(text.replace("\r\n", "\n").replace("\r", "\n"), encoding="utf-8", newline="\n")


def _plugin_version(root: Path) -> str:
    manifest = root / "plugins/metawingman/.codex-plugin/plugin.json"
    if not manifest.is_file():
        return "0.0.0-dev"
    return str(json.loads(manifest.read_text(encoding="utf-8"))["version"])


def _stage(root: Path, destination: Path) -> dict[str, Any]:
    source = root / "metawingman"
    toolkit = root / "toolkit"
    if not (source / "SKILL.md").is_file() or not (toolkit / "R").is_dir():
        raise BundleBuildError("MetaWingman skill or toolkit source is incomplete")
    _assert_source_tree_safe(source)
    _assert_source_tree_safe(toolkit)
    shutil.copytree(source, destination, ignore=_ignore)
    shutil.copytree(toolkit, destination / "scripts/r/toolkit", ignore=_ignore)
    for relative in SKILL_EXCLUDED_PATHS:
        path = destination / relative
        if path.exists():
            path.unlink()
    _normalise_text_files(destination)
    (destination / GENERATED_MARKER).write_text(
        "Generated by scripts/build_skill_bundle.py; edit metawingman/ or toolkit/ instead.\n",
        encoding="utf-8",
    )
    _scan_text(destination)
    file_entries = _files(destination)
    source_tree_sha256 = hashlib.sha256(
        json.dumps(file_entries, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    manifest = {
        "schema_version": "1.0",
        "bundle_name": "metawingman",
        "bundle_version": _plugin_version(root),
        "builder": {"name": "build_skill_bundle.py", "version": BUILDER_VERSION},
        "source_revision_policy": "bind the published bundle hash to a release tag or attestation",
        "source_tree_sha256": source_tree_sha256,
        "requirements": {
            "python": ">=3.10",
            "python_required": ["references/dependencies/python-core.lock.txt"],
            "python_optional": ["references/dependencies/python-pdf.lock.txt"],
            "r": "See references/dependencies/r-packages.lock.json and scripts/r/config/requirements.json",
            "execution_model": "host_model_only",
            "direct_model_api": "not bundled",
        },
        "capabilities": {
            "core": [
                "typed review control plane", "provenance graph", "protocol compiler",
                "screening policy judge", "effect recalculation", "pipeline evaluator",
                "host-model topic proposal contract", "topic opportunity portfolio", "sealed topic rediscovery",
                "judgment dossiers", "living deltas", "benchmark packaging",
            ],
            "optional": ["PDF page rendering", "Zotero integration", "external MetaWingman Agent runtime"],
            "credentialed": ["institutional database user export", "licensed full text"],
        },
        "files": file_entries,
    }
    (destination / "release-manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return manifest


def _replace_generated(staged: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        if not (target / GENERATED_MARKER).is_file():
            raise BundleBuildError(
                f"Refusing to replace non-generated directory: {target}"
            )
        shutil.rmtree(target)
    shutil.copytree(staged, target)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--target", action="append", type=Path)
    parser.add_argument("--no-default-targets", action="store_true")
    args = parser.parse_args()
    root = args.root.expanduser().resolve()
    targets = [] if args.no_default_targets else [
        root / ".agents/skills/metawingman",
        root / "plugins/metawingman/skills/metawingman",
    ]
    targets.extend(path.expanduser().resolve() for path in (args.target or []))
    if not targets:
        raise SystemExit("At least one target is required")
    for target in targets:
        try:
            target.resolve().relative_to(root)
        except ValueError as exc:
            raise SystemExit(f"Target must be inside repository root: {target}") from exc
    try:
        with tempfile.TemporaryDirectory(prefix="metawingman-bundle-") as directory:
            staged = Path(directory) / "metawingman"
            manifest = _stage(root, staged)
            for target in targets:
                _replace_generated(staged, target)
    except (OSError, json.JSONDecodeError, BundleBuildError) as exc:
        print(json.dumps({"built": False, "error": str(exc)}, indent=2))
        return 1
    print(json.dumps({
        "built": True,
        "targets": [str(target) for target in targets],
        "source_tree_sha256": manifest["source_tree_sha256"],
        "files": len(manifest["files"]),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
