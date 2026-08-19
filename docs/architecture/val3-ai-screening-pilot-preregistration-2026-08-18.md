# VAL-3 AI Screening Pilot — Preregistration (2026-08-18)

> Frozen design for the first AI-only screening run of the AI-only
> configuration/ablation pilot (roadmap VAL-3). Executes against the frozen
> ag-rdt operational corpus; the deterministic-line conclusion (term anchors
> are triage, decision-level screening belongs to the AI arm — recorded in
> `ag-rdt-living-update-case-design-2026-08-18.md`) makes this the decisive
> screening mechanism test.

## 1. Task

Given the verbatim eligibility criteria of the 2021 review
(`research/ag-rdt-eligibility-criteria-2021.json`), an AI run screens each
candidate record and outputs include/exclude with a quoted criterion
anchor. Configuration: single strong hosted model, prompt = the verbatim
Inclusion criteria section + the six-domain-free two exclusion rules,
C3-style (no trained verifier override in this pilot; verifier addition is
a later ablation).

## 2. Frozen sample (built after the workbook study list is mapped)

- Gold positives: every merged-corpus record whose normalized title matches
  a 2022 workbook included-study title (matching rule frozen: lowercase,
  alphanumerics only, exact match after removing bracketed citations;
  ambiguous matches resolved by longest common prefix — decision recorded
  per match).
- Negative/unlabeled pool: remaining corpus records.
- Sample: ALL gold positives (expected ~100-200) + 500 seeded
  (seed 20260815) non-gold records. Sample is hash-frozen before any run.

## 3. Metrics (frozen)

1. **Gold recall (Inc.R analogue)**: fraction of gold positives screened
   IN. Primary metric.
2. Retention rate: fraction of the full sample screened IN (reported with
   recall — never alone).
3. Abstention rate; per-record criterion anchor coverage (did the output
   quote an anchor?).
4. Cost: calls / tokens.
**No precision claim**: non-gold records are unlabeled (workbook absence
does not imply exclusion), so precision/P@1 are undefined here and must
not be reported.

## 4. Claim bounds (binding)

- Agreement with the published 2022 included-study list on the covered
  corpus slice; NOT accuracy against true inclusion; NOT human comparison.
- Repetitions: 1 for this pilot (release-eligible claims need 3 + frozen
  stopping rules per VAL-2b1).
- No tuning of prompt/thresholds on this sample; prompt hash frozen before
  the run.

## 5. Outputs

- Run record (per-record decisions + anchors + usage) + receipt.
- `docs/architecture/val3-ai-screening-pilot-results-2026-08-18.md`
  following this plan.
