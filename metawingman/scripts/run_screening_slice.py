"""Deterministic screening-slice engine (reconstruction runner v2, stage 1).

Implements the frozen screening-stage contract of
docs/architecture/reconstruction-runner-v2-preregistration-2026-08-18.md:

- Pure functions only (no LLM, no randomness): identical inputs -> identical
  outputs, asserted across repetitions.
- Include iff at least one include rule matches AND no exclude rule matches;
  exclude otherwise with the first matching reason; missing title AND
  abstract -> abstain (never auto-exclude).
- Every decision records its matched rule ids; a SHA-256 receipt carries
  input/rules/output hashes and decision counts.

Usage:
  python metawingman/scripts/run_screening_slice.py \
    --records fixtures/screening-records.jsonl \
    --rules fixtures/screening-criterion-anchors.json \
    --out-dir <dir>
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from pathlib import Path


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def matches(record: dict, rule: dict) -> bool:
    """Deterministic rule match over title+abstract text.

    rule = {"terms": ["..."], "regex": ["..."], "mode": "any"|"all"}
    Terms are case-insensitive substrings; regex entries are Python re
    patterns (case-insensitive). mode=any (default): any term/regex hit.
    mode=all: every listed term must hit AND at least one regex (if given)
    must hit.
    """
    text = " ".join(
        part for key in ("title", "abstract") if (part := (record.get(key) or ""))
    ).lower()
    terms = [t.lower() for t in rule.get("terms", [])]
    patterns = rule.get("regex", [])
    term_hits = [t in text for t in terms]
    regex_hits = [re.search(p, text, flags=re.IGNORECASE) is not None for p in patterns]
    hits = term_hits + regex_hits
    if rule.get("mode", "any") == "any":
        return any(hits)
    # mode=all: all terms hit; regex entries, when present, must all hit too
    return all(term_hits) and (not regex_hits or all(regex_hits))


def screen(records: list[dict], rules: dict) -> dict:
    include_rules = rules.get("include_rules", [])
    exclude_rules = rules.get("exclude_rules", [])
    by_id = {r["id"]: r for r in include_rules + exclude_rules}
    decisions = []
    counts = {"include": 0, "exclude": 0, "abstain": 0}
    for record in records:
        rec_id = record["id"]
        title = (record.get("title") or "").strip()
        abstract = (record.get("abstract") or "").strip()
        if not title and not abstract:
            decision = {
                "record_id": rec_id,
                "decision": "abstain",
                "reasons": ["missing_title_and_abstract"],
                "matched_include": [],
                "matched_exclude": [],
            }
            counts["abstain"] += 1
        else:
            # A rule only counts as matched when its `requires` rules also match
            # (cross-rule AND semantics, e.g. index test AND accuracy AND reference).
            def rule_matches(rule: dict) -> bool:
                return matches(record, rule) and all(
                    rid in by_id and matches(record, by_id[rid]) for rid in rule.get("requires", [])
                )
            matched_include = [r["id"] for r in include_rules if rule_matches(r)]
            matched_exclude = [r["id"] for r in exclude_rules if rule_matches(r)]
            if matched_exclude:
                decision = {
                    "record_id": rec_id, "decision": "exclude",
                    "reasons": [f"exclude_rule:{rid}" for rid in matched_exclude],
                    "matched_include": matched_include, "matched_exclude": matched_exclude,
                }
                counts["exclude"] += 1
            elif matched_include:
                decision = {
                    "record_id": rec_id, "decision": "include",
                    "reasons": [f"include_rule:{rid}" for rid in matched_include],
                    "matched_include": matched_include, "matched_exclude": [],
                }
                counts["include"] += 1
            else:
                decision = {
                    "record_id": rec_id, "decision": "exclude",
                    "reasons": ["no_include_rule_matched"],
                    "matched_include": [], "matched_exclude": [],
                }
                counts["exclude"] += 1
        decisions.append(decision)
    return {"counts": counts, "decisions": decisions}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--records", type=Path, required=True)
    parser.add_argument("--rules", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        started = time.monotonic()
        records = load_jsonl(args.records)
        rules = json.loads(args.rules.read_text(encoding="utf-8-sig"))
        if not isinstance(rules, dict) or "schema_version" not in rules:
            raise ValueError("rules file must be the criterion-anchor JSON (schema_version required)")
        args.out_dir.mkdir(parents=True, exist_ok=False)
        result = screen(records, rules)
        decisions_path = args.out_dir / "decisions.jsonl"
        decisions_path.write_text(
            "\n".join(json.dumps(d, ensure_ascii=False) for d in result["decisions"]) + "\n",
            encoding="utf-8",
        )
        receipt = {
            "schema_version": "1.0",
            "stage": "screening",
            "execution_state": "completed",
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "records_sha256": sha256_file(args.records),
            "rules_sha256": sha256_file(args.rules),
            "decisions_sha256": sha256_file(decisions_path),
            "counts": result["counts"],
            "determinism_note": "pure rule engine; identical inputs yield identical outputs",
        }
        (args.out_dir / "execution-receipt.json").write_text(
            json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        print(json.dumps(receipt, indent=2, ensure_ascii=False))
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"execution_state": "failed", "error": str(exc)}, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
