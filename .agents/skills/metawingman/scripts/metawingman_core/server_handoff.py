"""Build a secret-free metadata handoff for an explicitly authorized server run."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from pathlib import Path, PurePosixPath
from typing import Any

from .schema_guard import validate_document
from .state_store import atomic_write_json
from .training_corpus import TrainingCorpusError


_FORBIDDEN_SUFFIXES = (".pdf", ".xml", ".env", ".pt", ".pth", ".ckpt", ".safetensors", ".bin")
_SECRET_PATTERNS = (
    re.compile(rb"sk-[A-Za-z0-9_-]{16,}"),
    re.compile(rb"(?i)(?:api[_-]?key|password|secret)\s*[:=]\s*[^\s,;]{8,}"),
)


def _safe_member(name: str) -> str:
    normalized = name.replace("\\", "/")
    posix = PurePosixPath(normalized)
    if posix.is_absolute() or ".." in posix.parts or not posix.parts:
        raise TrainingCorpusError(f"unsafe handoff member path: {name}")
    if normalized.casefold().endswith(_FORBIDDEN_SUFFIXES):
        raise TrainingCorpusError(f"forbidden raw or checkpoint artifact in handoff: {name}")
    if re.match(r"^[A-Za-z]:/", normalized) or normalized.startswith(("/home/", "/Users/")):
        raise TrainingCorpusError(f"absolute author path in handoff: {name}")
    return posix.as_posix()


def _scan_content(name: str, content: bytes) -> None:
    if any(pattern.search(content) for pattern in _SECRET_PATTERNS):
        raise TrainingCorpusError(f"secret-like content in handoff member: {name}")


def build_server_handoff(spec: dict[str, Any]) -> dict[str, Any]:
    blockers = sorted(set(spec.get("preflight", {}).get("scientific_blockers", spec.get("preflight", {}).get("blocking_reasons", []))))
    if blockers:
        raise TrainingCorpusError("scientific preflight blocks server handoff: " + ", ".join(blockers))
    members = sorted({_safe_member(str(name)) for name in spec["members"]})
    contents = spec.get("member_contents", {})
    member_hashes = {}
    for name in members:
        content = contents.get(name, b"")
        if isinstance(content, str):
            content = content.encode("utf-8")
        _scan_content(name, content)
        member_hashes[name] = hashlib.sha256(content).hexdigest()
    pending = sorted(set(spec.get("preflight", {}).get("server_checks_pending", [])))
    if not pending:
        pending = ["cuda_runtime_unverified", "python_packages_unverified", "server_hardware_unverified"]
    result = {
        "schema_version": "1.0",
        "handoff_id": spec["handoff_id"],
        "created_at_utc": spec["created_at_utc"],
        "status": "local_ready_pending_server_preflight",
        "members": members,
        "member_hashes": member_hashes,
        "component_job_ids": sorted(set(spec["component_job_ids"])),
        "scientific_blockers": [],
        "server_only_pending": pending,
        "storage_estimate_gib": int(spec.get("storage_estimate_gib", 500)),
        "commands": spec["commands"],
        "content_policy": {
            "metadata_only": True,
            "raw_full_text_included": False,
            "secrets_included": False,
            "checkpoints_included": False,
            "absolute_author_paths_included": False,
        },
    }
    validate_document(result, "server_training_handoff")
    return result


def materialize_server_handoff(
    source_root: Path,
    output_root: Path,
    relative_members: list[str],
    spec: dict[str, Any],
) -> dict[str, Any]:
    source_root = source_root.resolve()
    output_root = output_root.resolve()
    if output_root == source_root:
        raise TrainingCorpusError("handoff output root cannot replace the source root")
    member_contents = {}
    for name in relative_members:
        safe = _safe_member(name)
        source = (source_root / safe).resolve()
        try:
            source.relative_to(source_root)
        except ValueError as exc:
            raise TrainingCorpusError(f"handoff member escapes source root: {name}") from exc
        if not source.is_file():
            raise TrainingCorpusError(f"handoff member is missing: {name}")
        member_contents[safe] = source.read_bytes()
    manifest = build_server_handoff({**spec, "members": sorted(member_contents), "member_contents": member_contents})
    output_root.mkdir(parents=True, exist_ok=True)
    for name in manifest["members"]:
        destination = output_root / Path(*PurePosixPath(name).parts)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(member_contents[name])
    atomic_write_json(output_root / "server-training-handoff.json", manifest, "server_training_handoff")
    return manifest
