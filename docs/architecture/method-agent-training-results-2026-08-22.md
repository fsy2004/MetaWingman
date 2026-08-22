# Method-agent training results — 2026-08-22

## Why this run was started

The project method framing was restored from a safety/audit-heavy presentation to the original strong-agent story: Review Question Certificate, Socratic stage reflection, PRM-style step verification, and Meta-update/distillation. Training was then rerun to test whether this method behavior is learnable rather than only described in prose.

## Protocol-method bootstrap

This run updated the protocol-stage bootstrap target so that each trained action includes a `method_trace` covering Review Question Certificate linkage, Socratic stage reflection, step verification, and meta-update.

| Field | Value |
|---|---|
| Source build | `7d260b8b6dca1974` |
| Export SHA-256 | `c7e0ff1f613173cb6f67f955e5a4684ff07b0710e83445718ccbea63b2ebe565` |
| Readiness SHA-256 | `f69789a92e7a3c4ea09fc8433ca528a94af8f46cee15d23cf9ebb486fbef93a0` |
| Receipt SHA-256 | `34a66c29f2705fe7c6adc0f61a9a9cafb17a65ba430102933f4c5ae946a1dd06` |
| Base model | `Qwen/Qwen2.5-1.5B-Instruct`, revision `989aa7980e4cf806f80c7fef2b1adb7bc71aa306` |
| Train / development examples | 15 / 4 |
| Development family scope | one BMJ adult-depression exercise NMA development family |
| Wall time | 72.47 s |

| Metric | Base | Student |
|---|---:|---:|
| Complete-method-action accuracy | 0.000 | 0.750 |
| Complete-action accuracy | 0.000 | 0.750 |
| JSON validity | 1.000 | 1.000 |
| Method-trace completeness | 0.000 | 1.000 |

Interpretation: positive development bootstrap for method-trace learning, not unseen-family or full-agent evidence.

## Multi-family Skill-method protocol-action run

This is the stronger method-agent run. It trains a student to emit action, decision, and method trace across development families, with deterministic action balancing to avoid collapse into common labels.

| Field | Value |
|---|---|
| Source build | `4804d7935605b4c4` |
| Corpus root | `/root/autodl-tmp/metawingman-agent-distillation/multifamily-protocol-4804d7935605b4c4/corpus` |
| Training receipt | `/root/autodl-tmp/metawingman-agent-distillation/multifamily-protocol-4804d7935605b4c4/training-seed-20260820/run/training-receipt.json` |
| Receipt SHA-256 | `c3eee98cd1cab8c8c93daca57ec76a93d453f6c9b21910f9cbad88ba8fca387f` |
| Corpus manifest SHA-256 | `291e463a79a7248a3ebd211c46524390119c32395f74167559a95c26e505d0bf` |
| Train corpus | 1,130 raw examples, 157 families |
| Development corpus | 357 examples, 55 families |
| Scored development subset | 200 examples, 53 families |
| Balanced training size | 3,033 examples |
| Primary metric | `complete_method_action_accuracy` |
| Wall time | 1,634.66 s |

Raw action counts were imbalanced (`certainty=10`, `reporting=5`, `synthesis=337`). The training loader therefore used deterministic upsampling to equalize all nine action classes to 337 examples each.

| Metric | Base | Student |
|---|---:|---:|
| Complete-method-action accuracy | 0.000 | 0.975 |
| Semantic-action accuracy | 0.000 | 0.975 |
| Decision accuracy | 0.000 | 1.000 |
| JSON validity | 0.575 | 1.000 |
| Method-trace completeness | 0.000 | 1.000 |

## Claim boundary

These results support the claim that the restored Skill-driven method behavior is learnable in protocol-action-stage development settings and across multiple development families. They do not establish full ten-stage systematic-review efficacy, independent confirmatory-family performance, clinical correctness, or human replacement.

The next result needed for the paper is a frozen baseline/general-control versus full Skill-method agent evaluation on unseen case families with matched resource budgets and complete action-execute-recompute receipts.

