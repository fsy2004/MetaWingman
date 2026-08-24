#!/usr/bin/env python3
"""Evaluate the design-selection skill against frozen gold review profiles.

Compares the agent's proposed `(profile, estimand, route)` (with living flag)
against the representative-case gold profile, plus deterministic baselines
(PICO-only always-pairwise, bibliometric/LLM-order ranking, fixed-profile).
Metrics are predeclared and continuous; the base profile is the primary axis,
living/abstention are reported separately.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from metawingman.scripts.metawingman_core.design_selection import PROFILE_STRATA


def _profile_score(predicted: dict[str, Any], gold: dict[str, Any]) -> tuple[bool, bool]:
    """Return (base-profile correct, living-flag correct)."""
    return (
        predicted.get("profile") == gold.get("profile"),
        bool(predicted.get("living")) == bool(gold.get("living")),
    )


def evaluate_design_selection(
    predictions: list[dict[str, Any]],
    gold: list[dict[str, Any]],
    *,
    baselines: dict[str, list[dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    if len(predictions) != len(gold):
        raise ValueError("predictions and gold must have the same case count")
    if not predictions:
        raise ValueError("no design-selection cases")

    def _accuracy(rows: list[dict[str, Any]], gold_rows: list[dict[str, Any]]) -> tuple[float, int, int]:
        att = sum(_profile_score(p, g)[0] for p, g in zip(rows, gold_rows))
        # abstention: a proposed empty profile is an abstention, not a wrong answer;
        # we count it separately so it does not inflate false-opportunity.
        abstained = sum(1 for p in rows if p.get("abstain"))
        return (att / len(rows), abstained, len(rows))

    # primary: base-profile match accuracy over all cases (abstentions counted as miss)
    base_match = sum(1 for p, g in zip(predictions, gold) if _profile_score(p, g)[0])
    living_match = sum(1 for p, g in zip(predictions, gold) if _profile_score(p, g)[1])
    n = len(predictions)
    abstained = sum(1 for p in predictions if p.get("abstain"))

    # confusion over strata (exclude abstain)
    labels = list(PROFILE_STRATA)
    confusion = {truth: {pred: 0 for pred in labels + ["abstain"]} for truth in labels}
    for p, g in zip(predictions, gold):
        truth = g.get("profile") or "?:?:?"
        pred = p.get("profile") or "abstain"
        if truth in confusion and pred in confusion[truth]:
            confusion[truth][pred] += 1

    per_family: dict[str, list[bool]] = defaultdict(list)
    for p, g in zip(predictions, gold):
        per_family[g.get("case_id") or str(len(per_family))].append(_profile_score(p, g)[0])

    result: dict[str, Any] = {
        "cases": n,
        "profile_match_accuracy": base_match / n,
        "living_flag_accuracy": living_match / n,
        "abstain_rate": abstained / n,
        "macro_over_strata": sum(sum(v) / len(v) for v in per_family.values()) / len(per_family),
        "false_opportunity_rate": sum(
            1 for p, g in zip(predictions, gold)
            if not p.get("abstain") and p.get("profile") and p.get("profile") != g.get("profile")
        ) / n,
        "confusion": confusion,
        "per_case_correct": {k: v for k, v in per_family.items()},
    }

    if baselines:
        baseline_metrics = {}
        for name, rows in baselines.items():
            att, abst, cnt = _accuracy(rows, gold)
            baseline_metrics[name] = {
                "profile_match_accuracy": att, "abstain_rate": abst / cnt if cnt else 0.0,
            }
        result["baselines"] = baseline_metrics
    return result


def unconditional_baseline(profile: str, cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """A baseline that always predicts a fixed profile (e.g. PICO-only / pairwise)."""
    return [
        {"profile": profile, "living": False, "abstain": False, "estimand": "", "synthesis_route": ""}
        for _ in cases
    ]
