#!/usr/bin/env python3
"""Step compliance: protocol -> execution step consistency (AgentIF-style dual
granularity, deterministic verification).

依据(出处): _deliverables/deep-study/notes/agentif.md (CSR = per-constraint correct
             rate, partial credit; ISR = all-or-nothing; chunked constraint
             extraction + cross-chunk checks; conditional constraints evaluated
             first), 论文: arXiv:2505.16944.
Mapping to us: the "protocol" is the compiled review-setup (question certificate,
design decision, pooling decision, EVPI/stop), the "execution" is the per-stage
intermediate objects; compliance = each stage object satisfies its preconditions
(checkable), reported at two granularities: CSR-like per-stage rate and ISR-like
full-flow rate. Chunking = stage-level checks + cross-stage consistency
(certificate -> design -> guard -> stop).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class StageCheck:
    stage: str
    ok: bool
    precondition: str
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"stage": self.stage, "ok": self.ok,
                "precondition": self.precondition, "detail": self.detail}


def check_flow(certificate: dict[str, Any], design: dict[str, Any],
               guard: dict[str, Any], stop: dict[str, Any],
               protocol_criteria: list[dict] | None = None) -> dict[str, Any]:
    """Deterministic stage checks (preconditions are checkable assertions)."""
    checks: list[StageCheck] = []

    def add(stage, ok, precondition, detail=""):
        checks.append(StageCheck(stage, bool(ok), precondition, detail))

    # 1. certificate completeness (hard gate)
    cert_needed = ("primitives", "hypothesis", "falsifier", "mechanism_model",
                   "minimal_decisive_test", "failure_update")
    add("question_certificate",
        all(str(certificate.get(k) or "").strip() for k in cert_needed),
        "certificate required fields non-empty",
        "missing: " + ", ".join(k for k in cert_needed if not str(certificate.get(k) or "").strip()) or "none")

    # 2. design consistency (cross-chunk: profile -> estimand -> route)
    profile = (design.get("profile") or "")
    add("design_decision",
        bool(profile) and bool(design.get("identification_assumption")) and bool(design.get("synthesis_route")),
        "design carries profile + identification + synthesis route")

    # 3. pooling consistency with design (cross-stage)
    pooled = bool(guard.get("passes"))
    narrative_design = profile == "structured_no_pooling"
    add("pooling_decision",
        (not narrative_design) or (not pooled),
        "narrative-design reviews must not be approved for pooling")

    # 4. guard certificate present
    add("guard_certificate",
        "guarantee" in guard and "alpha" in guard,
        "guard carries an (alpha) certificate")

    # 5. stop consistency (EVPI object well-formed)
    add("stop_decision",
        isinstance(stop, dict) and ("living" in stop) and ("max_evpi" in stop or "stop_rule" in stop),
        "stop object carries living + value/cost objects")

    # 6. protocol criteria compiled (optional stage)
    if protocol_criteria is not None:
        add("protocol_criteria",
            len(protocol_criteria) >= 4 and all(isinstance(c, dict) and c.get("criterion")
                                                for c in protocol_criteria),
            ">=4 typed criteria present")

    ok_stages = [c for c in checks if c.ok]
    return {
        "n_stages": len(checks),
        "per_stage_rate": round(len(ok_stages) / len(checks), 4),   # CSR-like
        "full_flow_rate": 1.0 if len(ok_stages) == len(checks) else 0.0,  # ISR-like
        "checks": [c.to_dict() for c in checks],
    }
