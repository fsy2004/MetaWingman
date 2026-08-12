# AI reviewer panel and integrity audit

## Independent review lenses

1. **Journal-fit/contribution reviewer**: decision relevance, novelty relative to current reviews, audience, and fit.
2. **Systematic-review methods reviewer**: protocol fidelity, search completeness, dual processes, reporting guideline, deviations, and certainty.
3. **Statistical/estimand reviewer**: effect construction, dependency, model assumptions, heterogeneity, multiplicity, robustness, and reproducibility.
4. **Domain/clinical reviewer**: clinical compatibility, outcome meaning, applicability, harms, and practice implications.
5. **Evidence-integrity reviewer**: citation identity, claim support, retractions/corrections, full-text anchors, and contradictory evidence.
6. **Data-lineage reviewer**: record-report-study-result mapping, duplicate cohorts, shared controls, follow-ups, and frozen-data trace.
7. **Devil's Advocate**: strongest alternative explanation, missing evidence, boundary cases, and conclusion that would change under plausible assumptions.

Review independently, then synthesize. Overlap is corroboration; do not ask reviewers to suppress it.

## Finding schema

Each finding must contain:

- `finding_id` and reviewer lens;
- severity: `critical`, `major`, `minor`, or `observation`;
- exact artifact and evidence anchor;
- problem and violated principle;
- consequence for validity, interpretation, reproducibility, or reporting;
- executable correction and verification test;
- status and responsible owner.

Critical means a core conclusion may be invalid, evidence may be fabricated/misattributed, or scientific completion is falsely claimed. Critical findings block release until resolved or explicitly acknowledged with the affected conclusion removed/downgraded.

## Revision verification

Use three gates:

1. Freeze the original finding and acceptance criterion before viewing the response letter.
2. Compare original and revised manuscript/data/code directly and assign `resolved`, `partly resolved`, `unresolved`, `made worse`, or `indeterminate`.
3. Read the response letter only after the evidence verdict; check whether its claim matches the observed change.

Maintain `finding -> response -> patch/diff -> changed output -> verification` traceability. A polished explanation does not resolve an unchanged artifact.

## Final integrity checks

- all citations verified and linked to claims;
- all counts reconcile across raw exports, deduplication, screening, PRISMA, tables, and text;
- all included studies/results map to extraction and appraisal;
- all analysis rows are frozen and hashed;
- clean rerun reproduces tables and figures;
- manuscript numbers match generated outputs;
- conclusions match certainty and sensitivity analyses;
- data/code/access and AI-use disclosures are accurate;
- unresolved limitations and missing source coverage are visible.
