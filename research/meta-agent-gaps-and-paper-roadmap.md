# Meta-analysis agents：现有缺口与 MetaWingman 研究路线

检索日期：2026-08-12
范围：系统综述/Meta 分析专用 LLM 或 multi-agent 项目、任务级评估研究、正式方法学指南。项目特性按论文、公开仓库和公开 issue 核查；未公开的内部实现不作推断。

## 结论先行

“做一个 agent”本身已不足以构成论文贡献。较有机会的贡献是：**用方法学状态机约束 agent，用逐字段证据锚定和确定性统计工具降低错误，并在完整流水线 benchmark 上证明它在不牺牲召回和审计性的前提下节省人工**。

当前证据不支持无人监督的全自动系统综述。GenAI 在检索、筛选、提取和偏倚评价上仍有显著且任务依赖的错误；全流程系统尤其缺少可比较的 stage-level ground truth、人工工作量指标、版本复现和失败时的安全退出。MetaWingman 应定位为 **auditable human-AI evidence-synthesis agent**，而不是 autonomous review generator。

## 代表性项目与未解决问题

| 项目/证据 | 已做到 | 仍留下的缺口 | 对 MetaWingman 的启示 |
|---|---|---|---|
| [MetaSyn](https://arxiv.org/abs/2606.17041) / [代码](https://github.com/THUIR/MetaSyn) | 422 个 Nature Portfolio source reviews、140,585 条 PubMed corpus；把 retrieval、selection、synthesis 分开评价；公开配置、结果和测试 | 即使 retrieval Recall@200 达 91.7%，最高端到端 inclusion recall 仍仅 51.2%；主要是题名摘要/部分全文 corpus，不覆盖真实双人提取、RoB、统计复算和 GRADE | 采用 stage-attributed metrics；优先攻克 eligibility 判定和 hard negatives，而不是只改善搜索排序 |
| [TrialMind](https://www.nature.com/articles/s41746-025-01840-7) / [代码](https://github.com/RyanWangZf/TrialMind-SLR) | search、screening、structured extraction、result extraction 与 forest plot；提取值可回看 source text；公开 TrialReviewBench | 聚焦临床试验；人工评价只覆盖部分 review/plot；仓库以 notebooks 为主，完整状态机、跨报告 study lineage、RoB/GRADE 和 living update 不是主要贡献 | 保留 source-linked extraction，但增加 report-study-result 谱系、冻结、gate 和可恢复批处理 |
| [LatteReview](https://arxiv.org/abs/2501.05468) / [代码](https://github.com/PouriaRouzrokh/LatteReview) | provider-agnostic、多 agent、RAG、structured output、本地模型和异步批处理 | 公开 issue 显示 full-text criteria screening 尚待支持；重试计数 bug 可形成无限循环并消耗 API credits；不同 Ollama 模型可能返回空/错误 JSON | 所有调用要有 retry budget、rate limit、cost ceiling、schema validation、checkpoint/resume 和 dead-letter queue；不能把“agent 会互相检查”当成可靠性机制 |
| [Manalyzer](https://arxiv.org/abs/2505.20310) | search/download/parse/screen/extract/analyze/report 的多 agent 流程；729 篇、3 个领域、1 万余数据点；hierarchical extraction、self-proving 和 checker ablation | 复杂 level-3 提取加入 checker 后 hit rate 仍为 3.4%；论文明确承认没有 benchmark 下载、分析和报告；以 relevance/reliability score 代替协议化纳排，且数据集只覆盖 3 个领域 | 使用字段级 evidence anchor + deterministic recomputation；评价完整流水线和 protocol adherence，不以总体“质量分”代替 eligibility reason |
| [EligMeta](https://arxiv.org/abs/2604.02678) | 从 ClinicalTrials.gov 自动发现试验，把 eligibility similarity 引入加权并由确定性代码计算 | 新的 eligibility-weighted estimand 与传统 precision weighting 不同，目前展示规模小；若无充分统计验证，容易把 cohort compatibility 和 sampling precision 混为一谈 | 可把 eligibility 当作适用性/transportability 层，但不默认改写 Meta 权重；先做模拟、校准和 sensitivity analysis |
| [GenAI evidence-synthesis systematic review](https://pubmed.ncbi.nlm.nih.gov/41626912/) | 汇总不同 review tasks 的实证表现 | 报告的中位遗漏/错误仍高：search 中位漏 91%，screening 错排中位 28%，extraction 中位错误 14%，RoB 中位错误 27% | 默认 human-in-the-loop；高风险字段必须双验，无法核验时输出 missing/needs-review 而非猜值 |

## 共性缺点

### 1. 检索“看起来相关”不等于系统综述召回

Agent 常依赖通用搜索、Crossref 或 embedding top-k。它们适合找到若干代表性论文，却不能证明覆盖完整。MetaSyn 显示高 retrieval ceiling 之后仍会在 PI/ECO screening 丢失近一半真阳性；Cochrane 也指出 AI search-strategy design 的适用条件与报告方式仍缺少充分指导。

**解决方向**：数据库特定 query compiler、PRESS/known-item tests、sentinel-study recall、citation chasing、registry-to-publication linkage、停止规则和 search audit；每个数据库保留原始查询、日期、计数和导出哈希。

### 2. Screening 的标签不是简单 relevance score

纳排是协议约束的多条件逻辑。最危险的是“主题相关但 population、design、comparator、outcome、publication type 或时间点不合格”的 hard negative。批量相对评分可能提高区分度，却会使同一研究的决定依赖当前 batch。

**解决方向**：逐条件 verdict（met/not met/unclear/not reported）+ evidence span + calibrated uncertainty；用 deterministic policy engine 汇总，而不是让 LLM直接给 include/exclude；AI 和两位 human reviewer 分轨保存，冲突进入 adjudication。

### 3. Full text、表格、图片和补充材料形成“最后一公里”

题名摘要任务容易评估，真正的数值常在多页表格、图、脚注、补充材料、registry 或 companion report。Manalyzer 的复杂计算字段准确率仍很低；LatteReview 也有公开 full-text screening feature request。

**解决方向**：layout-aware parsing；原页截图/坐标/表格单元格锚点；多报告 study lineage；先抽 reported primitives，再由代码计算 SD、SE、effect size 和 variance；任何 derived value 保存公式与输入 provenance。

### 4. “第二个 agent 检查”不等于独立复核

多个 agent 若使用相同模型、上下文、prompt 和错误来源，错误高度相关。checker 可能只让回答更一致，并不能保证更正确。

**解决方向**：独立 evidence retrieval、不同信息视图、blind extraction、deterministic cross-check、人工仲裁；记录 model/version/prompt/temperature/tool hashes。评价 correlated error，而不只报 majority vote accuracy。

### 5. 统计阶段常只生成脚本或森林图

现有 agent 论文多聚焦 search/screen/extract；模型选择、estimand compatibility、多臂/共享对照、多时间点、cluster trial、零事件、缺失 SD、重复 cohort 和 multiplicity 缺少系统评估。Manalyzer明确承认没有 analysis/report benchmark。

**解决方向**：LLM 只生成分析计划与结构化参数，R toolkit 执行并返回 machine-readable diagnostics；建立 gold analysis cases，比较 effect/SE/tau²/CI/prediction interval 与预期值；强制 data freeze、session info、package citation 和 rerun hash。

### 6. RoB、GRADE 和解释高度依赖上下文

这些任务不是从一段正文选标签。RoB 2 是 result-level；GRADE 是 body-of-evidence-level，涉及 indirectness、imprecision、publication bias 和绝对效应。最新综述仍发现 full-text screening 与 RoB 的特异性和细致判断不稳定。

**解决方向**：工具版本化 domain tree、逐 signaling question evidence anchor、AI suggestion 与 human judgment 分离；certainty 不由一个“质量 agent”直接输出；结论动词自动受到 certainty 与 study design 上限约束。

### 7. 工程可靠性、费用和可恢复性经常不进入论文

公开 issue 已出现无限重试消耗 credits、local provider JSON 不兼容和 quota throttling 问题。模型静默升级还会改变结果。

**解决方向**：幂等 task IDs、有限重试、指数退避、rate limiter、token/cost budget、checkpoint/resume、缓存、schema version、模型快照、失败队列和 dry-run。报告 accuracy 之外的 completion rate、manual minutes、tokens、cost、latency、re-run agreement。

### 8. Reference standard 本身可能有错

已发表综述的 extraction table 或 included-study list 不是绝对真值；人类提取也会出错。只把与 published review 不一致的 agent 输出都算错会误估性能。

**解决方向**：双人专家重新 adjudicate discordant cases；区分 agent error、reference error、ambiguous reporting 和 protocol disagreement；公开 adjudication log，并在分析中做 reference-standard sensitivity analysis。

### 9. 多语言、灰色文献和访问限制导致外推不足

许多 benchmark 主要为英文、PubMed、临床 RCT 或开放全文，难以代表 Embase、中文数据库、学位论文、监管文件、非随机研究和诊断/预后综述。

**解决方向**：至少构建英文 PubMed RCT、中文/非英文、灰色文献、非随机/诊断四个 stress strata；保留 original-language evidence span 与 translation layer；不声称 AI 搜过未授权数据库。

### 10. 报告“符合 PRISMA”常被误解为方法正确

PRISMA 是报告指南，不是自动保证检索完整、提取正确或模型适当。AI 使用还需要说明工具、版本、输入数据、人机交互、验证和限制。

**解决方向**：分开三层：method gate、reporting completeness、AI traceability；输出 PRISMA 2020/PRISMA-S 和 [PRISMA-trAIce](https://pmc.ncbi.nlm.nih.gov/articles/PMC12694947/) 映射，但不把 checklist completion 当质量分。

## 推荐的开发路线

### P0：先让系统可审计、可停止、可恢复

1. 统一 project state schema 和 stage gates。
2. 为所有 LLM 输出定义 JSON Schema；parse failure 进入人工队列。
3. 增加 task ledger：input hash、model、prompt hash、tool version、cost、latency、status、retry count。
4. 增加 API budget/rate limit/checkpoint/resume。
5. 让每个筛选和提取字段保存 page/table/cell/quote evidence anchor。
6. 统计只接受冻结的结构化数据，由 toolkit 执行。

### P1：做一个真正可发表的 benchmark

不要一次声称验证整个医学。先选择 20–30 个公开、可复现、有完整检索式和 extraction data 的 intervention reviews，构建：

- record/report/study/result linkage；
- search candidate corpus + hard negatives；
- dual-adjudicated title/abstract 与 full-text decisions；
- 关键 extraction fields 与 source anchors；
- 10–15 类可确定复算的 Meta analysis cases；
- 人工时间、AI cost、failure/retry 和 reproducibility logs。

主终点建议采用 safety-first 指标：

- retrieval recall 和 included-study recall；
- exclusion false-negative rate；
- field-level exact/tolerance accuracy、unsupported-value rate；
- analysis numerical equivalence；
- critical-error-free review proportion；
- human minutes saved while maintaining prespecified sensitivity；
- rerun agreement across model versions/providers。

### P2：论文一——系统/benchmark 论文

**暂定题目**：*MetaWingman: an auditable human–AI agent for stage-gated systematic reviews and reproducible meta-analysis*。

设计：在同一 benchmark 上比较：

1. 单 LLM prompt；
2. 通用 RAG/deep-research agent；
3. MetaWingman 无 evidence anchor；
4. MetaWingman 完整流程；
5. 人工双审 reference workflow。

做 component ablation：state gates、criteria decomposition、evidence anchor、independent verifier、deterministic calculation、human adjudication。统计报告 paired bootstrap CI，并按 review、study design、文献语言和字段难度分层。

这类论文适合 medical informatics / evidence-synthesis methods 方向；投稿期刊必须在数据和结果出来后依据实际贡献选择，不能现在预设“顶刊”。

### P3：论文二——嵌入真实综述的 SWAT/SWAR

在 3–5 个前瞻性真实综述中，把 MetaWingman 作为辅助 reviewer 随机或交叉评估：

- blinded human-first vs AI-first；
- screening sensitivity、冲突率和 adjudication time；
- extraction critical-error rate 和 time；
- RoB signaling-question agreement；
- 使用者信任、over-reliance 和错误发现率。

预注册 protocol，保存所有版本和失败，按 PRISMA-trAIce 报告 AI 使用。真实 workflow 研究比“用 agent 生成一篇 Meta”更容易形成可信的方法学贡献。

### P4：论文三——特定难点方法论文

从下面任选一个做深，不要同时铺开：

- protocol-aware hard-negative screening 与 calibrated abstention；
- table/figure/supplement 的 evidence-anchored numerical extraction；
- report-to-study-to-result entity resolution；
- human-AI dual extraction 的最优仲裁策略；
- living review 的 drift/retraction/update detection；
- multilingual eligibility screening 与 language-bias control。

## MetaWingman 的差异化定位

MetaWingman 已具备其他 agent 常缺少的基础：阶段 gate、研究谱系、数据 freeze、开放检索和引用核验、61 个可调用分析清单、确定性 R toolkit、GRADE/PRISMA/RoB、AI reviewer loop。下一步应补的是 **benchmark harness 与工程审计层**，而不是再增加 agent 角色数量。

一句话定位：

> MetaWingman is a protocol-bound, evidence-anchored, human-supervised agent that makes every systematic-review decision inspectable and every meta-analytic number reproducible.

## 已核验来源

- Xie A, et al. [Benchmarking LLM Agents on Meta-Analysis Articles from Nature Portfolio](https://arxiv.org/abs/2606.17041). arXiv, 2026. Code and dataset linked above.
- Ha HH, et al. [MedMeta: A Benchmark for LLMs in Synthesizing Meta-Analysis Conclusion from Medical Studies](https://arxiv.org/abs/2605.09661). arXiv, 2026.
- Wang Z, et al. [Accelerating clinical evidence synthesis with large language models](https://www.nature.com/articles/s41746-025-01840-7). *npj Digital Medicine*, 2025.
- Rouzrokh P, Shariatnia M. [LatteReview](https://arxiv.org/abs/2501.05468). arXiv, 2025; [repository](https://github.com/PouriaRouzrokh/LatteReview).
- Xu W, et al. [Manalyzer: End-to-end Automated Meta-analysis with Multi-agent System](https://arxiv.org/abs/2505.20310). arXiv, 2025.
- Zhao Y, et al. [Eligibility-Aware Evidence Synthesis](https://arxiv.org/abs/2604.02678). arXiv, 2026.
- [Generative artificial intelligence use in evidence synthesis: a systematic review](https://pubmed.ncbi.nlm.nih.gov/41626912/).
- [The Use of Generative Artificial Intelligence in Systematic Literature Reviews: A Rapid Review](https://pubmed.ncbi.nlm.nih.gov/42447981/).
- [Cochrane Handbook Chapter 5: Collecting data](https://www.cochrane.org/authors/handbooks-and-manuals/handbook/current/chapter-05).
- [PRISMA-trAIce checklist](https://pmc.ncbi.nlm.nih.gov/articles/PMC12694947/).

预印本结论仍可能在同行评议后改变；正式开发决策应保留版本和检索日期。
