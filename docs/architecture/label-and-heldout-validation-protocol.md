# Label & Held-out Validation Protocol

> Closes the two remaining scientific gaps before any training claim:
> (1) weak labels are not independently validated, and (2) no review family is
> held-out-ready. Neither gap can be closed by a model response or by silent
> automation; both need an explicit, pre-registered human arm plus deterministic
> machinery. This document is the frozen protocol for that arm.

## Current measured state (re-run 2026-08-16)

- Family registry: 4,098 records → 3,876 families. 56 candidate families,
  281 candidate edges, 296 integrity-blocked families, 0 held-out-ready.
- v2 biomedical plan: 2,048 records (1,620 train / 428 development / 0 held-out),
  2,040 family keys, every record
  `provisional_family_isolated_not_held_out`.
- Annotation verification (`verify_training_annotations.py`):
  - v1 run: `valid`, 1 exact-anchored annotation, 2 abstained.
  - v2 run: `invalid`, 2 non-exact excerpts (PMC9533950 `risk_of_bias` and
    `synthesis_method`), 6 exact-anchored. Acceptance boundary remains
    `exact_anchor_verified_but_not_independently_validated_not_gold`.

## Part A — Independent label validation

Goal: turn a sample of deterministic/model weak labels into independently
validated gold labels, and measure the weak-label error rate.

1. **Freeze the sampling frame** before drawing: strata =
   `primary_specialty × question_type × study_design × synthesis_route`,
   proportional to the v2 plan. Target ≥ 200 records drawn across ≥ 20 strata.
2. **Independent annotator**: a human (not the model, not the author of the weak
   labels) reads the full text and re-labels specialty / question type /
   section role / evidence anchors. Seed and draw order are recorded.
3. **Blindness**: the annotator sees source text, not the weak label or the model
   candidate, until after their own label is committed.
4. **Agreement**: report raw agreement + Cohen's kappa per field. A field with
   kappa < 0.8 does not promote to gold.
5. **Gold promotion**: only exact-source-anchored labels that the independent
   annotator confirms become gold. Everything else stays
   `candidate_hard_negative_not_gold` / `deterministic_weak_candidate`.
6. **Critical false exclusion**: count strata where the weak label would have
   routed a review to the wrong specialty/profile; these feed the AI-only
   benchmark's `critical_false_exclusion` metric.

Tooling: `prepare_training_annotation_tasks.py` (task export),
`verify_training_annotations.py` (exact-anchor gate). The two v2 non-exact
excerpts above must be repaired or rejected before any v2 example is frozen.

## Part B — Review-family held-out audit

Goal: promote confirmed multi-record families so a family-isolated held-out
split can be enabled without leakage.

1. **Edge adjudication**: a human confirms or rejects each of the 281 candidate
   edges against title / DOI / authors / full text. Rules to confirm:
   `exact_normalized_title` (same review re-issued), `high_title_overlap`, or
   `author_supported_overlap` — each confirmed individually, never by majority.
2. **Recompute components** from the confirmed edges; a family is
   `confirmed` only when every pair in it was individually confirmed.
3. **Integrity re-check**: any member with `hold_integrity_review` or
   `exclude_retracted` keeps the family `blocked_integrity`.
4. **Held-out enablement**: a family enters the held-out candidate set only when
   (a) it is confirmed, (b) it has ≥ 2 records, and (c) it is assigned by the
   `family_hash_80_10_10` split. Held-out stays **disabled** until the family
   and temporal audits pass and the user re-enables it.
5. **Leakage guard**: no confirmed family may span train/development/test; the
   registry's `split_status` flips from `blocked_pending_family_audit` to a
   verified assignment only through this audit.

Tooling today: `cluster_review_families.py` produces `candidate_edges` with
`status: requires_audit` and hardcodes `held_out_ready_families: 0`. A
deterministic `audit_review_families.py` (read confirmations, recompute
families, emit held-out candidates) is the next implementation step and is
listed in the master plan.

## Acceptance boundary

Completing this protocol raises labels to gold and families to held-out-ready;
it does **not** by itself produce a training performance result, a benchmark
score, or a human-superiority claim. Those remain gated on server execution and
the AI-only benchmark at matched cost.
