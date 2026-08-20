# Clinical Question and Synthesis Co-Design
Status: current scientific mainline design

Last source check: 2026-08-20

## Decision

MetaWingman will concentrate its scientific contribution on two coupled
problems:

1. **Clinical question and synthesis co-design.** The system searches jointly
   over the clinically useful question, review family, estimand, eligible
   evidence, and valid synthesis route. It must be able to narrow, broaden,
   split, redirect, or decline a proposed Meta-analysis when the evidence does
   not support the original formulation.
2. **A source-grounded full-review operating loop.** One persistent evidence
   state carries the review from topic selection through protocol, search,
   screening, multimodal extraction, lineage, appraisal, analysis, certainty,
   writing, review, and living updates. Model reflection is accepted only when
   it changes typed state through source or tool observations.

ReviewVerse-style published-review reconstruction remains training and
evaluation infrastructure. It is not presented as a third headline method.
Likewise, debate, routing, retrieval-augmented generation, tree search, and
uncertainty estimates are enabling mechanisms, not standalone MetaWingman
contributions.

## Problem Formulation

A review topic is not a title-generation task. The design object is a joint
state:

```text
Z = (C, Q, R, E, M, D, V)
```

- `C`: clinical decision context: stakeholder, setting, decision, feasible
  action, time horizon, patient-important outcomes, equity/subgroups, and
  implementation constraints.
- `Q`: operational question scope using the appropriate framework (for example
  PICO, PECO, PIRD, prognostic-factor, or prediction-model framing).
- `R`: review family and conduct/reporting/appraisal authority profile.
- `E`: target estimand, including contrast, population, outcome scale, time
  point, and handling of multiplicity or intercurrent events when relevant.
- `M`: synthesis route and effect measure, including an explicit `no_pooling`
  option.
- `D`: observed evidence landscape and data availability.
- `V`: validity state: overlap, leakage, identifiability, poolability, bias,
  access, and unresolved uncertainty.

The engine does not ask a model to emit one scalar quality score. It uses
evidence-linked objective fields plus hard gates. A candidate can be clinically
important yet infeasible, statistically feasible yet clinically trivial, or
novel only because its scope is incoherent. Those states must remain distinct.

## Search Space

### Clinical actions

The action vocabulary is bounded and auditable:

- narrow or broaden population, intervention/exposure, comparator, outcome,
  follow-up, setting, or design;
- split a heterogeneous question into linked review questions;
- merge clinically equivalent aliases without merging distinct estimands;
- change the review family when the clinical intent and evidence type disagree;
- change effect measure or synthesis route when assumptions are violated;
- route to pairwise, network, diagnostic, prognostic, prediction-model,
  prevalence/incidence, harms, dose-response, IPD, multilevel/multivariate,
  umbrella, qualitative/mixed, SWiM, or no-pooling conduct;
- request more evidence, abstain, or reject a duplicate/non-actionable topic.

The method registry must describe each route's admissible question types,
required fields, effect measures, minimum data shape, principal assumptions,
failure conditions, supported R adapter, and non-pooling fallback. The current
method authorities remain `metawingman/references/review-types.md` and
`metawingman/references/analysis-methods.md`.

### Search roles

The roles are capabilities with typed inputs and outputs, not personas:

- **Clinical framer:** converts a care or policy uncertainty into decision
  context and patient-important outcome priorities.
- **Evidence scout:** builds a time-bounded landscape, overlap map, known-item
  tests, and access/lineage feasibility evidence.
- **Methodologist:** enumerates compatible estimands and synthesis routes and
  exposes their assumptions.
- **Proposer:** creates alternative joint states rather than paraphrased titles.
- **Opposition agent:** seeks duplication, outcome substitution, unidentifiable
  estimands, sparse networks, incompatible thresholds/time points, and hidden
  access or reporting failures.
- **Judge/evolver:** applies executable gates, compares evidence-linked
  candidates, records why one branch was retained, and mutates promising
  branches within a fixed compute budget.

Search begins with deterministic seeds from the temporal evidence graph. Model
generation supplies candidate mutations. External checks supply observations.
The frontier receives more test-time compute only when uncertainty and
downstream impact justify it. A final portfolio includes selected, reserve,
rejected, and abstained candidates with branch histories.

