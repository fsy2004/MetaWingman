# Second Reconstruction Case — ag-rdt Pooled Sensitivity Slice (2026-08-18)

> Deterministic analysis slice on the COVID-19 Ag-RDT living-update family
> (Brümmer et al., PLoS Med 2021 e1003735 / 2022 e1004011). The second
> scored reconstruction case after `reconstruction-first-case-results`.

## Case identity

| Field | Value |
|---|---|
| case_id | `ag-rdt-pooled-sensitivity-slice` |
| review_family_id | covid19-antigen-dta-living |
| reference | Brümmer et al., PLoS Med 2022;19(5):e1004011 overall pooled estimates (verified with locators, `research/ag-rdt-2022-pooled-estimates.json`): sensitivity 72.0% (69.8–74.2), specificity 98.9% (98.6–99.1); 194 studies / 221,878 Ag-RDTs |
| sealed input (local staging) | `agrdt-2x2-study.csv` sha256 `20fcabed…` — 185 studies with complete 2×2 (from the 2022 heiDATA workbook, CC BY-NC-ND 4.0, read-only; derived input never redistributed) |
| slice definition | study-level 2×2 → mada bivariate (Reitsma) pooled sensitivity/specificity (`run_diagnostic.R --analysis sroc_summary`, new adapter leaf that skips the degenerate-data SROC figure/AUC) |
| exclusions (precommitted, model constraints) | ≥3 zero cells OR undefined rates (TP+FN=0 or FP+TN=0): f104, f118, f189, f193 → 185 of 194 studies; the workbook itself lacks complete 2×2 for 5 of 194 |
| repetitions | 3 locked (`deterministic-r-analysis`, RUN_BOUNDARY schema 2.0) |

## Scoring (precommitted tolerances, frozen before unsealing)

| metric | ours (mada Reitsma) | published | Δ (pp) | tolerance | result |
|---|---|---|---|---|---|
| pooled sensitivity | 72.73% | 72.0% | +0.73 | ±2.0 | **pass** |
| pooled specificity | 99.09% | 98.9% | +0.19 | ±2.0 | **pass** |

Rep-3 receipt: `scored: true, passed: true`; three runs byte-identical
outputs (deterministic pipeline).

## Honest interpretation

1. The deterministic diagnostic-meta module reproduces the published
   overall pooled estimates within the precommitted ±2 pp on 185 of 194
   studies. The 9-study gap (5 without complete 2×2 + 4 excluded by model
   constraints) and the model-family difference (mada Reitsma vs the
   authors' approach) are covered by the tolerance and stated here.
2. Same-engine-family caveat applies as in the first case: this validates
   pipeline mechanics on a second, different family (diagnostic test
   accuracy, not pairwise MD), not model capability.
3. The IFU-subgroup value (76.3%, 73.7–78.7) is NOT the overall estimate
   and was correctly avoided as the comparison target (recorded in the
   reference JSON's uncertainty).
4. The workbook is a read-only reference under CC BY-NC-ND 4.0; only
   aggregate statistics appear in this document and the run receipts.

## Artifacts

- Case spec (sealed): `research/reconstruction-cases/ag-rdt-pooled-
  sensitivity-slice.json`
- Run dir: `validation-output/ag-rdt-corpus/recon-runs/` (boundary 3/3
  locks; rep-1/2/3 receipts + `sroc_summary.csv`)
- Reference: `research/ag-rdt-2022-pooled-estimates.json`
- Inputs: `validation-output/ag-rdt-corpus/case-input/` (study-level +
  study×brand)
- Runner extensions: CSV input branch, per-case generic scoring
  (`reference_path` + `scale`), `run_diagnostic.R` `sroc_summary` leaf;
  schema extended (`scoring` object).
