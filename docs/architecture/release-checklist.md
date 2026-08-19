# MetaWingman release checklist

Status: local release engineering in progress
Last checked: 2026-08-15

## R0 repository skill

- [x] Canonical skill source is `metawingman/` and statistical source is `toolkit/`.
- [x] Deterministic builder generates `.agents/skills/metawingman` with file hashes.
- [x] Bundle scan rejects likely secrets and author-specific absolute paths.
- [x] Bundle build rejects symlinks and junctions so source files cannot escape the canonical trees.
- [x] Skill metadata passes the system `quick_validate.py` validator.
- [x] Clean-room `install.ps1` test is available and uses a staged build.
- [x] Deterministic ZIP generation emits an SPDX 2.3 SBOM and explicitly unsigned in-toto/SLSA provenance bound to the archive SHA-256.
- [ ] Pin a release commit with a clean Git tree and publish a signed tag or release attestation. A ZIP and adjacent SHA256 file alone do not authenticate the publisher.

## R1 skills-only plugin

- [x] `plugins/metawingman/.codex-plugin/plugin.json` uses stable identity and semantic version.
- [x] Plugin skill payload is generated from the same canonical source.
- [x] Positive and negative trigger fixtures are present.
- [x] Support, security, privacy/data-flow, acceptable-use, and release notes are present.
- [x] Install the repository marketplace and plugin in an isolated Codex profile.
- [ ] Complete a new-task invocation test when a model provider is enabled for validation. **2026-08-18 note:** live provider invocations exist (RQC smoke, dual-judge blind scoring, VAL-3 AI screening pilot 649 calls) but the dedicated new-task invocation test remains open.
- [ ] Add logo, public support URL, website, privacy URL, and terms URL.

## Benchmark and scientific release gate

- [x] Blind reconstruction package separates operational inputs, published-review answers, and post-cutoff evidence.
- [x] Published review-team outputs are expert references; verified corrections replace them and unresolved integrity cases are held out.
- [x] AI-only repeated-run configurations and ablations are encoded; human execution arms are prohibited.
- [x] Review-family train/dev/test isolation and asymmetric scientific loss are enforced.
- [x] Lifecycle/profile/synthesis/validation breadth is machine-audited and cannot be promoted from fixture evidence.
- [x] Conclusion-directed acquisition and counterfactual protocol replay have typed local primitives and failure fixtures.
- [x] Adversarial fixtures cover project path escape, private-network retrieval, unsafe redirects, wildcard high-risk approval, incomplete benchmark run locks, bundle links, prompt-control poisoning, and concurrent event-ledger appends.
- [x] Assemble licensed, redistribution-reviewed published-review cases. **2026-08-18:** sci-exercise (BSD-3-Clause, dev-split analysis slice, scored pass) promoted; ag-rdt living-update (CC-BY-4.0 2021 + CC-BY-NC-ND-4.0 read-only 2022) assembled with frozen corpus + anchors; remaining families guard-test-only or blocked (recorded in `val1-promotion-analysis`).
- [x] Run local malformed, encrypted, mixed-layout, rotated-page, page-count, pixel-budget, and file-size PDF boundary tests.
- [ ] Run a licensed, diverse real-PDF OCR/layout/VLM benchmark. Synthetic boundary fixtures do not establish scientific parser accuracy.
- [ ] Complete reference-integrity, reliability, positional, order, latency/cost, and security audits. **2026-08-18 note:** cross-provider kappa 0.872 measured; position/judge-order audits remain open.
- [x] Pre-register release thresholds before evaluating the held-out test families. **2026-08-18:** VAL-2b1 froze loss weights/thresholds/prompt hashes/stopping rules; VAL-2c froze kappa bands; reconstruction tolerances frozen pre-unsealing.

## Training-data and model gate

- [x] Freeze a deterministic OA train/development plan from hashed corpus and review-family inputs; keep held-out disabled.
- [x] Freeze a biomedical-stratified 2,048-record metadata plan with a hash-bound specialty registry and no journal feature in model inputs.
- [x] Verify article-level license and retraction state before OA PDF/XML admission, and hash every accepted artifact.
- [x] Generate source-anchored weak-supervision examples, model-neutral run plans, and chat-SFT/retrieval-positive exports.
- [x] Audit file hashes, family isolation, example hashes, weak-label status, and frozen counts before training.
- [x] Mine same-split, cross-family hard-negative candidates and freeze two component jobs with an immutable model revision, tokenizer, model card, declared license, hyperparameters, seeds, and resource request.
- [x] Build a metadata-only server handoff with a strict member allowlist, bounded secret scan, and explicit scientific versus hardware/CUDA/package blockers; require an independent deployment-side secret scan before upload.
- [x] Independently validate weak labels and hard negatives, audit review-family candidates, and scale the development set before model selection. **2026-08-18:** appraisal weak labels independently scored vs a rubric-grounded 100-item sheet (kappa 0.311) → rules do not match rubric judgment; pivot to rubric-supervised labels recorded (`appraisal-task-relabeling-decision`); retrieval hard negatives previously measured (candidate MRR 0.962).
- [x] Verify the exact CUDA/package environment, execute authorized jobs, and record accelerator details, elapsed time, metrics, and checkpoint hashes. **2026-08-18:** three component trainings on the 4090 server (torch 2.13.0+cu130 receipts with per-checkpoint hashes), plus BM25 eval and GLM pilot receipts.
- [ ] Demonstrate component and end-to-end gains against direct prompting, generic RAG, and prespecified MetaWingman ablations before any capability claim. **2026-08-18 note:** config ladder measured (DeepSeek C0 0.8535→C3 0.9668 on the 2k set; hosted-vs-verifier on R2; cross-provider kappa 0.872); a generic-RAG baseline arm remains open.

## R2 public submission

- [ ] Verify developer or business identity and submission permission.
- [ ] Finalize public metadata, starter prompts, category, country availability, and policy attestations.
- [ ] Confirm all bundled dependencies and redistributed fixtures are license-compatible.
- [x] Produce exact Python core/PDF and direct R package locks; validate Python in an isolated Windows environment and validate R pins against the local tested runtime.
- [ ] Validate the exact locks in isolated Linux and isolated R libraries. Linux is represented in CI but has not run from this unpushed worktree; WSL has no installed distribution locally.
- [x] Route every implemented append mutation through a cross-process lock with schema validation and unique-key enforcement. Empty streams without mutation APIs remain single-writer artifacts; distributed services stay disabled until their future writers use the same primitive or a transactional queue.
- [x] Publish the exact data-flow and model-provider support matrix, including live, contract-only and unsupported evidence levels.
- [ ] Submit only after R0, R1, and scientific benchmark gates pass.

No checklist item authorizes a remote push, marketplace submission, account creation, purchase, or external publication. Those remain explicit user actions.
