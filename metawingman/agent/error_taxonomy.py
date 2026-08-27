#!/usr/bin/env python3
"""Error taxonomy: per-case failure attribution (MAST-inspired, but grounded in
our own runnable evidence rather than LLM annotation).

依据(出处): _deliverables/deep-study/notes/mast-failure-taxonomy.md (14 failure
             modes / 3 categories; "symptom != root cause"; category overlap low),
             论文: arXiv:2503.13657 (NeurIPS 2025). Adaptation note: MAST's
             conversational MAS modes (conversation reset, information withholding,
             ignoring other agents) do not apply to a deterministic orchestration
             with checkable intermediate objects; we keep the four categories we
             can *attribute from data*: coupling / label-proxy / taxonomy-exhaustion
             / input-noise (+ design-layer residual).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class ErrorAttribution:
    kind: str
    evidence: dict[str, Any]
    fixable: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "evidence": self.evidence, "fixable": self.fixable}


def classify(case: dict[str, Any], *, base_only_agrees: bool | None = None) -> list[ErrorAttribution]:
    """Attribute disagreement between the decision object and the reference.

    case fields: gold_profile / agent_profile / gold_poolable / agent_poolable /
    failures (list of dimension keys that failed).
    Uses ONLY the case's own data (no external annotator).
    """
    out: list[ErrorAttribution] = []
    gold_p = case.get("gold_profile")
    agent_p = case.get("agent_profile")
    dims = case.get("dimensions", {})
    design_ok = bool(dims.get("design_selection", gold_p == agent_p))
    pool_ok = bool(dims.get("guard_consistency", case.get("agent_poolable") == case.get("gold_poolable")))

    # 1) design-pooling coupling: design wrong AND guard convolved (refused/forced)
    if not design_ok and not pool_ok and agent_p == "structured_no_pooling":
        out.append(ErrorAttribution(
            "coupling_design_pooling",
            {"agent_profile": agent_p, "gold_profile": gold_p,
             "note": "design rewritten by a pooling judgment (historical bug class)"}))

    # 2) label proxy: our reference's design label disagrees with the rule even
    #    though a strong LLM agrees (taxonomy exhaustion of the extracted label)
    if not design_ok and base_only_agrees is True:
        out.append(ErrorAttribution(
            "taxonomy_exhaustion",
            {"agent_profile": agent_p, "gold_profile": gold_p,
             "note": "rule and LLM disagree with the extracted label (label/signal exhaustion)"}))

    # 3) pooling label proxy: guard approved but the reference did not pool
    if pool_ok is False and case.get("agent_poolable") is True and case.get("gold_poolable") is False:
        out.append(ErrorAttribution(
            "label_proxy_nonpooling",
            {"note": "alignment-consistent non-pooling decision (declined for non-alignment reasons)"}))

    # 4) input noise: evidence signals incomplete (unknown dims present)
    unknowns = case.get("unknown_dimensions") or []
    if unknowns:
        out.append(ErrorAttribution(
            "input_noise_unknown_dimensions",
            {"unknown_dimensions": unknowns}, fixable=True))

    if not out and not design_ok:
        out.append(ErrorAttribution("residual_design", {"gold_profile": gold_p,
                                                        "agent_profile": agent_p}))
    return out


def aggregate(cases: list[dict[str, Any]]) -> dict[str, Any]:
    from collections import Counter
    counts: Counter[str] = Counter()
    detail: dict[str, list[str]] = {}
    for c in cases:
        for attr in classify(c):
            counts[attr.kind] += 1
            detail.setdefault(attr.kind, []).append(c.get("case_id", ""))
    n = len(cases)
    return {"n": n,
            "category_counts": dict(counts),
            "category_rates": {k: round(v / n, 4) for k, v in counts.items()},
            "examples": {k: v[:4] for k, v in detail.items()}}
