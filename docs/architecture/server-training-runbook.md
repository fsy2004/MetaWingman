# MetaWingman Biomedical Component Training Runbook

Status: local handoff implemented; one RTX 5090 target identified, but the
current source/handoff/runtime combination is not server-ready until the new
preflight receipt passes.
Last checked: 2026-08-20

## Scope

This runbook covers lawful full-text retrieval, weak-label freezing, contrastive pair export, and bounded training for section-role classification and evidence retrieval. It does not train a foundation model, run the four existing servers, or authorize model/checkpoint publication.

The current local handoff is `validation-output/server-training-handoff-v3/`. Its manifest must say `local_ready_pending_server_preflight`; `server_ready` is not a valid local state. Superseded handoff directories were moved to the recoverable 2026-08-20 cleanup archive and must not be uploaded.

## Recommended Server

For the two existing BiomedBERT component jobs alone, the original practical
pilot remains one 24 GiB NVIDIA GPU, 16 vCPU, 64 GiB RAM, and 500 GiB NVMe. That
is a component-training minimum, not the configuration for the complete
question-synthesis and full-review research mainline.

For the complete mainline, use the preferred 2 x L40S, 32-48 vCPU, 128-256 GiB
RAM, and 4 TiB NVMe profile in
`compute-and-deployment-budget.md`; one L40S is the lower-cost sequential-job
option. NVIDIA specifies 48 GB per L40S and no NVLink, so two cards run
independent workers rather than one pooled 96 GB model
([official specification](https://www.nvidia.com/en-us/data-center/l40s/)).

One 24-48 GiB GPU remains preferable to several smaller cards for each current
encoder. Multiple GPUs are useful for independent OCR, parser, local inference,
training, and benchmark jobs; no plan may assume that their VRAM pools
automatically.

For the current single RTX 5090 target, schedule one encoder or VLM job at a
time. Its observed 32,607 MiB is checked as one device; it is not rounded up to
48 GiB and is not combined with any other GPU.

The current hosted visual-parser route is `glm-4.6v`. It receives one rendered
page at a time from the local coordinator and must return a schema-gated visual
candidate. Exact native-text anchors and normalized bounding boxes are executable
verifiers; the model response alone is not scientific acceptance. This hosted
route uses no server GPU memory and its credential must not be copied to the
training server.

## Authorization Boundary

1. Prepare a clean, verified MetaWingman source checkout that contains the command scripts named in the manifest. Overlay only the metadata handoff at the repository root after comparing every member SHA-256 with `server-training-handoff.json` and running an independent secret scan; the bundled bounded-pattern scan is not proof of absence. The handoff alone is not a source-code distribution.
2. Run `preflight_component_training.py --inspect-server`; this may inspect disk, installed package versions, and `nvidia-smi`, but it does not import Torch or download a model.
3. Review unresolved CUDA, package, storage, model-license, dataset-license, and family-isolation findings.
4. Start download or training only after explicit user authorization for that server and job ID.

## Environment

Create a clean Python 3.12 environment. The handoff carries three runtime
locks that must all be installed: `python-core.lock.txt` (jsonschema-based
schema guard), `python-pdf.lock.txt` (PyMuPDF PDF metrics), and
`python-training.lock.txt` (accelerate/datasets/numpy/safetensors/
scikit-learn/torch/transformers). Install core first, then training (so the
training pins win any overlap), then pdf. The training pins were resolved from
the official Python package index on 2026-08-15. Before execution, resolve a
server/CUDA-specific transitive hash lock and verify that the selected Torch
wheel matches the installed driver. Do not install packages into an unrelated
running analysis environment.

The first candidate is `microsoft/BiomedNLP-BiomedBERT-base-uncased-abstract-fulltext`, immutable revision `e1354b7a3a09615f6aba48dfad4b7a613eef7062`, declared MIT license. The model card and Hub metadata must be rechecked at execution time. Raw source redistribution and public checkpoint release remain blocked pending a separate dataset-license review.

## Execution Order

Use the argv arrays in the handoff manifest from the verified repository root. Every array begins with `python` and uses the exact materialized member paths:

1. Re-run metadata, license, retraction, path, and storage preflight.
2. Download only article-level permitted OA content with resumable manifests.
3. Run `freeze_base` to create source-anchored weak-label examples.
4. Run `export` to create positive and candidate hard-negative pairs; audit that no negative crosses split or family.
5. Run the final `freeze` command with the exported pairs and biomedical plan to create the component-ready run plan.
6. Rebuild component jobs against the server-local file hashes.
7. Run `run_component_training.py <job> --root <handoff-root> --validate-only`.
8. Run normal training only when inspected preflight returns `ready: true`.
9. Run component and end-to-end benchmarks at matched cost before selecting a checkpoint.

## Resume And Recovery

- Never resume a checkpoint unless its hash is listed in the job ledger.
- Keep downloads, frozen data, checkpoints, metrics, and logs in separate content-addressed directories.
- On failure, retain the job manifest, package/accelerator receipt, last verified checkpoint hash, stdout/stderr, and elapsed/cost records.
- Re-run hashes after interruption. Rebuild the job rather than editing a frozen manifest in place.
- Retrieve only metrics, receipts, code-safe metadata, and explicitly approved checkpoints. Do not copy raw full text into Git.

### Interrupted-download recovery (sharded fetches)

When sharded fetchers are interrupted before writing their final manifests,
recover progress from disk instead of re-downloading: scan each shard's
existing XML files against its shard plan, build a valid
`training_document_manifest` per shard (provenance: file sha256/bytes,
plan-derived license/split/family, `verified_not_retracted`), then restart the
fetchers — the reuse path hash-verifies recovered artifacts and downloads only
the missing records. On this run the recovery manifests restored 533–548 of
1,500 records per shard and eliminated the overwrite loop. Operational tool:
`~/.agents/tools/mw-server/mw-recover.py`.

## Monitoring

Record GPU memory, utilization, temperature, host RAM, free NVMe, network transfer, examples/second, wall time, and failed records. Stop on hash drift, license/retraction changes, non-finite loss, output-path escape, repeated OOM, or development-family contamination.

The initial benchmark compares the general model baseline, biomedical schema, biomedical routing, and full biomedical stack. It reports critical false exclusion, evidence anchors, lineage, recomputation, selective coverage, abstention, time, tokens, and cost. It does not make a human-superiority claim.
