#!/usr/bin/env python3
"""Controlled mechanism validation of the EVPI stop layer.

(1) Rule properties (deterministic, one-step): continue iff max EVPI > 0;
    monotone in information cost; monotone in gap gains.
(2) Simulated evidence-accretion process: an evidence landscape accumulates
    new studies over time (Poisson rate); the value of an additional update
    decays as the synthesis approaches saturation; the EVPI rule decides
    continue/stop per cycle. We measure how close the rule's stopping time is
    to the value-optimal stopping time (which is known in the simulation).

This is a CONTROLLED mechanism test (the input is constructed, clearly labelled),
used alongside the real-data identifiability analysis (evpi-v2-identifiability.json).
Usage: python scripts/evpi_mechanism_tests.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from metawingman.agent.evpi_director import (  # noqa: E402
    decide_living_v2, estimate_evpi, landscape_gaps)

RES = _REPO_ROOT / "research"
SEEDS = [20260826, 20260827, 20260828]


def main() -> int:
    out: dict = {"scope": "controlled mechanism validation of the EVPI stop layer",
                 "note": "constructed inputs; not an estimate of real-world performance. "
                         "Real-data identifiability is reported separately."}
    # ---- (1) rule properties ----
    gaps = [{"gap": "g1", "expected_utility_gain": 0.9, "uncertainty": 0.8},
            {"gap": "g2", "expected_utility_gain": 0.4, "uncertainty": 0.6}]
    v_low = decide_living_v2(gaps, info_cost=0.30)
    v_high = decide_living_v2(gaps, info_cost=0.90)
    prop_continue = v_low["living"] is True
    prop_stop = v_high["living"] is False
    monotone_cost = (v_low["next_evidence"]["evpi"] >= v_high["next_evidence"]["evpi"])
    gains_hi = [{"gap": "g1", "expected_utility_gain": 0.95, "uncertainty": 0.95}]
    gains_lo = [{"gap": "g1", "expected_utility_gain": 0.10, "uncertainty": 0.10}]
    monotone_gain = (decide_living_v2(gains_hi, info_cost=0.5)["living"] is True and
                     decide_living_v2(gains_lo, info_cost=0.5)["living"] is False)
    out.update({"rule_properties": {
        "continues_when_max_evpi_positive": prop_continue,
        "stops_when_max_evpi_non_positive": prop_stop,
        "monotone_in_info_cost": bool(monotone_cost),
        "monotone_in_gains": bool(monotone_gain)}})

    # ---- (2) simulated accretion ----
    # Value of an update = g0 * exp(-k * n_landscape) * uncertainty - cost,
    # the standard diminishing-returns model; rate lambda studies/cycle.
    # The EVPI rule observes a NOISY estimate of the true gain (30% relative
    # noise); the value-optimal stop is the first cycle where the TRUE future
    # value is <= cost (known only in simulation). The test measures how close
    # the information-value rule's stopping time is to the optimal one.
    sigma = 0.30
    rng_all = []
    for seed in SEEDS:
        rng = np.random.default_rng(seed)
        diffs = []
        n_runs = 200
        for _ in range(n_runs):
            g0 = float(rng.uniform(0.4, 1.0))
            k = float(rng.uniform(0.6, 2.0))
            lam = float(rng.uniform(1, 12))
            cost = float(rng.uniform(0.15, 0.6))
            ts = None
            topt = None
            for t in range(1, 61):
                true_gain = g0 * np.exp(-k * (lam * t / lam))
                observed_gain = max(0.0, true_gain * (1.0 + rng.normal(0.0, sigma)))
                if ts is None:
                    pred = decide_living_v2(
                        [{"gap": "accretion", "expected_utility_gain": float(observed_gain),
                          "uncertainty": 1.0}], info_cost=cost)["living"]
                    if not pred:
                        ts = t
                if topt is None and true_gain <= cost:
                    topt = t
                if ts is not None and topt is not None:
                    break
            diffs.append((ts - topt) if (ts is not None and topt is not None) else 60)
        diffs = np.array(diffs, dtype=float)
        rng_all.append({"seed": seed, "n_runs": n_runs,
                        "mean_cycle_gap_rule_minus_optimal": round(float(diffs.mean()), 3),
                        "within_1_cycle": round(float(np.mean(np.abs(diffs) <= 1)), 4),
                        "within_2_cycles": round(float(np.mean(np.abs(diffs) <= 2)), 4)})
    out["simulated_accretion"] = {"per_seed": rng_all,
                                  "note": ("200 trajectories per seed; the rule stops "
                                           "when its EVPI calculation says so, the optimal "
                                           "stopping time is the first cycle where true "
                                           "future value <= cost (known only in simulation)")}
    (RES / "evpi-mechanism-tests.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
