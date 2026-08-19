# GitHub Repository Survey for MetaWingman

**Date:** 2026-08-19 · **Method:** GitHub REST API (`/search/repositories`, sorted by stars; direct `/repos/{owner}/{name}` lookups) and HuggingFace API for model artifacts. Star counts are approximate as of retrieval time. All URLs verified live during this session; items that could not be verified (404) are explicitly flagged.

---

## 1. LLM-based Systematic Review / Meta-analysis Tools

| Repository | Stars | Relevance to MetaWingman | Use |
|---|---|---|---|
| [ChaokunHong/MetaScreener](https://github.com/ChaokunHong/MetaScreener) | ~1,330 | AI-powered abstract + PDF screening for SRs; the most-starred LLM screening tool. Direct competitor to our section-role classifier + LLM screening pipeline. | **Comparison baseline** (screening stage) |
| [asreview/asreview](https://github.com/asreview/asreview) | ~975 | Active-learning screening (non-LLM, classical ML). Industry standard for ML screening; integrates with PRISMA reporting. | **Comparison baseline** for ML vs LLM screening; **reference** for screening UX |
| [ijmarshall/robotreviewer](https://github.com/ijmarshall/robotreviewer) | ~177 | Automatic synthesis of RCTs (RCT identification, PICO, risk-of-bias extraction). Overlaps with our appraisal classifier + extraction modules. | **Reference** / **baseline** for appraisal and PICO extraction |
| [GaoxiangLuo/OpenMetaMate](https://github.com/GaoxiangLuo/OpenMetaMate) | ~5 | LLM-powered PDF data extraction for SR/MA. Closest match to our extraction modules in the 26-module R toolkit. | **Reference** for extraction design; small but directly on-topic |
| [iwas108/SLR-Magic](https://github.com/iwas108/SLR-Magic) | ~1 | Local-first, LLM-powered SLR platform with human-in-the-loop screening/extraction. | **Reference** for human-in-the-loop architecture |
| [zanwenfu/agentic-reviewers-for-SRMA](https://github.com/zanwenfu/agentic-reviewers-for-SRMA) | ~2 | LUMINA agent: LLM-based citation screener for medical SRs. | **Comparison baseline** for screening agent |
| [Pkr2180/PRISM-LLM-Multi-Agent-LLM-for-Periodontal-Evidence-Synthesis](https://github.com/Pkr2180/PRISM-LLM-Multi-Agent-LLM-for-Periodontal-Evidence-Synthesis) | ~0 | Hierarchical multi-agent LLM for automated screening + structured synthesis. | **Reference** for multi-agent orchestration |
| [Vambrocop/EvidenceForge](https://github.com/Vambrocop/EvidenceForge) | ~5 | Agent skills for SR/MA/umbrella review and AI-assisted evidence synthesis — same packaging concept as MetaWingman's skill-based design. | **Direct comparison** for skill design |
| [ftoucch/weblit](https://github.com/ftoucch/weblit) | ~42 | GPT-4 driven systematic literature review assistant. | **Reference** |
| [eliaswestonfarber/scienceai](https://github.com/eliaswestonfarber/scienceai) | ~9 | Agentic harness for literature analysis (extraction, replication, critique). | **Reference** |
| [xwang297/metamate-dataset](https://github.com/xwang297/metamate-dataset) | ~4 | Dataset + prompts for LLM data extraction in SR/MA — usable as an **evaluation set** for our extraction modules. | **Reference** (eval data) |
| [Wang-Yuan-Chen/An-Analysis-of-LLMs-Capability-in-Risk-of-Bias-Assessment](https://github.com/Wang-Yuan-Chen/An-Analysis-of-LLMs-Capability-in-Risk-of-Bias-Assessment) | ~1 | Experimental data on optimizing LLM RoB assessment — directly relevant to validating our appraisal classifier. | **Reference** (validation evidence) |
| [RaihanArvi/LLM_RoB_Assessment](https://github.com/RaihanArvi/LLM_RoB_Assessment) | ~1 | Automated RoB assessment with LLMs. | **Reference** |
| [htlin222/prisma-automation](https://github.com/htlin222/prisma-automation) | ~7 | Multi-database search + dedup + PRISMA-compliant workflow automation. | **Reference** for search/dedup stages |

## 2. BiomedBERT / PubMedBERT Fine-tuning for Evidence Retrieval

| Repository | Stars | Relevance | Use |
|---|---|---|---|
| [dmis-lab/biobert](https://github.com/dmis-lab/biobert) | ~2,200 | Canonical BioBERT repo (Bioinformatics 2020) with fine-tuning code for NER/RE/QA — the standard recipe for biomedical BERT fine-tuning. | **Reference** for fine-tuning methodology |
| [naver/biobert-pretrained](https://github.com/naver/biobert-pretrained) | ~706 | BioBERT pretrained weights + usage examples. | **Reference** |
| [dmis-lab/bioasq-biobert](https://github.com/dmis-lab/bioasq-biobert) | ~126 | BioBERT fine-tuned for biomedical QA (BioASQ) — closest published analogue to a retrieval-reader pipeline for evidence. | **Reference** / **baseline** for retriever-reader |
| [microsoft/BiomedNLP-BiomedBERT-base-uncased-abstract-fulltext](https://huggingface.co/microsoft/BiomedNLP-BiomedBERT-base-uncased-abstract-fulltext) | 445k downloads / 333 likes (HF) | **The actual PubMedBERT model** (renamed BiomedBERT on HF). Our three trained BiomedBERT models presumably start from this checkpoint. | **Direct dependency** (weights) |
| ⚠️ microsoft/BLURB (GitHub) | — | The BLURB benchmark repo (home of PubMedBERT evaluation) returned **404 — no longer available**. Do not cite it as an existing repo; PubMedBERT lives on HuggingFace instead. | n/a (flag) |

## 3. Dense Passage Retrieval (DPR) for Biomedical NLP

| Repository | Stars | Relevance | Use |
|---|---|---|---|
| [facebookresearch/DPR](https://github.com/facebookresearch/DPR) | ~1,870 | Canonical DPR implementation (Karpukhin et al. 2020): Bi-encoder + in-batch negatives + FAISS index. The blueprint for our evidence retriever. | **Reference** (architecture) |
| [ncbi/MedCPT](https://github.com/ncbi/MedCPT) | ~276 | NCBI's zero-shot **biomedical** dense retriever (contrastive PubMed encoder, query + article encoders). Strong ready-made candidate to compare against our fine-tuned retriever. | **Comparison baseline** / could be used **directly** as an embedding model |
| [luyug/GC-DPR](https://github.com/luyug/GC-DPR) | ~136 | DPR training on a single GPU (gradient caching) — practical if we fine-tune DPR on PubMed abstracts locally. | **Reference** |
| [Hannibal046/nanoDPR](https://github.com/Hannibal046/nanoDPR) | ~55 | Minimal, readable DPR replication — good for understanding internals. | **Reference** |
| [dmis-lab/bioasq-biobert](https://github.com/dmis-lab/bioasq-biobert) | ~126 | BioBERT QA over BioASQ — the biomedical reader side of a DPR pipeline. | **Reference** |

## 4. Sentence-BERT for Scientific Literature

| Repository | Stars | Relevance | Use |
|---|---|---|---|
| [huggingface/sentence-transformers](https://github.com/huggingface/sentence-transformers) | ~19,000 | Canonical SBERT framework (formerly UKPLab/sentence-transformers). Likely already the backbone of our embedding/retrieval modules. | **Direct dependency** |
| [allenai/specter](https://github.com/allenai/specter) | ~590 | SPECTER: citation-informed document embeddings for scientific text — the classic baseline for scientific paper embeddings. | **Comparison baseline** for evidence retriever embeddings |
| [allenai/SPECTER2](https://github.com/allenai/SPECTER2) | ~140 | SPECTER successor with task-specific adapters. | **Comparison baseline** (newer) |
| [malteos/scincl](https://github.com/malteos/scincl) | ~79 | SciNCL (EMNLP 2022): neighborhood-contrastive citation embeddings for scientific documents. | **Comparison baseline** |

## 5. Process Reward Models / Step-level Verification

| Repository | Stars | Relevance | Use |
|---|---|---|---|
| [RyanLiu112/Awesome-Process-Reward-Models](https://github.com/RyanLiu112/Awesome-Process-Reward-Models) | ~180 | Curated index of PRM papers/code — fastest way to map the field for our step-verification work. | **Reference index** |
| [openai/prm800k](https://github.com/openai/prm800k) | ~2,150 | PRM800K dataset: 800k step-level correctness labels (MATH). Canonical resource if we train step-verifiers. | **Reference** (dataset) |
| [ssmisya/PRMBench](https://github.com/ssmisya/PRMBench) | ~94 | Fine-grained step-level PRM benchmark (ACL 2025) — usable to evaluate step-verification quality. | **Reference** (eval) |
| [CJReinforce/PURE](https://github.com/CJReinforce/PURE) | ~170 | Min-form credit assignment for PRMs — methodology reference for how to aggregate step scores. | **Reference** |
| [RyanLiu112/GenPRM](https://github.com/RyanLiu112/GenPRM) | ~100 | Generative-reasoning PRM scaling test-time compute. | **Reference** |
| [mukhal/ThinkPRM](https://github.com/mukhal/ThinkPRM) | ~90 | PRMs that think (TMLR). | **Reference** |

## 6. AI Scientist / Automated Research Pipelines

| Repository | Stars | Relevance | Use |
|---|---|---|---|
| [K-Dense-AI/scientific-agent-skills](https://github.com/K-Dense-AI/scientific-agent-skills) | ~33,900 | "Turn any AI agent into an AI Scientist": 160+ validated agent skills for science. Same concept space as MetaWingman's skill stack — worth studying for packaging/validation patterns. | **Reference** / **comparison** |
| [SakanaAI/AI-Scientist](https://github.com/SakanaAI/AI-Scientist) | ~14,400 | Fully automated discovery loop (ideate → experiment → write paper → review). Reference for end-to-end autonomous pipelines; not SR-specific. | **Reference** |
| [SakanaAI/AI-Scientist-v2](https://github.com/SakanaAI/AI-Scientist-v2) | ~7,000 | Agentic tree search version. | **Reference** |
| [AkariAsai/OpenScholar](https://github.com/AkariAsai/OpenScholar) | ~1,580 | Retrieval-augmented scientific literature synthesis (retrieve 100k+ papers, cite correctly, expert-evaluated). The closest "AI literature assistant" to MetaWingman's evidence layer. | **Comparison baseline** for RAG-based evidence synthesis |
| [ruc-datalab/DeepAnalyze](https://github.com/ruc-datalab/DeepAnalyze) | ~4,500 | Agentic LLM for autonomous data analysis. | **Reference** |
| [dwzhu-pku/PaperBanana](https://github.com/dwzhu-pku/PaperBanana) | ~6,900 | Automating academic illustration. | **Reference** (figures) |
| [EvoScientist/EvoScientist](https://github.com/EvoScientist/EvoScientist) | ~4,500 | Self-evolving AI scientists. | **Reference** |

## 7. metafor (R) Wrappers & Pipelines

| Repository | Stars | Relevance | Use |
|---|---|---|---|
| [wviechtb/metafor](https://github.com/wviechtb/metafor) | ~310 | The metafor package itself (Viechtbauer) — foundation of our 26-module deterministic R toolkit. | **Direct dependency** |
| [MathiasHarrer/dmetar](https://github.com/MathiasHarrer/dmetar) | ~46 | Companion package ("Doing Meta-Analysis in R") with semi-automated workflows (rma-based helpers, influence diagnostics). Good template for wrapping metafor deterministically. | **Reference** / **baseline** for workflow design |
| [prisma-flowdiagram/PRISMA2020](https://github.com/prisma-flowdiagram/PRISMA2020) | ~290 | Official R package for PRISMA-2020 flow diagrams — drop-in for our manuscript flow-diagram module. | **Direct use** |
| [mjwestgate/revtools](https://github.com/mjwestgate/revtools) | ~60 | R tools for research synthesis (screening, dedup, text mining of abstracts). | **Reference** for screening/dedup modules |
| [elizagrames/litsearchr](https://github.com/elizagrames/litsearchr) | ~130 | R package for search-term selection via keyword co-occurrence networks — supports our search-strategy module. | **Reference** |
| [nealhaddaway/livingPRISMAflow](https://github.com/nealhaddaway/livingPRISMAflow) | ~9 | Living SR flow diagrams (PRISMA-compliant). | **Reference** (living updates) |
| [Rimagination/easymeta](https://github.com/Rimagination/easymeta) | ~11 | Rigorous meta-analysis pipeline (medicine/ecology/biodiversity). | **Reference** |
| [cjvanlissa/metaforest](https://github.com/cjvanlissa/metaforest) | ~4 | Random-forest exploration of heterogeneity in meta-analysis. | **Reference** (heterogeneity module) |
| [ferreira-santos/metaforGUI](https://github.com/ferreira-santos/metaforGUI) | ~9 | GUI for metafor. | Low relevance (reference only) |

## 8. Cochrane RCT Classifier / ML Screening for Systematic Reviews

| Repository | Stars | Relevance | Use |
|---|---|---|---|
| [asreview/asreview](https://github.com/asreview/asreview) | ~975 | (also §1) Active-learning screening — the de-facto ML screening standard. | **Comparison baseline** |
| [ijmarshall/robotreviewer](https://github.com/ijmarshall/robotreviewer) | ~177 | RCT synthesis + RoB; includes RCT identification. | **Reference** / **baseline** |
| [bwallace/RRnlp](https://github.com/bwallace/RRnlp) | ~18 | NLP for evidence-based medicine (RCT classification, PICO extraction) — the research code behind RobotReviewer. | **Reference** |
| [ijmarshall/robotreviewer_old](https://github.com/ijmarshall/robotreviewer_old) | ~28 | Original automatic RoB assessment (Random Forest over BERT-style features). | **Reference** |
| [EPPI-Centre/CochraneCOVID19Classifier](https://github.com/EPPI-Centre/CochraneCOVID19Classifier) | ~7 | EPPI-Centre's Cochrane-style classifier (COVID-19 variant), recreatable from RIS files. | **Reference** |
| ⚠️ [ijmarshall/CochraneRCTClassifier](https://github.com/ijmarshall/CochraneRCTClassifier) | 404 | The original Marshall et al. (2018) Cochrane RCT classifier repo returned **404 (removed/archived)**. No HF copy found via HF search API either. Accessible implementations remain RRnlp/RobotReviewer; cite the *paper* (Marshall et al., JAMIA 2018) rather than a repo. | n/a (flag) |

## 9. Semantic Entropy for Hallucination Detection

| Repository | Stars | Relevance | Use |
|---|---|---|---|
| [OATML/semantic-entropy-probes](https://github.com/OATML/semantic-entropy-probes) | ~66 | Official code of **Semantic Entropy Probes** (Kossen et al., NeurIPS 2024) — the OATML group's current official semantic-entropy implementation (verified as the only entropy repo under the OATML org). Directly applicable to detecting hallucinations in our LLM screening/appraisal outputs. | **Reference** / **direct use** possible |
| [AlexanderVNikitin/kernel-language-entropy](https://github.com/AlexanderVNikitin/kernel-language-entropy) | ~36 | Fine-grained uncertainty for LLMs from semantic similarities (NeurIPS 2024). | **Reference** |
| [rdgbrandon/semanticentropy](https://github.com/rdgbrandon/semanticentropy) | ~0 | Interactive explorer implementing Farquhar et al. (Nature 2024) semantic entropy via NLI clustering. | **Reference** |
| ⚠️ jlko/semantic_entropy | 404 | The often-cited official repo for Farquhar et al. (Nature 2024) returned **404**; could not be located. Cite the paper; use OATML/semantic-entropy-probes as the accessible official code. | n/a (flag) |

## 10. Conformal Abstention / Risk Control for LLMs

| Repository | Stars | Relevance | Use |
|---|---|---|---|
| [Varal7/conformal-language-modeling](https://github.com/Varal7/conformal-language-modeling) | ~31 | Official code for **Conformal Language Modeling** (Quach et al.) — sequence-level conformal prediction for LLM outputs; the direct method for calibrated abstention in screening decisions. | **Reference** / candidate for **direct use** |
| [Bradley-Butcher/Conformers](https://github.com/Bradley-Butcher/Conformers) | ~29 | Unofficial CLM implementation. | **Reference** |
| [aangelopoulos/rcps](https://github.com/aangelopoulos/rcps) | ~90 | Official **Risk-Controlling Prediction Sets** (Bates et al.) — the risk-control framework behind many conformal abstention schemes. | **Reference** |
| [sinatayebati/vlm-uncertainty](https://github.com/sinatayebati/vlm-uncertainty) | ~6 | Conformal Abstention for LLMs and VLMs (ACML 2025) — most on-point recent implementation for LLM abstention. | **Reference** |
| [HHHAnQi/trustworthy-rag](https://github.com/HHHAnQi/trustworthy-rag) | ~2 | Agentic RAG with conformal prediction + calibrated abstention + NLI faithfulness. | **Reference** |

---

## Top picks for MetaWingman (by component)

- **Screening baseline:** MetaScreener, ASReview — benchmark our section-role classifier + LLM screening against both.
- **Evidence retriever:** fine-tune from `microsoft/BiomedNLP-BiomedBERT-*` (HF); compare embeddings vs **MedCPT**, **SPECTER2**, **SciNCL**, **sentence-transformers**.
- **Retriever architecture:** facebookresearch/DPR as the blueprint; GC-DPR if training locally on one GPU.
- **Appraisal classifier validation:** robotreviewer/RRnlp (RoB), Wang-Yuan-Chen RoB LLM analysis.
- **Step verification (VAL ladder):** PRMBench + PRM800K for eval/training; Awesome-Process-Reward-Models as index.
- **Hallucination / abstention gates:** OATML/semantic-entropy-probes + Varal7/conformal-language-modeling + aangelopoulos/rcps — directly map onto MetaWingman's cross-provider agreement and abstention logic.
- **Deterministic R toolkit:** metafor (core) + dmetar (workflow patterns) + PRISMA2020 (flow diagrams) + revtools/litsearchr (screening/search).
- **Pipeline comparison:** OpenScholar for RAG evidence synthesis; SakanaAI/AI-Scientist for autonomous-pipeline reference.

## Caveats

1. Star counts are from the GitHub REST API on 2026-08-19 and will drift; treat as order-of-magnitude.
2. Two often-cited repos no longer exist: `microsoft/BLURB` and `ijmarshall/CochraneRCTClassifier` (both 404); the Nature-2024 semantic-entropy code `jlko/semantic_entropy` also 404. Cite papers/models (HF) instead.
3. Small/zero-star repos (OpenMetaMate, SLR-Magic, PRISM-LLM) are single-lab projects — useful as design references, not battle-tested baselines.
4. `Math-Shepherd` (peiyi9979) also returned 404 during verification; use the Awesome-PRM list for canonical PRM code links instead.
