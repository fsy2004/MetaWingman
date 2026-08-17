# Whole-Project Improvement Review (2026-08-17)

> Evidence-based review of what is trained, what else could be trained per
> stage, and engineering gaps. Grounded in the current code, receipts, and
> run logs — not aspirational.

## 1. What is trained today (and what it covers)

| Trained component | Covers (of the ten stages) | Status |
|---|---|---|
| section-role classification (BiomedBERT 110M) | extraction/anchoring sub-task: which workflow role a passage plays | trained; dev macro-F1 0.983 (0.670 title-stripped) |
| evidence retrieval (BiomedBERT 110M, hard negatives) | evidence anchoring sub-task: field+title → supporting passage | trained; candidate MRR 0.954 / P@1 0.919 |

Everything else — search, screening, extraction numerics, RoB, meta-analysis,
GRADE, living updates — is orchestrated by the skill (host model + deterministic
R toolkit), not trained.

## 2. Other stages with trainable narrow components (priority order)

### 2.1 Screening criteria classification (P1 slice A) — next, high value

- Task: per eligibility criterion, classify each record `met / not_met /
  unclear / not_reported` (the roadmap's `criterion_agents`).
- Data: published reviews' screening decisions exist in the benchmark
  materials (carbon-pricing screening package); weak labels = the published
  include/exclude lists mapped to criterion-level decisions.
- Recipe: identical to section-role (same base model, same freeze/export
  pipeline, same family-isolated splits).
- Risk: low (candidate + human confirmation; the skill already gates final
  inclusion/exclusion).

### 2.2 Extraction field classification (P1 slice B) — next, medium value

- Task: PICO/field-level span classification on passages (which fields a
  sentence supports), feeding `effect_recalculator`.
- Data: SCI extraction-to-analysis material + published extraction tables.
- Recipe: same Bi-encoder/sequence-classification recipe; weak labels from
  published extraction tables.
- Risk: medium (numerics stay deterministic; the model only proposes fields).

### 2.3 Lineage resolution (record→report→study→arm) — later, medium value

- Task: cluster records into studies/arms (entity resolution over records).
- Data: benchmark materials with multi-report studies; weak labels from
  published PRISMA flow + extraction tables.
- Recipe: bi-encoder similarity + deterministic union rules (mirrors
  review-family clustering).
- Risk: medium (conservative linking + human adjudication gates).

### 2.4 RoB signaling-question classification — later, high stakes

- Task: propose RoB 2 / ROBINS-I signaling answers from dossiers.
- Risk: high — final judgments stay human-signed; train only as a
  dossier-drafting assistant after a validation arm exists.

### 2.5 Topic opportunity engine — gated behind TOPIC-1..4

- Trainable temporal-graph components (TGAT/TGN-style) only after the dated
  evidence graph exists; currently design-only.

**Decision rule for the next component**: narrow classification/retrieval,
publicly derivable weak labels, human gate downstream — criterion screening
first, then extraction fields.

## 3. Engineering improvements (non-training)

1. **Export within-bucket vectorization** — the 109k-example export ran 60+
   min because the general-medicine neighborhood bucket is huge and the
   within-bucket overlap loop is still O(bucket²) per query. Replace the
   per-pair set intersection with batched numpy/ANNOY token-overlap ranking.
2. **F1 title-robustness augmentation** — add title-stripped examples to
   section-role training (0.670 → target ≥0.9 without title).
3. **F8 verifier weighting** — the hosted model overrides the trained
   verifier in C3; the full-stack design needs explicit verifier
   weighting/abstention rules instead of free-form "verify or correct".
4. **Held-out enablement** — `audit_review_families.py` exists but the
   registry schema hard-codes `held_out_ready_families: 0`; ship schema v1.1
   with confirmed-family states after the 281-edge adjudication.
5. **Independent validation arm** — 200 blind tasks (47 strata) prepared;
   requires human annotation before any gold claim.
6. **VAL-1 reconstruction cases** — licensing/cutoff resolution blocks the
   end-to-end benchmark; the preregistered C0-C3 pilot stands in as the first
   cost-quality data point only.

## 4. Data and validation gaps

- Weak labels everywhere; gold labels only via the independent arm.
- Held-out closed; all numbers are development metrics.
- Publisher authentication not established.

## 5. Priority order

1. Finish the running 12k retrain + re-evaluation (automatic on server).
2. Export vectorization (unblocks larger corpora).
3. Independent human annotation of the 200-record arm.
4. Criterion-screening component (new trainable, highest value per cost).
5. F1/F8 fixes, held-out schema v1.1, then VAL-2b/VAL-3.
