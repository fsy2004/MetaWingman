# Top-Venue Methods Scan — Integrable Ideas (2026-08-17)

> Second scan against AI top venues (ICLR/NeurIPS/AISTATS/Nature-track and
> domain journals) for methods worth blending into MetaWingman. Each entry:
> paper → target component → concrete integration → feasibility/risk.
> Companion to `methods-bibliography.md`.

## A. Process reward models / verifier engineering → full-stack verifier (fixes F8)

- Setlur et al., *Rewarding Progress: Scaling Automated Process Verifiers for
  LLM Reasoning*, ICLR 2025, [arXiv:2410.08146](https://arxiv.org/abs/2410.08146);
  *Process Reward Models That Think*, [arXiv:2504.16828](https://arxiv.org/abs/2504.16828).
- **Target**: the C3 full-stack design and the F8 finding (hosted model ignores
  the small verifier).
- **Integration**: the trained component should emit a **score with a threshold
  gate**, not a bare prediction that a hosted model may override. Train a small
  process-reward head on the same weak-label data (per-step: anchor exactness +
  field agreement) and use its score to (a) abstain below a frozen threshold,
  (b) route disagreements to humans instead of to free-form model "correction".
  This replaces "verify or correct" with "score, gate, escalate".
- **Risk**: low; same 110M recipe, one extra head.

## B. Cochrane RCT classifier evaluation paradigm → next screening component

- Thomas, McDonald, Noel-Storr, Shemilt, Elliott, Mavergames, Marshall,
  *Machine learning reduced workload with minimal risk of missing studies:
  development and evaluation of a randomized controlled trial classifier for
  Cochrane Reviews*, J Clin Epidemiol 2021,
  [doi:10.1016/j.jclinepi.2020.11.003](https://doi.org/10.1016/j.jclinepi.2020.11.003).
- **Target**: the criterion-screening component (next trainable, see
  `improvement-review-2026-08-17.md` §2.1).
- **Integration**: adopt their evaluation frame verbatim — report **workload
  reduction at a frozen near-zero missed-study rate** (recall-first), and use
  their published screening corpora as an external sanity benchmark before our
  own weak labels. This is the established precedent our component must beat
  or match, and gives reviewers a citable baseline.
- **Risk**: low; evaluation-first, then our recipe.

## C. Hybrid sparse-dense + late interaction + rerankers → retrieval component

- BGE-M3 (dense+sparse+multi-vector in one pass); ColBERTv2 late interaction;
  SPLADE learned sparse; cross-encoder rerankers — canonical references:
  [BGE-M3](https://github.com/FlagOpen/FlagEmbedding) (FlagEmbedding),
  [ColBERTv2](https://github.com/stanford-futuredata/ColBERT).
- **Target**: the evidence-retrieval component (currently [CLS] cosine).
- **Integration**: two-stage retrieve-then-rerank: our 110M bi-encoder (or a
  ColBERT-style token interaction) as stage-1 over the candidate set, plus a
  light cross-encoder reranker trained on the same hard-negative pairs. Expect
  candidate-set MRR above the current 0.954 ceiling; TF-IDF remains the frozen
  lexical baseline.
- **Risk**: medium (new training objective; keep the frozen receipt chain and
  re-verify against the same dev protocol).

## D. Conformalized abstention → conclusion-directed control

- Tayebati et al., *Learning Conformal Abstention Policies for Adaptive Risk
  Management in LLMs and VLMs*, AISTATS 2025,
  [arXiv:2502.06884](https://arxiv.org/abs/2502.06884).
- **Target**: C3's abstention and `selective_coverage` / `abstention_quality`
  metrics; the screening escalator.
- **Integration**: replace heuristic abstention with **conformal risk control**
  on a calibration split: choose the threshold so the expected critical-error
  rate is bounded at the frozen value (the pilot plan's `max_critical_error_rate`).
  This converts "when to abstain" into a provable risk-control statement —
  exactly the mechanism the contribution story's C3 needs for its stopping rule.
- **Risk**: low-medium (standard split-conformal machinery; needs a calibration
  split per review family).

## E. Research-ideation evaluation → topic opportunity engine

- Si, Yang, Hashimoto, *Can LLMs Generate Novel Research Ideas? A Large-Scale
  Human Study with 100+ NLP Researchers*, ICLR 2025,
  [ICLR proceedings](https://proceedings.iclr.cc/paper_files/paper/2025/hash/ea94957d81b1c1caf87ef5319fa6b467-Abstract-Conference.html);
  Schmidgall et al., *The Ideation–Execution Gap*, [arXiv:2506.20803](https://arxiv.org/abs/2506.20803).
- **Target**: the topic opportunity engine's value/risk gate (TOPIC-1..4).
- **Integration**: their finding — LLM ideas score high on novelty but low on
  **executability** — motivates an explicit feasibility/execution dimension in
  our frozen value-risk gate (evidence maturity, data availability, team
  capacity), separate from novelty. Their 100-researcher rubric is a template
  for the prospective registration scoring manual.
- **Risk**: low; a design/gate refinement, not new training.

## F. Verification granularity in test-time scaling → C3 compute allocation

- *Rethinking Optimal Verification Granularity for Compute-Efficient Test-Time
  Scaling* (NeurIPS 2025) — verification at the right granularity beats
  end-to-end checks at fixed budgets.
- **Target**: C3's test-time compute allocation across retrieval/full-text/
  verification.
- **Integration**: allocate verifier calls per **criterion/evidence step**, not
  per whole-document pass — mirroring our conclusion-directed acquisition but
  with a granularity knob to ablate (coarse vs fine verification).
- **Risk**: medium (needs the criterion-level reward signal from A/B above).

## Priority to blend

1. **A+B together** (verifier scoring + Cochrane evaluation frame) — they are
   the backbone of the next component and resolve F8.
2. **D** (conformal abstention) — small, high-rigor, feeds C3 metrics.
3. **C** (retrieve-rerank) — direct retrieval gain at known cost.
4. **E/F** — design refinements when the topic engine / C3 ablations start.
