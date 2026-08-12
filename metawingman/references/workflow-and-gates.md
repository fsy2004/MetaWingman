# Workflow and gates

## Contents

1. Stage 0: topic and feasibility
2. Stage 1: protocol
3. Stage 2: search
4. Stages 3-5: selection, data, appraisal
5. Stages 6-7: synthesis and certainty
6. Stages 8-9: reporting, review, update

## Stage 0: topic and feasibility

Start from a decision problem, not from an available dataset or a fashionable method. Produce:

- decision-maker and decision to be informed;
- question framework appropriate to the evidence type;
- preliminary map of recent reviews, protocols, guidelines, pivotal studies, and ongoing trials;
- overlap matrix: population, intervention/exposure/test, comparator, outcomes, design, dates, and analytical gap;
- feasibility estimate for eligible studies, extractable outcomes, heterogeneity, access, skills, time, and update value;
- verdict: proceed, narrow, broaden, convert review type, update an existing review, or stop.

Novelty can come from a new decision need, evidence update, outcome, population, methodologically defensible design, or resolved limitation. Never claim novelty because no identical title was found.

## Stage 1: protocol

Freeze before formal screening:

- rationale and objectives;
- framework and operational definitions;
- eligibility and exclusion rules;
- primary and secondary outcomes, hierarchy, measures, timepoints, and minimal important differences where available;
- information sources and complete draft strategies;
- record management, deduplication, screening, conflict, and retrieval procedures;
- extraction schema and report/study/result lineage;
- appraisal instruments and target estimands;
- synthesis groups, effect measures, dependency handling, models, heterogeneity, prediction intervals, missing data, subgroups, meta-regression, sensitivity analyses, reporting-bias methods, and certainty assessment;
- deviations, amendments, AI use, data/code sharing, conflicts, funding, and update policy.

Register when eligible (for example PROSPERO) or publish an OSF protocol. Record why registration was not possible or appropriate. Date and version every amendment; label it prospective or post hoc.

## Stage 2: search

Require a source plan matched to the question. Biomedical intervention reviews normally need MEDLINE/PubMed, CENTRAL, Embase when available, trial registries, backward/forward citation chasing, and domain sources. Add Web of Science/Scopus, CINAHL, PsycINFO, regional and Chinese databases, regulatory sources, preprints, dissertations, or grey literature when justified.

For every search, preserve database and platform, full query, coverage dates, execution timestamp and timezone, limits, results count, export format, export filename, checksum, account/interface restrictions, and searcher. Peer-review high-stakes strategies with PRESS where feasible.

Gate fails if a claimed database was not actually searched, the query cannot be reconstructed, counts do not match exports, required sources are missing without rationale, or known eligible sentinel studies are not retrieved.

## Stages 3-5: selection, data, appraisal

Use two independent screeners at title/abstract and full text. Calibrate on a pilot set, reconcile rule ambiguity, then restart or document changed decisions. Preserve every full-text exclusion reason; choose one primary reason from a controlled hierarchy.

Pilot extraction on diverse studies. Extract report metadata, study lineage, design, setting, participants, interventions/exposures/tests, comparator, outcomes, timepoints, analysis population, effect estimates or raw data, adjusted covariates, missing data, funding/conflicts, and evidence anchors.

Assess bias for the exact result/estimand where the instrument requires it. Store signaling-question responses, rationale, source location, judgment, assessor, conflict, and adjudication.

Gate fails if conflicts remain, companion reports are unresolved, denominators or outcome definitions are substituted, shared controls are double counted, extracted numbers lack anchors, or synthesized results lack appraisal.

## Stages 6-7: synthesis and certainty

Create a canonical analysis table with one row per result and explicit linkage to synthesis. Validate bounds, units, direction, transformations, duplicated samples, impossible values, and effect/SE consistency. Freeze and hash the table, protocol, analysis configuration, and code commit.

Run the prespecified primary analysis, diagnostic checks, clinically motivated sensitivity analyses, and predeclared subgroup/meta-regression. Label every deviation and exploratory analysis. Preserve logs, session information, package versions, seeds, warnings, and generated files.

Assess certainty per critical outcome and comparison. Connect every downgrade/upgrade to explicit evidence. Interpret relative and absolute effects, uncertainty, prediction, heterogeneity, bias, indirectness, applicability, and decision relevance.

Gate fails if pooling ignores clinical incompatibility, dependency is untreated, direction is inconsistent, post hoc analyses are presented as confirmatory, GRADE is a mechanical score, or conclusions exceed certainty.

## Stages 8-9: reporting, review, update

Complete the applicable PRISMA checklist and extensions, flow diagram, excluded full-text list, search strategies, characteristics, result-level RoB, synthesis outputs, GRADE/SoF, deviations, data/code availability, funding, conflicts, and AI disclosure.

Run the reviewer panel on manuscript, supplement, frozen data, and code. Resolve or transparently retain critical issues. Re-run citation verification and a clean-room analysis before release.

For living or planned updates, define surveillance sources, cadence, triggers for reassessment/publication, versioning, notification, and retirement. An unchanged search is still logged; a changed conclusion triggers full reappraisal and reporting.
