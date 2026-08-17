# Adversarial Review — 4090 Component Training Results (2026-08-17)

> Independent adversarial audit of the first real training run, using the
> project's own seven-lens panel and finding schema
> (`metawingman/references/reviewer-and-integrity.md`). Every finding anchors
> to an artifact or measured output. Status: all critical/major findings
> acknowledged with executable corrections; none blocks the training-gate
> deliverable, all constrain its claims.

## Verified evidence base

- `section-role-execution-receipt.json`: dev macro-F1 **0.9832** (1,584 dev).
- Title-strip ablation (`mw-ablation-title.py`): 0.983 with title line, **0.670**
  without; majority-class baseline 0.046.
- Retrieval receipts (rev a positives-only / rev b hard-negatives):

| dev metric | TF-IDF | rev a | rev b |
|---|---|---|---|
| full-corpus recall@10 | 0.506 | **0.590** | 0.339 |
| full-corpus MRR | 0.375 | 0.440 | 0.200 |
| candidate-set MRR | 0.712 | 0.919 | **0.954** |
| candidate-set P@1 | 0.549 | 0.855 | **0.919** |

## Findings

### F1 — `major` — Section-role performance leans on the title line (methods lens)

- **Anchor**: title-strip ablation 0.983 → 0.670 on the same frozen dev split.
- **Problem**: the input embeds `Section title: {title}`; the classifier
  exploits it heavily. Any claim of "passage-text" role understanding is
  unsupported.
- **Consequence**: the 0.983 number overstates text-only ability; the product
  form (JATS sections carry titles, so the title IS available downstream)
  keeps the title-inclusive number legitimate for pipeline use.
- **Correction**: report both numbers; add title-stripped examples as a
  robustness augmentation in the next training revision; never claim
  text-only classification from this run.
- **Status**: acknowledged; both numbers are in the run report.

### F2 — `major` — Retrieval query revision used development feedback (Devil's Advocate)

- **Anchor**: rev 2026-08-17a was designed after observing dev recall@10 0.049.
- **Problem**: the frozen dev split informed the task definition; dev is no
  longer an untouched holdout for that design decision.
- **Consequence**: all dev numbers are development-tuned point estimates, not
  held-out evidence; held-out remains disabled (0 families, registry
  hard-codes `held_out_ready_families: 0`).
- **Correction**: label all component numbers "development"; do not cite them
  as held-out performance; the held-out gate stays closed until the family
  audit (`audit_review_families.py`) plus schema v1.1 promotion.
- **Status**: acknowledged in report wording.

### F3 — `major` — Hard negatives improve candidate ranking but degrade open-corpus retrieval (statistical/methods lens)

- **Anchor**: rev a vs rev b receipts; the direction matches prior work on
  hard negatives in NCE ([Zhang & Stratos 2021](https://arxiv.org/abs/2104.06245)):
  hard negatives concentrate mass on the top-ranked neighborhood and can hurt
  open-set generalization.
- **Consequence**: there is no single "best" checkpoint; the selection must be
  use-case bound. MetaWingman's downstream retrieval is **within-review
  candidate ranking** (given a review, locate the supporting passage), which
  the candidate-set metrics measure.
- **Correction**: select rev b for the in-review use case and rev a for any
  open-corpus use; record both receipts; encode the choice in the release
  checklist.
- **Status**: documented; selection rationale recorded.

### F4 — `minor` — Transient CUDA OOM warning during rev b training (evidence-integrity lens)

- **Anchor**: `mw-retrieval-hn.log` allocator warning (402 MB request, 321 MB
  free, cache 25.2 GB) at ~11 min; the run then completed (939 s).
- **Problem**: peak memory behavior unexplained; on a 24 GB card the 64-doc
  batches can fragment the caching allocator.
- **Consequence**: reproducibility risk only; no correctness impact observed.
- **Correction**: cap hard negatives per batch (≤3 already; optionally 2) or
  switch precision to fp16 for the retrieval run; note in the freeze doc.
- **Status**: documented; not blocking.

### F5 — `minor` — Weak labels are rule-derived; model may learn the labeling rule (methods lens)

- **Anchor**: `_section_role(title)` generates the section-role targets; the
  retrieval positives are self-anchored passages.
- **Consequence**: all metrics measure agreement with deterministic rules, not
  human gold; independent validation remains open (200-record blind sample
  prepared, `independent-validation/`).
- **Correction**: claim only "learns the frozen weak-label task"; complete the
  independent-validation arm before any gold claim.
- **Status**: acknowledged.

### F6 — `critical` — End-to-end benchmark claims would be unsupported (contribution lens)

- **Anchor**: `ai-only-evaluation-plan.template.json` is all
  `replace-before-freeze`; no reconstruction case is promoted (VAL-1); the
  pilot preregistration freezes only the design.
- **Problem**: any paper-level claim of system performance, superiority, or
  validation from the current artifacts would violate the project's claim
  ladder.
- **Consequence**: **blocks any manuscript claim** beyond "implemented
  components trained on weak labels; development metrics reported".
- **Correction**: run the frozen pilot (C0 first) after budget approval;
  resolve VAL-1 cases; keep the claim ceiling at
  `implemented_not_scientifically_validated`.
- **Status**: open by design; documented in the report.

### F7 — `observation` — Receipt traceability verified (lineage lens)

- **Anchor**: every number above maps to a receipt, log, or script output
  archived under `validation-output/server-download/`; job manifests pin
  hashes; preflights archived.
- **Status**: positive confirmation; no action.

## Synthesis

What survives adversarial review:

- The **training gate is complete and reproducible**: 2,048-record corpus
  (all verified not retracted), 15,136 weak examples, 30,272 family-isolated
  pairs, two trained components with hashed receipts.
- Two **real scientific findings** with external literature support:
  (1) retrieval queries need record context (ill-posed otherwise; +11×
  recall@10 after fix); (2) hard negatives trade open-corpus recall for
  candidate precision ([Zhang & Stratos 2021](https://arxiv.org/abs/2104.06245)).
- The section-role number is title-assisted; the honest range is 0.670–0.983.

What must NOT be claimed: held-out performance, gold-label agreement, human
superiority, or end-to-end system validation. The next evidence gate is the
independent human validation arm (200 records, 47 strata, prepared) and the
preregistered AI-only pilot (C0 pending budget approval).
