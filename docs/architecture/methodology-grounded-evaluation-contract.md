# Methodology-Grounded Training and Evaluation Contract

Status: implementation contract, 2026-08-20. This document defines what may
train, score, route, or release MetaWingman. It is not a manuscript or a claim
that scientific validation is complete.

## Authority

Scientific review behavior is governed in this order:

1. the selected current human conduct handbook or standard and frozen protocol;
2. the original appraisal, certainty, statistical, and reporting source plus
   applicable supplements;
3. verified professional review artifacts within their reproducible ceiling;
4. secondary explanations, used only to locate or clarify primary sources.

Agent papers contribute engineering candidates such as tool use, search,
reflection, routing, document parsing, uncertainty allocation, and persistent
state. They cannot change eligibility, estimands, poolability, risk-of-bias, or
certainty rules. The machine-readable authority and reading ledger is
`metawingman/references/human-methodology-training-registry.json`; source
identities and transfer boundaries are maintained in
`metawingman/references/methodology-source-registry.md`.

## Rule Provenance

Every rule, metric, or numeric threshold carries exactly one label:

| Label | Permitted use |
|---|---|
| `normative_requirement` | Apply only inside the named authority and profile scope. |
| `primary_study_empirical` | Treat as task-, population-, model-, and version-specific evidence. |
| `project_calibrated` | Freeze development calibration, family-grouped splits, metric, loss, and held-out evaluation before release. |
| `engineering_placeholder` | Exercise software only; never support a scientific claim, hard scientific gate, or release. |

Model self-scores, fluency, same-provider agreement, journal prestige, and a
single published review are not threshold provenance. A published review is a
`published_expert_reference` after correction, retraction, protocol, version,
and reproducibility-ceiling checks; it is not assumed infallible truth.

## Professional Workflow Targets

| Stage | Human-method target learned by the system | External verification |
|---|---|---|
| Topic | decision relevance, answerability, existing-review status, broad-versus-narrow scope | identifiers, date-bounded search, stakeholder and feasibility record |
| Protocol | review PICO, synthesis PICO, estimand, outcome hierarchy, grouping, review family, amendment policy | schema and contradiction checks; frozen protocol hash |
| Search | multi-source sensitive strategy, study-report linking, lawful access, complete reporting | database receipts, known-item tests, PRESS-compatible dossier |
| Screening | criterion-level decision with source span and one controlled exclusion reason | rule engine, duplicate-study graph, abstention on ambiguity |
| Parsing and extraction | report-study-result lineage, exact table/figure/page/cell anchors, unit and denominator checks | multimodal document state, schema validation, independent recomputation |
| Appraisal and certainty | profile- and result-specific RoB; synthesis-level missing evidence; outcome-level certainty | official tool version, signalling-question evidence, GRADE rationale |
| Synthesis | estimand and effect-measure compatibility before pooling; structured synthesis when pooling is not meaningful | typed R manifest, deterministic recomputation, dependency checks |
| Writing and review | claims bounded by source, result, bias, certainty, and clinical relevance | claim-evidence graph, citation verifier, numerical audit |
| Living update | persistent case state, surveillance, version delta, reappraisal, and conclusion-change trigger | immutable event ledger and prior/current state diff |

## Sensitivity Analysis Discipline

Sensitivity analysis is not a volume metric. Run it only for material uncertain
assumptions, borderline eligibility, missing-data rules, bias handling, or model
choices that could alter the conclusion. Prespecify foreseeable analyses. Mark
new analyses exploratory, report multiplicity, and state whether the conclusion
changes. Do not enumerate parameter combinations, repeat near-equivalent models,
or select the result that appears most stable or favorable.

## Model and Verifier Policy

Most source investigation, implementation, and adversarial review is performed
interactively in Codex. Repeatable server batches use one programmatic provider,
`deepseek-v4-flash`. The public Skill remains host-agnostic and contains no API
secret or mandatory provider client.

One model can fill capability-bounded proposer, opposition, judge, and repair
roles with separate context and tool permissions. This is test-time compute, not
independent corroboration. Scientific verification comes from source resolution,
evidence-span recovery, schemas, controlled vocabularies, deterministic R or
Python recomputation, graph consistency, and explicit abstention. DeepSeek Pro
or another model may later be an optional sensitivity arm, never a default
requirement or substitute for external verification.

## Training Instances

Training data have four layers:

1. authority-rule instances: source span, review profile, rule, permitted action,
   prohibited inference, and abstention condition;
2. professional workflow instances: protocols, searches, decisions, extraction
   tables, analysis code, corrections, and update deltas from legally usable
   reviews;
3. counterexamples: result-driven criteria, duplicate reports, incompatible
   estimands, unsupported values, wrong appraisal tools, over-pooling, and
   over-analysis;
4. executable cases: raw primitives through recomputed effects, synthesis, and
   claim lineage under a sealed reference.

Split by review family and dependency graph, not by row. Keep title, authors,
abstract, citations, descendants, and post-cutoff evidence sealed for topic
rediscovery. A model output remains a candidate until a source or executable
verifier accepts it.

## Evaluation

The primary comparison is AI-only MetaWingman against prespecified AI-only
ablations at matched cost. Required outcomes include false exclusion,
included-study recall, unsupported-value rate, critical-error-free proportion,
numerical equivalence, risk-coverage behavior, repeated-run reliability, wall
time, tokens, API cost, local compute, and abstention quality.

Core controls are direct prompting, generic retrieval, no evidence graph, no
opposition, no external verifier, no persistent document state, fixed compute,
and random or fixed method routing. Same-provider blind judges are diagnostic;
they do not determine the reference answer.

## P0-P3 Release Path

- **P0:** validate the rule ledger, joint clinical-question/synthesis schema,
  source and evidence graph, document state, typed actions, and deterministic
  verifier boundaries. No model score can release a scientific artifact.
- **P1:** build dependency-grouped multi-specialty review cases, train only
  narrow components with evidence of gain, calibrate abstention and routing, and
  run matched-cost component ablations with DeepSeek Flash.
- **P2:** replay complete intervention, diagnostic, prognostic/prediction,
  prevalence/etiology/harms, non-meta, and living cases from topic through
  update, preserving every report-study-result and claim edge.
- **P3:** freeze external families and prospective cases, run one-shot
  evaluation, audit failures by mechanism, publish versioned cards and receipts,
  and keep unsupported capabilities marked pending.

Passing software tests means contracts execute in the tested environment. A
scientific capability claim additionally requires the named real-data,
dependency-isolated, externally reviewed validation artifact.
