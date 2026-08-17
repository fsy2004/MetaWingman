# Top-Journal Five-Figure Evidence Checklist

> Maps the contribution story's five required evaluation figures
> (`top-journal-contribution-story.md`, "Evaluation Figures Before Prose") to
> evidence we now have versus evidence still needed. Updated 2026-08-17 after
> the first real training run, the four-configuration pilot, and the 6.6×
> corpus expansion.

## Figure 1 — Temporal evidence landscape → topic portfolio → protocol → living claim

- **Have**: typed lifecycle state (P0 schemas), the 4,098→27,046-record corpus
  with year/journals/strata, the frozen biomedical plan pipeline, provenance
  graph + living-update fixtures (P3 tests).
- **Missing**: the dated multidisciplinary graph (TOPIC-1) does not exist yet —
  no temporal edges between primary studies/reviews/guidelines. This figure is
  currently a schematic; it needs the TGAT/TGN-style graph (see
  `methods-bibliography.md` §4) before it can be drawn from real edges.

## Figure 2 — Historical Top-K topic rediscovery + false-opportunity controls

- **Have**: 15-target registry (3 with publisher-verified cutoffs),
  `evaluate_topic_rediscovery.py` scoring, sealed-boundary fixtures.
- **Missing**: promoted leakage-audited cases (TOPIC-2), baseline comparisons
  (TOPIC-3), prospective registration (TOPIC-4). Not yet evidence-backed.

## Figure 3 — Lifecycle/profile/validation coverage map

- **Have**: machine-audited coverage matrix (10 stages, 21 profiles, 19
  routes, validation levels), `audit_system_coverage.py` +
  `audit_biomedical_coverage.py` outputs, claim ceiling
  `implemented_not_scientifically_validated`. This figure can be drawn TODAY
  from real audit JSON.

## Figure 4 — End-to-end stage-loss and causal propagation waterfall

- **Have**: component-level dev numbers only (section-role F1 0.983 / 0.670
  title-stripped; retrieval MRR 0.954 candidate / 0.590 full-corpus rev a);
  counterfactual protocol replay fixtures (VAL-4a).
- **Missing**: real-review reconstruction cases (VAL-1 blocked on licensing /
  cutoff resolution), therefore no end-to-end waterfall. Cannot be drawn yet.

## Figure 5 — Risk-coverage-cost frontiers and ablations

- **Have (partial)**: the four-configuration pilot is the first real
  cost-quality data point: trained components (0 API cost) beat C0–C3 hosted
  configs (400 calls / ~1M tokens each) on both tasks; hard-negative revision
  trade-off (candidate MRR ↑, open-corpus recall ↓) is a real frontier point.
- **Missing**: conclusion-directed acquisition ablations (VAL-5: fixed Top-K,
  linear pipeline, confidence-only routing) and repeated runs with confidence
  intervals. The pilot is single-repetition.

## Bottom line

Figures 3 and (a first cut of) 5 are now evidence-backed; figures 1, 2, 4
remain design targets. The paper claim ladder stays at
"implemented components trained on weak labels; development metrics reported"
until the missing evidence is produced.
