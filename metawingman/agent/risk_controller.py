#!/usr/bin/env python3
"""Unified risk controller: accept / audit / abstain (three actions) with the
finite-sample certificate.

依据(出处): _deliverables/deep-study/notes/conformal-abstention.md §2 (CAP: dual
             thresholds q_predict / q_abstain; 3 actions; coverage >= 1 - alpha),
             官方实现: https://github.com/sinatayebati/vlm-uncertainty (ACML 2025);
             论文: arXiv:2502.06884 §3.
Methodological difference (stated, not hidden): CAP re-tunes thresholds with RL,
which its own analysis warns distorts conformal guarantees; our thresholds are
set on a frozen calibration set (split-conformal style) and we keep the
Clopper-Pearson finite-sample certificate on top.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from metawingman.agent.poolability_guard import PoolabilityGuard


@dataclass(frozen=True)
class RiskVerdict:
    action: str            # "accept" | "audit" | "abstain"
    risk: float
    threshold_accept: float
    threshold_abstain: float
    certificate: dict[str, Any]
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {"action": self.action, "risk": self.risk,
                "threshold_accept": self.threshold_accept,
                "threshold_abstain": self.threshold_abstain,
                "certificate": self.certificate, "reason": self.reason}


class RiskController:
    """Dual-threshold risk controller (CAP-style) around a certified guard.

    accept: risk <= tau_accept (certified by the guard's CP bound);
    audit:  tau_accept < risk <= tau_abstain  -> diagnostic only, no verdict;
    abstain: risk > tau_abstain  -> refuse to decide; request more evidence.
    """

    def __init__(self, tau_accept: float, tau_abstain: float | None = None,
                 abstain_budget: float = 0.10):
        self.tau_accept = float(tau_accept)
        self.tau_abstain = float(tau_abstain) if tau_abstain is not None else min(
            1.0, tau_accept + 0.15 * (1.0 - tau_accept))
        self.abstain_budget = abstain_budget

    def apply(self, guard: PoolabilityGuard | dict[str, Any]) -> RiskVerdict:
        if isinstance(guard, dict):
            risk = float(guard.get("safety_score") or 0.0)
            cert = {"alpha": guard.get("alpha"), "delta": None,
                    "guarantee": guard.get("guarantee", ""),
                    "risk_violation_estimate": guard.get("risk_violation_estimate"),
                    "passes": bool(guard.get("passes", False))}
        else:
            risk = float(getattr(guard, "safety_score", 0.0) or 0.0)
            cert = {"alpha": getattr(guard, "alpha", None), "delta": None,
                    "guarantee": getattr(guard, "guarantee", ""),
                    "risk_violation_estimate": getattr(guard, "risk_violation_estimate", None),
                    "passes": bool(getattr(guard, "passes", False))}
        if risk <= self.tau_accept:
            return RiskVerdict("accept", risk, self.tau_accept, self.tau_abstain, cert,
                               "within calibrated acceptance threshold")
        if risk <= self.tau_abstain:
            return RiskVerdict("audit", risk, self.tau_accept, self.tau_abstain, cert,
                               "between accept and abstain thresholds: emit diagnostics, no verdict")
        return RiskVerdict("abstain", risk, self.tau_accept, self.tau_abstain, cert,
                           "above abstain threshold: refuse to decide; request more evidence")
