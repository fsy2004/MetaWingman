# GLM Cross-Provider Results (2026-08-18)

> Executed per the preregistered plan
> `glm-integration-analysis-plan-2026-08-18.md` (analyses A-D in order).
> Scored with the project's official scorer `score_r2_ai_validation.py`
> against the sealed weak-label key after every provider call locked.
> **Amendment (2026-08-18, final run):** this revision supersedes the two
> earlier commits that carried intermediate-state numbers (n=927 pre-recovery,
> then 994 scored / 5 abstained after two recovery rounds). The final
> checkpoint after all recovery rounds is **999/999 passages with runs and 0
> abstains**; all numbers below are from the final `runs-*.jsonl` checkpoints.

## 0. Scope shrinkage (recorded, not hidden)

The R2 runner (`metawingman/scripts/run_r2_ai_validation.py`) supports **only
the C3 configuration** — the C3 prompt text, verifier inclusion, and task
construction are hardcoded; there are no C0/C1/C2 switches for schema/context/
verifier inclusion on the frozen R2 task set. The GLM pilot therefore executed
**C3 only** (both tasks, 999 + 200 tasks). GLM C0–C2 were not executed. All
comparisons below are C3-level; the DeepSeek C0–C3 ladder is reported for
context from the frozen pilot reports (different 2k-dev task set, flagged).

## 1. Data identities (frozen)

| Piece | Identity |
|---|---|
| blind set | 200 records / 999 passages, `blind-tasks.jsonl` sha256 `38c65be79575a8e1c68e5abcf57ece30a46ed55f4bacebe65cdaa5c28f2bf4ff` |
| key | `weak-label-key.json` sha256 `904fc501ccb6e3cdf559623572b6cb7c8b555886ee651d9b4ef85366cd691b41` (sealed; read only after all calls locked) |
| DeepSeek C3-R2 runs | `/root/autodl-tmp/r2-ai-2026-08-18/` (same scorer, same task set) |
| GLM C3 runs | `/root/autodl-tmp/glm-pilot-2026-08-18/` (glm-5.2, Zhipu openai_compatible adapter) |
| GLM runner variant (server) | `metawingman/scripts/run_r2_ai_validation_glm.py` sha256 `02cfaeeee1ad6b458787c073bc1c2c55ffcd13fe0737f685502a26aefda88546` (final) |
| GLM provider config (server) | `metawingman/references/glm-provider-config.json` sha256 `1ef791c0571993c17a37ecca3d343f66bb7d2d85d32c0ee637d898135afb4848` |

Task parity with DeepSeek verified byte-level: GLM `tasks-sr.jsonl` /
`tasks-rt.jsonl` are identical to the R2 task files except the `max_tokens`
field (999/999 and 200/200 tasks; instruction and input_document equal), so
`instruction_sha256` per task matches the DeepSeek run and the C3 prompt
hashes are unchanged (`section_role` `394bd424d7d5cece4dbd340b2fb2ceb1707de492efa48183f2dfde8531d8e633`,
`retrieval` `e3b07f1db9ea19b832247d2967f732a7c71d84922a0a5b143cadafd76a315604`).

### 1.1 Documented deviations (amendment to the plan)

1. **max_tokens, per task:** 64 → 2048 initially, then **4096 for RT** and
   **4096 → 8192 for SR** after dead-letter diagnosis. GLM-5.2 is a reasoning
   model: its `reasoning_tokens` consume the output budget, and on long
   passages a 64/2048/4096 budget yields `finish_reason=length` with empty
   content (adapter rejects empty content in the batch path). 8192 is the
   adapter's ceiling (`openai_compatible_provider` requires 1 ≤ max_tokens ≤
   8192). Prompt text and task construction unchanged; only the per-task
   token budget and the matching `maximum_reserved_output_tokens` were raised.
2. **Key plumbing:** the runner hardcodes `os.environ["DEEPSEEK_API_KEY"]`;
   the GLM wrapper exports `GLM_API_KEY` from `/root/autodl-tmp/.secrets/glm_key`
   (600 perms) before invoking the runner (`--key-file` still points at the
   GLM key file). `credential_source: environment:GLM_API_KEY`; the key
   appears in no file, log, or commit.
