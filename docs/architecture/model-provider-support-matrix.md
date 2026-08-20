# MetaWingman model-provider and data-flow matrix

Status: implemented development contract
Last checked: 2026-08-15

## Product boundary

| Product | Model execution | Provider client in package | Separate model account | Current validation |
|---|---|---:|---:|---|
| Standalone skill | host Codex/agent model and tools | no | no | bundle, invocation fixtures and deterministic workflow tests |
| External-API Agent | configured remote or loopback endpoint | yes, separate from skill bundle | depends on endpoint | provider contract, live DeepSeek probe and one schema-gated task |

The products share scientific schemas, deterministic verifiers, evidence lineage and benchmark contracts. A connectivity result from the Agent does not validate the standalone skill scientifically, and a skill test does not validate an external model.

## Provider support

| Adapter | Configuration | Secret source | Network policy | Evidence level | Scientific authority |
|---|---|---|---|---|---|
| DeepSeek | `deepseek-provider-config.json` | environment or Windows Credential Manager | HTTPS only | live model listing and structured calls passed on 2026-08-15 | uncalibrated development provider |
| Generic OpenAI-compatible | `provider-config.template.json` | named environment variable or Windows Credential Manager | HTTPS only | contract and mocked-response tests; exercised against DeepSeek's compatible endpoint | depends on each configured endpoint and task calibration |
| Loopback vLLM/Ollama-compatible | generic config with `allow_local_http=true` and no key if appropriate | optional | HTTP permitted only for `localhost`, `127.0.0.1` or `::1` | constructor and policy tests only | unsupported until endpoint-specific validation |
| Native non-compatible APIs | future adapter behind `ModelProvider` | adapter-specific secret store | HTTPS or explicit loopback | not implemented | unsupported |

Provider brand, model name, API compatibility and context length never grant a model permission to finalize scientific decisions. Capability registration and review-family calibration remain separate gates.

## Data flow

1. Provider configuration contains endpoint, model and feature flags but no key.
2. A key is resolved at run time from an environment variable or operating-system credential store. It is never serialized into an event, result, bundle or Git artifact.
3. Hosted transfer requires an explicit CLI flag. Inputs are size-bounded and treated as untrusted evidence data inside the prompt.
4. The endpoint receives only the selected task instruction, JSON Schema and selected input document. The provider response is parsed as JSON and validated locally.
5. One schema-repair call is allowed. A second invalid response becomes an abstention. Usage is retained per attempt and aggregated so repair cost is not hidden.
6. Batch execution reserves two provider calls and two output-token allowances before starting each task, writes schema-valid JSONL checkpoints under a cross-process lock, resumes completed task IDs and routes failed task hashes to a content-free dead-letter summary.
7. The persisted run stores the validated candidate plus provider/model, output hash, token use, finish status, fingerprint and non-secret credential-source label.
8. A generated value remains `candidate_only_requires_workflow_gate`; it cannot directly modify frozen protocol, eligibility, extraction, RoB, GRADE, poolability or final claims.

Public metadata may be sent after the operator confirms hosted transfer. Licensed full text, personal data, confidential manuscripts and institution-restricted material require a separate lawful-use and provider-data-policy decision; the presence of an API key is not authorization to transmit them.

## Current limits

- Only text and structured-data calls have live connectivity evidence.
- DeepSeek Flash and Pro are one provider family. Repeated roles from that family are test-time compute, not independent corroboration; high-risk routes therefore require declared source or executable verification and a human signature rather than a second provider by default.
- No real-PDF vision benchmark, review-family scientific calibration or high-risk proposal-opposition-judge release threshold has passed.
- The local batch runner has checkpoint, delay and call/output reservation controls. A distributed queue, provider-specific rate-limit scheduler and server deployment remain deployment work, not standalone-skill requirements.
