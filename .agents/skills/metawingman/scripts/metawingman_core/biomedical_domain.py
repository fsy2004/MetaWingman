"""Deterministic biomedical context resolution and fail-closed pack routing."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from .schema_guard import SchemaValidationError, validate_document


APPLICATION_DOMAIN = "human_health_clinical_translational_biomedicine"
_VALIDATION_RANK = {
    "contract_only": 0,
    "fixture_tested": 1,
    "retrospectively_tested": 2,
    "externally_validated": 3,
}


class BiomedicalDomainError(ValueError):
    """Raised when biomedical context or pack integrity cannot be established."""


def _canonical_pack_content(pack: dict[str, Any]) -> bytes:
    content = {key: value for key, value in pack.items() if key != "content_sha256"}
    return json.dumps(content, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def pack_content_sha256(pack: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical_pack_content(pack)).hexdigest()


def validate_pack_integrity(pack: dict[str, Any]) -> None:
    try:
        validate_document(pack, "domain_pack_manifest")
    except SchemaValidationError as exc:
        raise BiomedicalDomainError(str(exc)) from exc
    if pack_content_sha256(pack) != pack["content_sha256"]:
        raise BiomedicalDomainError(f"domain pack content hash mismatch: {pack.get('pack_id', '<unknown>')}")


def load_domain_packs(pack_dir: Path) -> list[dict[str, Any]]:
    packs: list[dict[str, Any]] = []
    ids: set[str] = set()
    for path in sorted(pack_dir.glob("*.json")):
        try:
            pack = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise BiomedicalDomainError(f"cannot load domain pack {path}: {exc}") from exc
        validate_pack_integrity(pack)
        if pack["pack_id"] in ids:
            raise BiomedicalDomainError(f"duplicate domain pack id: {pack['pack_id']}")
        ids.add(pack["pack_id"])
        packs.append(pack)
    by_id = {pack["pack_id"]: pack for pack in packs}
    skill_root = pack_dir.resolve().parents[1]
    for pack in packs:
        for authority in pack["authority_sources"]:
            authority_path = (skill_root / authority["path"]).resolve()
            try:
                authority_path.relative_to(skill_root)
            except ValueError as exc:
                raise BiomedicalDomainError(f"authority path escapes skill root: {authority['path']}") from exc
            if not authority_path.is_file():
                raise BiomedicalDomainError(f"authority source is missing: {authority['path']}")
            # LF-normalized so the hash is identical on CRLF (Windows) and LF working trees.
            normalized = authority_path.read_bytes().replace(b"\r\n", b"\n")
            if hashlib.sha256(normalized).hexdigest() != authority["content_sha256"]:
                raise BiomedicalDomainError(f"authority source hash mismatch: {authority['source_id']}")
        for dependency in pack["dependencies"]:
            target = by_id.get(dependency["pack_id"])
            if target is None:
                raise BiomedicalDomainError(f"missing domain pack dependency: {dependency['pack_id']}")
            if target["version"] != dependency["version"] or target["content_sha256"] != dependency["content_sha256"]:
                raise BiomedicalDomainError(f"domain pack dependency drift: {dependency['pack_id']}")
    return packs


def _specialty_terms(packs: list[dict[str, Any]]) -> list[tuple[str, str, str]]:
    terms: list[tuple[str, str, str]] = []
    for pack in packs:
        for specialty in pack.get("specialties", []):
            for phrase in [*specialty.get("title_terms", []), *specialty.get("aliases", [])]:
                terms.append((phrase.casefold(), specialty["specialty_id"], pack["pack_id"]))
    return sorted(terms, key=lambda item: (-len(item[0]), item))


def _matched_concepts(source_text: str, packs: list[dict[str, Any]]) -> list[dict[str, str]]:
    lower = source_text.casefold()
    concepts: list[dict[str, str]] = []
    occupied: list[tuple[int, int]] = []
    for phrase, specialty_id, pack_id in _specialty_terms(packs):
        for match in re.finditer(rf"(?<!\w){re.escape(phrase)}(?!\w)", lower):
            span = match.span()
            if any(span[0] < end and start < span[1] for start, end in occupied):
                continue
            occupied.append(span)
            concepts.append(
                {
                    "source_phrase": source_text[span[0] : span[1]],
                    "normalized_term": specialty_id,
                    "identifier": specialty_id,
                    "terminology": "specialty_registry_weak_title_terms",
                    "pack_id": pack_id,
                    "confidence": 0.5,
                    "alternatives": [],
                }
            )
    return sorted(concepts, key=lambda item: (source_text.casefold().find(item["source_phrase"].casefold()), item["normalized_term"]))


def _unresolved_source_terms(source_text: str) -> list[str]:
    explicit = re.findall(r"\b(?:unmapped|unknown|unspecified)\s+[A-Za-z][A-Za-z-]*\b", source_text, flags=re.IGNORECASE)
    return list(dict.fromkeys(item.casefold() for item in explicit))


def resolve_context(seed: dict[str, Any], packs: list[dict[str, Any]], now: str) -> dict[str, Any]:
    for pack in packs:
        validate_pack_integrity(pack)
    declared = list(dict.fromkeys(str(item) for item in seed.get("declared_specialties", []) if str(item)))
    known = {item[1] for item in _specialty_terms(packs)}
    unknown = [item for item in declared if item not in known]
    if unknown:
        raise BiomedicalDomainError(f"unknown declared specialties: {', '.join(unknown)}")
    source_text = str(seed.get("source_text", ""))
    context = {
        "schema_version": "1.0",
        "context_id": seed["context_id"],
        "application_domain": APPLICATION_DOMAIN,
        "status": "draft",
        "review_family": seed["review_family"],
        "primary_specialty": declared[0] if declared else "general-medicine",
        "secondary_specialties": declared[1:],
        "question_framework": {
            "framework": seed.get("framework", "profile_specific"),
            "source_text": source_text,
            "normalized_concepts": _matched_concepts(source_text, packs),
            "unresolved_terms": _unresolved_source_terms(source_text),
        },
        "eligible_study_designs": list(dict.fromkeys(seed.get("eligible_study_designs", []))),
        "population_constraints": list(dict.fromkeys(seed.get("population_constraints", []))),
        "setting_constraints": list(dict.fromkeys(seed.get("setting_constraints", []))),
        "equity_constraints": list(dict.fromkeys(seed.get("equity_constraints", []))),
        "database_constraints": list(dict.fromkeys(seed.get("database_constraints", []))),
        "terminology_releases": [],
        "source_classes": list(dict.fromkeys(seed.get("source_classes", []))),
        "languages": list(dict.fromkeys(seed.get("languages", ["en"]))),
        "geographies": list(dict.fromkeys(seed.get("geographies", []))),
        "ood_assessment": {
            "status": "in_scope" if declared else "uncertain",
            "reason_codes": [] if declared else ["specialty_not_declared"],
            "routing_confidence": 1.0 if declared else 0.0,
        },
        "created_at_utc": now,
        "updated_at_utc": now,
    }
    try:
        validate_document(context, "biomedical_context")
    except SchemaValidationError as exc:
        raise BiomedicalDomainError(str(exc)) from exc
    return context


def route_domain_packs(
    context: dict[str, Any],
    packs: list[dict[str, Any]],
    task_type: str,
    risk_class: str,
    now: str,
) -> dict[str, Any]:
    try:
        validate_document(context, "biomedical_context")
    except SchemaValidationError as exc:
        raise BiomedicalDomainError(str(exc)) from exc
    for pack in packs:
        validate_pack_integrity(pack)
    active = [pack for pack in packs if pack["status"] == "active"]
    by_id = {pack["pack_id"]: pack for pack in active}
    compatible = [pack for pack in active if context["review_family"] in pack["supported_review_families"]]
    foundation = next((pack for pack in compatible if pack["pack_type"] == "foundation"), None)
    profiles = sorted(
        (pack for pack in compatible if pack["pack_type"] == "review_profile"),
        key=lambda item: item["pack_id"],
    )
    specialties = sorted(
        (
            pack
            for pack in compatible
            if pack["pack_type"] == "specialty"
            and context["primary_specialty"] in {item["specialty_id"] for item in pack["specialties"]}
        ),
        key=lambda item: item["pack_id"],
    )
    reason_codes: list[str] = []
    selected: list[dict[str, Any]] = []
    if foundation is None:
        reason_codes.append("missing_foundation_pack")
    else:
        selected.append(foundation)
    if profiles:
        selected.append(profiles[0])
        if len(profiles) > 1:
            reason_codes.append("multiple_profile_packs")
    else:
        reason_codes.append("missing_profile_pack")
    selected.extend(specialties)
    selected_by_id = {pack["pack_id"]: pack for pack in selected}
    missing_dependencies = sorted({
        dependency["pack_id"]
        for pack in selected
        for dependency in pack["dependencies"]
        if dependency["pack_id"] not in selected_by_id
        or selected_by_id[dependency["pack_id"]]["version"] != dependency["version"]
        or selected_by_id[dependency["pack_id"]]["content_sha256"] != dependency["content_sha256"]
    })
    if missing_dependencies:
        reason_codes.append("missing_pack_dependency")
    high_risk = risk_class in {"high", "critical"}
    profile_validated = bool(profiles) and _VALIDATION_RANK[profiles[0]["validation"]["level"]] >= _VALIDATION_RANK["fixture_tested"]
    if high_risk and profiles and not profile_validated:
        reason_codes.append("profile_not_fixture_tested")
    abstain = foundation is None or bool(missing_dependencies) or (high_risk and not profile_validated) or len(profiles) > 1
    if abstain:
        status = "abstained"
        selected_ids: list[str] = []
        fallback = {"action": "abstain", "pack_id": foundation["pack_id"] if foundation else None}
        confidence = 0.0
    elif profiles:
        status = "selected"
        selected_ids = [pack["pack_id"] for pack in selected]
        fallback = {"action": "none", "pack_id": None}
        confidence = 1.0 if specialties else 0.9
    else:
        status = "fallback"
        selected_ids = [foundation["pack_id"]]
        fallback = {"action": "use_foundation", "pack_id": foundation["pack_id"]}
        confidence = 0.5
    fingerprint = json.dumps(
        {
            "context_id": context["context_id"],
            "task_type": task_type,
            "risk_class": risk_class,
            "candidate_pack_ids": sorted(pack["pack_id"] for pack in compatible),
            "created_at_utc": now,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    decision = {
        "schema_version": "1.0",
        "decision_id": "domain-route:" + hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()[:16],
        "context_id": context["context_id"],
        "task_type": task_type,
        "risk_class": risk_class,
        "candidate_pack_ids": sorted(pack["pack_id"] for pack in compatible),
        "selected_pack_ids": selected_ids,
        "status": status,
        "confidence": confidence,
        "evidence": [
            {
                "pack_id": pack["pack_id"],
                "version": pack["version"],
                "content_sha256": pack["content_sha256"],
                "validation_level": pack["validation"]["level"],
            }
            for pack in selected
        ],
        "reason_codes": sorted(set(reason_codes)),
        "fallback": fallback,
        "created_at_utc": now,
    }
    validate_document(decision, "domain_routing_decision")
    return decision
