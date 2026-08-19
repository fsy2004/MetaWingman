# MetaSyn Evaluation-Adapter Design (2026-08-18)

> Turns the two MetaSyn gaps identified in
> `research/benchmark-2606-17041-task-map.md` (gold corpus, stage-attribution
> diagnostics) into a concrete, gated plan. Design only — nothing here runs
> until the freeze conditions in §6 hold. All MetaSyn facts come from the
> verified dataset card (2026-08-18, HF API + README via proxy) and the
> task-map document.

## 1. Goal

Use MetaSyn's **test split** (86 Nature Portfolio source reviews + the shared
140,585-article PubMed corpus) as a **third-party evaluation axis** for
MetaWingman's retrieval and screening stages, measuring:

- retrieval quality against a gold included-article set (R@K, P@K);
- end-to-end included-list quality (Inc.R / Inc.P / Inc.F1);
- candidate-level screening accuracy (Scr.A);
- **stage attribution**: for every missed gold article, was it lost at
  retrieval (never surfaced) or at screening (surfaced, then wrongly
  excluded)?

## 2. License record (project convention: record before use)

| Component | Terms (verified 2026-08-18) | Our use |
|---|---|---|
| Project-authored annotations (labels, PI/ECO, gold lists) | MIT | allowed |
| PubMed metadata/abstracts in the corpus | upstream PubMed terms | academic benchmark use; no redistribution of corpus in our repo |
| Source-review excerpts, PMC-derived sections | publisher/PMC terms | not needed for the retrieval/screening axis — exclude from our pipeline inputs |
| Dataset as a whole | `other` (third-party text not relicensed) | fetch locally via HF datasets; do NOT commit corpus files to git |

Record kept in `research/ag-rdt-heidata-inventory`-style doc when the adapter
lands; nothing above is a blocker for a local, non-redistributed evaluation.

## 3. Adapter stages

1. **Fetch**: `datasets.load_dataset("THUIR/MetaSyn", "reviews")` + `"corpus"`
   via HF (proxy), pinned to the dataset revision recorded at fetch time
   (lastModified 2026-07-23 seen; pin the resolved git revision).
2. **Gold construction**: per test review, gold ids = `matched_corpus_ids`;
   exclude `source_review_corpus_ids` before any top-K truncation (dataset
   rule). Record the per-review title-match incompleteness caveat: gold
   coverage is bounded by the 67.7% test macro title-match rate — a "miss"
   against this reference includes reference-construction misses. Report
   agreement against gold, not absolute recall of the true included set.
3. **Retrieval stage**: rank the shared corpus for each review's
   PI/ECO-derived query with our open-retrieval policy (BM25 single-stage;
   the trained reranker is NOT applied — open-corpus negative contribution,
   `bm25-two-stage-results-2026-08-18.md`). Report R@K/P@K at K ∈ {50, 100,
   200} and the recall ceiling (fraction of gold ids inside BM25 top-K).
4. **Screening stage**: run our frozen-criterion screening
   (`screen_record.py` semantics) over the BM25 top-K candidates per review;
   record include/exclude per candidate. Scr.A vs MetaSyn candidate labels
   where labels exist.
5. **End-to-end**: included list = screened-in set → Inc.R/Inc.P/Inc.F1 vs
   gold.
6. **Attribution**: per missed gold id — `retrieval_loss` if absent from
   top-K; `screening_loss` if present but excluded; `reference_missing` if
   the id never matches any corpus title (reference-construction miss).
   This is the analogue of MetaSyn's post_retrieval_loss /
   conditional_retention diagnostics, implemented at stage granularity.

## 4. Configurations and gating

- Configs: the VAL-2b1 frozen ids apply only to the component-axis pilot;
  this adapter preregisters its own config set (BM25 params k1=1.5/b=0.75;
  screening criteria = the review's own inclusion/exclusion text parsed into
  frozen criterion anchors; K grid frozen above). Freeze before the first
  run, hash into the run record.
- **No tuning on MetaSyn test**: all threshold/prompt choices come from
  development evidence. The 86 test reviews stay untouched until the freeze.
- Human execution prohibited during runs (AI-only policy).

## 5. Non-comparability declaration (binding)

Our numbers on this adapter are **not directly comparable** to the MetaSyn
paper's reported numbers unless we replicate their exact evaluator, prompts,
retriever, and K conventions — which this design does not attempt. Our axis
answers a different question: "how do MetaWingman's retrieval+screening
stages behave on an external gold corpus, and where are the losses?" No
MetaSyn-vs-MetaWingman headline comparison may be published from this
adapter without replicating the original protocol.

## 6. Freeze conditions (all must hold before the first run)

1. Dataset revision pinned + license record written (§2 doc).
2. Config set + K grid + criterion-anchor extraction procedure frozen and
   hashed (run record).
3. Attribution taxonomy frozen (the three classes in §3.6).
4. Run-lock boundary for the test split created (RUN_BOUNDARY.json schema
   2.0); gold lists remain answer-sealed until all runs lock.
5. Output: per-review + macro-aggregate metrics, attribution counts, and the
   recall-ceiling caveat in every report.

## 7. Do not build

- No retraining, prompt-tuning, or BM25 parameter-tuning on the MetaSyn test
  split.
- No effect-size comparison against MetaSyn (its effect fields are strings;
  that axis stays out of scope).
