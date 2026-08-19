# 基准对标调研：arXiv:2606.17041（MetaSyn）任务分类学 → MetaWingman 映射

> 调研日期：2026-08-18 · 调研人：MetaWingman 基准对标子代理
> 关联文档：`docs/architecture/next-steps-2026-08-18.md`（"Benchmarking LLM Agents on Meta-Analysis Articles from Nature Portfolio (arXiv:2606.17041)" 一节）
> 本调研只读网络 + 仅写本文件；未修改仓库其他文件，未 git 提交。

---

## 1. 论文元信息

| 项 | 内容 |
|---|---|
| 标题 | **MetaSyn: A Benchmark for LLM Agents on Meta-Analysis Articles from Nature Portfolio**（v1 曾用标题：Benchmarking LLM Agents on Meta-Analysis Articles from Nature Portfolio） |
| 作者 | Anzhe Xie, Weihang Su, Yujia Zhou, Yiqun Liu, Min Zhang, Qingyao Ai（清华大学 THUIR，信息检索方向；Qingyao Ai 为通讯作者） |
| arXiv | 2606.17041 [cs.CL]（交叉 cs.IR）· DOI: 10.48550/arXiv.2606.17041 |
| 版本史 | v1 提交 2026-06-15；v6（当前权威版）最后修订 2026-07-26 |
| 官方资源 | 代码 https://github.com/THUIR/MetaSyn · 数据集 https://huggingface.co/datasets/THUIR/MetaSyn · 检索模型（MA-Retriever）https://huggingface.co/BFTree/MA-Retriever |
| 获取日期 | 2026-08-18 |
| 获取方式 | ① `read_page` 抓取 arXiv 摘要页（abs/2606.17041，成功）；② `read_page` 抓取 HTML 全文（html/2606.17041v6，成功但提取内容在 §3.4 处被截断）；③ `pwsh` Invoke-WebRequest 只读抓取 v6 原始 HTML 并在内存中剥离标签、提取 **§4 全文（含全部指标公式）**，未落盘任何文件；④ `read_page` 抓取官方 GitHub 仓库 README（github.com/THUIR/MetaSyn，成功）；⑤ `read_page` 抓取 v1 HTML（html/2606.17041v1，用于摘要/贡献/§4 旧版结构佐证）；⑥ `web_search` 未使用（read_page 已覆盖）；HuggingFace 数据集卡读取**超时失败** |
| 内容来源标注 | §2.2/§3.3/§3.5/§4/§5.1 来自 **v6 全文原文**；指标清单（9 主指标 + 4 检索诊断）经 **官方 GitHub README** 与 **v1 摘要/贡献节** 双重交叉验证；实验数值（91.7% R@200、51.2% 端到端纳入召回）来自 **v6 GitHub README** |
| 版本差异提示 | v1 与 v6 数字不一致（v1：442 实例 / 90.9% R@200 / 52.7% 纳入召回；v6：**422 实例 / 91.7% R@200 / 51.2% 纳入召回**）。本文件一律以 **v6（最新权威版）** 为准。 |

---

## 2. MetaSyn 任务分类学（task taxonomy）

### 2.1 总览：工作流与评测范围的边界（v6 §2.2）

论文把 meta 分析描述为四个有序阶段（v6 §2.2）：**Retrieval → Screen → Extract and analyze → Synthesize and report**（PRISMA 提供对应报告框架）。
但论文明确**只评测其中三个阶段**，因为只有这三个阶段能对源综述构建一致的参考标签：

> "MetaSyn evaluates the three stages for which consistent reference labels can be constructed across the source reviews: **retrieval, protocol-based selection, and written synthesis**."（v6 §2.2）

即：**数据提取（extraction）与统计合并（effect-size 计算、meta 分析模型）不在 MetaSyn 的评测任务集内**；偏倚评估（risk of bias）亦完全未涉及。这一点对映射至关重要——MetaWingman 在这两块的组件属于"对方未评测"区域，不构成 gap。

### 2.2 任务定义（v6 §4.1 "Tasks and Labels"）

MetaSyn 定义**两个关联任务**：

1. **检索任务（retrieval task）**：对给定 meta 分析实例，对共享语料库（140,585 篇 PubMed 锚定文章）中的文章排序。
2. **端到端任务（end-to-end task）**：基于检索证据生成报告，报告必须 (a) **点名纳入的文章**（included articles），(b) **陈述纳入与排除标准**（inclusion/exclusion criteria），(c) **给出结论与关键发现**（conclusion and key findings）。

