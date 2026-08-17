# MetaWingman End-to-End Methodology Blueprint

Status: governing design
Last verified: 2026-08-12
Scope: the methodological contract for an AI-first, evidence-grounded, human-overseen systematic review and meta-analysis system. It is an implementation blueprint, not a manuscript.

## 1. Governing Principle

MetaWingman should maximize verified AI execution, not maximize nominal automation.

`AI prepares and executes reversible work; typed rules and external tools verify it; humans resolve mandated independent decisions, abstentions, material conflicts, high-risk judgments, credentials, irreversible actions, and final responsibility.`

AI-first therefore means that the model starts the work and assembles the evidence dossier. It does not mean that an LLM may silently count as an independent reviewer, invent unavailable access, or waive a conduct standard.

## 2. Authority Stack

Every rule in the system must declare its source class. Higher classes constrain lower classes.

1. **Profile-specific conduct authority**: current Cochrane/MECIR, JBI, or another explicitly selected domain handbook defines how the review is conducted.
2. **Protocol and registration**: the frozen, versioned protocol operationalizes the authority for this project. Post-freeze changes are amendments, never invisible prompt edits.
3. **Appraisal, certainty, and statistical authority**: official tool versions and current method guidance define result-level judgments and synthesis behavior.
4. **Reporting authority**: PRISMA and applicable extensions define what must be reported. A reporting checklist is not a conduct or risk-of-bias instrument.
5. **Evidence-synthesis automation studies**: empirical studies estimate performance, workload, and failure modes for a defined task and dataset. They do not change review conduct by themselves.
6. **General LLM and agent papers**: these provide candidate engineering mechanisms only. ReAct, debate, RAG, routing, semantic entropy, and conformal methods cannot redefine eligibility, estimands, pooling, RoB, or GRADE.

For each project, store the exact authority URL, version, chapter or tool release, verification date, and any justified deviation. The root label “current” is insufficient because individual handbook chapters and tools update on different dates.

## 3. Operating Modes

### `assurance`

Production mode for a decision-relevant review that claims adherence to its selected conduct standard.

- AI performs discovery, drafting, prioritization, criterion decomposition, document parsing, extraction proposals, dossier assembly, deterministic computation, and audit by default.
- Mandatory independent human processes remain mandatory. For a Cochrane-style intervention review, final full-text eligibility requires at least two people working independently, and outcome data extraction in duplicate is mandatory.
- AI may be an additional reviewer or prepare evidence for both reviewers, but it is not silently represented as one of the required independent people.
- Protocol freeze, final exclusions, unresolved extraction conflicts, final RoB/certainty/poolability judgments, external submission, and conclusions require recorded human responsibility.

### `evaluation`

Preregistered method-development mode for testing whether AI can replace a specified human task.

- Define the exact replacement claim, review profiles, languages, document types, loss function, recall floor, and maximum acceptable critical error before evaluation.
- Compare against the published review team's expert work product, anchored to original reports where lawful materials permit verification, rather than treating copied review tables as an oracle.
- For the current validation program, use AI-only repeated runs with blinded sealed answers, verified correction handling, and no routine de novo human adjudication. Do not add human execution arms.
- Use random tail audits, hard-negative challenge sets, risk-coverage curves, drift tests, and prospective validation.
- Do not call an experimental replacement “standards compliant” until the relevant authority accepts it or equivalence has been prospectively demonstrated under an explicitly justified design.

### `rapid`

Decision-driven accelerated mode using declared shortcuts under current rapid-review guidance.

- Record each omitted or streamlined step, reason, likely bias, and mitigation.
- Retain design-matched appraisal and transparent reporting.
- Never describe a deliberately restricted search or single-reviewer process as comprehensive.

The mode is stored in review state and cannot be changed without a protocol amendment.

## 4. First-Class Scientific Objects

The state model must represent the decisions that determine the review, not only files and agent messages.

