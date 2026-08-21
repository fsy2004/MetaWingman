#!/usr/bin/env python3
"""Refresh MetaWingman's generated README metrics and check for drift."""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"


def replace_block(text: str, name: str, content: str) -> str:
    start = f"<!-- {name}:start -->"
    end = f"<!-- {name}:end -->"
    pattern = re.compile(re.escape(start) + r".*?" + re.escape(end), re.DOTALL)
    if not pattern.search(text):
        raise ValueError(f"README is missing generated block {name}")
    return pattern.sub(f"{start}\n{content.rstrip()}\n{end}", text, count=1)


def local_link_errors(root: Path, text: str) -> list[str]:
    missing = []
    for raw in re.findall(r"\]\(([^)]+)\)", text):
        target = raw.strip().strip("<>")
        if not target or target.startswith(("#", "http://", "https://", "mailto:")):
            continue
        target = target.split("#", 1)[0]
        if target and not (root / target).exists() and target not in missing:
            missing.append(target)
    return missing


def compute_metrics(root: Path) -> dict[str, int]:
    return {
        "r_modules": len(list((root / "toolkit" / "R").glob("*.R"))),
        "manifests": len(list((root / "metawingman" / "scripts" / "r" / "manifests").glob("*.json"))),
        "adapters": len(list((root / "metawingman" / "scripts" / "r" / "adapters").glob("run_*.R"))),
        "python_entrypoints": len(list((root / "metawingman" / "scripts").glob("*.py"))),
        "schemas": len(list((root / "metawingman" / "schemas").glob("*.json"))),
    }


def latest_tag(root: Path) -> str:
    result = subprocess.run(["git", "tag", "--sort=-v:refname"], cwd=root, capture_output=True, text=True, check=True)
    return next((line.strip() for line in result.stdout.splitlines() if line.strip()), "unreleased")


def render_metrics(root: Path, *, version: str | None = None) -> str:
    metrics = compute_metrics(root)
    version = version or latest_tag(root)
    return (
        "[![license](https://img.shields.io/badge/license-MIT-15803D)](LICENSE)\n"
        f"[![release](https://img.shields.io/badge/release-{version}-2563EB)](https://github.com/fsy2004/MetaWingman/releases)\n"
        f"![R toolkit](https://img.shields.io/badge/R_modules-{metrics['r_modules']}-276DC3)\n"
        f"![manifests](https://img.shields.io/badge/manifests-{metrics['manifests']}-7C3AED)\n"
        f"![schemas](https://img.shields.io/badge/schemas-{metrics['schemas']}-0F766E)"
    )


def render_inventory(root: Path) -> str:
    metrics = compute_metrics(root)
    return (
        "| Repository metric | Current |\n"
        "|---|---:|\n"
        f"| Python entry points | {metrics['python_entrypoints']} |\n"
        f"| JSON schemas | {metrics['schemas']} |\n"
        f"| R analysis modules | {metrics['r_modules']} |\n"
        f"| R adapter manifests | {metrics['manifests']} |\n"
        f"| R adapters | {metrics['adapters']} |"
    )


def update_generated_blocks(root: Path, text: str, *, version: str | None = None) -> str:
    updated = replace_block(text, "readme-metrics", render_metrics(root, version=version))
    return replace_block(updated, "readme-inventory", render_inventory(root))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="fail instead of writing when README metrics drift")
    args = parser.parse_args()
    source = README.read_text(encoding="utf-8")
    expected = update_generated_blocks(ROOT, source)
    missing = local_link_errors(ROOT, expected)
    if missing:
        print("README has missing local links: " + ", ".join(missing), file=sys.stderr)
        return 1
    if expected == source:
        print("README generated metrics are current")
        return 0
    if args.check:
        print("README generated metrics are stale; run: python scripts/update_readme.py", file=sys.stderr)
        return 1
    README.write_text(expected, encoding="utf-8", newline="\n")
    print("README generated metrics updated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
