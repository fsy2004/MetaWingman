# MetaWingman Two-Product Boundary

Status: binding implementation contract
Last checked: 2026-08-15

## Product 1: Standalone Skill

The first deliverable is a self-contained Codex skill. It uses the host agent's model, web, browser, filesystem and shell capabilities. It bundles the review methodology, schemas, stage gates, deterministic verifiers, project state, benchmark contracts and R toolkit.

The skill does not bundle a model-provider HTTP client, model API key manager or vendor-specific model registry. A user can install and invoke it without a DeepSeek, OpenAI or other model-provider account. Literature APIs, contact emails and institutional database handoffs remain separate because they are evidence-access capabilities rather than model inference.

## Product 2: External-API Agent

The later Agent runtime consumes the same schemas and methods but orchestrates one or more external models. Its core depends only on a provider-neutral `ModelProvider` contract. Vendor implementations are adapters selected from configuration, never hard-coded in topic, screening, extraction, appraisal or writing modules.

An adapter must return the same content-free provenance fields: provider, model/version, finish status, content hash, token usage, credential source and optional system fingerprint. Capability registration, calibration, modalities, context, cost, latency and allowed tools belong in `model_registry`; API shape or brand does not determine scientific authority.

DeepSeek is only the first connectivity adapter. It is not the architecture, default scientific judge or required public dependency. Future adapters may target any compatible commercial, domestic, institutional or local runtime, including OpenAI-compatible endpoints, native provider APIs, vLLM and Ollama, without changing the scientific workflow.

The external runtime now implements a validated secret-free provider configuration, a generic OpenAI-compatible adapter, explicit loopback-only HTTP support for local runtimes, and a schema-gated candidate runner. The generic contract has been exercised through the live DeepSeek-compatible endpoint; that proves interface portability only, not independent-provider evidence. See [model-provider-support-matrix.md](model-provider-support-matrix.md).

## Shared and Separate Assets

Shared:

- methodology and source hierarchy;
- schemas and evidence graph;
- deterministic tools and R adapters;
- task definitions, error taxonomy and benchmark cases;
- safety, legality, abstention and responsibility gates.

Separate:

- release packages and dependency manifests;
- credential storage and data-transfer declarations;
- runtime orchestration and provider adapters;
- model/provider calibration and cost benchmarks;
- capability claims and support commitments.

The skill can guide and execute through host tools. The Agent can autonomously schedule external model calls. Neither product may claim scientific validation from the other's technical smoke tests.
