# Methods Bibliography — Remaining Steps Grounded in AI Top Venues and GitHub

> Maps every remaining MetaWingman step to peer-reviewed methods and
> maintained GitHub implementations. Entries marked (verified link) were
> re-checked online; entries marked (repo doc) are already anchored in the
> project's own architecture docs. New steps must extend this file before
> implementation.

## 1. Independent human validation arm (轨道 A)

| Reference | What it contributes |
|---|---|
| Zheng et al., *Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena*, NeurIPS 2023, [arXiv:2306.05685](https://arxiv.org/abs/2306.05685); code [lm-sys/FastChat](https://github.com/lm-sys/FastChat) | Why model-judged labels must not masquerade as independent human judgment; position bias and self-enhancement bias inform the blind single-annotator design of our 200-record/47-stratum arm. |
| Cohen's kappa for inter-annotator agreement (standard; our protocol Part A sets κ ≥ 0.8 before gold promotion) | The promotion threshold in `label-and-heldout-validation-protocol.md`. |
| Annotation tooling: [HumanSignal/label-studio](https://github.com/HumanSignal/label-studio), [argilla-io/argilla](https://github.com/argilla-io/argilla) | Ready-made review UIs for the blind tasks we exported (`blind-tasks.jsonl`); use if the user prefers a GUI over spreadsheets. |

## 2. Family held-out audit and leakage control (轨道 A/C)

| Reference | What it contributes |
|---|---|
| Deng et al., *Benchmark Probing: Investigating Data Leakage in Large Language Models*, NeurIPS 2023 W, [OpenReview/NeurIPS workshop](https://openreview.net/forum?id=Qk2A3Byj2n); paper list [lyy1994/awesome-data-contamination](https://github.com/lyy1994/awesome-data-contamination) | Why review-family and temporal splits are the right unit for systematic-review leakage (updated reviews contaminate the original); justifies the hard-zero held-out gate. |
| Li et al., *An Open Source Data Contamination Report for LLMs*, [arXiv:2310.17589](https://arxiv.org/abs/2310.17589) | Sealed-reference discipline mirrored in our benchmark's `answers_sealed_until_all_runs_locked`. |

## 3. AI-only benchmark and pilot (轨道 C)

| Reference | What it contributes |
|---|---|
| Liang et al., *Holistic Evaluation of Language Models (HELM)*, TMLR 2023, [arXiv:2211.09110](https://arxiv.org/abs/2211.09110); code [stanford-crfm/helm](https://github.com/stanford-crfm/helm) | Multi-metric, scenario-level evaluation and reporting discipline for the four-configuration pilot aggregation. |
| MAST (multi-agent system failures, NeurIPS 2025) and AgentIF (long-horizon instruction adherence, NeurIPS 2025) (repo doc: `top-journal-contribution-story.md`) | Failure taxonomy the pilot must score (schema drift, unanchored output, abstention quality). |
| AI Scientist (Nature 2026), Virtual Lab (Nature 2025), OpenScholar (Nature 2025, [akariasai/OpenScholar](https://github.com/akariasai/OpenScholar)) (repo doc) | The contribution story's external anchors; OpenScholar's retriever-trained evaluation is the closest analogue to our trained-component benchmark. |

## 4. Topic opportunity engine (轨道 C, TOPIC-1..4)

| Reference | What it contributes |
|---|---|
| Xu et al., *Inductive Representation Learning on Temporal Graphs (TGAT)*, ICLR 2020, [arXiv:2002.07962](https://arxiv.org/abs/2002.07962); Rossi et al., *Temporal Graph Networks*, ICML-W 2020, [arXiv:2006.10637](https://arxiv.org/abs/2006.10637); framework [pyg-team/pytorch_geometric](https://github.com/pyg-team/pytorch_geometric) | The dated multidisciplinary evidence graph (TOPIC-1) should be a temporal graph with these message-passing primitives; PyG is the maintained implementation. |
| Swanson, *Fish oil, Raynaud's syndrome, and undiscovered public knowledge*, Perspectives in Biology and Medicine, 1986 | The original literature-based-discovery formalism for gap detection; the engine's value/risk gate must go beyond Swanson-style co-occurrence. |

## 5. Conclusion-directed evidence control (轨道 C, VAL-5)

| Reference | What it contributes |
|---|---|
| Snell et al., *Scaling LLM Test-Time Compute Optimally can be More Effective than Scaling Model Parameters*, [arXiv:2408.03314](https://arxiv.org/abs/2408.03314); replication [moolean/test-time-scaling-dev](https://github.com/moolean/test-time-scaling-dev) | Best-of-N / verifier-guided allocation is the direct analogue of allocating retrieval, full-text, and verification by residual conclusion risk; our C3 ablations (fixed Top-K, confidence-only routing) mirror its compute-scaling comparisons. |
| Farquhar et al., *Detecting hallucinations in LLMs using semantic entropy*, Nature 2024 (repo doc: `top-journal-contribution-story.md`) | Uncertainty-gated acquisition: when semantic entropy is high, spend more evidence budget — one concrete signal for C3's router. |

## 6. Already-implemented steps (for completeness)

- Dense retrieval training: Karpukhin et al., DPR, EMNLP 2020, [arXiv:2004.04906](https://arxiv.org/abs/2004.04906); [facebookresearch/DPR](https://github.com/facebookresearch/DPR).
- Bi-encoder + hard negatives: Reimers & Gurevych, Sentence-BERT, EMNLP 2019, [arXiv:1908.10084](https://arxiv.org/abs/1908.10084); [UKPLab/sentence-transformers](https://github.com/UKPLab/sentence-transformers).
- Hard-negative trade-off: Zhang & Stratos, NAACL 2021, [arXiv:2104.06245](https://arxiv.org/abs/2104.06245).
- Base model: Gu et al., ACM TOCH 2021, [doi:10.1145/3458754](https://doi.org/10.1145/3458754).
