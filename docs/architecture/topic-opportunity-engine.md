# Topic Opportunity Engine

Status: implementation and evaluation contract, not a validated scientific claim
Last checked: 2026-08-13

## Problem Definition

MetaWingman must solve two related but non-interchangeable tasks.

1. **Historical topic rediscovery:** using only evidence available at a frozen date, rank review questions and test whether a later published human-authored review question appears near the top.
2. **Prospective topic discovery:** register review questions that do not yet have a satisfactory synthesis, then observe their evidence growth, decision use, later review activity, and feasibility.

The historical task measures concordance with a consequential human product. It does not make the published paper an oracle and it does not establish AI superiority to people. Runtime masking also cannot remove information already absorbed during model pretraining; `independent discovery` is permitted only when the model-memory boundary is supported or the prediction was prospectively registered before the reference existed.

## Core Method

The method is a closed evidence-to-question loop:

```text
time-bounded multidisciplinary corpus
  -> typed temporal evidence landscape
  -> graph paths, gaps, update signals, priorities and cross-domain bridges
  -> operational review-question candidates
  -> novelty/overlap opposition and feasibility verification
  -> frozen value-risk scoring
  -> diversity-aware topic portfolio
  -> protocol and full MetaWingman execution
  -> outcome and living-update feedback
```

The evidence landscape contains dated primary studies, registrations, prior reviews and protocols, guidelines, priority statements, concepts, PICO/PECO elements, results, claims and unresolved uncertainties. Every node and edge retains source identity, date and provenance status. Candidate scores are not model opinions: each signal points to evidence nodes and records whether it is calibrated, heuristic or unavailable.

The first hosted-model boundary is now executable. `propose_topics.py` requires explicit authorization to transmit a validated landscape, applies a prompt-size ceiling, and asks the model only for frameworks, evidence-node references, interpretations and disconfirmation searches. Invalid JSON or schema output receives one recorded repair attempt; surviving unknown nodes or numeric self-scores cause abstention rather than silent filling. Output remains `requires_independent_signal_audit`; separate overlap/feasibility retrieval and frozen scoring must convert proposals into `topic_candidate` records.

Eight positive signals are kept separate:

- decision relevance;
- unresolved uncertainty or discordance;
- feasibility;
- evidence maturity;
- nonduplication;
- need for an update or purposeful replication;
- equity priority;
- cross-domain value.

Contamination and ambiguity are explicit risk penalties. Hard gates reject a non-operational question, too few primary studies or source families, inadequate known-item recall, unjustified overlap with an existing or active review, unavailable high-impact signals, or failed temporal/identity leakage controls. A diversity-aware greedy portfolio discourages repeated paraphrases of the same question.

This first implementation does not require training a new deep network. LLM extraction and proposal, sparse/dense retrieval, graph topology and deterministic gates are separable components. Learned temporal link prediction, graph neural networks or a trained ranking policy enter only after a sufficiently large, leakage-controlled development set exists and must beat the transparent graph/rule baselines.

## Corpus and Benchmark Policy

Development intake is intentionally broad across medicine, public health, psychology, ecology, climate, economics, education and social policy. High-impact general and field journals are oversampled because their topics are consequential human research products, but venue is only a stratum and sampling signal. It is not a quality label, material-completeness guarantee or score input.

Use three nested corpora:

| Corpus | Admission | Permitted use |
|---|---|---|
| Broad development corpus | verified formal identity and lawful metadata/full text | ontology, graph extraction, prompts, candidate generation, error discovery |
| Topic rediscovery targets | verified question, publication date and recoverable pre-publication evidence boundary | sealed historical framework-level concordance only |
| Full workflow reconstruction | strict cutoff, materials, license, family split, sealed answers and run lock | search, screening, lineage, extraction, appraisal and synthesis evaluation |

