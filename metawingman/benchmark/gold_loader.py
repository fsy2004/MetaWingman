#!/usr/bin/env python3
"""Load a frozen gold case set for the design-selection benchmark.

Gold cases carry the clinical/methodological question shape and the
evidence-structure signals (the "landscape") together with the reference review
profile the evidence actually warranted. This is deterministic and does not
score topics by prestige.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class GoldCase:
    """One gold design-selection case."""

    case_id: str
    question: dict[str, Any]
    landscape: dict[str, Any]
    gold_profile: str
    gold_living: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "question": self.question,
            "landscape": self.landscape,
            "gold_profile": self.gold_profile,
            "gold_living": self.gold_living,
        }


def load_gold(path: str | Path) -> list[GoldCase]:
    """Load a gold fixture file into GoldCase records."""
    p = Path(path)
    data = json.loads(p.read_text(encoding="utf-8"))
    cases = data.get("cases") or []
    out: list[GoldCase] = []
    for case in cases:
        if not case.get("case_id") or not case.get("gold_profile"):
            raise ValueError(f"gold case missing case_id or gold_profile: {case}")
        out.append(GoldCase(
            case_id=case["case_id"],
            question=case.get("question") or {},
            landscape=case.get("landscape") or {},
            gold_profile=case["gold_profile"],
            gold_living=bool(case.get("gold_living", False)),
        ))
    return out


def gold_to_eval_rows(gold: list[GoldCase]) -> list[dict[str, Any]]:
    """Convert gold cases to the (profile, living) rows the evaluator expects."""
    return [
        {"case_id": g.case_id, "profile": g.gold_profile, "living": g.gold_living}
        for g in gold
    ]
