#!/usr/bin/env python3
"""Generate a Markdown inventory from bundled R modules and adapter manifests."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


FUNCTION = re.compile(r"^([A-Za-z][A-Za-z0-9_.]*)\s*<-\s*function", re.MULTILINE)


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("skill", type=Path); args = parser.parse_args(); root = args.skill.resolve()
    toolkit_root = root / "scripts/r/toolkit"
    if not toolkit_root.is_dir(): toolkit_root = root.parent / "toolkit"
    toolkit = toolkit_root / "R"; adapters = root / "scripts/r/adapters"; manifests = root / "scripts/r/manifests"
    lines = ["# Bundled analysis tool catalog", "", "Generated from live bundled source. Functions are wrappers around cited R packages; availability still depends on installed packages and compatible input data.", "", "## Toolkit modules", "", "| File | Exported functions |", "|---|---|"]
    total = 0
    for path in sorted(toolkit.glob("*.R")):
        funcs = FUNCTION.findall(path.read_text(encoding="utf-8", errors="ignore")); total += len(funcs)
        lines.append(f"| `toolkit/R/{path.name}` | {', '.join(f'`{x}`' for x in funcs) or 'internal helpers'} |")
    lines += ["", f"Bundled public-function count: **{total}**.", "", "## Executable adapter families", "", "| Adapter | Purpose |", "|---|---|"]
    purpose = {
        "run_pairwise.R": "pairwise effects, binary/continuous/correlation/survival plots and summaries",
        "run_heterogeneity.R": "heterogeneity, subgroup, meta-regression, permutation and prediction",
        "run_influence.R": "leave-one-out, Baujat, cumulative, GOSH and diagnostics",
        "run_network.R": "network models, graph, rank, league, inconsistency and component analyses",
        "run_diagnostic.R": "DTA bivariate/HSROC, SROC, sensitivity/specificity, LR and DOR",
        "run_proportion.R": "proportion, mean and incidence-rate synthesis",
        "run_complex.R": "multilevel, robust variance and dose-response models",
        "run_bayesian.R": "Bayesian random-effects summaries and posterior displays",
        "run_sequential.R": "trial sequential analysis and required information size",
        "run_convert.R": "effect and uncertainty conversions",
        "run_dataprep_msd.R": "median/range/IQR to mean and SD",
        "run_prisma.R": "PRISMA flow diagram",
        "run_rob.R": "risk-of-bias visualizations",
        "run_grade.R": "GRADE/SoF helpers",
        "run_evalue.R": "E-value sensitivity analysis",
    }
    for path in sorted(adapters.glob("run_*.R")): lines.append(f"| `scripts/r/adapters/{path.name}` | {purpose.get(path.name, 'see source and manifest')} |")
    lines += ["", "## Manifests", "", f"Bundled manifest count: **{len(list(manifests.glob('*.json')))}**. Some legacy manifest text may contain encoding damage; treat executable R source and validated input/output behavior as authority.", "", "## Method boundary", "", "The catalog is not a recommendation to run every method. Select only analyses justified by the protocol, estimand, design, dependency structure, information size, and current methodological guidance. Record package citations from `toolkit/docs/REFERENCES.md`."]
    out = root / "references/tool-catalog.md"; out.write_text("\n".join(lines) + "\n", encoding="utf-8"); print(out); return 0


if __name__ == "__main__": raise SystemExit(main())
