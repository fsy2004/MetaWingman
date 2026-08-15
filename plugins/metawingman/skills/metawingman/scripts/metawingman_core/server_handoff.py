"""Build a bounded-secret-scan metadata handoff for an authorized server run."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
from pathlib import Path, PurePosixPath
from typing import Any

from .schema_guard import validate_document
from .state_store import atomic_write_json
from .training_corpus import TrainingCorpusError


_FORBIDDEN_SUFFIXES = (
    ".pdf", ".xml", ".env", ".pt", ".pth", ".ckpt", ".safetensors", ".bin",
    ".zip", ".tar", ".gz", ".7z", ".pem", ".key", ".pfx", ".p12", ".crt",
    ".cer", ".sqlite", ".db",
)
_SECRET_PATTERNS = (
    re.compile(rb"sk-[A-Za-z0-9_-]{16,}"),
    re.compile(rb"(?i)(?:api[_-]?key|password|secret)\s*[:=]\s*[^\s,;]{8,}"),
    re.compile(rb"(?i)authorization\s*[:=]\s*bearer\s+[A-Za-z0-9._-]{12,}"),
    re.compile(rb"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
)
_ALLOWED_MEMBER_PATTERNS = (
    re.compile(r"^research/training-corpus-plan-biomedical-v2\.json$"),
    re.compile(r"^metawingman/references/dependencies/python-training\.lock\.txt$"),
    re.compile(
        r"^metawingman/schemas/(?:training_corpus_plan|training_pair|training_run_plan|"
        r"component_training_job|server_training_handoff)\.schema\.json$"
    ),
    re.compile(r"^validation-output/training-corpus/jobs/[a-z0-9._-]+\.json$"),
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
    safe = posix.as_posix()
    if not any(pattern.fullmatch(safe) for pattern in _ALLOWED_MEMBER_PATTERNS):
        raise TrainingCorpusError(f"member is outside metadata handoff allowlist: {name}")
    return safe


def _scan_content(name: str, content: bytes) -> None:
    if any(pattern.search(content) for pattern in _SECRET_PATTERNS):
        raise TrainingCorpusError(f"secret-like content in handoff member: {name}")


def build_server_commands(plan_member: str, evidence_job_member: str) -> dict[str, list[str]]:
    plan = _safe_member(plan_member)
    job = _safe_member(evidence_job_member)
    documents = "validation-output/training-corpus/documents"
    manifest = f"{documents}/training-document-manifest.json"
    examples = "validation-output/training-corpus/training-examples.jsonl"
    run_plan = "validation-output/training-corpus/training-run-plan-biomedical-v2.json"
    export_root = "validation-output/training-corpus/exports-biomedical-v2"
    pairs = f"{export_root}/evidence-retrieval.pairs.jsonl"
    return {
        "download": ["python", "metawingman/scripts/fetch_training_corpus.py", plan, "--out", documents],
        "freeze_base": [
            "python", "metawingman/scripts/freeze_training_dataset.py", manifest,
            "--artifact-root", documents, "--examples-out", examples,
            "--run-plan-out", run_plan,
        ],
        "audit": [
            "python", "metawingman/scripts/audit_training_dataset.py", "--plan", plan,
            "--manifest", manifest, "--examples", examples, "--run-plan", run_plan,
            "--artifact-root", documents,
        ],
        "export": [
            "python", "metawingman/scripts/export_training_splits.py", examples,
            "--out", export_root, "--training-plan", plan,
        ],
        "freeze": [
            "python", "metawingman/scripts/freeze_training_dataset.py", manifest,
            "--artifact-root", documents, "--examples-out", examples,
            "--run-plan-out", run_plan, "--pairs", pairs, "--training-plan", plan,
        ],
        "preflight": [
            "python", "metawingman/scripts/preflight_component_training.py", job,
            "--root", ".", "--inspect-server",
        ],
        "train": ["python", "metawingman/scripts/run_component_training.py", job, "--root", "."],
        "benchmark": ["python", "metawingman/scripts/evaluate_pipeline.py", "--help"],
    }


def validate_server_handoff_manifest(manifest: dict[str, Any]) -> None:
    validate_document(manifest, "server_training_handoff")
    members = set(manifest["members"])
    hashes = set(manifest["member_hashes"])
    if members != hashes:
        raise TrainingCorpusError("handoff member_hashes keys must exactly match members")
    for member in members:
        if _safe_member(member) != member:
            raise TrainingCorpusError(f"handoff member is not canonical: {member}")


def _is_link_or_junction(path: Path) -> bool:
    return path.is_symlink() or bool(getattr(os.path, "isjunction", lambda _: False)(path))


def _existing_output_members(output_root: Path) -> set[str]:
    if not output_root.exists():
        return set()
    if _is_link_or_junction(output_root) or not output_root.is_dir():
        raise TrainingCorpusError("handoff output root must be an ordinary directory")
    manifest_path = output_root / "server-training-handoff.json"
    if not manifest_path.is_file() or _is_link_or_junction(manifest_path):
        raise TrainingCorpusError("existing handoff output lacks a governed manifest")
    try:
        prior = json.loads(manifest_path.read_text(encoding="utf-8"))
        validate_server_handoff_manifest(prior)
    except (OSError, json.JSONDecodeError, KeyError, ValueError) as exc:
        raise TrainingCorpusError("existing handoff manifest is invalid") from exc
    allowed = set(prior["members"]) | {"server-training-handoff.json"}
    for path in output_root.rglob("*"):
        if _is_link_or_junction(path):
            raise TrainingCorpusError(f"existing handoff contains link or junction: {path}")
        if path.is_file() and path.relative_to(output_root).as_posix() not in allowed:
            raise TrainingCorpusError(f"existing handoff contains unmanaged file: {path}")
    for member, expected_hash in prior["member_hashes"].items():
        path = output_root / Path(*PurePosixPath(member).parts)
        if not path.is_file() or _is_link_or_junction(path):
            raise TrainingCorpusError(f"existing handoff member is missing or unsafe: {member}")
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected_hash:
            raise TrainingCorpusError(f"existing handoff member hash drift: {member}")
    return set(prior["members"])


def build_server_handoff(spec: dict[str, Any]) -> dict[str, Any]:
    blockers = sorted(set(spec.get("preflight", {}).get("scientific_blockers", spec.get("preflight", {}).get("blocking_reasons", []))))
    if blockers:
        raise TrainingCorpusError("scientific preflight blocks server handoff: " + ", ".join(blockers))
    members = sorted({_safe_member(str(name)) for name in spec["members"]})
    contents = {
        _safe_member(str(name)): content
        for name, content in spec.get("member_contents", {}).items()
    }
    if set(contents) != set(members):
        raise TrainingCorpusError("member_contents keys must exactly match handoff members")
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
            "secret_scan_status": "passed_bounded_patterns_not_proof_of_absence",
            "checkpoints_included": False,
            "absolute_author_paths_included": False,
        },
    }
    _scan_content(
        "server-training-handoff.json",
        json.dumps(result, ensure_ascii=False, sort_keys=True).encode("utf-8"),
    )
    validate_server_handoff_manifest(result)
    return result


def materialize_server_handoff(
    source_root: Path,
    output_root: Path,
    relative_members: list[str],
    spec: dict[str, Any],
) -> dict[str, Any]:
    source_root = source_root.resolve()
    raw_output_root = output_root.absolute()
    if _is_link_or_junction(raw_output_root):
        raise TrainingCorpusError("handoff output root cannot be a link or junction")
    output_root = raw_output_root.resolve()
    if output_root == source_root:
        raise TrainingCorpusError("handoff output root cannot replace the source root")
    existing_members = _existing_output_members(output_root)
    member_contents = {}
    for name in relative_members:
        safe = _safe_member(name)
        source_candidate = source_root / Path(*PurePosixPath(safe).parts)
        if _is_link_or_junction(source_candidate):
            raise TrainingCorpusError(f"handoff member cannot be a link or junction: {name}")
        source = source_candidate.resolve()
        try:
            source.relative_to(source_root)
        except ValueError as exc:
            raise TrainingCorpusError(f"handoff member escapes source root: {name}") from exc
        if not source.is_file():
            raise TrainingCorpusError(f"handoff member is missing: {name}")
        member_contents[safe] = source.read_bytes()
    manifest = build_server_handoff({**spec, "members": sorted(member_contents), "member_contents": member_contents})
    removed_members = existing_members - set(manifest["members"])
    if removed_members:
        raise TrainingCorpusError(
            "existing handoff contains members absent from replacement: "
            + ", ".join(sorted(removed_members))
        )
    output_root.mkdir(parents=True, exist_ok=True)
    for name in manifest["members"]:
        destination = output_root / Path(*PurePosixPath(name).parts)
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            destination.parent.resolve().relative_to(output_root)
        except ValueError as exc:
            raise TrainingCorpusError(f"handoff destination escapes output root: {name}") from exc
        if destination.exists() and (not destination.is_file() or _is_link_or_junction(destination)):
            raise TrainingCorpusError(f"handoff destination is not an ordinary file: {name}")
        destination.write_bytes(member_contents[name])
    atomic_write_json(output_root / "server-training-handoff.json", manifest, "server_training_handoff")
    return manifest
