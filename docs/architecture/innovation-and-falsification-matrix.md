# MetaWingman Innovation and Falsification Matrix

Status: candidate contributions, not established claims
Last checked: 2026-08-13

## Claim Discipline

MetaWingman reuses proven mechanisms including ReAct-style tool use, proposal-opposition-judge panels, retrieval-grounded generation, semantic-uncertainty signals, conformal risk control, multimodal document parsing, and model routing. Reuse is infrastructure, not novelty. A contribution may be claimed only when its MetaWingman-specific mechanism is implemented, compared against a credible baseline, and survives the prespecified ablation and held-out review-family evaluation.

## Contribution Hierarchy

The external story must not present a flat list of agents or features. It has four claim-bearing levels:

1. **System contribution - lifecycle-complete evidence synthesis scientist.** The system connects topic selection, protocol, retrieval, selection, multimodal extraction, report-study-result lineage, appraisal, deterministic synthesis, certainty, reporting, review, and living updates through one typed evidence state. Breadth is audited by `references/system-capability-matrix.json`; it means explicit workflow coverage, not equal native depth or validation for every review family.
2. **Discovery contribution - decision-aware topic opportunity control.** A time-bounded multidisciplinary evidence landscape converts graph gaps, discordance, update need, priorities and cross-domain bridges into operational review questions, then filters them through overlap, feasibility, contamination and diversity controls.
3. **Execution contribution - conclusion-directed evidence control.** Residual omission risk, criterion difficulty, source diversity, and downstream claim impact jointly choose the next evidence-acquisition or verification action and the test-time compute budget. This turns a fixed linear pipeline into a closed risk-control loop.
4. **Evaluation contribution - sealed topic rediscovery plus counterfactual protocol stress testing.** Historical and prospective topic tasks test whether the system chooses consequential questions; controlled protocol perturbations then test downstream adherence and causal software-error localization.

I1-I5 below are enabling mechanisms. I6-I8 are the primary discovery, execution and evaluation candidates. None is a paper claim until the stated falsification test passes.

## Candidate Contributions

| ID | Reused foundation | MetaWingman-specific optimization | Falsifiable hypothesis | Required comparison | Failure condition |
|---|---|---|---|---|---|
| I1 | RAG, provenance graphs, scientific workflow state | **Executable evidence compiler:** one typed graph joins protocol predicates, document coordinates, report-study-result lineage, derived statistics, appraisal, certainty, claims, freezes and living deltas; invalid downstream claims are blocked rather than merely annotated | Graph-constrained compilation lowers unsupported values and cross-stage lineage errors at matched coverage | generic RAG; provenance annotations without executable gates; full compiler | no reduction in unsupported/lineage critical errors, or benefit disappears after review-family clustering |
| I2 | uncertainty estimation, semantic entropy, conformal prediction, model routing | **Scientific risk-coverage controller:** calibrates task-specific asymmetric harms, evidence coverage, deterministic conflicts, rerun disagreement, verifier availability and optional model/provider diversity to choose compute, opposition or abstention | At a frozen false-exclusion or unsupported-value ceiling, the controller increases automated coverage versus fixed-call and confidence-threshold routing | one-call model; fixed proposer-judge; semantic entropy alone; full controller | risk ceiling violated on held-out families or coverage is not improved |
| I3 | debate, CRITIC, self-correction | **Counterevidence tournament:** roles are assigned by criterion and estimand; opposition must retrieve disconfirming source anchors and the judge receives randomized role/order views plus rule checks | Counterevidence-first judging reduces false exclusions and one-sided RoB/poolability errors without unacceptable abstention inflation | self-consistency; generic debate; opposition without retrieval; full tournament | no critical-error benefit, order sensitivity remains material, or retrieved opposition is mostly unsupported |
| I4 | OCR/VLM ensembles, document parsing | **Global multimodal result-state solver:** competing native-text, layout, table, figure and registry candidates are linked to result entities and reconciled with denominator, unit, arm, timepoint and cross-report constraints before acceptance | Global constraints improve result-level exactness and effect-size equivalence beyond the best parser or late ensemble | text-only; best single parser; unconstrained multimodal voting; full solver | gains occur only on easy text fields or deterministic checks fail to localize errors |
| I5 | workflow engines, living reviews, dependency graphs | **Change-impact evidence maintenance:** a new record, correction, retraction or model/parser drift event propagates only through affected lineage, synthesis, certainty and claim nodes, producing a minimal auditable rerun plan | Impact-scoped updates match full reruns on affected conclusions while reducing unnecessary recomputation and preventing stale claims | full rerun; timestamp-only update; dependency graph without scientific gates; full system | misses any materially affected claim or cannot reproduce full-rerun outputs |
| I6 | active-learning screening, iterative retrieval, known-item tests, statistical stopping, model routing | **Conclusion-directed evidence acquisition and verification:** protocol-criterion residual risk is multiplied by downstream claim impact and asymmetric harm to select source, query, retrieval, screening, verifier, and compute actions; stopping requires both evidence-coverage and conclusion-impact thresholds | At matched cost or false-exclusion ceiling, conclusion-directed control improves end-to-end included-evidence and claim accuracy over fixed Top-K, linear retrieval-screening, and confidence-only routing | fixed Top-K; SAFE/statistical stopping without claim impact; uncertainty-only routing; full controller | no held-out gain after review-family clustering, risk ceiling is violated, or the learned policy merely spends more compute everywhere |
| I7 | stage-attributed metrics, workflow traces, perturbation testing, failure taxonomies | **Counterfactual protocol stress test with causal error replay:** change exactly one protocol/estimand/time-bound predicate, rerun the dependency graph, and intervene on the earliest discrepant event to quantify whether the expected selection, analysis, certainty, and claim changes are recovered | Controlled protocol interventions expose hidden instruction non-adherence and localize error propagation more accurately than final-output scoring or post-hoc transcript labels | final-score benchmark; stage labels without intervention; trace taxonomy; full causal replay | perturbations do not produce predictable gold deltas, replay cannot recover downstream outputs, or attribution is unstable across equivalent event orderings |
| I8 | literature-based discovery, temporal knowledge graphs, scientific idea agents, priority setting and review-overlap checks | **Decision-aware topic opportunity control:** construct a cutoff-bounded evidence landscape, generate operational review questions from gaps, discordance, update signals, priorities and cross-domain bridges, then apply evidence-backed value, feasibility, nonduplication, contamination and portfolio-diversity controls | The full engine improves held-out Top-K published-topic concordance, false-opportunity rate and prospective decision relevance over bibliometrics, generic RAG, LLM-only ideation and graph-only link prediction at matched corpus and budget | citation trends; semantic gap map; LLM-only; graph-only; ResearchAgent/SciMON-style inspiration without review gates; full engine | performance is explained by target/model-memory leakage, venue prestige, duplicated paraphrases or extra compute; feasible novel topics are not improved on held-out or prospective cases |

