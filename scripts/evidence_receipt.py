#!/usr/bin/env python3
"""Reproducibility: aggregate the evidence-chain result files into a single
versioned index + sha256 receipt (seed/hash/metric-definition/evidence-file).
This is the reproducibility evidence a top-venue paper needs."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RES = REPO / "research"

# result files -> human metric summary
FILES = {
    "cross-glm.json": "cross-model delta (GLM-4.5-Air bare vs decision-object); see cross-model-design-task.json for the like-for-like design-task delta",
    "cross-ds.json": "cross-model delta (DeepSeek V4 flash bare vs decision-object); see cross-model-design-task.json for the like-for-like design-task delta",
    "cross-model-design-task.json": "cross-model design-task comparison (like-for-like) with bootstrap CIs",
    "cross-ds-large.json": "cross-model delta (DeepSeek V4 flash) on the 170-review diverse corpus (design task)",
    "cross-ds-multitask-holdout.json": "bare-LLM MULTI-TASK arm (design+pooling+stop) on OOD holdout-40",
    "cross-ds-multitask-large.json": "bare-LLM MULTI-TASK arm (design+pooling+stop) on the 170-review diverse corpus",
    "cross-ds-multitask-holdout-run2.json": "bare-LLM MULTI-TASK arm re-run on holdout-40 (run-to-run variance check)",
    "ablation-holdout.json": "ablation mechanism contribution (drop guard/evpi/estimand-first)",
    "method-trace-fidelity-real.json": "dev(8-strata) fidelity baseline",
    "method-trace-fidelity-holdout.json": "OOD holdout fidelity (design_selection)",
    "method-trace-fidelity-large.json": "diverse-corpus fidelity (covers more profiles)",
    "method-trace-fidelity-lora-honest.json": "honest strict evaluation of the Qwen2.5-1.5B LoRA (210 samples) on OOD holdout; no fallback to gold",
    "method-trace-fidelity-lora-honest-v2.json": "honest strict evaluation of the Qwen2.5-1.5B LoRA on methods-text-extracted (v2) holdout gold; no fallback",
    "method-trace-large-signal-v2.jsonl": "methods-text gold extraction (v2) — diverse corpus structure signals (outcome-stripped)",
    "method-trace-holdout-signal-v2.jsonl": "methods-text gold extraction (v2) — holdout structure signals",
    "method-trace-gold-signal-v2.jsonl": "methods-text gold extraction (v2) — dev structure signals",
    "method-trace-living-signal-v2.jsonl": "methods-text gold extraction (v2) — 35-review living/update benchmark (OOD)",
    "living-review-catalog.json": "living-review benchmark catalog (35 records, top journals, zero overlap with other corpora)",
    "fidelity-v2-dev.json": "decision-object v2 on methods-text gold (dev)",
    "fidelity-v2-holdout.json": "decision-object v2 on methods-text gold (OOD holdout)",
    "fidelity-v2-large.json": "decision-object v2 on methods-text gold (diverse corpus)",
    "fidelity-v2-living.json": "decision-object v2 on methods-text gold (living benchmark)",
    "guard-v2-calibration.json": "v2 dimension-guard calibration (empirical risk control + Clopper-Pearson certificate)",
    "guard-v2-ood-risk.json": "OOD risk audit of the calibrated guard (guarantee check per corpus)",
    "ablation-v2.json": "v2 ablation + progressive baselines (paired bootstrap CIs)",
    "evpi-v2-calibration.json": "EVPI split-conformal calibration search (result: degenerate → default conservative config; documented)",
    "evpi-v2-identifiability.json": "stop-layer identifiability: AUC of structure-derived EVPI score for living status",
    "evpi-v2-oos-stop.json": "EVPI stop-layer OOD evaluation on the held-out half",
    "evpi-mechanism-tests.json": "controlled mechanism validation of the EVPI stop rule (properties + simulated accretion)",
    "cross-ds-multitask-holdout-v2.json": "bare-LLM MULTI-TASK arm on v2 holdout gold",
    "cross-ds-multitask-large-v2.json": "bare-LLM MULTI-TASK arm on v2 diverse gold",
    "cross-ds-multitask-holdout-v2-run2.json": "bare-LLM MULTI-TASK arm re-run (v2; run-to-run variance check)",
    "cross-ds-v2.json": "bare-LLM design-only arm on v2 holdout gold",
    "cross-ds-large-v2.json": "bare-LLM design-only arm on v2 diverse gold",
    "bootstrap-v2-ci.json": "bootstrap CIs (5 seeds) for v2 corpora and rule-vs-bare multi-task",
    "multitask-compare-v2.json": "v2 like-for-like rule vs bare multi-task comparison (paired)",
    "reconstruction-agrdt-pooled-v2.json": "analysis-stage reconstruction: pooled estimates vs published (+0.70/+0.20 pp, tolerance 2.0 pp)",
    "blind-reconstruction-agrdt.json": "blind full-workflow reconstruction: agent (question-only) vs published review (design/pooling/model/criteria 8/8)",
    "method-layer3-summary.json": "method layer 3.0 (scrutiny: oppose/adjudicate + precedent retrieval) evaluation — verification coverage + honest zeros",
    "method-layer3-checker-audit.json": "scrutiny checker audit: flags the historical design-pooling coupling (33/196, 33/33 fix matches gold, 0 false positives)",
    "bare-llm-holdout.json": "bare-LLM no-skill arm (v1 gold; historical)",
    "bootstrap-ci.json": "bootstrap CIs + multi-seed stability for v1 results (historical)",
    "multitask-agreement.json": "design/pooling/stopping as independent tasks (+3-task mean) per corpus (v1 gold; historical)",
    "multitask-compare.json": "like-for-like rule vs bare-LLM multi-task comparison (v1 gold; historical)",
    "progressive-baseline.json": "progressive baselines bare LLM -> design rule -> +guard -> full (v1 gold; historical)",
}

FIXED_SEED = 20260826


def sha(p: Path) -> str:
    if not p.is_file():
        return "MISSING"
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> int:
    index = {"schema_version": "1.0", "generated_at_utc": datetime.now(timezone.utc).isoformat(),
             "seed": FIXED_SEED, "metric": "fidelity (agreement with published_expert_reference, "
                                             "OOD, strict parse, no fallback)", "results": {}}
    for name, desc in FILES.items():
        p = RES / name
        entry = {"description": desc, "path": name, "sha256": sha(p)}
        if p.is_file():
            try:
                entry["payload"] = json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                entry["payload"] = None
        index["results"][name] = entry
    index["receipt_sha256"] = sha256_json(index)
    out = RES / "evidence-index.json"
    out.write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"seed": FIXED_SEED, "files": len(index["results"]),
                      "receipt_sha256": index["receipt_sha256"], "out": out.name}, indent=2))
    return 0


def sha256_json(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
