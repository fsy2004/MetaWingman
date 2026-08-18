# MetaWingman AI-first Architecture Roadmap

Status: implementation in progress
Last checked: 2026-08-12
Scope: implementation plan for an AI-first, evidence-grounded, human-overseen systematic review and meta-analysis skill.

## Product Boundary

MetaWingman should maximize AI execution under explicit risk controls. It should not promise unconditional unsupervised systematic reviews.

Default principle:

`AI proposes and executes reversible, verifiable work; humans adjudicate abstentions, conflicts, high-risk judgments, credentials, irreversible submissions, and final scientific responsibility.`

The architecture must measure AI coverage, abstention, critical error rate, unsupported values, false exclusions, API/compute cost, latency, and reproducibility. A smooth demo without these measurements is not evidence.

## Method Contract

Implementation follows [the end-to-end methodology blueprint](end-to-end-methodology-blueprint.md). Every project pins:

- a review profile and exact conduct/reporting/appraisal/certainty authorities;
- an operating mode: `assurance`, `evaluation`, or `rapid`;
- separate review and synthesis questions, target estimands, outcome/result hierarchy, time windows, and decision thresholds;
- independent-review rules, AI-exposure order, amendments, and living-update policy.

`assurance` keeps independent-human decisions required by the selected authority while AI prepares the work first. `evaluation` is the only mode that may test replacement of a mandated human task, under preregistered reference standards and error limits. `rapid` records every shortcut and must not claim comprehensiveness.

## P0: Audit Core

Goal: make every action replayable, typed, and stoppable before adding more agents.

The implemented infrastructure subset does not complete the P0 method contract. P0 is complete only when scientific decisions are typed as well as agent actions.

Schemas:

- `review_state.schema.json`: project, review profile, current stage, gates, protocol version, freezes, unresolved risks.
- `event_ledger.schema.json`: append-only action records with input hash, output hash, tool/model version, prompt hash, cost, latency, retry count, status, and actor.
- `evidence_anchor.schema.json`: report ID, page, block/table/cell/figure, bounding box, quote or crop reference, parser source, checksum, confidence.
- `model_registry.schema.json`: capability slots, provider, model, version, context, modality, cost, latency, allowed tools, calibration set.
- `tool_contract.schema.json`: typed input/output, permissions, idempotency key, retry budget, verifier, credential boundary.
- `abstention.schema.json`: abstain reason, risk signal, affected decision, required human role, resolution record.
- `review_profile.schema.json`: question family, operating mode, conduct/reporting authorities, tool versions, certainty route, independent-review requirements.
- `protocol.schema.json`: decision context, review and synthesis questions, estimands, predicates, outcome hierarchy, time windows, thresholds, source plan, amendment policy.
- `reviewer_assignment.schema.json` and `protocol_deviation.schema.json`: actor/independence/order/conflict plus versioned post-freeze changes.
- `document_state.schema.json`, `evidence_assertion.schema.json`, and `lineage_edge.schema.json`: global multimodal state and `record -> report -> study/trial -> arm/cohort -> result -> synthesis -> certainty -> claim`.
- `extraction_candidate.schema.json`, `appraisal_dossier.schema.json`, `analysis_manifest.schema.json`, and `claim.schema.json`: candidate values, judgment evidence, executable analysis contract, and support-bounded reporting.

Modules:

- `state_store`: reads/writes review state and event ledger.
- `schema_guard`: validates all LLM and tool outputs before state changes.
- `method_contract`: validates profile/protocol readiness, exact authority versions, reviewer independence, artifact hashes, document/anchor consistency, accepted-value provenance, and final human responsibility across objects.
- `capability_router`: chooses model/tool/test-time budget from task, risk, cost, and prior failures.
- `pipeline_compiler`: versions typed LM modules, demonstrations, prompts, and optimization data; evaluates changes on review-family splits with an asymmetric scientific loss.
- `agent_interface`: exposes bounded scientific actions and compact observations instead of a general shell or unconstrained browser transcript.
- `credential_boundary`: separates public APIs, user-authorized browser handoff, and inaccessible/licensed sources.
- `provenance_graph`: stores protocol predicates, records, reports, studies, results, evidence anchors, derived values, judgments, syntheses, and claims.

