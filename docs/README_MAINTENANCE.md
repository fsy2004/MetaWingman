# README writing and continuous-maintenance standard

This file is the single authority for MetaWingman's root README. The older
architecture style note redirects here.

## Reader contract

The README serves a first-time researcher before it serves a contributor. A
reader should understand the product, its two control policies, shortest install,
scientific evidence level, and primary documentation path within one minute.

Use this order:

1. product name, one-sentence value, and primary navigation;
2. generated release metrics;
3. the Agent + Skill identity and the two control loops;
4. the end-to-end review state and shortest runnable path;
5. user goals and concrete outputs;
6. a compact evidence section linked to dated status reports;
7. repository map, generated inventory, and development commands;
8. a Chinese section covering the same product, controls, and invocation;
9. citation, contact, security, and licence links.

English comes first for the public GitHub audience. Chinese follows under
`## 中文说明`. The two sections must agree on capabilities, evidence, and
limitations; they need not translate every sentence literally. Commands and
tables may be shared when duplication would make maintenance harder.

## Writing rules

- Write for a reader who has never seen internal plans or conversations.
- Start sections with the conclusion. Use active voice, short paragraphs, and
  concrete nouns.
- Distinguish the product from its mechanisms: MetaWingman is an Agent and
  reusable Skill; decision-aware topic control and conclusion-directed evidence
  acquisition are the two headline policies; question--method co-design,
  provenance, R adapters, multi-role compute, and verifiers are mechanisms.
- State what the software does, how to run it, what evidence supports it, and
  what remains unvalidated.
- Avoid marketing adjectives, journal-prestige language, internal codenames,
  server credentials, local absolute paths, and operational history that does
  not help a user.
- Keep numbers next to a dated evidence link. Distinguish interface tests,
  weak-label reconstruction, component evaluation, AI-only feasibility, and
  external scientific validation.
- Never turn a passing test, generated bundle, or successful model response
  into a clinical-validity claim.
- Keep the README concise. Put protocols, receipts, failure analyses, and full
  result tables in `docs/`.
- Do not open with a limitation ledger. Give the positive, executable product
  path first, then one compact evidence-status section with dated links.

## Reference-driven redesign rule

A material README redesign must inspect at least two live, relevant open-source
research repositories before editing. Record the URLs, observed information
hierarchy, adopted patterns, and rejected non-transferable claims in the task
audit. Learn structure and user flow; never copy project-specific prose, metrics,
screenshots, or capability claims.

For MetaWingman, useful comparison classes include systematic-review software,
scientific literature agents, reproducible analysis engines, and research-agent
frameworks. The final README must still follow MetaWingman's own scientific
authorities and live repository state.

## Single sources of truth

| Claim | Authority |
|---|---|
| Skill behavior | `metawingman/` |
| Deterministic R analysis | `toolkit/R/` and adapter manifests |
| Generated distributions | `.agents/skills/` and `plugins/`, rebuilt from canonical sources |
| Current supported boundary | `docs/STATUS.md` |
| Dated validation result | reviewed report under `docs/architecture/` |
| Release version | Git tag and plugin manifest |
| Repository counts | `scripts/update_readme.py` |

README prose must not announce a capability before its canonical source,
contract, tests, and evidence report exist.

## Generated blocks

`scripts/update_readme.py` owns exactly two marked blocks:

- `readme-metrics`: license, release, R-module, manifest, and schema badges;
- `readme-inventory`: canonical Python, schema, R-module, manifest, and adapter
  counts.

Edit text outside those markers by hand. Run the updater after adding or
removing canonical entry points, schemas, R modules, adapter manifests,
adapters, or tags.

```powershell
python .\scripts\update_readme.py
python .\scripts\update_readme.py --check
python -m unittest discover -s .\tests -p "test_readme_update.py" -v
```

The updater also rejects missing repository-relative links. It reads canonical
sources only and ignores generated bundles, preventing triple-counted metrics.

## Continuous update policy

GitHub Actions runs the drift check and focused tests on every push and pull
request, on a scheduled audit, and on manual dispatch. A drift failure blocks a
clean status and prints the local command that repairs the README. The workflow
does not auto-commit because this repository mirrors the same default-branch
commit to GitHub and Gitee; maintainers update both remotes from one reviewed
commit.

Manual prose review is required when any of these change:

- installation or invocation;
- supported review stage or method family;
- validation level or scientific claim boundary;
- human-responsibility or credential boundary;
- current status report or primary documentation path;
- public security, privacy, or acceptable-use policy.

The same pull request or commit must update the README whenever one of these
changes. Scheduled CI detects metric and link drift; it does not invent or
rewrite scientific prose.

## Release checklist

Before committing a README change:

```powershell
python .\scripts\update_readme.py
python .\scripts\update_readme.py --check
python -m unittest discover -s .\tests -p "test_readme_update.py" -v
python .\scripts\build_skill_bundle.py
python .\scripts\verify_skill_bundle.py .\.agents\skills\metawingman
python .\scripts\verify_skill_bundle.py .\plugins\metawingman\skills\metawingman
python .\scripts\verify_dependency_locks.py
git diff --check
```

Then inspect the rendered GitHub Markdown, verify every local link, confirm the
status wording against its dated report, inspect staged paths, and scan tracked
text for secrets and author-specific absolute paths.
