#!/usr/bin/env python3
"""Remove target-family identities and unverifiable/post-cutoff records."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

from metawingman_core.operational_corpus import load_jsonl_records, sanitize_records


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--records", type=Path, required=True)
    parser.add_argument("--cutoff", required=True)
    parser.add_argument("--forbidden", action="append", default=[])
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    started = time.monotonic()
    try:
        records = load_jsonl_records(args.records)
        clean, audit = sanitize_records(records, cutoff=args.cutoff, forbidden_identity_patterns=args.forbidden)
        args.out_dir.mkdir(parents=True, exist_ok=False)
        output = args.out_dir / "operational-candidates.jsonl"
        output.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in clean) + "\n", encoding="utf-8")
        receipt = {
            "schema_version": "1.0", "execution_state": "completed",
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "cutoff": args.cutoff, "forbidden_patterns_sha256": hashlib.sha256(
                json.dumps(args.forbidden, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            ).hexdigest(),
            "audit": audit, "input_sha256": sha256_file(args.records),
            "output_sha256": sha256_file(output), "output_bytes": output.stat().st_size,
        }
        (args.out_dir / "execution-receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(receipt, indent=2, sort_keys=True))
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"execution_state": "failed", "error": str(exc)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
