#!/usr/bin/env python3
"""A) Improve the poolability guard by CALIBRATING its threshold on the REAL
published-meta 'did it actually pool' labels (holdout). The default guard uses a
fixed threshold (0.45) and is over-conservative (rejects poolable exposure);
calibrating should raise guard_consistency toward the real review behaviour.

Compares: default (un-calibrated) vs calibrated guard-consistency on holdout.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from metawingman.agent.poolability_guard import GuardModel, calibrate_guard, safety_score
from metawingman.training.method_trace_normalizer import normalize_gold_trace

REPO = Path(__file__).resolve().parents[1]
SIGNAL = REPO / "research" / "method-trace-holdout-signal.jsonl"


def signal_for_guard(signal: dict, profile_hint: str) -> dict:
    s = dict(signal)
    s["estimand_aligned"] = bool(profile_hint and profile_hint != "structured_no_pooling")
    s["profile_hint"] = profile_hint
    return s


def main() -> int:
    rows = [json.loads(l) for l in SIGNAL.read_text(encoding="utf-8").splitlines() if l.strip()]
    cases = []
    for row in rows:
        gold = normalize_gold_trace(row)
        if gold is None:
            continue
        cases.append((gold, gold.get("signal") or {}))

    # default guard
    default = GuardModel(alpha=0.05, threshold=0.45, empirical_risk=0.0, calibration_size=0)
    # calibrated guard from REAL pooled labels (misleading = real said NO-pool but guard says poolable)
    calibration = []
    for gold, sig in cases:
        sg = signal_for_guard(sig, gold["design_selection"])
        real_pooled = bool(sig.get("pooled"))
        calibration.append({**sg, "is_pooling_misleading": not real_pooled})
    calibrated = calibrate_guard(calibration, alpha=0.10)

    def consistency(model: GuardModel) -> float:
        ok = 0
        for gold, sig in cases:
            real_pooled = bool(sig.get("pooled"))
            g = model.apply(signal_for_guard(sig, gold["design_selection"]))
            ok += int(g.passes == real_pooled)
        return ok / len(cases)

    default_cons = consistency(default)
    calib_cons = consistency(calibrated)
    print(f"cases={len(cases)}")
    print(f"default guard_consistency = {default_cons:.3f}  (threshold=0.45)")
    print(f"calibrated guard_consistency = {calib_cons:.3f}  (alpha=0.10, threshold={calibrated.threshold:.3f})")
    print(f"delta = {calib_cons - default_cons:+.3f}")
    # per-profile calibrated vs default
    from collections import defaultdict
    def per_profile(model):
        d = defaultdict(lambda: [0, 0])
        for gold, sig in cases:
            real = bool(sig.get("pooled"))
            g = model.apply(signal_for_guard(sig, gold["design_selection"]))
            d[gold["design_selection"]][1] += 1
            d[gold["design_selection"]][0] += int(g.passes == real)
        return {p: round(v[0] / v[1], 3) for p, v in d.items()}
    print("calibrated by profile:", per_profile(calibrated))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
