"""Frozen contracts for conclusion-directed evidence acquisition experiments."""

from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Any, Iterable


class AcquisitionError(ValueError):
    """Raised when an acquisition plan or receipt is not reproducible."""


CONFIGURATIONS = (
    "generic-fixed-unverified",
    "generic-fixed-verified",
    "conclusion-directed-unverified",
    "full-conclusion-directed-verified",
)

_CAPABILITIES = {
    "generic-fixed-unverified": {"conclusion_directed": False, "source_verifier": False},
    "generic-fixed-verified": {"conclusion_directed": False, "source_verifier": True},
    "conclusion-directed-unverified": {"conclusion_directed": True, "source_verifier": False},
    "full-conclusion-directed-verified": {"conclusion_directed": True, "source_verifier": True},
}
_SEEDS = (20260820, 20260821, 20260822)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _require_keys(document: dict[str, Any], required: set[str], *, label: str) -> None:
    missing = required - set(document)
    if missing:
        raise AcquisitionError(f"{label} is missing required fields: {sorted(missing)}")


def _check_existing_hash(path_value: str, expected: str, *, label: str) -> None:
    path = Path(path_value)
    if not path.is_file():
        raise AcquisitionError(f"{label} is missing: {path}")
    if _sha256(path) != expected:
        raise AcquisitionError(f"{label} SHA-256 mismatch")


def _check_checkpoint(path_value: str, expected: str, *, label: str) -> None:
    path = Path(path_value)
    weights = path / "model.safetensors"
    if not path.is_dir() or not weights.is_file():
        raise AcquisitionError(f"{label} directory or weights are missing: {path}")
    if _sha256(weights) != expected:
        raise AcquisitionError(f"{label} SHA-256 mismatch")


def validate_acquisition_plan(plan: dict[str, Any]) -> dict[str, Any]:
    """Validate an exact 2x2 acquisition design without opening the sealed reference."""
    _require_keys(
        plan,
        {"schema_version", "plan_id", "frozen_at_utc", "case", "runtime", "checkpoints", "configurations", "seeds", "slots"},
        label="plan",
    )
    if plan["schema_version"] != "1.0":
        raise AcquisitionError("unsupported acquisition plan schema version")
    if tuple(plan["configurations"]) != CONFIGURATIONS:
        raise AcquisitionError("configurations must be the frozen exact 2x2 factorial")
    if tuple(plan["seeds"]) != _SEEDS:
        raise AcquisitionError("seeds must be the three frozen training seeds")
    case = plan["case"]
    _require_keys(
        case,
        {"case_id", "review_family_id", "historical_cutoff", "operational_corpus_path", "operational_corpus_sha256", "sealed_reference_path", "sealed_reference_sha256", "operational_question", "eligibility_criteria", "generic_queries"},
        label="case",
    )
    try:
        date.fromisoformat(case["historical_cutoff"])
    except (TypeError, ValueError) as exc:
        raise AcquisitionError("historical cutoff must be an ISO date") from exc
    _check_existing_hash(
        case["operational_corpus_path"], case["operational_corpus_sha256"], label="operational corpus"
    )
    if not str(case["operational_question"]).strip() or not case["eligibility_criteria"] or not case["generic_queries"]:
        raise AcquisitionError("operational question, eligibility criteria, and generic queries are required")
    # Deliberately do not touch sealed_reference_path before all outputs are locked.
    runtime = plan["runtime"]
    _require_keys(runtime, {"model_id", "provider_config_path", "provider_config_sha256", "prompt_path", "prompt_sha256", "matched_budget"}, label="runtime")
    if runtime["model_id"] != "deepseek-v4-flash":
        raise AcquisitionError("text model must be deepseek-v4-flash")
    _check_existing_hash(runtime["provider_config_path"], runtime["provider_config_sha256"], label="provider configuration")
    _check_existing_hash(runtime["prompt_path"], runtime["prompt_sha256"], label="prompt")
    budget = runtime["matched_budget"]
    _require_keys(
        budget,
        {"max_model_calls", "max_input_tokens", "max_output_tokens", "retry_limit", "wall_seconds"},
        label="matched budget",
    )
    if budget["retry_limit"] != 0 or any(int(budget[key]) <= 0 for key in ("max_model_calls", "max_input_tokens", "max_output_tokens", "wall_seconds")):
        raise AcquisitionError("matched budget must be positive with zero retries")
    checkpoints = plan["checkpoints"]
    if [item.get("seed") for item in checkpoints] != list(_SEEDS):
        raise AcquisitionError("one checkpoint pair is required for each frozen seed")
    for item in checkpoints:
        _require_keys(item, {"seed", "query_path", "query_sha256", "document_path", "document_sha256"}, label="checkpoint")
        _check_checkpoint(item["query_path"], item["query_sha256"], label="query checkpoint")
        _check_checkpoint(item["document_path"], item["document_sha256"], label="document checkpoint")
    expected = {(configuration_id, seed) for configuration_id in CONFIGURATIONS for seed in _SEEDS}
    observed = {(slot.get("configuration_id"), slot.get("seed")) for slot in plan["slots"]}
    if len(plan["slots"]) != len(expected) or observed != expected:
        raise AcquisitionError("slots must equal the exact configuration by seed Cartesian product")
    validated = dict(plan)
    validated["capabilities"] = {key: dict(value) for key, value in _CAPABILITIES.items()}
    return validated


