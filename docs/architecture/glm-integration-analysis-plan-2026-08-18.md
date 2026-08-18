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
