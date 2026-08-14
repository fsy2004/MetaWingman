"""Deterministically compose models by capability, risk, calibration, and diversity."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

from .schema_guard import validate_document


RouteStatus = Literal["routed", "abstained"]
ROLE_PLANS = {
    "low": ("executor",),
    "medium": ("proposer", "verifier"),
    "high": ("proposal", "opposition", "judge"),
    "irreversible": ("proposal", "opposition", "judge"),
}
ROLE_METRICS = {
    "executor": ("critical_error_free", "accuracy"),
    "proposer": ("recall", "accuracy"),
    "verifier": ("critical_error_free", "precision"),
    "proposal": ("recall", "accuracy"),
    "opposition": ("counterevidence_recall", "recall"),
    "judge": ("critical_error_free", "accuracy"),
}


@dataclass(frozen=True)
class RoutingDecision:
    status: RouteStatus
    assignments: dict[str, str]
    reason_codes: tuple[str, ...]
    test_time_calls: int
    requires_human_signature: bool


def _metric(model: dict[str, Any], role: str) -> float:
    metrics = model["calibration"]["metrics"]
    for name in ROLE_METRICS[role]:
        if name in metrics:
            return float(metrics[name])
    return -1.0


def _eligible(
    model: dict[str, Any],
    capability: str,
    modalities: set[str],
    required_tools: set[str],
) -> bool:
    return (
        capability in model["capabilities"]
        and modalities.issubset(set(model["modalities"]))
        and required_tools.issubset(set(model["allowed_tools"]))
    )


def route_models(
    registry: dict[str, Any],
    capability: str,
    modalities: set[str],
    risk_class: str,
    required_tools: set[str] | None = None,
) -> RoutingDecision:
    validate_document(registry, "model_registry")
    if risk_class not in ROLE_PLANS:
        raise ValueError(f"Unsupported risk class: {risk_class}")
    tools = required_tools or set()
    eligible = [
        model for model in registry["models"]
        if _eligible(model, capability, modalities, tools)
    ]
    roles = ROLE_PLANS[risk_class]
    if len(eligible) < len(roles):
        return RoutingDecision(
            "abstained", {}, ("insufficient_capability_coverage",), 0,
            risk_class in {"high", "irreversible"},
        )

    assignments: dict[str, str] = {}
    selected: list[dict[str, Any]] = []
    for role in roles:
        remaining = [model for model in eligible if model not in selected]
        remaining.sort(
            key=lambda model: (
                model["provider"] not in {item["provider"] for item in selected},
                _metric(model, role),
                model["model_id"],
            ),
            reverse=True,
        )
        chosen = remaining[0]
        assignments[role] = chosen["model_id"]
        selected.append(chosen)

    if risk_class in {"high", "irreversible"} and len({model["provider"] for model in selected}) < 2:
        return RoutingDecision(
            "abstained", {}, ("insufficient_provider_diversity",), 0, True,
        )
    return RoutingDecision(
        "routed",
        assignments,
        (),
        len(roles),
        risk_class in {"high", "irreversible"},
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("registry", type=Path)
    parser.add_argument("--capability", required=True)
    parser.add_argument("--modality", action="append", default=["text"])
    parser.add_argument("--risk", choices=sorted(ROLE_PLANS), default="low")
    parser.add_argument("--tool", action="append", default=[])
    args = parser.parse_args()
    registry = json.loads(args.registry.read_text(encoding="utf-8"))
    decision = route_models(registry, args.capability, set(args.modality), args.risk, set(args.tool))
    print(json.dumps(asdict(decision), indent=2))
    return 0 if decision.status == "routed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
