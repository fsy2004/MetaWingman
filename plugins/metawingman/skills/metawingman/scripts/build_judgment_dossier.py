#!/usr/bin/env python3
"""Build a non-final appraisal or missing-evidence dossier from typed JSON."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from metawingman_core.judgment_workbench import (
    JudgmentWorkbenchError,
    build_appraisal_dossier,
    build_missing_evidence_matrix,
    load_appraisal_adapter,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--kind", choices=("appraisal", "missing-evidence"), required=True)
    parser.add_argument("--adapter", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    try:
        candidate = json.loads(args.candidate.read_text(encoding="utf-8"))
        if args.kind == "appraisal":
            if args.adapter is None:
                raise JudgmentWorkbenchError("--adapter is required for appraisal dossiers")
            output = build_appraisal_dossier(load_appraisal_adapter(args.adapter), candidate)
        else:
            output = build_missing_evidence_matrix(candidate)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    except (OSError, json.JSONDecodeError, JudgmentWorkbenchError) as exc:
        print(json.dumps({"built": False, "error": str(exc)}, indent=2))
        return 1
    print(json.dumps({"built": True, "status": output["status"], "out": str(args.out)}, indent=2))
    return 0 if output["status"] == "ready_for_adjudication" else 2


if __name__ == "__main__":
    raise SystemExit(main())
