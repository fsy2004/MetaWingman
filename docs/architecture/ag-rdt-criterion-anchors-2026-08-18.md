# ag-rdt Criterion Anchors — Auditable Mapping (draft, 2026-08-18)

> Status: **draft until reviewed** (contract in
> `ag-rdt-living-update-case-design-2026-08-18.md`: the mapping is a design
> decision, never an automatic translation). Anchors file:
> `metawingman/fixtures/reconstruction-v2/ag-rdt-criterion-anchors.draft.json`.

## 1. Mapping table (rule → source criterion → simplification)

| Anchor rule | Source criterion (locator) | Simplification rationale |
|---|---|---|
| inc-index-agrdt | #1+#7 commercial Ag-RDT index test (Methods para 1; S1 Text Index test) | "Commercial/POC" not detectable from title/abstract terms |
| inc-accuracy-eval | #1 accuracy evaluation (Methods para 1) | accuracy phrasing proxies the reference-standard requirement |
| inc-reference-standard | #1 RT-PCR or cell culture (Methods para 1) | term proxy; Ag-RDT-vs-Ag-RDT studies not excluded at this stage |
| inc-design | #3 designs (Methods para 1) | design terms from title/abstract only |
| exc-quarantine-monitoring | #1-excl testing for monitoring/ending quarantine (para 2) | exact purpose phrases only; bare "surveillance" deliberately omitted (over-exclusion risk) |
| exc-tiny-sample | #2-excl population <10 (para 2) | **partial**: only explicit small-n statements; silent small samples not captured |

## 2. Criteria deliberately NOT captured (vacuous or stage-level)

- population "any age / symptoms / location" (#2 incl) — no filter, nothing to anchor;
- "peer-reviewed + preprints both" (#4 incl) — no filter;
- "no language restrictions" (#5 incl) — no filter;
- meta-analysis eligibility "clinical vs spiked samples" (#6 incl) — a
  meta-analysis-stage distinction, not a screening filter;
- protocol-layer variants (S1 Text wording differences, uncertainty[3]) — the
  body text is authoritative; differences recorded, not anchored.

## 3. Sanity check performed

Three synthetic records (typical accuracy study / quarantine-monitoring study
/ n=8 study) screened with these anchors: include / exclude (exc-quarantine) /
exclude (exc-tiny-sample) as expected (run log in validation-output).

## 4. Review gate

- (a) line-by-line re-check against
  `research/ag-rdt-eligibility-criteria-2021.json` — **done 2026-08-18**;
- (b) 2021-10-13 correction (PLoS Med 18(10):e1003825) — **checked: NOT
  eligibility-relevant** (Author Summary sensitivity number only; see
  `research/ag-rdt-correction-e1003825-2026-08-18.md`);
- (c) anchors frozen — `ag-rdt-criterion-anchors.frozen.json` (sha256 below),
  recorded in the case spec at sealing time.

Frozen anchors sha256: computed at freeze time (see file metadata in git).
