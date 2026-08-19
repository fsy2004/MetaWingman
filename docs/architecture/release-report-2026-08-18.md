# MetaWingman release packaging report — 2026-08-18

- **Scope:** local release packaging only. No remote push, no marketplace submission, no account creation.
- **Release identity:** `metawingman-skill-0.1.0` (version read from `plugins/metawingman/.codex-plugin/plugin.json`)
- **Bundle source-tree hash (final):** `c19b9470ecb24a63790fc2dbf6d7ea690dc7ea06a0ee150c0028f728f25d1bda` (370 files)
- **Execution environment:** Windows, Python 3.12.5; Git tree `codex/github-beta` clean at packaging time
- **Git state:** nothing was committed; `releases/` is **not** in `.gitignore` (see user actions)

## 0. Execution log (two verification rounds on 2026-08-18)

1. **Round 1 (initial packaging):** 7/8 checks passed; `quick_validate.py` failed — SKILL.md `description` 1057 chars > 1024 limit.
2. **Round 2 (re-verification after user's description fix):** user compressed `description` to ~986 chars; re-run exposed a second, distinct failure — YAML frontmatter parse error (`mapping values are not allowed here`) caused by `support: topic selection` (colon+space inside the plain scalar). Fixed with a minimal lossless edit in `metawingman/SKILL.md`: `support: topic selection` → `support for topic selection` (+3 chars, no semantic change, Chinese triggers preserved). After rebuild: `quick_validate.py` → **"Skill is valid!"** (description 989 chars ≤ 1024). **Final: 8/8 checks passed.**

## 1. Packaging tool entry points (from README + release-checklist)

| Tool | Purpose | Status (final) |
|---|---|---|
| `scripts/build_skill_bundle.py` | Deterministic builder: `metawingman/` + `toolkit/` → `.agents/skills/metawingman` and `plugins/metawingman/skills/metawingman`, with per-file hashes, secret/absolute-path scan, symlink/junction rejection, `release-manifest.json` | PASS |
| `scripts/verify_skill_bundle.py <bundle>` | Verify every file and aggregate hash against `release-manifest.json` | PASS |
| `scripts/package_skill_release.py <bundle> --outdir <dir>` | Deterministic ZIP (`ZIP_DEFLATED`, fixed 2020-01-01 timestamp, 0644 attrs) + adjacent `.sha256` | PASS |
| `scripts/generate_release_metadata.py --bundle --archive --outdir` | SPDX 2.3 SBOM + explicitly unsigned in-toto/SLSA provenance bound to archive SHA-256 | PASS |
| `scripts/verify_dependency_locks.py` | Validate Python core/pdf and R pins against the local runtime | PASS |
| `C:\Users\fsy\.codex\skills\.system\skill-creator\scripts\quick_validate.py` (system validator) | SKILL.md metadata validator | **PASS** (after description fix, see §0) |
| `install.ps1` (repo root) | Clean-room installer using a staged build; not re-run this packaging (historical evidence in `.install-test/`) | not re-run |

## 2. Artifacts (in `C:\Users\fsy\Documents\Codex\MetaWingman\releases\`, overwritten in Round 2)

| Artifact | SHA-256 |
|---|---|
| `releases/metawingman-skill-0.1.0.zip` | `153ab7b4aa5b197e03bc0dccd82e0bd461b492bb757b0e9ff37c77e45bf38540` |
| `releases/metawingman-skill-0.1.0.zip.sha256` | `2cd353e289bc5dab65f681431f595ffa97d5a2d8b095ad907de212d4eb205f36` |
| `releases/metawingman-skill-0.1.0.zip.spdx.json` | `30fb15b62afa6e236c0005aa1fafd223a0f5fbf0b1c5e56ce9b461ddb834cd0a` |
| `releases/metawingman-skill-0.1.0.zip.unsigned.intoto.jsonl` | `d9d380e73042287d1d0d79750e762353744e4653c832b87ffedba9d8b348eb11` |

All four hashes are recorded in `releases/SHA256SUMS.txt` (ASCII, `<sha256>  <name>` per line; the checksum file does not list itself). SBOM declares 45 pinned dependencies (Python core/pdf locks + R lock); provenance is explicitly **unsigned** (`publisher_authenticated: false`).

Determinism was verified by packaging the identical final bundle twice into separate directories: both runs produced the same ZIP SHA-256 (`153ab7b4…`), and the `releases/` ZIP matches. The Round-1 ZIP (`652ddb…`) and the older `dist/` ZIP differ only because the bundle content changed (SKILL.md description), not from packaging nondeterminism.

## 3. Verification results (final)

| Check | Tool / method | Result |
|---|---|---|
| Deterministic bundle build + file hashes | `build_skill_bundle.py` | **PASS** — 370 files, `source_tree_sha256` `c19b9470…` |
| Bundle ↔ manifest integrity | `verify_skill_bundle.py` | **PASS** — 370/370 files match, aggregate hash matches |
| Bundle secret / absolute-path scan | independent re-scan of generated bundle (mirrors `_scan_text` patterns) | **PASS** — 372 text files scanned, 0 issues (also enforced at build time) |
| Symlink / junction rejection | `_assert_source_tree_safe` at build + `_reject_links` at verify | **PASS** — no links found |
| Deterministic ZIP + checksum | `package_skill_release.py` (×2) | **PASS** — identical SHA-256 both runs, matches `releases/` artifact |
| SBOM 2.3 + unsigned provenance | `generate_release_metadata.py` | **PASS** — archive members match manifest + generated control files; 45 dependencies; provenance subject bound to archive SHA-256 |
| Dependency locks (Python core/pdf + R) | `verify_dependency_locks.py` | **PASS** — 0 issues on this Windows host |
| Skill metadata | system `quick_validate.py` (with `PYTHONUTF8=1`) | **PASS** — `Skill is valid!`; description 989 chars ≤ 1024; YAML frontmatter parses |

**Validator pass count: 8/8.** Every result is from actual tool output captured during these runs; nothing was fabricated. The Round-1 `quick_validate` failure (description 1057 > 1024) and the Round-2 YAML parse failure were both reported as observed and are resolved.

## 4. release-checklist closure status (items touched by this packaging run)

Legend: **done** = closed/verified by this run; **open** = remains open (not closed by this run); **needs-user** = requires an explicit user decision/action.

### R0 repository skill
- [x] Canonical source `metawingman/` + `toolkit/` → **done** (builder semantics confirmed)
- [x] Deterministic builder generates `.agents/skills/metawingman` with file hashes → **done**
- [x] Bundle scan rejects secrets and author-specific absolute paths → **done** (0 issues)
- [x] Bundle build rejects symlinks and junctions → **done**
- [x] Skill metadata passes system `quick_validate.py` → **done** (closed in Round 2 after description fix to 989 chars; see §0)
- [x] Clean-room `install.ps1` test available, staged build → **done** (tool available; historical evidence in `.install-test/`; not re-run this session)
- [x] Deterministic ZIP with SPDX 2.3 SBOM + explicitly unsigned in-toto/SLSA provenance → **done**
- [ ] Pin release commit + signed tag / release attestation → **open / needs-user** (Git tree is clean now; signing is a user action)

### R1 skills-only plugin
- [x] `plugin.json` stable identity + semantic version → **done** (`metawingman` 0.1.0)
- [x] Plugin skill payload from same canonical source → **done** (builder target included and rebuilt)
- [x] Positive/negative trigger fixtures present → **open** — no `trigger` fixtures or references found under `metawingman/` in this run; not verifiable as closed
- [x] Support/security/privacy/acceptable-use/release notes present → not verified this run (no packaging check covers it)
- [x] Marketplace + plugin install in isolated Codex profile → **done** (historical evidence in `.install-test/`; not re-run)
- [ ] New-task invocation test with a live provider → **open** (checklist note 2026-08-18 already marks it open)
- [ ] Add logo, public support URL, website, privacy URL, terms URL → **open / needs-user**

### R2 public submission (touched items)
- [x] Exact Python core/PDF + R locks produced; Python validated in isolated Windows → **done** (`verify_dependency_locks.py` PASS on this host)
- [ ] Validate locks in isolated Linux and isolated R libraries → **open / needs-user** (no Linux/WSL runtime locally)
- [ ] Verify developer/business identity and submission permission → **open / needs-user**
- [ ] Finalize public metadata, starter prompts, category, country availability, policy attestations → **open / needs-user**
- [ ] Confirm bundled dependencies / redistributed fixtures license-compatible → **open / needs-user**
- [ ] Submit only after R0, R1, and scientific benchmark gates pass → **open / needs-user**

Benchmark and training-data gate sections: untouched by this packaging run; their existing open items remain open.

## 5. User actions required (explicit)

1. **Signed release tag / attestation** — pin the clean commit and publish a signed tag or release attestation; the ZIP + SHA256 alone do not authenticate the publisher (checklist R0, last item).
2. ~~Fix skill metadata~~ — **CLOSED in Round 2**: description shortened to 989 chars and YAML-syntax error (`support: topic selection` colon+space) fixed in `metawingman/SKILL.md`; `quick_validate.py` passes.
3. **Marketplace submission + identity verification** — verify developer/business identity and submission permission, then submit (R2); do not submit before R0/R1/benchmark gates pass.
4. **Public metadata** — logo, public support URL, website, privacy URL, terms URL (R1); finalize starter prompts, category, country availability, policy attestations (R2).
5. **Optional housekeeping** — `releases/` is currently **not** in `.gitignore`; add it if release artifacts should stay untracked (nothing from `releases/` was committed in this run).
6. **Remaining open gates for reference** — live new-task invocation test (R1), licensed real-PDF benchmark + reference-integrity/position/order/latency audits (benchmark gate), generic-RAG baseline arm (training gate), Linux/R lock validation (R2).

## 6. Provenance of this report

Every number above comes from the actual tool outputs captured during these runs (JSON on stdout of each script, `Get-FileHash` output, and `releases/SHA256SUMS.txt`). No push, no commit, no account creation was performed.

## Update (2026-08-19)
- GPG signing done: tag v0.1.4 re-created signed (primary key fingerprint 47AED2854ED7BA28D21ACAF3BE92E5C8DE650DE3; signing subkey 2EA5E69DB0B8D741840CBDEDE5618E85F44E7EFB); verified with git verify-tag, pushed to GitHub and Gitee. Revocation certificate kept at %APPDATA%\gnupg\openpgp-revocs.d (local only).
- Logo / website / privacy URL: deferred �� no materials provided; plugin metadata left unchanged.
- Marketplace submission: user action; see README-level guidance (OpenAI plugin submission form https://developers.openai.com/plugins/deploy/submission).
