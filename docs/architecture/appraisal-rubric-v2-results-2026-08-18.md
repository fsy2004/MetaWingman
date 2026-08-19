# Appraisal Component — Rubric V2 Results (2026-08-18)

> Final record of the appraisal-domain line after the VAL-2c-triggered
> pivot (`appraisal-task-relabeling-decision-2026-08-18.md`). All numbers
> are consistency measurements against rubric-grounded labels — NOT
> scientific validation, NOT human-vs-model agreement.

## 1. Timeline of the line

| Era | Training labels | Result |
|---|---|---|
| Rule-era V3 | deterministic keywords (9,906 candidates) | dev macro-F1 0.8500 (rule-consistency) |
| VAL-2c verdict | 100-item rubric-grounded sheet | kappa 0.311 (0.191–0.431) → rules do not match rubric judgment |
| Rule calibration | 4 variants vs the same sheet | best 0.313 → keyword ceiling ≈0.31; pivot to rubric labels |
| Rubric V1 | 800 rubric labels (96.6% other) | dev macro-F1 0.1929 (thin-domain baseline) |
| **Rubric V2** | **9,906 rubric labels** (train 7,932 / dev 1,974) | dev macro-F1 **0.3777**, eval loss 0.5789 |

Final label distribution (9,906): other 8,443; selection 617; reporting
488; performance 145; attrition 112; detection 101. Train ratings used the
scripted rubric procedure; dev ratings used the subagent procedure — the
procedures differ measurably (train 14.8% domain vs dev 3.5% domain), which
is itself recorded as a rating-procedure variance finding and bounds the
dev metrics.

## 2. Generation-2 spot-check (frozen)

100 new items (seed 20260816, gen-1 candidates excluded), key = rubric
labels (questions `f385d309…`, key `f568c9e4…`). Rubric V2 predictions:
raw agreement 0.80, weighted-F1 0.871, macro-F1 0.170, **kappa 0.068
(95% CI −0.297 to 0.433)** — the gen-2 key is 98% `other` (2 domain
items), so kappa is statistically uninformative for domain
discrimination; recorded for completeness, not interpreted as a band
verdict.

## 3. Conclusions (bound by the evidence)

1. Rubric supervision improved dev macro-F1 from 0.193 (thin data) to
   0.378 (full 9,906) — a real, receipt-verified gain, still far from the
   rule-era 0.85 because rubric labels encode a different, harder task
   (multi-domain passages → other).
2. The component now reproduces rubric-style judgment at weighted-F1 0.87
   (dev) / 0.87 (gen-2) — usable as a **prefilter and abstention trigger**
   inside the verification chain, with the honest ceiling documented.
3. Open items (recorded, not hidden): rating-procedure harmonization,
   a third rating wave for cross-procedure agreement, and any
   domain-discrimination claim requiring a richer domain-positive sample.

## 4. Artifacts

- Training receipt: `validation-output/training-runs/appraisal-rubric-v2/
  execution-receipt.json` (checkpoint hashes inside).
- Candidates: `appraisal-rubric-final-candidates.jsonl` sha256
  `e96cc29e…`.
- Gen-2 freeze + scoring: `validation-output/independent-validation/
  human-blind-appraisal-spotcheck-gen2/` + the numbers above.
