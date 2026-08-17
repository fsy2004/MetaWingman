"""Measure repeated-run, position, and judge-order reliability."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from itertools import combinations
from typing import Any, Iterable

from .schema_guard import SchemaValidationError, validate_document


@dataclass(frozen=True)
class ReliabilityGate:
    passed: bool
    reason_codes: tuple[str, ...]


def _rate(values: Iterable[bool]) -> float:
    values = list(values)
    return sum(values) / len(values) if values else 0.0


def evaluate_reliability(
    trials: Iterable[dict[str, Any]],
    *,
    repeat_k: int,
    min_pass_power_k: float,
    max_critical_error_rate: float,
    max_position_gap: float,
    max_judge_order_disagreement: float,
) -> dict[str, Any]:
    if repeat_k < 1:
        raise ValueError("repeat_k must be at least 1")
    records = list(trials)
    if not records:
        raise ValueError("At least one reliability trial is required")
    seen_trials: set[str] = set()
    for record in records:
        try:
            validate_document(record, "reliability_trial")
        except SchemaValidationError as exc:
            raise ValueError(str(exc)) from exc
        if record["trial_id"] in seen_trials:
            raise ValueError(f"Duplicate trial_id: {record['trial_id']}")
        seen_trials.add(record["trial_id"])

    by_case: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        by_case[record["case_id"]].append(record)

    per_case: list[dict[str, Any]] = []
    insufficient_repeats: list[str] = []
    for case_id, case_trials in sorted(by_case.items()):
        pass_rate = _rate(record["passed"] for record in case_trials)
        replicates = {record["replicate"] for record in case_trials}
        if len(replicates) < repeat_k:
            insufficient_repeats.append(case_id)
        per_case.append({
            "case_id": case_id,
            "trials": len(case_trials),
            "unique_replicates": len(replicates),
            "pass_rate": pass_rate,
            "pass_power_k": pass_rate ** repeat_k,
            "critical_error_rate": _rate(record["critical_error"] for record in case_trials),
        })

    pass_power_k = sum(item["pass_power_k"] for item in per_case) / len(per_case)
    critical_error_rate = _rate(record["critical_error"] for record in records)

    position_rates: dict[str, float] = {}
    for position in ("start", "middle", "end"):
        values = [record["passed"] for record in records if record["position"] == position]
        if values:
            position_rates[position] = _rate(values)
    position_gap = (
        max(position_rates.values()) - min(position_rates.values())
        if len(position_rates) >= 2 else 0.0
    )

    order_case_disagreements: list[float] = []
    order_audit: list[dict[str, Any]] = []
    for case_id, case_trials in sorted(by_case.items()):
        order_trials = [record for record in case_trials if record["judge_order"]]
        distinct_orders = {tuple(record["judge_order"]) for record in order_trials}
        if len(distinct_orders) < 2:
            continue
        pairs = list(combinations(order_trials, 2))
        cross_order_pairs = [pair for pair in pairs if pair[0]["judge_order"] != pair[1]["judge_order"]]
        disagreement = _rate(a["decision"] != b["decision"] for a, b in cross_order_pairs)
        order_case_disagreements.append(disagreement)
        order_audit.append({
            "case_id": case_id,
            "orders": [list(order) for order in sorted(distinct_orders)],
            "cross_order_pairs": len(cross_order_pairs),
            "decision_disagreement": disagreement,
        })
    judge_order_disagreement = (
        sum(order_case_disagreements) / len(order_case_disagreements)
        if order_case_disagreements else 0.0
    )

    reasons: list[str] = []
    if insufficient_repeats:
        reasons.append("insufficient_repeated_runs:" + ",".join(insufficient_repeats))
    if pass_power_k < min_pass_power_k:
        reasons.append("pass_power_k_below_floor")
    if critical_error_rate > max_critical_error_rate:
        reasons.append("critical_error_rate_above_ceiling")
    if position_gap > max_position_gap:
        reasons.append("position_gap_above_ceiling")
    if judge_order_disagreement > max_judge_order_disagreement:
        reasons.append("judge_order_disagreement_above_ceiling")

    return {
        "valid": not reasons,
        "reason_codes": reasons,
        "trials": len(records),
        "cases": len(by_case),
        "repeat_k": repeat_k,
        "pass_rate": _rate(record["passed"] for record in records),
        "pass_power_k": pass_power_k,
        "critical_error_rate": critical_error_rate,
        "position_pass_rates": position_rates,
        "max_position_gap": position_gap,
        "judge_order_disagreement": judge_order_disagreement,
        "judge_order_audit": order_audit,
        "per_case": per_case,
    }