Acceptance tests:

- Invalid JSON, schema drift, missing hashes, over-budget retries, and tool failure must produce a blocked or abstained event, not silent continuation.
- Re-running a completed action with the same idempotency key must not duplicate state.
- A generated conclusion with no evidence anchor must fail validation.
- A project without a pinned mode, profile authority, synthesis question, estimand, and threshold cannot freeze its protocol.
- An AI actor cannot satisfy a field marked `independent_human_required` in `assurance` mode.
- A `current` tool label without an exact version and verification date fails the profile gate.
- Prompt/compiler optimization that uses held-out review families or optimizes a generic judge score without source-grounded task metrics fails release validation.
- Repeated identical tasks must meet a prespecified pass-style reliability floor, not only a favorable mean score.

### Stage 0 discovery control

Topic selection is now a separate executable control surface, described in [Topic Opportunity Engine](topic-opportunity-engine.md). Its P0 contracts are `temporal_evidence_landscape`, `topic_proposal_batch`, `topic_candidate`, `topic_opportunity_decision`, `topic_rediscovery_case`, and `topic_rediscovery_report`. `propose_topics.py` lets an explicitly authorized hosted model propose frameworks and evidence references without self-scoring; `select_topics.py` applies independently audited signals, frozen gates and a diversity-aware portfolio; `evaluate_topic_rediscovery.py` scores locked framework-level concordance. These fixtures establish boundary behavior only. Automatic graph construction, independent signal acquisition/calibration and prospective validation remain open. A 15-target, 39-domain-tag intake registry now supplies broad historical development strata; only three have a publisher-verified initial cutoff and none is a sealed test case.

## P1: Two Vertical Slices

### Slice A: Protocol-aware hard-negative screening

Inputs:

- frozen protocol predicates;
- database exports and public API records;
- known included studies and hard-negative candidates.

Modules:

- `protocol_compiler`: converts natural-language eligibility into typed criteria.
- `query_swarm`: proposes source-specific search strategies and known-item tests.
- `criterion_agents`: classify each criterion as `met`, `not_met`, `unclear`, or `not_reported`.
- `hard_negative_adversary`: searches for the strongest exclusion evidence.
- `protocol_judge`: aggregates criterion outputs through deterministic policy rules.
- `screening_escalator`: routes missing full text, conflicting evidence, high-impact exclusions, and low calibration confidence to humans.

Primary metrics:

- included-study recall;
- exclusion false-negative rate;
- evidence-anchor accuracy;
- abstention rate;
- AI selective coverage and cost-quality frontier at the prespecified recall floor.

### Slice B: Multimodal extraction with deterministic recomputation

Inputs:

- PDFs, XML/HTML, supplements, registry records, and user-provided extraction tables where allowed.

Modules:

- `document_ingestor`: stores original files, checksums, text layer, page images, supplements, and license metadata.
- `layout_parser`: produces page blocks, tables, captions, figures, equations, footnotes, and coordinates.
- `text_table_vision_extractors`: generate candidate primitives from independent evidence channels.
- `lineage_resolver`: links report, study/trial, arm, outcome, timepoint, and result entities.
- `global_state_solver`: checks cross-table totals, arms, timepoints, units, and incompatible candidate merges.
- `effect_recalculator`: computes effect sizes, SEs, CIs, variances, and direction using deterministic code.

Primary metrics:

- field-level exact or tolerance accuracy;
- unsupported-value rate;
- lineage precision and recall;
- numerical equivalence for effect, SE, CI, tau-squared, and prediction interval;
- error attribution by parser, model, lineage, and computation stage.

## P2: Judgment Workbench

Goal: turn high-risk scientific judgments into evidence dossiers rather than oracle labels.

Modules:

