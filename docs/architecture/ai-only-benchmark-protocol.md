# AI-only benchmark protocol

Status: implementation-ready draft; thresholds and configurations are not frozen.

## Design

MetaWingman validation uses only AI execution. A benchmark case is reconstructed under the published review's historical search cutoff. Operational inputs are mounted separately from the published answers and post-cutoff evidence. Every preregistered AI configuration is repeated at least twice, and no human may alter a prompt, decision, extraction, tool action, or output during a run.

Humans are not an experimental arm and routine de novo human adjudication is not part of this benchmark. The published review team's final inclusion decisions, extraction tables, risk-of-bias judgments, and reported analyses form the `published_expert_reference`. If the publisher has issued a correction, only the verified corrected version may become `published_corrected_reference`. Retractions, unresolved expressions of concern, version conflicts, and material internal contradictions are held outside held-out scoring until the integrity state is resolved. Discordance is classified as AI-reference disagreement, reference ambiguity, protocol interpretation, post-cutoff effect, or tool failure; it is not silently relabeled as AI error.

The reference is selected because the published review represents a consequential expert work product, not because journal acceptance creates an oracle. Top general and field journals are oversampled for training and development, then broadened across domains and venue strata. No model-selection or performance score may use journal prestige as a quality feature.

Topic selection adds a stricter masking layer. The operational corpus excludes the target review's title, authors, DOI/PMID, journal, abstract, author keywords, direct citations, update descendants and all post-cutoff evidence. Runtime masking cannot erase provider-model pretraining; each case therefore records model version, declared training cutoff, memorization probes and residual contamination risk. Historical runs with an unresolved model-memory boundary measure published-topic concordance, not independent discovery. Prospective candidates must be registered before any later reference outcome exists.

## Configuration comparisons

Freeze configuration IDs, model versions, prompt hashes, pipeline and tool versions, maximum model calls, retry budgets, and ablations before held-out evaluation. Initial comparisons should include a single strong structured model, generic RAG, full MetaWingman, and one-at-a-time ablations of routing, opposition, evidence graph, multimodal document state, deterministic verification, and abstention.

Do not optimize prompts, thresholds, routing, or tools on held-out review families. Each `review_family_id` belongs to exactly one train, development, or test split.

## Recorded metrics

Primary metrics are critical-error rate, false-exclusion rate, unsupported-value rate, and end-to-end result accuracy. Secondary metrics include coverage, selective accuracy, abstention, precision/recall where defined, numerical equivalence, repeated-run agreement, all-repeats-correct rate, position sensitivity, judge-order sensitivity, wall-clock time, model calls, tokens, API cost, and local compute cost.

For topic selection, primary metrics are Top-1/3/10 framework-level rediscovery, false-opportunity rate and prospective decision relevance/answerability. Secondary metrics are field-level PICO/PECO and synthesis-route similarity, nonduplication, portfolio diversity, rank stability, cost and venue/domain strata. Journal prestige is a sampling and reporting stratum, not a score input or quality oracle.

Aggregate uncertainty by review family, not by treating records or extracted cells as independent. Prespecify asymmetric error weights and release ceilings before the held-out run.

## Inference boundary

This design can compare AI configurations and estimate agreement with published expert references, reliability, risk-coverage, latency, and cost. It cannot estimate accuracy against absolute truth, establish superiority or non-inferiority to humans, measure human-AI synergy, or claim saved human labor.

Machine-readable assets:

- `schemas/ai_only_evaluation_plan.schema.json`
- `schemas/ai_only_run_record.schema.json`
- `schemas/benchmark_candidate_registry.schema.json`
- `schemas/benchmark_discovery_catalog.schema.json`
- `schemas/benchmark_material_plan.schema.json`
- `schemas/topic_target_registry.schema.json`
- `schemas/topic_rediscovery_case.schema.json`
- `schemas/topic_rediscovery_report.schema.json`
- `schemas/top_journal_training_corpus.schema.json`
- `references/ai-only-evaluation-plan.template.json`
- `scripts/evaluate_ai_only.py`
- `scripts/export_benchmark_citations.py`
- `scripts/fetch_benchmark_materials.py`
- `scripts/harvest_top_journal_corpus.py`
- `research/benchmark-candidate-registry.json`
- `research/topic-rediscovery-target-registry.json`
- `research/meta-reproduction-discovery-catalog.json`
- `research/top-journal-training-corpus.json`
- `research/benchmark-material-plans/*.json`

Use the topic-target registry and discovery catalog for broad development and component-case intake. A topic-only target needs a verified formal identity, publication date, question framework and defensible pre-publication evidence boundary; it does not need complete extraction tables or analysis code. Every target also needs a publisher/Crossref/PubMed integrity audit, but metadata relations are not assumed complete: a correction found only on the publisher site still controls the benchmark artifact. Corrected papers use the corrected version only, while retractions or unresolved concerns block promotion. Promotion into the full-workflow strict candidate registry still requires a separate audit of historical cutoffs, artifact identity, licenses, answer sealing, family split, and the exact supported benchmark scope. A prestigious venue does not by itself establish scientific correctness or material completeness.

`harvest_top_journal_corpus.py` builds a large metadata-only intake from the official Europe PMC API. Abstracts are intentionally omitted. All records remain `unassigned_pending_family_audit`: family clustering, correction/retraction checks, lawful-material audit, and answer sealing must occur before any held-out split. The intake may support training and development immediately, but its raw size is not evidence of end-to-end benchmark readiness.

`cluster_review_families.py` adds a conservative title/author candidate layer without silently confirming relationships. It strips generic review and notice boilerplate, blocks common-token fan-out, records every candidate edge and generates only family-level split suggestions. Every family remains `blocked_pending_family_audit`, and the registry schema fixes `held_out_ready_families` at zero until explicit identifier, citation/update-lineage and integrity audits replace provisional clustering. This prevents a lexical cluster or single provider judgment from creating a supposedly clean test set.

Initial local pilots should favor small, complementary, explicitly versioned packages: BMJ COVID-19 therapies for living NMA, the PLOS antigen-test pair for living DTA, Nature Communications carbon pricing for screening-to-analysis, PLOS spinal-cord exercise for extraction/meta-regression, and HEPSANET or Decide-TB for controlled-IPD workflow guards. Fetch individual pinned files from very large repositories rather than cloning the whole repository; `cholera_positivity` is currently about 600 MB according to GitHub metadata.

Material plans classify each pinned artifact as `operational_input`, `documentation`, `sealed_reference`, or `sealed_post_cutoff`. The fetcher downloads only non-answer-bearing operational/documentation files by default, verifies expected bytes and SHA-256, and requires a complete locked `RUN_BOUNDARY.json` covering every preregistered AI-only repetition before sealed retrieval. An arbitrary or partial file cannot unlock answers. Network fetches are restricted to public HTTPS destinations and revalidated after redirects. `metadata_only` and `blocked` artifacts are never fetched. A material plan's `reproduction_ceiling` is the maximum defensible benchmark scope, not a promise that the paper can be reproduced end to end.