术语（v6 §4.1）：*selection* = 选择证据的整体过程；*screening* = 候选级的 include/exclude 判定。参考标签分三层（§4.1 Figure 2）：**ID labels**（Included Articles）、**Protocol labels**（Included Articles, Eligibility Criteria）、**Synthesis labels**（Direction + Key Insights）。

### 2.3 评测指标（v6 §4.2、§4.3；共 9 个主指标 + 2 个检索隔离指标）

**A. 检索隔离指标（v6 §4.2 "Retrieval Metrics"）**——检索任务单独评分，每实例计算后 test 集 macro-average：
- **R@K** = |P_K ∩ G| / |G|（参考文章被检索到的比例，recall）
- **P@K** = |P_K ∩ G| / |P_K|（检索池中属于参考集的比例，precision）
- 另记录 **token 使用量** 作为检索深度诊断（retrieval-depth diagnostic）

**B. 端到端指标（v6 §4.3 "End-to-End Metrics"）**，其中 G=黄金参考文章集，P=暴露给系统的候选池，L=系统最终报告去重后的纳入清单（未匹配条目留在 L 中、计入精度分母）：

1. **Included article metrics（纳入文章指标）**：
   - **Inc.R** = |L∩G| / |G|（对黄金集的覆盖率）
   - **Inc.P** = |L∩G| / |L|（最终清单中属于黄金集的比例）
   - **Inc.F1** = 2·Inc.R·Inc.P / (Inc.R + Inc.P)
2. **Screening accuracy（筛选准确率）**：**Scr.A** = (1/|P|) Σ_a 𝟙[ŷ_a = y_a]——候选级预测标签与参考标签的一致率（候选级二分类）。
3. **Criteria consistency（标准一致性）**：**Cons(Q,R)** = 2·ps·rs/(ps+rs)，其中 ps=软精度、rs=软召回（报告标准项与参考标准项的嵌入余弦相似度 best-match 均值，harmonic mean）。**Inc.C** 用于纳入标准，**Exc.C** 用于排除标准。空 Q 或 ps+rs≤0 记 0；无参考 R 的实例跳过。
4. **Synthesis metrics（合成指标）**：
   - **Dir.A（Direction Accuracy）** = 𝟙[d̂ = d]——结论方向匹配准确率。方向标签为三分类 **Positive / Negative / Mixed**（v6 §3.3：Positive/Negative 表示报告答案方向；Mixed 覆盖冲突、null、异质、描述性或非方向性结论）。
   - **Insights**——报告对参考关键发现（key findings）的覆盖度，0–1。
   - **SQ（Structure Quality）**——报告组织结构评分，1–5。

（v6 原文："Table 4 reports all nine metrics"，9 个 = Inc.R / Inc.P / Inc.F1 / Scr.A / Inc.C / Exc.C / Dir.A / Insights / SQ。）

**C. 评估器指标的人工校验（v6 §4.3 末尾引 Appendix F.2）**：Dir.A 与 8 名标注者两两判断的排名一致性最强（**ρ = +0.82**）；Exc.C 与 Insights 支持系统级比较；Inc.C 与 SQ 仅作描述性指标。（Appendix F.2 正文未逐字读取，见第 5 节诚实声明。）

**D. 官方仓库补充的检索诊断（GitHub README "Evaluate one report" 节）**：四个可直接复算的诊断：
- **retrieval_recall** = |P∩G| / |G|
- **retrieval_precision** = |P∩G| / |P|
- **conditional_retention** = |P∩G∩L| / |P∩G|（检索到的参考文章中被最终纳入的比例）
- **post_retrieval_loss** = |(P∩G) − L| / |G|（检索成功但后续被遗漏的参考文章占比）

### 2.4 数据集规模（v6 §3.5 Table 2）

422 个实例（test 86）；7,374 个 instance/article 对、7,187 个唯一 PMID（test 1,677 对 / 1,649 唯一）；每实例平均报告纳入 38.4 个研究 / 链接 17.5 篇文章；标题匹配率整体 51.6% / test 67.7%；PI/ECO 结构化 100%、检索策略 99.5%、检索结束日期 99.5%、纳入标准 96.4%；共享语料 140,585 篇（PMC 全文 57.0%、含结构化章节 48.3%）。

### 2.5 评测系统基线（v6 §5.1，供参考）

