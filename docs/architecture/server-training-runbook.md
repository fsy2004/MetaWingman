# MetaWingman Biomedical Component Training Runbook

Status: local handoff implemented; server execution requires explicit authorization.
Last checked: 2026-08-15

## Scope

This runbook covers lawful full-text retrieval, weak-label freezing, contrastive pair export, and bounded training for section-role classification and evidence retrieval. It does not train a foundation model, run the four existing servers, or authorize model/checkpoint publication.

The current local handoff is `validation-output/server-training-handoff-v2/`. Its manifest must say `local_ready_pending_server_preflight`; `server_ready` is not a valid local state. The earlier local directory is retained only as an ignored development artifact and must not be uploaded.

## Recommended Server

- Minimum practical pilot: one 24 GiB NVIDIA GPU, 16 vCPU, 64 GiB RAM, and 500 GiB NVMe.
- Comfortable scale-up: one 48 GiB GPU, 24-32 vCPU, 128 GiB RAM, and 1 TiB NVMe.
- Network: stable public HTTPS, preferably at least 100 Mbps, with institutional sources handled outside automation.

One 24-48 GiB GPU is preferable to several small GPUs for the current encoders. Multiple low-memory GPUs do not pool VRAM automatically and add synchronization overhead. Several inexpensive GPUs are useful only for independent jobs such as OCR, parser ablations, classification, retrieval, and benchmark replicas.

## Authorization Boundary

1. Prepare a clean, verified MetaWingman source checkout that contains the command scripts named in the manifest. Overlay only the metadata handoff at the repository root after comparing every member SHA-256 with `server-training-handoff.json`; the handoff alone is not a source-code distribution.
2. Run `preflight_component_training.py --inspect-server`; this may inspect disk, installed package versions, and `nvidia-smi`, but it does not import Torch or download a model.
3. Review unresolved CUDA, package, storage, model-license, dataset-license, and family-isolation findings.
4. Start download or training only after explicit user authorization for that server and job ID.

## Environment

Create a clean Python 3.12 environment. The direct pins in `python-training.lock.txt` were resolved from the official Python package index on 2026-08-15. Before execution, resolve a server/CUDA-specific transitive hash lock and verify that the selected Torch wheel matches the installed driver. Do not install packages into an unrelated running analysis environment.

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

## Monitoring

Record GPU memory, utilization, temperature, host RAM, free NVMe, network transfer, examples/second, wall time, and failed records. Stop on hash drift, license/retraction changes, non-finite loss, output-path escape, repeated OOM, or development-family contamination.

The initial benchmark compares the general model baseline, biomedical schema, biomedical routing, and full biomedical stack. It reports critical false exclusion, evidence anchors, lineage, recomputation, selective coverage, abstention, time, tokens, and cost. It does not make a human-superiority claim.
