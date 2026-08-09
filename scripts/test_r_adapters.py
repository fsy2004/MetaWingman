#!/usr/bin/env python3
"""Run every bundled R manifest on its declared example and record results."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path


def value_arg(value) -> str:
    if isinstance(value, bool): return "true" if value else "false"
    return str(value)


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("skill", type=Path); parser.add_argument("--outdir", required=True, type=Path); parser.add_argument("--timeout", type=int, default=180); parser.add_argument("--match", default=""); args = parser.parse_args()
    skill = args.skill.resolve(); base = skill / "scripts/r"; manifests = base / "manifests"; adapters = base / "adapters"; toolkit = base / "toolkit"
    args.outdir.mkdir(parents=True, exist_ok=True); results = []
    rscript = os.getenv("RSCRIPT", r"C:\Program Files\R\R-4.4.3\bin\Rscript.exe")
    for manifest_path in sorted(manifests.glob("*.json")):
        if args.match and args.match not in manifest_path.name: continue
        manifest = json.loads(manifest_path.read_text(encoding="utf-8")); mid = manifest.get("id", manifest_path.stem); started = time.time()
        entry = str(manifest.get("entry", "")).replace("adapters/meta/", "")
        script = adapters / entry
        inputs = manifest.get("inputs", []); primary = next((x for x in inputs if x.get("primary")), inputs[0] if inputs else None)
        example = adapters / primary.get("example", "") if primary else None
        output = args.outdir / mid; output.mkdir(parents=True, exist_ok=True)
        cmd = [rscript, str(script), "--outdir", str(output), "--toolkit", str(toolkit)]
        if primary: cmd += [primary.get("flag", "--input"), str(example)]
        if manifest.get("analysis"): cmd += ["--analysis", str(manifest["analysis"])]
        props = manifest.get("params_schema", {}).get("properties", {}); flags = manifest.get("param_flags", {})
        for key, flag in flags.items():
            if key in props and "default" in props[key]: cmd += [flag, value_arg(props[key]["default"])]
        status = "passed"; returncode = 0; note = ""
        try:
            proc = subprocess.run(cmd, cwd=adapters, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=args.timeout)
            returncode = proc.returncode
            (output / "stdout.log").write_text(proc.stdout, encoding="utf-8")
            (output / "stderr.log").write_text(proc.stderr, encoding="utf-8")
            if returncode != 0: status = "failed"; note = proc.stderr[-1000:] or proc.stdout[-1000:]
        except subprocess.TimeoutExpired as exc:
            status = "timeout"; returncode = -1; note = str(exc)
        except Exception as exc:
            status = "error"; returncode = -2; note = f"{type(exc).__name__}: {exc}"
        result = {"id": mid, "manifest": manifest_path.name, "status": status, "returncode": returncode, "seconds": round(time.time() - started, 2), "output_files": len([x for x in output.rglob("*") if x.is_file() and x.name not in {"stdout.log", "stderr.log"}]), "note": note}
        results.append(result); print(json.dumps(result, ensure_ascii=False), flush=True)
    summary = {"created_at": datetime.now(timezone.utc).isoformat(), "total": len(results), "passed": sum(x["status"] == "passed" for x in results), "failed": sum(x["status"] != "passed" for x in results), "results": results}
    (args.outdir / "adapter-regression.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({k: summary[k] for k in ["total", "passed", "failed"]}), flush=True)
    return 1 if summary["failed"] else 0


if __name__ == "__main__": raise SystemExit(main())
