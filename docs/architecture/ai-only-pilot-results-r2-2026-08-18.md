# AI-only pilot results — R2-AI independent validation (2026-08-18)

> Round 2 of the AI-only validation: the preregistered C3 configuration
> (hosted DeepSeek + the two **12k retrained** components as verifiers) run over
> the project's 200-task blind sample. This is a **weak-label agreement**
> measurement, not independent gold validation, not accuracy, not human
> superiority.

## 1. What "R2-AI" and "200 blind tasks" mean here

The task brief described "200 blind tasks … sampled from benchmark materials …
compared against `published_expert_reference`". That framing does **not** match
this repo's frozen protocol, and the record is corrected here explicitly:

- **"200 blind tasks"** is the preregistered Part-A independent-validation
  sample (`docs/architecture/label-and-heldout-validation-protocol.md`):
  **200 development records** drawn deterministically across **47 strata**
  (seed `20260817`) by `metawingman/scripts/prepare_independent_validation_sample.py`,
  each record expanded to ≤6 source-anchored passages (**999 passages total**).
  It is materialized as `blind-tasks.jsonl` + a sealed `weak-label-key.json`.
- **The reference is the deterministic weak-label key**
  (`weak_label_status: deterministic_weak_candidate`), **not**
  `published_expert_reference`. The `published_expert_reference` concept belongs
  to the separate, unfrozen VAL-3 reconstruction benchmark. Its materials live
  in `validation-output/benchmark-materials/` (5 review families:
  `ag-rdt-living-update`, `bmj-covid-therapies-methods`, `carbon-pricing-screening`,
  `hepsanet-controlled-ipd`, `sci-exercise-analysis`) and contain **only**
  `operational_input` + `documentation` + fetch receipts — every fetch receipt
  records `sealed_unlocked: false` and no `sealed_reference`/`sealed_post_cutoff`
  artifact is present locally or on the server. No benchmark-material reference
  answer is available, so no task could be built from it.
- **R2-AI** = "round 2, AI as the (non-human) annotator": the C3 stack labels
  the blind passages; agreement is scored against the sealed weak-label key
  only after every provider call has locked.

All R2 numbers are therefore **agreement with frozen deterministic weak labels
that the trained components were themselves optimized to reproduce** — see
§8 (limitations).

## 2. Task-set construction (frozen)

| Parameter | Value |
|---|---|
| Builder script | `metawingman/scripts/prepare_independent_validation_sample.py` |
| Target records / minimum strata | 200 / 20 |
| Seed | `20260817` |
| Strata covered | **47** |
| Selected records | **200** |
| Passages (blind) | **999** (min 2, max 6, mean 4.995 per record) |
| Section-role labels in key | 822 unique `section_path` → role entries |
| Label distribution | synthesis 212 · search 155 · extraction 155 · selection 127 · appraisal 109 · eligibility 29 · certainty 20 · protocol 15 |

Source files (sha256, verified identical on server and locally):

| Role | Path | sha256 |
|---|---|---|
| blind task set | `validation-output/server-download/independent-validation/blind-tasks.jsonl` (server `/root/autodl-tmp/mw/validation-output/independent-validation/blind-tasks.jsonl`) | `38c65be79575a8e1c68e5abcf57ece30a46ed55f4bacebe65cdaa5c28f2bf4ff` |
| sealed reference key | `validation-output/server-download/independent-validation/weak-label-key.json` | `904fc501ccb6e3cdf559623572b6cb7c8b555886ee651d9b4ef85366cd691b41` |
| fulltext bundle | `validation-output/server-download/independent-validation/fulltext.tar.gz` | (6,531,311 bytes) |

Full construction manifest: `docs/architecture/r2-ai-task-set-manifest-2026-08-18.json`.

Retrieval tasks: the blind sample is a section-role labeling task and carries no
retrieval queries/candidates. To keep a retrieval column comparable in spirit to
the C0–C3 table, 200 retrieval queries were additionally drawn from the **12k
development split** with the same seed/order as the pilot
(`evidence_retrieval`, `split == development`, stable order by
`sha256("20260817:<example_id>")`), each with its positive + 3 hard negatives
(4 candidates). This retrieval run is **supplementary**, not part of the blind
sample.

## 3. Configuration (C3, frozen prompt)

