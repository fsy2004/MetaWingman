# MetaWingman Compute and Deployment Budget

Status: architecture guidance
Last checked: 2026-08-20

## Short Answer

MetaWingman's production workflow is not primarily a foundation-model training workload. Search orchestration, provenance, screening state, deterministic extraction checks, and conventional R Meta-analysis are primarily network, storage, CPU, and model-API workloads. GPU demand comes from local document vision, concurrent local inference, bounded encoder training, and large parser/benchmark batches.

The workstation description retained in the 2026-08-12 history was adequate for repository development and reduced-scale experiments, but it is not the target for the new server mainline. Server sizing below is a project recommendation to be tested by preflight and pilot telemetry, not a measured minimum.

## Deployment Profiles

| Profile | Local requirement | Best use | Main constraint |
|---|---|---|---|
| Cloud-first default | 4-8 CPU cores, 16 GB RAM, no GPU, SSD | Most reviews; hosted multimodal/reasoning models with local audit and R | API cost, data policy, network latency |
| Hybrid private | 8-16 CPU cores, 32 GB RAM recommended, 8-16 GB VRAM optional | Local OCR/layout and redaction; remote high-reasoning calls for permitted content | Workflow complexity and two-provider calibration |
| Fully local research | 16+ CPU cores, 64 GB RAM recommended, 24-48 GB VRAM or multiple GPUs | Sensitive data or model-method research with local VLM/LLM ensembles | Hardware cost, maintenance, slower high-quality reasoning |
| Team service | 16+ CPU cores, 64-128 GB RAM, queue-backed workers; GPU pool only for local inference | Shared state, living updates, batch ingestion, organization routing | Operations, authentication, observability, governance |

These are planning ranges, not hard minimums. Exact requirements depend on model size, quantization, page resolution, concurrency, document count, and whether OCR/layout inference is CPU, GPU, or API based.

## Recommended Mainline Server

### Preferred research configuration

- 2 x NVIDIA L40S, 48 GB ECC VRAM per GPU;
- 32-48 vCPU;
- 128 GB RAM minimum, 256 GB preferred for concurrent PDF parsing, indexing,
  training, and R jobs;
- 4 TB local NVMe plus an external backup/object-storage target;
- stable 1 Gbps network egress;
- Ubuntu 22.04 LTS or 24.04 LTS, a driver/CUDA combination selected against the
  pinned PyTorch wheel, Docker, and NVIDIA Container Toolkit.

NVIDIA lists the L40S with 48 GB GDDR6 ECC memory, 350 W maximum power, and no
MIG or NVLink support ([official L40S specifications](https://www.nvidia.com/en-us/data-center/l40s/)). Therefore the two cards are separate workers; their memory must not be described as one 96 GB model address space. The intended allocation is concurrent independent work: GPU 0 for document vision/local inference and GPU 1 for bounded training or benchmark replicas, with jobs free to swap roles.

### Lower-cost configurations

| Configuration | Project use | Important limit |
|---|---|---|
| 1 x L40S 48 GB, 24-32 vCPU, 96-128 GB RAM, 2 TB NVMe | Recommended minimum for the complete mainline | Run parser, training, and local inference jobs sequentially |
| 1 x RTX 6000 Ada 48 GB, 24-32 vCPU, 96-128 GB RAM, 2 TB NVMe | Workstation-style 48 GB alternative | NVIDIA specifies 48 GB ECC and 300 W, but hosting and cooling remain provider responsibilities ([official specification](https://www.nvidia.com/en-us/products/workstations/rtx-6000/)) |
| 1 x RTX 5090 32 GB, 24 vCPU, 96 GB RAM, 2 TB NVMe | Economical development and bounded-model training | 32 GB constrains larger local VLM/LLM concurrency; NVIDIA specifies 575 W total graphics power ([official specification](https://www.nvidia.com/en-us/geforce/graphics-cards/50-series/rtx-5090/)) |

An A100 80 GB class instance is an escalation option only when a measured pilot
requires a larger single-GPU memory space or high-memory-bandwidth local model.
NVIDIA specifies 80 GB and more than 2 TB/s memory bandwidth for that variant
([official A100 page](https://www.nvidia.com/en-us/data-center/a100/)). It is not
required for the current BiomedBERT components or the P0/P1 controller.

### Storage layout for a 4 TB node

- 200 GB: operating system, containers, Python/R environments, and source;
- 1.5 TB: lawfully acquired corpus objects, XML/PDF, and rendered pages;
- 1 TB: model, tokenizer, OCR, embedding, and provider-response caches;
- 1 TB: runs, checkpoints, metrics, logs, and benchmark replicas;
- 300 GB: free-space reserve for atomic writes and recovery.

Keep source, corpus, cache, run, checkpoint, and receipt roots distinct. Raw full
text and credentials stay outside Git. A second copy of irreplaceable manifests,
hashes, metrics, and approved checkpoints must live outside the rented node.

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

1. Use one 2 x L40S server as the preferred all-in-one research node; choose one
   L40S when budget matters more than concurrency.
2. Run P0 contracts, evidence graphs, database ingestion, and deterministic R on
   CPU; do not reserve GPU for those jobs.
3. Use the GPUs for PDF vision/layout, local model inference, bounded component
   training, and repeated benchmark replicas.
4. Use `deepseek-v4-flash` as the single programmatic text API behind the
   provider-neutral contract. Codex carries most interactive development and
   source review. A second commercial provider is not a P0-P3 prerequisite;
   deterministic and source verifiers remain mandatory even when repeated model
   calls agree.
5. Start with the existing 110M-class component jobs, then add question-method
   ranking, source-support verification, and risk-cost routing. Do not plan a
   foundation-model pretraining run for this project.
6. Promote to A100 80 GB or a newer 80-96 GB single-GPU class only after recorded
   OOM, throughput, or quality-cost evidence shows that the 48 GB route is the
   limiting factor.

## Current external-provider development

The latest retained live receipt is
`validation-output/live-provider/deepseek-probe-2026-08-20.json`. It records one
successful `deepseek-v4-flash` call with 36 prompt tokens, 5 completion tokens,
and 41 total tokens; the credential source is recorded as an environment
variable and no secret value is present. This verifies that single call and the
provider contract on 2026-08-20. It does not establish task accuracy, future
model availability, price, or an independent second model family.

DeepSeek Flash is the default text reasoning provider for repeatable server jobs. Local
document parsers and deterministic verifiers cover different capabilities; they
are not replaced by a text API. Codex in the desktop application is an
interactive development, research, and review collaborator, not a server runtime
credential. No programmatic Codex/OpenAI route is required. DeepSeek Pro remains
an optional later sensitivity arm, not the baseline model.

The generic adapter permits HTTPS endpoints from other commercial, domestic or institutional providers without changing scientific modules. Local keyless OpenAI-compatible runtimes may use plain HTTP only on loopback with explicit opt-in; remote private-network HTTP is rejected. The exact support and transfer boundary is maintained in [model-provider-support-matrix.md](model-provider-support-matrix.md).
