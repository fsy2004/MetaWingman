# ag-rdt Living-Update Case Design (VAL-2b2 draft, 2026-08-18)

> Status: **design draft**. This is the task-manual skeleton for the second
> reconstruction family (`covid19-antigen-dta-living`). It is NOT frozen: two
> of the three material-plan blockers are still open (see §4). Nothing here
> may be run or claimed until the freeze note at the end is satisfied.

## 1. Family and slice

| Field | Value |
|---|---|
| review_family_id | covid19-antigen-dta-living |
| published reviews | Brümmer et al., COVID-19 antigen rapid diagnostic test living systematic review (2021 first version; 2022 update) |
| supported scopes (plan) | extraction, appraisal, analysis, living_update |
| reproduction ceiling | living_update |
| cutoffs | 2021-04-30 (first version), 2021-08-31 (update) — both day-precision |
| frozen reference artifact | 2021 extraction workbook, Zenodo 4924035 revision 7, CC-BY-4.0, sha256 `8c2dfe6f4a1512994890c8346b7e2a52598d90fe84f1aed1fe5ebac3c9fb6955`, 531,709 bytes |
| 2022 reference artifact (sealed, read-only) | update workbook, heiDATA doi:10.11588/DATA/T3MIB0/FIDTR9, **CC-BY-NC-ND 4.0**, sha256 `b5683efa9fa4577179124663de3d0a3517811cbbbb71e8e53fe3c91e02647085`, 674,749 bytes |

## 2. Reconstruction task (the "living update" slice)

An AI-only run replays the **update** under the historical boundary:

1. **Operational inputs** (must contain no post-2021-08-31 evidence): the
   2021 frozen workbook (operational copy of the extraction tables) + a
   pre-update candidate corpus (records identifiable by a search executed as
   of 2021-08-31, with post-cutoff records excluded and sealed).
2. **Run**: screen the delta window (new records 2021-04-30 → 2021-08-31),
   extract/appraise newly included studies per the protocol criteria, and
   produce the updated synthesis (per-outcome pooled estimates + counts).
3. **Reference (sealed)**: the 2022 update publication's inclusion decisions,
   per-study extractions, and updated estimates. Source artifact = the 2022
   heiDATA record (inventory in flight, 2026-08-18) — see §4.

### Criterion-anchor derivation (auditable mapping contract)

The screening engine consumes criterion anchors (terms/regex per rule), not
free text. The mapping from the review's eligibility text to anchors is a
**design decision, not an automatic translation**, and must be recorded as a
derived artifact with:

- one row per anchor: rule id → source criterion (from
  `research/ag-rdt-eligibility-criteria-2021.json`, with its locator) →
  terms/regex → rationale for any simplification;
- a statement of what the anchors do NOT capture (e.g. continuous-outcome
  nuance, "any setting" clauses that are vacuously true);
- the anchors file hash-frozen before any screening run.

This mapping is reviewed before the living-update case seals; until then the
anchors are drafts.

### Screening-stage ceiling (measured in rehearsal, 2026-08-18)

Blind rehearsal over the merged corpus (12,498 candidates): OR-only draft
anchors retained 55.6%; v2 anchors (index requires accuracy + reference
co-occurrence) retain **41.9%** — still an order of magnitude above the
review's real inclusion rate (~4.5%: 133/2,990 PubMed at the 2020-12
snapshot). Conclusion, recorded as a design constraint:

**Title/abstract term anchors are a coarse prefilter (triage), not a
reproduction of the review's dual-screening decisions.** Decision-level
screening agreement for this case therefore belongs to the AI-assisted
screening arm (VAL-3), not to the deterministic engine; the deterministic
stage's deliverable is the reduced candidate set + audit trail, and its
retention rate is reported, not scored against the sealed reference.

### Deterministic-chain rehearsal (2026-08-18, same corpus)

Staged screening→extraction over the 5,244 screened-in records: abstract-level
field extraction recovered sensitivity from 17.4%, specificity from 14.7%,
and an n value from 41.5%. Interpretation recorded: these rates are measured
on the NOISY prefiltered pool (most retained records are not true accuracy
studies), so they bound abstract-level feasibility of the deterministic
chain, not the quality of true extraction. The deterministic line is triage +
audit; field-level extraction for the case requires the full-text stage
(outside the current pack) or the AI-assisted arm.

## 3. Scoring design (precommitted BEFORE the reference is sealed)

- **Inclusion delta agreement**: studies entering/leaving the included set
  between versions — exact match on study identifiers; discordance classified
  via the benchmark error classes (no de-novo adjudication).
- **Extraction agreement**: per-field agreement on newly included studies,
  with the precommitted tolerance per field type (continuous ±0.05 in natural
  units; counts exact; categorical exact).
- **Synthesis agreement**: updated pooled estimates within the same tolerance
  scheme as the sci-exercise case (pooled ±0.05, CI ±0.05, I² ±1.0 pp,
  k exact), extended per outcome.
- **Update mechanics**: did the run produce a valid living-update delta
  (version increment, changelog, re-run receipt)? Scored as process
  compliance (yes/no), not a number.
- All tolerances freeze together with the reference answers, before any
  unsealing, recorded in the case spec JSON.

## 4. Blockers and their exact resolution paths

| # | Blocker (from the material plan) | Status 2026-08-18 | Resolution path |
|---|---|---|---|
| 1 | Inventory and hash the immutable 2022 heiDATA files | ✅ **resolved** | one file, 674,749 bytes, file DOI 10.11588/DATA/T3MIB0/FIDTR9; repository MD5 `8541981cc4ec230b2a8c67e885fac4a6` verified on fetch; local SHA-256 `b5683efa9fa4577179124663de3d0a3517811cbbbb71e8e53fe3c91e02647085`; V1.0→V1.1 rename-only (same MD5/storageIdentifier), no V2 |
| 2 | Verify the later repository license | ✅ **resolved** | **CC BY-NC-ND 4.0** (both versions, termsOfUse field) — NOT CC BY: non-commercial, no derivatives → read-only reference, not redistributable; recorded in the material plan (`controlled_terms`) |
| 3 | Construct a pre-update operational corpus that excludes later evidence | ✅ **resolved 2026-08-18** | corpus built + frozen: PubMed 7,500 (native NCBI) + preprints 5,000 (cap) → merged 12,498, freeze manifest `validation-output/ag-rdt-corpus/freeze-manifest.json`; coverage boundary (no WoS/FIND) recorded |

## 5. Freeze note

This design becomes a sealed case only when: (a) the 2022 artifact is pinned
with SHA-256 and a verified-open license; (b) the pre-update operational
corpus exists and is hash-frozen; (c) the reference answers are extracted
with source locators (same standard as the sci-exercise sealed file); (d) the
case spec JSON passes `reconstruction_case.schema.json` with `status:
sealed`; (e) tolerances are frozen in the spec. Until then this document is a
plan, not a benchmark.

## 6. Reuse

- Runner: `metawingman/scripts/run_reconstruction_case.py` (the living-update
  slice adds screening/extraction stages; the extension is **preregistered**
  in `reconstruction-runner-v2-preregistration-2026-08-18.md` — frozen
  design, fixture-based acceptance, deterministic-first, no LLM arms).
- Machinery precedent: `reconstruction-first-case-results-2026-08-18.md`.