- `rob2_dossier`: signaling-question evidence, missing information, proposed answer, opposition, rule check, and judge recommendation.
- `robins_quadas_adapter`: design-specific appraisal schema adapters.
- `missing_evidence_dossier`: study-by-synthesis result availability plus ROB-ME or ROB-MEN where applicable.
- `estimand_alignment_matrix`: population, intervention/exposure, comparator, outcome, time horizon, effect measure, conditioning set, and unit of analysis.
- `poolability_conference`: clinical, methods, and statistical proposal-opposition-judge with abstention.
- `grade_dossier`: per-domain certainty evidence, imprecision thresholds, indirectness map, publication-bias signals, absolute effects, and wording limits.
- `claim_compiler`: observation, interpretation, implication, certainty, scope, allowed verbs, and source nodes for each manuscript claim.

Human-overseen policy:

- RoB, GRADE, poolability, protocol freeze, and final conclusions require human signature.
- The AI should complete the dossier and recommendation first, then request adjudication only when the gate requires it.
- The benchmark has no human execution mode or routine de novo human reference adjudication. Published review-team outputs are sealed until every AI run is locked; production scientific responsibility remains a separate boundary.

## P3: Living System and Prospective Evaluation

Modules:

- `living_monitor`: scheduled source searches, registry updates, citation alerts, retraction checks, and model-drift checks.
- `impact_analyzer`: computes which graph nodes, analyses, and claims are affected by a new record or correction.
- `amendment_manager`: records post-freeze changes, required reruns, version history, and retired conclusions.
- `prospective_workflow_logger`: captures AI configuration, repeated-run outputs, latency, token/compute cost, abstentions, errors, reference version, and publication-integrity provenance.

Study designs:

- Time-split reconstruction of published reviews with open materials.
- Component benchmark against published expert references with verified correction handling.
- AI-only repeated-run comparison of the full system, prespecified model/router/tool configurations, and ablations.
- Human judgment is not an execution arm or a routine post-run benchmark repair step; production scientific responsibility gates remain outside the AI-only comparison.
- This design estimates agreement and stability against published expert references. It cannot estimate absolute truth accuracy, superiority to humans, human-AI synergy, or labor savings.

## Benchmark Backlog

Candidate novelty is governed by [the innovation and falsification matrix](innovation-and-falsification-matrix.md) and the [contribution story contract](top-journal-contribution-story.md). ReAct-style tools, debate, routing, semantic uncertainty, conformal control and multimodal parsing are reused foundations. The external story has four contributions: decision-aware topic opportunity control, a lifecycle-complete evidence-synthesis system, conclusion-directed evidence acquisition and verification, and time-sealed/counterfactual evaluation. The evidence compiler, counterevidence tournament, multimodal state solver and living graph are enabling mechanisms. None is an established claim until its direct baseline and ablation pass on held-out review families.

Datasets to assemble first:

- 20 to 30 public intervention reviews with protocols, search exports, included studies, extraction tables, and analysis code or sufficient numeric outputs.
- Stress strata for hard negatives, multi-report studies, multi-arm trials, non-English reports, supplements, tables/figures, and missing variance data.
- Gold cases for pairwise, proportion, diagnostic, network, RVE/multilevel, dose-response, and Bayesian analyses.
- Adversarial cases for hidden document instructions, poisoned retrieval/memory, unauthorized tool actions, and data exfiltration.
- Position-shifted long-document cases, order-swapped judge cases, repeated-run reliability cases, and policy-conflict tool scenarios.

Baselines:

- single strong LLM structured prompt;
- generic RAG agent;
- single-model multi-agent system;
- heterogeneous models without provenance graph;
- full MetaWingman AI-only pipeline;
- ablations without router, counterevidence, multimodal layer, deterministic verifier, or calibrated abstention.
- ablations without the narrow agent interface, compiled prompt/module optimization, positional probes, or judge order randomization.

Reporting:

- Use paired bootstrap confidence intervals by review and by result.
- Distinguish AI error, reference-standard error, ambiguous report, and protocol disagreement.
- Report model/provider versions, prompts, tool versions, search dates, dataset hashes, and costs.

