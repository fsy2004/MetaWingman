# MetaWingman Compute and Deployment Budget

Status: architecture guidance
Last checked: 2026-08-12

## Short Answer

MetaWingman does not require a large local GPU in its recommended deployment. Search orchestration, provenance, screening state, deterministic extraction checks, and conventional R Meta-analysis are primarily network, storage, CPU, and model-API workloads. Local GPU demand appears only when users choose to run document vision or language models on their own hardware.

The current development machine has a 24-core/32-thread Intel Core i9-13900HX, 16 GB RAM, and an NVIDIA RTX 4060 Laptop GPU with 8 GB VRAM. It is sufficient for repository development, R analyses, PDF rendering/OCR, small quantized local models, and reduced-scale parser experiments. RAM is the tighter constraint for large PDF batches; the machine is not a sensible target for running several large multimodal models concurrently.

## Deployment Profiles

| Profile | Local requirement | Best use | Main constraint |
|---|---|---|---|
| Cloud-first default | 4-8 CPU cores, 16 GB RAM, no GPU, SSD | Most reviews; hosted multimodal/reasoning models with local audit and R | API cost, data policy, network latency |
| Hybrid private | 8-16 CPU cores, 32 GB RAM recommended, 8-16 GB VRAM optional | Local OCR/layout and redaction; remote high-reasoning calls for permitted content | Workflow complexity and two-provider calibration |
| Fully local research | 16+ CPU cores, 64 GB RAM recommended, 24-48 GB VRAM or multiple GPUs | Sensitive data or model-method research with local VLM/LLM ensembles | Hardware cost, maintenance, slower high-quality reasoning |
| Team service | 16+ CPU cores, 64-128 GB RAM, queue-backed workers; GPU pool only for local inference | Shared state, living updates, batch ingestion, organization routing | Operations, authentication, observability, governance |

These are planning ranges, not hard minimums. Exact requirements depend on model size, quantization, page resolution, concurrency, document count, and whether OCR/layout inference is CPU, GPU, or API based.

## Workload by Stage

| Stage | Dominant resource | Expected intensity |
|---|---|---|
| Topic, protocol, search design | Remote model calls and web/database I/O | Low local compute |
| Search import and deduplication | CPU, RAM, disk | Low to moderate; scales with record count |
| PDF rendering and OCR | CPU/RAM; optional GPU | Moderate and batchable |
| Multimodal table/figure extraction | Remote VLM or local GPU | Potentially high; page count is the main multiplier |
| Evidence graph and lineage | RAM, database I/O | Moderate; graph size is manageable for ordinary reviews |
| RoB/GRADE/poolability dossiers | Model reasoning and human review | Low local compute, potentially high token use |
| R Meta-analysis | CPU and RAM | Usually low; GOSH, Bayesian MCMC, bootstrap, and large NMA can be higher |
| AI reviewer and living update | Model calls, scheduler, incremental search | Low per event; cost accumulates over time |

## Cost and Compute Controls

The router should budget inference by risk and uncertainty, not assign the strongest model to every page.

- Use deterministic parsers and small/cheap models for metadata, normalization, and easy records.
- Escalate only low-confidence, high-impact, conflicting, or high-risk cases.
- Cache by document hash, page hash, prompt version, model version, and tool version.
- Batch independent pages and records where the provider and privacy policy permit it.
- Cap retries, candidate count, debate rounds, and test-time compute per task.
- Stop early when independent channels agree and external validators pass.
- Record tokens, API and local-compute cost, latency, and energy-relevant runtime in the event ledger. Reference-integrity audit effort is corpus operations metadata, not an AI performance endpoint.

## Benchmark the Budget

Report resource use per 1,000 search records and per 100 full-text reports:

- CPU time, peak RAM, peak VRAM, disk growth, and wall-clock time;
- model input/output tokens and provider cost by workflow stage;
- parser and model cache hit rates;
- number of proposal/opposition/judge rounds;
- AI coverage at the prespecified error or recall threshold;
- reference-integrity audit time and excluded-case count as operational metadata, not an AI performance or labor-savings endpoint;
- quality-cost curves for each model-routing policy.

The main comparison should be constrained performance: for example, the least costly configuration that maintains the required included-study recall and unsupported-value ceiling. Raw task accuracy without cost, abstention, and manual burden is insufficient.

## Recommendation for This Project

1. Develop P0 and P1 on the current machine with a cloud-first or hybrid architecture.
2. Increase system RAM to 32 GB before routine large PDF batches or simultaneous R, OCR, and local-model work.
3. Treat the 8 GB RTX 4060 as an optional accelerator for OCR/layout and small quantized models, not as the primary multi-agent inference cluster.
4. Keep provider adapters modular so sensitive projects can switch to local or institution-approved endpoints.
5. Delay dedicated GPU infrastructure until benchmark logs show that local inference is cheaper or required by data governance at the target quality level.

## Current DeepSeek Development Provider

The first live adapter uses DeepSeek's official OpenAI-compatible endpoint. On 2026-08-13, the account-visible model list and a minimal structured request were verified for `deepseek-v4-flash` and `deepseek-v4-pro`; the legacy `deepseek-chat` and `deepseek-reasoner` identifiers had been deprecated. Official pricing at that check reported a 1M-token context and cache-miss input/output prices of USD 0.14/0.28 per million tokens for Flash and USD 0.435/0.87 for Pro. Prices and model names are provider state, so each frozen benchmark must query and record the live model list and current pricing rather than rely on this paragraph.

DeepSeek is sufficient for inexpensive text classification, question generation, structured candidates and development-scale critique. It is not a bundled vision/PDF parser, and using Flash and Pro from the same provider does not create independent-provider evidence. High-risk proposal-opposition-judge routing therefore remains abstained until calibrated task evidence and a second provider or defensibly independent external verifier are available. No dedicated local GPU is needed for this API-first stage; corpus indexing, graph construction and R analysis remain CPU/RAM workloads.