## Full-Coverage Evidence Contract

Run `python scripts/audit_system_coverage.py` before any lifecycle-completeness claim. Report separately:

- lifecycle stages with an explicit state, gate, artifact route, and responsibility boundary;
- review profiles admitted to the shared workflow;
- native executable, generic guarded, structured-synthesis, and external-handoff analysis routes;
- schema/fixture, published-reconstruction, and prospective validation levels;
- known gaps and abstention or handoff paths.

Do not call a profile "fully supported" from shared workflow coverage alone. Do not call the system "validated end to end" while any required stage has only schema or fixture evidence.

## Cross-Cutting Experimental Contract

- Use only AI execution arms: single structured model, generic RAG, single-provider multi-agent, heterogeneous models without the evidence compiler, full MetaWingman, and one-at-a-time ablations.
- Repeat each frozen configuration at least three times for the pilot. Lock prompts, model/provider versions, tool versions, budgets, thresholds and stopping rules before held-out runs.
- Split by `review_family_id`; never tune on the test family. Aggregate uncertainty by review family, not by records or cells.
- Primary safety outcomes: critical-error rate, false-exclusion rate, unsupported-value rate and end-to-end result accuracy. Report coverage and selective accuracy jointly with risk.
- Attribute failures to protocol ambiguity, inaccessible evidence, parser, model, lineage, deterministic computation, tool, post-cutoff knowledge, published-review error or adjudication error.
- Do not claim a new foundation model, autonomous science, human equivalence, human superiority, labor savings, or general clinical validity from these experiments.

## Promotion Rule

A candidate contribution becomes a release or paper claim only when:

1. its implementation is reachable through the public skill workflow;
2. its benchmark artifacts and configuration hashes are immutable and legally usable;
3. the full system beats its direct mechanism baseline on the prespecified held-out metric without crossing a safety ceiling;
4. the corresponding ablation causes the predicted degradation;
5. repeated-run, position and judge-order sensitivity remain within frozen limits;
6. the claim wording is compiled from the measured scope and uncertainty.

Until then, call it a design hypothesis or engineering optimization.
