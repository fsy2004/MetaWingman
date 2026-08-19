# VAL-2c Scoring Result (2026-08-18)

> Scored with `metawingman/scripts/rate_blind_spotcheck.py` against the
> sealed answer key after the rating sheet was completed. Interpretation
> follows the frozen protocol
> (`appraisal-human-blind-spotcheck-protocol-2026-08-18.md`).

## Result

- n = 100 (full coverage); Cohen's **kappa 0.311**, 95% CI 0.191–0.431
  (Fleiss SE, normal approximation); raw agreement 44.0%.
- Per-class agreement (rating vs sealed weak labels):

| domain | reference n | agreed | agreement |
|---|---|---|---|
| other | 21 | 18 | 0.857 |
| performance_bias | 13 | 8 | 0.615 |
| detection_bias | 17 | 10 | 0.588 |
| attrition_bias | 17 | 4 | 0.235 |
| selection_bias | 17 | 3 | 0.176 |
| reporting_bias | 15 | 1 | 0.067 |

- Rating distribution: other 58, performance 13, detection 13, selection 6,
  attrition 6, reporting 4 — versus the key's other 21. The largest
  systematic divergence: passages the rubric reads as tool/process
  descriptions or overall multi-domain summaries are labeled specific
  domains by the deterministic rules.

## Protocol-mandated decision

Per protocol §5: kappa < 0.41 ⇒ **the deterministic weak-label rules do not
match rubric-grounded judgment on the appraisal-domain task; the rules must
be revised before the component can be reported as anything but
rule-consistent on its own rules.** The current generation stays frozen
(immutability), a new generation will be frozen after rule revision.

## Consequence for the training line

The appraisal component's dev macro-F1 0.8500 exceeds this rule-clarity
kappa (0.311): the model reproduces rules whose own rubric agreement is
low. Therefore **V4 (larger model / more epochs) is deferred** — it would
chase a ceiling that is not the target; the next action is rule revision in
`build_appraisal_step_candidates.py`, then re-training against the revised
rules and a new VAL-2c generation.

## Files

- ratings: `validation-output/independent-validation/human-blind-
  appraisal-spotcheck/rating-sheet.tsv` (100 rows, six-label vocabulary)
- report: `kappa-report.json` (same directory)
- decision record: this document; whitepaper §8 row + roadmap updated
  accordingly.