- `decision_context`: stakeholder, decision, deadline, priority source/process, represented and missing voices, values, equity, conflicts, governance, and consequences of false positive, false negative, and delayed conclusions.
- `review_profile`: question family, conduct authority, reporting extensions, appraisal tools, certainty framework, and pinned versions.
- `review_question`: broad eligibility frame and review PICO/PECO/PIRD/PCC or profile-specific equivalent.
- `synthesis_question`: one planned synthesis PICO, target estimand, comparison, outcome domain, metric, time window, population subgroup, and eligible design.
- `included_study_question`: what each included study actually investigated, retained separately from the planned questions.
- `outcome_hierarchy`: criticality, preferred instruments, time windows, analysis populations, and rules for choosing among multiple results.
- `decision_threshold`: outcome-specific threshold used for interpretation and imprecision; the null is not automatically the decision threshold.
- `protocol_predicate`: typed inclusion/exclusion rule with examples, exceptions, and ambiguity state.
- `protocol_deviation`: trigger, discovery time, prospective/post hoc status, impact, approver, and affected artifacts.
- `reviewer_assignment`: role, independence requirement, blinding/order, decision, conflict, and adjudication.
- `document_state`: original file, license, checksum, text layer, page image, layout blocks, tables, figures, equations, footnotes, supplements, and parse alternatives.
- `evidence_assertion`: atomic source statement or value with page/block/cell/figure anchor and support/contradiction relation.
- `analysis_manifest`: typed estimand, effect measure, model, dependency handling, missing-data rules, diagnostics, and prespecified sensitivity analyses.
- `claim`: observation, interpretation, implication, scope, certainty, allowed verbs, and supporting graph nodes.

The core lineage is:

`record -> report -> study/trial -> cohort/arm -> result -> synthesis -> certainty judgment -> claim`

Every transformation adds a provenance edge; no merge destroys the source node.

## 5. Full-Workflow Audit and Target Design

| Stage | Recurrent methodological defect | AI-first default | Independent verifier | Human gate |
|---|---|---|---|---|
| 0. Topic and feasibility | novelty by title search; question follows an available dataset; no decision need; stakeholder/equity values hidden; stale review or wasteful duplication ignored | map priority exercises, stakeholder needs, guidelines, reviews, protocols, pivotal and ongoing studies; generate competing scopes; estimate access, extractability, added value, and opportunity cost | DOI/registry identity resolver, date/version checks, known-study recovery, update/replication worksheet, priority-process completeness check | select the question and proceed/narrow/update/replicate/surveil/archive/stop; approve values and represented voices |
| 1. Protocol | vague eligibility; review PICO confused with synthesis PICO; no estimand, result hierarchy, thresholds, or deviation policy | compile natural language into typed predicates and synthesis questions; generate adversarial examples and ambiguity list | schema lint, logical contradiction tests, profile rule engine | approve scope, unresolved definitions, protocol freeze, registration |
| 2. Search and lawful retrieval | one database treated as exhaustive; RAG answer substitutes for search; syntax copied across platforms; illegal or unlogged downloads | query swarm creates source-specific strategies, known-item tests, citation chasing, registry and grey-source plans; imports authorized exports | PRESS-style rule checks, search replay, export/hash/count reconciliation, license checker | information-specialist review; licensed login/export and access decisions |
| 3. Selection | report confused with study; abstract used for final exclusion; outcome non-reporting used as exclusion; AI presented as an independent human | criterion agents return `met/not_met/unclear/not_reported` with anchors; hard-negative opponent seeks decisive exclusion evidence; uncertain records abstain | frozen predicate engine, duplicate/report linker, random tail audit | mode/profile-specific independent final eligibility and adjudication |
| 4. Multimodal document state | OCR text treated as the document; supplements lost; cross-page tables and figure data detached | parse XML/HTML/PDF text, layout, tables, figures and scans into one versioned document state; keep competing parses | checksum, coordinates, page render, table totals, caption/unit and cross-page constraints | resolve inaccessible, illegible, or materially discordant evidence |
| 5. Lineage and extraction | flat article rows; companion reports double counted; arms/timepoints/populations mixed; copied review tables treated as truth | report-study-arm-result entity resolution; independent text/table/vision candidates; source-anchored field extraction | deterministic arithmetic, range/unit/denominator checks, cross-report consistency, effect recomputation | mandated duplicate extraction and unresolved material conflicts |
| 6. RoB and missing evidence | one study score; tool mismatch; poor reporting automatically rated high; selective reporting conflated with missing studies | build signaling-question dossiers for exact results and proposed counterjudgments; construct result-availability matrix | official algorithm/rule adapter, protocol-registry-report comparison, ROB-ME/ROB-MEN adapter where applicable | final domain judgments, justified overrides, missing-evidence conclusion |
| 7. Poolability and analysis | “run all methods”; I-squared used as pooling rule; effect measures or estimands mixed; dependence ignored | estimand alignment matrix and proposal-opposition-judge poolability dossier; compile typed R manifest; execute deterministic analysis | manifest validator, independent effect and model recomputation, unit/dependency checks, clean rerun | poolability, primary model, justified deviations, data freeze |
| 8. Certainty and writing | GRADE as arithmetic score; null as universal threshold; claims exceed certainty; reporting checklist treated as quality proof | assemble domain evidence and absolute effects; compile claims from evidence graph; draft tables/text only from accepted nodes | GRADE rule prompts plus threshold checks, citation/identity resolver, numeric consistency and unsupported-claim scan | final certainty, language strength, authorship, disclosure and conclusion |
| 9. Review, release, and living update | generator reviews itself; persuasive response replaces verification; updates append studies without full reappraisal | heterogeneous reviewer lenses, strongest counter-explanation, executable correction loop; delta search and graph impact analysis | separate model/tool stack, changed-artifact verification, retraction/version monitor, full clean run | resolve critical findings, submit/release, trigger status change or retirement |

