"""AI-only screening pilot runner (VAL-3, preregistered 2026-08-18).

Screens a frozen candidate sample with a hosted model using the VERBATIM
eligibility criteria of the 2021 review. One schema-repair retry per record,
then abstain. Writes a run record + receipt; scoring is a separate step
(gold recall only, per the preregistration).

Usage:
  python metawingman/scripts/run_ai_screening_pilot.py \
    --sample <frozen-sample.jsonl> \
    --criteria research/ag-rdt-eligibility-criteria-2021.json \
    --provider-config metawingman/references/deepseek-provider-config.json \
    --out-dir <dir> --repetition 1
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from metawingman_core.deepseek_provider import DeepSeekProvider  # noqa: E402
from metawingman_core.model_provider import ProviderRequestError  # noqa: E402
from metawingman_core.openai_compatible_provider import OpenAICompatibleProvider  # noqa: E402

SYSTEM = (
    "You are a systematic-review screening assistant. Screen the record "
    "against the review's inclusion and exclusion criteria, quoted verbatim "
    "below. Output ONLY JSON: "
    '{"decision": "include"|"exclude"|"abstain", "anchor": "<short verbatim '
    'quote of the criterion that decides, or the reason for abstention>"}. '
    "If the title and abstract are insufficient to decide, output abstain."
)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_prompt(criteria: dict) -> str:
    inc = criteria.get("verbatim_methods_section") or ""
    lines = ["ELIGIBILITY CRITERIA (verbatim from the review):", inc, "", "RECORD:"]
    return "\n".join(lines)


def load_provider(config_path: Path):
    config = json.loads(config_path.read_text(encoding="utf-8-sig"))
    adapter = config.get("adapter", "openai_compatible")
    if adapter == "deepseek":
        return DeepSeekProvider(model=config.get("model"))
    return OpenAICompatibleProvider(
        base_url=config.get("base_url"), api_key=os.environ.get(config.get("api_key_env", "")),
        model=config.get("model"),
    )


def screen(record: dict, prompt_prefix: str, provider) -> dict:
    prompt = f"{prompt_prefix} Title: {record.get('title') or ''}\nAbstract: {(record.get('abstract') or '')[:2000]}"
    attempts = []
    for attempt in range(2):
        try:
            result = provider.chat(
                messages=[
                    {"role": "system", "content": SYSTEM},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=1024,
                json_output=True,
            )
        except ProviderRequestError as exc:
            return {"decision": "abstain", "anchor": f"provider_error:{exc}", "attempts": attempts}
        text = (result.content or "").strip()
        attempts.append({
            "attempt": attempt + 1,
            "content_sha256": hashlib.sha256(text.encode()).hexdigest(),
            "prompt_tokens": result.prompt_tokens,
            "completion_tokens": result.completion_tokens,
            "total_tokens": result.total_tokens,
        })
        # extract the first JSON object from the text
        try:
            start = text.index("{")
            end = text.rindex("}") + 1
            payload = json.loads(text[start:end])
            decision = payload.get("decision")
            if decision not in ("include", "exclude", "abstain"):
                raise ValueError("decision must be include|exclude|abstain")
            payload["anchor"] = str(payload.get("anchor") or "")[:500]
            payload["attempts"] = attempts
            return payload
        except (ValueError, json.JSONDecodeError) as exc:
            if attempt == 0:
                continue  # one schema repair
            return {"decision": "abstain", "anchor": f"schema_failure:{exc}", "attempts": attempts}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample", type=Path, required=True)
    parser.add_argument("--criteria", type=Path, required=True)
    parser.add_argument("--provider-config", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--repetition", type=int, default=1)
    args = parser.parse_args()
    try:
        started = time.monotonic()
        criteria = json.loads(args.criteria.read_text(encoding="utf-8-sig"))
        records = [json.loads(line) for line in args.sample.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
        if not records:
            raise ValueError("sample is empty")
        provider = load_provider(args.provider_config)
        args.out_dir.mkdir(parents=True, exist_ok=True)  # resume-friendly
        prompt_prefix = build_prompt(criteria)
        runs_path = args.out_dir / "screening-runs.jsonl"
        done_ids: set[str] = set()
        if runs_path.exists():
            for line in runs_path.read_text(encoding="utf-8-sig").splitlines():
                if not line.strip():
                    continue
                row = json.loads(line)
                if row.get("repetition") == args.repetition:
                    done_ids.add(row.get("record_id"))
        started_count = len(done_ids)
        with runs_path.open("a", encoding="utf-8") as fh:
            for record in records:
                if record["id"] in done_ids:
                    continue  # resume
                decision = screen(record, prompt_prefix, provider)
                row = {
                    "record_id": record["id"],
                    "repetition": args.repetition,
                    "decision": decision.get("decision"),
                    "anchor": decision.get("anchor"),
                    "attempts": decision.get("attempts"),
                    "input_sha256": hashlib.sha256(
                        f"{record.get('title') or ''}|{(record.get('abstract') or '')[:2000]}".encode()
                    ).hexdigest(),
                }
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
                fh.flush()
        receipt = {
            "schema_version": "1.0",
            "execution_state": "completed",
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "sample_sha256": sha256_file(args.sample),
            "criteria_sha256": sha256_file(args.criteria),
            "provider_config_sha256": sha256_file(args.provider_config),
            "prompt_prefix_sha256": hashlib.sha256(prompt_prefix.encode()).hexdigest(),
            "records": len(records),
            "resumed_from": started_count,
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