- Hosted model: `deepseek-v4-flash` via `https://api.deepseek.com`
  (`metawingman/references/deepseek-provider-config.json`); key read from
  `/root/autodl-tmp/.secrets/deepseek_key` (never logged).
- Verifiers (12k retrained finals, server):
  - section-role: `BertForSequenceClassification` (BiomedBERT 110M, 8 roles) at
    `validation-output/training-runs/section-role/final`.
  - evidence-retrieval: `BertModel` bi-encoder (BiomedBERT 110M) at
    `validation-output/training-runs/evidence-retrieval/final`.
- C3 prompt text is **byte-identical** to the frozen pilot C3 prompts:

  | Prompt | sha256 |
  |---|---|
  | section_role | `394bd424d7d5cece4dbd340b2fb2ceb1707de492efa48183f2dfde8531d8e633` |
  | retrieval | `e3b07f1db9ea19b832247d2967f732a7c71d84922a0a5b143cadafd76a315604` |

- Model file sha256 (see `validation-output/r2-ai-2026-08-18/report.json`):
  section-role `model.safetensors` `9a7f4586e45bb67dfd831e706eb69b30a8ed394424cf274bf5e8cca4eb4b3620`;
  evidence-retrieval `model.safetensors` `604562bb167752e8dddf27cc2dab2b59950b2e88e9541560012261d0d7bbff9e`.

## 4. Results (C3-R2, 12k verifiers)

### 4.1 Section-role — 200-record blind sample (999 passages)

| Metric | C3-R2 hosted | 12k verifier alone |
|---|---|---|
| macro-F1 vs weak labels | **0.938531** | **1.000000** |
| abstained | 0 | — |
| passage-level agreement | 936 / 999 (93.69%) | 999 / 999 |
| record-level (all passages correct) | 154 / 200 (77.0%) | 200 / 200 |

Hosted per-class F1 (vs weak labels): eligibility **0.818**, selection 0.906,
extraction 0.934, appraisal 0.947, synthesis 0.954, search 0.970, protocol
0.979, certainty 1.000.

### 4.2 Retrieval — 200 dev queries from the 12k corpus (4 candidates each)

| Metric | C3-R2 hosted | 12k verifier alone |
|---|---|---|
| candidate-set MRR | 0.465 (pilot formula) | **0.953333** (standard) |
| P@1 | 0.20 (pilot formula) | **0.925** (standard) |
| **selection accuracy** (picked == gold index) | **0.93** | **0.925** |
| abstained | 0 | — |

### 4.3 Cost

| Section | provider calls | total tokens |
|---|---|---|
| section-role (999 tasks) | 999 | 619,081 |
| retrieval (200 tasks) | 200 | 823,340 |
| **total** | **1,199** | **1,442,421** |

0 abstentions, 0 schema repairs (every call accepted on first attempt).

## 5. Metric-definition note (important)

The two retrieval metric families are not interchangeable, and the C0–C3 table
mixed them:

- **Pilot formula** (`score_pilot_tasks`, used for the hosted C0–C3 rows):
  a single selected index; if it is the positive, contribute
  `1/(selected_index+1)`; P@1 counts only `selected_index == 0`. This is
  **capped by the candidate shuffle** — a perfect model's expected MRR is
  `(1 + 1/2 + 1/3 + 1/4)/4 ≈ 0.521`, and its P@1 is ≈0.25. The hosted C3-R2
  value 0.465 is therefore ≈89% of that ceiling, and 0.20 is near the 0.25
  ceiling; neither is a standard retrieval metric.
- **Standard candidate-set MRR/P@1** (used for the "trained components" row and
  here for the 12k verifier): sort the candidates by model score, take the
  positive's reciprocal rank. This is what the training report's
  "hard-negative MRR 0.962 / P@1 0.933" means.

The interpretable single-selection quantity is **selection accuracy** (picked
index == gold index): hosted **0.93** vs verifier **0.925**.

## 6. Comparison vs C0–C3 history

| Configuration | section-role macro-F1 | retrieval candidate MRR | retrieval P@1 | calls / tokens |
|---|---|---|---|---|
| C0 general-model-baseline | 0.853 | 0.408 | 0.195 | 400 / 930k |
| C1 + schema definitions | 0.908 | 0.415 | 0.215 | 400 / 951k |
| C2 + biomedical context | 0.880 | 0.405 | 0.205 | 400 / 1.04M |
| C3 + trained verifier (2k) | 0.967 | 0.495 | 0.240 | 400 / 1.03M |
| trained 110M components (2k) | 0.983 | 0.954 | 0.919 | 0 |
| **C3-R2 + 12k verifier (this run)** | **0.9385** | **0.465** | **0.20** | **1,199 / 1.44M** |
| **12k verifier alone (this run)** | **1.0000** | **0.9533** | **0.925** | 0 |