## Issue-style Backlog

Checked items below mean the local typed primitive and focused tests exist. They do not mean a real review, prospective human comparison, model validation, or public release has passed.

- [x] P0-1: Add schema folder and implement `review_state`, `event_ledger`, `evidence_anchor`, `model_registry`, `tool_contract`, `scientific_action`, and `abstention` schemas.
- [x] P0-2: Add hash-chained state/event validator with failure fixtures and idempotency checks.
- [x] P0-3: Add model capability registry and dry-run router with deterministic proposal-opposition-judge formation.
- [x] P0-4: Add `review_profile`/authority/mode and full protocol/synthesis-question schemas, project templates, and protocol-freeze readiness checks.
- [x] P0-5: Add reviewer assignment, independence, AI-exposure-order, and protocol-deviation schemas and cross-object guards.
- [x] P0-6: Add document-state, evidence/lineage, extraction, appraisal, analysis-manifest, and claim schemas with accepted/final-state invariants.
- [x] P0-7: Add provenance graph storage interface and minimal CLI inspector.
- [x] P0-8: Add prompt-injection and poisoned-retrieval security fixtures.
- [x] P0-9: Add bounded agent action/observation interface, repeated-run reliability tests, long-context position probes, and judge-order audit fixtures.
- [x] P0-10: Add versioned pipeline compiler/evaluator with review-family train/dev/test isolation and asymmetric loss.
- [x] P1-1: Extend the compiler to synthesis PICO, outcome hierarchy, estimand, timepoint, and decision-threshold predicates, then benchmark ambiguity.
- [x] P1-2: Implement screening criterion agents with abstention and hard-negative opposition.
- [x] P1-3: Build document ingestion manifest with original PDF, text layer, page image, supplement, license, and checksum records.
- [x] P1-4: Connect extraction candidates to deterministic effect-size recomputation and numerical-equivalence fixtures.
- [x] P2-1: Build RoB 2 signaling-question dossier format with proposal-opposition-judge fields.
- [x] P2-2: Build ROB-ME/ROB-MEN missing-evidence dossiers.
- [x] P2-3: Build estimand alignment and poolability matrix.
- [x] P2-4: Build GRADE dossier, decision-threshold checks, and claim compiler guardrails.
- [x] P3-1: Build living update monitor around source deltas and graph impact.
- [x] P3-2: Create benchmark packaging scripts and public/private data split policy.
- [x] P3-3: Add a machine-audited capability matrix spanning ten lifecycle stages, the complete 21-profile catalog, explicit synthesis routes, cross-cutting controls, validation levels, and anti-overclaim guards.
- [x] P3-4: Add a typed conclusion-directed evidence-acquisition controller with frozen risk/impact thresholds, legal-action filtering, historical leakage guards, deterministic ranking, stop candidates, and abstention.
- [x] P0-11: Add the typed temporal evidence landscape, evidence-grounded topic candidates, frozen value-risk gates, diversity-aware topic portfolio, sealed framework-level rediscovery evaluator, and model-memory claim boundary.
- [x] P0-12: Add a live DeepSeek text/structured-data provider adapter with Windows Credential Manager or environment-secret resolution, model discovery, bounded JSON probe, content-free telemetry and an unvalidated registry template.
- [x] P0-13: Generalize the external Agent to secret-free OpenAI-compatible provider configuration, explicit loopback-only local HTTP, schema-gated candidate generation, one-repair abstention and content-free provider telemetry; live exercise the contract through DeepSeek without claiming independent-provider validation.
- [x] P0-14: Build a conservative 4,098-record review-family candidate registry with boilerplate-resistant title blocking, integrity propagation, family-level split suggestions and a hard zero held-out-ready gate pending lineage audit.
- [x] P0-15: Add a checkpointed external-Agent batch runner with per-attempt usage aggregation, worst-case repair-call/output reservation, duplicate-task prevention, cross-process JSONL append, dead-letter hashes and resume validation; verify one live DeepSeek task and zero-call replay from checkpoint.
- [x] P0-13: Add an explicit-consent, prompt-size-bounded topic proposal adapter that validates temporal landscapes and evidence-node references, permits one hash-audited schema-repair call, abstains on surviving schema/self-score violations, and routes every proposal to independent signal audit before frozen ranking.
- [ ] TOPIC-1: Build dated multidisciplinary graph ingestion from primary studies, registries, reviews/protocols, guidelines and priority statements with source anchors and ontology normalization.
- [ ] TOPIC-2: Promote the 15-target, 39-domain-tag broad top-general/top-field intake registry into leakage-audited cases; add hard-negative false opportunities and model-memory probes, then split by review family and time. Three targets are boundary-ready, none is sealed-case-ready, and two publisher corrections are explicitly bound to corrected-version-only benchmark actions.
- [ ] TOPIC-3: Compare bibliometrics, semantic gap maps, LLM-only, generic RAG, graph-only and literature-idea-agent baselines, then run one-at-a-time ablations.
- [ ] TOPIC-4: Prospectively register a diverse topic portfolio and follow evidence growth, later reviews/guidelines, decision use, feasibility and duplication.
- [ ] VAL-0: Freeze profile-specific capability claims from `audit_system_coverage.py`; no lifecycle, profile, or validation breadth claim may exceed the matrix.
- [ ] VAL-1: Select and license-review the first published-review reconstruction families without contaminating the held-out split. Eighteen formally identified reviews are in the broad discovery catalog and four are in the strict registry. Five immutable material plans now cover BMJ living-NMA method code, the PLOS living-DTA pair, carbon-pricing screening, SCI extraction-to-analysis and HEPSANET controlled-IPD guards. BMJ lacks article-specific data, carbon pricing lacks explicit artifact licensing and cutoff, the later DTA repository remains unresolved, and HEPSANET IPD is controlled; promotion therefore remains open.
- [x] VAL-2a: Encode an AI-only repeated-run plan, published-expert/corrected reference policy, integrity exclusions, error taxonomy, metric set, and inference limits.
- [x] VAL-2b1: Freeze the component-axis task manual (blind task set + sealed weak-label key + ten stage checklists + VAL-2c spot-check + verifier rules), scientific loss weights, release thresholds, C0-C3 prompt hashes, and stopping rules (`docs/architecture/val2b-task-manual-freeze-2026-08-18.md` + `research/ai-only-evaluation-plan.val2b1-v1.0-frozen.json`).
- [ ] VAL-2b2: Fill and freeze the reconstruction-case task manuals (blocked on VAL-1 promotion of the five benchmark families).
- [x] VAL-2c: Freeze the 100-item human-blind appraisal-domain spot-check (weak-label rule-clarity measurement) with a sealed answer key and SHA-256 manifest; rating pending (protocol: `appraisal-human-blind-spotcheck-protocol-2026-08-18.md`).
- [ ] VAL-3: Run the AI-only configuration/ablation pilot and measure critical error, coverage, accuracy, cost, reliability, position sensitivity, and judge-order sensitivity.
- [x] VAL-4a: Add typed counterfactual protocol cases, sealed-boundary guards, expected dependency-graph deltas, earliest-error localization, verified-output intervention replay, recovery scoring, and event-order stability fixtures.
- [ ] VAL-4b: Build real-review counterfactual cases from published expert artifacts with verified corrections, then test whether replay attribution is stable across held-out review families.
- [ ] VAL-5: Calibrate conclusion-directed acquisition on development review families and compare fixed Top-K, linear pipeline, non-claim-aware stopping, confidence-only routing, and full control on held-out families.

## Do Not Build Yet

- A one-click manuscript generator without source-level claim validation.
- Unbounded browser automation for licensed databases.
- A single all-purpose reviewer persona.
- Analysis scripts generated from free text without a typed manifest.
- Automatic RoB, GRADE, or poolability final judgments without human signature.
