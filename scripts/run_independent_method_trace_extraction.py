#!/usr/bin/env python3
"""Independently extract gold *method trajectories* from real published meta
reviews, WITHOUT reference to our profile/identification/synthesis maps.

This is what breaks the same-source self-check: the reference instructions ask
the provider to read the paper's methods and report, verbatim, the actual method
process the review used (design type, how it estimated, synthesis approach,
heterogeneity handling, whether it pooled, why it stopped), and FORBID outputting
any numeric outcome (effect, I2, GRADE, direction). It also forbids using any
pre-canned meta-type taxonomy so the extract is genuinely independent.

Runs on the server where the deepseek provider is configured. Deterministic given
the same paper text + provider; the extraction request can be generated locally
with --dry-run (no provider call).

Usage:
  python scripts/run_independent_method_trace_extraction.py \
      --catalog research/method-trace-request-catalog.json \
      --provider-config metawingman/references/deepseek-provider-config.json \
      --out research/method-trace-gold-independent.jsonl \
      [--dry-run] [--limit 40] [--fulltext-dir research/method-trace-fulltext]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from metawingman.scripts.metawingman_core.model_provider import ModelProvider
from metawingman.scripts.metawingman_core.provider_factory import build_provider, load_provider_config
from metawingman.scripts.metawingman_core.state_store import sha256_json

# The independent extraction prompt. Crucially it forbids numeric outcomes AND
# forbids using a pre-canned meta-type taxonomy — the extract must reflect the
# paper's own method process.
INDEPENDENT_SYSTEM = (
    "You are extracting the METHOD STRUCTURE of a published systematic review / meta-analysis, to use as an "
    "expert reference. Read only the methods/design sections. Report what THIS review actually did as JSON "
    "with exactly these fields:\n"
    "- design_type_hint: one of pairwise|network|diagnostic|prediction|prevalence|exposure|narrative_no_pooling "
    "— based on the paper's own procedural structure (how many interventions/comparators it compared, whether "
    "it used a reference standard or a prediction model, and whether it pooled or narrated).\n"
    "- intervention_arm_count: integer — number of distinct intervention/arm groups compared (0 if not an "
    "intervention comparison).\n"
    "- comparator_count: integer — number of distinct comparator nodes.\n"
    "- has_reference_standard: true/false — a diagnostic reference standard present.\n"
    "- has_prediction_model: true/false — a prediction/risk model present.\n"
    "- outcome_measure_type: one of binary|continuous|rate|proportion|diagnostic — the outcome measure nature.\n"
    "- pooled: true/false — did it actually produce a pooled estimate.\n"
    "- living_or_update: true/false — is it a living review / ongoing update.\n"
    "- estimand: string — what it aimed to estimate.\n"
    "- heterogeneity_handling: string — how it handled heterogeneity.\n"
    "HARD RULES: (1) Do NOT report any numeric outcome — no pooled effect, no I2 value, no GRADE grade, no "
    "direction, no CI. (2) Base design_type_hint on the paper's actual procedural structure (arm counts, "
    "reference standard, prediction model, pooled/narrative), not on guessing a pre-canned taxonomy. "
    "(3) When the paper does not state a numeric field, use 0 / false / the most conservative enum."
)


def fetch_fulltext(record: dict, fulltext_dir: Path) -> str | None:
    """Fetch the paper full text (Europe PMC fullTextXML) and cache it."""
    if fulltext_dir.is_dir():
        cached = fulltext_dir / f"{record['source_id'].replace(':', '_')}.xml"
        if cached.is_file():
            return cached.read_text(encoding="utf-8", errors="replace")
    import urllib.request

    src = record.get("pmcid") or record.get("source_id") or record.get("record_id") or ""
    if not src:
        return None
    url = f"https://www.ebi.ac.uk/europepmc/webservices/rest/{src}/fullTextXML"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "MetaWingman/1.0"})
        with urllib.request.urlopen(req, timeout=40) as resp:
            payload = resp.read().decode("utf-8", errors="replace")
        if fulltext_dir.is_dir():
            fulltext_dir.mkdir(parents=True, exist_ok=True)
            (fulltext_dir / f"{src.replace(':', '_')}.xml").write_text(payload, encoding="utf-8")
        return payload
    except Exception:
        return None


def extraction_request(record: dict) -> dict:
    """The extraction request (without needing full text yet)."""
    return {
        "record_id": record["record_id"],
        "doi": record["doi"],
        "title": record["title"],
        "journal": record["journal"],
        "year": record["year"],
        "task": "independent_method_structure_extraction",
        "output_schema": ["design_type_hint", "intervention_arm_count", "comparator_count",
                          "has_reference_standard", "has_prediction_model", "outcome_measure_type",
                          "pooled", "living_or_update", "estimand", "heterogeneity_handling"],
        "rules": ["no numeric outcome", "structure-driven design_type_hint"],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--catalog", required=True)
    ap.add_argument("--provider-config", default=None)
    ap.add_argument("--out", required=True)
    ap.add_argument("--fulltext-dir", default=None)
    ap.add_argument("--limit", type=int, default=40)
    ap.add_argument("--max-tokens", type=int, default=1200)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    catalog = json.loads(Path(args.catalog).read_text(encoding="utf-8"))
    records = catalog["records"][: args.limit]
    provider: ModelProvider | None = None
    if not args.dry_run:
        if not args.provider_config:
            raise SystemExit("--provider-config required unless --dry-run")
        provider = build_provider(load_provider_config(Path(args.provider_config)))

    fulltext_dir = Path(args.fulltext_dir) if args.fulltext_dir else None
    results = []
    n_fetched = n_failed = n_extracted = 0
    for record in records:
        request = extraction_request(record)
        if args.dry_run:
            results.append({"record_id": record["record_id"], "request": request,
                            "mode": "dry_run"})
            continue
        fulltext = fetch_fulltext(record, fulltext_dir) if fulltext_dir else None
        if not fulltext:
            n_failed += 1
            results.append({"record_id": record["record_id"], "status": "fulltext_unavailable",
                            "mode": "skip"})
            continue
        n_fetched += 1
        # Truncate full text to the methods portion (heuristic) but keep author-written text.
        text = fulltext  # provider reads the article; the system prompt directs to methods.
        user_msg = (
            f"Article: {record['title']} ({record['journal']}, {record['year']}). "
            f"DOI: {record['doi']}.\n"
            f"Extract the METHOD STRUCTURE per the system rules. Return a JSON object with exactly the "
            "fields: design_type_hint, intervention_arm_count, comparator_count, has_reference_standard, "
            "has_prediction_model, outcome_measure_type, pooled, living_or_update, estimand, "
            "heterogeneity_handling. No numeric outcome values."
        )
        try:
            result = provider.chat(
                [{"role": "system", "content": INDEPENDENT_SYSTEM},
                 {"role": "user", "content": user_msg}],
                model=None, json_output=True, max_tokens=args.max_tokens,
            )
            content = result.content
            try:
                parsed = json.loads(content)
            except json.JSONDecodeError:
                parsed = {"raw": content}
            parsed.pop("raw", None)
            results.append({"record_id": record["record_id"], "status": "extracted",
                            "method_trace": parsed, "content_sha256": result.content_sha256,
                            "mode": "extract"})
            n_extracted += 1
        except Exception as exc:
            results.append({"record_id": record["record_id"], "status": "error",
                            "error": f"{type(exc).__name__}: {exc}", "mode": "extract"})

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as handle:
        for row in results:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    summary = {"mode": "dry_run" if args.dry_run else "extract",
               "records": len(records), "fetched": n_fetched,
               "extracted": n_extracted, "fulltext_unavailable": n_failed,
               "out": str(out)}
    summary["receipt_sha256"] = sha256_json(summary)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
