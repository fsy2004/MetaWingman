---
name: systematic-review-meta-analysis
description: End-to-end, evidence-grounded systematic review and meta-analysis support from topic selection, protocol and registration through live database searching, lawful full-text retrieval, deduplication, dual screening, extraction, study/result lineage, risk-of-bias assessment, quantitative or SWiM synthesis, GRADE, manuscript writing, AI reviewer audit, revision and living updates. Use whenever Codex is asked to plan, conduct, automate, analyze, write, audit, update, or peer-review a systematic review, scoping review, evidence synthesis, or meta-analysis in biomedicine or related fields. Supports pairwise, network, diagnostic, prognostic, prevalence, incidence, proportion, dose-response, IPD, multilevel/RVE, Bayesian, umbrella, qualitative, mixed-methods, rapid, living, and other review profiles. Requires live source verification, auditable provenance, reproducible code, and explicit human decisions; never invent references, screening decisions, extracted values, or completed analyses.
---

# Systematic Review and Meta-Analysis

Treat the review as a research project with irreversible scientific decisions, not as a sequence of AI summaries or a statistics menu.

## Start every task

1. Inspect the live project, Git state, protocol, decision log, search audit, data freeze, and latest outputs. Historical notes are routing context only.
2. Classify the request as `plan`, `topic`, `search`, `screen`, `extract`, `appraise`, `analyze`, `write`, `review`, `revise`, `update`, or `full`.
3. Select the review profile before choosing databases, appraisal tools, or models. Read [review-types.md](references/review-types.md).
4. State the current scientific stage, completed gate, next gate, unavailable inputs, and actions that require human confirmation or credentials.
5. For a new project, run `python scripts/init_review.py --name "..." --root <parent> --profile <profile>`.

## Non-negotiable integrity rules

- Search the live web and authoritative databases for current facts, guidance, registrations, retractions, and references. Prefer official guidance, publisher records, Crossref, PubMed, Europe PMC, trial registries, and DOI landing pages.
- Verify every cited reference as an independent identity: title, authors, year, venue, DOI/PMID/registry ID, and relevance. A plausible or partially matching citation is a failure, not an uncertain citation.
- Never infer full-text eligibility, methods, outcomes, numerical results, or risk-of-bias judgments from an abstract when the full report is required.
- Never fabricate database access, search counts, PDFs, reviewer decisions, extracted cells, analysis outputs, confidence intervals, GRADE ratings, or completion status.
- Preserve `record_id -> report_id -> study_id/trial_id -> result_id`. Analyze at the prespecified independent unit; resolve companion reports, follow-up reports, shared controls, multi-arm trials, duplicate cohorts, and outcome-timepoint lineage before pooling.
- Keep automated suggestions separate from human decisions. AI may prioritize, annotate, or flag records; it must not silently make final exclusions, adjudicate disagreements, or overwrite reviewer-entered data.
- Use dual independent screening, extraction, and appraisal unless the protocol explicitly justifies a different design. Record reviewer identity, timestamp, decision, reason, conflict, and adjudication.
- Freeze the analysis dataset and hash it before confirmatory synthesis. Any post-freeze change requires a versioned amendment and rerun.
- A scaffold, smoke test, compiled manuscript, or successful script is technical evidence only. Do not call the review scientifically complete until every required gate passes.
- Download only lawfully accessible content through documented APIs, open-access links, licensed institutional routes, or user-provided files. Do not bypass paywalls, CAPTCHAs, robots restrictions, or publisher terms.

Read [evidence-integrity.md](references/evidence-integrity.md) before search, extraction, analysis, or writing.

## Stage-gated workflow

Follow [workflow-and-gates.md](references/workflow-and-gates.md). Do not skip forward because a later task is easier.

| Stage | Required output | Hard gate |
|---|---|---|
| 0. Feasibility and topic | novelty map, decision need, existing-review map, accessible evidence estimate | question is useful, answerable, and not merely duplicative |
| 1. Protocol | question framework, eligibility, outcomes, search sources, appraisal and synthesis plan, amendments policy | protocol frozen and registered or registration decision documented |
| 2. Search | source-specific strategies, exact dates, exports, query text, counts, hashes, dedup audit | search is reproducible and required sources are covered |
| 3. Selection | dual title/abstract and full-text decisions, conflicts, exclusion reasons, PRISMA counts | all conflicts adjudicated; full-text exclusions reasoned |
| 4. Data and lineage | piloted extraction, study/report/result map, duplicate/shared-control resolution | dual verification complete; result definitions match protocol |
| 5. Appraisal | result-level or design-appropriate RoB plus supporting quotes/locations | every synthesized result has an appraisal |
| 6. Freeze and synthesis | immutable analysis input, code, environment, tables, figures, sensitivity analyses | hashes and model checks pass; pooling is clinically and statistically defensible |
| 7. Certainty and interpretation | GRADE or profile-appropriate certainty, absolute effects, limitations, applicability | conclusions follow certainty and do not exceed evidence |
| 8. Reporting and review | manuscript, supplement, checklists, disclosure, reviewer panel, response matrix | all critical findings resolved or transparently unresolved |
| 9. Update | search alerts, update cadence, status-change rules, version history | update criteria and retirement rule are explicit |

