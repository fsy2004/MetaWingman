# MetaWingman Biomedical Application Contract

Status: approved design; implementation pending
Last reviewed: 2026-08-15
Scope: incremental domain contract for the existing MetaWingman architecture

## 1. Decision

MetaWingman serves researchers conducting systematic reviews and meta-analyses
across human health and clinical translational biomedicine. Biomedical scope is
a product requirement, not an optional prompt preset.

The system retains a domain-neutral evidence-synthesis kernel for engineering
reuse, verification, and out-of-distribution fallback. Public capability claims
remain bounded to biomedical evidence synthesis until another domain passes its
own validation program.

This contract extends the existing P0-P3 roadmap. It does not replace the
evidence graph, global multimodal document state, report-study-result lineage,
provider-neutral runtime, AI-only benchmark, or human responsibility gates.

## 2. Included Scope

The biomedical application domain includes:

- clinical medicine across specialties;
- public health, epidemiology, and health services research;
- diagnostics, prognosis, prediction, prevention, treatment, and harms;
- pharmacology, pharmacoepidemiology, and regulatory evidence;
- rehabilitation, nursing, dentistry, mental health, and allied health;
- clinically connected genetics, imaging, biomarkers, and multi-omics;
- qualitative, mixed-methods, economic, scoping, umbrella, rapid, and living
  reviews when a supported review profile governs the method.

Veterinary, agricultural, and basic-mechanism-only reviews remain outside the
validated product scope in the first release. They may appear in explicit
out-of-distribution tests. A translational review that mixes clinical and
preclinical evidence must preserve separate evidence units, appraisal tools,
and synthesis claims.

## 3. Architecture

### 3.1 Core kernel

The existing kernel remains authoritative for protocol state, event logging,
permissions, provenance, evidence anchors, document state, lineage, analysis,
claims, abstention, and release gates. Domain packs cannot override a frozen
protocol, conduct authority, estimand, eligibility predicate, appraisal
algorithm, certainty framework, or human responsibility rule.

### 3.2 Biomedical foundation

Every new review has a versioned biomedical context that records:

- primary and secondary clinical specialties;
- review profile and eligible study designs;
- PICO, PECO, PIRD, PCC, or profile-specific concepts;
- unresolved and ambiguous concepts in their source wording;
- terminology systems and releases used for normalization;
- source classes and databases required by the question;
- language, geography, population, setting, and equity constraints;
- out-of-distribution status and routing confidence.

Normalization supplements source text. It never erases the original wording or
turns a mapped code into evidence that the source did not report.

### 3.3 Review-profile packs

Review-profile packs bind the question type to conduct, appraisal, reporting,
and synthesis rules. Initial packs cover intervention, diagnostic, prognostic,
prediction-model, etiology, prevalence/incidence, harms, and network reviews.
Existing profiles remain available, but a profile cannot claim native support
until its required adapters and benchmark strata pass their gates.

### 3.4 Specialty packs

Specialty packs add terminology, aliases, outcome hierarchies, common design
patterns, source priorities, and deterministic validators. Initial breadth may
include oncology, cardiovascular medicine, neurology, infectious disease,
mental health, maternal and child health, public health, drug safety,
diagnostics, imaging, and clinical omics.

A project may load several packs. Pack selection is a typed routing decision,
not an unlogged prompt choice. The biomedical foundation handles uncovered
specialties until evidence supports a dedicated pack.

## 4. Runtime Data Flow

1. Compile the protocol into the existing review profile, review questions,
   synthesis questions, eligibility predicates, estimands, and outcome rules.
2. Resolve biomedical concepts and specialties from source-anchored protocol
   text. Retain confidence, alternatives, and unresolved text.
3. Load compatible review-profile and specialty pack manifests.
4. Route each bounded task by capability, modality, review profile, specialty,
   risk, calibration stratum, cost, latency, and available tools.
5. Require model outputs to pass existing schema, anchor, lineage, unit,
   direction, range, arithmetic, identity, and state-transition validators.
6. Use proposal-opposition-judge and external tools for material ambiguity.
7. Fall back to the biomedical foundation or abstain when coverage,
   calibration, evidence, or pack compatibility is inadequate.

No domain route may directly mutate accepted scientific state.

## 5. New Typed Artifacts

Implementation should add narrow artifacts instead of embedding domain logic in
prompts:

- `biomedical_context`: project-level application scope, concept mappings,
  specialty assignments, ambiguity, and out-of-distribution state;
- `domain_pack_manifest`: pack identity, semantic version, supported profiles,
  terminology and authority versions, capabilities, dependencies, constraints,
  compatibility hashes, and validation status;
- `domain_routing_decision`: requested task, candidate packs, selected packs,
  confidence, evidence, reason codes, fallback, and abstention;
- `biomedical_training_stratum`: specialty, question type, study design,
  synthesis route, language, document modality, and challenge tags;
