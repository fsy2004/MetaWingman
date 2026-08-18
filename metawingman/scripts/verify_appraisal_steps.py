"""Rule-based step-level verifier for appraisal dossiers (R6, rules-first).

Checks each step of a risk-of-bias/certainty appraisal chain against
deterministic rules (FirstResearch-style hard gates + uncertainty-aware
abstention). Later versions will add a trained verifier component; this
rule layer stays as the deterministic floor.

Usage:
  python metawingman/scripts/verify_appraisal_steps.py --dossier dossier.json
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from metawingman_core.schema_guard import SchemaValidationError, validate_document

KNOWN_TOOLS = {
    "rob2": "RCT",
    "rob 2": "RCT",
    "rob2 (2019)": "RCT",
    "robins-i": "non-randomized",
    "robins-i (2016)": "non-randomized",
    "quadas-2": "diagnostic-test-accuracy",
    "quadas-2 (2011)": "diagnostic-test-accuracy",
    "grade": "certainty",
}


def _step(step_id: str, check: str, passed: bool, detail: str) -> dict[str, Any]:
    return {"id": step_id, "check": check, "passed": passed, "confidence": 1.0, "detail": detail}


def verify_appraisal_steps(dossier: dict[str, Any]) -> dict[str, Any]:
    """Run deterministic step checks over an appraisal dossier."""
    validate_document(dossier, "appraisal_dossier")
    steps: list[dict[str, Any]] = []

    framework = dossier.get("framework", {})
    tool_key = (framework.get("name") or "").strip().lower()
    tool_known = tool_key in KNOWN_TOOLS
    steps.append(_step(
        "framework_known", "appraisal tool is a recognized instrument",
        tool_known, f"framework name {framework.get('name')!r}" + ("" if tool_known else " is not a recognized appraisal tool"),
    ))

    steps.append(_step(
        "framework_verified", "framework carries source_url and verified_at_utc",
        bool(framework.get("source_url") and framework.get("verified_at_utc")),
        "framework provenance fields present",
    ))

    domains = dossier.get("domains", [])
    steps.append(_step(
        "domains_present", "at least one domain appraised",
        len(domains) > 0,
        f"{len(domains)} domain(s)",
    ))

    unanchored: list[str] = []
    unanswered: list[str] = []
    unproposed: list[str] = []
    for domain in domains:
        label = domain.get("domain_id", "?")
        if not domain.get("proposal") or not domain.get("rationale"):
            unproposed.append(label)
        for question in domain.get("signaling_questions", []):
            if not question.get("answer"):
                unanswered.append(f"{label}:{question.get('question_id', '?')}")
            if not question.get("anchor_ids"):
                unanchored.append(f"{label}:{question.get('question_id', '?')}")

    steps.append(_step(
        "signaling_answers", "every signaling question answered",
        not unanswered,
        "missing answers: " + (", ".join(unanswered[:5]) or "none"),
    ))
    steps.append(_step(
        "signaling_anchors", "every signaling answer anchored to source evidence",
        not unanchored,
        "unanchored: " + (", ".join(unanchored[:5]) or "none"),
    ))
    steps.append(_step(
        "domain_proposals", "every domain has a proposal and rationale",
        not unproposed,
        "missing: " + (", ".join(unproposed[:5]) or "none"),
    ))

    overall = dossier.get("overall_proposal") or ""
    steps.append(_step(
        "overall_proposal", "overall judgment proposed",
        bool(overall),
        f"overall proposal {'present' if overall else 'missing'}",
    ))

    steps.append(_step(
        "opposition_recorded", "opposition (counter-case) recorded",
        bool(dossier.get("opposition")),
        "opposition field present",
    ))

    steps.append(_step(
        "missing_information", "missing information enumerated",
        isinstance(dossier.get("missing_information"), list),
        "missing_information list present",
    ))

    final = dossier.get("final_judgment")
    has_final = bool(final and str(final).strip())
    steps.append(_step(
        "final_judgment", "final judgment recorded",
        has_final,
        "final judgment " + ("recorded" if has_final else "missing"),
    ))

    signed = (dossier.get("human_signature") or {}).get("status") == "approved"
    steps.append(_step(
        "human_signature", "human review signature present",
        signed,
        "human signature " + ("present" if signed else "pending — human window required"),
    ))

    passed = [step for step in steps if step["passed"]]
    confidence = round(len(passed) / len(steps), 4) if steps else 0.0
    abstain_required = any(
        not step["passed"] for step in steps
        if step["id"] in {"signaling_answers", "signaling_anchors", "domain_proposals", "overall_proposal", "final_judgment"}
    )
    return {
        "schema_version": "1.0",
        "report_id": f"asv:{dossier.get('dossier_id', 'unknown')}",
        "dossier_id": dossier.get("dossier_id", ""),
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "steps": steps,
        "summary": {
            "steps_total": len(steps),
            "steps_passed": len(passed),
            "confidence": confidence,
            "abstain_required": abstain_required,
            "human_window_required": not signed,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dossier", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    try:
        dossier = json.loads(args.dossier.read_text(encoding="utf-8"))
        report = verify_appraisal_steps(dossier)
        validate_document(report, "appraisal_step_verification_report")
        text = json.dumps(report, indent=2, ensure_ascii=False)
        if args.out:
            args.out.write_text(text + "\n", encoding="utf-8")
        print(text)
        return 0 if not report["summary"]["abstain_required"] else 2
    except (OSError, ValueError, json.JSONDecodeError, SchemaValidationError) as exc:
        print(json.dumps({"error": str(exc)}, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
