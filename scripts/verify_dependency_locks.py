#!/usr/bin/env python3
"""Verify the current Python and R runtimes against release dependency locks."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEPENDENCIES = ROOT / "metawingman/references/dependencies"
PIN = re.compile(r"^([A-Za-z0-9_.-]+)==([^\s]+)$")


def read_python_lock(path: Path) -> dict[str, str]:
    pins: dict[str, str] = {}
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = PIN.fullmatch(line)
        if not match:
            raise ValueError(f"{path}:{line_number}: dependency must be exactly pinned")
        name, version = match.groups()
        key = name.casefold().replace("_", "-")
        if key in pins:
            raise ValueError(f"{path}:{line_number}: duplicate package {name}")
        pins[key] = version
    return pins


def verify_python(paths: list[Path]) -> list[str]:
    issues: list[str] = []
    for path in paths:
        for package, expected in read_python_lock(path).items():
            try:
                actual = importlib.metadata.version(package)
            except importlib.metadata.PackageNotFoundError:
                issues.append(f"Python package missing: {package}=={expected}")
                continue
            if actual != expected:
                issues.append(f"Python package drift: {package} expected {expected}, found {actual}")
    return issues


def verify_r(path: Path, rscript: str) -> list[str]:
    lock = json.loads(path.read_text(encoding="utf-8"))
    packages: dict[str, str] = lock["packages"]
    expression = (
        "ip<-installed.packages();"
        "p<-c(" + ",".join(json.dumps(name) for name in packages) + ");"
        "cat(paste(p,ifelse(p %in% rownames(ip),ip[p,'Version'],'MISSING'),sep='=='),sep='\\n')"
    )
    process = subprocess.run(
        [rscript, "-e", expression],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if process.returncode != 0:
        return [f"R dependency query failed: {process.stderr.strip() or process.stdout.strip()}"]
    observed = dict(line.split("==", 1) for line in process.stdout.splitlines() if "==" in line)
    issues = []
    for package, expected in packages.items():
        actual = observed.get(package, "MISSING")
        if actual == "MISSING":
            issues.append(f"R package missing: {package}=={expected}")
        elif actual != expected:
            issues.append(f"R package drift: {package} expected {expected}, found {actual}")
    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-python", action="store_true")
    parser.add_argument("--skip-pdf", action="store_true")
    parser.add_argument("--skip-r", action="store_true")
    parser.add_argument("--rscript", default="Rscript")
    args = parser.parse_args()
    python_locks = [] if args.skip_python else [DEPENDENCIES / "python-core.lock.txt"]
    if not args.skip_python and not args.skip_pdf:
        python_locks.append(DEPENDENCIES / "python-pdf.lock.txt")
    issues = verify_python(python_locks)
    if not args.skip_r:
        issues.extend(verify_r(DEPENDENCIES / "r-packages.lock.json", args.rscript))
    result = {
        "valid": not issues,
        "python_locks": [str(path.relative_to(ROOT)) for path in python_locks],
        "r_lock_checked": not args.skip_r,
        "issues": issues,
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if not issues else 1


if __name__ == "__main__":
    raise SystemExit(main())
