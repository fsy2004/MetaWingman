# Methodology and AI Source Registry

Verified: 2026-08-20
Purpose: exact primary or official sources governing MetaWingman. Recheck live versions at the start of every review and before a public methods claim.

The machine-readable reading and rule ledger is
[`human-methodology-training-registry.json`](human-methodology-training-registry.json).
It records local cache hashes, source scope, admitted rules, unsupported
inferences, and threshold provenance without distributing cached full text.

## Source Classes

- `CONDUCT` controls review methods for the selected profile.
- `REPORT` controls reporting completeness, not conduct quality or risk of bias.
- `APPRAISE` controls design/result-specific bias, missing-evidence, or certainty judgments.
- `EMPIRICAL` estimates AI performance on defined evidence-synthesis tasks and datasets.
- `MECHANISM` proposes a transferable AI/agent mechanism but cannot alter review methodology.
- `BENCHMARK` informs evaluation or security tests and is not evidence of MetaWingman performance.

For every project or research claim, retain the exact title, authors, venue, year, DOI/PMID or official identifier, source class, supported use, unsupported use, URL, verification date, and correction/retraction status.

## Conduct and Reporting Authorities

### COCH-HB — Cochrane Handbook

- **Identity:** *Cochrane Handbook for Systematic Reviews of Interventions*, root edition Version 6.5 (2024), with chapter-level Version 6.5.1 corrections recorded in 2025 and 2026.
- **Class:** `CONDUCT`.
- **Supports:** intervention-review scope, synthesis questions, search, selection, collection, RoB, analysis, missing evidence, GRADE, interpretation, and updates.
- **Boundary:** pin chapter dates; the root label “current” is insufficient. The handbook is primarily for intervention reviews.
- **Official:** [current handbook](https://www.cochrane.org/authors/handbooks-and-manuals/handbook/current), [versions and changes](https://www.cochrane.org/authors/handbooks-and-manuals/handbook/versions-and-changes-handbook).

### COCH-PICO — Review and Synthesis Questions

- **Identity:** Cochrane Handbook Chapters 2, 3, and 9.
- **Class:** `CONDUCT`.
- **Supports:** distinct review PICO, PICO for each synthesis, and PICO of included studies; outcome hierarchy, grouping, and result-selection rules.
- **Boundary:** do not exclude a study merely because an outcome result is unreported or unusable unless outcome measurement is a justified eligibility criterion.
- **Official:** [Chapter 2](https://training.cochrane.org/handbook/current/chapter-02), [Chapter 3](https://training.cochrane.org/handbook/current/chapter-03), [Chapter 9](https://www.cochrane.org/authors/handbooks-and-manuals/handbook/current/chapter-09).

### TOPIC-PRIORITY — Priority, Equity, and Stakeholder Process

- **Cochrane identity:** Thomas J, Kneale D, McKenzie JE, Brennan SE, Bhaumik S. Cochrane Handbook Chapter 2, last updated August 2023.
- **WHO identity:** *WHO guidance on the ethics of health research priority setting*. World Health Organization, 23 June 2025. ISBN 978-92-4-011095-3. [Official publication](https://www.who.int/publications/i/item/9789240110953).
- **REPRISE identity:** Tong A, Synnot A, Crowe S, et al. “Reporting guideline for priority setting of health research (REPRISE).” *BMC Medical Research Methodology*. 2019;19:243. DOI [10.1186/s12874-019-0889-3](https://doi.org/10.1186/s12874-019-0889-3).
- **Class:** Cochrane and WHO `CONDUCT/ETHICS`; REPRISE `REPORT`.
- **Supports:** decision-relevant questions, transparent stakeholder and governance records, explicit values and equity considerations, and traceable translation of a priority into an answerable review question.
- **Boundary:** priority setting is value-laden, not a model-only novelty score. REPRISE reports the process; it does not prescribe a preferred prioritization method, appraise conduct quality, or define priority criteria.

### UPDATE-REPLICATE — New Review, Update, Replication, or Stop

- **Update identity:** Garner P, Hopewell S, Chandler J, et al. “When and how to update systematic reviews: consensus and checklist.” *BMJ*. 2016;354:i3507. DOI [10.1136/bmj.i3507](https://doi.org/10.1136/bmj.i3507). The author-list correction is *BMJ*. 2016;354:i4853, DOI [10.1136/bmj.i4853](https://doi.org/10.1136/bmj.i4853).
- **Replication identity:** Tugwell P, Welch VA, Karunananthan S, et al. “When to replicate systematic reviews of interventions: consensus checklist.” *BMJ*. 2020;370:m2864. DOI [10.1136/bmj.m2864](https://doi.org/10.1136/bmj.m2864).
- **Class:** `CONDUCT/CONSENSUS`.
- **Supports:** classifying a candidate as a new review, update, purposeful replication, surveillance, archive, or stop based on question currency, stakeholder priority, existing-review validity, new evidence or methods, unresolved uncertainty, likely impact, feasibility, and opportunity cost.
- **Boundary:** these are judgment frameworks, not automatic thresholds; both were developed mainly around intervention reviews and require explicit adaptation for other profiles.

### COCH-SEARCH — Searching and Selecting Studies

- **Identity:** Lefebvre C, et al. Cochrane Handbook Chapter 4, last updated March 2025.
- **Class:** `CONDUCT`.
- **Supports:** multi-source sensitive search, study/report distinction, lawful retrieval, documentation, report linking, and selection.
- **Boundary:** literature QA or RAG does not constitute a reproducible comprehensive search.
- **Official:** [Chapter 4](https://www.cochrane.org/authors/handbooks-and-manuals/handbook/current/chapter-04).

### MECIR-C39 and MECIR-C46 — Independent Decisions

- **Identity:** MECIR C39, “Making inclusion decisions”; MECIR C46, “Extracting outcome data in duplicate”.
- **Class:** `CONDUCT`.
- **Supports:** at least two people independently make final study-eligibility decisions; at least two people independently extract outcome data, with predefined conflict resolution.
- **Boundary:** duplicate title/abstract screening is described as desirable in current Cochrane guidance; final full-text eligibility and duplicate outcome extraction are the mandatory points. An LLM is not silently counted as an independent person in an assurance review.
- **Official:** [C39](https://www.cochrane.org/authors/handbooks-and-manuals/mecir-manual/standards-conduct-new-cochrane-intervention-reviews-c1-c75/performing-review-c24-c75/selecting-studies-include-review-c39-c42), [MECIR manual](https://www.cochrane.org/authors/handbooks-and-manuals/mecir-manual).

### JBI-MANUAL — JBI Manual for Evidence Synthesis

- **Identity:** *JBI Manual for Evidence Synthesis*, current official manual.
- **Class:** `CONDUCT`.
- **Supports:** effectiveness, qualitative, etiology/risk, diagnostic, mixed-methods, umbrella, scoping, economic, and other JBI review types.
- **Boundary:** select and pin the relevant chapter; do not mechanically import intervention-review rules to every profile.
- **Official:** [JBI Manual](https://jbi-global.atlassian.net/wiki/spaces/MANUAL).

### DTA-HB — Diagnostic Test Accuracy Handbook

- **Identity:** *Cochrane Handbook for Systematic Reviews of Diagnostic Test Accuracy*, Version 2.0, July 2023.
- **Class:** `CONDUCT`.
- **Supports:** DTA question, search, extraction, bivariate/HSROC synthesis, and interpretation.
- **Boundary:** DTA methods and appraisal differ from intervention-effect reviews.
- **Official:** [Cochrane DTA handbook](https://training.cochrane.org/handbook-diagnostic-test-accuracy).

### PRESS — Search Strategy Peer Review

- **Identity:** McGowan J, et al. “PRESS Peer Review of Electronic Search Strategies: 2015 Guideline Statement.” *Journal of Clinical Epidemiology*. 2016;75:40-46. DOI [10.1016/j.jclinepi.2016.01.021](https://doi.org/10.1016/j.jclinepi.2016.01.021).
- **Class:** `CONDUCT`.
- **Supports:** structured peer review of database search strategies.
- **Boundary:** PRESS does not prove source coverage or replace known-item testing.
- **Record:** [PubMed](https://pubmed.ncbi.nlm.nih.gov/27005575/).

### TARCiS — Citation Searching

- **Identity:** Hirt J, et al. “Guidance on terminology, application, and reporting of citation searching: the TARCiS statement.” *BMJ*. 2024;385:e078384. DOI [10.1136/bmj-2023-078384](https://doi.org/10.1136/bmj-2023-078384).
- **Class:** `CONDUCT/REPORT`.
- **Supports:** transparent backward and forward citation searching.
- **Boundary:** citation chasing complements rather than replaces planned databases, registries, and grey sources.
- **Record:** [BMJ](https://www.bmj.com/content/385/bmj-2023-078384).

### RAPID — Rapid Review Guidance

- **Identity:** Garritty C, et al. “Updated recommendations for the Cochrane rapid review methods guidance for rapid reviews of effectiveness.” *BMJ*. 2024;384:e076335. DOI [10.1136/bmj-2023-076335](https://doi.org/10.1136/bmj-2023-076335).
- **Class:** `CONDUCT`.
- **Supports:** explicit, decision-driven rapid-review shortcuts.
- **Boundary:** a restricted process must not be labelled comprehensive.
- **Record:** [BMJ](https://www.bmj.com/content/384/bmj-2023-076335).

### PRISMA Family

- **PRISMA 2020:** Page MJ, et al. “The PRISMA 2020 statement: an updated guideline for reporting systematic reviews.” *BMJ*. 2021;372:n71. DOI [10.1136/bmj.n71](https://doi.org/10.1136/bmj.n71). [Record](https://www.bmj.com/content/372/bmj.n71).
- **PRISMA-P:** Moher D, et al. “Preferred reporting items for systematic review and meta-analysis protocols (PRISMA-P) 2015 statement.” *Systematic Reviews*. 2015;4:1. DOI [10.1186/2046-4053-4-1](https://doi.org/10.1186/2046-4053-4-1). [Official page](https://www.prisma-statement.org/protocols).
- **PRISMA-S:** Rethlefsen ML, et al. “PRISMA-S: an extension to the PRISMA Statement for Reporting Literature Searches in Systematic Reviews.” *Systematic Reviews*. 2021;10:39. DOI [10.1186/s13643-020-01542-z](https://doi.org/10.1186/s13643-020-01542-z). [EQUATOR](https://www.equator-network.org/reporting-guidelines/prisma-s/).
- **PRISMA-LSR:** Akl EA, et al.; PRISMA-LSR Group. “Extension of the PRISMA 2020 statement for living systematic reviews (PRISMA-LSR): checklist and explanation.” *BMJ*. 2024;387:e079183. DOI [10.1136/bmj-2024-079183](https://doi.org/10.1136/bmj-2024-079183). PMID 39562017. [Official page](https://www.prisma-statement.org/lsr).
- **Extensions:** use the [official PRISMA extension registry](https://www.prisma-statement.org/extensions) and pin each applicable version.
- **Class:** `REPORT`.
- **Boundary:** reporting compliance does not establish valid conduct, adequate search recall, low risk of bias, or certainty.

### SWiM — Synthesis Without Meta-analysis

- **Identity:** Campbell M, et al. “Synthesis without meta-analysis (SWiM) in systematic reviews: reporting guideline.” *BMJ*. 2020;368:l6890. DOI [10.1136/bmj.l6890](https://doi.org/10.1136/bmj.l6890).
- **Class:** `REPORT`.
- **Supports:** transparent reporting when statistical meta-analysis is not used.
- **Boundary:** not a license for informal vote counting.
- **Record:** [BMJ](https://www.bmj.com/content/368/bmj.l6890).

### Registration Authorities

- **PROSPERO:** prospective registration for eligible health-related reviews; registration is not peer review or endorsement. [Official guidance](https://www.crd.york.ac.uk/PROSPERO/documents/Guidance%20for%20registering%20human%20studies.pdf).
- **OSF Registrations:** immutable, timestamped registration, including a generalized systematic-review template where appropriate. [Official help](https://help.osf.io/article/330-welcome-to-registrations).
- **Class:** `CONDUCT/REGISTRY`.

## Appraisal, Missing Evidence, and Certainty

### ROB2 — Randomized Trials

- **Identity:** Sterne JAC, et al. “RoB 2: a revised tool for assessing risk of bias in randomised trials.” *BMJ*. 2019;366:l4898. DOI [10.1136/bmj.l4898](https://doi.org/10.1136/bmj.l4898); official tool release 22 August 2019.
- **Class:** `APPRAISE`.
- **Supports:** result-level RoB for randomized trials and design variants.
- **Boundary:** do not collapse domains into a study quality score.
- **Official:** [RoB 2](https://www.riskofbias.info/welcome/rob-2-0-tool).

### ROBINS-I — Non-randomized Intervention Studies

- **Identity:** Sterne JAC, et al. “ROBINS-I: a tool for assessing risk of bias in non-randomised studies of interventions.” *BMJ*. 2016;355:i4919. DOI [10.1136/bmj.i4919](https://doi.org/10.1136/bmj.i4919).
- **Class:** `APPRAISE`.
- **Supports:** target-trial-based, result-level RoB for NRSI.
- **Boundary:** the November 2025 ROBINS-I V2 is explicitly a draft subject to change. Pin the 2016 version or a named draft and justify its use.
- **Official:** [tool home](https://www.riskofbias.info/welcome/home), [V2 draft](https://www.riskofbias.info/welcome/robins-i-v2).

### ROBINS-E — Exposure Studies

- **Identity:** ROBINS-E official tool, Version 24 March 2024; associated article *Environment International*. 2024;186:108602. DOI [10.1016/j.envint.2024.108602](https://doi.org/10.1016/j.envint.2024.108602).
- **Class:** `APPRAISE`.
- **Supports:** non-randomized studies of exposure effects.
- **Boundary:** apply only to supported exposure questions and pin the exact form.
- **Official:** [ROBINS-E](https://www.riskofbias.info/welcome/robins-e-tool).

### ROB-ME and ROB-MEN — Missing Evidence

- **ROB-ME identity:** Page MJ, et al. “ROB-ME: a tool for assessing risk of bias due to missing evidence in systematic reviews with meta-analysis.” *BMJ*. 2023;383:e076754. DOI [10.1136/bmj-2023-076754](https://doi.org/10.1136/bmj-2023-076754). PMID 37984978. [Record](https://www.bmj.com/content/383/bmj-2023-076754).
- **ROB-MEN identity:** Chiocchia V, et al. “ROB-MEN: a tool to assess risk of bias due to missing evidence in network meta-analysis.” *BMC Medicine*. 2021;19:304. [Article](https://pmc.ncbi.nlm.nih.gov/articles/PMC8609747/), [official app](https://cinema.ispm.unibe.ch/rob-men/).
- **Class:** `APPRAISE`.
- **Supports:** missing whole studies and missing results at pairwise meta-analysis or network-meta-analysis level.
- **Boundary:** separate from within-result selection bias handled by RoB 2/ROBINS-I; neither is a study quality score.

### QUADAS-3 — Diagnostic Accuracy

- **Identity:** Whiting PF, Tomlinson E, Rutjes AWS, et al. “QUADAS-3: A Revised Tool for the Quality Assessment of Diagnostic Test Accuracy Studies.” *Annals of Internal Medicine*. Published online 17 February 2026. DOI [10.7326/ANNALS-25-02104](https://doi.org/10.7326/ANNALS-25-02104); official tool Version 1.2 when verified.
- **Class:** `APPRAISE`.
- **Supports:** estimate-level risk of bias and applicability for primary test-accuracy studies addressing diagnosis, screening, or staging.
- **Boundary:** QUADAS-2 is retained only when a protocol or historical comparison requires it.
- **Official:** [QUADAS home](https://www.bristol.ac.uk/population-health-sciences/projects/quadas/), [resources](https://www.bristol.ac.uk/population-health-sciences/projects/quadas/quadas-3/resources/).

### PROBAST+AI — Prediction Models

- **Identity:** Moons KGM, et al. “PROBAST+AI: an updated quality, risk of bias, and applicability assessment tool for prediction models using regression or artificial intelligence methods.” *BMJ*. 2025;388:e082505. DOI [10.1136/bmj-2024-082505](https://doi.org/10.1136/bmj-2024-082505).
- **Class:** `APPRAISE`.
- **Supports:** development quality, performance-evaluation RoB, applicability, and fairness.
- **Boundary:** state whether development, apparent/internal/external evaluation, or both are assessed.
- **Record:** [BMJ](https://www.bmj.com/content/388/bmj-2024-082505).

### Reviews of Reviews and Measurement Instruments

- **ROBIS:** Whiting P, et al. “ROBIS: A new tool to assess risk of bias in systematic reviews was developed.” *Journal of Clinical Epidemiology*. 2016;69:225-234. DOI [10.1016/j.jclinepi.2015.06.005](https://doi.org/10.1016/j.jclinepi.2015.06.005). [PubMed](https://pubmed.ncbi.nlm.nih.gov/26092286/).
- **AMSTAR 2:** Shea BJ, et al. “AMSTAR 2: a critical appraisal tool for systematic reviews that include randomised or non-randomised studies of healthcare interventions, or both.” *BMJ*. 2017;358:j4008. DOI [10.1136/bmj.j4008](https://doi.org/10.1136/bmj.j4008). [BMJ](https://www.bmj.com/content/358/bmj.j4008).
- **COSMIN:** official methodology for reviews of outcome measurement instruments. [Official guidance](https://www.cosmin.nl/finding-right-tool/conducting-systematic-review-outcome-measurement-instruments/).
- **Class:** `APPRAISE`.
- **Boundary:** ROBIS is for review-level bias, AMSTAR 2 for methodology, and COSMIN for measurement properties; none is interchangeable or a generic numeric quality score.

### RoB NMA and AMSTAR-PF — Profile-Specific Review/Synthesis Appraisal

- **RoB NMA:** Lunny C, et al. “Risk of Bias in Network Meta-Analysis (RoB NMA) tool.” *BMJ*. 2025;388:e079839. DOI [10.1136/bmj-2024-079839](https://doi.org/10.1136/bmj-2024-079839). PMID 40101916. A presentation error in Figure 1 was corrected in *BMJ*. 2025;389:r673. DOI [10.1136/bmj.r673](https://doi.org/10.1136/bmj.r673). [Article](https://www.bmj.com/content/388/bmj-2024-079839).
- **AMSTAR-PF:** Henry ML, et al. “AMSTAR-PF: a critical appraisal tool for systematic reviews of prognostic factor studies.” *BMJ*. 2025;391:e085718. DOI [10.1136/bmj-2025-085718](https://doi.org/10.1136/bmj-2025-085718). [Article](https://www.bmj.com/content/391/bmj-2025-085718).
- **Class:** `APPRAISE`.
- **Boundary:** RoB NMA assesses bias in the conduct, analysis, and conclusions of an individual completed NMA; ROB-MEN separately addresses missing evidence in NMA. AMSTAR-PF appraises systematic reviews of prognostic factors, not primary prognostic-factor studies.

### GRADE, CINeMA, and CERQual

- **GRADE Book:** current official guidance for outcome/comparison-level certainty and absolute effects. [Overview](https://book.gradepro.org/guideline/overview-of-the-grade-approach).
- **Decision thresholds:** outcome-specific thresholds make certainty judgments explicit; the line of no effect is generally not the relevant decision threshold. [Official guidance](https://book.gradepro.org/guideline/decision-thresholds).
- **CINeMA:** confidence in network meta-analysis. [Official site](https://cinema.ispm.unibe.ch/).
- **GRADE-CERQual:** confidence in qualitative evidence-synthesis findings. [Official guidance](https://www.cerqual.org/official-guidance-for-applying-grade-cerqual/).
- **Class:** `APPRAISE`.
- **Boundary:** certainty is not a hidden arithmetic score, and frameworks are profile-specific.

### ESTIMAND — Target Effects

- **Identity:** Kahan BC, Hindley J, Edwards M, Cro S, Morris TP. “The estimands framework: a primer on the ICH E9(R1) addendum.” *BMJ*. 2024;384:e076316. DOI [10.1136/bmj-2023-076316](https://doi.org/10.1136/bmj-2023-076316).
- **Class:** `CONDUCT/METHOD`.
- **Supports:** explicit population, treatment conditions, endpoint, intercurrent-event strategies, and population-level summary for intervention-effect questions.
- **Boundary:** a review still needs synthesis-level operationalization and compatibility checks.
- **Record:** [BMJ](https://www.bmj.com/content/384/bmj-2023-076316).

### CORE-OUTCOMES — Outcome Relevance

- **Identity:** Kirkham JJ, Davis K, Altman DG, et al. “Core Outcome Set-STAndards for Development: The COS-STAD recommendations.” *PLOS Medicine*. 2017;14(11):e1002447. DOI [10.1371/journal.pmed.1002447](https://doi.org/10.1371/journal.pmed.1002447). [PubMed](https://pubmed.ncbi.nlm.nih.gov/29145404/).
- **Class:** `CONDUCT/METHOD`.
- **Supports:** checking relevant core outcome sets and documenting stakeholder-relevant outcome domains when constructing the review outcome hierarchy.
- **Boundary:** an existing core outcome set informs outcome choice but does not replace review-specific criticality, time windows, instruments, estimands, adverse outcomes, or stakeholder confirmation.

## Empirical Evidence for AI in Evidence Synthesis

### GENAI-SR — Systematic Review of Generative AI

- **Identity:** Clark J, et al. “Generative artificial intelligence use in evidence synthesis: A systematic review.” *Research Synthesis Methods*. 2025;16(4):601-619. DOI [10.1017/rsm.2025.16](https://doi.org/10.1017/rsm.2025.16). PMID 41626912.
- **Class:** `EMPIRICAL`.
- **Supports:** current performance and failure evidence across search, screening, extraction, and RoB tasks.
- **Boundary:** the authors conclude that evidence does not support GenAI use in evidence synthesis without human involvement or oversight. The reported medians and ranges come from heterogeneous small studies and are not permanent model constants.
- **Records:** [PubMed](https://pubmed.ncbi.nlm.nih.gov/41626912/), [full text](https://pmc.ncbi.nlm.nih.gov/articles/PMC12527500/).

### AI-POSITION — Four-Organization Position Statement

- **Identity:** Flemyng E, et al. “Position statement on artificial intelligence (AI) use in evidence synthesis across Cochrane, the Campbell Collaboration, JBI and the Collaboration for Environmental Evidence 2025.” *Environmental Evidence*. 2025;14:20. DOI [10.1186/s13750-025-00374-5](https://doi.org/10.1186/s13750-025-00374-5). PMID 41174758.
- **Class:** `CONDUCT/POSITION`.
- **Supports:** responsible, disclosed, justified AI use while human authors retain responsibility.
- **Boundary:** permission is conditional on not compromising rigor or integrity; it is not evidence that a specific task is accurate.
- **Record:** [full text](https://pmc.ncbi.nlm.nih.gov/articles/PMC12577299/).

### TRIALMIND — Clinical Evidence Synthesis Pipeline

- **Identity:** Wang Z, Cao L, Danek B, et al. “Accelerating clinical evidence synthesis with large language models.” *npj Digital Medicine*. 2025;8:509. DOI [10.1038/s41746-025-01840-7](https://doi.org/10.1038/s41746-025-01840-7).
- **Class:** `EMPIRICAL`.
- **Supports:** source-linked search, screening, and extraction; TrialReviewBench with 100 reviews and 2,220 studies; a small human-AI workflow pilot.
- **Boundary:** for screening, the authors formed a 2,000-citation pool and ensured all target papers were included after initial retrieval. This isolates ranking but prevents the screening result from measuring upstream retrieval loss. Clinical/domain scope, retrospective review-derived targets, and a two-participant user study further limit transport. The authors explicitly state that TrialMind is not yet an end-to-end solution for all review steps; it does not validate complete multi-database coverage, RoB/GRADE, full lineage, or living updates.
- **Record:** [Nature](https://www.nature.com/articles/s41746-025-01840-7).

### METASYN-V6 — Stage-wise Meta-analysis Agent Benchmark

- **Identity:** Xie A, Su W, Zhou Y, Liu Y, Zhang M, Ai Q. “MetaSyn: A Benchmark for LLM Agents on Meta-Analysis Articles from Nature Portfolio.” arXiv:2606.17041v6, 26 July 2026.
- **Class:** `BENCHMARK/PREPRINT`.
- **Supports:** 422 source reviews, 86 held-out test instances, a shared 140,585-article PubMed corpus, structured PI/ECO and date bounds, and separate retrieval, evidence-selection, criteria, and written-synthesis metrics. In the reported ProtoMA trace decomposition, 20.7% of the reference set was lost at retrieval, 40.0% at explicit screening, and 39.3% reached the final list. Controlled diagnostics show that supplying a complete or ground-truth-first pool did not by itself repair final inclusion recall.
- **Boundary:** v6 supersedes earlier counts and results; do not repeat the former 442-instance or 90.9/52.7 summary as current. The source review is a fallible reference, only PubMed-linked articles are scored, title-match coverage is incomplete, and the current release evaluates retrieval, selection, and written synthesis rather than full-text extraction, report-study-result lineage, RoB, quantitative recomputation, GRADE, or living updates. It is a preprint and must be version-pinned.
- **Record:** [arXiv v6](https://arxiv.org/abs/2606.17041v6), [code](https://github.com/THUIR/MetaSyn), [dataset](https://huggingface.co/datasets/THUIR/MetaSyn).

### ASREVIEW — Active-Learning Prioritization

- **Identity:** van de Schoot R, et al. “An open source machine learning framework for efficient and transparent systematic reviews.” *Nature Machine Intelligence*. 2021;3:125-133. DOI [10.1038/s42256-020-00287-7](https://doi.org/10.1038/s42256-020-00287-7).
- **Class:** `EMPIRICAL`.
- **Supports:** active-learning prioritization with a human oracle and reproducible simulation.
- **Boundary:** prioritization and simulated work savings do not establish autonomous exclusion safety.
- **Record:** [Nature](https://www.nature.com/articles/s42256-020-00287-7).

### SCREEN-STOP — Statistical and Practical Screening Stopping

- **Statistical identity:** Callaghan MW, Muller-Hansen F. “Statistical stopping criteria for automated screening in systematic reviews.” *Systematic Reviews*. 2020;9:273. DOI [10.1186/s13643-020-01521-4](https://doi.org/10.1186/s13643-020-01521-4).
- **SAFE identity:** Boetje J, van de Schoot R. “The SAFE procedure: a practical stopping heuristic for active learning-based screening in systematic reviews and meta-analyses.” *Systematic Reviews*. 2024;13:81. DOI [10.1186/s13643-024-02502-7](https://doi.org/10.1186/s13643-024-02502-7).
- **Class:** `EMPIRICAL/METHOD`.
- **Supports:** predeclared recall and confidence targets with random sampling of unseen records; comparison with a conservative four-phase practical heuristic that combines random initialization, active learning, a different model, and quality evaluation.
- **Boundary:** Callaghan and Muller-Hansen reported an average 17% work reduction on their test datasets, not a universal savings estimate. SAFE is explicitly a practical heuristic rather than a distribution-free guarantee. Neither result proves end-to-end completeness, protects against an incomplete starting corpus, or transfers unchanged across review families, languages, prevalence, and drift.
- **Records:** [statistical stopping primary article](https://link.springer.com/article/10.1186/s13643-020-01521-4), [SAFE primary article](https://link.springer.com/article/10.1186/s13643-024-02502-7).

### ROBOTREVIEWER — Machine-Assisted RoB

- **Identity:** Marshall I, Kuiper J, Banner E, Wallace BC. “Automating Biomedical Evidence Synthesis: RobotReviewer.” *Proceedings of ACL 2017, System Demonstrations*. 2017:7-12.
- **Class:** `EMPIRICAL`.
- **Supports:** machine-assisted RoB evidence identification and preliminary judgments.
- **Boundary:** the task and tool predate several current instruments; final appraisal requires current, design-specific rules and verification.
- **Record:** [ACL Anthology](https://aclanthology.org/P17-4002/).

### PRISMA-TRAICE — Proposed AI Reporting Aid

- **Identity:** Holst M, et al. “Transparent Reporting of AI in Systematic Literature Reviews: Development of the PRISMA-trAIce Checklist.” *JMIR AI*. 2025;4:e80247. DOI [10.2196/80247](https://doi.org/10.2196/80247).
- **Class:** `REPORT/PROPOSED`.
- **Supports:** a useful proposed 14-item disclosure aid for AI use.
- **Boundary:** its authors describe it as a methodological proposal without a formal broad Delphi or consensus process. It is not an official PRISMA extension or conduct standard.
- **Record:** [JMIR AI](https://ai.jmir.org/2025/1/e80247/).

### HUMAN-AI — Human-AI Collaboration Meta-analysis

- **Identity:** Vaccaro M, Almaatouq A, Malone T. “When combinations of humans and AI are useful: A systematic review and meta-analysis.” *Nature Human Behaviour*. 2024;8:2293-2303. DOI [10.1038/s41562-024-02024-1](https://doi.org/10.1038/s41562-024-02024-1).
- **Class:** `EMPIRICAL`.
- **Supports:** warns that human-AI synergy cannot be presumed and motivates keeping claims within the selected experimental design.
- **Boundary:** across 106 experiments and 370 effects, human-AI combinations averaged below the better of human or AI alone. The current MetaWingman benchmark has no human execution arm, so this evidence is contextual only and does not supply a comparator.
- **Record:** [Nature](https://www.nature.com/articles/s41562-024-02024-1).

## Topic Opportunity and Scientific Ideation Mechanisms

### EVIDENCE-BASED-RESEARCH — Justifying New Questions from Existing Evidence

- **Identity:** Lund H, Brunnhuber K, Juhl C, et al. “Towards evidence based research.” *BMJ*. 2016;355:i5440. DOI [10.1136/bmj.i5440](https://doi.org/10.1136/bmj.i5440).
- **Class:** `CONDUCT/POSITION`.
- **Supports:** a candidate research question should be justified through a systematic assessment of existing evidence rather than selective citations or intuition alone.
- **Boundary:** this is a position article and does not define a machine ranking objective, a complete topic-selection algorithm, or a guarantee that a published review question was optimal.
- **Record:** [BMJ primary article](https://www.bmj.com/content/355/bmj.i5440).

### SCIMON — Literature-Grounded Novelty Iteration

- **Identity:** Wang Q, Downey D, Ji H, Hope T. “SciMON: Scientific Inspiration Machines Optimized for Novelty.” *Proceedings of ACL 2024, Volume 1: Long Papers*. 2024:279-299. DOI [10.18653/v1/2024.acl-long.18](https://doi.org/10.18653/v1/2024.acl-long.18).
- **Class:** `MECHANISM/EMPIRICAL`.
- **Transfer:** retrieve literature inspirations, compare proposed directions against prior papers, and iteratively revise candidates to reduce obvious duplication.
- **Boundary:** SciMON generates natural-language research directions rather than operational systematic-review questions. Its own evaluations found low technical depth and novelty in a GPT-4 baseline. Novel wording is not nonduplication, decision value, evidence maturity, or feasibility.
- **Record:** [ACL Anthology](https://aclanthology.org/2024.acl-long.18/).

### RESEARCHAGENT — Academic-Graph Ideation and Iterative Review

- **Identity:** Baek J, Jauhar SK, Cucerzan S, Hwang SJ. “ResearchAgent: Iterative Research Idea Generation over Scientific Literature with Large Language Models.” *NAACL 2025, Volume 1: Long Papers*. 2025:6709-6738. DOI [10.18653/v1/2025.naacl-long.342](https://doi.org/10.18653/v1/2025.naacl-long.342).
- **Class:** `MECHANISM/EMPIRICAL`.
- **Transfer:** connect a seed paper to related publications through an academic graph, retrieve shared concepts from a knowledge store, and revise proposals using multiple reviewing agents.
- **Boundary:** model- and human-rated idea quality does not establish comprehensive evidence coverage, review nonduplication, answerability, or prospective decision impact. Reviewing agents based on related models are not independent scientific adjudicators.
- **Record:** [ACL Anthology](https://aclanthology.org/2025.naacl-long.342/).

### LLM-IDEATION-STUDY — Controlled Expert Comparison

- **Identity:** Si C, Yang D, Hashimoto T. “Can LLMs Generate Novel Research Ideas? A Large-Scale Human Study with 100+ NLP Researchers.” *ICLR 2025*.
- **Class:** `EMPIRICAL/BENCHMARK`.
- **Supports:** blinded expert evaluation with confounder control; the reported LLM ideas were rated more novel but slightly less feasible, while model self-evaluation and generation diversity remained open problems.
- **Boundary:** the experiment concerns NLP research ideas, not evidence-synthesis topics, and novelty judgments do not imply scientific value or superiority over humans. MetaWingman has no human execution arm and must not import that comparative claim.
- **Record:** [ICLR proceedings](https://proceedings.iclr.cc/paper_files/paper/2025/hash/ea94957d81b1c1caf87ef5319fa6b467-Abstract-Conference.html).

### CONCEPT-GRAPH-DIRECTIONS — Time-Sliced Concept Extraction and Link Prediction

- **Identity:** Marwitz T, Colsmann A, Breitung B, et al. “Predicting new research directions in materials science using large language models and concept graphs.” *Nature Machine Intelligence*. 2026;8:535-544. DOI [10.1038/s42256-026-01206-y](https://doi.org/10.1038/s42256-026-01206-y).
- **Class:** `MECHANISM/EMPIRICAL`.
- **Transfer:** use LLM-extracted concepts, time-evolving co-occurrence graphs, structural features, semantic embeddings, and temporal link prediction to propose not-yet-observed concept combinations; retain high recall and let later gates evaluate false positives.
- **Boundary:** the study used materials-science abstracts and qualitative interviews with ten experts. Emerging concept links and “interesting” suggestions are not systematic-review opportunities. Its authors did not optimize a review-value threshold, and high false-positive output was intentionally deferred to human evaluation.
- **Record:** [Nature Machine Intelligence](https://www.nature.com/articles/s42256-026-01206-y).

### DELPHI — Dynamic Graph Early Warning of Research Impact

- **Identity:** Weis JW, Jacobson JM. “Learning on knowledge graph dynamics provides an early warning of impactful research.” *Nature Biotechnology*. 2021;39:1300-1307. DOI [10.1038/s41587-021-00907-6](https://doi.org/10.1038/s41587-021-00907-6).
- **Class:** `MECHANISM/EMPIRICAL`.
- **Transfer:** construct time-structured publication graphs, learn graph dynamics, conduct blinded retrospective back-testing, and build diversified candidate portfolios rather than selecting one fashionable node.
- **Boundary:** DELPHI predicts future time-rescaled graph centrality and demonstrated 19/20 retrospective seminal-biotechnology identification. Citation-network impact is not review priority, correctness, equity, feasibility, uncertainty resolution, or decision value.
- **Record:** [Nature Biotechnology](https://www.nature.com/articles/s41587-021-00907-6).

## Transferable LLM and Agent Mechanisms

### AI-SCIENTIST — End-to-End AI Research

- **Identity:** Lu C, et al. “Towards end-to-end automation of AI research.” *Nature*. 2026;651:914-919. DOI [10.1038/s41586-026-10265-5](https://doi.org/10.1038/s41586-026-10265-5).
- **Class:** `MECHANISM`.
- **Transfer:** staged research lifecycle, agentic search, executable checkpoints, and automated review as one signal.
- **Boundary:** computer-contained machine-learning experiments do not establish unattended systematic-review validity.
- **Record:** [Nature](https://www.nature.com/articles/s41586-026-10265-5).

### CO-SCIENTIST — Test-Time Scientific Search

- **Identity:** Gottweis J, et al. “Accelerating scientific discovery with Co-Scientist.” *Nature*. 2026;655:487-496. DOI [10.1038/s41586-026-10644-y](https://doi.org/10.1038/s41586-026-10644-y).
- **Class:** `MECHANISM`.
- **Transfer:** supervisor; generation, reflection, ranking, evolution, proximity, and meta-review; tournament and test-time compute.
- **Boundary:** model ranking or Elo is not scientific truth without external evidence.
- **Record:** [Nature](https://www.nature.com/articles/s41586-026-10644-y).

### VIRTUAL-LAB — Specialist Agents and Scientific Tools

- **Identity:** Swanson K, et al. “The Virtual Lab of AI agents designs new SARS-CoV-2 nanobodies.” *Nature*. 2025;646:716-723. DOI [10.1038/s41586-025-09442-9](https://doi.org/10.1038/s41586-025-09442-9).
- **Class:** `MECHANISM`.
- **Transfer:** PI-led specialist agents, specialized scientific tools, high-level human feedback, and external experimental verification.
- **Boundary:** multiple personas are not independent experts; the strong transferable element is differentiated tools and evidence.
- **Record:** [Nature](https://www.nature.com/articles/s41586-025-09442-9).

### COSCIENTIST-CHEM — Tool-Integrated Chemical Research

- **Identity:** Boiko DA, et al. “Autonomous chemical research with large language models.” *Nature*. 2023;624:570-578. DOI [10.1038/s41586-023-06792-0](https://doi.org/10.1038/s41586-023-06792-0).
- **Class:** `MECHANISM`.
- **Transfer:** interleaved planning, web/document search, code, instruments, and observations.
- **Boundary:** does not justify unbounded credentialed browser or laboratory actions.
- **Record:** [Nature](https://www.nature.com/articles/s41586-023-06792-0).

### OPENSCHOLAR — Literature RAG

- **Identity:** Asai A, et al. “Synthesizing scientific literature with retrieval-augmented language models.” *Nature*. 2026;650:857-863. DOI [10.1038/s41586-025-10072-4](https://doi.org/10.1038/s41586-025-10072-4).
- **Class:** `MECHANISM`.
- **Transfer:** specialized literature corpus, retrieval, cited synthesis, and expert benchmark.
- **Boundary:** literature QA quality is not database-level systematic-search recall.
- **Record:** [Nature](https://www.nature.com/articles/s41586-025-10072-4).

### DEEPRARE — Traceable Host-and-Specialist Medical Agent

- **Identity:** Zhao W, Wu C, Fan Y, et al. “An agentic system for rare disease diagnosis with traceable reasoning.” *Nature*. 2026;651:775-784. DOI [10.1038/s41586-025-10097-9](https://doi.org/10.1038/s41586-025-10097-9).
- **Class:** `MECHANISM/EMPIRICAL`.
- **Transfer:** use a central host with memory, differentiated specialist tool servers, heterogeneous up-to-date knowledge sources, source-linked reasoning, and an iterative validate-or-refute loop.
- **Boundary:** rare-disease differential diagnosis is not systematic-review conduct. Multiple roles powered by related models are not independent experts, and source-linked reasoning still requires field-level support and coverage evaluation.
- **Record:** [Nature](https://www.nature.com/articles/s41586-025-10097-9).

### ERA — Tree Search Against Executable Scientific Scores

- **Identity:** Aygun E, Belyaeva A, Comanici G, et al. “An AI system to help scientists write expert-level empirical software.” *Nature*. 2026;654:909-916. DOI [10.1038/s41586-026-10658-6](https://doi.org/10.1038/s41586-026-10658-6).
- **Class:** `MECHANISM/EMPIRICAL`.
- **Transfer:** mutate several candidate solutions, use tree search to balance exploration and exploitation, inject external research ideas, and retain branches using an executable quality metric.
- **Boundary:** most review judgments lack one complete leaderboard-style objective. MetaWingman can use executable checks for syntax, lineage, effect recalculation, and source support, but clinical value, RoB, certainty, and question validity remain multi-objective evidence judgments.
- **Record:** [Nature](https://www.nature.com/articles/s41586-026-10658-6).

### MIRA — Sandboxed Medical Action Space

- **Identity:** Ferber D, Hilgers L, Hoper C, et al. “Towards autonomous medical artificial intelligence agents.” *Nature*. 2026;655:1282-1291. DOI [10.1038/s41586-026-10675-5](https://doi.org/10.1038/s41586-026-10675-5).
- **Class:** `MECHANISM/EMPIRICAL`.
- **Transfer:** expose a broad but standardized action space inside a sandbox, maintain case state across sequential observations, and evaluate final structured actions rather than free-text advice alone.
- **Boundary:** the published evaluation used a simulated EHR workflow and explicitly called for prospective real-world safety and governance work. It does not authorize unattended credentialed search, download, registration, publication, or irreversible review decisions.
- **Record:** [Nature](https://www.nature.com/articles/s41586-026-10675-5).

### AMIE-MANAGEMENT — Longitudinal Guideline-Grounded Reasoning

- **Identity:** Lievin V, Palepu A, Weng WH, et al. “Towards conversational artificial intelligence for disease management.” *Nature*. 2026;655:1292-1299. DOI [10.1038/s41586-026-10764-5](https://doi.org/10.1038/s41586-026-10764-5).
- **Class:** `MECHANISM/EMPIRICAL`.
- **Transfer:** maintain longitudinal state across multiple encounters and ground structured reasoning in current authoritative guidelines and formularies.
- **Boundary:** guideline concordance in virtual clinical scenarios is not primary-study synthesis. MetaWingman uses authorities to constrain method and reporting while preserving primary sources, protocol eligibility, and result lineage as separate evidence layers.
- **Record:** [Nature](https://www.nature.com/articles/s41586-026-10764-5).

### OPEN-RUBRIC-HALLUCINATION — Abstention-Aligned Evaluation

- **Identity:** Kalai AT, Nachum O, Vempala SS, et al. “Evaluating large language models for accuracy incentivizes hallucinations.” *Nature*. 2026;653:1047-1051. DOI [10.1038/s41586-026-10549-w](https://doi.org/10.1038/s41586-026-10549-w).
- **Class:** `MECHANISM/EVALUATION`.
- **Transfer:** expose the cost of errors and the value of abstention in an open rubric, evaluate across several error penalties, and avoid headline metrics that reward guessing.
- **Boundary:** an open rubric changes incentives; it does not calibrate correctness by itself. MetaWingman must define task- and review-family-specific asymmetric loss and validate selective risk on sealed data.
- **Record:** [Nature](https://www.nature.com/articles/s41586-026-10549-w).

### PAPERQA2 and SCIRAG — Agentic Literature Exploration

- **PaperQA2 identity:** Skarlinski MD, Cox S, Laurent JM, et al. “Language agents achieve superhuman synthesis of scientific knowledge.” arXiv:2409.13740, 2024. This remained a preprint when verified. [arXiv](https://arxiv.org/abs/2409.13740).
- **SciRAG identity:** Ding H, Zhao Y, Hu T, et al. “SciRAG: Adaptive, Citation-Aware, and Outline-Guided Retrieval and Synthesis for Scientific Literature.” *Proceedings of the 19th Conference of the European Chapter of the Association for Computational Linguistics*, Volume 1, 2026:6440-6460. DOI [10.18653/v1/2026.eacl-long.303](https://doi.org/10.18653/v1/2026.eacl-long.303).
- **Class:** PaperQA2 `MECHANISM/PREPRINT`; SciRAG `MECHANISM`.
- **Transfer:** iterative scientific retrieval, cited synthesis, contradiction finding, adaptive sequential/parallel search, citation-graph traversal, and outline-plan-critic refinement.
- **Boundary:** literature QA and cited synthesis do not demonstrate database-level recall, study eligibility, numeric extraction, appraisal, or certainty. Citation graphs inherit coverage bias; the PaperQA2 claims require preprint-level qualification.

### REACT and TOOLFORMER — Reasoning With Tools

- **ReAct:** Yao S, et al. “ReAct: Synergizing Reasoning and Acting in Language Models.” ICLR 2023. [OpenReview](https://openreview.net/forum?id=WE_vluYUL-X).
- **Toolformer:** Schick T, et al. “Toolformer: Language Models Can Teach Themselves to Use Tools.” NeurIPS 2023. [Proceedings](https://proceedings.neurips.cc/paper/2023/hash/d842425e4bf79ba039352da0f658a906-Abstract-Conference.html).
- **Class:** `MECHANISM`.
- **Transfer:** interleave reasoning, typed actions, API calls, and observations.
- **Boundary:** tool selection is not tool correctness or authority; free-text calls need schemas and permission guards.

### TOT and BOT — Branching and Reusable Reasoning

- **Tree of Thoughts:** Yao S, et al. “Tree of Thoughts: Deliberate Problem Solving with Large Language Models.” NeurIPS 2023. [Proceedings](https://proceedings.neurips.cc/paper/2023/hash/271db9922b8d1f4dd7aaef84ed5ac703-Abstract.html).
- **Buffer of Thoughts:** Yang L, et al. “Buffer of Thoughts: Thought-Augmented Reasoning with Large Language Models.” NeurIPS 2024. [Proceedings](https://proceedings.neurips.cc/paper_files/paper/2024/hash/cde328b7bf6358f5ebb91fe9c539745e-Abstract-Conference.html).
- **Class:** `MECHANISM`.
- **Transfer:** explore, evaluate, and backtrack over ambiguous plans; reuse validated high-level templates.
- **Boundary:** model self-evaluation cannot be the sole pruning signal; templates require profile-specific revalidation.

### SELF-RAG, CRITIC, and NO-SELF-CORRECT — External Feedback

- **Self-RAG:** Asai A, et al. “Self-RAG: Learning to Retrieve, Generate, and Critique through Self-Reflection.” ICLR 2024. [OpenReview](https://openreview.net/forum?id=hSyW5go0v8).
- **CRITIC:** Gou Z, et al. “CRITIC: Large Language Models Can Self-Correct with Tool-Interactive Critiquing.” ICLR 2024. [OpenReview](https://openreview.net/forum?id=Sx038qxjek).
- **Boundary paper:** Huang J, et al. “Large Language Models Cannot Self-Correct Reasoning Yet.” ICLR 2024. [OpenReview](https://openreview.net/forum?id=IkmD3fKBPQ).
- **Class:** `MECHANISM`.
- **Transfer:** adaptive retrieval plus external-tool critique and correction.
- **Boundary:** same-model reflection is not independent verification; external feedback is the defensible mechanism.

### DEBATE and MOA — Multiple Candidate Models

- **Multiagent Debate:** Du Y, et al. “Improving Factuality and Reasoning in Language Models through Multiagent Debate.” ICML 2024, PMLR 235:11733-11763. [PMLR](https://proceedings.mlr.press/v235/du24e.html).
- **Mixture-of-Agents:** Wang J, et al. “Mixture-of-Agents Enhances Large Language Model Capabilities.” ICLR 2025. [ICLR proceedings](https://proceedings.iclr.cc/paper_files/paper/2025/hash/5434be94e82c54327bb9dcaf7fca52b6-Abstract-Conference.html).
- **Class:** `MECHANISM`.
- **Transfer:** proposal/opposition exchange and heterogeneous layered aggregation.
- **Boundary:** same-model instances have correlated errors, and MoA was evaluated mainly on general generation benchmarks. Debate and aggregation are not evidence-synthesis truth.

### ROUTELLM — Dynamic Model Routing

- **HybridLLM identity:** Ding D, Mallick A, Wang C, et al. “Hybrid LLM: Cost-Efficient and Quality-Aware Query Routing.” ICLR 2024. [ICLR proceedings](https://proceedings.iclr.cc/paper_files/paper/2024/hash/b47d93c99fa22ac0b377578af0a1f63a-Abstract-Conference.html).
- **RouteLLM identity:** Ong I, et al. “RouteLLM: Learning to Route LLMs from Preference Data.” ICLR 2025.
- **Class:** `MECHANISM`.
- **Transfer:** quality-cost routing between stronger and weaker models.
- **Boundary:** general preference routing must be recalibrated on MetaWingman tasks, profiles, and asymmetric losses.
- **Record:** [ICLR proceedings](https://proceedings.iclr.cc/paper_files/paper/2025/hash/5503a7c69d48a2f86fc00b3dc09de686-Abstract-Conference.html).

### DSPY — Declarative, Metric-Driven LM Pipelines

- **Identity:** Khattab O, Singhvi A, Maheshwari P, et al. “DSPy: Compiling Declarative Language Model Calls into State-of-the-Art Pipelines.” ICLR 2024. [ICLR proceedings](https://proceedings.iclr.cc/paper_files/paper/2024/hash/f1cf02ce09757f57c3b93c0db83181e0-Abstract-Conference.html).
- **Class:** `MECHANISM`.
- **Transfer:** express model calls as typed, reusable modules and optimize prompts/demonstrations against a task metric instead of maintaining hand-tuned prompt strings.
- **Boundary:** compilation can optimize a misspecified or leaked metric. MetaWingman optimization requires review-family splits, frozen gold labels, asymmetric scientific loss, and post-optimization external validation.

### TEST-TIME-SCALE — Adaptive Inference Budget

- **Identity:** Snell C, Lee J, Xu K, Kumar A. “Scaling LLM Test-Time Compute Optimally Can be More Effective than Scaling Parameters for Reasoning.” ICLR 2025. [ICLR proceedings](https://proceedings.iclr.cc/paper_files/paper/2025/hash/1b623663fd9b874366f3ce019fdfdd44-Abstract-Conference.html).
- **Class:** `MECHANISM`.
- **Transfer:** allocate search, sampling, and verifier calls by task difficulty rather than using a fixed best-of-N budget.
- **Boundary:** results are from reasoning benchmarks and depend on verifier quality. More inference cannot repair absent evidence, invalid rules, correlated model error, or a weak scientific objective.

### NOUGAT and OMNIDOC — Multimodal Document Parsing

- **Nougat:** Blecher L, et al. “Nougat: Neural Optical Understanding for Academic Documents.” ICLR 2024. [ICLR proceedings](https://proceedings.iclr.cc/paper_files/paper/2024/hash/a39a9aceda771cded859ae7560530e09-Abstract-Conference.html).
- **OmniDocBench:** Ouyang L, et al. “OmniDocBench: Benchmarking Diverse PDF Document Parsing with Comprehensive Annotations.” CVPR 2025. [CVPR proceedings](https://openaccess.thecvf.com/content/CVPR2025/html/Ouyang_OmniDocBench_Benchmarking_Diverse_PDF_Document_Parsing_with_Comprehensive_Annotations_CVPR_2025_paper.html).
- **Class:** `MECHANISM/BENCHMARK`.
- **Transfer:** scientific PDF to markup and multi-level text, formula, table, layout, and document evaluation.
- **Boundary:** one parser or an aggregate document score does not establish field-level extraction correctness.

### LONG-CONTEXT — Position-Sensitive Document Reasoning

- **Identity:** Liu NF, Lin K, Hewitt J, et al. “Lost in the Middle: How Language Models Use Long Contexts.” *Transactions of the Association for Computational Linguistics*. 2024;12:157-173. DOI [10.1162/tacl_a_00638](https://doi.org/10.1162/tacl_a_00638). [ACL Anthology](https://aclanthology.org/2024.tacl-1.9/).
- **Class:** `MECHANISM/BENCHMARK`.
- **Transfer:** test whether evidence-anchor recovery changes with source position and use structured retrieval, section-aware decomposition, and repeated positional probes for long reports and supplements.
- **Boundary:** a large context window is not evidence that all supplied pages were used; retrieval and position robustness require field-level evaluation.

### SEM-ENTROPY — Uncertainty Signal

- **Identity:** Farquhar S, et al. “Detecting hallucinations in large language models using semantic entropy.” *Nature*. 2024;630:625-630. DOI [10.1038/s41586-024-07421-0](https://doi.org/10.1038/s41586-024-07421-0).
- **Class:** `MECHANISM`.
- **Transfer:** semantic disagreement as one confabulation and abstention signal.
- **Boundary:** low entropy cannot detect a stable shared error and is not calibrated correctness.
- **Record:** [Nature](https://www.nature.com/articles/s41586-024-07421-0).

### CONFORMAL-TAIL — Tail-Risk Calibration

- **Identity:** Chen C, et al. “Conformal Tail Risk Control for Large Language Model Alignment.” ICML 2025, PMLR 267:8955-8978.
- **Class:** `MECHANISM`.
- **Transfer:** task-specific calibration of high-cost tail risk in human-machine scoring.
- **Boundary:** its published assumptions and results do not automatically guarantee systematic-review false-exclusion control. A new calibration target, exchangeability/drift analysis, and prospective evaluation are required.
- **Record:** [PMLR](https://proceedings.mlr.press/v267/chen25bd.html).

### CONFORMAL-RISK — Loss-Level Risk Control

- **Identity:** Angelopoulos AN, Bates S, Fisch A, Lei L, Schuster T. “Conformal Risk Control.” *ICLR 2024*.
- **Class:** `MECHANISM`.
- **Transfer:** calibrate a nested family of prediction sets or decision rules against a bounded task loss and choose an operating point that controls expected risk under the paper's assumptions.
- **Boundary:** conformal risk control is not automatically a false-exclusion guarantee for active-learning screening. MetaWingman must define a review-specific loss, nested decision family, exchangeability or drift conditions, calibration split, and sample size, then evaluate coverage by review family. Until that work passes, conformal scores are research candidates rather than production stopping authority.
- **Record:** [ICLR proceedings](https://proceedings.iclr.cc/paper_files/paper/2024/hash/f3549ef9b5ff520a7e41ff3cc306ab2b-Abstract-Conference.html).

### REFLEXION and LATS — Feedback Memory and Trajectory Search

- **Reflexion:** Shinn N, et al. “Reflexion: Language Agents with Verbal Reinforcement Learning.” NeurIPS 2023. DOI [10.52202/075280-0377](https://doi.org/10.52202/075280-0377). [Proceedings](https://proceedings.neurips.cc/paper_files/paper/2023/hash/1b44b878bb782e6954cd888628510e90-Abstract-Conference.html).
- **LATS:** Zhou A, et al. “Language Agent Tree Search Unifies Reasoning, Acting, and Planning in Language Models.” ICML 2024, PMLR 235:62138-62160. [PMLR](https://proceedings.mlr.press/v235/zhou24r.html).
- **Class:** `MECHANISM`.
- **Transfer:** retain verified failure feedback and search action trajectories with environment observations.
- **Boundary:** self-generated reflection can preserve errors; durable memory and rewards require external validation.

### ACI and TAU-BENCH — Agent Interfaces and Stateful Reliability

- **SWE-agent identity:** Yang J, Jimenez CE, Wettig A, et al. “SWE-agent: Agent-Computer Interfaces Enable Automated Software Engineering.” NeurIPS 2024. DOI [10.52202/079017-1601](https://doi.org/10.52202/079017-1601). [Proceedings](https://proceedings.neurips.cc/paper_files/paper/2024/hash/5a7c947568c1b1328ccc5230172e1e7c-Abstract-Conference.html).
- **tau-bench identity:** Yao S, Shinn N, Razavi P, Narasimhan K. “τ-bench: A Benchmark for Tool-Agent-User Interaction in Real-World Domains.” ICLR 2025. [ICLR proceedings](https://proceedings.iclr.cc/paper_files/paper/2025/hash/1b126cc38b8638e07bef37e7b2bb72bf-Abstract-Conference.html).
- **Class:** SWE-agent `MECHANISM`; tau-bench `BENCHMARK`.
- **Transfer:** design narrow scientific action/observation interfaces; verify final typed state rather than persuasive transcripts; measure repeated-run reliability with pass-style metrics and policy compliance.
- **Boundary:** software repair and customer-service domains do not establish evidence-synthesis accuracy. MetaWingman needs protocol, provenance, licensed-access, and scientific-state scenarios with deterministic end states.

### LLM-JUDGE — Automated Evaluation Bias

- **Identity:** Zheng L, Chiang WL, Sheng Y, et al. “Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena.” NeurIPS 2023 Datasets and Benchmarks Track. DOI [10.52202/075280-2020](https://doi.org/10.52202/075280-2020). [Proceedings](https://proceedings.neurips.cc/paper_files/paper/2023/hash/91f18a1287b398d378ef22505bf41832-Abstract-Datasets_and_Benchmarks.html).
- **Class:** `MECHANISM/BENCHMARK`.
- **Transfer:** randomize candidate order, use pairwise swaps, separate generator and judge where possible, expose evidence and rubrics, and audit position, verbosity, and self-enhancement bias.
- **Boundary:** agreement with human preferences on chat responses is not scientific correctness. LLM judges cannot replace source resolution, executable checks, or expert-adjudicated gold data.

### POPPER — Sequential Falsification

- **Identity:** Huang K, Jin Y, Li R, et al. “Automated Hypothesis Validation with Agentic Sequential Falsifications.” ICML 2025, PMLR 267:25372-25437. [PMLR](https://proceedings.mlr.press/v267/huang25n.html).
- **Class:** `MECHANISM`.
- **Transfer:** turn testable analysis claims into explicit implications, seek countertests, execute them with tools, record failed tests, and control repeated statistical testing when the mathematical conditions hold.
- **Boundary:** a proposed subtest may not be logically implied by the main claim, and Type-I error control is not truth or false-discovery control across generated claims. Narrative interpretation, eligibility, RoB, and GRADE must not be converted into invented p-values.

### ROBIN — Literature-to-Experiment Scientific Loop

- **Identity:** Ghareeb AE, Chang B, Mitchener L, et al. “A multi-agent system for automating scientific discovery.” *Nature*. 2026;655:497-505. DOI [10.1038/s41586-026-10652-y](https://doi.org/10.1038/s41586-026-10652-y).
- **Class:** `MECHANISM`.
- **Transfer:** maintain a continuous research state across deep literature search, hypothesis generation, data analysis, experimental feedback, and hypothesis revision; use differentiated agents and real external observations. Robin's authors observed that tools were almost always called in the same order and exposed a deterministic notebook route, supporting typed workflows when scientific actions are structurally stable.
- **Boundary:** the biology workflow and experimental verification are central to its evidence. It does not validate autonomous review conduct, and a literature-only agent cannot imitate the strength of external experimental feedback. A fixed tool order is evidence for deterministic orchestration, not proof that one fixed scientific method fits every review.

### AI-RESEARCHER — Autonomous Computational Research and Scientist-Bench

- **Identity:** Tang J, Xia L, Li Z, Huang C. “AI-Researcher: Autonomous Scientific Innovation.” *NeurIPS 2025*, Main Conference Track. DOI [10.52202/085713-0320](https://doi.org/10.52202/085713-0320).
- **Class:** `MECHANISM/BENCHMARK`.
- **Transfer:** package literature review, hypothesis generation, implementation, experimentation, and manuscript preparation as one system contribution; evaluate both guided innovation and open-ended exploration instead of one hand-picked demonstration.
- **Boundary:** the domain is computational AI research, where experiments and outputs can be contained in code environments. Claims of human-level paper quality do not transfer to evidence-synthesis recall, appraisal, certainty, or responsibility.
- **Record:** [NeurIPS proceedings](https://proceedings.neurips.cc/paper_files/paper/2025/hash/0d904d300a105809a2114d727851e759-Abstract-Conference.html).

### KOSMOS — Long-Horizon Shared Scientific World Model

- **Identity:** Mitchener L, Yiu A, Chang B, et al. “Kosmos: An AI Scientist for Autonomous Discovery.” arXiv:2511.02824, 2025.
- **Class:** `MECHANISM/PREPRINT`.
- **Transfer:** a structured world model shares claims, literature evidence, analysis outputs, and open questions between parallel literature-search and data-analysis agents over long research cycles. This supports one durable MetaWingman evidence state rather than stage-local chat memory.
- **Boundary:** the report remains a preprint. Its average papers read, code generated, statement accuracy, discovery count, and collaborator-estimated human-time equivalence are author-reported evaluations, not evidence-synthesis recall or an AI-versus-human execution trial. A long run with cited statements can still contain unsupported or protocol-ineligible evidence.
- **Record:** [arXiv](https://arxiv.org/abs/2511.02824).

### X-RAY-SCIENTIST — Simulation-to-Real Scientific Tool Agent

- **Identity:** Chen Z, Petsch AN, Israelski AJ, et al. “An agentic artificially intelligent X-ray scientist.” *Nature Machine Intelligence*. 2026;8:1075-1086. DOI [10.1038/s42256-026-01261-5](https://doi.org/10.1038/s42256-026-01261-5).
- **Class:** `MECHANISM/EMPIRICAL`.
- **Transfer:** structured tool use, plan-act-observe iteration, failure discovery in a virtual instrument, and direct deployment to a real synchrotron beamline show the value of testing an agent against realistic state and safety constraints before production use. MetaWingman should similarly promote workflows from fixtures to sealed reconstructions and prospective evidence batches.
- **Boundary:** the validated task is narrow X-ray sample alignment, not autonomous scientific interpretation or an entire discovery lifecycle. The prompts were iteratively refined around simulation failures, and some important instructions had to be reiterated; this supports typed guards and failure fixtures, not reliance on a long prompt.
- **Record:** [Nature Machine Intelligence](https://www.nature.com/articles/s42256-026-01261-5), [data](https://doi.org/10.5281/zenodo.20017861), [code](https://doi.org/10.5281/zenodo.20017991).

### MAST — Multi-Agent Failure Traces

- **Identity:** Cemri M, Pan MZ, Yang S, et al. “Why Do Multi-Agent LLM Systems Fail?” *NeurIPS 2025*, Datasets and Benchmarks Track.
- **Class:** `BENCHMARK`.
- **Transfer:** 1,600-plus annotated traces across seven multi-agent systems and a 14-mode taxonomy covering system design, inter-agent misalignment, and task verification support stage- and trajectory-level failure analysis rather than counting agent votes.
- **Boundary:** coding, mathematics, and general-agent failures do not supply a scientific error taxonomy or causal attribution for evidence synthesis. Transcript labels remain observational; MetaWingman must connect traces to typed scientific state and intervention replay.
- **Record:** [NeurIPS proceedings](https://proceedings.neurips.cc/paper_files/paper/2025/hash/b1041e52d3be19f0a9bc491657488e4a-Abstract-Datasets_and_Benchmarks_Track.html).

### AGENTIF — Long and Constrained Agent Instructions

- **Identity:** Qi Y, Peng H, Wang X, et al. “AGENTIF: Benchmarking Large Language Models Instruction Following Ability in Agentic Scenarios.” *NeurIPS 2025*, Datasets and Benchmarks Track. DOI [10.52202/085713-1892](https://doi.org/10.52202/085713-1892).
- **Class:** `BENCHMARK`.
- **Transfer:** 707 instructions from 50 agentic tasks average 1,723 words and 11.9 constraints; poor performance on complex structures and tool rules motivates compiling protocols into typed predicates and executable guards instead of relying on a long prompt.
- **Boundary:** generic instruction adherence is not protocol validity. A model may follow an incorrect rule perfectly, so authority, version, evidence, and scientific validation remain separate.
- **Record:** [NeurIPS proceedings](https://proceedings.neurips.cc/paper_files/paper/2025/hash/51bb3a8a33610a25aae074bfc51b1b1f-Abstract-Datasets_and_Benchmarks_Track.html).

### BIOMEDAGENT — Tool-Aware Biomedical Data Analysis

- **Identity:** Bu D, Sun J, Li K, et al. “Empowering AI data scientists using a multi-agent LLM framework with self-evolving capabilities for autonomous, tool-aware biomedical data analyses.” *Nature Biomedical Engineering*. 2026. DOI [10.1038/s41551-026-01634-6](https://doi.org/10.1038/s41551-026-01634-6).
- **Class:** `MECHANISM/BENCHMARK`.
- **Transfer:** executable tool chains, interactive exploration, retrieved experience, 327 open biomedical analysis tasks, and external BixBench evaluation show how broad tool capability can be made measurable.
- **Boundary:** task success in bioinformatics, machine learning, and image segmentation is not lifecycle coverage of evidence synthesis. Self-evolution from stored trajectories requires leakage, failure-retention, version, and domain-shift controls.
- **Record:** [Nature](https://www.nature.com/articles/s41551-026-01634-6).

### BIOMEDICAL-CODE-PLAN — Plan Before Code

- **Identity:** Wang Z, Danek B, Yang Z, et al. “Making large language models reliable data science programming copilots for biomedical research.” *Nature Biomedical Engineering*. 2026;10:1732-1746. DOI [10.1038/s41551-025-01587-2](https://doi.org/10.1038/s41551-025-01587-2).
- **Class:** `EMPIRICAL/MECHANISM`.
- **Transfer:** a benchmark of 293 coding tasks from 39 studies found overall accuracy below 40% for tested unadapted approaches; refining an analysis plan before code improved the proposed agent to 74%. This supports typed analysis manifests and plan verification before R execution.
- **Boundary:** coding-task accuracy and a five-researcher user study do not validate estimand choice, poolability, numerical meta-analysis, or entire review workflows.
- **Record:** [Nature](https://www.nature.com/articles/s41551-025-01587-2).

### SCIENCEAGENT — Scientific Agent Benchmark

- **Identity:** Chen Z, et al. “ScienceAgentBench: Toward Rigorous Assessment of Language Agents for Data-Driven Scientific Discovery.” ICLR 2025.
- **Class:** `BENCHMARK`.
- **Transfer:** realistic task-level scientific-agent evaluation and failure decomposition.
- **Boundary:** supports component validation before end-to-end claims, not direct MetaWingman performance.
- **Record:** [ICLR proceedings](https://proceedings.iclr.cc/paper_files/paper/2025/hash/f12b4df26344f3be803c06b555252efe-Abstract-Conference.html).

### AGENTDOJO and ASB — Agent Security

- **AgentDojo:** Debenedetti E, et al. “AgentDojo: A Dynamic Environment to Evaluate Prompt Injection Attacks and Defenses for LLM Agents.” NeurIPS 2024 Datasets and Benchmarks. DOI [10.52202/079017-2636](https://doi.org/10.52202/079017-2636). [Proceedings](https://proceedings.neurips.cc/paper_files/paper/2024/hash/97091a5177d8dc64b1da8bf3e1f6fb54-Abstract-Datasets_and_Benchmarks_Track.html).
- **Agent Security Bench:** Zhang H, et al. “Agent Security Bench (ASB): Formalizing and Benchmarking Attacks and Defenses in LLM-based Agents.” ICLR 2025. [ICLR proceedings](https://proceedings.iclr.cc/paper_files/paper/2025/hash/5750f91d8fb9d5c02bd8ad2c3b44456b-Abstract-Conference.html).
- **Class:** `BENCHMARK`.
- **Transfer:** indirect prompt injection, memory poisoning, tool misuse, data exfiltration, and utility-security evaluation.
- **Boundary:** source domains differ from reviews and existing defenses remain limited. MetaWingman needs PDF, supplement, webpage, and retrieval-specific adversarial tests.

## Maintenance Rules

1. Prefer official handbook/tool pages, publisher records, PubMed/Europe PMC, and formal conference proceedings over lab posts, news, vendor pages, or search snippets.
2. When a preprint later has a formal publication, cite the formal identity and retain the preprint only if it supplies a separately required artifact.
3. Mark draft tools and proposed reporting checklists explicitly; never promote them to official status by repetition.
4. Record `supports` and `does_not_support` for every new source so architectural enthusiasm cannot silently become a methodological claim.
5. Recheck live versions, URLs, venue/year identities, corrections, and retractions before release.