检索器：BM25、BGE-large-en-v1.5（FAISS）、MA-Retriever（BGE 在 MetaSyn 训练划分上微调）。生成：one-pass RAG（固定 top-200 池 + LLM 写报告，LLM 为 DeepSeek-V4-Pro / GLM-5.1 / GPT-5.4）；ProtoMA（GPT-5.4，在合成前显式筛选）。关键结果（README v6）：MA-Retriever **R@200 = 91.7%**，但标准检索下最高端到端纳入召回仅 **51.2%**——"检索高召回不保证筛选性能"，筛选（screening）是主要瓶颈。

---

## 3. 与 MetaWingman 任务集的逐项映射

MetaWingman 对照侧（已核实存在）：
- 十阶段 Socratic 清单 `metawingman/references/socratic-checklists/`：topic / protocol / search / screening / extraction / appraisal / analysis / writing / reproducibility / update（各 9–10 项，带 required/optional gate）
- 脚本 `metawingman/scripts/`：`search_sources.py`、`deduplicate_records.py`、`download_open_access.py`、`screen_record.py`、`recalculate_effect.py`、`verify_citations.py`、`verify_appraisal_steps.py`（appraisal 卷宗的规则式步骤校验）、`check_socratic_checklist.py`（按阶段 gate 检查清单作答完整性）、`blind_judge_certificates.py`（双 judge 盲评 5 维度 1–5 + judge 间一致性）、`evaluate_topic_rediscovery.py`（锁定时间切分的主题再发现评分）、`evaluate_pipeline.py`（在孤立 source-grounded case 上评估编译后的管线）、`evaluate_ai_only.py` / `run_ai_only_pilot.py`（AI-only 重复运行基准聚合）、`build_poolability_matrix.py`、`living_update.py` 等

映射列说明：covered = 我方有对应任务/组件（流程或检查）；partial = 有部分对应但缺对方的关键评测能力；gap = 我方无对应。