## 6. AI Architecture Derived From the Method

### Capability-based model team

Model names are configuration, not architecture. Expose narrow, typed action/observation interfaces and register capability slots such as:

- high-recall biomedical retrieval and query translation;
- long-context protocol reasoning;
- multilingual clinical interpretation;
- page-layout, table, figure, and equation understanding;
- entity resolution and graph consistency;
- quantitative/statistical reasoning;
- adversarial counterevidence generation;
- citation and identity verification;
- calibrated judging and abstention.

The router considers task/profile, document modality, risk, calibration stratum, prior failures, cost, latency, privacy, and tool permissions. A model is not eligible for a slot without task-level calibration evidence. Prompt and demonstration optimization is treated as compiled configuration evaluated on review-family splits, never hand-edited hidden methodology.

### Test-time compute policy

- Tier 0: deterministic parser/rule/tool only.
- Tier 1: one model plus schema and evidence-anchor validation for low-risk reversible work.
- Tier 2: proposer plus independent verifier when a plausible error can propagate.
- Tier 3: proposal-opposition-judge using heterogeneous models, evidence views, or tools for high-impact ambiguity.
- Tier 4: human adjudication when the authority requires it, calibration is out of scope, evidence is inaccessible, or conflicts survive the budget.

More calls are justified only when they improve prespecified risk-coverage or utility. Majority vote and model self-confidence are not sufficient evidence.

Long-context access is tested, not presumed. Position-shift probes, section-aware retrieval, and evidence-anchor recall audits must detect whether key facts are missed when they occur in the middle of reports or supplements. Automated judges use order swaps and generator/judge separation and remain below source, rule, and executable verifiers in the hierarchy.

### External verifier hierarchy

Prefer, in order:

1. exact schema, type, permission, checksum, and state-transition checks;
2. direct source identity and evidence-anchor resolution;
3. deterministic calculations and executable R analysis;
4. protocol/tool algorithms and cross-document constraints;
5. independent model critique using different evidence views;
6. human adjudication.

Semantic entropy and cross-model disagreement are escalation signals. They can detect some instability but cannot establish correctness because models can be consistently wrong. Conformal tail-risk methods are research candidates only after task-specific calibration and drift assumptions are demonstrated; their published guarantees do not automatically become a systematic-review false-exclusion guarantee.

### Security boundary

PDFs, webpages, retrieved records, supplements, and model memory are untrusted data. Their contents cannot authorize tool calls, change the protocol, reveal credentials, or modify state. Tool calls require typed permissions, idempotency keys, bounded retries, allowlisted destinations, and a scientific-action guard. Security evaluation must include indirect prompt injection, poisoned retrieval/memory, data exfiltration, and unauthorized action cases.

## 7. Evaluation Program

### Primary claims

Evaluate separately whether MetaWingman:

1. maintains the prespecified critical-error ceiling while increasing AI coverage;
2. reduces expert minutes without reducing end-to-end included-study and result recall;
3. improves source anchoring, lineage, and numerical reproducibility;
4. localizes failures well enough for selective escalation;
5. remains calibrated across review profiles, languages, document forms, models, and time.

