# GLM Cross-Provider Results (2026-08-18)

> Executed per the preregistered plan
> `glm-integration-analysis-plan-2026-08-18.md` (analyses A-D in order).
> Scored with the project's official scorer `score_r2_ai_validation.py`
> against the sealed weak-label key after every provider call locked.

## 0. Scope shrinkage (recorded, not hidden)

The GLM pilot executed **C3 only** (both tasks): 927 section-role runs (all C3
prompt hash `394bd424…`; 72 of 999 passages abstained/missing) and 200
retrieval runs. GLM C0-C2 were not executed. All comparisons below are
therefore C3-level; the DeepSeek C0-C3 ladder is reported for context from
the frozen pilot reports, with its different task set flagged.

## 1. Data identities (frozen)

| Piece | Identity |
|---|---|
| blind set | 200 records / 999 passages, `blind-tasks.jsonl` sha256 `38c65be7…` |
| key | `weak-label-key.json` (sealed; read only after all calls locked) |
| DeepSeek C3-R2 runs | `/root/autodl-tmp/r2-ai-2026-08-18/` (same scorer) |
| GLM C3 runs | `/root/autodl-tmp/glm-pilot-2026-08-18/` (glm-5.2; deviation: max_tokens 64→2048, prompt text unchanged) |

## 2. Analysis A — per-config table (same 999-passage blind set where applicable)

| Metric | DeepSeek C3-R2 | GLM C3 |
|---|---|---|
| section-role hosted macro-F1 | **0.9385** | 0.8829 (994 scored; 5 abstained after two dead-letter recovery rounds) |
| section-role verifier-only F1 | 1.0000 | 1.0000 (circular — trained on these rules; not a claim) |
| retrieval hosted MRR (pilot formula) | 0.465 | **0.4788** |
| retrieval hosted P@1 | 0.20 | 0.205 |
| retrieval hosted selection accuracy | 0.93 | **0.96** |
| retrieval verifier MRR / P@1 | 0.9533 / 0.925 | 0.9533 / 0.925 |

Dead-letter recovery (recorded): RT had 4 dead letters recovered at
max_tokens 4096 (0 abstain); SR had 72 dead letters — the dominant cause
was GLM-5.2 reasoning tokens consuming the output budget (empty content,
finish=length) — recovered in two rounds (4096 → 8192) to 994/999, with
the remaining 5 recorded as abstained. Root cause: reasoning-model token
budgets must be sized for reasoning plus content, not content alone.

DeepSeek pilot ladder (2k dev set, different population — context only):
C0 0.8535 → C1 0.9079 → C2 0.8799 → C3 0.9668.

## 3. Analysis B — stack delta

Only measurable within DeepSeek (C0→C3): +0.11 macro-F1 (2k set). GLM has no
ladder data; recorded as scope shrinkage, not a null result.

## 4. Analysis C — cross-provider agreement

Section-role predictions, shared 998 scored passages: **Cohen's kappa 0.8483
(95% CI 0.8233–0.8733, Fleiss SE)**; raw agreement 87.6%. Interpretation:
provider-invariance of the C3 prompt stack is high but not perfect; the
largest divergence is eligibility (DeepSeek 60 vs GLM 95 predictions).

## 5. Analysis D — cost

GLM C3 sr: 200 tasks, 956,699 observed tokens (from the completed batch
summary; retries across restarts inflated the call count — 927 runs for 999
tasks). DeepSeek C3-R2: 1,199 calls / 1.44M tokens (from the R2 doc table).
No cost-efficiency headline: token accounting is reported, not gated
(per plan §4).

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

## 7. Deliverables

- This doc.
- Whitepaper §8 跨模型 row update (below) + audit-log entry applied with
  the commit.