## Full-Review Operating Loop

### Persistent review case state

The project state is a versioned graph, not a chat transcript. Its scientific
lineage is:

```text
record -> report -> study/trial -> arm/cohort -> result -> estimand
       -> synthesis -> certainty -> claim
```

The state also retains protocol predicates, database exports, search versions,
document hashes, layout objects, evidence spans, disagreements, tool receipts,
model/provider versions, costs, abstentions, and human responsibility events.
Every action consumes a state revision and emits a validated observation plus
an event-ledger entry. Free-text reasoning may explain a transition but cannot
be the transition itself.

### Multimodal document state

Each report has one global document state joining born-digital text, OCR text,
page image, layout blocks, tables, figures, captions, supplements, and
cross-references. Parser ensembles may propose objects, but field-level
verification and report-study-result lineage decide whether an extracted value
can enter analysis. A high document-level parsing score never licenses an
unsupported numeric field.

### Reflection and learning

Reflection follows `propose -> oppose -> verify -> revise/abstain`:

1. identify the exact state assertion at risk;
2. retrieve or execute the independent observation needed to test it;
3. attach source spans, identifier resolution, schema checks, or deterministic
   R/Python recomputation;
4. revise the typed state or preserve the disagreement;
5. store the failure and successful repair as a replayable training candidate.

Same-model self-critique is never counted as independent verification. The
first trainable additions are bounded components: question-method compatibility
ranking, source-support verification, and task/risk routing. The main reasoning
model remains provider-neutral. Published reviews are `published_reference`
labels rather than infallible truth; corrections, retractions, family leakage,
and post-cutoff information are handled before examples are frozen.

## Borrowed Mechanisms and Boundaries

