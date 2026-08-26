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
    "cross-glm.json": "cross-model delta (GLM-4.5-Air bare vs decision-object)",
    "cross-ds.json": "cross-model delta (DeepSeek V4 flash bare vs decision-object)",
    "ablation-holdout.json": "ablation mechanism contribution (drop guard/evpi/estimand-first)",
    "method-trace-fidelity-real.json": "dev(8-strata) fidelity baseline",
    "method-trace-fidelity-holdout.json": "OOD holdout fidelity (design_selection)",
    "method-trace-fidelity-large.json": "diverse-corpus fidelity (covers more profiles)",
    "bare-llm-holdout.json": "bare-LLM no-skill arm",
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
