"""Package published-review reconstructions with physical answer sealing."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from .schema_guard import SchemaValidationError, validate_document
from .state_store import sha256_json


class BenchmarkPackageError(ValueError):
    """Raised when a benchmark package would leak answers or violate its data policy."""


SENSITIVE_SUFFIXES = {".env", ".key", ".pem", ".p12", ".pfx"}
SECRET_BYTE_PATTERNS = (
    re.compile(rb"(?i)(api[_-]?key|token|password|secret)\s*[:=]\s*['\"]?[A-Za-z0-9_\-]{12,}"),
    re.compile(rb"gh[opusr]_[A-Za-z0-9]{20,}"),
    re.compile(rb"sk-[A-Za-z0-9]{16,}"),
)


def _assert_no_embedded_secret(path: Path) -> None:
    if path.name.casefold() == ".env" or path.suffix.casefold() in SENSITIVE_SUFFIXES:
        raise BenchmarkPackageError(f"Sensitive file type cannot enter a benchmark package: {path.name}")
    overlap = b""
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            window = overlap + chunk
            if any(pattern.search(window) for pattern in SECRET_BYTE_PATTERNS):
                raise BenchmarkPackageError(
                    f"Possible embedded secret in benchmark source: {path.name}"
                )
            overlap = window[-512:]


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _tree_hash(root: Path) -> str:
    entries = []
    if root.exists():
        for path in sorted((item for item in root.rglob("*") if item.is_file()), key=lambda item: item.relative_to(root).as_posix()):
            entries.append({
                "path": path.relative_to(root).as_posix(),
                "sha256": _file_hash(path),
                "bytes": path.stat().st_size,
            })
    return sha256_json(entries)


def _validate_relative_destination(value: str) -> Path:
    destination = Path(value)
    if destination.is_absolute() or ".." in destination.parts or not destination.parts:
        raise BenchmarkPackageError(f"Invalid package-relative destination: {value}")
    return destination


def _artifact_role(raw: dict[str, Any], cutoff: date) -> str:
    if raw["contains_answer"]:
        return "sealed_reference"
    available_date = raw.get("available_date")
    if available_date and date.fromisoformat(available_date) > cutoff:
        return "sealed_post_cutoff"
    if not raw["available_at_cutoff"]:
        return "sealed_post_cutoff"
    return str(raw.get("role") or "operational_input")


def build_benchmark_package(candidate: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    output = output_dir.expanduser().resolve()
    if output.exists() and any(output.iterdir()):
        raise BenchmarkPackageError(f"Refusing to overwrite non-empty benchmark directory: {output}")
    output.mkdir(parents=True, exist_ok=True)
    visibility = str(candidate.get("visibility") or "private")
    if "comparison_arms" in candidate:
        raise BenchmarkPackageError(
            "comparison_arms is retired; AI-only repeated-run evaluation uses evaluation_design"
        )
    design = candidate.get("evaluation_design")
    if not isinstance(design, dict) or design.get("design") != "ai_only_repeated_runs":
        raise BenchmarkPackageError("candidate.evaluation_design must declare ai_only_repeated_runs")
    configuration_ids = list(design.get("configuration_ids") or [])
    repetitions = design.get("repetitions_per_configuration")
    if not configuration_ids or len(set(configuration_ids)) != len(configuration_ids):
        raise BenchmarkPackageError("evaluation_design needs unique configuration_ids")
    if not isinstance(repetitions, int) or repetitions < 2:
        raise BenchmarkPackageError("AI-only reliability evaluation requires at least two repetitions")
    cutoff = date.fromisoformat(candidate["reconstruction"]["search_cutoff_date"])
    artifacts = candidate.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        raise BenchmarkPackageError("candidate.artifacts must be a non-empty list")

    records: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    seen_destinations: set[str] = set()
    for raw in artifacts:
        artifact_id = str(raw.get("artifact_id") or "")
        if not artifact_id or artifact_id in seen_ids:
            raise BenchmarkPackageError(f"Missing or duplicate artifact_id: {artifact_id!r}")
        seen_ids.add(artifact_id)
        source = Path(raw["path"]).expanduser().resolve()
        if not source.is_file():
            raise BenchmarkPackageError(f"Benchmark source artifact is missing: {source}")
        _assert_no_embedded_secret(source)
        license_name = str(raw.get("license") or "").strip()
        if not license_name:
            raise BenchmarkPackageError(f"Artifact {artifact_id} needs a license/access-rights statement")
        redistributable = bool(raw.get("redistributable", False))
        if visibility == "public" and not redistributable:
            raise BenchmarkPackageError(
                f"Public package cannot copy a non-redistributable artifact: {artifact_id}"
            )
        role = _artifact_role(raw, cutoff)
        if role not in {"operational_input", "sealed_reference", "sealed_post_cutoff", "documentation"}:
            raise BenchmarkPackageError(f"Invalid artifact role for {artifact_id}: {role}")
        if raw["contains_answer"] and role == "operational_input":
            raise BenchmarkPackageError(f"Answer-containing artifact cannot be operational input: {artifact_id}")
        destination_rel = _validate_relative_destination(str(raw.get("destination") or source.name))
        top = "operational" if role in {"operational_input", "documentation"} else "sealed"
        destination = output / top / destination_rel
        package_path = destination.relative_to(output).as_posix()
        if package_path in seen_destinations:
            raise BenchmarkPackageError(f"Duplicate benchmark package path: {package_path}")
        seen_destinations.add(package_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        records.append({
            "artifact_id": artifact_id,
            "role": role,
            "artifact_type": raw["artifact_type"],
            "package_path": package_path,
            "sha256": _file_hash(destination),
            "bytes": destination.stat().st_size,
            "source": str(raw.get("source") or source.name),
            "license": license_name,
            "redistributable": redistributable,
            "available_at_cutoff": bool(raw["available_at_cutoff"]),
            "contains_answer": bool(raw["contains_answer"]),
            "sealed": top == "sealed",
            "notes": str(raw.get("notes") or ""),
        })

    operational_hash = _tree_hash(output / "operational")
    sealed_hash = _tree_hash(output / "sealed")
    boundary = {
        "schema_version": "2.0",
        "benchmark_id": candidate["benchmark_id"],
        "run_state": "collecting",
        "operational_tree_sha256": operational_hash,
        "sealed_tree_sha256": sealed_hash,
        "sealed_directory_must_not_be_mounted_during_run": True,
        "expected_runs": len(configuration_ids) * repetitions,
        "run_locks": [],
        "evaluation_design": {
            "design": "ai_only_repeated_runs",
            "configuration_ids": configuration_ids,
            "repetitions_per_configuration": repetitions,
            "human_interventions_permitted_during_run": False,
        },
        "instructions": [
            "Mount or copy only the operational directory for a blind reconstruction run.",
            "Write an AI-only run lock with configuration, repetition, model, prompt, tool, cost, input-tree, and output hashes before unsealing.",
            "Do not train, prompt-optimize, or retrieve against dev/test sealed artifacts.",
            "Do not unseal published expert answers until all planned runs are locked.",
        ],
    }
    (output / "RUN_BOUNDARY.json").write_text(
        json.dumps(boundary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    now = str(candidate.get("created_at_utc") or datetime.now(timezone.utc).isoformat())
    manifest = {
        "schema_version": "2.0",
        "benchmark_id": candidate["benchmark_id"],
        "benchmark_version": candidate["benchmark_version"],
        "visibility": visibility,
        "review": candidate["review"],
        "reconstruction": {
            "search_cutoff_date": cutoff.isoformat(),
            "knowledge_cutoff_policy": "operational_inputs_available_on_or_before_search_cutoff",
            "blinding_policy": "published_review_and_reference_answers_sealed_until_run_lock",
            "post_cutoff_policy": "exclude_and_seal_post_cutoff_evidence",
        },
        "split": candidate["split"],
        "artifacts": records,
        "reference_standard": {
            "source": "published_expert_reference",
            "correction_policy": "verified_corrected_version_only",
            "integrity_policy": "unresolved_cases_excluded_from_held_out_scoring",
            "discordance_policy": "classify_without_de_novo_human_adjudication",
            "error_classes": [
                "ai_reference_disagreement", "published_review_error", "reference_ambiguity",
                "protocol_disagreement", "post_cutoff_knowledge", "tool_failure",
            ],
            "published_review_not_infallible": True,
        },
        "evaluation_design": {
            "design": "ai_only_repeated_runs",
            "configuration_ids": configuration_ids,
            "repetitions_per_configuration": repetitions,
            "human_execution_arms_prohibited": True,
            "reference_policy": "published_expert_reference_no_de_novo_adjudication",
            "inference_scope": "ai_agreement_with_published_expert_reference_only",
            "no_human_superiority_claim": True,
            "no_labor_savings_claim": True,
        },
        "data_policy": {
            "no_secrets": True,
            "no_unlicensed_public_redistribution": True,
            "no_training_on_test": True,
            "run_lock_required_before_unsealing": True,
        },
        "package_sha256": "0" * 64,
        "created_at_utc": now,
    }
    manifest["package_sha256"] = sha256_json({key: value for key, value in manifest.items() if key != "package_sha256"})
    try:
        validate_document(manifest, "benchmark_manifest")
    except SchemaValidationError as exc:
        raise BenchmarkPackageError(str(exc)) from exc
    (output / "benchmark_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return manifest


def lock_benchmark_run(
    package_dir: Path,
    run: dict[str, Any],
    *,
    created_at_utc: str | None = None,
) -> dict[str, Any]:
    root = package_dir.expanduser().resolve()
    boundary_path = root / "RUN_BOUNDARY.json"
    if not boundary_path.is_file():
        raise BenchmarkPackageError("RUN_BOUNDARY.json is missing")
    boundary = json.loads(boundary_path.read_text(encoding="utf-8"))
    if boundary["run_state"] != "collecting":
        raise BenchmarkPackageError("Benchmark package is not accepting more runs")
    current_operational = _tree_hash(root / "operational")
    current_sealed = _tree_hash(root / "sealed")
    if current_operational != boundary["operational_tree_sha256"]:
        raise BenchmarkPackageError("Operational inputs changed after package creation")
    if current_sealed != boundary["sealed_tree_sha256"]:
        raise BenchmarkPackageError("Sealed artifacts changed after package creation")
    output_path = Path(run["output_path"]).expanduser().resolve()
    if not output_path.is_file():
        raise BenchmarkPackageError(f"Run output is missing: {output_path}")
    run_lock = {
        "run_id": str(run["run_id"]),
        "execution_mode": str(run.get("execution_mode") or ""),
        "configuration_id": str(run.get("configuration_id") or ""),
        "repetition_index": run.get("repetition_index"),
        "model_versions": list(run.get("model_versions") or []),
        "prompt_sha256": str(run.get("prompt_sha256") or ""),
        "tool_versions": list(run.get("tool_versions") or []),
        "operational_tree_sha256": current_operational,
        "output_sha256": _file_hash(output_path),
        "output_path": str(output_path),
        "human_interventions": run.get("human_interventions"),
        "wall_clock_seconds": run.get("wall_clock_seconds"),
        "model_calls": run.get("model_calls"),
        "input_tokens": run.get("input_tokens"),
        "output_tokens": run.get("output_tokens"),
        "api_cost": run.get("api_cost"),
        "compute_cost": run.get("compute_cost"),
        "cost_currency": str(run.get("cost_currency") or ""),
        "locked_at_utc": created_at_utc or datetime.now(timezone.utc).isoformat(),
    }
    design = boundary.get("evaluation_design") or {}
    if run_lock["execution_mode"] != "ai_only":
        raise BenchmarkPackageError("Benchmark execution_mode must be ai_only")
    if run_lock["configuration_id"] not in design.get("configuration_ids", []):
        raise BenchmarkPackageError("Run configuration_id is not registered in the package")
    if not isinstance(run_lock["repetition_index"], int) or not (
        1 <= run_lock["repetition_index"] <= design.get("repetitions_per_configuration", 0)
    ):
        raise BenchmarkPackageError("Run repetition_index is outside the preregistered range")
    if run_lock["human_interventions"] != 0:
        raise BenchmarkPackageError("AI-only benchmark runs must record zero human interventions")
    if not run_lock["model_versions"]:
        raise BenchmarkPackageError("AI-only runs must record model versions")
    if len(run_lock["prompt_sha256"]) != 64:
        raise BenchmarkPackageError("AI-only runs must record a prompt SHA-256")
    for field in ("wall_clock_seconds", "model_calls", "input_tokens", "output_tokens", "api_cost", "compute_cost"):
        value = run_lock[field]
        if not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0:
            raise BenchmarkPackageError(f"AI-only runs must record non-negative {field}")
    if not run_lock["cost_currency"]:
        raise BenchmarkPackageError("AI-only runs must record cost_currency")
    existing = boundary.get("run_locks") or []
    if any(item["run_id"] == run_lock["run_id"] for item in existing):
        raise BenchmarkPackageError(f"Duplicate run_id: {run_lock['run_id']}")
    if any(
        item["configuration_id"] == run_lock["configuration_id"]
        and item["repetition_index"] == run_lock["repetition_index"]
        for item in existing
    ):
        raise BenchmarkPackageError("Configuration repetition is already locked")
    existing.append(run_lock)
    boundary["run_locks"] = existing
    boundary["run_state"] = (
        "locked" if len(existing) == boundary["expected_runs"] else "collecting"
    )
    boundary_path.write_text(json.dumps(boundary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return boundary