| # | MetaSyn 任务/指标（来源） | MetaWingman 对应组件 | 覆盖状态 |
|---|---|---|---|
| 1 | **检索任务 + R@K / P@K**（v6 §4.1/§4.2） | `search.json` 10 项（策略推导、known-item 召回验证、过滤器版本、原始导出+hash、灰色文献、去重、日期边界）；`search_sources.py`；`deduplicate_records.py` | **partial** —— 检索执行与策略审计齐全，但无离线 PubMed 锚定黄金语料，也无 R@K/P@K 的定量评测（known-item 测试是策略验证，非 benchmark 指标） |
| 2 | **端到端报告生成**（点名纳入文章+标准+结论；v6 §4.1） | 全管线（`run_structured_batch.py`、`compile_pipeline.py`）；`writing.json`；`evaluate_pipeline.py`（source-grounded 案例评估） | **partial** —— 有生成与内部评估框架，但无对黄金基准报告的三段式自动评分 |
| 3 | **Inc.R / Inc.P / Inc.F1**（纳入清单 vs 黄金清单；v6 §4.3） | `verify_citations.py`（引用存在性/一致性校验）；`screening.json`（逐条排除理由可复现 PRISMA flow）；`extraction.json`（研究/报告谱系） | **partial** —— 有引用与谱系完整性校验，无"报告纳入清单 vs 专家黄金清单"的 recall/precision/F1 评分 |
| 4 | **Scr.A 筛选准确率**（候选级 include/exclude；v6 §4.3） | `screening.json` 10 项（双人独立筛选、abstract-only 升级规则、冲突仲裁、排除理由记录）；`screen_record.py` | **partial** —— 筛选流程与记录齐全，但无候选级二分类对黄金标签的准确率评测 |
| 5 | **Inc.C / Exc.C 标准一致性**（嵌入相似度；v6 §4.3） | `screening.json-02`（eligibility criteria 与 certificate PICOT 原语"字段级映射"核对）；`protocol.json`；`check_socratic_checklist.py` | **covered** —— 有字段级人工映射核对（MetaSyn 用自动嵌入相似度度量，我方为确定性核对，能力对应） |
| 6 | **Dir.A 结论方向准确率**（Positive/Negative/Mixed；v6 §4.3 + §3.3） | `writing.json-03`（结论措辞与确定性等级匹配、区分"无效应证据"与"无证据"）；`blind_judge_certificates.py`（双盲评分） | **partial** —— 有结论措辞审计与盲评，但无 Positive/Negative/Mixed 三分类的自动方向判定与准确率指标 |
| 7 | **Insights 关键发现覆盖度**（v6 §4.3） | `writing.json-01`（每个定量声明追溯到验证过的分析输出+定位）；`compile_claim.py` | **partial** —— 有声明可追溯性审计，无"参考关键发现覆盖度"的自动评分 |
| 8 | **SQ 结构质量 1–5**（v6 §4.3） | `writing.json-06`（PRISMA 2020 27 项逐条带定位核对）；`check_socratic_checklist.py` | **covered** —— PRISMA 27 项逐条检查比 1–5 主观打分更严格 |
| 9 | **PI/ECO 协议结构化**（研究问题→结构化字段；v6 §3.3/§4.1） | `topic.json` + `protocol.json`（PICOT 原语与假设）；`screening.json-02` | **covered** |
| 10 | **检索元数据记录**（检索策略/日期边界/标准；v6 §3.5 Table 2 字段） | `search.json-04`（策略原样存储+运行日期+查询 hash）、`search.json-07`（日期边界与更新节奏） | **covered** |
| 11 | **语料库 + 硬负例/干扰项构造**（PubMed 锚定 140,585 语料、正例+topically-similar 但 PI/ECO 不合格的干扰项；v6 §3.4） | 无（`fetch_training_corpus.py` / `harvest_top_journal_corpus.py` 为训练语料采集，非"黄金纳入清单+干扰项池"评测语料） | **gap** |
| 12 | **阶段归因评测 + 检索诊断**（conditional_retention / post_retrieval_loss / token 深度；README §4.1） | `evaluate_pipeline.py`（孤立案例评估）、`evaluate_ai_only.py`（AI-only 重复运行聚合）、`evaluate_topic_rediscovery.py`（时间切分再发现） | **gap** —— 我方有内部评估但无"遗漏归因到检索 vs 筛选 vs 合成"的阶段分离指标 |
| 13 | **自动度量的人工校验分级**（8 标注者两两判断、ρ=+0.82；v6 §4.3/App. F.2） | `blind_judge_certificates.py`（双 judge 盲评 + inter-judge agreement）；`check_grade_threshold.py` | **partial** —— 有 judge 间一致性，但无对自动度量本身的人工校验与可靠性分层 |
| 14 | **数据提取 + 统计合并**（MetaSyn 四阶段之一，明确未评测；v6 §2.2） | `extraction.json`（提取与谱系）；`analysis.json`（效应量选择、固定/随机模型、异质性、poolability、小样本效应、敏感性分析）；`recalculate_effect.py`；`build_poolability_matrix.py` | **covered**（我方更全） |
| 15 | **偏倚评估**（MetaSyn 完全未涉及） | `appraisal.json`（RoB 2/ROBINS-I/QUADAS-2 工具匹配、域判断锚定、GRADE 衔接）；`verify_appraisal_steps.py`（规则式步骤校验） | **covered**（我方独有） |

**汇总：covered 6 · partial 7 · gap 2（共 15 项映射）**

---

## 4. Gaps 清单与建议

### Gap 1（最重要）：无黄金评测语料库（离线、PubMed 锚定、含硬负例）
- 对方：422 个专家 curated meta 分析实例，每实例含研究问题、PI/ECO 结构、检索策略与日期边界、纳入/排除标准、**黄金纳入文章清单**、结论方向标签与关键发现；共享 140,585 篇 PubMed 语料含 8,674 正例与 131,911 个"topically similar 但 PI/ECO 不合格"的硬负例（v1 §3.4 数字）。
- 我方：MetaWingman 全部为 live 流程（live 检索 + 人机双筛），没有任何离线 benchmark 语料可供定量评测组件。
- 建议：**值得补**。接入官方数据集（HuggingFace `THUIR/MetaSyn`）作为 MetaWingman 组件的第三方评测基准：把 search/screening/writing 阶段接到 MetaSyn 评测器，产出与论文可比的 R@K / Inc.R / Inc.P / Scr.A 分数。这是把 MetaWingman"流程完备但无分数"变成"可与 SOTA 基线比较"的最低成本路径。

