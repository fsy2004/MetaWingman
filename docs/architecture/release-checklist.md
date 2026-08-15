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
- [ ] Complete a new-task invocation test when a model provider is enabled for validation.
- [ ] Add logo, public support URL, website, privacy URL, and terms URL.

## Benchmark and scientific release gate

- [x] Blind reconstruction package separates operational inputs, published-review answers, and post-cutoff evidence.
- [x] Published review-team outputs are expert references; verified corrections replace them and unresolved integrity cases are held out.
- [x] AI-only repeated-run configurations and ablations are encoded; human execution arms are prohibited.
- [x] Review-family train/dev/test isolation and asymmetric scientific loss are enforced.
- [x] Lifecycle/profile/synthesis/validation breadth is machine-audited and cannot be promoted from fixture evidence.
- [x] Conclusion-directed acquisition and counterfactual protocol replay have typed local primitives and failure fixtures.
- [x] Adversarial fixtures cover project path escape, private-network retrieval, unsafe redirects, wildcard high-risk approval, incomplete benchmark run locks, bundle links, prompt-control poisoning, and concurrent event-ledger appends.
- [ ] Assemble licensed, redistribution-reviewed published-review cases.
- [x] Run local malformed, encrypted, mixed-layout, rotated-page, page-count, pixel-budget, and file-size PDF boundary tests.
- [ ] Run a licensed, diverse real-PDF OCR/layout/VLM benchmark. Synthetic boundary fixtures do not establish scientific parser accuracy.
- [ ] Complete reference-integrity, reliability, positional, order, latency/cost, and security audits.
- [ ] Pre-register release thresholds before evaluating the held-out test families.

## Training-data and model gate

- [x] Freeze a deterministic OA train/development plan from hashed corpus and review-family inputs; keep held-out disabled.
- [x] Verify article-level license and retraction state before OA PDF/XML admission, and hash every accepted artifact.
- [x] Generate source-anchored weak-supervision examples, model-neutral run plans, and chat-SFT/retrieval-positive exports.
- [x] Audit file hashes, family isolation, example hashes, weak-label status, and frozen counts before training.
- [ ] Independently validate labels, mine leakage-safe retrieval negatives, and scale the development set before model selection.
- [ ] Record the exact base model, revision, tokenizer, model license, hyperparameters, random seeds, compute, and checkpoint hashes before a real training run.
- [ ] Demonstrate component and end-to-end gains against direct prompting, generic RAG, and prespecified MetaWingman ablations before any capability claim.

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
