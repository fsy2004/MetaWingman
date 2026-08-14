"""Deterministically recompute common effect estimates from verified primitives."""

from __future__ import annotations

import math
import statistics
from datetime import datetime, timezone
from typing import Any, Callable

from .schema_guard import SchemaValidationError, validate_document


RECALCULATOR_VERSION = "1.0"


class EffectCalculationError(ValueError):
    """Raised when an effect estimate cannot be computed from valid inputs."""


def _number(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise EffectCalculationError(f"{name} must be a finite number")
    return float(value)


def _positive(value: Any, name: str) -> float:
    result = _number(value, name)
    if result <= 0:
        raise EffectCalculationError(f"{name} must be positive")
    return result


def _count(value: Any, name: str) -> float:
    result = _number(value, name)
    if result < 0 or not result.is_integer():
        raise EffectCalculationError(f"{name} must be a non-negative integer")
    return result


def _candidate_values(candidates: list[dict[str, Any]]) -> tuple[dict[str, float], list[str]]:
    values: dict[str, float] = {}
    ids: list[str] = []
    for candidate in candidates:
        try:
            validate_document(candidate, "extraction_candidate")
        except SchemaValidationError as exc:
            raise EffectCalculationError(str(exc)) from exc
        if candidate["status"] != "accepted" or candidate["verification"]["status"] != "passed":
            raise EffectCalculationError(f"Input candidate is not accepted and verified: {candidate['candidate_id']}")
        if candidate["value"]["data_type"] not in {"number", "integer"}:
            raise EffectCalculationError(f"Input candidate is not numeric: {candidate['candidate_id']}")
        field = candidate["field"]
        if field in values:
            raise EffectCalculationError(f"Duplicate input field: {field}")
        values[field] = _number(candidate["value"]["normalized"], field)
        ids.append(candidate["candidate_id"])
    return values, ids


def _binary_cells(values: dict[str, float], correction: float) -> tuple[float, float, float, float]:
    a = _count(values.get("events_intervention"), "events_intervention")
    n1 = _positive(values.get("total_intervention"), "total_intervention")
    c = _count(values.get("events_control"), "events_control")
    n0 = _positive(values.get("total_control"), "total_control")
    if a > n1 or c > n0:
        raise EffectCalculationError("Events cannot exceed arm totals")
    b, d = n1 - a, n0 - c
    if min(a, b, c, d) == 0:
        if correction <= 0:
            raise EffectCalculationError("A zero cell requires an explicit positive continuity correction")
        a, b, c, d = (cell + correction for cell in (a, b, c, d))
    return a, b, c, d


def _calculate_log_rr(values: dict[str, float], correction: float) -> tuple[float, float, str]:
    a, b, c, d = _binary_cells(values, correction)
    n1, n0 = a + b, c + d
    estimate = math.log((a / n1) / (c / n0))
    variance = 1 / a - 1 / n1 + 1 / c - 1 / n0
    return estimate, variance, "log((a/(a+b))/(c/(c+d))); var=1/a-1/(a+b)+1/c-1/(c+d)"


def _calculate_log_or(values: dict[str, float], correction: float) -> tuple[float, float, str]:
    a, b, c, d = _binary_cells(values, correction)
    return math.log(a * d / (b * c)), 1 / a + 1 / b + 1 / c + 1 / d, "log((a*d)/(b*c)); var=1/a+1/b+1/c+1/d"


def _calculate_rd(values: dict[str, float], _: float) -> tuple[float, float, str]:
    a = _count(values.get("events_intervention"), "events_intervention")
    n1 = _positive(values.get("total_intervention"), "total_intervention")
    c = _count(values.get("events_control"), "events_control")
    n0 = _positive(values.get("total_control"), "total_control")
    if a > n1 or c > n0:
        raise EffectCalculationError("Events cannot exceed arm totals")
    p1, p0 = a / n1, c / n0
    return p1 - p0, p1 * (1 - p1) / n1 + p0 * (1 - p0) / n0, "p1-p0; var=p1(1-p1)/n1+p0(1-p0)/n0"


def _calculate_md(values: dict[str, float], _: float) -> tuple[float, float, str]:
    m1 = _number(values.get("mean_intervention"), "mean_intervention")
    m0 = _number(values.get("mean_control"), "mean_control")
    sd1 = _positive(values.get("sd_intervention"), "sd_intervention")
    sd0 = _positive(values.get("sd_control"), "sd_control")
    n1 = _positive(values.get("total_intervention"), "total_intervention")
    n0 = _positive(values.get("total_control"), "total_control")
    return m1 - m0, sd1 ** 2 / n1 + sd0 ** 2 / n0, "m1-m0; var=sd1^2/n1+sd0^2/n0"


def _calculate_smd(values: dict[str, float], _: float) -> tuple[float, float, str]:
    m1 = _number(values.get("mean_intervention"), "mean_intervention")
    m0 = _number(values.get("mean_control"), "mean_control")
    sd1 = _positive(values.get("sd_intervention"), "sd_intervention")
    sd0 = _positive(values.get("sd_control"), "sd_control")
    n1 = _positive(values.get("total_intervention"), "total_intervention")
    n0 = _positive(values.get("total_control"), "total_control")
    if n1 + n0 <= 2:
        raise EffectCalculationError("SMD requires total degrees of freedom greater than zero")
    pooled = math.sqrt(((n1 - 1) * sd1 ** 2 + (n0 - 1) * sd0 ** 2) / (n1 + n0 - 2))
    if pooled == 0:
        raise EffectCalculationError("Pooled standard deviation is zero")
    d = (m1 - m0) / pooled
    correction = 1 - 3 / (4 * (n1 + n0) - 9)
    g = correction * d
    variance = (n1 + n0) / (n1 * n0) + g ** 2 / (2 * (n1 + n0 - 2))
    return g, variance, "Hedges g=J*(m1-m0)/sp; var=(n1+n0)/(n1*n0)+g^2/(2*(n1+n0-2))"


def _calculate_fisher_z(values: dict[str, float], _: float) -> tuple[float, float, str]:
    correlation = _number(values.get("correlation"), "correlation")
    n = _positive(values.get("total"), "total")
    if not -1 < correlation < 1 or n <= 3:
        raise EffectCalculationError("Fisher z requires -1 < r < 1 and n > 3")
    return math.atanh(correlation), 1 / (n - 3), "atanh(r); var=1/(n-3)"


def _calculate_logit_proportion(values: dict[str, float], correction: float) -> tuple[float, float, str]:
    events = _count(values.get("events"), "events")
    total = _positive(values.get("total"), "total")
    if events > total:
        raise EffectCalculationError("Events cannot exceed total")
    non_events = total - events
    if min(events, non_events) == 0:
        if correction <= 0:
            raise EffectCalculationError("Boundary proportion requires a positive continuity correction")
        events += correction
        non_events += correction
    return math.log(events / non_events), 1 / events + 1 / non_events, "log(events/non_events); var=1/events+1/non_events"


CALCULATORS: dict[str, tuple[Callable[[dict[str, float], float], tuple[float, float, str]], str, str]] = {
    "log_risk_ratio": (_calculate_log_rr, "log", "risk_ratio"),
    "log_odds_ratio": (_calculate_log_or, "log", "odds_ratio"),
    "risk_difference": (_calculate_rd, "identity", "risk_difference"),
    "mean_difference": (_calculate_md, "identity", "mean_difference"),
    "standardized_mean_difference": (_calculate_smd, "identity", "hedges_g"),
    "fisher_z": (_calculate_fisher_z, "fisher_z", "correlation"),
    "logit_proportion": (_calculate_logit_proportion, "logit", "proportion"),
}


def _normal_quantile(confidence_level: float) -> float:
    if not 0 < confidence_level < 1:
        raise EffectCalculationError("confidence_level must be between 0 and 1")
    return statistics.NormalDist().inv_cdf(0.5 + confidence_level / 2)


def _back_transform(scale: str, value: float) -> float:
    if scale == "log":
        return math.exp(value)
    if scale == "fisher_z":
        return math.tanh(value)
    if scale == "logit":
        return 1 / (1 + math.exp(-value))
    return value


def calculate_effect(
    candidates: list[dict[str, Any]],
    *,
    effect_id: str,
    result_id: str,
    measure: str,
    direction: str,
    confidence_level: float = 0.95,
    continuity_correction: float | None = None,
    created_at_utc: str | None = None,
) -> dict[str, Any]:
    values, candidate_ids = _candidate_values(candidates)
    if measure not in CALCULATORS:
        raise EffectCalculationError(f"Unsupported effect measure: {measure}")
    correction = 0.0 if continuity_correction is None else _number(continuity_correction, "continuity_correction")
    if correction < 0:
        raise EffectCalculationError("continuity_correction cannot be negative")
    calculator, scale, back_measure = CALCULATORS[measure]
    estimate, variance, formula = calculator(values, correction)
    if not math.isfinite(estimate) or not math.isfinite(variance) or variance <= 0:
        raise EffectCalculationError("Computed estimate or variance is not finite and positive")
    standard_error = math.sqrt(variance)
    quantile = _normal_quantile(confidence_level)
    lower, upper = estimate - quantile * standard_error, estimate + quantile * standard_error
    output = {
        "schema_version": "1.0",
        "effect_id": effect_id,
        "result_id": result_id,
        "measure": measure,
        "scale": scale,
        "direction": direction,
        "estimate": estimate,
        "standard_error": standard_error,
        "variance": variance,
        "confidence_level": confidence_level,
        "ci_lower": lower,
        "ci_upper": upper,
        "back_transformed": {
            "measure": back_measure,
            "estimate": _back_transform(scale, estimate),
            "ci_lower": _back_transform(scale, lower),
            "ci_upper": _back_transform(scale, upper),
        },
        "input_candidate_ids": candidate_ids,
        "formula": formula,
        "continuity_correction": continuity_correction,
        "software": {"name": "metawingman-effect-recalculator", "version": RECALCULATOR_VERSION},
        "verification": {
            "status": "passed",
            "checks": ["inputs_accepted", "inputs_schema_valid", "finite_positive_variance", "ci_recomputed"],
            "tolerance": 1e-12,
        },
        "created_at_utc": created_at_utc or datetime.now(timezone.utc).isoformat(),
    }
    try:
        validate_document(output, "effect_estimate")
    except SchemaValidationError as exc:
        raise EffectCalculationError(str(exc)) from exc
    return output
