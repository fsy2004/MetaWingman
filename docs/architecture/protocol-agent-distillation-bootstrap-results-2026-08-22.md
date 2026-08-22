# Protocol-agent distillation development bootstrap — 2026-08-22

## Result

A governed LoRA bootstrap was completed on the protocol-registration component.
Across three fixed seeds, the unadapted base model scored 0.000 mean complete-action
accuracy on four action-group-held-out development spans; the adapted students
scored 1.000, 1.000, and 0.750 (mean 0.917). JSON validity was 1.000 for both base
and student models in every seed.

This is a positive **development-only** learning signal. It is not evidence of
cross-family generalization, complete-agent improvement, or systematic-review
accuracy.

## Frozen inputs

- Case: `bmj-exercise-depression-nma`, an authoritative and broadly relevant adult
  depression network meta-analysis ([BMJ](https://www.bmj.com/content/384/bmj-2023-075847),
  [PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC10870815/)).
- Source: licensed JATS methods only (`CC BY-NC`), SHA-256
  `01a4b69271df51d9e68f2b4ebd27be531d41ab5ed32222e2e4a9b759be5fcff7`.
- Export: 19 exact source-anchored positive protocol actions; no abstract, results,
  discussion, conclusion, held-out case, or published answer was used as a label.
- Governance export SHA-256: `e184f8e627d60d002fd7fb8799355518184c92c2596a95af72959f835d7ffa54`.
- Readiness SHA-256: `15d65126155947ff4c95637e814396eec3c02e8e5d5de31247fbfe015b0d05ce`;
  readiness was true with no blockers.

## Model and evaluation

The student base was
[`Qwen/Qwen2.5-1.5B-Instruct`](https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct)
at commit `989aa7980e4cf806f80c7fef2b1adb7bc71aa306` (Apache-2.0). Each seed used
LoRA rank 8, alpha 16, dropout 0.05, eight epochs, and learning rate 0.0002.
Fifteen spans were used for training and four for deterministic development
evaluation. A complete action required exact action type, exact source section,
and exact decision status.

| Seed | Base complete accuracy | Student complete accuracy | Base JSON valid | Student JSON valid | Wall time (s) |
|---:|---:|---:|---:|---:|---:|
| 20260822 | 0.000 | 1.000 | 1.000 | 1.000 | 1530.55 |
| 20260823 | 0.000 | 1.000 | 1.000 | 1.000 | 41.39 |
| 20260824 | 0.000 | 0.750 | 1.000 | 1.000 | 42.32 |
| **Mean** | **0.000** | **0.917** | **1.000** | **1.000** | — |

The first wall time includes the one-time model download. Monetary server cost was
not available and is recorded as `null/unknown`. Adapter weights remain on the
controlled server; Git contains only hashes and the public receipt.

## Claim boundary and next gate

The held-out spans come from the same article and share its review family. The
experiment can therefore support only `development_only_student_gain_not_generalization`.
Promotion requires frozen base-versus-student-versus-teacher evaluation on unseen
authoritative review families under matched budgets, followed by stage-level and
complete-lifecycle scientific outcomes. The exact public receipt is
[`research/protocol-agent-distillation-training-receipt-v1.json`](../../research/protocol-agent-distillation-training-receipt-v1.json).
