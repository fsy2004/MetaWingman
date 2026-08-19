# VAL-1 Promotion Analysis (2026-08-18)

> Purpose: replace the roadmap's "promotion therefore remains open" with a
> per-family decision and a concrete first promotion. All facts below come
> from the five immutable material plans in `research/benchmark-material-plans/`
> and the local fetch receipts in `validation-output/benchmark-materials/`.

## 1. Per-family status

| Family | Plan status | License | Answer-bearing artifact | Verdict |
|---|---|---|---|---|
| sci-exercise-analysis (spinal-cord-exercise) | development_ready | BSD-3-Clause verified | `RCTS_DATA.xlsx` sealed, hash `a3d237bf…` | **Promotion-eligible: analysis slice** |
| bmj-covid-therapies-methods (covid19-living-nma) | development_ready | MIT verified | none public (no article-specific dataset) | Guard test only; not a reconstruction |
| ag-rdt-living-update (covid19-antigen-dta-living) | reference_only | CC-BY-4.0 (2021) verified; 2022 heiDATA unverified | 2021 workbook sealed, hash `8c2dfe6f…` | Blocked: heiDATA inventory + pre-update corpus |
| hepsanet-controlled-ipd | development_ready | MIT verified | none (IPD controlled) | Guard test only by design |
| carbon-pricing-screening | blocked | NOASSERTION | screening_data.csv, metadata-only | Blocked: license + cutoff |

## 2. Decision: promote sci-exercise-analysis first

The five families were never equally close. `sci-exercise-analysis` has the
complete promotion prerequisites for a **development-split, analysis-only**
reconstruction slice:

1. **Fully verified license** (BSD-3-Clause, repository pin `58f690c0…`).
2. **Frozen operational input**: `RVO2_RCT.R` (fetched, hash
   `e10b9f73…`) defines the exact slice deterministically:
   `read.xlsx(RCTS_DATA.xlsx, sheet=2)` → `metafor::escalc(measure="MD")` →
   `rma()` random-effects → forest / Egger `regtest` / funnel.
3. **Frozen sealed analysis input**: `RCTS_DATA.xlsx` (hash `a3d237bf…`,
   12,452 bytes), retrieval policy `requires_run_lock`.
4. **Cutoff**: 2023-03 (month precision). This blocks only a day-level
   *search* reconstruction, which is outside this plan's supported scopes
   (`extraction`, `analysis`) and its `reproduction_ceiling`
   (`extraction_to_analysis`). It does not block the analysis slice.

### What the slice is NOT

- It is **not** a screening reconstruction (the plan records "no screening
  labels are present").
- It is **not** an extraction reconstruction (no source PDFs in the pack).
- It is **not** a test-split case: this first promotion is assigned to the
  **dev** split (`review_family_id` granularity), consistent with the
  benchmark split rule ("never tune on the test family"; this family is the
  first end-to-end rehearsal of the run-lock/sealing machinery).

## 3. Case definition (VAL-2b2 draft for this family)

- **Task**: given the sealed `RCTS_DATA.xlsx` sheet 2 (unsealed only after
  the run lock), compute with MetaWingman's R analysis module: per-study MD,
  pooled random-effects MD + 95% CI, tau², I², Z/p, and Egger's regression
  test for the RVO2 RCT meta-analysis.
- **Reference**: the published article's reported values, collected with
  source locators into a sealed answer file (extraction in flight, 2026-08-18;
  draft at `validation-output/benchmark-materials/sci-exercise-analysis/
  sealed-reference/reported-estimates.draft.json`).
- **Scoring (proposed, frozen at run lock)**: numerical equivalence with
  precommitted tolerances — pooled MD ±0.05 mL/kg/min; CI bounds ±0.05;
  I² ±1.0 percentage point; tau² ±0.05; Egger p agreement on the
  significance side only. Rationale: REML optimizers differ in convergence
  digits; tolerances must be fixed before unsealing, and the comparison is
  "agreement with published expert reference", never "who is more correct".
- **Configuration**: AI-only run of the pipeline's analysis stage
  (configuration ids per the VAL-2b1 frozen plan); 3 repetitions;
  human execution prohibited.
- **Run lock**: `RUN_BOUNDARY.json` complete for every preregistered
  repetition before `RCTS_DATA.xlsx` or the answer file is read.
- **Harness (landed 2026-08-18)**: `metawingman/scripts/run_reconstruction_case.py`
  + `metawingman/schemas/reconstruction_case.schema.json` + case spec
  `research/reconstruction-cases/sci-exercise-analysis.json`. Smoke-tested
  locally with a synthetic sealed xlsx: lock-before-read contract enforced,
  output hashes in receipt, sealed file unmodified, R summary/egger calls
  succeed. Scoring stays disabled until the sealed answer file lands
  (extraction in flight) and all three repetitions lock.

## 4. Other families — concrete next actions

1. **ag-rdt-living-update**: inventory + hash the immutable 2022 heiDATA
   files and verify their license (Zenodo/heiDATA record review). Then build
   the pre-update operational corpus. Blocked on network inventory work only.
2. **carbon-pricing-screening**: two non-technical blockers (reuse terms,
   exact cutoff). Options: contact the authors for explicit terms, or drop
   the family. No local action can resolve it; record as waiting.
3. **bmj-covid-therapies-methods**: keep as a code-level guard test (NMA
   functions execute under our environment), not a reconstruction.
4. **hepsanet-controlled-ipd**: keep as controlled-data workflow guard
   (JAGS model syntax compiles; access policy test).

## 5. Effect on the roadmap

- VAL-1 changes from "promotion therefore remains open" to **"first
  promotion drafted: sci-exercise-analysis (dev split, analysis slice);
  three families blocked/guard-only; one family pending inventory"**.
- VAL-2b2 for this family is drafted here (§3); VAL-2b2 for the remaining
  families stays open.
- VAL-3 remains open until the dev-split run executes end to end.
