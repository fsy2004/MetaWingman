# VAL-2c: Human-Blind Appraisal-Domain Spot-Check — Frozen Protocol

**Status:** frozen before any independent-validation claim
**Date:** 2026-08-18
**Component:** appraisal-step domain classifier (six risk-of-bias domains:
selection / performance / detection / attrition / reporting / other)
**Tooling:** `metawingman/scripts/build_human_blind_spotcheck.py`

> **Ladder note:** this protocol is **VAL-2c** (human-blind weak-label spot-check).
> The roadmap's **VAL-2b** ("fill and freeze task manuals, scientific loss
> weights, release thresholds, configuration hashes, stopping rules") remains a
> separate, still-open item. The frozen manifest's `generation` field reads
> `val2b-human-blind-appraisal-spotcheck` because it was assigned before the
> collision was corrected; treat that string as a historical label for VAL-2c.

## 1. Why this exists

The appraisal-step candidate stream is weak-supervised: labels are produced by
deterministic rules over passage text (`build_appraisal_step_candidates.py`),
so a model trained on them can at best reproduce those rules. Before anyone
can even discuss "how well the component works", two questions must be
separated:

1. **Rule clarity:** are the deterministic labels themselves what a careful
   human would assign? (VAL-2c measures this.)
2. **Rule consistency:** does the trained component reproduce the rule labels
   on held-out passages? (the training receipt's `eval_macro_f1` measures this.)

VAL-2c is the human-blind measurement of (1). It is a spot-check, not a
clinical validation: the passages concern methods descriptions, and no claim
about any medical conclusion is being validated. This restriction is recorded
in the manifest (`claim_policy`) and is binding on every downstream report.

## 2. Population and sampling

- **Population:** all 1,974 development-split records of
  `validation-output/training-corpus/appraisal-step-candidates.jsonl`
  (the train split is excluded so the spot-check is disjoint from training
  data; the sampled set is also disjoint from any later independent eval).
- **Sample size:** n = 100.
- **Sampling:** deterministic stratified sampling by `weak_label`, seeded
  20260815. Each of the six labels gets a minimum quota of
  min(pool size, ⌈100/6⌉ = 17); remaining slots are filled from the labels
  with the largest unused pools, sorted deterministically. The exact draw is
  reproducible by re-running the script with the same seed and inputs.

## 3. Blinding and sealing

- `blind-questions.jsonl` — the ONLY file shown to the human rater. It contains
  per task: `task_id`, a fixed `instruction` (choose exactly one of the six
  domain labels from the passage text alone, no outside sources), and the
  `passage`. It contains **no** weak label, no source id, no family id.
- `answer-key.jsonl` — sealed separately (never shown during rating). It maps
  `task_id` → `weak_label` plus the source candidate/family ids for lineage.
- `manifest.json` — records n, seed, population size, per-label counts,
  SHA-256 of both files, freeze timestamp, and the claim policy. A freeze is
  **immutable by convention**: the script refuses to overwrite an existing
  freeze unless `--force` is passed, and `--force` starts a new generation
  rather than editing the old one.

## 4. Rating procedure

1. Rater reads `blind-questions.jsonl` only.
2. For each task, assign exactly one of the six domain labels.
3. No consultation of the answer key, the candidate file, or the model output.
4. Two independent raters are preferred; single-rater mode is acceptable for a
   first spot-check but must be reported as such.

**Tooling:** `metawingman/scripts/rate_blind_spotcheck.py`
- `export` writes a one-row-per-task rating sheet (TSV: task_id / label /
  flattened passage; the original passage stays in the questions JSONL).
- `score` reads the filled sheet + the sealed key and computes Cohen's kappa,
  approximate 95% CI (Fleiss SE), per-class agreement, and a confusion
  matrix — the key is never printed, only aggregate statistics.

## 5. Metrics and interpretation

- **Agreement:** Cohen's kappa (quadratic weighting is NOT used; the six
  domains are unordered categories) with 95% CI, plus per-class agreement
  (recall of each weak label against the human label) and a confusion table.
- **Interpretation bands (Landis & Koch 1977 conventions, cited for
  convention only):** kappa ≥ 0.81 near-perfect rule clarity; 0.61–0.80
  substantial; 0.41–0.60 moderate; below 0.41 → the deterministic rules do not
  match human judgment and the weak-label rules must be revised before the
  component can be reported as anything but "rule-consistent on its own
  rules".
- **No over-claiming:** even kappa = 1.0 means only "the human and the rules
  agree on domain labels of methods passages". It validates neither clinical
  content nor the trained model.

## 6. Reporting rules

Any document citing VAL-2c must: (a) cite this protocol; (b) report the
manifest SHA-256 pair so reviewers can verify the freeze; (c) report kappa
with CI and per-class counts; (d) use the claim-policy sentence verbatim when
describing what the result does and does not show.

## References

- Landis JR, Koch GG. The measurement of observer agreement for categorical
  data. Biometrics. 1977;33(1):159-174. doi:10.2307/2529310
- Cohen J. A coefficient of agreement for nominal scales. Educational and
  Psychological Measurement. 1960;20(1):37-46.
  doi:10.1177/001316446002000104
- MetaWingman component preregistration:
  `docs/architecture/appraisal-step-component-preregistration-2026-08-18.md`
