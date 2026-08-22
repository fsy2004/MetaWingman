"""Fail-closed readiness audit for governed agent-trajectory distillation.

This module does not train a student.  It independently reopens frozen export,
registry, revocation, source/audit, data, prompt, tool, checkpoint, and family-
closure bindings and reports which examples could enter a future trainer.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from pathlib import Path
from typing import Any, Iterable, Sequence

from .schema_guard import SchemaValidationError, validate_document


SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
CANONICAL_STAGES = (
    "topic_feasibility", "protocol_registration", "search_retrieval", "selection",
    "data_lineage", "appraisal", "freeze_synthesis", "certainty_interpretation",
    "reporting_review", "living_update",
)
LEGACY_STAGE_MAP = {
    "topic_proposal": "topic_feasibility",
    "protocol": "protocol_registration",
    "evidence_acquisition": "search_retrieval",
    "screening": "selection",
    "extraction": "data_lineage",
    "appraisal": "appraisal",
    "synthesis": "freeze_synthesis",
    "verification": "reporting_review",
}
FORBIDDEN_KEYS = {
    "published_expert_reference", "published_answer", "target_title", "target_authors",
    "target_doi", "target_pmid", "target_abstract", "target_citations",
    "target_descendants", "post_cutoff_evidence", "journal_impact_factor",
    "journal_rank", "venue_score",
}


class DistillationReadinessError(ValueError):
    """Raised when an audit input is unreadable or structurally ambiguous."""


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _sha256_json(value: Any) -> str:
    payload = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    ).encode("utf-8")
    return _sha256_bytes(payload)


def _read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DistillationReadinessError(f"cannot read {label} JSON from {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise DistillationReadinessError(f"{label} must be a JSON object")
    return value


def _normalise_marker(value: Any) -> str:
    return "".join(
        character
        for character in unicodedata.normalize("NFKC", str(value)).casefold()
        if character.isalnum()
    )


FORBIDDEN_MARKERS = {_normalise_marker(item) for item in FORBIDDEN_KEYS}


def _find_forbidden(
    value: Any,
    path: str = "",
    *,
    alias_markers: set[str] | None = None,
) -> list[str]:
    markers = FORBIDDEN_MARKERS | (alias_markers or set())
    hits: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            current = f"{path}.{key}" if path else str(key)
            if _normalise_marker(key) in markers:
                hits.append(current)
            hits.extend(_find_forbidden(item, current, alias_markers=alias_markers))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            hits.extend(
                _find_forbidden(item, f"{path}[{index}]", alias_markers=alias_markers)
            )
    elif isinstance(value, str):
        marker = _normalise_marker(value)
        if marker and any(item in marker for item in markers):
            hits.append(path or "<root>")
    return hits


def _canonical_provider_id(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).casefold()
    tokens = re.findall(r"[a-z0-9]+", text)
    compact = "".join(tokens)
    if "deepseek" in compact:
        return "deepseek"
    if "openai" in compact:
        return "openai"
    if "anthropic" in compact:
        return "anthropic"
    if "google" in compact or "gemini" in compact:
        return "google"
    if "zhipu" in compact or "bigmodel" in compact or any(
        item.startswith("glm") for item in tokens
    ):
        return "zhipu"
    ignored = {"http", "https", "www", "api", "v1", "v2", "com", "org", "net", "ai"}
    return "-".join(item for item in tokens if item not in ignored)


def _canonical_model_id(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).casefold().strip()
    if "/" in text:
        text = text.rsplit("/", 1)[-1]
    return "-".join(re.findall(r"[a-z0-9]+", text))


def _identity_reasons(identity: Any, prefix: str) -> list[str]:
    if not isinstance(identity, dict):
        return [f"{prefix}_identity_missing"]
    provider = _canonical_provider_id(identity.get("provider_id"))
    model = _canonical_model_id(identity.get("model_id"))
    reasons: list[str] = []
    if not provider or identity.get("canonical_provider_id") != provider:
        reasons.append(f"{prefix}_provider_identity_not_canonical")
    if not model or identity.get("canonical_model_id") != model:
        reasons.append(f"{prefix}_model_identity_not_canonical")
    return reasons


def _resolve_artifact(root: Path, value: Any) -> Path | None:
    if not isinstance(value, str) or not value:
        return None
    raw = Path(value)
    candidate = (raw if raw.is_absolute() else root / raw).resolve(strict=False)
    try:
        candidate.relative_to(root.resolve(strict=False))
    except ValueError:
        return None
    return candidate


def _file_binding_reasons(
    *,
    path_value: Any,
    expected_sha256: Any,
    root: Path,
    prefix: str,
) -> list[str]:
    if not isinstance(expected_sha256, str) or not SHA256_RE.fullmatch(expected_sha256):
        return [f"{prefix}_sha256_invalid"]
    path = _resolve_artifact(root, path_value)
    if path is None:
        return [f"{prefix}_path_outside_artifact_root"]
    if not path.is_file():
        return [f"{prefix}_missing"]
    if _sha256_file(path) != expected_sha256:
        return [f"{prefix}_hash_mismatch"]
    return []


def _deduplicate(items: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(items))


def _empty_counts() -> dict[str, int]:
    return {
        "positive": 0,
        "negative": 0,
        "abstention": 0,
        "audit_only": 0,
        "quarantine": 0,
        "total": 0,
    }


def _disposition_bucket(example: dict[str, Any]) -> str:
    disposition = example.get("training_disposition")
    if disposition == "positive_demonstration":
        return "positive"
    if disposition == "negative_decision":
        return "negative"
    if disposition == "abstention_demonstration":
        return "abstention"
    return "audit_only"


def _stage_training_status(case: dict[str, Any], example: dict[str, Any]) -> str | None:
    readiness = case.get("training_stage_readiness")
    if not isinstance(readiness, dict):
        return None
    for key in (example.get("stage"), example.get("canonical_stage")):
        value = readiness.get(key)
        if isinstance(value, dict):
            return value.get("status") if isinstance(value.get("status"), str) else None
    return None


def _registry_case_map(case_registry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    cases = case_registry.get("cases")
    if not isinstance(cases, list):
        raise DistillationReadinessError("case registry requires a cases array")
    output: dict[str, dict[str, Any]] = {}
    for row in cases:
        if not isinstance(row, dict) or not isinstance(row.get("case_id"), str):
            raise DistillationReadinessError("case registry rows require case_id")
        if row["case_id"] in output:
            raise DistillationReadinessError("case registry case IDs must be unique")
        output[row["case_id"]] = row
    return output


def _binding_maps(
    lineage: dict[str, Any] | None,
    blockers: list[str],
) -> dict[str, dict[str, dict[str, Any]]]:
    result: dict[str, dict[str, dict[str, Any]]] = {
        "dataset": {}, "prompt": {}, "tool": {}, "checkpoint": {},
    }
    if lineage is None:
        return result
    for kind in result:
        rows = lineage[f"{kind}_bindings"]
        for row in rows:
            digest = row["sha256"]
            if digest in result[kind]:
                blockers.append(f"duplicate_{kind}_sha256_binding:{digest}")
            else:
                result[kind][digest] = row
    return result


def _scope_reasons(
    binding: dict[str, Any],
    *,
    kind: str,
    example: dict[str, Any],
) -> list[str]:
    example_id = example["example_id"]
    reasons: list[str] = []
    if example["case_id"] not in binding.get("case_ids", []):
        reasons.append(f"{kind}_case_scope_mismatch:{example_id}")
    if example["family_id"] not in binding.get("family_ids", []):
        reasons.append(f"{kind}_family_scope_mismatch:{example_id}")
    if example["canonical_stage"] not in binding.get("stages", []):
        reasons.append(f"{kind}_stage_scope_mismatch:{example_id}")
    return reasons


def _lineage_binding_reasons(
    *,
    kind: str,
    digest: Any,
    maps: dict[str, dict[str, dict[str, Any]]],
    root: Path,
    example: dict[str, Any],
) -> tuple[list[str], dict[str, Any] | None]:
    example_id = example["example_id"]
    if not isinstance(digest, str) or not SHA256_RE.fullmatch(digest):
        return [f"{kind}_hash_missing_or_invalid:{example_id}"], None
    binding = maps[kind].get(digest)
    if binding is None:
        return [f"{kind}_hash_unbound:{example_id}"], None
    reasons = _file_binding_reasons(
        path_value=binding.get("artifact_path"),
        expected_sha256=binding.get("sha256"),
        root=root,
        prefix=f"{kind}_artifact:{example_id}",
    )
    reasons.extend(_scope_reasons(binding, kind=kind, example=example))
    return reasons, binding


def _revocation_audit(
    export: dict[str, Any],
    revocation: dict[str, Any] | None,
    registry_sha256: str,
    label: str,
) -> tuple[list[str], set[str], set[str]]:
    if revocation is None:
        return ["missing_revocation_manifest"], set(), set()
    reasons: list[str] = []
    required = {
        "schema_version", "revision", "case_registry_sha256",
        "revoked_trace_ids", "forbidden_value_aliases",
    }
    if set(revocation) != required or revocation.get("schema_version") != "1.0":
        return ["revocation_manifest_contract_invalid"], set(), set()
    revoked = revocation.get("revoked_trace_ids")
    aliases = revocation.get("forbidden_value_aliases")
    if not isinstance(revoked, list) or not all(isinstance(item, str) and item for item in revoked):
        return ["revocation_manifest_contract_invalid"], set(), set()
    if len(revoked) != len(set(revoked)):
        reasons.append("revocation_manifest_duplicate_trace_ids")
    if not isinstance(aliases, list) or not all(isinstance(item, str) and item for item in aliases):
        return ["revocation_manifest_contract_invalid"], set(revoked), set()
    alias_markers = {_normalise_marker(item) for item in aliases}
    if "" in alias_markers:
        reasons.append("revocation_manifest_empty_normalized_alias")
    if revocation.get("case_registry_sha256") != registry_sha256:
        reasons.append("revocation_registry_hash_mismatch")
    binding = export.get("revocation_binding") or {}
    expected = {
        "revision": revocation.get("revision"),
        "case_registry_sha256": registry_sha256,
        "manifest_sha256": _sha256_json(revocation),
        "revoked_trace_ids_sha256": _sha256_json(sorted(revoked)),
        "forbidden_value_aliases_sha256": _sha256_json(sorted(aliases)),
    }
    for field, value in expected.items():
        if binding.get(field) != value:
            reasons.append(f"revocation_manifest_hash_mismatch:{label}:{field}")
    return reasons, set(revoked), alias_markers


def _report(
    *,
    registry_path: Path,
    registry_sha256: str,
    case_count: int,
    export_paths: Sequence[Path],
    lineage_path: Path | None,
    revocation_path: Path | None,
    candidate_counts: dict[str, int],
    trainable_counts: dict[str, int],
    referenced_families: set[str],
    verified_families: set[str],
    referenced_checkpoints: set[str],
    verified_checkpoints: set[str],
    eligible: list[str],
    exclusions: list[dict[str, Any]],
    blockers: list[str],
) -> dict[str, Any]:
    blockers = _deduplicate(blockers)
    document = {
        "schema_version": "1.0",
        "audit_status": "valid_fail_closed_audit",
        "ready_for_student_training": bool(eligible) and not blockers,
        "case_registry": {
            "path": str(registry_path),
            "sha256": registry_sha256,
            "cases": case_count,
        },
        "inputs": {
            "trajectory_exports": [str(path) for path in export_paths],
            "lineage_manifest_path": str(lineage_path) if lineage_path is not None else None,
            "revocation_manifest_path": str(revocation_path) if revocation_path is not None else None,
        },
        "counts": {"candidates": candidate_counts, "trainable": trainable_counts},
        "family_closure": {
            "referenced_families": sorted(referenced_families),
            "verified_families": sorted(verified_families),
        },
        "checkpoint_closure": {
            "referenced_checkpoints": len(referenced_checkpoints),
            "verified_checkpoints": len(verified_checkpoints),
        },
        "eligible_example_ids": eligible,
        "exclusions": exclusions,
        "blockers": blockers,
    }
    try:
        validate_document(document, "distillation_readiness_report")
    except (FileNotFoundError, SchemaValidationError) as exc:
        raise DistillationReadinessError(str(exc)) from exc
    return document


def audit_distillation_readiness(
    *,
    export_paths: Sequence[Path],
    case_registry_path: Path,
    lineage_manifest_path: Path | None = None,
    revocation_manifest_path: Path | None = None,
    artifact_root: Path | None = None,
) -> dict[str, Any]:
    """Recheck every training boundary and derive a fail-closed readiness report.

    ``audit_only_quarantine`` examples remain visible in counts but are never
    eligible.  Held-out, diagnostic-only, forbidden, revoked, family-overlap,
    or published-answer-bearing examples make the audit non-ready.
    """
    registry_path = case_registry_path.resolve(strict=False)
    case_registry = _read_json(registry_path, "case registry")
    case_map = _registry_case_map(case_registry)
    registry_sha256 = _sha256_json(case_registry)
    root = (
        artifact_root.resolve(strict=False)
        if artifact_root is not None
        else registry_path.parent.resolve(strict=False)
    )
    paths = [Path(path).resolve(strict=False) for path in export_paths]
    candidate_counts = _empty_counts()
    trainable_counts = _empty_counts()
    referenced_families: set[str] = set()
    verified_families: set[str] = set()
    referenced_checkpoints: set[str] = set()
    verified_checkpoints: set[str] = set()
    eligible: list[str] = []
    exclusions: list[dict[str, Any]] = []
    blockers: list[str] = []

    if not paths:
        blockers.append("no_frozen_trajectory_exports")
        return _report(
            registry_path=registry_path,
            registry_sha256=registry_sha256,
            case_count=len(case_map),
            export_paths=paths,
            lineage_path=lineage_manifest_path,
            revocation_path=revocation_manifest_path,
            candidate_counts=candidate_counts,
            trainable_counts=trainable_counts,
            referenced_families=referenced_families,
            verified_families=verified_families,
            referenced_checkpoints=referenced_checkpoints,
            verified_checkpoints=verified_checkpoints,
            eligible=eligible,
            exclusions=exclusions,
            blockers=blockers,
        )

    lineage: dict[str, Any] | None = None
    lineage_path = (
        lineage_manifest_path.resolve(strict=False)
        if lineage_manifest_path is not None else None
    )
    if lineage_path is None:
        blockers.append("missing_lineage_manifest")
    else:
        lineage = _read_json(lineage_path, "lineage manifest")
        try:
            validate_document(lineage, "distillation_lineage_manifest")
        except (FileNotFoundError, SchemaValidationError) as exc:
            raise DistillationReadinessError(str(exc)) from exc
        if lineage.get("case_registry_sha256") != registry_sha256:
            blockers.append("lineage_manifest_registry_hash_mismatch")
    maps = _binding_maps(lineage, blockers)

    revocation: dict[str, Any] | None = None
    revocation_path = (
        revocation_manifest_path.resolve(strict=False)
        if revocation_manifest_path is not None else None
    )
    if revocation_path is not None:
        revocation = _read_json(revocation_path, "revocation manifest")

    seen_examples: set[str] = set()
    for export_path in paths:
        export_label = export_path.name
        export = _read_json(export_path, "trajectory export")
        try:
            validate_document(export, "agent_distillation_export")
        except (FileNotFoundError, SchemaValidationError) as exc:
            raise DistillationReadinessError(f"{export_path}: {exc}") from exc

        export_reasons: list[str] = []
        if export.get("case_registry_sha256") != registry_sha256:
            export_reasons.append(f"case_registry_hash_mismatch:{export_label}")
        if export.get("canonical_case_registry_sha256") != registry_sha256:
            export_reasons.append(f"canonical_case_registry_hash_mismatch:{export_label}")
        examples = export["examples"]
        if export.get("examples_sha256") != _sha256_json(examples):
            export_reasons.append(f"examples_hash_mismatch:{export_label}")

        computed_summary = {
            "examples": len(examples),
            "families": len({item["family_id"] for item in examples}),
            "failures_retained": sum(item["outcome"] == "failure" for item in examples),
            "abstentions_retained": sum(item["outcome"] == "abstention" for item in examples),
            "trainable_examples": sum(
                item["training_disposition"] != "audit_only_quarantine" for item in examples
            ),
            "quarantined_examples": sum(
                item["training_disposition"] == "audit_only_quarantine" for item in examples
            ),
        }
        if export.get("summary") != computed_summary:
            export_reasons.append(f"export_summary_mismatch:{export_label}")

        revocation_reasons, revoked_ids, alias_markers = _revocation_audit(
            export, revocation, registry_sha256, export_label,
        )
        export_reasons.extend(revocation_reasons)
        blockers.extend(export_reasons)

        for example in examples:
            example_id = example["example_id"]
            bucket = _disposition_bucket(example)
            is_quarantine = (
                bucket == "audit_only"
                and example.get("target_decision", {}).get("status") == "quarantine"
            )
            if is_quarantine:
                candidate_counts["quarantine"] += 1
            else:
                candidate_counts[bucket] += 1
            candidate_counts["total"] += 1
            referenced_families.add(example["family_id"])
            reasons = list(export_reasons)

            if example_id in seen_examples:
                reasons.append(f"duplicate_example_id:{example_id}")
            seen_examples.add(example_id)
            trace_id = example_id.removeprefix("distill-")
            if trace_id in revoked_ids or example_id in revoked_ids:
                reasons.append(f"revoked_example:{example_id}")

            case = case_map.get(example["case_id"])
            if case is None:
                reasons.append(f"case_absent_from_registry:{example_id}")
            else:
                if example["family_id"] != case.get("review_family_id"):
                    reasons.append(f"case_family_mismatch:{example_id}")
                if case.get("split") != "development":
                    reasons.append(f"held_out_case_forbidden:{example_id}")
                training_use = case.get("training_use")
                if training_use in {"forbidden", "audit_only"}:
                    reasons.append(f"registry_training_use_forbidden:{example_id}:{training_use}")
                elif training_use == "negative_or_abstention_only":
                    if bucket == "positive":
                        reasons.append(f"positive_training_forbidden:{example_id}")
                elif training_use == "stage_verified_only":
                    if _stage_training_status(case, example) != "verified":
                        reasons.append(f"stage_training_readiness_unverified:{example_id}")
                else:
                    reasons.append(f"registry_training_use_unknown:{example_id}")

            reasons.extend(_identity_reasons(example.get("teacher_identity"), "teacher"))
            if (
                _canonical_provider_id(example.get("teacher_provider_id"))
                != (example.get("teacher_identity") or {}).get("canonical_provider_id")
            ):
                reasons.append(f"teacher_provider_alias_mismatch:{example_id}")

            stage = example.get("stage")
            declared_canonical_stage = example.get("canonical_stage")
            expected_canonical_stage = (
                stage if stage in CANONICAL_STAGES else LEGACY_STAGE_MAP.get(stage)
            )
            if (
                stage != "abstention"
                and expected_canonical_stage != declared_canonical_stage
            ):
                reasons.append(f"stage_canonicalization_mismatch:{example_id}")

            expected_outcome = {
                "positive_demonstration": "success",
                "negative_decision": "failure",
                "abstention_demonstration": "abstention",
            }.get(example.get("training_disposition"))
            if expected_outcome is not None and example.get("outcome") != expected_outcome:
                reasons.append(f"disposition_outcome_mismatch:{example_id}")

            verification = example.get("verification") or {}
            if verification.get("verifier_kind") == "provider":
                verifier_identity = verification.get("provider_identity")
                reasons.extend(
                    _identity_reasons(verifier_identity, "verification_provider")
                )
                if (
                    isinstance(verifier_identity, dict)
                    and verifier_identity.get("canonical_provider_id")
                    == (example.get("teacher_identity") or {}).get(
                        "canonical_provider_id"
                    )
                ):
                    reasons.append(f"same_provider_self_verification:{example_id}")

            scan_target = {
                key: example[key]
                for key in (
                    "input_state", "target_action", "target_decision",
                    "source_anchors", "verification",
                )
            }
            leaked = _find_forbidden(scan_target, alias_markers=alias_markers)
            if leaked:
                reasons.append(
                    f"published_answer_marker_present:{example_id}:{','.join(leaked)}"
                )

            for group, prefix in (
                ("source_artifacts", "source_artifact"),
                ("audit_artifacts", "audit_artifact"),
            ):
                for index, binding in enumerate(example["artifact_bindings"][group]):
                    binding_reasons = _file_binding_reasons(
                        path_value=binding.get("path"),
                        expected_sha256=binding.get("sha256"),
                        root=root,
                        prefix=prefix,
                    )
                    reasons.extend(
                        f"{reason}:{example_id}:{index}" for reason in binding_reasons
                    )

            disposition_trainable = bucket != "audit_only"
            if not disposition_trainable:
                exclusion_reasons = ["non_trainable_audit_only_disposition"]
                if is_quarantine:
                    exclusion_reasons.append("quarantine_never_enters_training")
                exclusion_reasons.extend(reasons)
                exclusions.append({
                    "example_id": example_id,
                    "reasons": _deduplicate(exclusion_reasons),
                })
                blockers.extend(
                    item for item in reasons
                    if "held_out_case_forbidden" in item
                    or "published_answer_marker_present" in item
                    or "artifact" in item
                    or item.startswith("revocation_")
                    or item.startswith("case_registry_")
                    or item.startswith("canonical_case_registry_")
                    or item.startswith("examples_hash_")
                    or item.startswith("export_summary_")
                )
                continue

            reproducibility = example.get("reproducibility_bindings") or {}
            checkpoint_binding: dict[str, Any] | None = None
            for kind, field in (
                ("dataset", "dataset_sha256"),
                ("prompt", "prompt_sha256"),
                ("tool", "tool_sha256"),
                ("checkpoint", "checkpoint_sha256"),
            ):
                digest = reproducibility.get(field)
                if kind == "checkpoint" and isinstance(digest, str):
                    referenced_checkpoints.add(digest)
                lineage_reasons, binding = _lineage_binding_reasons(
                    kind=kind,
                    digest=digest,
                    maps=maps,
                    root=root,
                    example=example,
                )
                reasons.extend(lineage_reasons)
                if kind == "checkpoint":
                    checkpoint_binding = binding

            if checkpoint_binding is not None:
                checkpoint_identity = checkpoint_binding["teacher_identity"]
                reasons.extend(_identity_reasons(checkpoint_identity, "checkpoint"))
                teacher = example["teacher_identity"]
                if (
                    checkpoint_identity.get("canonical_provider_id")
                    != teacher.get("canonical_provider_id")
                ):
                    reasons.append(f"checkpoint_provider_mismatch:{example_id}")
                if (
                    checkpoint_identity.get("canonical_model_id")
                    != teacher.get("canonical_model_id")
                ):
                    reasons.append(f"checkpoint_model_mismatch:{example_id}")
                if example["family_id"] in checkpoint_binding.get("training_family_ids", []):
                    reasons.append(f"checkpoint_family_overlap:{example_id}")
                closure = checkpoint_binding.get("family_closure") or {}
                if closure.get("status") != "verified_target_family_absent":
                    reasons.append(f"checkpoint_family_closure_unverified:{example_id}")
                if closure.get("case_registry_sha256") != registry_sha256:
                    reasons.append(f"checkpoint_family_closure_registry_drift:{example_id}")
                reasons.extend(_file_binding_reasons(
                    path_value=closure.get("artifact_path"),
                    expected_sha256=closure.get("sha256"),
                    root=root,
                    prefix=f"checkpoint_family_closure:{example_id}",
                ))

            reasons = _deduplicate(reasons)
            if reasons:
                exclusions.append({"example_id": example_id, "reasons": reasons})
                blockers.extend(reasons)
                continue

            eligible.append(example_id)
            trainable_counts[bucket] += 1
            trainable_counts["total"] += 1
            digest = reproducibility["checkpoint_sha256"]
            verified_checkpoints.add(digest)
            verified_families.add(example["family_id"])

    if not eligible:
        blockers.append("no_eligible_trainable_examples")
    return _report(
        registry_path=registry_path,
        registry_sha256=registry_sha256,
        case_count=len(case_map),
        export_paths=paths,
        lineage_path=lineage_path,
        revocation_path=revocation_path,
        candidate_counts=candidate_counts,
        trainable_counts=trainable_counts,
        referenced_families=referenced_families,
        verified_families=verified_families,
        referenced_checkpoints=referenced_checkpoints,
        verified_checkpoints=verified_checkpoints,
        eligible=eligible,
        exclusions=exclusions,
        blockers=blockers,
    )