def verify_candidates(
    records: Iterable[dict[str, Any]], candidate_ids: Iterable[str], *, cutoff: str
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Apply the deterministic corpus-membership and historical-cutoff verifier."""
    cutoff_date = date.fromisoformat(cutoff)
    index = {str(record.get("id")): record for record in records}
    verified: list[dict[str, Any]] = []
    audit = {"requested": 0, "verified": 0, "unknown": 0, "post_cutoff": 0}
    seen: set[str] = set()
    for raw_id in candidate_ids:
        audit["requested"] += 1
        record_id = str(raw_id)
        record = index.get(record_id)
        if record is None:
            audit["unknown"] += 1
            continue
        verification = record.get("cutoff_verification") or {}
        try:
            observed_date = date.fromisoformat(str(verification.get("conservative_latest_date")))
        except ValueError:
            audit["post_cutoff"] += 1
            continue
        if verification.get("status") != "passed" or observed_date > cutoff_date:
            audit["post_cutoff"] += 1
            continue
        if record_id not in seen:
            verified.append(record)
            seen.add(record_id)
    audit["verified"] = len(verified)
    return verified, audit


def replay_verifier_counterfactual(
    records: Iterable[dict[str, Any]],
    candidate_ids: Iterable[str],
    *,
    cutoff: str,
    unknown_candidate_id: str,
    postcutoff_record: dict[str, Any],
) -> dict[str, Any]:
    """Inject one unknown and one post-cutoff ID to isolate verifier behavior."""
    baseline_records = list(records)
    baseline_ids = {str(record.get("id")) for record in baseline_records}
    unknown_id = str(unknown_candidate_id)
    postcutoff_id = str(postcutoff_record.get("id"))
    if not unknown_id or unknown_id in baseline_ids or not postcutoff_id or postcutoff_id in baseline_ids:
        raise AcquisitionError("counterfactual injections must be distinct from the operational corpus")
    baseline_candidates = list(dict.fromkeys(str(value) for value in candidate_ids))
    baseline_verified, baseline_audit = verify_candidates(
        baseline_records, baseline_candidates, cutoff=cutoff
    )
    injected_candidates = list(dict.fromkeys(baseline_candidates + [unknown_id, postcutoff_id]))
    verified, audit = verify_candidates(
        baseline_records + [postcutoff_record], injected_candidates, cutoff=cutoff
    )
    baseline_verified_ids = [str(record["id"]) for record in baseline_verified]
    verified_ids = [str(record["id"]) for record in verified]
    audit_delta = {
        key: audit[key] - baseline_audit[key]
        for key in ("requested", "verified", "unknown", "post_cutoff")
    }
    if audit_delta["unknown"] != 1 or audit_delta["post_cutoff"] != 1:
        raise AcquisitionError("counterfactual did not isolate one unknown and one post-cutoff rejection")
    return {
        "injected_candidate_ids": [unknown_id, postcutoff_id],
        "unverified_selected_candidate_ids": injected_candidates,
        "verified_selected_candidate_ids": verified_ids,
        "verification_audit": audit,
        "baseline_verification_audit": baseline_audit,
        "verification_audit_delta": audit_delta,
        "baseline_verified_candidate_ids": baseline_verified_ids,
        "baseline_verified_preserved": verified_ids == baseline_verified_ids,
    }


def _string_list_response(content: str, key: str, *, allow_empty: bool = False) -> list[str]:
    try:
        document = json.loads(content)
    except json.JSONDecodeError as exc:
        raise AcquisitionError("provider output is not valid JSON") from exc
    values = document.get(key) if isinstance(document, dict) else None
    if not isinstance(values, list) or len(values) > 100 or (not allow_empty and not values):
        qualifier = "an" if allow_empty else "a non-empty"
        raise AcquisitionError(f"provider output requires {qualifier} {key} array")
    cleaned = [str(value).strip() for value in values]
    if any(not value for value in cleaned):
        raise AcquisitionError(f"provider output {key} contains an empty value")
    return list(dict.fromkeys(cleaned))


def parse_query_response(content: str) -> list[str]:
    return _string_list_response(content, "queries")


def interpret_query_response(content: str, fallback_queries: Iterable[str]) -> tuple[list[str], str]:
    """Preserve the two-call budget by using preregistered queries after malformed JSON."""
    try:
        return parse_query_response(content), "generated"
    except AcquisitionError:
        cleaned = list(dict.fromkeys(str(value).strip() for value in fallback_queries if str(value).strip()))
        if not cleaned:
            raise AcquisitionError("frozen fallback queries are required after invalid provider JSON")
        return cleaned, "fallback_frozen_generic_query_schema_invalid"


def parse_candidate_response(content: str) -> list[str]:
    return _string_list_response(content, "candidate_ids", allow_empty=True)


def interpret_candidate_response(content: str) -> tuple[list[str], str]:
    """Convert a consumed selection call into candidates or a typed abstention."""
    try:
        candidate_ids = parse_candidate_response(content)
    except AcquisitionError:
        return [], "abstained_provider_schema_invalid"
    return candidate_ids, "selected" if candidate_ids else "abstained_no_supported_candidate"


def rank_candidate_ids(
    query_vectors: list[list[float]],
    document_vectors: list[list[float]],
    document_ids: list[str],
    *,
    top_k: int,
) -> list[str]:
    """Rank by maximum query-document inner product with stable ID tie-breaking."""
    if not query_vectors or len(document_vectors) != len(document_ids) or top_k < 1:
        raise AcquisitionError("ranking inputs are incomplete")
    width = len(query_vectors[0])
    if width < 1 or any(len(vector) != width for vector in query_vectors + document_vectors):
        raise AcquisitionError("ranking vector dimensions do not match")
    scored = []
    for document_id, document in zip(document_ids, document_vectors, strict=True):
        score = max(sum(q * d for q, d in zip(query, document, strict=True)) for query in query_vectors)
        scored.append((score, str(document_id)))
    return [document_id for _score, document_id in sorted(scored, key=lambda row: (-row[0], row[1]))[:top_k]]


def balanced_round_robin(rankings: list[list[str]], *, top_k: int) -> list[str]:
    """Guarantee equal opportunity for every frozen query to contribute records."""
    if not rankings or top_k < 1 or any(not ranking for ranking in rankings):
        raise AcquisitionError("balanced aggregation requires non-empty query rankings")
    output: list[str] = []
    seen: set[str] = set()
    depth = 0
    while len(output) < top_k and any(depth < len(ranking) for ranking in rankings):
        for ranking in rankings:
            if depth < len(ranking):
                value = str(ranking[depth])
                if value not in seen:
                    output.append(value); seen.add(value)
                    if len(output) == top_k:
                        break
        depth += 1
    return output


def reciprocal_rank_fusion(
    rankings: list[list[str]], *, top_k: int, constant: int = 60
) -> list[str]:
    if not rankings or top_k < 1 or constant < 1:
        raise AcquisitionError("RRF requires rankings, a positive cutoff, and a positive constant")
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, raw_value in enumerate(ranking, start=1):
            value = str(raw_value)
            scores[value] = scores.get(value, 0.0) + 1.0 / (constant + rank)
    return [value for value, _score in sorted(scores.items(), key=lambda row: (-row[1], row[0]))[:top_k]]


def validate_embedding_cache(cache: dict[str, Any], plan: dict[str, Any], *, seed: int) -> None:
    checkpoint = next((item for item in plan["checkpoints"] if item["seed"] == seed), None)
    if checkpoint is None:
        raise AcquisitionError("embedding cache seed has no frozen checkpoint")
    expected = {
        "schema_version": "1.0",
        "seed": seed,
        "corpus_sha256": plan["case"]["operational_corpus_sha256"],
        "document_checkpoint_sha256": checkpoint["document_sha256"],
    }
    for key, value in expected.items():
        if cache.get(key) != value:
            raise AcquisitionError(f"embedding cache {key} mismatch")
    if int(cache.get("rows", 0)) < 1 or not isinstance(cache.get("embedding_sha256"), str):
        raise AcquisitionError("embedding cache receipt is incomplete")


def lock_acquisition_outputs(plan: dict[str, Any], receipts: list[dict[str, Any]]) -> dict[str, Any]:
    validate_acquisition_plan(plan)
    expected = {(configuration_id, seed) for configuration_id in CONFIGURATIONS for seed in _SEEDS}
    observed: set[tuple[str, int]] = set()
    for receipt in receipts:
        slot = (receipt.get("configuration_id"), receipt.get("seed"))
        if slot not in expected or slot in observed:
            raise AcquisitionError("receipt slot is unexpected or duplicated")
        observed.add(slot)
        if receipt.get("case_id") != plan["case"]["case_id"] or receipt.get("plan_id") != plan["plan_id"]:
            raise AcquisitionError("receipt plan or case binding mismatch")
        if receipt.get("corpus_sha256") != plan["case"]["operational_corpus_sha256"]:
            raise AcquisitionError("receipt corpus binding mismatch")
        if receipt.get("status") != "completed":
            raise AcquisitionError("all acquisition slots must complete before lock")
        _check_existing_hash(receipt["output_path"], receipt["output_sha256"], label="acquisition output")
    if observed != expected or len(receipts) != len(expected):
        raise AcquisitionError("all twelve acquisition slots are required before lock")
    return {
        "schema_version": "1.0",
        "plan_id": plan["plan_id"],
        "case_id": plan["case"]["case_id"],
        "corpus_sha256": plan["case"]["operational_corpus_sha256"],
        "locked_slots": len(receipts),
        "status": "locked",
    }
