# Asymmetric MedCPT retrieval results (V4)

Date: 2026-08-21
Status: frozen development-component evaluation

## Question

The earlier evidence-retrieval component separated positives from neighborhood
negatives but failed when each development query was ranked against the full
document pool. V4 tested whether an asymmetric query encoder and article encoder,
trained with in-batch and explicit hard negatives, could repair that full-corpus
failure on the same family-isolated development split.

This is a component evaluation. It does not measure database-search recall,
missed-study risk, complete-review accuracy, or the effect of MetaWingman's two
headline control policies.

## Frozen data and models

- 109,028 frozen examples across two tasks: 54,514 evidence-retrieval queries and
  54,514 section-role examples;
- retrieval training: 43,632 queries from 8,798 review families, forming 174,528
  query--document pairs;
- retrieval development: 10,882 queries from 2,211 disjoint review families,
  forming 43,528 query--document pairs;
- every retrieval query has one self-anchored positive and three explicit hard
  negatives;
- development queries ranked against the complete development document pool after
  same-family masking;
- query encoder: `ncbi/MedCPT-Query-Encoder`, revision
  `d83a36cc6b8e3a5c5e9d9d6ba156808c1643dcbc`;
- article encoder: `ncbi/MedCPT-Article-Encoder`, revision
  `d05a736da4bb84ee4057b7f7999485be6ed85465`;
- frozen example-set SHA-256:
  `647e11b9aadbc3c9e4e721b53b36305685a9bd9963444f57c39058325f6fbb51`.

Raw source text and model checkpoints are not distributed with this report.
The public
[aggregate-only corpus receipt](../../research/retrieval-v4-corpus-aggregate-receipt.json)
binds these counts and the zero family overlap to the frozen examples, pairs, and
export-manifest hashes without exposing training text or record identifiers.

## Training and evaluation

Each prespecified seed ran three epochs with batch size 64, learning rate
`2e-5`, weight decay 0.01, 10% warm-up, bfloat16 mixed precision, gradient
checkpointing, inner-product similarity, and separate trainable query and article
encoders. Seeds were 20260820, 20260821, and 20260822. Jobs ran serially on one
RTX 5090 reporting 32,607 MiB memory with PyTorch `2.13.0+cu130`.

The frozen run plan named the review family as the evaluation unit. An adversarial
audit found that the first receipt reported only query-micro metrics. The audited
evaluator therefore reports equal-family Recall@10 with a deterministic
10,000-replicate family bootstrap (seed 20260821) as the unit-aligned result;
query-micro Recall@10, MRR, and precision@1 are retained as secondary metrics. A
separately frozen zero-shot evaluation used the identical queries, pool, masking,
model revisions, pooling, and similarity.

## Results

| Configuration | Family-macro Recall@10 | Family-bootstrap 95% interval |
|---|---:|---:|
| Zero-shot MedCPT | 0.411867 | 0.399628--0.424189 |
| Seed 20260820 | 0.683177 | 0.672428--0.693573 |
| Seed 20260821 | 0.689809 | 0.679116--0.700227 |
| Seed 20260822 | 0.677878 | 0.667249--0.688578 |
| Fine-tuned mean | **0.683621** | descriptive across-seed mean |

The equal-family mean gain was 0.271754. The intervals are deterministic
10,000-replicate family bootstraps added during the post-lock adversarial audit;
they were not present in the first query-micro receipt.

Secondary query-micro results are:

| Configuration | Recall@10 | MRR | Precision@1 |
|---|---:|---:|---:|
| Zero-shot MedCPT | 0.376401 | 0.261997 | 0.201158 |
| Seed 20260820 | 0.654659 | 0.542485 | 0.477853 |
| Seed 20260821 | 0.659438 | 0.551144 | 0.487962 |
| Seed 20260822 | 0.650708 | 0.536263 | 0.471329 |
| Fine-tuned mean | **0.654935** | **0.543297** | **0.479048** |

Query-micro Recall@10 increased by 0.278533 on average, a 73.999% relative
increase over zero shot. The across-seed sample standard deviation was 0.004372.

The retained query-level ranks show the distribution behind the aggregate result.
Median positive-document rank moved from 62 (interquartile range 2--1,390.25) at
zero shot to 2 (1--35 or 1--36) after fine-tuning. Depending on seed,
75.54--76.21% of queries improved, 18.17--18.94% were unchanged, and
4.85--6.29% worsened.

| Seed | Wall time (s) | Train queries/s | Peak allocated GPU bytes | Train mean loss |
|---|---:|---:|---:|---:|
| 20260820 | 2,123.838 | 65.894 | 20,612,291,584 | 0.633514 |
| 20260821 | 2,122.854 | 65.861 | 20,612,291,584 | 0.629906 |
| 20260822 | 2,127.967 | 65.777 | 20,612,291,584 | 0.634182 |

## Interpretation

The objective change repaired the prespecified full-corpus development endpoint
and was stable across the three registered seeds. The retained deterioration in
approximately 5--6% of queries is material: V4 is an improved component operating
point, not a universal retrieval guarantee. Database-level known-item tests,
source-specific syntax, citation chasing, lawful full-text acquisition, and
missed-study audits remain separate parts of a production review.

The result supports the evidence-access mechanism used by conclusion-directed
acquisition. It does not estimate the causal effect of conclusion-directed
control itself; that requires dependency-complete review cases and a frozen
comparison with fixed-depth, linear, statistical-stopping, and confidence-only
policies.

## Integrity anchors

| Artifact | SHA-256 |
|---|---|
| Aggregate-only corpus receipt | `350304fe6b0c6ff7b032d27934713737a06cf2cd3e52b8d2098a44331a5207c4` |
| Zero-shot metrics | `2cf4e245acb9ce8f4eef23f79671e4f3774010168e86dd6151b1d563a5d958b2` |
| Zero-shot ranks | `2caa4ff1572da859b5073252e6e1031959c9bd61681ea8a139f376f7eecd2832` |
| Seed 20260820 metrics | `23315d49df5479b60a363bda9651b2f1e81ff2d928cc39316bf4c0edc6c0a456` |
| Seed 20260820 ranks | `5a6c5635135c71289349671b18a5cdb39e6331a5b8fe8cfb2790354282e821b9` |
| Seed 20260821 metrics | `f7eaa7a287df4dd1002ae7296f9f8be0d2796eb72edb49b7a095f5458cf80687` |
| Seed 20260821 ranks | `55b861a444b3fc0f29a1cc09ecaa795c1eabf83682bcbd6dba17f83918fc327a` |
| Seed 20260822 metrics | `22ffcb4441e36bd8d92ee9187ba165502aeadb24abae8eb6d703d07076193912` |
| Seed 20260822 ranks | `2c506fbe5ab751572800838c9e4873f24a049cb7c70dc25038ad417694240804` |

The audited evaluator source SHA-256 is
`512170922eea407e236bb80d44f5023ef6740d5ae5eb88062ac1399f44b9fbfd`.
Each fine-tuned metrics receipt records the exact loaded query/document
`model.safetensors` SHA-256 and its source training-receipt SHA-256. The three
training-receipt hashes are, in seed order, `8ef1570d93ae6e5127643f71ef265650f8ff2ba0f03ca28563494a8c59574c62`,
`a0192c7c5ed49a94d57be0021618383da6b7036a4662bb47e6c0ede7ccf93657`,
and `3c77333c981873a8eaa051861987bdcb56de5fe53bafd128250021455769265d`.
