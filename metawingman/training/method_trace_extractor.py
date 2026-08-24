#!/usr/bin/env python3
"""Method-trace extractor — learn the *process*, never the answer.

We take a published meta-analysis / systematic review record and extract its
method trajectory (how the authors decided on a design, how they handled
heterogeneity, why they chose narrative synthesis, when they stopped) while
*stripping the numeric outcome* (pooled estimate, effect direction, I² point
value, GRADE grade, final effect direction). The agent never sees these, so it
cannot cheat by memorizing answers — it can only learn procedure.
Deterministic and offline.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# Fields that carry the *answer*. These are removed from the agent's view so it
# cannot learn from the result, only from the trajectory of decisions.
OUTCOME_FIELDS = (
    "final_effect",
    "pooled_estimate",
    "effect_direction",
    "i2",
    "grade_level",
    "effect_size",
    "confidence_interval",
    "overall_conclusion",
)


@dataclass(frozen=True)
class MethodTrace:
    case_id: str
    input_view: dict[str, Any]          # what the agent sees (no outcome values)
    method_trajectory: list[dict[str, Any]]  # step-by-step procedural decisions
    stripped_outcomes: dict[str, Any]   # the answer, stored out-of-band (never trained on)

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "input_view": self.input_view,
            "method_trajectory": self.method_trajectory,
            "stripped_outcomes": self.stripped_outcomes,
        }


def _strip(record: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Split a record into the agent-visible input view and the stripped outcome."""
    view: dict[str, Any] = {}
    stripped: dict[str, Any] = {}
    for key, value in record.items():
        if key in OUTCOME_FIELDS:
            stripped[key] = value
        else:
            view[key] = value
    return view, stripped


def _trajectory(view: dict[str, Any]) -> list[dict[str, Any]]:
    """Rebuild the method trajectory (the procedural decisions) from a record.

    The published record carries a list of 'method_steps' (or a blank field we
    synthesize from the design). Each step is a procedural decision with no
    numeric outcome. We keep the leading design / heterogeneity / stop signals.
    """
    steps = []
    raw_steps = view.get("method_steps") or []
    for step in raw_steps:
        if isinstance(step, dict):
            s = {k: v for k, v in step.items() if k not in OUTCOME_FIELDS}
            steps.append(s)
        else:
            steps.append({"step": str(step)})
    if not steps:
        # synthesize a minimal trajectory from structural signals if the record lacks one.
        design_parts = []
        if view.get("review_profile"):
            design_parts.append({"step": "design_selection", "value": view["review_profile"]})
        if view.get("heterogeneity_handling"):
            design_parts.append({"step": "heterogeneity_handling",
                                 "value": view["heterogeneity_handling"]})
        if view.get("synthesis_choice"):
            design_parts.append({"step": "synthesis_choice", "value": view["synthesis_choice"]})
        if view.get("stop_decision"):
            design_parts.append({"step": "stop_decision", "value": view["stop_decision"]})
        steps = design_parts
    return steps


def extract_method_trace(published_meta: dict[str, Any]) -> MethodTrace:
    """Extract the method trajectory, separating input view from the outcome."""
    view, stripped = _strip(published_meta)
    return MethodTrace(
        case_id=str(published_meta.get("case_id") or published_meta.get("study_id") or "case"),
        input_view=view,
        method_trajectory=_trajectory(view),
        stripped_outcomes=stripped,
    )
