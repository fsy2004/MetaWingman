"""Audit lifecycle breadth without converting implementation into validation claims."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from .schema_guard import validate_document


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
