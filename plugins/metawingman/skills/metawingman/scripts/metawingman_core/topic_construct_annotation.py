"""Bind topic construct inputs to explicit source MeSH and registry evidence."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .schema_guard import SchemaValidationError, validate_document
from .state_store import atomic_write_json, canonical_json, sha256_json


class TopicConstructAnnotationError(ValueError):
    """Raised when explicit construct annotations cannot be frozen safely."""


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, dict):
                raise TopicConstructAnnotationError(f"record line {number} is not an object")
            rows.append(row)
    except (OSError, json.JSONDecodeError) as exc:
        raise TopicConstructAnnotationError(f"invalid topic record JSONL: {exc}") from exc
    identifiers = [str(row.get("id") or row.get("record_id") or "") for row in rows]
    if not rows or any(not value for value in identifiers) or len(identifiers) != len(set(identifiers)):
        raise TopicConstructAnnotationError("topic records require non-empty unique identifiers")
    return rows


def _validate_manifest(manifest: dict[str, Any]) -> None:
    try:
        validate_document(manifest, "topic_construct_annotation_manifest")
    except SchemaValidationError as exc:
        if manifest.get("target_reference_derived") is True:
            raise TopicConstructAnnotationError("target-reference-derived domain mapping is forbidden") from exc
        raise TopicConstructAnnotationError(str(exc)) from exc
    domain_ids = [row["domain_id"] for row in manifest["domains"]]
    if len(domain_ids) != len(set(domain_ids)):
        raise TopicConstructAnnotationError("domain_id values must be unique")


def annotate_topic_construct_records(
    source_path: Path,
    manifest: dict[str, Any],
    *,
    output_path: Path,
    receipt_path: Path,
    created_at_utc: str | None = None,
) -> dict[str, Any]:
    """Add only exact source-vocabulary domains; retain unavailable annotations as empty."""
    _validate_manifest(manifest)
    if output_path.exists() or receipt_path.exists():
        raise TopicConstructAnnotationError("refusing to overwrite a construct annotation artifact")
    rows = _load_rows(source_path)
    mapping = {
        row["domain_id"]: {term.casefold().strip() for term in row["mesh_descriptor_terms"]}
        for row in manifest["domains"]
    }
    annotated: list[dict[str, Any]] = []
    for row in rows:
        terms = row.get("mesh_terms")
        if not isinstance(terms, list) or not all(isinstance(term, str) for term in terms):
            terms = []
        normalized = {term.casefold().strip() for term in terms if term.strip()}
        domains = sorted(domain_id for domain_id, allowed in mapping.items() if normalized & allowed)
        existing = row.get("domain_ids")
        if existing is not None and sorted(existing) != domains:
            raise TopicConstructAnnotationError("existing domain_ids disagree with the frozen exact-MeSH mapping")
        candidate = dict(row)
        candidate["domain_ids"] = domains
        candidate["domain_annotation_basis"] = {
            "method": "exact_mesh_descriptor_mapping_v1",
            "manifest_id": manifest["manifest_id"],
            "manifest_sha256": sha256_json(manifest),
            "matched_mesh_terms": sorted(term for term in terms if term.casefold().strip() in set().union(*mapping.values())),
        }
        annotated.append(candidate)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_name(f".{output_path.name}.{os.getpid()}.tmp")
    try:
        temporary.write_bytes(b"\n".join(canonical_json(row) for row in annotated) + b"\n")
        os.replace(temporary, output_path)
    finally:
        if temporary.exists():
            temporary.unlink()
    receipt = {
        "schema_version": "1.0", "annotation_id": manifest["manifest_id"],
        "created_at_utc": created_at_utc or datetime.now(timezone.utc).isoformat(),
        "source_path": str(source_path), "source_sha256": _sha(source_path),
        "manifest_sha256": sha256_json(manifest), "output_path": str(output_path),
        "output_sha256": _sha(output_path), "records": len(annotated),
        "records_with_explicit_domains": sum(bool(row["domain_ids"]) for row in annotated),
        "records_with_explicit_study_families": sum(bool(row.get("study_family_ids")) for row in annotated),
        "decision_anchor_records": sum(bool(row.get("decision_anchor_type")) for row in annotated),
        "target_reference_derived": False,
    }
    atomic_write_json(receipt_path, receipt)
    return receipt
