"""Bulk rubric rating of appraisal passages via the hosted provider.

Same rubric as the subagent rating procedure, scripted: each passage gets a
six-label domain judgement with JSON output; resume-capable; per-shard run
record + receipt. Ratings are judgement labels (rubric-grounded), used to
build the rubric-supervised training set.

Usage:
  python metawingman/scripts/run_rubric_rating.py \
    --passages <slice.jsonl> \
    --provider-config metawingman/references/deepseek-provider-config.json \
    --out-dir <dir> [--limit N]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from metawingman_core.deepseek_provider import DeepSeekProvider  # noqa: E402
from metawingman_core.model_provider import ProviderRequestError  # noqa: E402

RUBRIC = (
    "Label the SINGLE risk-of-bias domain this passage most directly concerns. "
    "Choose exactly one of: selection_bias, performance_bias, detection_bias, "
    "attrition_bias, reporting_bias, other. Definitions (Cochrane RoB 2 / ROBINS-I): "
    "selection_bias = randomization sequence, allocation concealment, baseline comparability, "
    "participant selection; performance_bias = deviations from intended interventions, "
    "blinding of participants/personnel; detection_bias = blinding of outcome assessors, "
    "outcome measurement methods/timing; attrition_bias = loss to follow-up, dropout, "
    "incomplete/missing outcome data; reporting_bias = selective reporting, protocol comparison, "
    "publication bias (Egger/Begg/funnel/trim-fill). "
    "Use other for: tool/process introductions (RoB2/ROBINS-I/NOS/PEDro/CASP/NIH etc.), "
    "dual independent assessment procedures, pure statistical methods, GRADE certainty, "
    "funding/conflict declarations, multi-domain overall overviews, or any passage not "
    "focused on a single domain. Output ONLY JSON: "
    '{"label": "<one of the six labels>"}.'
)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rate_one(record: dict, provider) -> str:
    text = record["text"][:3000]
    for attempt in range(2):
        try:
            result = provider.chat(
                messages=[
                    {"role": "system", "content": RUBRIC},
                    {"role": "user", "content": f"Passage:\n{text}"},
                ],
                max_tokens=64,
                json_output=True,
            )
        except ProviderRequestError as exc:
            if attempt == 0:
                time.sleep(1)
                continue
            return "other"  # provider failure -> conservative other (recorded)
        content = (result.content or "").strip()
        try:
            start = content.index("{")
            end = content.rindex("}") + 1
            payload = json.loads(content[start:end])
            label = payload.get("label")
            if label in ("selection_bias", "performance_bias", "detection_bias", "attrition_bias", "reporting_bias", "other"):
                return label
        except (ValueError, json.JSONDecodeError):
            pass
        if attempt == 0:
            continue
    return "other"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--passages", type=Path, required=True)
    parser.add_argument("--provider-config", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()
    try:
        started = time.monotonic()
        records = [json.loads(line) for line in args.passages.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
        if args.limit:
            records = records[: args.limit]
        provider = DeepSeekProvider(model=json.loads(args.provider_config.read_text(encoding="utf-8-sig")).get("model"))
        args.out_dir.mkdir(parents=True, exist_ok=True)
        runs_path = args.out_dir / "ratings.jsonl"
        done_ids = set()
        if runs_path.exists():
            for line in runs_path.read_text(encoding="utf-8-sig").splitlines():
                if not line.strip():
                    continue
                done_ids.add(json.loads(line).get("task_id"))
        written = 0
        with runs_path.open("a", encoding="utf-8") as fh:
            for record in records:
                if record["task_id"] in done_ids:
                    continue
                label = rate_one(record, provider)
                fh.write(json.dumps({"task_id": record["task_id"], "label": label}, ensure_ascii=False) + "\n")
                fh.flush()
                written += 1
        receipt = {
            "schema_version": "1.0",
            "execution_state": "completed",
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "passages_sha256": sha256_file(args.passages),
            "total": len(records),
            "newly_rated": written,
            "runs_sha256": sha256_file(runs_path),
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
