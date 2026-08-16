# MetaWingman Component Training — Frozen Decisions

> Authoritative freeze for the first two biomedical component training jobs.
> Any change to a frozen value must be recorded as a revision, re-hash the
> affected artifacts, and re-run preflight — never edited in place.
> Status: local freeze complete; server execution requires explicit authorization.

## 1. Frozen base model

| Field | Frozen value |
|---|---|
| Repository | `microsoft/BiomedNLP-BiomedBERT-base-uncased-abstract-fulltext` |
| Revision (model + tokenizer) | `e1354b7a3a09615f6aba48dfad4b7a613eef7062` (immutable) |
| Declared license | MIT |
| Release intent | `internal_research_only` |
| Model card | https://huggingface.co/microsoft/BiomedNLP-BiomedBERT-base-uncased-abstract-fulltext |

Preflight rejects any mutable revision (e.g. `main`). The model card and Hub
metadata must be re-checked at execution time; raw-source redistribution and
public checkpoint release stay blocked pending a separate dataset-license review.

## 2. Frozen seed

`seed = 20260815` (both jobs). Python/NumPy/Torch/trainer seeds are all set from
this value by `run_component_training.py`.

## 3. Frozen optimization (both jobs)

| Field | Value |
|---|---|
| epochs | 3 |
| batch_size | 16 |
| learning_rate | 2e-5 |
| weight_decay | 0.01 |
| warmup_ratio | 0.1 |
| precision | bf16 |
| selection metric | section-role `macro_f1`; retrieval `retrieval_recall_at_10` |
| checkpoint cadence | every 250 steps, keep ≤ 3 |
| resume policy | only from checkpoint hashes listed in the job ledger |

> Precision/GPU coupling: `bf16` is native on Ada-class cards (RTX 4090). On
> Ampere-class cards (RTX 3090) bf16 is not natively supported and runs via
> slow emulation; if the rented GPU is a 3090, re-freeze `precision` to `fp16`
> for that server and re-run preflight before training.

## 4. Frozen resources

1× GPU with 24 GiB VRAM (single card; multi-GPU not used), 16 vCPU, 64 GiB RAM,
500 GiB NVMe, network required. A 24 GiB card (RTX 4090 / RTX 3090 class) is the
declared floor; see `compute-and-deployment-budget.md`.

## 5. Frozen dependency lock

`metawingman/references/dependencies/python-training.lock.txt`
(SHA-256 `30399f1a0c7abacb4092e546e9e25ff357c9145a8e18c2853d9e78e9c44287ee`):

```text
accelerate==1.14.0
datasets==5.0.1
numpy==2.5.2
safetensors==0.8.0
scikit-learn==1.9.0
torch==2.13.0
transformers==5.15.0
```

Python 3.12. A server/CUDA-specific transitive hash lock and a driver-matched
Torch wheel must be resolved at execution time.

## 6. Frozen data contract (pilot vs 2048-record plan)

The two job manifests currently point at the **local 24-family pilot** artifacts
(160 train / 12 dev examples, 311 train / 20 dev retrieval pairs):

- `training-examples.jsonl` SHA-256 `1c62c5e1af2a03c636bd0ef87208b5aab7e76d8a6686eb986b202c73d16e0429`
- retrieval pairs SHA-256 `8bf65c104372e48cfb9a55e4a8e73d906cbe9b01b1d49fa8c5d1d6537b057605`
- run plan (biomedical-v2) SHA-256 `84844d8dd6e17d71d0b7e9aecd3e35fd1dfa0923cafb4dd9211c3f6de0a3d62b`

The 2,048-record `training-corpus-plan-biomedical-v2.json` is **metadata-only**;
its full text has not been downloaded. At server time the component jobs MUST be
**rebuilt against the server-local file hashes** (runbook step 6). The frozen
values above (model, seed, hyperparameters, resources, lock) carry over; only the
data paths/hashes are re-materialized.

## 7. Split, family isolation, and held-out policy

- Split policy: `family_hash_80_10_10_suggestion_only` — a suggestion, not an
  active split.
- Split boundary: by **review family only**; no record may cross train/dev/test
  within a confirmed family.
- Held-out: **disabled**. `held_out_ready_families = 0`. No record in the plan
  carries `held_out`; every record is
  `provisional_family_isolated_not_held_out` until the family audit passes.
- Journal identity is never a model feature or target; it is used only for
  reporting and tie diversity.

## 8. Label policy — weak candidates, never gold

- Deterministic biomedical strata (title + publication-type matching) are
  `deterministic_weak_candidate`, never `verified`.
- Model-generated annotations are candidates, never auto-promoted to gold.
- `verify_training_annotations.py` enforces only **exact source-substring
  anchoring**; its acceptance boundary is
  `exact_anchor_verified_but_not_independently_validated_not_gold`.
- A label becomes gold only through an independent, pre-registered human
  validation arm (see `label-and-heldout-validation-protocol.md`).

## 9. Negative-sample rules

- One positive pair per anchored example.
- Up to three negatives per positive, drawn from the **same split** and the same
  primary specialty or question type.
- Excluded as negatives: the same record, the same review family, the exact
  source span, and likely companion reports.
- Negatives are ordered by deterministic token overlap + seeded hash.
- Every negative is marked `candidate_hard_negative_not_gold`; no negative may
  cross split or family.

## 10. Server preflight gate

Local preflight output: `manifest_valid: true`, `ready: false`, with
`scientific_blockers: []`. The only remaining reason codes are

- `server_hardware_unverified`
- `cuda_runtime_unverified`
- `python_packages_unverified`

These are resolved only by running
`preflight_component_training.py --inspect-server` on the target machine. No
download or training may start until the user authorizes that server and job ID.

## 11. Not frozen / explicitly not claimed

- No training has run; there is no performance result, no checkpoint, and no
  claim of scientific validity.
- Publisher authentication is not established.
- Weak labels and hard negatives are not independently validated.
- The 96–120-family scale-up target is superseded by the 2,048-record
  metadata-only plan; the outstanding family work is the **held-out audit**,
  not more plan records.

## 12. Server adaptation record (2026-08-16, AutoDL 4090 D)

The rented server's measured reality, recorded before any training:

- Container: AutoDL (Ubuntu 22.04), `root@connect.westb.seetacloud.com:12977`.
- GPU: RTX 4090 D, `nvidia-smi` reports 24564 MiB (≈ 23.99 GiB) with driver
  595.71.05. Because the preflight check compares GiB, the component jobs are
  **rebuilt with `gpu_memory_gib_each: 23`** (a 24 GiB nominal card always
  reports slightly below 24 GiB); precision stays `bf16` (Ada-native).
- Host RAM 503 GiB; data disk 650 GiB at `/root/autodl-tmp` (repo and all
  caches live there; the 30 GiB overlay is not used for data).
- `huggingface.co` is unreachable from the server; model downloads use
  `HF_ENDPOINT=https://hf-mirror.com`. The model card and LICENSE are rechecked
  from the mirror at execution time.
- pip uses the AutoDL aliyun mirror. `pip freeze` after install is saved as
  `server-lock.txt` (the runbook's server/CUDA-specific transitive lock).

