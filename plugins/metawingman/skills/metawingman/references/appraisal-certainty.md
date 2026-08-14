# Risk of bias, reporting bias, and certainty

## Match tool to evidence

| Evidence | Preferred approach |
|---|---|
| Individually randomized parallel RCT | RoB 2 current individually randomized version, per result |
| Cluster or crossover RCT | corresponding RoB 2 variant |
| Non-randomized intervention | ROBINS-I 2016 formal version or explicitly named draft, with target trial and confounding plan |
| Non-randomized exposure | ROBINS-E current version or justified design-specific tool |
| Diagnostic accuracy | QUADAS-3 current recommended release; record the exact version |
| Prediction model | PROBAST+AI; distinguish development quality from performance-evaluation RoB |
| Prognostic factor | QUIPS or justified current instrument |
| Prevalence | JBI prevalence tool or justified equivalent |
| Qualitative / economic / mixed evidence | JBI or method-specific appraisal |
| Systematic review in an overview | ROBIS for bias; AMSTAR 2 or profile-specific AMSTAR-PF for methodology where applicable |
| Measurement instrument | COSMIN risk-of-bias methods |

Verify the current tool version and license before bundling forms. The November 2025 ROBINS-I V2 is explicitly a draft subject to change; never call it the current formal version without qualification. Link to the official form rather than modifying a no-derivatives instrument.

## Judgment discipline

Answer signaling questions using report-specific evidence anchors. Distinguish `yes`, `probably yes`, `probably no`, `no`, and `no information` when the tool requires it. The overall judgment must follow the tool algorithm or a documented justified override.

Do not:

- convert domains into an unvalidated total score;
- assess a whole study once when results differ in measurement, missingness, or selective reporting;
- equate poor reporting automatically with high bias when the tool requires `no information` or structured inference;
- in an `assurance` production review, let AI supply the final judgment without the human verification or signature required by the selected authority and protocol.

## Missing evidence and reporting bias

Separate three levels:

- selection of a reported result within a study, handled within result-level tools such as RoB 2 or ROBINS-I;
- missing results from known eligible studies and missing whole studies in a pairwise meta-analysis, assessed with ROB-ME where its scope applies;
- missing evidence in network meta-analysis, assessed with ROB-MEN where applicable.

Use a study-by-synthesis result-availability matrix informed by protocol/registry/report comparison, unavailable outcomes, selective timepoints/analyses, unpublished studies, regulatory sources, small-study effects, and search limitations. Funnel asymmetry is not synonymous with publication bias. Most tests are weak with small `k`; follow method-specific thresholds and interpretation.

## Certainty

Use GRADE per critical outcome/comparison for intervention effects: risk of bias, inconsistency, indirectness, imprecision, and publication bias, plus applicable upgrading considerations. Define outcome-specific decision thresholds or minimally important differences before assessing imprecision when possible. Do not treat the line of no effect as the universal decision threshold.

For network meta-analysis use a framework such as CINeMA or GRADE NMA guidance. For qualitative evidence use GRADE-CERQual when appropriate. For diagnostic, prognostic, prevalence, and other profiles, select current domain-specific certainty guidance and document any adaptation.

For an existing network meta-analysis, distinguish primary-study RoB, ROB-MEN missing-evidence bias, RoB NMA conduct/analysis/conclusion bias, and CINeMA/GRADE certainty. These tools answer different questions and cannot be merged into one score.

Every certainty judgment requires a concise rationale tied to evidence. Do not calculate certainty as a hidden arithmetic score. Present relative effect, baseline risk, absolute effect, certainty, participants/studies, and explanatory footnotes in the Summary of Findings table.
