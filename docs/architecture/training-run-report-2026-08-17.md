# MetaWingman 4090 Component Training Run Report (2026-08-17)

> First real server training-gate execution. Every number below is read from
> the receipts, manifests, and logs archived under
> `validation-output/server-download/` (ignored by git, kept for provenance).
> Status: components trained and benchmarked at matched cost; the end-to-end
> AI-only benchmark remains gated behind task-manual freezing (VAL-2b/VAL-3).

## 1. Server and environment (measured)

| Item | Value |
|---|---|
| Host | AutoDL container, `root@connect.westb.seetacloud.com:12977` |
| GPU | NVIDIA GeForce RTX 4090 D, 24564 MiB, driver 595.71.05 |
| GPU usable | 23.52 GiB (torch) → jobs rebuilt with `gpu_memory_gib_each: 23` |
| RAM / disk | 503 GiB / 650 GiB at `/root/autodl-tmp` |
| Python | 3.12 (conda env `/root/autodl-tmp/condaenvs/metawingman`) |
| torch | 2.13.0+cu130, CUDA 13.0, `cuda.is_available()=True` |
| transformers | 5.15.0 (two API changes fixed, see §5) |
| HF endpoint | `https://hf-mirror.com` (huggingface.co unreachable from server) |
| pip index | AutoDL aliyun mirror |
| Repo | `/root/autodl-tmp/mw`, checkout `e74dc03` + patched files (see §5) |

## 2. Data pipeline (all gates green)

- Download (Europe PMC fullTextXML + PMC OA Web Service license/retraction
  check per record): **2,048 planned → 1,278 complete, 756 partial, 14 failed**;
  every record `verified_not_retracted`; 4 license=`none` records rejected
  fail-closed; 3,313 artifacts, 3.33 GB.
- `freeze_base`: **15,136 weak-supervised examples** (11,968 train / 3,168 dev /
  0 held-out) from 2,040 review families.
- `audit_training_dataset`: `valid: true`, 0 issues.
- `export`: **30,272 pairs** (7,568 positives + 22,704 hard negatives) across
  1,864 families; no negative crosses split or family.
- Frozen run-plan v1.1 (hashes): manifest `22c991f7…`, examples `da4cdae…`,
  pairs `4906a131…`.

## 3. Preflight and training results

Both rebuilt server jobs (`section-role-server.json`,
`evidence-retrieval-server.json`) passed `preflight --inspect-server` with
`ready: true`, empty `reason_codes` / `scientific_blockers` /
`server_checks_pending`, and `--validate-only` with `manifest_valid: true`.

| Component | Epochs / batch / precision | Result (dev) | Wall time |
|---|---|---|---|
| section-role classification | 3 / 16 / bf16, warmup 112 steps | **macro-F1 0.9869**, eval loss 0.0448 (1,584 dev examples) | 130 s |
| evidence retrieval (in-batch) | 3 / 16 / bf16 | train mean loss 2.057 (random ≈ ln16 = 2.77) | 327 s |

Receipts with full checkpoint hashes:
`section-role-execution-receipt.json`,
`evidence-retrieval-execution-receipt.json` (archived locally). Final models
are safetensors under `validation-output/training-runs/<component>/final/` on
the server; `torch_version: 2.13.0+cu130` in both receipts.

## 4. Component benchmark at matched cost

| Metric (dev) | Baseline | Trained component |
|---|---|---|
| section-role macro-F1 | majority-class 0.0459 | **0.9869** |
| retrieval MRR (1,584 queries) | TF-IDF lexical 0.556 | **0.824** |
| retrieval P@1 | TF-IDF 0.316 | **0.698** |

Baselines and the trained-model re-evaluation were run by
`mw-baseline.py` (exploratory, outside the frozen pipeline; log archived).
These numbers use weak-supervised labels — they are development metrics, not
an independent validation claim.

## 5. Defects found by real execution and fixed (all pushed to `codex/github-beta`)

1. `e41dbc8` — server handoff shipped only the training lock; the data
   pipeline needs the core lock (jsonschema) and the pdf lock (PyMuPDF).
   `SERVER_RUNTIME_LOCKS` now includes both + regression test.
2. `72d9707` — `build_retrieval_pairs` tokenized every candidate per query
   (O(n²) tokenization; hours at 2,048-record scale). Precomputed token sets
   keep identical output; 30,272 pairs exported in minutes.
3. `19b46cb` — transformers 5.x dropped `TrainingArguments.warmup_ratio`;
   runner now materializes `warmup_steps = round(ceil(n/batch)·epochs·ratio)`
   (semantically identical) + unit test.
4. `2d21059` — transformers 5.x hard-requires `save_steps` to be a multiple of
   `eval_steps` under `load_best_model_at_end`; `eval_steps` now aligns to the
   frozen checkpoint cadence (250).

## 6. Known limitations and honest gates

- **Degenerate retrieval metric**: the runner's `development_recall_at_10` is
  1.0 by construction (each query has 1 positive + ≤3 hard negatives, so
  top-10 always contains everything). MRR/P@1 in §4 are the meaningful
  numbers; the frozen metric needs a redesign (tracked as an issue).
- Weak labels are deterministic candidates, **not gold**; no independent
  human validation has run (`label-and-heldout-validation-protocol.md`).
- Held-out is disabled (0 held-out families); results are development-only.
- No publisher authentication and no end-to-end AI-only benchmark: VAL-2b
  (task manuals, loss weights, thresholds, sealed references) must be frozen
  before any honest VAL-3 run. Nothing here claims human superiority or
  absolute accuracy.
- Server checkout was `e74dc03` + the patched files above; doc-only commits
  since then (through `2d21059`) do not affect the training code paths.

## 7. Reproducing

The exact sequence is `mw-setup.sh` → `mw-download.sh` → `mw-freeze.sh` →
`mw-export.sh` → `mw-jobs.sh` → `mw-train.sh` under
`~/.agents/tools/mw-server/` (run via `mws.py`), with the handoff-verified
repo, the frozen v2 plan, and the environment of §1. All hashes are pinned in
the run-plan, job manifests, and receipts.
