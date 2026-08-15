"""Audit lifecycle breadth without converting implementation into validation claims."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from .biomedical_domain import BiomedicalDomainError, load_domain_packs
from .schema_guard import validate_document
from .state_store import sha256_json


EXPECTED_STAGES = {
    0: "topic_feasibility",
    1: "protocol_registration",
    2: "search_retrieval",
    3: "selection",
    4: "data_lineage",
    5: "appraisal",
    6: "freeze_synthesis",
    7: "certainty_interpretation",
    8: "reporting_review",
    9: "living_update",
}

REQUIRED_SYNTHESIS_ROUTES = {
    "pairwise",
    "network",
    "diagnostic",
    "proportion_prevalence",
    "incidence_rate",
    "multilevel",
    "robust_variance",
    "dose_response",
    "bayesian",
    "meta_regression",
    "component_network",
    "rare_event",
    "sequential",
    "reporting_bias_sensitivity",
    "multivariate",
    "ipd_one_two_stage",
    "prediction_model_performance",
    "prognostic_factor",
    "structured_no_pooling",
}

ADVANCED_VALIDATION_LEVELS = {"published_reconstruction_passed", "prospective_passed"}
SCIENTIFIC_CLAIM_CEILING = "implemented_not_scientifically_validated"


class CoverageAuditError(ValueError):
    """Raised when the capability matrix cannot be audited."""


def _duplicates(values: list[str]) -> list[str]:
    return sorted(value for value, count in Counter(values).items() if count > 1)


def _profile_enum(skill_root: Path) -> set[str]:
    path = skill_root / "schemas/review_profile.schema.json"
    try:
        schema = json.loads(path.read_text(encoding="utf-8"))
        return set(schema["properties"]["review_family"]["enum"])
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise CoverageAuditError(f"cannot read review-profile authority from {path}: {exc}") from exc


def _artifact_issues(matrix: dict[str, Any], skill_root: Path) -> list[str]:
    issues: list[str] = []
    collections = (
        ("lifecycle_stages", "stage_id"),
        ("review_profiles", "profile_id"),
        ("synthesis_routes", "route_id"),
        ("cross_cutting_capabilities", "capability_id"),
    )
    for collection_name, id_field in collections:
        for item in matrix[collection_name]:
            for relative in item["evidence_paths"]:
                path = (skill_root / relative).resolve()
                try:
                    path.relative_to(skill_root.resolve())
                except ValueError:
                    issues.append(f"{collection_name}.{item[id_field]}: evidence path escapes skill root: {relative}")
                    continue
                if not path.is_file():
                    issues.append(f"{collection_name}.{item[id_field]}: missing evidence path: {relative}")
            for relative in item.get("native_routes", []):
                path = (skill_root / relative).resolve()
                if not path.is_file():
                    issues.append(f"{collection_name}.{item[id_field]}: missing native route: {relative}")
    return issues


def audit_capability_matrix(matrix: dict[str, Any], skill_root: Path) -> dict[str, Any]:
    """Return a machine-readable coverage verdict and conservative summary."""
    validate_document(matrix, "system_capability_matrix")
    skill_root = skill_root.resolve()
    issues: list[str] = []

    stage_ids = [item["stage_id"] for item in matrix["lifecycle_stages"]]
    stage_numbers = [item["stage_number"] for item in matrix["lifecycle_stages"]]
    issues.extend(f"duplicate lifecycle stage id: {item}" for item in _duplicates(stage_ids))
    issues.extend(f"duplicate lifecycle stage number: {item}" for item in _duplicates([str(value) for value in stage_numbers]))
    observed_stages = {item["stage_number"]: item["stage_id"] for item in matrix["lifecycle_stages"]}
    if observed_stages != EXPECTED_STAGES:
        issues.append(f"lifecycle stages must exactly match {EXPECTED_STAGES}; observed {observed_stages}")

    profile_ids = [item["profile_id"] for item in matrix["review_profiles"]]
    issues.extend(f"duplicate review profile: {item}" for item in _duplicates(profile_ids))
    expected_profiles = _profile_enum(skill_root)
    observed_profiles = set(profile_ids)
    if observed_profiles != expected_profiles:
        missing = sorted(expected_profiles - observed_profiles)
        unexpected = sorted(observed_profiles - expected_profiles)
        issues.append(f"review profile mismatch; missing={missing}, unexpected={unexpected}")

    route_ids = [item["route_id"] for item in matrix["synthesis_routes"]]
    issues.extend(f"duplicate synthesis route: {item}" for item in _duplicates(route_ids))
    missing_routes = sorted(REQUIRED_SYNTHESIS_ROUTES - set(route_ids))
    if missing_routes:
        issues.append(f"missing explicit synthesis routes: {missing_routes}")

    capability_ids = [item["capability_id"] for item in matrix["cross_cutting_capabilities"]]
    issues.extend(f"duplicate cross-cutting capability: {item}" for item in _duplicates(capability_ids))
    valid_stage_ids = set(stage_ids)
    for capability in matrix["cross_cutting_capabilities"]:
        unknown = sorted(set(capability["stage_ids"]) - valid_stage_ids)
        if unknown:
            issues.append(f"cross_cutting_capabilities.{capability['capability_id']}: unknown stages {unknown}")

    for collection_name in (
        "lifecycle_stages",
        "review_profiles",
        "synthesis_routes",
        "cross_cutting_capabilities",
    ):
        for item in matrix[collection_name]:
            if item["validation_level"] in ADVANCED_VALIDATION_LEVELS and not item["validation_evidence"]:
                issues.append(
                    f"{collection_name}: {item.get('stage_id') or item.get('profile_id') or item.get('route_id') or item.get('capability_id')} "
                    "claims advanced validation without evidence"
                )

    issues.extend(_artifact_issues(matrix, skill_root))

    validation_counts = Counter(
        item["validation_level"]
        for collection in (
            matrix["lifecycle_stages"],
            matrix["review_profiles"],
            matrix["synthesis_routes"],
            matrix["cross_cutting_capabilities"],
        )
        for item in collection
    )
    implementation_counts = Counter(
        item["implementation_level"]
        for collection in (matrix["lifecycle_stages"], matrix["cross_cutting_capabilities"])
        for item in collection
    )
    profile_synthesis_counts = Counter(item["synthesis_implementation"] for item in matrix["review_profiles"])

    return {
        "valid": not issues,
        "matrix_id": matrix["matrix_id"],
        "as_of": matrix["as_of"],
        "coverage": {
            "lifecycle_stages_declared": len(stage_ids),
            "lifecycle_contract_complete": observed_stages == EXPECTED_STAGES,
            "review_profiles_declared": len(profile_ids),
            "review_profile_catalog_complete": observed_profiles == expected_profiles,
            "synthesis_routes_declared": len(route_ids),
            "required_synthesis_routes_explicit": not missing_routes,
            "cross_cutting_capabilities_declared": len(capability_ids),
        },
        "implementation_counts": dict(sorted(implementation_counts.items())),
        "profile_synthesis_counts": dict(sorted(profile_synthesis_counts.items())),
        "validation_counts": dict(sorted(validation_counts.items())),
        "advanced_validation_claims": sum(validation_counts[level] for level in ADVANCED_VALIDATION_LEVELS),
        "issues": issues,
    }


def _issue(code: str, message: str) -> dict[str, str]:
    return {"severity": "error", "code": code, "message": message}


def _versioned_terms(pack: dict[str, Any]) -> list[dict[str, str]]:
    return sorted(
        (
            {
                "system": item["system"],
                "release": item["release"],
                "content_sha256": item["content_sha256"],
            }
            for item in pack["terminology_releases"]
        ),
        key=lambda item: (item["system"], item["release"], item["content_sha256"]),
    )


def _authority_versions(pack: dict[str, Any]) -> list[dict[str, str]]:
    return sorted(
        (
            {
                "source_id": item["source_id"],
                "version": item["version"],
                "content_sha256": item["content_sha256"],
            }
            for item in pack["authority_sources"]
        ),
        key=lambda item: (item["source_id"], item["version"], item["content_sha256"]),
    )


def _pack_evidence_paths(
    packs: list[dict[str, Any]],
    capability_paths: dict[str, list[str]],
) -> list[str]:
    capabilities = {
        capability
        for pack in packs
        for capability in pack["capabilities"]
    }
    return sorted({
        path
        for capability in capabilities
        for path in capability_paths.get(capability, [])
    })


def audit_biomedical_coverage(
    pack_root: Path,
    capability_matrix: dict[str, Any],
) -> dict[str, Any]:
    """Audit the frozen biomedical pack inventory without promoting test fixtures."""
    pack_root = Path(pack_root).resolve()
    skill_root = pack_root.parents[1]
    issues: list[dict[str, str]] = []

    try:
        matrix_report = audit_capability_matrix(capability_matrix, skill_root)
    except (CoverageAuditError, KeyError, TypeError) as exc:
        return {
            "valid": False,
            "profiles": [],
            "specialties": [],
            "capabilities": [],
            "unsupported_combinations": [],
            "issues": [_issue("invalid_capability_matrix", str(exc))],
        }
    issues.extend(
        _issue("invalid_capability_matrix", message)
        for message in matrix_report["issues"]
    )
    biomedical = capability_matrix["biomedical_coverage"]

    configured_root = (skill_root / biomedical["pack_root"]).resolve()
    if configured_root != pack_root:
        issues.append(_issue(
            "pack_root_mismatch",
            f"matrix pack root is {configured_root}; audited root is {pack_root}",
        ))

    try:
        packs = load_domain_packs(pack_root)
    except BiomedicalDomainError as exc:
        return {
            "valid": False,
            "profiles": [],
            "specialties": [],
            "capabilities": [],
            "unsupported_combinations": [],
            "issues": issues + [_issue("domain_pack_integrity_failed", str(exc))],
        }

    actual_by_id = {pack["pack_id"]: pack for pack in packs}
    inventory = biomedical["pack_inventory"]
    inventory_ids = [item["pack_id"] for item in inventory]
    for duplicate in _duplicates(inventory_ids):
        issues.append(_issue("duplicate_pack_inventory", f"duplicate pack inventory entry: {duplicate}"))
    expected_by_id = {item["pack_id"]: item for item in inventory}
    missing_pack_ids = sorted(set(expected_by_id) - set(actual_by_id))
    unexpected_pack_ids = sorted(set(actual_by_id) - set(expected_by_id))
    if missing_pack_ids:
        issues.append(_issue("missing_domain_pack", f"missing packs: {missing_pack_ids}"))
    if unexpected_pack_ids:
        issues.append(_issue("unregistered_domain_pack", f"unregistered packs: {unexpected_pack_ids}"))

    for pack_id in sorted(set(expected_by_id) & set(actual_by_id)):
        expected = expected_by_id[pack_id]
        actual = actual_by_id[pack_id]
        if expected["version"] != actual["version"]:
            issues.append(_issue(
                "domain_pack_version_changed",
                f"{pack_id}: expected {expected['version']}, observed {actual['version']}",
            ))
        if expected["content_sha256"] != actual["content_sha256"]:
            issues.append(_issue(
                "domain_pack_hash_changed",
                f"{pack_id}: frozen content hash does not match the live pack",
            ))
        if expected["validation_level"] != actual["validation"]["level"]:
            issues.append(_issue(
                "domain_pack_validation_changed",
                f"{pack_id}: frozen validation level does not match the live pack",
            ))
        if sorted(expected["terminology_releases"], key=lambda item: (item["system"], item["release"])) != _versioned_terms(actual):
            issues.append(_issue(
                "terminology_release_changed",
                f"{pack_id}: terminology system, release, or content hash changed",
            ))
        if sorted(expected["authority_versions"], key=lambda item: (item["source_id"], item["version"])) != _authority_versions(actual):
            issues.append(_issue(
                "authority_version_changed",
                f"{pack_id}: authority version or content hash changed",
            ))

    expected_profiles = set(biomedical["expected_profile_ids"])
    matrix_profiles = {item["profile_id"] for item in capability_matrix["review_profiles"]}
    if expected_profiles != matrix_profiles:
        issues.append(_issue(
            "profile_catalog_drift",
            f"expected profiles {sorted(expected_profiles)}; matrix profiles {sorted(matrix_profiles)}",
        ))

    expected_specialties = set(biomedical["expected_specialty_ids"])
    observed_specialties = {
        specialty["specialty_id"]
        for pack in packs
        for specialty in pack["specialties"]
    }
    if expected_specialties != observed_specialties:
        issues.append(_issue(
            "specialty_catalog_drift",
            f"expected specialties {sorted(expected_specialties)}; live specialties {sorted(observed_specialties)}",
        ))

    expected_capabilities = {
        capability
        for pack in packs
        for capability in pack["capabilities"]
    }
    capability_entries = biomedical["capability_evidence"]
    capability_ids = [item["capability_id"] for item in capability_entries]
    for duplicate in _duplicates(capability_ids):
        issues.append(_issue(
            "duplicate_capability_evidence",
            f"duplicate capability evidence entry: {duplicate}",
        ))
    capability_paths = {
        item["capability_id"]: item["evidence_paths"]
        for item in capability_entries
    }
    if expected_capabilities != set(capability_paths):
        issues.append(_issue(
            "capability_catalog_drift",
            f"pack capabilities {sorted(expected_capabilities)}; matrix capabilities {sorted(capability_paths)}",
        ))
    for capability_id, paths in sorted(capability_paths.items()):
        for relative in paths:
            evidence_path = (skill_root / relative).resolve()
            try:
                evidence_path.relative_to(skill_root)
            except ValueError:
                issues.append(_issue(
                    "capability_evidence_path_escape",
                    f"{capability_id}: evidence path escapes skill root: {relative}",
                ))
                continue
            if not evidence_path.is_file():
                issues.append(_issue(
                    "missing_capability_evidence",
                    f"{capability_id}: missing evidence path: {relative}",
                ))

    active_packs = [pack for pack in packs if pack["status"] == "active"]
    foundation = next(
        (pack for pack in active_packs if pack["pack_type"] == "foundation"),
        None,
    )
    profiles: list[dict[str, Any]] = []
    for profile_id in sorted(expected_profiles):
        profile_packs = [
            pack for pack in active_packs
            if pack["pack_type"] == "review_profile"
            and profile_id in pack["supported_review_families"]
        ]
        foundation_support = bool(
            foundation and profile_id in foundation["supported_review_families"]
        )
        relevant = profile_packs or ([foundation] if foundation_support and foundation else [])
        if profile_packs:
            implementation_level = "pack_available"
            validation_level = min(
                (pack["validation"]["level"] for pack in profile_packs),
                key=("contract_only", "fixture_tested", "retrospectively_tested", "externally_validated").index,
            )
            known_gaps = ["No external scientific validation is established by fixture or contract evidence."]
        elif foundation_support:
            implementation_level = "foundation_fallback"
            validation_level = "contract_only"
            known_gaps = ["No profile-specific domain pack; biomedical foundation fallback only."]
        else:
            implementation_level = "unsupported"
            validation_level = "none"
            known_gaps = ["No active domain pack supports this review profile."]
        profiles.append({
            "id": profile_id,
            "implementation_level": implementation_level,
            "validation_level": validation_level,
            "scientific_claim_level": biomedical["scientific_claim_ceiling"],
            "evidence_paths": _pack_evidence_paths(relevant, capability_paths),
            "known_gaps": known_gaps,
        })

    specialties: list[dict[str, Any]] = []
    for specialty_id in sorted(expected_specialties):
        specialty_packs = [
            pack for pack in active_packs
            if specialty_id in {item["specialty_id"] for item in pack["specialties"]}
        ]
        specialties.append({
            "id": specialty_id,
            "implementation_level": "pack_available" if specialty_packs else "unsupported",
            "validation_level": (
                "contract_only" if specialty_packs else "none"
            ),
            "scientific_claim_level": biomedical["scientific_claim_ceiling"],
            "evidence_paths": _pack_evidence_paths(specialty_packs, capability_paths),
            "known_gaps": (
                ["Specialty resolution is contract-level and not externally validated."]
                if specialty_packs else ["No active pack declares this specialty."]
            ),
        })

    unsupported_combinations = [
        {
            "profile_id": profile_id,
            "specialty_id": specialty_id,
            "reason_codes": sorted(reason_codes),
        }
        for profile_id in sorted(expected_profiles)
        for specialty_id in sorted(expected_specialties)
        for reason_codes in [[
            *([] if foundation and profile_id in foundation["supported_review_families"] else ["profile_not_supported"]),
            *([] if specialty_id in observed_specialties else ["specialty_not_supported"]),
        ]]
        if reason_codes
    ]

    pack_state = [
        {
            "pack_id": pack["pack_id"],
            "version": pack["version"],
            "content_sha256": pack["content_sha256"],
            "terminology_releases": _versioned_terms(pack),
            "authority_versions": _authority_versions(pack),
        }
        for pack in sorted(active_packs, key=lambda item: item["pack_id"])
    ]
    return {
        "schema_version": "1.0",
        "report_id": f"biomedical-coverage:{capability_matrix['matrix_id']}",
        "registry_sha256": sha256_json(pack_state),
        "generated_at_utc": f"{capability_matrix['as_of']}T00:00:00Z",
        "application_domain": biomedical["application_domain"],
        "scientific_claim_ceiling": SCIENTIFIC_CLAIM_CEILING,
        "pack_state": pack_state,
        "profiles": profiles,
        "specialties": specialties,
        "capabilities": [
            {"capability_id": item, "evidence_paths": capability_paths.get(item, [])}
            for item in sorted(expected_capabilities)
        ],
        "unsupported_combinations": unsupported_combinations,
        "issues": issues,
        "valid": not issues and not unsupported_combinations,
    }