Targets and their update descendants must remain outside operational inputs. Hide title, authors, DOI/PMID, journal, abstract, author keywords, direct citations and post-publication descendants. Freeze candidate-universe construction before scoring. Record model provider/version, declared training cutoff, memorization probes and contamination risk. A model with unknown training data may report historical concordance but not independent rediscovery.

The curated broad registry contains 15 publisher-verified review identities spanning 39 domain tags. It is complemented by a reproducible top-journal metadata intake harvested from Europe PMC. Large-scale intake records are development candidates only: review-family clustering, historical-boundary audit, lawful-material checks, and sealing are required before promotion. Three curated targets have a publisher-methods-verified initial historical boundary and none is yet `sealed_case_ready`. Two targets have publisher corrections bound to `use_corrected_version_only`; this also demonstrates why Crossref relation metadata is checked but never treated as a complete correction/retraction audit.

## Evaluation

### Historical endpoints

Primary topic endpoints:

- Top-1, Top-3, Top-10 and area-under-hit-rate by review family;
- framework similarity and exact match for population, intervention/exposure, comparator, outcome, design and synthesis route;
- agreement with the published expert question framework plus separately audited decision relevance, feasibility and nonduplication;
- false-opportunity rate among already saturated, infeasible, empty-evidence and false-novelty controls;
- cross-domain portfolio coverage and duplicate-topic rate;
- repeated-run rank stability, provider/model sensitivity, token cost and latency.

The published review team's final question is the `published_expert_reference`. A verified correction replaces it; retractions, unresolved integrity conflicts and materially ambiguous question scopes block held-out scoring. No routine de novo human adjudication is added. Agreement is called concordance or rediscovery, never truth-oracle accuracy or human superiority.

### Prospective endpoints

Preregister the graph snapshot, candidates, policy, model version and portfolio. At fixed follow-up dates assess:

- whether evidence volume crossed the prespecified answerability threshold;
- whether a review, guideline, HTA or priority-setting body addressed the question;
- whether the candidate changed a real decision or exposed a material evidence gap;
- whether the review remained feasible and nonduplicative;
- whether predicted uncertainty or update need matched observed evidence change.

Prospective confirmation is stronger for discovery claims than retrospective matching, but it still requires source-grounded adjudication and cannot be replaced by citations or journal acceptance alone.

## Baselines and Ablations

Baselines:

1. publication-count and citation-trend bibliometrics;
2. semantic-cluster gap detection without a graph;
3. single strong LLM with the same corpus and budget;
4. generic RAG idea generator;
5. graph topology or temporal link prediction without semantic question state;
6. ResearchAgent/SciMON-style literature inspiration plus critique without review-specific gates;
7. full topic opportunity engine.

One-at-a-time ablations remove temporal masking, cross-domain edges, priority/guideline nodes, overlap opposition, feasibility verification, decision relevance, uncertainty/discordance, source diversity, ambiguity/contamination penalties, active evidence acquisition, model routing and portfolio diversity. A component is supported only if its removal causes the preregistered degradation on held-out review families without improving a more important safety endpoint.

## Screening Link

Topic screening and study screening share a risk-control principle but use different labels and losses. The topic engine filters candidate questions for value, novelty and answerability. Protocol-aware study screening seeks very high included-study recall and controls false exclusions. ASReview-style active learning is a prioritization mechanism; SAFE is a practical heuristic; statistical stopping estimates whether a recall target has been achieved under stated assumptions. Conformal risk control may later calibrate nested candidate sets or abstention thresholds, but no conformal guarantee is claimed until exchangeability, loss monotonicity, calibration size and domain-shift assumptions are tested by review family.

## Implementation Roadmap

### P0: typed and leakage-safe

- `temporal_evidence_landscape.schema.json`
- `topic_proposal_batch.schema.json`
- `topic_candidate.schema.json`
- `topic_opportunity_decision.schema.json`
- `topic_rediscovery_case.schema.json`
- `topic_rediscovery_report.schema.json`
- deterministic gates, utility decomposition, diverse portfolio and framework evaluator
- evidence-bound hosted-model proposal CLI with explicit transfer consent and no model self-scoring

