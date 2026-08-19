# First Reconstruction Case — Results (2026-08-18)

> **What this is:** the first VAL-1-promoted reconstruction case
> (`sci-exercise-rvo2-rct-analysis`, dev split, analysis slice) ran three
> locked repetitions against the sealed published reference and scored
> `passed: true`.
> **What this is NOT:** an AI-only end-to-end reconstruction. The executed
> configuration is `deterministic-r-analysis` — MetaWingman's R pipeline on
> the frozen analysis input. The AI-only LLM pilot (VAL-3) remains open.

## 1. Case identity

| Field | Value |
|---|---|
| case_id | `sci-exercise-rvo2-rct-analysis` |
| review_family_id | spinal-cord-exercise |
| published review | Hodgkiss et al., *Exercise and aerobic capacity in individuals with spinal cord injury: A systematic review with meta-analysis and meta-regression*, PLoS Medicine 2023;20(11):e1004082, doi:10.1371/journal.pmed.1004082, PMID 38011304, PROSPERO CRD42018104342 |
| slice | RCT random-effects meta-analysis of relative peak oxygen uptake (R V̇O2peak), WMD mL/kg/min |
| frozen slice definition | `RVO2_RCT.R` @ repo `jutzca/Exercise-and-fitness-in-SCI` commit `58f690c0…` (BSD-3-Clause): `read.xlsx(RCTS_DATA.xlsx, sheet=2)` → `metafor::escalc(measure="MD")` → `rma()` (REML) → forest / Egger `regtest` |
| sealed input | `RCTS_DATA.xlsx` sha256 `a3d237bf50c7682383456723e6f84b7e34994441cd0cc2efb4627011edd2d21d` (12,452 bytes; verified on download) |
| sealed answers | `reported-estimates.sealed.json` sha256 `3d9f643dc819f7f5fc0bb83f0163bac218ef5deb704bd9aca692205004b591d5` (extracted 2026-08-18 from PMC HTML / PLOS JATS XML / S4 supplement, every value with a source locator; unreported statistics left null) |
| repetitions | 3 (`deterministic-r-analysis`, RUN_BOUNDARY schema 2.0, locks appended before any sealed read) |
| harness | `metawingman/scripts/run_reconstruction_case.py` + `schemas/reconstruction_case.schema.json` |

## 2. Scoring (precommitted tolerances, frozen before unsealing)

| metric | ours (rep-1; identical across reps) | published | tolerance | result |
|---|---|---|---|---|
| pooled MD | 2.8650 mL/kg/min | 2.9 mL/kg/min | ±0.05 | **pass** (Δ −0.035) |
| CI lower | 1.7950 | 1.8 | ±0.05 | **pass** (Δ −0.005) |
| CI upper | 3.9349 | 3.9 | ±0.05 | **pass** (Δ +0.035) |
| I² | 92.67% | 93% | ±1.0 pp | **pass** (Δ −0.33) |
| k | 16 | 16 | exact | **pass** |
| Egger p | 0.483 (z=0.721) | 0.54 (z=0.62) | significance side | **pass** (both non-significant) |
| tau² | 4.149 | not reported in article | — | reference missing (recorded, not scored) |

All three repetitions produced byte-identical outputs (same `summary.csv`
sha256 `57d71cc1…` across reps — deterministic pipeline, as expected).

## 3. Honest interpretation (claim boundary)

1. **The run-lock/sealing/scoring machinery works end to end**: locks before
   reads, hash-verified staging, sealed answers read only after 3/3 locks,
   tolerance-gated comparison, receipt with every artifact hash.
2. **The analysis module reproduces the published numbers to rounding
   precision.** Both sides use the same `metafor` REML engine, so this proves
   *material fidelity + computational reproduction*, not any model
   capability, and not that MetaWingman "performs like the authors".
3. **Not scored / not claimed:** search reconstruction (month-precision
   cutoff), screening (no labels in pack), extraction (no source PDFs),
   LLM-driven analysis decisions. All remain open for later families.
4. **Egger z differs** (0.721 vs 0.62) though both non-significant. The
   precommitted rule (significance side only) passed; the numeric difference
   is noted and would be investigated only if it ever crossed the
   significance boundary.

## 4. Artifacts

- Case spec: `research/reconstruction-cases/sci-exercise-analysis.json`
  (status `sealed`, tolerances frozen).
- Run directory: `validation-output/reconstruction-runs/sci-exercise/`
  (RUN_BOUNDARY with 3 locks, rep-1/2/3 receipts + summaries + forest +
  egger; gitignored, local-only).
- Sealed answers: `validation-output/benchmark-materials/sci-exercise-
  analysis/sealed-reference/reported-estimates.sealed.json` (local-only).
- Harness: `metawingman/scripts/run_reconstruction_case.py`.

## 5. Lessons recorded

- Sealed *input* staging (the xlsx is both input and answer-bearing) uses
  hash-verified operator staging under the lock contract; the runner
  enforces lock-before-read on its side. Documented in the audit log
  (reflection entry, this date).
- Windows subprocess encoding (GBK default) broke R output capture; fixed
  with explicit UTF-8 + errors=replace.
- Scoring mapping must follow the sealed extractor's metric names; the
  runner now implements the concrete mapping for this reference schema.
