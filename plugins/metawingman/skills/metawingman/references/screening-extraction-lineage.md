# Screening, extraction, and lineage

## Record model

- `record_id`: one database/export record before deduplication.
- `report_id`: one accessible report, abstract, registry entry, supplement, correction, thesis, or conference item.
- `study_id` or `trial_id`: one underlying study/cohort/trial.
- `arm_id` or `cohort_id`: one assigned group or independently sampled cohort within a study.
- `result_id`: one estimand-specific result defined by outcome, metric, timepoint, population, comparison, model, and report location.
- `synthesis_id`: one prespecified group of compatible results.
- `claim_id`: one reportable observation, interpretation, or implication connected to accepted synthesis and certainty nodes.

Keep alias tables for DOI, PMID, PMCID, NCT/registry IDs, acronyms, author-year labels, cohort names, and sponsor study IDs. Never destroy the original record during merging.

The minimum lineage is `record -> report -> study/trial -> arm/cohort -> result -> synthesis -> certainty -> claim`. Store every raw assertion or value as an evidence node with page/block/table/cell/figure coordinates, and every derivation as an edge rather than replacing its source.

## Screening

Use controlled decisions: `include`, `exclude`, `maybe/unclear`, `duplicate-candidate`, and `awaiting-report`. At full text, use one primary exclusion reason from a protocol-specific hierarchy and optional secondary notes.

Store reviewer, timestamp, stage, decision, reason, confidence if used, evidence note, conflict flag, adjudicator, and final decision. Report inter-reviewer agreement as process information, not as proof of valid criteria.

Automation may prioritize records and prepare criterion-level decisions. Preserve original order, score, prompt/model/tool version, anchors, and abstention state. In assurance mode, apply the selected conduct authority's independent-human rule; do not present an AI decision as an independent person. Automatic removal is permitted only in a preregistered evaluation or explicitly allowed rapid workflow with an audit and declared limits.

## Extraction

Pilot the form. Extract:

- identifiers and report/study relationships;
- design, recruitment, setting, dates, centers, funding, conflicts;
- eligibility, baseline participants, intervention/exposure/test and comparator/reference standard;
- outcome definition, hierarchy, ascertainment, unit, direction, timepoint/window, analysis population;
- raw cells and/or effect, uncertainty, model, adjustment set, missing-data handling;
- multiplicity, subgroup definition, shared controls, cluster/crossover features;
- source anchor and original wording/value;
- extractor, verifier, conflict, adjudication, transformation, and status.

## Lineage checks before freeze

- Map all companion publications and registries to one study.
- Select the report/result according to the prespecified hierarchy, not effect size or significance.
- Split genuinely independent cohorts and join duplicate cohorts.
- Reuse shared control groups with appropriate covariance or arm splitting; do not double count.
- Match outcome name, severity/grade, attribution, measurement instrument, denominator, follow-up, and analysis population.
- Keep adjusted and unadjusted estimates separate; choose the prespecified adjustment hierarchy.
- Document author contact and any derived or imputed values.
- Ensure every analysis row maps to exactly one result and every included result has appraisal coverage.