3. **report.json:** adds additive fields `hosted_provider` /
   `deviation_note`. The final server `report.json` (written by the last
   `--task sr` rerun) carries only the section_role section; a merged
   SR+RT report was reconstructed locally from both checkpoints
   (`validation-output/glm-pilot-2026-08-18/report.json`).

### 1.2 Dead-letter history (all recovered; 0 abstains in the final checkpoint)

| Phase | SR | RT |
|---|---|---|
| main pass | 927 runs + 72 dead letters | 196 runs + 4 dead letters |
| recovery 1 (max_tokens 4096) | +64 → 991 | +4 → 200 |
| recovery 2 (max_tokens 8192) | +8 → 999 | — |
| final | **999 runs, 0 dead, 0 abstain** | **200 runs, 0 dead, 0 abstain** |

Dead-letter cause (diagnosed by reproducing calls): ~60% deterministic empty
content (`finish_reason=length`, reasoning 2,040–4,096 tokens consumed the
budget), ~40% transient (re-succeeded unchanged). 3 SR tasks
(`sr-r2-0017/0400/0536`) needed the 8192 budget (reasoning 4,071–4,096 at the
4096 cap); all 8 final SR dead letters recovered at 8192. Root cause (durable
lesson): reasoning-model token budgets must be sized for reasoning **plus**
content, not content alone.

## 2. Analysis A — per-config table (same 999-passage blind set where applicable)

| Metric | DeepSeek C3-R2 | GLM C3-R2 |
|---|---|---|
| section-role hosted macro-F1 | **0.938531** | 0.881621 (999 scored; 0 abstained) |
| section-role hosted per-passage agreement | 936/999 (93.69%) | 893/999 (89.39%) |
| section-role record-level (all passages correct) | 154/200 (77.0%) | 142/200 (71.0%) |
| section-role verifier-only F1 | 1.000000 | 1.000000 (circular — trained on these rules; not a claim) |
| retrieval hosted MRR (pilot formula) | 0.465 | **0.47875** |
| retrieval hosted P@1 | 0.20 | 0.205 |
| retrieval hosted selection accuracy | 0.93 | **0.96** |
| retrieval verifier MRR / P@1 / sel-acc | 0.953333 / 0.925 / 0.925 | 0.953333 / 0.925 / 0.925 |

GLM hosted per-class F1 (vs weak labels): appraisal 0.973, search 0.980,
protocol 0.980, extraction 0.914, synthesis 0.904, certainty 0.889, selection
0.809, eligibility 0.605. DeepSeek per-class: eligibility 0.818, selection
0.906, extraction 0.934, appraisal 0.947, synthesis 0.954, search 0.970,
protocol 0.979, certainty 1.000. GLM is higher on appraisal/search/protocol,
lower on eligibility/selection/extraction/synthesis/certainty.

DeepSeek pilot ladder (2k-dev set, different population — context only):
C0 0.853 → C1 0.908 → C2 0.880 → C3 0.967 (section-role macro-F1);
retrieval MRR 0.408 / 0.415 / 0.405 / 0.495. **Do not read as same-task-set.**

## 3. Analysis B — stack delta

Only measurable within DeepSeek (C0→C3, 2k-dev set): +0.114 macro-F1
(0.853→0.967) and +0.087 retrieval MRR (0.408→0.495). GLM has no ladder data
(runner limitation, §0); recorded as scope shrinkage, not a null result.

## 4. Analysis C — cross-provider agreement

Section-role predictions, shared **999** scored passages (0 abstains on either
provider): **Cohen's kappa 0.847181 (95% CI 0.822123–0.872240, Fleiss SE
0.012785)**; raw agreement 874/999 = 87.49%. Substantial-to-almost-perfect
agreement: the C3 prompt stack is highly (not perfectly) provider-invariant.

