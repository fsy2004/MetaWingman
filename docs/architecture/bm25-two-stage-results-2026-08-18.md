# BM25-Recall Two-Stage Retrieval Results (2026-08-18)

> Executes the direction fix prescribed in
> `two-stage-retrieval-results-2026-08-18.md`: retest the two-stage ceiling
> with a stronger lexical recall (BM25) instead of a larger K. Script:
> `tools/bm25-two-stage-retrieval-eval.py` (server run 2026-08-18, 145 s,
> dev 10,882×10,882, family-masked, positive = own document).

## 1. Results (full receipt: `/root/autodl-tmp/bm25-two-stage-results.json`)

| Stage | MRR | R@10 | P@1 |
|---|---|---|---|
| TF-IDF full corpus (continuity) | 0.2199 | 0.3148 | 0.1702 |
| **BM25 full corpus** (k1=1.5, b=0.75) | **0.2649** | 0.3447 | 0.2212 |
| trained model full corpus | 0.0045 | 0.0060 | 0.0006 |
| two-stage K=50 (BM25 recall + rerank) | 0.1278 | 0.3030 | 0.0561 |
| two-stage K=100 | 0.0895 | 0.2313 | 0.0316 |
| two-stage K=200 | 0.0581 | 0.1437 | 0.0154 |

BM25 recall ceilings: 0.4300 / 0.4655 / 0.5071 at K=50/100/200.

## 2. Conclusions (evidence chain now closed)

1. **BM25 single-stage is the best open-retrieval option** (MRR 0.2649),
   ahead of TF-IDF (0.2199) and far ahead of the trained 110M model
   (0.0045) — consistent with the earlier lexical-superiority finding.
2. **The trained reranker is negative-contribution in open-corpus candidate
   sets**: two-stage MRR falls monotonically with K (0.128 → 0.058) and is
   always below the BM25 single-stage baseline. Its competence is confined
   to its own training distribution (curated hard-negative candidate sets,
   MRR 0.962). Direction: **use BM25 for open retrieval; keep the trained
   component as a reranker on curated candidate sets only.**
3. **Recall ceiling ~50% is inherent to the dev task semantics** (query =
   instruction + review title; positive = the query's own document): about
   half of the positives cannot be lexically recovered at K=200 under
   family masking. No K increase fixes this; a different task design would
   (e.g. query = title alone, or positives = the review's own included
   studies). Recorded as a known task-design limitation, not a model bug.

## 3. Actions applied

- `next-steps-2026-08-18.md` P0 item 1 marked concluded with this verdict.
- Retrieval architecture in the skill stays: lexical (BM25) first stage for
  open corpora; trained reranker gated to curated candidate sets.
