# Reconstruction Runner v2 — Preregistration (2026-08-18)

> Status: **frozen design; implementation not started.** This preregistration
> is required by `ag-rdt-living-update-case-design-2026-08-18.md` §6 before
> any extension of `metawingman/scripts/run_reconstruction_case.py` beyond the
> deterministic analysis slice.

## 1. v1 capability (already landed, unchanged)

- Deterministic analysis slice: sealed xlsx → staged copy → CSV → R adapters
  → hash receipt → run-lock append/update → optional tolerance-gated scoring
  against a sealed reference, only when the boundary is fully locked.
- Evidence: first reconstruction case scored pass
  (`reconstruction-first-case-results-2026-08-18.md`).

## 2. v2 scope: staged slices for the living-update case

The ag-rdt living-update slice needs three deterministic stages before the
R analysis stage:

1. **screening stage**: candidate records (pre-update operational corpus,
   hash-frozen) → include/exclude per frozen criterion anchors derived from
   the 2021 publication's eligibility criteria. Deterministic rules first;
   every decision recorded with its criterion anchor and record id.
2. **extraction stage**: newly included records → per-field extraction into
   the frozen schema; missing/unclear cells flagged, never silently
   imputed.
3. **analysis stage**: reuse v1 (R adapters) on the extracted table to
   produce updated pooled estimates.

## 3. Frozen design elements

- **Input contract per stage**: screening takes a records JSONL
  (id, title, abstract, source, dates) + criterion-anchor JSON; extraction
  takes included ids + source texts; analysis takes the extracted table in
  the v1 CSV contract. Each input is SHA-256-frozen before the run.
- **Receipts per stage**: each stage writes its own receipt (input hash,
  output hash, rule versions, decision counts) — the same discipline as v1,
  so any stage can be audited or re-run alone.
- **Run-lock semantics**: identical to v1 — lock registered before any
  sealed read; sealed reference answers readable only when the boundary is
  fully locked; scoring per stage follows the case-design §3 tolerances
  (inclusion delta exact-match; extraction per-field tolerances;
  synthesis tolerances as in the sci-exercise case).
- **Determinism**: screening/extraction rule engines are pure functions of
  their inputs (no LLM); three repetitions must yield byte-identical
  outputs, asserted by the runner (same assertion discipline as v1's
  identical summary.csv hashes).

## 4. Explicitly NOT in v2

- No LLM execution arms (the AI-only configurations belong to the VAL-3
  pilot; v2 is deterministic-machinery rehearsal for staged slices).
- No search-stage reconstruction (ag-rdt has no frozen search export yet).
- No new scoring metrics beyond the frozen case-design §3 set.

## 5. Acceptance (precommitted)

1. Per-stage synthetic fixtures: a 30-record screening fixture with 10
   hand-labeled includes; an extraction fixture with known fields. The
   runner reproduces the fixture key exactly (rules = fixtures' source of
   truth, labeled as such).
2. Living-update dry rehearsal on the ag-rdt sealed workbooks is NOT an
   acceptance item for v2 (it requires the operational corpus, still open);
   v2 acceptance is fixture-based only.
3. All three stages emit receipts + hash chains; a tampered intermediate
   file is detected (hash mismatch aborts).

## 6. Implementation order (when started)

screening fixture + rule engine → extraction fixture + engine → runner
orchestration → acceptance runs → then (and only then) ag-rdt operational-
corpus work.
