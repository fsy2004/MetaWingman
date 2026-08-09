#!/usr/bin/env python3
"""Validate scientific gate evidence, hashes, counts, and secret hygiene."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from pathlib import Path


REQUIRED = {
    0: ["00_admin/project.json", "00_admin/decision_log.md"],
    1: ["01_protocol/protocol.md", "01_protocol/amendments.csv"],
    2: ["02_search/search_log.csv"],
    3: ["03_screening/screening_decisions.csv", "03_screening/full_text_exclusions.csv"],
    4: ["04_extraction/report_study_map.csv", "04_extraction/results.csv"],
    5: ["05_appraisal/risk_of_bias.csv"],
    6: ["06_analysis/freeze_manifest.json"],
    7: ["05_appraisal/certainty.csv"],
    8: ["07_reporting/manuscript.md", "07_reporting/claim_evidence_ledger.csv", "08_review/reviewer_findings.csv"],
    9: ["09_update/update_log.csv"],
}
SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|token|password|secret)\s*[:=]\s*['\"]?[A-Za-z0-9_\-]{12,}"),
    re.compile(r"gh[opusr]_[A-Za-z0-9]{20,}"),
]


def data_rows(path: Path) -> int:
    if path.suffix.lower() != ".csv" or not path.exists(): return 0
    with path.open(encoding="utf-8-sig", newline="") as handle: return sum(1 for _ in csv.DictReader(handle))


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("project", type=Path); args = parser.parse_args(); root = args.project.resolve()
    issues, warnings = [], []
    gate_file = root / "00_admin/gate_status.json"
    try: gates = json.loads(gate_file.read_text(encoding="utf-8"))
    except Exception as exc: gates = {}; issues.append(f"Cannot read gate_status.json: {exc}")
    for stage, paths in REQUIRED.items():
        status = gates.get(str(stage), {}).get("status", "not_started")
        for rel in paths:
            path = root / rel
            if status == "complete" and (not path.exists() or path.stat().st_size == 0): issues.append(f"Stage {stage} marked complete but missing/empty: {rel}")
        if status == "complete" and not gates.get(str(stage), {}).get("verified_by"): issues.append(f"Stage {stage} complete without verified_by")
    freeze = root / "06_analysis/freeze_manifest.json"
    if freeze.exists():
        try:
            manifest = json.loads(freeze.read_text(encoding="utf-8"))
            if manifest.get("status") == "frozen":
                for item in manifest.get("files", []):
                    path = root / item["path"]
                    if not path.exists(): issues.append(f"Frozen file missing: {item['path']}"); continue
                    actual = hashlib.sha256(path.read_bytes()).hexdigest()
                    if actual != item.get("sha256"): issues.append(f"Frozen hash mismatch: {item['path']}")
        except Exception as exc: issues.append(f"Invalid freeze manifest: {exc}")
    for path in root.rglob("*"):
        if not path.is_file() or path.stat().st_size > 5_000_000 or any(part == ".git" for part in path.parts): continue
        try: content = path.read_text(encoding="utf-8", errors="ignore")
        except Exception: continue
        if path.name == ".env": issues.append(".env file exists inside project; keep secrets outside versioned project")
        for pattern in SECRET_PATTERNS:
            if pattern.search(content): issues.append(f"Possible embedded secret: {path.relative_to(root)}"); break
    screening = data_rows(root / "03_screening/screening_decisions.csv")
    results = data_rows(root / "04_extraction/results.csv")
    rob = data_rows(root / "05_appraisal/risk_of_bias.csv")
    if gates.get("5", {}).get("status") == "complete" and results and not rob: issues.append("Appraisal complete but no risk-of-bias rows")
    if gates.get("6", {}).get("status") == "complete" and not results: issues.append("Synthesis complete but extraction results are empty")
    if screening == 0: warnings.append("No screening decisions yet")
    report = {"project": str(root), "issues": issues, "warnings": warnings, "row_counts": {"screening": screening, "results": results, "risk_of_bias": rob}, "valid": not issues}
    print(json.dumps(report, indent=2)); return 1 if issues else 0


if __name__ == "__main__": raise SystemExit(main())