**Do not read this table as same-task-set.** C0–C3 used 200 examples per task
from the 2,048-record development split. R2 uses (a) the 999-passage blind
sample of 200 records from the 12k development split for section-role, and
(b) a fresh 200-query sample from the 12k development split for retrieval. The
rows are comparable **qualitatively** (same C3 prompt, same weak-label type,
same metric formulas), not as a strict numerical trend.

Qualitative takeaways:

1. The **12k retrained verifiers agree with the weak labels at ceiling**
   (section-role 1.0 on 999 passages, consistent with the reported eval
   macro-F1 0.9995; retrieval 0.953/0.925, consistent with the reported
   hard-negative MRR 0.962/P@1 0.933). This is expected — they were trained on
   the same deterministic label rules — and it is exactly why this is **not**
   independent validation.
2. The **hosted model does not improve over the verifier**:
   - section-role: hosted 0.9385 < verifier 1.0 — the hosted model overrides a
     *correct* verifier ~6% of the time and degrades the result (the C3
     verifier-weighting problem, now sharper with a perfect verifier).
   - retrieval: hosted selection accuracy 0.93 ≈ verifier 0.925 — the hosted
     model roughly follows (slightly improves on) the verifier.
3. The hosted model's retrieval "MRR 0.465 / P@1 0.20" is dominated by the
   shuffle-capped pilot formula (§5); the interpretable number is 0.93
   selection accuracy.

## 7. Receipts

- Per-run receipts (in `runs-sr.jsonl` / `runs-rt.jsonl`): every run carries
  `input_sha256`, `instruction_sha256`, and per-attempt `content_sha256`
  (provider output hashes) plus token usage — no provider output or source text
  is stored beyond these hashes.
- Run report with model/task-set hashes and token totals:
  `validation-output/r2-ai-2026-08-18/report.json`.
- Scoring output (per-passage and per-query pass/fail):
  `validation-output/r2-ai-2026-08-18/scoring-results.json`.
- The DeepSeek API key appears in no file, log, or commit (read from
  `/root/autodl-tmp/.secrets/deepseek_key`, `credential_source:
  environment:DEEPSEEK_API_KEY`).

## 8. Honest limitations

- **Weak labels, not gold.** The reference is the deterministic weak-label key;
  the 12k verifiers were trained to reproduce those same rules, so their
  ~1.0 / ~0.95 agreement is circular and says nothing about correctness. The
  independent **human** annotation arm (Part A) remains the only path to gold,
  and it has not run.
- **No `published_expert_reference`.** The VAL-3 reconstruction benchmark is
  unfrozen; its sealed answers are absent locally and on the server, so nothing
  here is a published-expert comparison.
- **Task-set shift.** R2's section-role is on the 12k blind sample (not the 2k
  pilot examples); R2's retrieval is on a fresh 12k dev sample. Cross-row
  numeric comparison with C0–C3 is qualitative only.
- **Retrieval metric ambiguity.** The pilot's hosted retrieval formula is
  shuffle-capped and was historically conflated with the standard candidate-set
  MRR; both are reported and labeled here (§5).
- **No repeat runs.** Like the pilot (repetitions = 1), R2 ran once per task.
- **Prompt/context deviation.** The `biomedical_context` input_document field
  that the pilot's C2/C3 added was omitted for both tasks: the C3 prompt text
  does not reference it, and for the blind section-role tasks including it would
  leak the reference stratum (blindness). The C3 prompt hashes are unchanged.

## 9. Protocol deviations (explicit)

1. Task-set source: the "200 blind tasks" are the Part-A independent-validation
   sample, **not** benchmark-material-derived tasks; benchmark materials contain
   no reference answers (documented in §1 and the manifest).
2. `biomedical_context` omitted from C3 input_document (blindness / prompt does
   not reference it).
3. Retrieval run added as a supplementary 12k-dev sample (the blind sample is
   section-role-only).
4. Hosted retrieval metric reported both in the pilot's shuffle-capped formula
   (for C0–C3 comparability) and as standard selection accuracy.
