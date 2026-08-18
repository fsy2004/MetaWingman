# Appraisal-Step Component — V3 Training Results & VAL-2b Freeze

**Date:** 2026-08-18
**Component:** appraisal-step domain classifier (six risk-of-bias domains)
**Preregistration:** `docs/architecture/appraisal-step-component-preregistration-2026-08-18.md`
**Human-blind protocol:** `docs/architecture/appraisal-human-blind-spotcheck-protocol-2026-08-18.md`

## 1. Training run (V3, receipt-verified)

- Server: AutoDL 4090 D, conda env `/root/autodl-tmp/condaenvs/metawingman`
- Launcher: `/root/autodl-tmp/appr-train.sh` (fetches `codex/github-beta` from
  the Gitee mirror and checks out `run_appraisal_step_training.py` before each
  run). The V3 run executed the script at commit `4bc303a` (the weight fix).
- Data: `validation-output/training-corpus/appraisal-step-candidates.jsonl`
  (9,906 records; 7,932 train / 1,974 development).
- Model: `microsoft/BiomedNLP-BiomedBERT-base-uncased-abstract-fulltext` @
  `e1354b7a3a09615f6aba48dfad4b7a613eef7062`, 6-way sequence classification.
- Hyperparameters: 3 epochs, batch 8 × grad-accum 2 (effective 16), lr 2e-5,
  weight decay 0.01, warmup 10% of steps, bf16, seed 20260815, max_length 512.
- Loss: class-imbalanced cross-entropy with **per-class** inverse-frequency
  weights (fix `4bc303a`; the first attempt `043f0f3` passed per-example
  weights and crashed with a shape error — see
  `metawingman/scripts/run_appraisal_step_training.py:60`).

Receipt (`validation-output/training-runs/appraisal-step/execution-receipt.json`):

| metric | value |
|---|---|
| eval_macro_f1 (dev, best checkpoint) | **0.850008** |
| eval_loss | 0.405262 |
| train / dev records | 7,932 / 1,974 |
| elapsed | 224.4 s |
| torch | 2.13.0+cu130 |

Best checkpoint was the end of epoch 3 (checkpoint-1488); `final/` holds the
best model + tokenizer, hashed in the receipt.

## 2. What 0.85 macro-F1 does and does not mean

- **It does mean:** the 110M BiomedBERT can reproduce the deterministic
  weak-label rules on held-out appraisal passages with macro-F1 0.850 — i.e.
  the rules are learnable but not perfectly separable by a model this size.
- **It does NOT mean:** independent validation, clinical correctness, or
  agreement with human experts. The labels came from rules; the model learned
  the rules. This is the "rule-consistency ceiling" defined in the
  preregistration, and every downstream claim must use that vocabulary.

## 3. VAL-2b human-blind spot-check — frozen

Frozen 2026-08-18 by
`metawingman/scripts/build_human_blind_spotcheck.py` (seed 20260815), sampled
from the development split (1,974 records), n = 100.

| weak_label | n |
|---|---|
| selection_bias | 17 |
| detection_bias | 17 |
| attrition_bias | 17 |
| other | 21 |
| reporting_bias | 15 |
| performance_bias | 13 (entire dev pool) |

SHA-256 (also recorded in the manifest, verified identical on server and
local download):

- `blind-questions.jsonl` `ff505f5521aca733db517a942f710e6be3526bd758f2a1f20ddbf5c8d4aa3950`
- `answer-key.jsonl` `920930011fc9550360e111bbffe197b8fb64976bffb34fba837d2e4a8fe4525b`

Local copies for the human-review window:
`validation-output/independent-validation/human-blind-appraisal-spotcheck/`
(questions for rating; the answer key must not be opened until rating is
complete).

## 4. Pending and next steps

1. **Human rating window (user):** rate the 100 questions per the protocol;
   then compute Cohen's kappa + per-class agreement against the sealed key.
   This measures rule clarity — it decides whether the 0.85 ceiling is
   "model too small" or "rules themselves ambiguous".
2. **Benchmark vs arXiv:2606.17041:** planned frozen-split comparison once
   the human rating establishes the rule ceiling (see next-steps doc).
3. **Possible V4:** if kappa is high (>0.81) but model consistency plateaus
   below it, retrain with more epochs / larger model / RoBERTa-large to chase
   the ceiling; if kappa is low, revise the weak-label rules first and
   re-freeze a new VAL-2b generation (old generation retained).

## 5. Training lessons (meta-update loop)

- **Class-imbalanced cross-entropy weights are per-class, not per-example.**
  `torch.nn.functional.cross_entropy(weight=...)` expects one weight per
  output class (length = num_classes). Passing per-example weights fails with
  a shape error ("weight tensor should be defined either for all N classes").
  The V3 fix computes per-class inverse-frequency weights with zero weight for
  classes absent from the training split
  (`metawingman/scripts/run_appraisal_step_training.py:60-72`). Source:
  commit 4bc303a, verified by the V3 re-run receipt.
