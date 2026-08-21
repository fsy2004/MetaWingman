"""Apply reflections only after named external verifiers return observations."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from .review_case import read_case_state
from .schema_guard import validate_document


def _abstained(reflection: dict[str, Any], reason: str) -> dict[str, Any]:
    return {"reflection_id": reflection["reflection_id"], "disposition": "abstained", "state_changed": False, "reason": reason, "observations": []}


def reflect_on_assertion(
    project: Path,
    reflection: dict[str, Any],
    verifiers: dict[str, Callable[[dict[str, Any]], dict[str, Any]]],
) -> dict[str, Any]:
    validate_document(reflection, "scientific_reflection")
    read_case_state(project)
    if not reflection["external_tests"]:
        return _abstained(reflection, "external_observation_required")
    observations: list[dict[str, Any]] = []
    for test in reflection["external_tests"]:
        verifier = verifiers.get(test["verifier_id"])
        if verifier is None:
            return _abstained(reflection, "verifier_unavailable")
        observation = verifier(test["input"])
        observations.append(observation)
        if observation.get("status") != "verified" or observation.get("external") is not True:
            return {"reflection_id": reflection["reflection_id"], "disposition": "abstained", "state_changed": False, "reason": "external_test_failed", "observations": observations}
    return {"reflection_id": reflection["reflection_id"], "disposition": "verified_candidate_change", "state_changed": False, "reason": "human_or_stage_transition_required", "observations": observations}