### P1: corpus and graph construction

- normalize concepts with domain ontologies while retaining raw text;
- extract dated report-study-result-question relations with source anchors;
- index registries, existing reviews, protocols, guidelines, priority statements and retractions;
- add sparse, dense, citation and graph-path retrieval with source-family audits;
- build hard-negative topic controls and model-memory probes.

### P2: active discovery and screening

- proposal-opposition-judge candidate generation where opposition retrieves overlap and disconfirming evidence;
- conclusion-aware feasibility searches connected to the existing acquisition controller;
- calibrated active-learning study screening and statistically defensible stopping comparisons;
- learned ranker/router only after frozen development data are sufficient.

### P3: sealed and prospective validation

- broad multi-domain top-journal historical targets, split by review family and time;
- full-workflow subset with legally usable reconstruction artifacts;
- prospective candidate registry and living evidence follow-up;
- repeated-model/provider runs, cost-quality curves, failure taxonomy and ablations.

## Primary and Official Sources

- Thomas J, Kneale D, McKenzie JE, Brennan SE, Bhaumik S. [Cochrane Handbook Chapter 2: determining review scope and questions](https://training.cochrane.org/handbook/current/chapter-02), Version 6.5, 2024.
- van de Schoot R, et al. [An open source machine learning framework for efficient and transparent systematic reviews](https://www.nature.com/articles/s42256-020-00287-7). *Nature Machine Intelligence*. 2021;3:125-133. DOI 10.1038/s42256-020-00287-7.
- Callaghan MW, Muller-Hansen F. [Statistical stopping criteria for automated screening in systematic reviews](https://doi.org/10.1186/s13643-020-01521-4). *Systematic Reviews*. 2020;9:273.
- Boetje J, van de Schoot R. [The SAFE procedure](https://doi.org/10.1186/s13643-024-02502-7). *Systematic Reviews*. 2024;13:81.
- Wang Q, Downey D, Ji H, Hope T. [SciMON](https://aclanthology.org/2024.acl-long.18/). ACL 2024, pp. 279-299. DOI 10.18653/v1/2024.acl-long.18.
- Baek J, Jauhar SK, Cucerzan S, Hwang SJ. [ResearchAgent](https://aclanthology.org/2025.naacl-long.342/). NAACL 2025, pp. 6709-6738. DOI 10.18653/v1/2025.naacl-long.342.
- Si C, Yang D, Hashimoto T. [Can LLMs Generate Novel Research Ideas?](https://proceedings.iclr.cc/paper_files/paper/2025/hash/ea94957d81b1c1caf87ef5319fa6b467-Abstract-Conference.html). ICLR 2025.
- Marwitz T, et al. [Predicting new research directions in materials science using large language models and concept graphs](https://www.nature.com/articles/s42256-026-01206-y). *Nature Machine Intelligence*. 2026;8:535-544.
- Weis JW, Jacobson JM. [Learning on knowledge graph dynamics provides an early warning of impactful research](https://www.nature.com/articles/s41587-021-00907-6). *Nature Biotechnology*. 2021;39:1300-1307.
- Angelopoulos AN, Bates S, Fisch A, Lei L, Schuster T. [Conformal Risk Control](https://proceedings.iclr.cc/paper_files/paper/2024/hash/f3549ef9b5ff520a7e41ff3cc306ab2b-Abstract-Conference.html). ICLR 2024.
- Centre for Reviews and Dissemination. [PROSPERO registration guidance](https://www.crd.york.ac.uk/PROSPERO/documents/Guidance%20for%20registering%20human%20studies.pdf).
- James Lind Alliance. [Priority Setting Partnership process](https://www.jla.nihr.ac.uk/about-the-james-lind-alliance/downloads/JLA%20PSP%20process%20complete_final2.pdf).
