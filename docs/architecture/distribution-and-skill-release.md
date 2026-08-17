# MetaWingman Distribution and Skill Release Plan

Status: implementation plan
Last checked: 2026-08-13
Authority: live repository plus official OpenAI skill and plugin documentation.

## Decision

MetaWingman has two products: a standalone host-executed skill and a later external-API Agent runtime. The standalone skill is the first release. It uses the host model and tools, needs no separate model API account, and excludes provider clients and model-key managers. The Agent will share schemas and methods but ship separately behind a provider-neutral interface; DeepSeek is only one adapter.

Use one canonical skill source and generate or package all installable forms from it:

```text
metawingman/                         canonical skill source
  SKILL.md
  agents/openai.yaml
  references/
  scripts/
toolkit/                             repository-level R toolkit source
install.ps1                          assembles a self-contained personal skill
.agents/skills/metawingman/          generated repo-discovery form, not hand-edited
plugins/metawingman/                 generated public plugin package
  .codex-plugin/plugin.json
  skills/metawingman/                packaged canonical skill plus toolkit
```

The generated repo and plugin forms must be reproducible artifacts. CI should fail when their content differs from the canonical source at the same commit.

## Four Distribution Surfaces

| Surface | Purpose | Near-term action |
|---|---|---|
| Source repository | Develop the skill, scripts, schemas, tests, toolkit, and research documents | Keep `metawingman/` canonical |
| Repo-scoped discovery | Let Codex automatically discover the skill when working inside this repository | Generate `.agents/skills/metawingman/` or a supported link during packaging; do not duplicate it manually |
| Personal installation | Let a user clone the repository and install the self-contained skill | Retain and harden `install.ps1`; add non-destructive upgrade and uninstall guidance |
| Public installation | Let other users install through ChatGPT/Codex plugin distribution | Package a skills-only plugin first; add MCP only when remote tools or shared state justify it |

Official OpenAI documentation treats skills as the reusable workflow format and plugins as the preferred distribution format beyond one repository. A skills-only plugin is therefore sufficient for the first public release. See [the two-product boundary](two-product-boundary.md).

## Release Sequence

### R0: Repository-ready skill

- Keep `metawingman/SKILL.md` concise enough to route into stage-specific references.
- Keep `agents/openai.yaml` with display name, short description, and default prompt.
- Add a deterministic build command that copies `metawingman/` and `toolkit/` into a staging skill.
- Generate a manifest containing release version, Git commit, file hashes, Python/R requirements, and optional capabilities.
- Validate the staged skill with `quick_validate.py` and run representative Python/R smoke tests.
- Add positive and negative trigger tests so generic statistics requests do not accidentally invoke a full systematic-review workflow.

Exit gate: a fresh clone can build and invoke the same skill without relying on the author's personal directories.

### R1: Skills-only plugin beta

Create `plugins/metawingman/` with:

- `.codex-plugin/plugin.json` using a stable `metawingman` identity and semantic version;
- `skills/metawingman/` populated by the same deterministic build;
- release notes, support matrix, example prompts, and public test cases;
- a local or repository marketplace entry for installation testing.

Do not add an MCP server merely to make the package look more agentic. The first plugin can call the host's existing web, shell, file, browser, and code tools under the skill's explicit permission and credential boundaries.

Exit gate: install from a clean local marketplace, invoke in a new task, run positive and negative cases, and verify that no absolute author-specific paths remain.

### R2: Public submission candidate

Prepare the materials required by the current public plugin submission workflow:

- verified developer or business identity and submission permission;
- plugin name, descriptions, category, logo, website, support URL, privacy policy URL, and terms URL;
- five positive and three negative test cases with expected behavior;
- starter prompts, country availability, release notes, and policy attestations;
- a documented data-flow statement explaining when documents stay local and when content is sent to a selected model provider.

Exit gate: privacy, licensing, credential handling, data retention, and scientific-responsibility claims are accurate for every supported execution mode.

### R3: Optional MCP service

Add an MCP-backed service only for capabilities that cannot be supplied reliably by a packaged skill:

- shared team review state and append-only event ledger;
- centrally managed licensed-source connectors and OAuth boundaries;
- scheduled living-review jobs and notifications;
- long-running parser queues or organization-wide model routing;
- controlled remote benchmark and telemetry services.

An MCP release creates hosting, authentication, privacy, availability, abuse, and incident-response obligations. It should follow the skills-only release, not block it.

## Package Boundaries

Include in the public skill:

- stage-gated instructions and method references;
- deterministic search, deduplication, verification, project-validation, and R adapter scripts;
- JSON schemas, fixtures, and lightweight examples;
- the required R toolkit source and explicit package requirements.

Exclude from the package:

- credentials, cookies, institutional exports, copyrighted PDFs, and user review projects;
- validation output, caches, model responses, or local absolute paths;
- benchmark documents whose licenses do not permit redistribution;
- large local model weights and parser checkpoints.
- direct model-provider clients, provider model templates and model-key management scripts; these belong to the separate Agent runtime.

## Compatibility and Versioning

- Version the plugin and skill bundle together using semantic versioning.
- Record schema versions separately because review projects may outlive one software release.
- Support migration of review state before changing a schema incompatibly.
- Pin benchmark snapshots and release manifests, but keep model providers configurable.
- Mark features as `core`, `optional`, `experimental`, or `credentialed` in the capability manifest.
- Publish checksums for generated bundles and verify them before installation.

## Release Tests

Positive cases should cover topic/protocol planning, lawful search, screening with abstention, evidence-anchored extraction, and deterministic Meta-analysis execution.

Negative cases should confirm that MetaWingman:

- does not invent full-text eligibility or extracted values from an abstract;
- does not bypass a paywall, CAPTCHA, or institutional login;
- does not silently finalize exclusions, RoB/GRADE judgments, poolability, or manuscript conclusions;
- does not claim scientific completion from a successful script or smoke test;
- does not send protected documents to an undeclared remote provider.

## Immediate Backlog

- [x] DIST-01: Add deterministic `build_skill_bundle` with hashes and no author-specific paths.
- [x] DIST-02: Add repo-discovery generation for `.agents/skills/metawingman`.
- [x] DIST-03: Add clean-room installation test for `install.ps1`.
- [x] DIST-04: Add plugin scaffold and local marketplace installation test.
- [x] DIST-05: Add trigger, safety, and credential-boundary test fixtures.
- [x] DIST-06: Add `SUPPORT.md`, `SECURITY.md`, privacy/data-flow notice, and terms/acceptable-use page.
- [x] DIST-07: Add release checklist and CI artifact validation.
- [ ] DIST-08: Prepare the public listing and submission only after R0-R1 gates pass.

## Official References

- [Build skills](https://learn.chatgpt.com/docs/build-skills)
- [Package your plugin](https://developers.openai.com/plugins/build/plugins)
- [Submit plugins](https://developers.openai.com/plugins/deploy/submission)
