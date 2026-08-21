"""Deterministically enumerate synthesis methods without making scientific choices."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .schema_guard import validate_document
from .state_store import sha256_json


class SynthesisMethodRouteError(ValueError):
    """Raised when the method registry or candidate is inconsistent."""


def load_method_registry(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    routes = payload.get("routes")
    if payload.get("schema_version") != "1.0" or not isinstance(routes, list) or not routes:
        raise SynthesisMethodRouteError("method registry is missing a non-empty routes array")
    ids = [str(item.get("route_id") or "") for item in routes]
    if any(not item for item in ids) or len(ids) != len(set(ids)):
        raise SynthesisMethodRouteError("method registry route_id values must be non-empty and unique")
    if "no_pooling" not in ids:
        raise SynthesisMethodRouteError("method registry must include no_pooling")
    return routes


def _failed_checks(candidate: dict[str, Any], route: dict[str, Any]) -> list[str]:
    failed: set[str] = set()
    if candidate.get("review_family") not in route.get("review_families", []):
        failed.add("review_family_compatibility")
    observations = {
        str(item.get("check_id")): str(item.get("status"))
        for item in candidate.get("assumption_checks", [])
        if isinstance(item, dict)
    }
    for check in route.get("required_checks", []):
        if observations.get(str(check)) == "failed":
            failed.add(str(check))
    return sorted(failed)


def enumerate_synthesis_routes(
    context: dict[str, Any],
    candidate: dict[str, Any],
    routes: list[dict[str, Any]],
    *,
    created_at_utc: str,
) -> dict[str, Any]:
    if candidate.get("context_id") != context.get("context_id"):
        raise SynthesisMethodRouteError("candidate context_id does not match clinical context")
    compatible: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for route in sorted(routes, key=lambda item: str(item["route_id"])):
        failures = _failed_checks(candidate, route)
        record = {"route_id": route["route_id"], "failed_checks": failures}
        (rejected if failures else compatible).append(record)
    substantive = [item for item in compatible if item["route_id"] != "no_pooling"]
    selected = substantive[0]["route_id"] if len(substantive) == 1 else None
    if selected is not None:
        status = "selected"
    elif substantive:
        status = "requires_choice"
    else:
        status = "abstained"
    fallback = "no_pooling" if any(item["route_id"] == "no_pooling" for item in compatible) else None
    decision_basis = {
        "candidate_id": candidate["candidate_id"],
        "compatible": compatible,
        "rejected": rejected,
        "created_at_utc": created_at_utc,
    }
    decision = {
        "schema_version": "1.0",
        "decision_id": f"route-{sha256_json(decision_basis)[:20]}",
        "candidate_id": candidate["candidate_id"],
        "compatible_routes": compatible,
        "rejected_routes": rejected,
        "selected_route_id": selected,
        "fallback_route_id": fallback,
        "required_checks": sorted({check for route in routes for check in route.get("required_checks", [])}),
        "evidence_anchor_ids": list(candidate.get("evidence_anchor_ids", [])),
        "status": status,
        "created_at_utc": created_at_utc,
    }
    validate_document(decision, "method_route_decision")
    return decision
