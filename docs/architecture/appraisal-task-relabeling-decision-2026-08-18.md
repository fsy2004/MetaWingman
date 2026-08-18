# Appraisal-Task Relabeling Decision (2026-08-18)

> Data-driven pivot after the VAL-2c verdict (kappa 0.311) and rule
> calibration (best variant 0.313). Binding on the appraisal component line.

## 1. Calibration evidence

Four rule variants were scored against the same 100-item rating sheet:
v1 0.311, v2a strong-signals 0.313, v2b tool-demotion 0.264, v2c
judgement-required 0.289. The dominant divergence is distributional: the
rubric assigns 58% of passages to `other` (multi-domain overviews, tool
introductions, GRADE/certainty content), while keyword rules force a
specific domain onto most of them. No keyword threshold closes this gap.

## 2. Decision

1. **Stop rule-based relabeling for this task.** The deterministic keyword
   rules have a measured ceiling of ≈0.3 kappa against rubric judgment.
2. **Adopt rubric-supervised labels**: the completed 100-item rating sheet
   is the seed gold set; scale it to a training-sized rubric-labeled sample
   (target ≈800 dev passages) using the same six-domain rubric and the same
   rating procedure.
3. **Retrain the appraisal component on rubric labels** (server; this
   replaces the deferred V4). The component's ceiling claim changes from
   "rule-consistency" to "rubric-consistency" — still NOT independent
   validation and NOT human-vs-model agreement; claim bounds unchanged in
   kind.
4. **Freeze a new VAL-2c generation** (fresh 100-item sample, different
   seed) for validation after retraining; the old generation and its kappa
   0.311 remain frozen as the rule-era record.

## 3. Execution sequence

1. Server: sample ≈800 dev appraisal candidates (exclude the 100 already
   rated), export locally with SHA-256.
2. Rubric-rate the sample (batched, same rubric and procedure as the
   original sheet; ratings are judgment labels, provenance recorded only in
   the private audit log per project policy).
3. Train on rubric labels (server job, same trainer with rubric-label
   mapping; receipt + hashes).
4. Validate: rubric-consistency on a held-out rubric-rated slice + new
   VAL-2c generation.
