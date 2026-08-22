"""Govern verified trajectories as candidates for future bounded student training."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from pathlib import Path
from typing import Any

from .state_store import sha256_json
from .schema_guard import validate_document
from .topic_opportunity import _eligibility_reasons


FORBIDDEN_KEYS = {
    "published_expert_reference", "published_answer", "target_title", "target_authors",
    "target_doi", "target_pmid", "target_abstract", "target_citations", "target_descendants",
    "post_cutoff_evidence", "journal_impact_factor", "journal_rank", "venue_score",
}
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
ALLOWED_STAGES = set(CANONICAL_STAGES) | {
    "topic_proposal", "protocol", "evidence_acquisition", "screening", "extraction",
    "appraisal", "synthesis", "verification", "abstention",
}
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
REPRODUCIBILITY_HASH_FIELDS = (
    "dataset_sha256",
    "prompt_sha256",
    "tool_sha256",
    "checkpoint_sha256",
)


class DistillationError(ValueError):
    pass


def _normalise_marker(value: str) -> str:
    return "".join(
        character for character in unicodedata.normalize("NFKC", value).casefold()
        if character.isalnum()
    )


FORBIDDEN_MARKERS = {_normalise_marker(value) for value in FORBIDDEN_KEYS}


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
    if "zhipu" in compact or "bigmodel" in compact or any(item.startswith("glm") for item in tokens):
        return "zhipu"
    ignored = {"http", "https", "www", "api", "v1", "v2", "com", "org", "net", "ai"}
    canonical = "-".join(item for item in tokens if item not in ignored)
    if not canonical:
        raise DistillationError("provider identity must have a canonical non-empty ID")
    return canonical


def _canonical_model_id(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).casefold().strip()
    if "/" in text:
        text = text.rsplit("/", 1)[-1]
    canonical = "-".join(re.findall(r"[a-z0-9]+", text))
    if not canonical:
        raise DistillationError("model identity must have a canonical non-empty ID")
    return canonical


def _canonical_identity(value: Any, *, fallback: str) -> dict[str, str]:
    identity = value if isinstance(value, dict) else {}
    provider_id = str(identity.get("provider_id") or fallback)
    model_id = str(identity.get("model_id") or fallback)
    canonical_provider_id = _canonical_provider_id(provider_id)
    canonical_model_id = _canonical_model_id(model_id)
    declared_provider = identity.get("canonical_provider_id")
    declared_model = identity.get("canonical_model_id")
    if declared_provider is not None and declared_provider != canonical_provider_id:
        raise DistillationError("declared canonical provider identity does not match raw identity")
    if declared_model is not None and declared_model != canonical_model_id:
        raise DistillationError("declared canonical model identity does not match raw identity")
    return {
        "provider_id": provider_id,
        "model_id": model_id,
        "canonical_provider_id": canonical_provider_id,
        "canonical_model_id": canonical_model_id,
    }


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _verified_artifact_bindings(trace: dict[str, Any]) -> dict[str, list[dict[str, str]]]:
    bindings = trace.get("artifact_bindings")
    if not isinstance(bindings, dict):
        raise DistillationError("source and audit artifact bindings are required")
    output: dict[str, list[dict[str, str]]] = {}
    for group in ("source_artifacts", "audit_artifacts"):
        rows = bindings.get(group)
        if not isinstance(rows, list) or not rows:
            raise DistillationError("source and audit artifact bindings are required")
        verified: list[dict[str, str]] = []
        for row in rows:
            if not isinstance(row, dict) or not isinstance(row.get("path"), str):
                raise DistillationError("artifact bindings require a path and SHA-256")
            expected = row.get("sha256")
            if not isinstance(expected, str) or not _SHA256_RE.fullmatch(expected):
                raise DistillationError("artifact bindings require a path and SHA-256")
            path = Path(row["path"])
            if not path.is_file():
                raise DistillationError(f"bound artifact is missing: {path}")
            if _sha256_file(path) != expected:
                raise DistillationError(f"artifact SHA-256 mismatch: {path}")
            verified.append({"path": row["path"], "sha256": expected})
        output[group] = verified
    return output


def _reproducibility_bindings(
    trace: dict[str, Any],
) -> tuple[dict[str, str | None], bool]:
    raw = trace.get("reproducibility_bindings")
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise DistillationError("reproducibility bindings must be an object")
    unexpected = set(raw) - set(REPRODUCIBILITY_HASH_FIELDS)
    if unexpected:
        raise DistillationError("reproducibility bindings contain unsupported fields")
    bindings: dict[str, str | None] = {}
    for field in REPRODUCIBILITY_HASH_FIELDS:
        value = raw.get(field)
        if value is None:
            bindings[field] = None
        elif isinstance(value, str) and _SHA256_RE.fullmatch(value):
            bindings[field] = value
        else:
            raise DistillationError(
                "reproducibility bindings must be lowercase SHA-256 values"
            )
    return bindings, all(bindings.values())


def _canonical_stage(trace: dict[str, Any]) -> str:
    stage = trace.get("stage")
    if stage in CANONICAL_STAGES:
        return str(stage)
    if stage in LEGACY_STAGE_MAP:
        return LEGACY_STAGE_MAP[str(stage)]
    if stage == "abstention" and trace.get("canonical_stage") in CANONICAL_STAGES:
        return str(trace["canonical_stage"])
    raise DistillationError("unsupported scientific stage")


def _revocation_state(
    case_registry_sha256: str,
    manifest: dict[str, Any] | None,
) -> tuple[dict[str, Any], set[str], set[str]]:
    if manifest is None:
        manifest = {
            "schema_version": "1.0",
            "revision": "implicit-empty-v1",
            "case_registry_sha256": case_registry_sha256,
            "revoked_trace_ids": [],
            "forbidden_value_aliases": [],
        }
    if not isinstance(manifest, dict):
        raise DistillationError("revocation manifest must be an object")
    if manifest.get("schema_version") != "1.0":
        raise DistillationError("unsupported revocation manifest schema version")
    revision = manifest.get("revision")
    if not isinstance(revision, str) or not revision.strip():
        raise DistillationError("revocation manifest requires a revision")
    if manifest.get("case_registry_sha256") != case_registry_sha256:
        raise DistillationError("revocation manifest registry SHA-256 mismatch")
    revoked = manifest.get("revoked_trace_ids")
    aliases = manifest.get("forbidden_value_aliases")
    if (
        not isinstance(revoked, list)
        or not all(isinstance(item, str) and item for item in revoked)
        or len(revoked) != len(set(revoked))
    ):
        raise DistillationError("revocation manifest requires unique trace IDs")
    if not isinstance(aliases, list) or not all(isinstance(item, str) and item for item in aliases):
        raise DistillationError("revocation manifest aliases must be non-empty strings")
    alias_markers = {_normalise_marker(item) for item in aliases}
    if any(not item for item in alias_markers):
        raise DistillationError("revocation manifest aliases must normalize to non-empty values")
    binding = {
        "revision": revision,
        "case_registry_sha256": case_registry_sha256,
        "manifest_sha256": sha256_json(manifest),
        "revoked_trace_ids_sha256": sha256_json(sorted(revoked)),
        "forbidden_value_aliases_sha256": sha256_json(sorted(aliases)),
    }
    return binding, set(revoked), alias_markers


def build_topic_proposal_traces(
    batch: dict[str, Any],
    landscape: dict[str, Any],
    candidates_by_proposal_id: dict[str, dict[str, Any]],
    failures_by_proposal_id: dict[str, dict[str, Any]],
    *,
    case_id: str,
    review_family_id: str,
    seed: int,
) -> list[dict[str, Any]]:
    """Convert a locked proposal batch and independent audits into trainable traces.

    Scientific gate failures are negative examples. Infrastructure failures are
    quarantined examples, never interpreted as evidence that a topic is poor.
    """
    if batch.get("landscape_id") != landscape.get("landscape_id"):
        raise DistillationError("proposal batch and landscape IDs do not match")
    teacher = (batch.get("model_provenance") or {}).get("model")
    if not isinstance(teacher, str) or not teacher:
        raise DistillationError("proposal batch requires teacher model provenance")
    policy = landscape.get("selection_policy")
    if not isinstance(policy, dict):
        raise DistillationError("landscape selection policy is required")
    common_input = {
        "landscape_id": landscape["landscape_id"],
        "cutoff_date": (landscape.get("corpus_boundary") or {}).get("cutoff_date"),
        "seed": seed,
        "evidence_boundary": "supplied_pre_cutoff_landscape_only",
    }
    traces: list[dict[str, Any]] = []
    proposals = batch.get("proposals") or []
    if batch.get("status") == "abstain" and not proposals:
        node_ids = [
            str(node.get("node_id")) for node in landscape.get("nodes", [])
            if isinstance(node, dict) and node.get("node_id")
        ][:32]
        if not node_ids:
            raise DistillationError("an abstention trace still requires landscape source anchors")
        return [{
            "trace_id": f"topic-{seed}-abstain",
            "case_id": case_id,
            "review_family_id": review_family_id,
            "split": "development",
            "teacher_provider_id": teacher,
            "stage": "topic_proposal",
            "input_state": {**common_input, "supplied_node_ids": node_ids},
            "action": {"type": "abstain_from_topic_proposal"},
            "decision": {"status": "abstain", "reason_codes": list(batch.get("reason_codes") or ["no_supported_proposal"])},
            "source_anchors": [{"source_id": node_id, "anchor": "temporal_evidence_landscape.nodes"} for node_id in node_ids],
            "verification": {
                "status": "verified", "verifier_kind": "deterministic_guard",
                "verifier_id": "locked-topic-batch-audit-v1",
                "checks": ["locked_batch_abstention", "pre_cutoff_source_anchors"],
            },
            "outcome": "abstention",
        }]
    for proposal in proposals:
        proposal_id = str(proposal.get("proposal_id") or "")
        evidence_ids = list(dict.fromkeys(proposal.get("evidence_node_ids") or []))
        if not proposal_id or not evidence_ids:
            raise DistillationError("topic proposal traces require proposal and evidence IDs")
        trace = {
            "trace_id": f"topic-{seed}-{proposal_id}",
            "case_id": case_id,
            "review_family_id": review_family_id,
            "split": "development",
            "teacher_provider_id": teacher,
            "stage": "topic_proposal",
            "input_state": {
                **common_input,
                "supplied_evidence_node_ids": evidence_ids,
                "supplied_concept_node_ids": list(proposal.get("concept_node_ids") or []),
            },
            "action": {
                "type": "propose_review_question",
                "generation_method": proposal.get("generation_method"),
                "question_framework": proposal.get("question_framework"),
                "disconfirmation_queries": proposal.get("disconfirmation_queries"),
            },
            "source_anchors": [
                {"source_id": node_id, "anchor": "temporal_evidence_landscape.nodes"}
                for node_id in evidence_ids
            ],
        }
        failure = failures_by_proposal_id.get(proposal_id)
        if failure is not None:
            trace.update({
                "decision": {
                    "status": "quarantine", "reason_codes": ["independent_audit_pipeline_failure"],
                    "failed_stage": failure.get("stage"),
                },
                "verification": {
                    "status": "verified", "verifier_kind": "deterministic_guard",
                    "verifier_id": "topic-audit-pipeline-receipt-v1",
                    "checks": ["pipeline_failure_recorded", "not_a_scientific_negative_label"],
                },
                "outcome": "failure",
            })
            traces.append(trace)
            continue
        candidate = candidates_by_proposal_id.get(proposal_id)
        if candidate is None:
            raise DistillationError(f"proposal {proposal_id} has neither candidate nor failure receipt")
        reasons = _eligibility_reasons(candidate, policy)
        trace.update({
            "decision": {
                "status": "reject" if reasons else "accept",
                "reason_codes": reasons or ["all_frozen_hard_gates_passed"],
            },
            "verification": {
                "status": "verified", "verifier_kind": "deterministic_guard",
                "verifier_id": "topic-opportunity-hard-gates-v1",
                "checks": [
                    "external_search_completed", "independent_signal_audit",
                    "identity_and_temporal_leakage_passed", "frozen_hard_gates_evaluated",
                ],
            },
            "outcome": "failure" if reasons else "success",
        })
        traces.append(trace)
    return traces


def _find_forbidden(
    value: Any,
    path: str = "",
    *,
    forbidden_value_markers: set[str] | None = None,
) -> list[str]:
    """Return paths carrying sealed keys or normalized aliases.

    The scan is deliberately recursive and punctuation-insensitive so aliases
    such as ``Target-DOI`` and value-carried labels such as
    ``Published-Expert Reference`` cannot bypass the governance gate.
    """
    hits: list[str] = []
    markers = FORBIDDEN_MARKERS | (forbidden_value_markers or set())
    if isinstance(value, dict):
        for key, item in value.items():
            current = f"{path}.{key}" if path else str(key)
            if _normalise_marker(str(key)) in markers:
                hits.append(current)
            hits.extend(
                _find_forbidden(
                    item,
                    current,
                    forbidden_value_markers=forbidden_value_markers,
                )
            )
    elif isinstance(value, list):
        for index, item in enumerate(value):
            hits.extend(
                _find_forbidden(
                    item,
                    f"{path}[{index}]",
                    forbidden_value_markers=forbidden_value_markers,
                )
            )
    elif isinstance(value, str):
        normalised = _normalise_marker(value)
        if normalised and any(marker in normalised for marker in markers):
            hits.append(path or "<root>")
    return hits


def freeze_distillation_examples(
    traces: list[dict[str, Any]],
    *,
    case_registry: dict[str, Any],
    created_at_utc: str,
    revocation_manifest: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not traces:
        raise DistillationError("at least one trajectory is required")
    registry_cases = case_registry.get("cases")
    if not isinstance(registry_cases, list) or not registry_cases:
        raise DistillationError("a non-empty frozen case registry is required")
    cases_by_id: dict[str, dict[str, Any]] = {}
    for case in registry_cases:
        if not isinstance(case, dict) or not isinstance(case.get("case_id"), str):
            raise DistillationError("case registry entries require case_id")
        if case["case_id"] in cases_by_id:
            raise DistillationError("case registry IDs must be unique")
        cases_by_id[case["case_id"]] = case
    registry_sha256 = sha256_json(case_registry)
    revocation_binding, revoked_trace_ids, forbidden_aliases = _revocation_state(
        registry_sha256,
        revocation_manifest,
    )
    examples: list[dict[str, Any]] = []
    seen: set[str] = set()
    for trace in traces:
        trace_id = str(trace.get("trace_id") or "")
        if not trace_id or trace_id in seen:
            raise DistillationError("trace IDs must be non-empty and unique")
        seen.add(trace_id)
        if trace_id in revoked_trace_ids:
            raise DistillationError("trajectory trace ID has been revoked")
        if trace.get("split") != "development":
            raise DistillationError("distillation accepts the development split only")
        registered = cases_by_id.get(trace.get("case_id"))
        if registered is None:
            raise DistillationError("trajectory case is absent from the frozen case registry")
        if registered.get("split") != "development":
            raise DistillationError("distillation requires the registry development split")
        if trace.get("review_family_id") != registered.get("review_family_id"):
            raise DistillationError("trajectory family does not match the frozen case registry")
        stage = trace.get("stage")
        canonical_stage = _canonical_stage(trace)
        if registered.get("execution_status") != "run_ready":
            readiness = registered.get("training_stage_readiness", {})
            stage_readiness = readiness.get(stage, readiness.get(canonical_stage, {}))
            if stage_readiness.get("status") != "verified":
                raise DistillationError(
                    "distillation requires run_ready or a stage is not verified for training"
                )
        teacher_identity = _canonical_identity(
            trace.get("teacher_identity"),
            fallback=str(trace.get("teacher_provider_id") or ""),
        )
        verification = trace.get("verification")
        if not isinstance(verification, dict) or verification.get("status") != "verified":
            raise DistillationError("teacher output requires independent verification")
        verification = dict(verification)
        verifier_kind = verification.get("verifier_kind")
        verifier_id = verification.get("verifier_id")
        if verifier_kind not in {"deterministic_guard", "provider", "human"}:
            raise DistillationError("unsupported independent verification kind")
        if verifier_kind == "provider":
            provider_identity = _canonical_identity(
                verification.get("provider_identity"),
                fallback=str(verifier_id or ""),
            )
            if (
                provider_identity["canonical_provider_id"]
                == teacher_identity["canonical_provider_id"]
            ):
                raise DistillationError("same-provider self-verification is not independent")
            verification["provider_identity"] = provider_identity
        checks = verification.get("checks")
        if not isinstance(checks, list) or not checks or not all(isinstance(item, str) and item for item in checks):
            raise DistillationError("independent verification checks are required")
        anchors = trace.get("source_anchors")
        if not isinstance(anchors, list) or not anchors or not all(
            isinstance(item, dict) and isinstance(item.get("source_id"), str)
            and item["source_id"] and isinstance(item.get("anchor"), str) and item["anchor"]
            for item in anchors
        ):
            raise DistillationError("source-anchored lineage is required")
        artifact_bindings = _verified_artifact_bindings(trace)
        reproducibility_bindings, reproducibility_complete = _reproducibility_bindings(trace)
        leaked = _find_forbidden(
            trace,
            forbidden_value_markers=forbidden_aliases,
        )
        if leaked:
            raise DistillationError(
                "sealed target identity or answer fields are forbidden: " + ", ".join(leaked)
            )
        if trace.get("outcome") not in {"success", "failure", "abstention"}:
            raise DistillationError("trajectory outcome must be success, failure, or abstention")
        decision_status = str((trace.get("decision") or {}).get("status") or "")
        if decision_status == "quarantine":
            training_disposition = "audit_only_quarantine"
        elif trace["outcome"] == "success":
            training_disposition = "positive_demonstration"
        elif trace["outcome"] == "abstention":
            training_disposition = "abstention_demonstration"
        else:
            training_disposition = "negative_decision"
        if not reproducibility_complete:
            if training_disposition == "positive_demonstration":
                raise DistillationError(
                    "positive demonstration requires complete reproducibility bindings"
                )
            training_disposition = "audit_only_quarantine"
        examples.append({
            "schema_version": "1.0",
            "example_id": f"distill-{trace_id}",
            "case_id": trace["case_id"],
            "family_id": trace["review_family_id"],
            "split": "train",
            "stage": trace["stage"],
            "canonical_stage": canonical_stage,
            "input_state": trace["input_state"],
            "target_action": trace["action"],
            "target_decision": trace["decision"],
            "source_anchors": anchors,
            "artifact_bindings": artifact_bindings,
            "reproducibility_bindings": reproducibility_bindings,
            "verification": verification,
            "outcome": trace["outcome"],
            "training_disposition": training_disposition,
            "label_authority": "verified_teacher_trajectory_not_gold",
            "teacher_provider_id": trace["teacher_provider_id"],
            "teacher_identity": teacher_identity,
            "created_at_utc": created_at_utc,
        })
    export = {
        "schema_version": "1.0",
        "created_at_utc": created_at_utc,
        "governance_status": "governance_only_no_student_trained",
        "policy": {
            "case_registry_bound": True,
            "run_ready_or_verified_stage_only": True,
            "development_families_only": True,
            "held_out_disabled": True,
            "source_anchors_required": True,
            "independent_verification_required": True,
            "same_provider_self_verification_forbidden": True,
            "failed_and_abstained_trajectories_retained": True,
            "journal_features_forbidden": True,
            "published_reference_is_not_gold": True,
            "artifact_hash_binding_required": True,
            "canonical_identity_required": True,
            "revocation_binding_required": True,
            "canonical_ten_stage_lifecycle": True,
            "governance_only_no_student_claim": True,
            "reproducibility_hashes_required_for_training": True,
        },
        "case_registry_sha256": registry_sha256,
        "canonical_case_registry_sha256": registry_sha256,
        "revocation_binding": revocation_binding,
        "summary": {
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
        },
        "examples": examples,
        "examples_sha256": sha256_json(examples),
    }
    try:
        validate_document(export, "agent_distillation_export")
    except Exception as exc:
        raise DistillationError(str(exc)) from exc
    return export
