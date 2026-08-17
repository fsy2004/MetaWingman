#!/usr/bin/env python3
"""Benchmark build_retrieval_pairs at ~12,000-record / ~30,000-query scale.

Builds synthetic evidence-retrieval examples whose token-overlap distribution
mimics the real biomedical corpus (shared common vocabulary + specialty-biased
terms + per-section unique terms) so the hard-negative ranking does real work,
then times build_retrieval_pairs and checks determinism.

No large data files are written; everything is generated in memory.
"""

from __future__ import annotations

import argparse
import hashlib
import random
import sys
import time
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "metawingman" / "scripts"))

from metawingman_core.training_corpus import build_retrieval_pairs  # noqa: E402


SPECIALTIES = [
    "general-medicine", "neurology", "mental-health", "cardiovascular-medicine",
    "oncology", "maternal-child-health", "infectious-disease", "diagnostics",
    "imaging", "public-health", "clinical-omics", "drug-safety",
]
QUESTION_TYPES = [
    "unresolved", "intervention", "etiology", "harms",
    "prevalence", "diagnostic", "prognostic",
]
# Specialty weights mirror the frozen v3 plan (general-medicine dominates).
SPECIALTY_WEIGHTS = [
    4934, 1550, 1477, 1381, 885, 548, 453, 391, 202, 134, 41, 4,
]
QUESTION_WEIGHTS = [5499, 1892, 1313, 1310, 1203, 412, 371]

COMMON_WORDS = [
    "systematic", "review", "meta", "analysis", "studies", "patients", "outcomes",
    "treatment", "evidence", "risk", "bias", "selection", "criteria", "search",
    "database", "medline", "embase", "cochrane", "controlled", "trial", "cohort",
    "observational", "prospective", "retrospective", "follow", "up", "baseline",
    "intervention", "comparator", "placebo", "randomized", "blinding", "allocation",
    "concealment", "attrition", "heterogeneity", "subgroup", "sensitivity",
    "publication", "funnel", "plot", "forest", "confidence", "interval", "odds",
    "ratio", "relative", "absolute", "incidence", "prevalence", "mortality",
    "morbidity", "quality", "life", "adverse", "events", "safety", "efficacy",
    "effectiveness", "dose", "duration", "adherence", "discontinuation", "washout",
    "crossover", "parallel", "arm", "allocation", "stratification", "center",
    "multicenter", "population", "sample", "inclusion", "exclusion", "eligibility",
    "consent", "ethics", "registration", "protocol", "prospero", "reporting",
    "guideline", "prisma", "abstract", "title", "author", "journal", "year",
    "country", "language", "duplicate", "screening", "full", "text", "extraction",
    "independent", "reviewers", "disagreement", "consensus", "third", "adjudication",
    "kappa", "agreement", "agreement", "agreement", "agreement", "agreement",
    "mean", "standard", "deviation", "median", "range", "interquartile", "count",
    "percentage", "missing", "imputation", "complete", "case", "analysis",
    "intention", "treat", "protocol", "deviation", "adjustment", "covariate",
    "confounder", "interaction", "moderator", "mediator", "regression", "logistic",
    "linear", "cox", "hazard", "survival", "kaplan", "meier", "log", "rank",
    "p", "value", "significance", "power", "sample", "size", "calculation",
    "effect", "size", "direction", "magnitude", "precision", "consistency",
    "directness", "grade", "certainty", "recommendation", "strength", "weak",
    "conditional", "high", "moderate", "low", "very", "critically", "important",
    "benefit", "harm", "burden", "equity", "acceptability", "feasibility",
    "cost", "resource", "use", "implementation", "barrier", "facilitator",
    "stakeholder", "patient", "public", "involvement", "dissemination",
]
SPECIALTY_WORDS = {
    specialty: [f"{specialty[:6]}{i}term{j}" for j in range(24) for i in range(3)]
    for specialty in SPECIALTIES
}
FIXED_TERMS = COMMON_WORDS[:160]  # terms every section shares -> nonzero overlap floor