Per-class prediction counts (GLM vs DeepSeek): eligibility **106 vs 64**,
search 248 vs 241, extraction 216 vs 238, synthesis 188 vs 168, selection 137
vs 181, appraisal 74 vs 80, protocol 25 vs 23, certainty 5 vs 4. Largest
divergence: eligibility (GLM over-predicts vs DeepSeek), dominated by
GLM-eligibility vs DeepSeek-selection (45 passages) and GLM-synthesis vs
DeepSeek-extraction (24 passages).

Retrieval selected-index agreement between providers: 178/200 = 89.0%
(supplementary; kappa not reported for a 4-category single-selection task).

## 5. Analysis D — cost

| Section | GLM completed runs / recorded attempts / recorded tokens | DeepSeek calls / tokens |
|---|---|---|
| section-role (999 tasks) | 999 runs / 1,051 attempts (52 schema repairs) / **1,191,438 tokens** (prompt 693,621 + completion 497,817, of which reasoning 479,692) | 999 / 619,081 |
| retrieval (200 tasks) | 200 runs / 200 attempts (0 repairs) / **956,699 tokens** (prompt 847,851 + completion 108,848, of which reasoning 104,318) | 200 / 823,340 |
| total | 1,199 runs / 1,251 recorded attempts / **2,148,137 tokens** | 1,199 / 1,442,421 |

GLM additionally incurred **84 failed dead-letter calls** (SR 80, RT 4) whose
tokens are not recorded in the checkpoint (each failed call still billed by
the API; e.g. one 8192-budget SR task consumed ~5.8k tokens on a failed
attempt). Reasoning is 96% of GLM completion tokens (583,010 / 606,665);
the usable answer is a few hundred tokens. No cost-efficiency headline:
token accounting is reported, not gated (per plan §4).

Latency (from run `created_at_utc`): DeepSeek C3-R2 SR 20.2 min / RT 5.7 min
(≈1.2–1.7 s/call). GLM ran ~5–15 s/call on SR (serial, 18:08→21:16 main pass)
plus recovery rounds; RT ran concurrently at ~4–8 s/call. Wall-clock
throughput of the reasoning model is roughly an order of magnitude lower.

## 6. Claim bounds (verbatim from the plan, binding)

- Everything above is **agreement with frozen deterministic weak labels** on
  a development sample. No accuracy, no gold validation, no human comparison.
- Cross-provider agreement measures **provider-invariance of the prompt
  stack**, not scientific verification: two providers agreeing does not make
  a label correct; different providers are a limited cross-check, still not
  human gold.
- No "GLM is better/worse than DeepSeek" headline: config-level differences
  are reported with the GLM token-budget deviation note always attached.
- The trained-verifier-only 1.0/0.953/0.925 numbers are **circular**
  (components scored on labels they were trained to reproduce) and are
  reported only for completeness, exactly as in the R2 doc.

## 7. Receipts

- Server: `/root/autodl-tmp/glm-pilot-2026-08-18/` (tasks/manifests/runs +
  per-phase report.json), logs `glm-pilot-c3-2026-08-18.log` and
  `glm-pilot-c3-{rt,sr}-recovery*-2026-08-18.log`.
- Local mirror: `validation-output/glm-pilot-2026-08-18/` (same files +
  `scoring-results.json` from the official scorer).
- GLM runner variant sha256 (final): `02cfaeeee1ad6b458787c073bc1c2c55ffcd13fe0737f685502a26aefda88546`;
  provider config sha256: `1ef791c0571993c17a37ecca3d343f66bb7d2d85d32c0ee637d898135afb4848`.
- The GLM key appears in no file, log, or commit
  (`credential_source: environment:GLM_API_KEY`).

## 8. Deliverables

- This doc (analyses A–D).
- Whitepaper §8 跨模型 row, `final-status-2026-08-18.md`, methodology
  manuscript abstract/Table, and `goal-progress-audit-2026-08-18.md` updated
  to the final numbers (correction commit), plus a new audit-log entry
  (event_type `fix`).