| Primary source | Mechanism adopted | MetaWingman boundary |
|---|---|---|
| [AI Scientist, Nature 2026](https://www.nature.com/articles/s41586-026-10265-5) and [ERA, Nature 2026](https://www.nature.com/articles/s41586-026-10658-6) | lifecycle checkpoints, candidate mutation, tree search, executable scoring | only evidence/tool-verifiable objectives may prune scientific branches |
| [Co-Scientist, Nature 2026](https://www.nature.com/articles/s41586-026-10644-y) | generation, reflection, ranking, evolution, meta-review, tournament compute | Elo or model preference is not scientific truth; ranking is evidence constrained |
| [Virtual Lab, Nature 2025](https://www.nature.com/articles/s41586-025-09442-9) and [DeepRare, Nature 2026](https://www.nature.com/articles/s41586-025-10097-9) | host plus differentiated specialists, tools, traceable evidence, validate/refute loop | multiple model roles are not independent experts; sources and tools carry the evidential weight |
| [OpenScholar, Nature 2026](https://www.nature.com/articles/s41586-025-10072-4) | domain literature store, retrieval, cited synthesis, expert evaluation | literature QA cannot replace reproducible database search or recall auditing |
| [Robin, Nature 2026](https://www.nature.com/articles/s41586-026-10652-y) | continuous literature-analysis-observation-revision state | review observations are source/tool results, not simulated experiments |
| [MIRA, Nature 2026](https://www.nature.com/articles/s41586-026-10675-5) | sandboxed action space and persistent case interaction | access, download, registration, and publication actions remain permission governed |
| [AMIE, Nature 2026](https://www.nature.com/articles/s41586-026-10764-5) | longitudinal state and authoritative guideline grounding | guidelines constrain conduct but do not replace primary-study evidence |
| [Hallucination incentives, Nature 2026](https://www.nature.com/articles/s41586-026-10549-w) | open rubrics, explicit error cost, controllable abstention | every benchmark exposes asymmetric scientific loss; guessing is not rewarded |
| [Self-RAG, ICLR 2024](https://openreview.net/forum?id=hSyW5go0v8) and [CRITIC, ICLR 2024](https://openreview.net/forum?id=Sx038qxjek) | adaptive retrieval and tool-interactive critique | external observations, not introspection alone, authorize correction |
| [Multiagent Debate, ICML 2024](https://proceedings.mlr.press/v235/du24e.html) and [Mixture-of-Agents, ICLR 2025](https://proceedings.iclr.cc/paper_files/paper/2025/hash/5434be94e82c54327bb9dcaf7fca52b6-Abstract-Conference.html) | proposal-opposition-judge and heterogeneous aggregation | correlated errors are measured; vote count is never an evidence rule |
| [Nougat, ICLR 2024](https://proceedings.iclr.cc/paper_files/paper/2024/hash/a39a9aceda771cded859ae7560530e09-Abstract-Conference.html) and [OmniDocBench, CVPR 2025](https://openaccess.thecvf.com/content/CVPR2025/html/Ouyang_OmniDocBench_Benchmarking_Diverse_PDF_Document_Parsing_with_Comprehensive_Annotations_CVPR_2025_paper.html) | scientific-document parsing and multi-level parser evaluation | final evaluation is field and lineage specific |
| [Semantic entropy, Nature 2024](https://www.nature.com/articles/s41586-024-07421-0), [Conformal Risk Control, ICLR 2024](https://proceedings.iclr.cc/paper_files/paper/2024/hash/f3549ef9b5ff520a7e41ff3cc306ab2b-Abstract-Conference.html), and [RouteLLM, ICLR 2025](https://proceedings.iclr.cc/paper_files/paper/2025/hash/5503a7c69d48a2f86fc00b3dc09de686-Abstract-Conference.html) | uncertainty signals, calibrated decision policies, and quality-cost routing | calibration is profile- and loss-specific; no score is a production stopping guarantee until prospectively validated |

## Evaluation Contract

The benchmark has one execution arm: AI-only. Published expert work supplies a
time-sealed reference and is not counted as a contemporaneous human workflow
arm. The system receives only material available before the registered cutoff.
Target title, authors, identifiers, descendants, final included-study set, and
post-cutoff evidence are sealed from generation.

### Baselines

1. direct single-model question and method proposal;
2. current topic-opportunity score without joint method search;
3. retrieval plus biomedical schema and fixed method route;
4. joint search without opposition/reflection;
5. the full evidence-state system.

### Primary measurements

- top-K recovery of a clinically coherent review opportunity;
- critical eligibility false exclusion and search known-item recall;
- invalid review-family, estimand, effect-measure, or synthesis-route rate;
- unsupported source, value, lineage edge, certainty judgment, and claim rate;
- selective risk-coverage curve with abstention;
- repeated-run reliability and first-divergence stage;
- wall time, CPU/GPU time, peak memory, tokens, API cost, and storage growth;
- prospective topic yield and update impact after temporal registration.

Exact reproduction of a published conclusion is not the sole success target.
A defensible narrower question, a justified no-pooling decision, or rejection
of a flawed/duplicate historical topic can be correct. Such departures require
explicit evidence and are scored separately from simple match.

### Required ablations

- remove clinical decision context;
- freeze review family and synthesis method before evidence inspection;
- remove the opposition role;
- replace external verifiers with same-model reflection;
- remove the evidence graph or global document state;
- use fixed rather than risk-adaptive test-time compute;
- use one model/role for all tasks;
- remove review-profile specialist packs;
- remove abstention-aware open rubrics.

## Delivery Gates

- **P0 - contracts and sealed benchmark:** schemas, method registry, leakage
  controls, clinical-decision fixtures, server preflight, and published-reference
  benchmark cases.
- **P1 - joint design engine:** deterministic route enumeration, evidence-linked
  tree search, proposal-opposition-judge, portfolio output, and topic/method
  benchmark.
- **P2 - full operating loop:** persistent review case state, multimodal global
  document state, report-study-result lineage, source/tool reflection, and
  type-specific appraisal/analysis specialists.
- **P3 - learned control and living validation:** bounded ranker/verifier/router
  training, calibrated selective policies, prospective topic registration,
  living updates, and matched-cost ablations.

The standalone skill and provider-backed agent share these contracts. The skill
must not embed a provider client or credential. The runtime may use any provider
that satisfies the existing model-provider contract, but model availability is
never a substitute for database access, lawful full text, deterministic
analysis, or final human responsibility.