def _section_text(rng: random.Random, specialty: str, section: int) -> str:
    sample = list(FIXED_TERMS)
    sample.extend(rng.sample(COMMON_WORDS, 120))
    sample.extend(rng.sample(SPECIALTY_WORDS[specialty], 18))
    sample.extend(f"unique{section}x{k}" for k in range(8))
    return " ".join(sample)


def build_synthetic_examples(num_docs: int, query_ratio: float, seed: int):
    rng = random.Random(seed)
    total_queries = int(round(num_docs * query_ratio))
    examples = []
    strata = {}
    section = 0
    doc = 0
    while section < total_queries:
        split = "train" if rng.random() < 0.8 else "development"
        specialty = rng.choices(SPECIALTIES, weights=SPECIALTY_WEIGHTS, k=1)[0]
        question = rng.choices(QUESTION_TYPES, weights=QUESTION_WEIGHTS, k=1)[0]
        record_id = f"epmc:MED:{doc}"
        family_id = f"family:{doc:016x}"
        strata[record_id] = {"primary_specialty": specialty, "question_type": question}
        # 2 or 3 retrieval sections per document (average ~query_ratio).
        per_doc = 2 if doc % 2 == 0 else 3
        for _ in range(per_doc):
            if section >= total_queries:
                break
            text = _section_text(rng, specialty, section)
            passage = text
            example_id = f"example:{section:020x}"
            examples.append({
                "schema_version": "1.0",
                "example_id": example_id,
                "document_id": f"training-document:PMC{1000 + doc}",
                "record_id": record_id,
                "family_id": family_id,
                "split": split,
                "task": "evidence_retrieval",
                "instruction": "Identify the source passage that supports the review workflow field: search.",
                "review_title": f"Systematic review {doc}",
                "input_text": "Section title: Search strategy\n\n" + passage,
                "target": {"section_role": "search", "section_title": "Search strategy"},
                "evidence_anchor": {
                    "artifact_sha256": f"{section:064x}",
                    "section_path": f"//body//sec[{section}]",
                    "section_index": section,
                    "source_text_sha256": hashlib.sha256(passage.encode("utf-8")).hexdigest(),
                },
                "label_status": "deterministic_weak_supervision_requires_independent_validation",
                "gold_label": False,
            })
            section += 1
        doc += 1
    return examples, strata


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--docs", type=int, default=12000)
    parser.add_argument("--query-ratio", type=float, default=2.5)
    parser.add_argument("--seed", type=int, default=20260815)
    parser.add_argument("--profile", action="store_true")
    args = parser.parse_args()

    examples, strata = build_synthetic_examples(args.docs, args.query_ratio, seed=1)
    print(f"queries={len(examples)} docs={args.docs} "
          f"train={sum(e['split']=='train' for e in examples)} "
          f"dev={sum(e['split']=='development' for e in examples)}")

    if args.profile:
        import cProfile
        import pstats

        profiler = cProfile.Profile()
        profiler.enable()
        pairs = build_retrieval_pairs(examples, strata, args.seed)
        profiler.disable()
        stats = pstats.Stats(profiler)
        stats.sort_stats("cumulative").print_stats(20)
    else:
        start = time.perf_counter()
        pairs = build_retrieval_pairs(examples, strata, args.seed)
        elapsed = time.perf_counter() - start

    labels = Counter(pair["label"] for pair in pairs)
    print(f"pairs={len(pairs)} positives={labels[1]} negatives={labels[0]} "
          f"families={len({p['query_family_id'] for p in pairs})}")

    # Determinism check: same inputs -> byte-identical pair ids and ordering.
    pairs2 = build_retrieval_pairs(examples, strata, args.seed)
    assert [p["pair_id"] for p in pairs] == [p["pair_id"] for p in pairs2]
    assert pairs == pairs2
    print(f"deterministic=True")

    if not args.profile:
        print(f"build_retrieval_pairs: {elapsed:.3f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
