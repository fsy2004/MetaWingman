# VAL-2b1: Component-Axis Task-Manual Freeze (2026-08-18)

> Roadmap item VAL-2b ("fill and freeze task manuals, scientific loss weights,
> release thresholds, configuration hashes, and stopping rules before any
> held-out model run") is split into **VAL-2b1** (component axis; frozen in
> this document) and **VAL-2b2** (reconstruction-case manuals; still blocked on
> VAL-1 licensing/cutoff promotion of the five benchmark families).

## 1. Scope and honest limits

This freeze covers the **component-axis AI-only evaluation**: the two trained
component tasks (section-role classification, evidence-excerpt retrieval) on
the frozen development sample, scored against the **sealed deterministic
weak-label key**. It does **not** cover end-to-end reconstruction
(`published_expert_reference`), which remains VAL-1/VAL-2b2/VAL-3.

Allowed claims stay exactly those of the preregistration
(`docs/architecture/ai-only-pilot-preregistration.md`): agreement with frozen
weak labels; risk-coverage-latency-cost comparisons between configurations and
the trained components. Forbidden: human superiority, labor savings, absolute
accuracy, "validated" performance.

## 2. Frozen task manuals (index of frozen artifacts)

| # | Manual | Frozen artifact | Identifier |
|---|---|---|---|
| 1 | Blind task set | 200 development records / 47 strata / 999 passages, builder `metawingman/scripts/prepare_independent_validation_sample.py`, seed 20260817 | `blind-tasks.jsonl` sha256 `38c65be79575a8e1c68e5abcf57ece30a46ed55f4bacebe65cdaa5c28f2bf4ff` |
| 2 | Weak-label key | sealed; read only after every provider call locks | key file under `validation-output/independent-validation/` |
| 3 | Ten Socratic stage checklists | `references/socratic-checklists/*.json` at commit `87888d0` (all ten stages, 9 required + 1 optional each) | gate: `scripts/check_socratic_checklist.py --stage <stage>` |
| 4 | VAL-2c human spot-check | protocol `docs/architecture/appraisal-human-blind-spotcheck-protocol-2026-08-18.md` | questions `ff505f5521aca733db517a942f710e6be3526bd758f2a1f20ddbf5c8d4aa3950`, key `920930011fc9550360e111bbffe197b8fb64976bffb34fba837d2e4a8fe4525b` |
| 5 | Appraisal step verifier rules | `metawingman/scripts/verify_appraisal_steps.py` (10-step rule verifier, abstain/human-window flags) at commit `f7075c1` | report schema `appraisal_step_verification_report.schema.json` |
| 6 | Review Question Certificate | `generate_review_question_certificate.py` + `review_question_certificate.schema.json` | 7-stage derivation, hard/soft gates |
| 7 | Blind judge protocol | `blind_judge_certificates.py` (dual-judge, strips audit/quality_scores/gate) | judge-report schema |

The ten checklists also serve as the **stage manuals** of the main skill
workflow (Stage 0 topic, 1 protocol, 2 search, 3 screening, 4 extraction,
5 appraisal, 6 analysis+reproducibility, 8 writing, 9 update).

## 3. Frozen configurations (C0–C3)

Configuration ids map onto the canonical four of
`references/ai-only-evaluation-plan.template.json`. Prompt hashes below are
the frozen per-task prompt texts recorded by the DeepSeek pilot run records
(`validation-output/ai-only-pilot/report-C*.json`, 2026-08-17); the R2-AI
12k-verifier rerun and the GLM pilot reused the same C3 prompts (R2 results
doc, line 218).

| Config | canonical id | section_role prompt sha256 | retrieval prompt sha256 |
|---|---|---|---|
| C0 | general-model-baseline | `a1bcce33671e6f05a84a69b9925333094a08d14121f3a0a80e454ba48b4274f4` | `02611df4c23fe9b3f9fc8c495cb41228e39803f63204572a6bf42ea8b69dda01` |
| C1 | biomedical-schema | `0b4803f1aa0f3763a77f70b3c69446938bc5cf867d2dd5b763a004eb6dad5bd2` | `967c4caadc25a874fcd490df0dae464132be39335702b12dbc73aa24cdf48855` |
| C2 | biomedical-routing | `fc131f3e107627d0ea1a8642645e1c22871783005eb673a720e3c578833de364` | `a1280b2ecf9237a6b6b735471758eda3af17a81585809419316c16a62045a291` |
| C3 | full-biomedical-stack | `394bd424d7d5cece4dbd340b2fb2ceb1707de492efa48183f2dfde8531d8e633` | `e3b07f1db9ea19b832247d2967f732a7c71d84922a0a5b143cadafd76a315604` |