### Reference standard

- Use original reports, supplements, registries, protocols, and analysis artifacts.
- Use the published review team's final labels and values as the expert reference; bind publisher corrections and exclude unresolved integrity cases from held-out scoring.
- Preserve ambiguity rather than forcing false certainty, and classify AI-reference disagreement separately from published-reference error, protocol ambiguity, inaccessible evidence, and legitimate multiple interpretations.
- Split by review or study family, not random fields, to prevent report and topic leakage.

### Benchmark strata

Include hard negatives, multiple reports, multiple arms, shared controls, cluster/crossover trials, non-English and scanned reports, cross-page tables, figures-only results, corrections/retractions, missing variance, inconsistent registry/publication data, and adversarial instructions embedded in documents.

### Outcomes

- screening: included-study recall, false-exclusion rate, AI selective coverage, and false-exclusion risk at each coverage level;
- retrieval: known-item recall, source coverage, reproducibility, and lawful-access attribution;
- parsing/extraction: anchor accuracy, field tolerance accuracy, unsupported-value rate, lineage precision/recall, and exact recomputation rate;
- appraisal: domain agreement, rationale completeness, calibration, and critical disagreement rate;
- synthesis: manifest correctness, estimand alignment, numerical equivalence, sensitivity completeness, and claim support;
- system: end-to-end critical error relative to the published expert reference, AI coverage, abstention quality, cost, latency, reproducibility, security utility, and drift.

Do not use accuracy alone for imbalanced screening. Report uncertainty by review and by result, plus risk-coverage and cost-quality frontiers.

### Controls and ablations

Controls: one strong LLM, generic RAG, single-model multi-agent, alternative routed model configurations, and the full MetaWingman AI-only pipeline.

Ablate router, test-time scaling, heterogeneous models, opposition, evidence graph, global document state, deterministic verifier, and uncertainty/abstention. Repeat each frozen configuration and randomize internal judge order where relevant. Human-AI synergy and human labor savings are outside this design.

### Validation phases

1. component fixtures and synthetic edge cases;
2. retrospective time-split reconstruction on public reviews;
3. externally held-out review families and providers;
4. preregistered prospective AI-only runs on newly arriving evidence batches, with answers sealed until run lock;
5. externally held-out AI configurations and review families with sealed published expert references and integrity gates;
6. monitored human-overseen deployment with drift, override, and incident review, without treating oversight as a comparison arm.

## 8. Implementation Order

### P0: Method contract and audit core

Add schemas for review profile and authority versions, protocol/synthesis questions, outcome hierarchy, decision thresholds, reviewer assignments, protocol deviations, document state, evidence assertions, lineage edges, extraction candidates, appraisal/missing-evidence dossiers, analysis manifests, and claims. Extend the append-only event ledger and graph so every accepted decision has actor, evidence, rule, version, and state transition.

### P1: Two validated vertical slices

1. Protocol-aware hard-negative selection with criterion anchors, abstention, and mode-specific reviewer rules.
2. Multimodal extraction with global document state, report-study-result lineage, independent candidates, and deterministic recomputation.

### P2: Scientific judgment workbench

Implement design-specific RoB adapters, ROB-ME/ROB-MEN, estimand alignment, poolability conference, GRADE/other certainty dossiers, and the claim compiler. AI completes the dossier first; final authority follows the selected mode and profile.

### P3: Prospective and living system

Implement search deltas, retraction/tool/model drift monitoring, graph impact propagation, amendment handling, and prospective workflow logging. Promote task automation only after its prespecified validation gate passes.

## 9. Explicit Non-Claims

The current literature supports researching and building this architecture. It does not yet establish that:

- a general LLM can conduct a comprehensive systematic search from literature QA alone;
- multiple LLM personas are independent reviewers;
- low semantic entropy means a decision is correct;
- conformal calibration from another domain controls systematic-review false exclusions;
- AI-only benchmark performance establishes superiority to humans or labor savings;
- an automated reviewer can validate a generator without external evidence and blinded checks;
- end-to-end autonomous scientific agents are already reliable enough for unattended decision-relevant evidence synthesis.

The verified source identities and transfer limits are maintained in [`methodology-source-registry.md`](../../metawingman/references/methodology-source-registry.md).
