# AI-Only Component Pilot — Preregistration (v0)

> Freezes the design of a bounded AI-only pilot comparing the trained
> components against a general hosted model on the frozen development sets.
> This is a pilot preregistration (VAL-2b-lite), NOT the end-to-end
> reconstruction benchmark (VAL-3): the reconstruction cases still need
> licensing/cutoff resolution (VAL-1) before their task manuals can be frozen.
> Status: design frozen; config C0 run gated on explicit budget approval.

## 1. Scope and honest limits

- Task set: the two trained component tasks on the **development split only**
  (section-role classification, evidence retrieval).
- Reference: **deterministic weak labels** (source-anchored), not human gold.
  Results are "agreement with the frozen weak labels", never absolute accuracy
  or human superiority.
- The end-to-end four-configuration benchmark in
  `ai-only-evaluation-plan.template.json` stays unfrozen; nothing in this pilot
  may be presented as that benchmark.

## 2. Frozen task definitions

| Field | Value |
|---|---|
| section-role task | input = `input_text`; predict one of the 8 frozen roles (`search, eligibility, selection, extraction, appraisal, synthesis, certainty, protocol`) |
| retrieval task | input = `_retrieval_query(example)` (field + review title); candidates = the query's positive + hard negatives from the frozen pairs |
| sampling | 200 dev examples per task, deterministic order by `sha256(seed:example_id)`, seed `20260817` |
| repetitions | **1** (pilot; the frozen protocol's 3 reps apply to the full benchmark, not this pilot) |

## 3. Frozen configurations

- **C0 general-model-baseline** (runs first): hosted DeepSeek model, raw prompt
  "Predict the systematic-review workflow role of this passage" with no
  MetaWingman schema, terminology, routing, or verifier context.
- **C1 biomedical-schema** (follow-up): prompt carries the exact 8-role output
  schema and per-role definitions.
- **C2 biomedical-routing** (follow-up): C1 + the record's biomedical stratum
  (specialty, question type) as context.
- **C3 full-biomedical-stack** (follow-up): C2 + the trained component as
  verifier; disagreement routes to abstention.

Each configuration's prompt text must be frozen (sha256) before its run. Only
C0's prompt is drafted below; C1–C3 prompts are frozen when scheduled.

C0 prompt (draft, to be hash-frozen at run time):

```
You are classifying a passage from a systematic review. Output ONLY JSON:
{"section_role": "<one of search|eligibility|selection|extraction|appraisal|synthesis|certainty|protocol>"}
Passage:
<passage text>
```

## 4. Frozen metrics and inference limits

- section-role: macro-F1 vs weak labels; per-class F1 reported.
- retrieval: hard-negative MRR and P@1 vs frozen pairs; full-corpus recall@10
  and MRR vs dev examples (trained model only; hosted model gets the
  candidate-set metric).
- Cost accounting: model calls, input/output tokens, wall time per
  configuration.
- Allowed claims: agreement with frozen weak labels; risk-coverage-latency-cost
  comparisons between configurations and the trained components.
- Forbidden claims: human superiority, labor savings, absolute accuracy,
  "validated" performance.

## 5. Budget and sealing

- Caps: ≤ 200 calls per task per configuration, ≤ 2,048 reserved output tokens
  per call, ≤ 1 repair call per task on schema failure (then abstain).
- Sealing: weak labels live in the key file only; the scorer reads the key
  after every provider call for that task has locked (no answer-driven
  re-prompting).
- Any configuration run that exceeds its cap is reported as incomplete, not
  scored.

## 6. Execution checklist

1. Freeze C0 prompt hash into the run record.
2. Sample the 200-example task files with seed `20260817`.
3. Run C0 via the provider-neutral batch runner against DeepSeek
   (`provider-config` + environment secret, never committed).
4. Score against the sealed key; write `ai-only-pilot-run.jsonl` + a summary.
5. Decide C1–C3 scheduling with the user; every later configuration repeats
   the same tasks with its frozen prompt.
