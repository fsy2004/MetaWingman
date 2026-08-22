# MetaWingman Server Mainline Runbook

Status: single-RTX-5090 execution target identified; server preflight and first
pilot remain receipt-gated

Last checked: 2026-08-20

## Rent This Configuration

Current authorized pilot target (inventory observed 2026-08-20): one NVIDIA
GeForce RTX 5090 with 32,607 MiB reported VRAM. Treat it as one 32-GB worker;
never aggregate memory with another card. Run GPU workloads sequentially and
reduce batch size or use gradient accumulation only through a versioned job.
The L40S profiles below remain planning references, not descriptions of the
current target.

Preferred single-node research server:

```text
GPU:      2 x NVIDIA L40S, 48 GB per GPU
CPU:      48 vCPU (32 vCPU acceptable)
RAM:      256 GB (128 GB minimum)
Disk:     4 TB local NVMe
Network:  stable 1 Gbps public egress
OS:       Ubuntu 22.04 LTS or Ubuntu 24.04 LTS
Access:   SSH key; one non-root project account; sudo only for runtime setup
```

NVIDIA specifies 48 GB GDDR6 ECC, 350 W maximum power, and no NVLink or MIG for
the L40S ([official specification](https://www.nvidia.com/en-us/data-center/l40s/)).
The two GPUs are independent workers and do not form one 96 GB address space.

Lower-cost acceptable node:

```text
GPU:      1 x NVIDIA L40S, 48 GB
CPU:      24-32 vCPU
RAM:      96-128 GB
Disk:     2 TB local NVMe
Network:  stable 300 Mbps or faster public egress
OS:       Ubuntu 22.04 LTS or Ubuntu 24.04 LTS
```

Use the lower-cost node when parser, training, and local inference jobs can run
sequentially. The existing two BiomedBERT jobs alone still fit the smaller
24-GiB component-training profile documented in
`server-training-runbook.md`; that profile is not the complete mainline.

## Workload Allocation

On the preferred node:

| Worker | Default queue | May run concurrently with |
|---|---|---|
| CPU | API/database ingestion, deduplication, evidence graph, BM25, schema checks, R orchestration | both GPU workers |
| GPU 0 | OCR/layout/document VLM, local text/VLM inference | CPU and GPU 1 |
| GPU 1 | bounded component training, parser ablations, repeated benchmark replicas | CPU and GPU 0 |

Do not launch one distributed job merely because two GPUs exist. Use data
parallelism only when a frozen job declares it. API-hosted model calls consume
no local GPU.

## Filesystem Contract

Create these distinct resolved roots:

```text
/srv/metawingman/src             verified Git checkout
/srv/metawingman/config          non-secret frozen configs
/srv/metawingman/corpus          lawful XML/PDF and rendered pages
/srv/metawingman/cache           models, tokenizers, OCR and embeddings
/srv/metawingman/runs            immutable run directories
/srv/metawingman/checkpoints     approved local checkpoints
/srv/metawingman/receipts        preflight, package, provider and hash receipts
/srv/metawingman/backup-staging  manifests/metrics awaiting off-node backup
```

For a 4-TB disk, reserve 200 GB for the operating system and environments, 1.5
TB for corpus objects, 1 TB for caches, 1 TB for runs/checkpoints, and 300 GB as
free-space reserve. Put irreplaceable manifests, hashes, metrics, and explicitly
approved checkpoints in an independent backup target. Raw copyrighted full text
does not enter Git or a public artifact bundle.

Example non-secret runtime config:

```json
{
  "schema_version": "1.0",
  "source_root": "/srv/metawingman/src",
  "corpus_root": "/srv/metawingman/corpus",
  "cache_root": "/srv/metawingman/cache",
  "run_root": "/srv/metawingman/runs",
  "checkpoint_root": "/srv/metawingman/checkpoints",
  "receipt_root": "/srv/metawingman/receipts",
  "gpu_workers": {
    "0": ["document_parsing", "local_inference"],
    "1": ["component_training", "benchmark_replica"]
  },
  "provider_config_paths": [
    "/srv/metawingman/config/deepseek-provider.json"
  ],
  "allow_remote_plain_http": false,
  "allow_raw_fulltext_in_git": false
}
```

## Runtime Layers

1. Install Git, a clean Python 3.12 environment manager, R, build tools,
   Poppler/qpdf where required, and the NVIDIA driver.
2. Select the CUDA-compatible PyTorch wheel only after recording `nvidia-smi`
   and driver output. The repository lock does not prove compatibility with an
   uninspected server.
3. Keep `mw-core`, `mw-pdf`, and `mw-training` environments or equivalent
   containers separate from unrelated analyses.
4. Install the repository locks in the order documented by
   `server-training-runbook.md`: core, training, then PDF, followed by an
   independently resolved server/CUDA transitive hash lock.
5. Keep provider configuration files free of secrets. Export secret values into
   the process environment or an approved secret manager.

Do not expose Jupyter, a local model server, a database, or a dashboard to the
public network by default. Bind internal services to loopback or a private
network and tunnel through SSH when interactive access is needed.

## API and Database Capabilities

The default programmatic text provider is `deepseek-v4-flash`. The retained 2026-08-20 receipt at
`validation-output/live-provider/deepseek-probe-2026-08-20.json` verifies one
successful `deepseek-v4-flash` contract call; it does not freeze future model
availability or scientific performance. Codex remains the main interactive
development, source-audit, and code-review environment. Repeatable text batches
use only DeepSeek. Scientific-document page vision uses `glm-4.6v` as a distinct
visual parser, not as a second text judge or independent scientific witness.
Proposer, opposition, and judge roles may use
separate calls to this model, but source checks, schema checks, and executable
statistics are the verifiers because same-provider calls are not independent
scientific evidence. Text API execution is frozen to `deepseek-v4-flash`; no
Pro-model sensitivity analysis is run or required for release.

Keep hosted visual parsing on the local coordinator unless a separately approved
server secret route exists. Hash the rendered page and prompt, require exact
native-text anchor recovery plus bounded normalized regions, and store only the
verified structured receipt. Never retain the raw provider response or upload a
desktop credential file.

When DeepSeek batch execution is deliberately kept on that coordinator, the
server preflight may consume a non-secret capability receipt located under its
configured receipt root. Set `provider_capability_receipt` and
`expected_provider_capability_receipt_sha256`; the receipt must bind the exact
model, UTC observation time, content hash, token accounting, and
`execution_location: coordinator`. This proves a recent contract call only. It
does not imply server-side secret availability or model quality.

Set only the capabilities actually available:

```text
DEEPSEEK_API_KEY       text reasoning provider
GLM_API_KEY            local-coordinator visual parsing only
NCBI_EMAIL             PubMed/PMC identification
NCBI_API_KEY           optional NCBI rate capability
CROSSREF_EMAIL         DOI metadata identification
UNPAYWALL_EMAIL        required by the project's Unpaywall adapter contract
OPENALEX_API_KEY       only when required by the active OpenAlex service
```

Europe PMC and ClinicalTrials.gov do not require a secret in the current
project contract. Licensed Embase, CENTRAL interfaces, Scopus, Web of Science,
CINAHL, and publisher access remain account/license dependent and must use an
approved API, export, or authorized browser handoff. The current authority is
`metawingman/references/search-retrieval-and-apis.md`; an account or login never
counts as evidence that a source was searched.

Codex in the desktop application performs most current research and development,
but it is not a server API credential. Do not block the server plan on a
programmatic Codex route. If one is authorized later, it must satisfy the same
provider-neutral schema, secret, and audit contract.

## Transfer Allowlist

Transfer to the server:

- a verified Git checkout at an explicit commit;
- `validation-output/server-training-handoff-v3/` after checking every manifest
  hash;
- approved non-secret provider configs;
- metadata manifests, family registries, licenses, retraction receipts, and
  benchmark plans;
- user-authorized corpus files through a private transfer route.

Do not transfer the 2026-08-20 cleanup archive, superseded handoffs, duplicate R
outputs, `.env`, desktop credential files, unrelated analysis environments, or
raw provider response logs.

## First Session Order

Run only inspection before download or training:

```bash
cd /srv/metawingman/src
git status --short --branch
git rev-parse HEAD
nvidia-smi
python --version
R --version
df -h /srv/metawingman
```

Then verify the current repository and handoff:

```bash
python -m unittest discover -s tests -v
python metawingman/scripts/test_r_adapters.py metawingman
python scripts/verify_dependency_locks.py
python metawingman/scripts/preflight_component_training.py \
  validation-output/server-training-handoff-v3/validation-output/training-corpus/jobs/section-role.json \
  --root validation-output/server-training-handoff-v3 \
  --inspect-server
python metawingman/scripts/preflight_component_training.py \
  validation-output/server-training-handoff-v3/validation-output/training-corpus/jobs/evidence-retrieval.json \
  --root validation-output/server-training-handoff-v3 \
  --inspect-server
```

`scripts/server/preflight_mainline.py` enforces distinct roots, per-GPU memory,
active-process, source-tree, handoff, provider-capability, and storage checks.
Until its receipt and both component preflights pass, retain
`local_ready_pending_server_preflight`; do not hand-edit a manifest to
`server_ready`.

## Execution Sequence

1. Implement and test P0 contracts and the sealed question-synthesis benchmark.
2. Implement P1 joint tree search, method routing, typed agent roles, and
   external verifiers.
3. Run the five matched-cost development configurations; freeze calibration and
   held-out commands before viewing held-out results.
4. Connect the selected design to the P2 persistent review case and replay one
   complete review, including one justified no-pooling case.
5. Export family/time-safe P3 ranker, support-verifier, and risk-cost-router
   examples; run `--validate-only` before each training job.
6. Train bounded components, run repeated seeds and required ablations, and
   retain all failure trajectories.
7. Copy only metrics, receipts, code-safe metadata, and separately approved
   checkpoints back from the server.

The exact file-by-file implementation order and tests are frozen in
`docs/superpowers/plans/2026-08-20-question-synthesis-server-mainline.md`.