**数据集卡核实（2026-08-18，经 HF API + 数据集卡 README 实际获取）**：
- 整体 `license: other`；**项目自建标注为 MIT**；PubMed 元数据/摘要、综述摘录、官方 PMC 派生段落**保留上游条款**；语料**不含**任何封闭出版商页面文本（README "Licensing and provenance" 原文）。
- 规模：422 篇 Nature Portfolio 源综述（336 训练 / 86 测试）+ 共享 140,585 篇 PubMed 语料；7,374 条综述-文章链接（7,187 篇唯一文章）；宏平均标题匹配率 51.6%（测试集 67.7%）——**参考集本身有缺口，Inc.R 天花板受限于此**。
- 构造：约 50 名标注者筛 34,375 候选；每条保留记录二次人工核查；GLM-4.6 起草 PI/ECO 字段、人工修正（README 原文）。
- 关键机制：`source_review_corpus_ids` 必须在 top-K 截断前移除；测试集链接文章已从检索器正例训练对排除。
- 效应量字段为字符串（数字/区间/NR 混合）——效应量对比需先解析。
- **接入判定**：标注 + PubMed 元数据可按 MIT/上游条款用于评测；正式纳入前需按项目惯例做一次许可清单存档（not yet done）。

### Gap 2：端到端纳入清单评分 + 阶段归因诊断
- 对方：Inc.R/Inc.P/Inc.F1 对黄金清单；conditional_retention / post_retrieval_loss 把"检索后遗漏"与"筛选丢弃"分离；token 用量作检索深度诊断。
- 我方：`verify_citations.py` 只校验引用存在性/一致性，无覆盖度/精度评分；无任何"失败发生在哪一阶段"的归因输出。
- 建议：**值得补**（若接入 MetaSyn 则顺带实现）。也可独立在 `evaluate_pipeline.py` 增加"黄金清单对照 + 归因诊断"输出，用于内部组件回归测试。

### Gap 3：自动合成度量（Dir.A / Insights / Inc.C-Exc.C）与人工校验分级
- 对方：结论方向三分类自动判定（Dir.A）、关键发现覆盖度（Insights）、标准一致性嵌入相似度（Inc.C/Exc.C），且经 8 标注者两两判断校验分级（Dir.A ρ=+0.82 最强；Exc.C/Insights 可作系统级比较；Inc.C/SQ 仅描述性）。
- 我方：盲评（`blind_judge_certificates.py`）与措辞审计（`writing.json`）是流程性的，无可复算的自动度量。
- 建议：**值得补**。最小实现：为 writing 阶段 gate 增加 Dir.A 式自动方向检查（Positive/Negative/Mixed，对照 `analysis`/`writing` 阶段产出），并记录一致性；Insights 覆盖度评估器可作为后续增强。建议采纳对方的可靠性分层思路（先人工校验再决定指标用途），与我方 `check_grade_threshold.py` 的做法一致。

### 不建议补的项
- SQ 1–5 主观结构打分：我方 PRISMA 2020 27 项逐条定位检查（`writing.json-06`）更强，无需退化。
- 提取/统计合并/偏倚评估的"评测化"：对方明确未评测这三块（v6 §2.2），我方组件已覆盖且更全（映射 #14/#15）。

---

## 5. 诚实声明（not verified 清单）

以下内容**未获取到**，本文件未据此做任何断言，如后续需要请补充获取：
- **HuggingFace 数据集卡**（`datasets/THUIR/MetaSyn`）：**2026-08-18 已补获取**（HF API 元数据 + 数据集卡 README 全文，经本地代理）。许可/规模/构造已核实（见 Gap 1 附录）；字段级说明已记录（Review fields / Corpus fields 表）。
- **v6 附录 F.2 / G.3 / C 的逐字内容**：仅凭 §4.3 正文引用（ρ=+0.82、Inc.C/SQ 描述性等）与 v1 摘要转述，附录正文 **not verified**。
- **Table 4 的具体数值表**与实验细节（检索深度、token 用量的具体数字）：本次任务范围外，未逐表核实。
- **v1 与 v6 之间所有数字差异**（422 vs 442 实例、91.7% vs 90.9% R@200、51.2% vs 52.7% 纳入召回）未逐项核对原因；本文件一律以 **v6** 为准并明确标注。
- 本任务分类学清单（第 2 节）全部条目均来自实际抓取内容（v6 §2.2/§3.3/§3.5/§4.1–4.3/§5.1 原文、v1 摘要、官方 GitHub README），**无任何臆造的任务名、数字或引用**。

---

*来源 URL：https://arxiv.org/abs/2606.17041 · https://arxiv.org/html/2606.17041v6 · https://arxiv.org/html/2606.17041v1 · https://github.com/THUIR/MetaSyn · 获取日期 2026-08-18*