## Search and retrieval

Read [search-retrieval-and-apis.md](references/search-retrieval-and-apis.md).

- Build each database strategy from concepts, controlled vocabulary, free text, validated filters, and known-item testing. Translate intentionally; never paste one database syntax into another.
- Use `scripts/search_sources.py` for auditable PubMed, Europe PMC, and ClinicalTrials.gov retrieval. Preserve raw responses and a machine-readable audit.
- Import licensed database exports without claiming that an API searched them. Record platform, database, date range, interface, query, limits, result count, and export filename/hash.
- Run `scripts/deduplicate_records.py` for conservative exact deduplication. Treat fuzzy-title matches as candidates for human review, never automatic deletion.
- Run `scripts/download_open_access.py` only for verified open-access locations. Store license, resolved URL, checksum, and retrieval timestamp.
- Run `scripts/verify_citations.py` before any manuscript handoff. Exclude or repair failed identities.

Credentials must come from environment variables or the user's approved secret store. Never write tokens, passwords, cookies, library credentials, or API keys into the project or Git history.

## Selection, extraction, and appraisal

Read [screening-extraction-lineage.md](references/screening-extraction-lineage.md) and [appraisal-certainty.md](references/appraisal-certainty.md).

- Pilot eligibility and extraction on a representative sample before full work.
- Attach evidence anchors to every material field: report ID, page/table/figure/supplement/registry location, quote or cell provenance, extractor, verifier, and date.
- Match appraisal tool to design and estimand. RoB 2 is result-level; do not reduce it to an unexplained study score. Avoid combining incompatible tools into one pseudo-score.
- Distinguish risk of bias within studies, reporting bias across a synthesis, and certainty of the body of evidence.

## Synthesis and code

Read [analysis-methods.md](references/analysis-methods.md) and [tool-catalog.md](references/tool-catalog.md).

1. Decide whether studies address the same estimand and are meaningfully poolable.
2. Predeclare effect measure, scale, model, heterogeneity estimator, CI method, prediction interval, multi-arm/dependency handling, missing-data rules, subgroups, meta-regression, sensitivity analyses, and multiplicity control.
3. Use the bundled R modules in `scripts/r/toolkit/R` and executable runners in `scripts/r/adapters`. Cite the statistical packages and methods actually used.
4. Prefer REML random effects with Hartung-Knapp where suitable; justify alternatives. Report tau-squared and prediction intervals when meaningful. Do not use I-squared thresholds as an automatic pooling rule.
5. Treat subgroup, meta-regression, trim-and-fill, PET-PEESE, ranking, TSA, E-values, and Bayesian priors as assumption-dependent analyses, not automatic upgrades.
6. If pooling is not defensible, use structured synthesis and SWiM rather than forcing a diamond.

## AI reviewer panel and revision loop

Read [reviewer-and-integrity.md](references/reviewer-and-integrity.md).

Run independent lenses before finalization:

- journal fit and contribution;
- review-methods compliance;
- statistical and estimand audit;
- domain/clinical interpretation;
- evidence and citation integrity;
- reproducibility and data-lineage audit;
- Devil's Advocate strongest counter-explanation.

Each finding must include severity, exact evidence anchor, consequence, and executable correction. Synthesize overlaps only after independent review. Trace every revision as `reviewer finding -> author action -> changed artifact -> verification verdict`. Do not let a persuasive response letter substitute for checking the changed manuscript, data, and code.

## Writing and unified style

Read [writing-style.md](references/writing-style.md).

- Write one evidence-led argument from decision problem to methods, results, certainty, applicability, and limitations.
- Separate observed result, interpretation, and implication. Calibrate verbs to design and certainty.
- Report null, imprecise, conflicting, and adverse findings with the same discipline as favorable findings.
- Keep terminology, outcome names, timepoints, effect direction, decimal precision, abbreviations, headings, tables, figures, and citation style consistent across manuscript and supplement.
- Never use generic AI filler, inflated novelty, causal language unsupported by design, or defensive contrast framing.

## Completion report

Report:

1. live project stage and passed/failed gates;
2. sources searched and coverage still missing;
3. record/report/study/result counts and unresolved lineage;
4. appraisal and certainty coverage;
5. frozen dataset/code hashes and verified outputs;
6. reviewer findings and unresolved critical issues;
7. paths to deliverables and the next scientifically necessary action.
