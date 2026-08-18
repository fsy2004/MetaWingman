# GLM Integration Analysis Plan — Preregistered (2026-08-18)

> Frozen BEFORE the GLM pilot results land. The integration step that follows
> the pilot may only run this analysis; any deviation must be recorded as an
> amendment. This prevents post-hoc metric selection.

## 1. Data (all already frozen)

| Piece | Frozen identity |
|---|---|
| Task set | 200-task blind sample, `blind-tasks.jsonl` sha256 `38c65be79575a8e1c68e5abcf57ece30a46ed55f4bacebe65cdaa5c28f2bf4ff` (47 strata, 999 passages) |
| Reference | sealed weak-label key (deterministic rules); unsealed by the scorer only after every provider call locks |
| DeepSeek C0-C3 | `validation-output/ai-only-pilot/report-C{0..3}.json` (2026-08-17), prompt hashes per config (frozen in the VAL-2b1 freeze doc) |
| GLM C0-C3 | server pilot `glm-pilot-2026-08-18/` (glm-5.2; deviation recorded: max_tokens 64→2048, prompt text unchanged; C3 prompt hashes identical to DeepSeek C3) |

## 2. Metrics (frozen set, nothing else headline-worthy)

Per configuration, per task:
1. section-role: macro-F1 vs sealed weak labels; per-class F1 reported.
2. retrieval: candidate-set MRR and P@1 (candidate semantics, as in the
   pilot preregistration; NOT the open-corpus metric).
3. abstention rate (abstain ≠ wrong; selective coverage reported jointly).
4. cost: provider calls, input/output/reasoning tokens.

## 3. Precommitted analyses (in order)

A. **Per-config table**: DeepSeek vs GLM side by side for C0-C3.
B. **Stack delta**: within each provider, C0→C3 change per task (does the
   verification stack help both providers?).
C. **Cross-provider agreement**: Cohen's kappa + 95% CI (Fleiss SE) on
   section-role predictions between the two providers at each config level,
   computed on the shared task set.
D. **Cost-quality view**: tokens per config per provider; no cost-efficiency
   headline without paired quality.

## 4. Claim bounds (binding on the integration doc)

- Everything is **agreement with frozen deterministic weak labels** on a
  development sample. No accuracy, no gold validation, no human comparison.
- Cross-provider agreement measures **provider-invariance of the prompt
  stack**, not scientific verification: two providers agreeing does not make
  a label correct (SKILL.md: multiple models from one provider are not
  independent verification; different providers are a limited cross-check,
  still not human gold).
- No "GLM is better/worse than DeepSeek" headline; report config-level
  differences with the deviation note (reasoning-model token budget) always
  attached.
- Whitepaper §8 跨模型 row gets: per-provider C3 macro-F1/MRR, kappa
  agreement, and the claim-boundary sentence verbatim.

## 5. Deliverables when results land

1. `docs/architecture/glm-cross-provider-results-2026-08-18.md` following
   this plan (analyses A-D in order).
2. Whitepaper §8 row update + audit-log entry (event_type fix/reflection)
   applied with the commit.

## 6. Amendments (recorded per plan §0; executed 2026-08-18/19)

1. **Scope: C3 only.** `run_r2_ai_validation.py` has no C0/C1/C2 switches on
   the frozen R2 task set; the GLM pilot ran C3 only (999 SR + 200 RT tasks).
   GLM C0-C2 rows do not exist; the DeepSeek C0-C3 ladder is context-only
   (different 2k-dev task set).
2. **max_tokens deviation chain:** 64 → 2048 (initial), then RT 4096 and SR
   4096 → 8192 after dead-letter diagnosis. GLM-5.2 reasoning tokens exhaust
   the output budget (empty content, finish=length); all 999 SR + 200 RT
   tasks recovered (0 abstains final). Prompt text unchanged; prompt sha256
   identical to DeepSeek C3.
3. **Correction of intermediate-state numbers:** commits `5785407` (n=927)
   and `58f4741` (994 scored / 5 abstained) carried pre-recovery numbers; the
   final checkpoint (999/999, 0 abstains) is authoritative
   (`validation-output/glm-pilot-2026-08-18/scoring-results.json`).
4. **kappa scope:** computable only at C3 on the shared task set (999
   passages); C0-C2 kappa not computable (different task sets).