Model pins: hosted provider resolved at run time and recorded per run record
(registry template `deepseek-model-registry.template.json`); trained verifiers
pinned at `BiomedBERT-base-uncased-abstract-fulltext` revision
`e1354b7a3a09615f6aba48dfad4b7a613eef7062` with checkpoint hashes in each
training receipt. GLM runs use `glm-5.2` (max_tokens deviation 64→2048 is a
GLM-variant deviation recorded in the run report, prompt text unchanged).

## 4. Frozen scientific loss weights (asymmetric error weights)

Adopted binding from the evaluation-plan template (design choices, project
convention — not literature-derived; the asymmetry encodes that integrity
violations outweigh content errors):

| error class | weight | justification |
|---|---|---|
| unauthorized_action | 20 | process-integrity violation (credentials, unlawful retrieval, out-of-bounds tool use); double weight because it is never a "near miss" |
| false_exclusion | 10 | a study wrongly excluded can change a review's conclusion |
| unsupported_value | 10 | a number without an anchor poisons downstream synthesis |
| unanchored_claim | 10 | claim-level analogue of unsupported values |
| missed_required_abstention | 10 | proceeding where the verifier required abstention converts uncertainty into error |

## 5. Frozen release thresholds and claim rules

- `max_critical_error_rate = 0` — any critical error (weighted classes above)
  blocks every release claim for that configuration until root-caused.
- `min_run_to_run_reliability = 0.90` — exact-output agreement across the
  frozen repetitions (3 reps per the plan schema); below this the configuration
  is not release-eligible.
- `max_position_sensitivity = 0.05` and `max_judge_order_sensitivity = 0.03`
  (absolute metric deltas; frozen limits required by the falsification matrix,
  line 63; position-bias measurement follows the LLM-as-judge measurement
  practice of Zheng et al. 2023, arXiv:2306.05685, used here as measurement
  practice only).
- **VAL-2c kappa bands** (rule clarity, convention): ≥0.81 near-perfect,
  0.61–0.80 substantial, 0.41–0.60 moderate, <0.41 rules must be revised
  (Landis & Koch 1977, doi:10.2307/2529310 — convention only).
- `min_coverage` / `min_accuracy`: **report-only at this phase** (0 in the
  machine-readable plan). Accuracy/coverage claims become eligible only when
  the safety ceilings hold AND at least two reconstruction families have
  completed (VAL-3).

## 6. Frozen stopping rules

- Per-task caps: ≤200 provider calls per task per configuration; ≤2,048
  reserved output tokens per call (GLM variant: 2,048 budget applied, recorded
  as deviation); ≤1 schema-repair call on schema failure, then abstain.
- Any configuration exceeding its cap is reported **incomplete, not scored**.
- Abstention is counted separately from wrong answers; selective coverage is
  reported jointly with risk (never coverage alone).
- Dead letters (crash/hash-invalid attempts) are recorded and excluded from
  held-out scoring, with counts reported.
- Answer sealing: the weak-label key is readable by the scorer only after
  every provider call for that task has locked; no answer-driven re-prompting.
- Repetitions: pilot phase used 1 rep (preregistration §2 carve-out); the
  frozen plan requires **3 reps** for any release-eligible comparison.

## 7. Still open (not frozen here)

- **VAL-1**: license/cutoff promotion of the five benchmark families → **VAL-2b2**
  reconstruction-case manuals → **VAL-3** end-to-end runs.
- Full-benchmark configuration hashes for reconstruction tasks (search,
  screening-at-scale, extraction forms) — created when VAL-2b2 freezes.
- `max_mean_wall_clock_seconds` / `max_mean_total_cost` ceilings: intentionally
  left unfrozen until two provider cost baselines exist (cost is reported,
  not gated, at this phase).

## 8. Machine-readable plan

`research/ai-only-evaluation-plan.val2b1-v1.0-frozen.json` — validated against
`schemas/ai_only_evaluation_plan.schema.json` (JSON Schema 2020-12). The
schema's single per-configuration `prompt_sha256` carries the **section_role**
hash; the retrieval hash lives in this document's §3 table and in the run
records.