- `domain_coverage_report`: implemented, fixture-tested, retrospectively tested,
  externally validated, and unsupported capabilities by profile and specialty.

Existing schema version 1.0 artifacts remain readable. A migration command must
create the new biomedical context explicitly; migration cannot infer accepted
clinical meaning from filenames or project names.

## 6. Training Corpus

The corpus is broad across medicine and stratified jointly by:

- specialty and cross-specialty status;
- review question and synthesis profile;
- eligible study design and evidence unit;
- document modality, language, and extraction difficulty;
- corrections, duplicate reports, multiple arms, timepoints, shared controls,
  registry-publication conflicts, missing data, and other hard cases.

Top-journal reviews provide high-value sampling strata and expert reference
artifacts. Journal prestige is not a label. Published decisions and values stay
candidate references until original reports, corrections, protocol boundaries,
and source anchors support them.

Training proceeds from bounded tasks: section and table roles, evidence
retrieval, concept normalization, criterion-level screening, structured
extraction, report-study-result linking, routing, and critique. It does not begin
with foundation-model pretraining. Fine-tuning is justified only when it beats
prompt, retrieval, ontology, rule, and verifier baselines on family-isolated
development data.

The corpus keeps review-family and temporal isolation. Hard negatives come from
the same medical neighborhood when possible, such as the same disease with an
ineligible design, intervention, outcome, population, or time window. Model
outputs remain candidates and cannot promote themselves to gold.

## 7. Evaluation

The AI-only benchmark compares four frozen configurations:

1. a general model baseline;
2. biomedical prompts and schemas;
3. biomedical terminology, retrieval, and domain routing;
4. the full biomedical stack with evidence graph, document state, external
   verifiers, test-time scaling, and abstention.

Report task and end-to-end performance by review family and specialty. Primary
measures include critical false exclusion, included-study and result recall,
anchor accuracy, unsupported-value rate, lineage precision and recall, exact
recomputation, calibration, selective coverage, abstention quality, tokens,
cost, latency, and reproducibility.

The benchmark must include cross-specialty cases and explicit out-of-
distribution cases. A gain in average accuracy cannot compensate for a worse
prespecified critical-error bound.

## 8. Failure and Version Policy

- Preserve unmapped text as `unresolved`; do not guess a concept code.
- Treat conflicting pack outputs as evidence for escalation, not a vote.
- Block accepted extraction when the source anchor, unit, direction, result
  identity, or derivation is missing.
- Block a route when its pack, terminology, model, or verifier lacks compatible
  calibration for the requested profile and risk.
- Record pack version, terminology release, authority version, content hash,
  valid date, and compatibility range in every run.
- Do not upgrade packs or terminology silently during a frozen review. A living
  update performs an explicit migration and graph-impact audit.
- Quarantine retrieved instructions as untrusted document content. Domain packs
  cannot grant tool permissions or disclose credentials.

## 9. Integration With P0-P3

### P0

Add the typed artifacts, compatibility migration, deterministic domain resolver,
pack registry, training strata, coverage audit, fixtures, and release checks.
Prepare a larger lawful corpus plan and server-ready run manifests without
starting bulk jobs.

### P1

Apply the biomedical context to the two existing vertical slices: protocol-aware
hard-negative screening and multimodal lineage-preserving extraction. Establish
cross-specialty and out-of-distribution benchmark fixtures.

### P2

Bind design-specific appraisal, poolability, certainty, and claim compilation to
review-profile packs. Add specialty validators only where they change material
clinical interpretation or error detection.

### P3

Version terminology, packs, source priorities, and calibration alongside living
searches. Propagate a domain or ontology change through the evidence graph before
accepting an update.

## 10. Local-to-Server Gate

Local development is complete for the first training scale-up only when:

- schemas, migrations, pack manifests, and validators pass the full local suite;
- a medically stratified corpus plan has frozen input hashes, seed, family split,
  license policy, size budget, and expected strata;
- download, resume, audit, freeze, annotation, export, and benchmark commands have
  small local end-to-end evidence;
- base model, revision, tokenizer, license review, hyperparameters, random seeds,
  resource request, checkpoint policy, and output paths are frozen in a
  provider-neutral run plan;
- sealed benchmark families and training families are separated and audited;
- raw full text, credentials, and generated checkpoints are excluded from Git;
- a server preflight can validate storage, runtime, accelerator, network, and
  hashes without starting download or training.

The next action after this gate is an explicitly authorized server run for bulk
lawful retrieval, corpus processing, component training, or benchmark execution.
Server scale is not required to finish the schemas, orchestration, fixtures,
small-corpus validation, or run manifests.

## 11. Non-Goals

- Renaming MetaWingman or replacing its current architecture.
- Creating a separate full Agent for every medical specialty.
- Training a biomedical foundation model from scratch.
- Treating ontology codes, top-journal publication, model agreement, or fluent
  clinical language as ground truth.
- Claiming all medical specialties or review profiles are validated because a
  common workflow entry exists.
