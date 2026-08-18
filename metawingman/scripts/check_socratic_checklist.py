"""Check that Socratic checklist items for a stage have been answered.

Usage:
  python metawingman/scripts/check_socratic_checklist.py \
    --stage screening --answers answers.json [--strict]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

STAGE_TO_FILE = {
    "topic": "topic.json",
    "screening": "screening.json",
    "appraisal": "appraisal.json",
    "analysis": "analysis.json",
}


def _load_checklist(stage: str, skill_root: Path) -> dict[str, Any]:
    path = skill_root / "references" / "socratic-checklists" / STAGE_TO_FILE[stage]
    if not path.is_file():
        raise ValueError(f"no socratic checklist for stage {stage!r} at {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def check_answers(stage: str, answers: dict[str, str], skill_root: Path, *, strict: bool = False) -> dict[str, Any]:
    """Validate answers against the stage checklist; returns a report."""
    checklist = _load_checklist(stage, skill_root)
    items = checklist["items"]
    missing: list[str] = []
    optional_missing: list[str] = []
    for item in items:
        answer = (answers.get(item["id"]) or "").strip()
        if item["gate"] == "required" and not answer:
            missing.append(item["id"])
        elif item["gate"] == "optional" and not answer:
            optional_missing.append(item["id"])
    passed = not missing
    if strict and optional_missing:
        passed = False
    return {
        "schema_version": "1.0",
        "stage": stage,
        "checklist_title": checklist["title"],
        "answered": len(answers),
        "total_required": sum(1 for i in items if i["gate"] == "required"),
        "total_optional": sum(1 for i in items if i["gate"] == "optional"),
        "missing_required": missing,
        "missing_optional": optional_missing,
        "passed": passed,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", required=True, choices=sorted(STAGE_TO_FILE))
    parser.add_argument("--answers", type=Path, required=True)
    parser.add_argument("--skill-root", type=Path, default=Path("metawingman"))
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    try:
        answers = json.loads(args.answers.read_text(encoding="utf-8-sig"))
        if not isinstance(answers, dict):
            raise ValueError("answers must be a JSON object keyed by item id")
        report = check_answers(args.stage, answers, args.skill_root, strict=args.strict)
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0 if report["passed"] else 2
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"error": str(exc)}, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
