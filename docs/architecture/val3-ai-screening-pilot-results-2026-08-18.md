# VAL-3 AI Screening Pilot — Results (2026-08-18)

> Executed per `val3-ai-screening-pilot-preregistration-2026-08-18.md`.
> First AI-only screening run of the AI-only configuration/ablation pilot.

## Run

- Sample: 649 frozen records (149 gold = merged-corpus matches of the 2022
  workbook's 194 included studies; 500 seeded non-gold), sample sha256
  `f8b9c53c…`.
- Configuration: single hosted model (DeepSeek), prompt = verbatim
  eligibility criteria (Inclusion criteria section) + JSON decision
  schema; 1 repair retry then abstain; 649 calls, resume-friendly runner.
- Reference: the published 2022 included-study list (sealed workbook,
  used only for scoring).

## Results

| Metric | Value |
|---|---|
| decision distribution | include 126 / exclude 482 / abstain 41 |
| **gold recall (Inc.R analogue)** | **0.7651** (114/149) |
| gold excluded by the AI | 9 |
| gold abstained (title/abstract insufficient) | 26 |
| retention rate (full sample) | 0.1941 |

## Interpretation (claim bounds verbatim)

- Gold recall measures agreement with the published 2022 included-study
  list on the **covered corpus slice** (149/194 matched; 45 unmatched are
  WoS/FIND-coverage losses, not screening losses).
- The dominant recall loss is **abstention** (26/149 gold, 17.4%), not
  wrong exclusion (9). This is the designed behavior of the abstain path
  and points to full-text retrieval as the next lever, not prompt tuning.
- Retention 19.4% versus the deterministic anchors' 42% retention
  (different sample) — consistent with the AI arm being a decision-grade
  filter rather than a term prefilter.
- **No precision claim**: non-gold records are unlabeled (workbook absence
  does not imply exclusion).
- No human comparison; weak-label-free but reference-limited measurement.

## Next steps

1. Repetitions 2-3 (release-eligible reliability needs 3 reps per
   VAL-2b1).
2. Full-text stage feasibility for the 26 abstained gold records.
3. Verifier-override ablation (C3-style) as the next configuration.
