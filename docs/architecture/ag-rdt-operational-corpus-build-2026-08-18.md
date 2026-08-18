# ag-rdt Operational Corpus Build — Run Notes (2026-08-18)

> First concrete execution of VAL-1 blocker ③ ("construct a pre-update
> operational corpus that excludes later evidence") for the
> covid19-antigen-dta-living family.

## 1. Strategy provenance (all verbatim, source-located)

Extracted 2026-08-18 from PLoS Med 18(8):e1003735 + supplement S2 Text
(PLOS s016, the only authoritative strategy source):
`research/ag-rdt-search-strategy-2021.json`.

- Databases actually searched by the review: **PubMed, Web of Science Core
  Collection, bioRxiv+medRxiv (via Europe PMC), FIND website (manual)**.
  Embase/Cochrane were NOT searched (uncertainty[4]) — no fabricated
  strategies.
- **Date-window correction (critical)**: every executable date filter in S2
  Text ends 2020-12-11 (a living-review snapshot), while the article searched
  to 2021-04-30. Corpus queries therefore use **2019-12-01 .. 2021-08-31**
  (upper bound = the 2022 update cutoff, per the living-update case design).
- PubMed syntax → Europe PMC syntax translation recorded in
  `validation-output/ag-rdt-corpus/strategy-pubmed-epmc.json` (tags dropped,
  MeSH mapped to `MESH:`), with the verbatim PubMed string kept for audit.

## 2. Built so far

| Slice | Engine | Query source | Result |
|---|---|---|---|
| bioRxiv+medRxiv | Europe PMC (native EPMC syntax from S2 Text) | `strategy-preprints.json` | ✅ **5,000 records** (cap hit — more available), receipt + hashes |
| PubMed | Europe PMC (translated query) | `strategy-pubmed-epmc.json` | ⏳ background job `pwsh-4` (page-size 200, retries, max 20,000) |
| Web of Science Core | not executable locally (no WoS API access) | verbatim TS= string in strategy file | ⛔ recorded limitation |
| FIND website | manual browsing in the review | n/a | ⛔ not reconstructible from a string (uncertainty[4]) |

## 3. Coverage boundary (must travel with every downstream report)

The corpus covers **PubMed/MEDLINE + bioRxiv/medRxiv preprints** retrievable
via Europe PMC. It does NOT cover Web-of-Science-only records or FIND manual
additions; the 2022 update (194 studies) drew on the same source set, so the
corpus is a subset, not an equal, of the update's evidence base. Screening
agreement against the sealed 2022 workbook is therefore evaluated on the
covered slice only.

## 4. Next steps

1. Collect `pwsh-4` (PubMed slice) and freeze both slices' receipts.
2. Merge + dedup slices into one candidate-records JSONL with provenance.
3. Wire the corpus into the living-update case (screening stage via
   `run_screening_slice.py`, criterion anchors derived from the 2021
   publication's eligibility text).
