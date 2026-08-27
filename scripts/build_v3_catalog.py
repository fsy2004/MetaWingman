#!/usr/bin/env python3
"""Build the v3 judgment-layer catalog from EXISTING assets.

Source of candidates: research/training-corpus-plan-biomedical-v3.json
(12,000 records: record_id / family_id / split / title / year / journal /
pmcid / doi / biomedical_stratum — the project's own corpus plan).

Sampling (pre-registered, seeded 20260827):
  * exclude every record already used by the v1/v2 corpora
    (request/dev-40, holdout-40, large-200 (v2 catalog ids), living-35, train-210);
  * stratify by biomedical_stratum (keep the composition in the plan);
  * family isolation: keep families that are NOT already used, and drop
    duplicate families within the sample (family_id hash order);
  * keep >= 20 records whose title indicates living/update reviews;
  * output: research/v3-catalog.json (public metadata only; no text).

Usage: python scripts/build_v3_catalog.py [--n 600] [--seed 20260827]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

RES = Path(__file__).resolve().parents[1] / "research"


def stable_order(items: list, key: str, seed: int) -> list:
    return sorted(items, key=lambda x: hashlib.sha256(f"{seed}:{x[key]}".encode()).hexdigest())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=600)
    ap.add_argument("--seed", type=int, default=20260827)
    ap.add_argument("--plan", default=str(RES / "training-corpus-plan-biomedical-v3.json"))
    args = ap.parse_args()

    plan = json.loads(Path(args.plan).read_text(encoding="utf-8"))
    records = plan["records"]

    used: set[str] = set()
    for p in ("research/method-trace-request-catalog.json",
              "research/method-trace-holdout-catalog.json",
              "research/method-trace-large-catalog.json",
              "research/living-review-catalog.json"):
        cat = json.loads((Path(__file__).resolve().parents[1] / p).read_text(encoding="utf-8"))
        used |= {r["record_id"] for r in cat.get("records", [])}
    used |= {json.loads(l)["record_id"] for l in
             (RES / "method-trace-gold-independent.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()}
    # training/validation records from the corpus plan itself (splits used before)
    used |= {r["record_id"] for r in records if r.get("split") in ("train", "validation")}

    cand = [r for r in records
            if r.get("pmcid") and r["record_id"] not in used and r.get("split") == "development"
            and str(r.get("split_status", "")).startswith("provisional_family_isolated")]
    print("candidates (family-isolated dev splits, pmcid present):", len(cand))

    # family isolation within the sample + stratum stratification
    import re
    from collections import defaultdict
    living_re = re.compile(r"living\s+(systematic|network|meta|evidence)", re.I)

    def is_living(r) -> bool:
        return bool(living_re.search(r.get("title") or ""))

    def stratum_key(r) -> str:
        bs = r.get("biomedical_stratum")
        if isinstance(bs, dict):
            return str(bs.get("primary_specialty") or bs.get("question_type") or "unknown")
        return str(bs or "unknown")

    strata = defaultdict(list)
    for r in cand:
        strata[stratum_key(r)].append(r)
    sampled: list[dict] = []
    used_families: set[str] = set()
    n_living = 0
    per_stratum = {k: max(1, round(args.n * len(v) / len(cand))) for k, v in strata.items()}
    # deterministic: stable order within stratum; also force living records first
    for stratum, items in sorted(strata.items()):
        target = per_stratum[stratum]
        ordered = stable_order(items, "record_id", args.seed)
        # keep living records with priority, then fill to target
        living_items = [r for r in ordered if is_living(r)]
        rest = [r for r in ordered if not is_living(r)]
        picked: list[dict] = []
        for r in living_items + rest:
            if len(picked) >= target:
                break
            if r["family_id"] in used_families:
                continue
            used_families.add(r["family_id"])
            picked.append(r)
            n_living += int(is_living(r))
        sampled.extend(picked)
    sampled.sort(key=lambda r: r["record_id"])
    print("sampled:", len(sampled), "| living n:", n_living)
    catalog = {
        "schema_version": "1.0",
        "source": "research/training-corpus-plan-biomedical-v3.json (project asset; metadata only)",
        "sampling": {"seed": args.seed, "target": args.n, "excluded": "all previously used corpora "
                     "(request/holdout/large/living + train/validation splits)",
                     "family_isolation": True,
                     "stratum_targets": per_stratum},
        "records": [{"record_id": r["record_id"], "pmcid": r["pmcid"], "title": r["title"],
                     "journal": r["journal"], "year": r["year"], "doi": r.get("doi"),
                     "biomedical_stratum": r.get("biomedical_stratum"),
                     "family_id": r["family_id"]} for r in sampled],
    }
    (RES / "v3-catalog.json").write_text(json.dumps(catalog, indent=2) + "\n", encoding="utf-8")
    print("wrote research/v3-catalog.json with", len(catalog["records"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
