# 系统综述与 Meta-analysis Agent：全流程能力、判断瓶颈与创新地图

检索日期：2026-08-13
定位：产品与方法学研究，不是论文选题承诺。结论仅基于已核验的论文、正式方法指南和公开实现；预印本结论按预印本处理。

## 执行结论

Meta-analysis 的数值计算在输入正确、estimand 明确且依赖结构已处理后，确实比检索、纳排、数据谱系和证据评价更容易确定性自动化。真正的瓶颈不是“让 LLM 写一段 `metafor` 代码”，而是形成一条不会悄悄改变研究问题的证据链：

`protocol -> record -> report -> study/trial -> result -> estimand -> appraisal -> synthesis -> claim`

现有系统已经在题录筛选、给定字段抽取和部分端到端演示上取得可用进展，但尚未同时解决以下问题：

1. 从数据库检索到最终结论的逐阶段召回与错误归因；
2. 主题相关但协议不合格的 hard-negative 纳排；
3. 正文、表格、图、补充材料、注册信息和 companion reports 的联合读取；
4. report-study-result 谱系、重复队列、共享对照、多臂和多时间点；
5. RoB、GRADE、可合并性与结论措辞等高判断任务的校准、弃权和人工仲裁；
6. 把每个数值和判断锚定到原始证据，并由确定性代码复算；
7. 模型漂移、成本、失败恢复、安全和版本复现；
8. 在冻结的 AI-only 重复运行中同时验证关键召回、错误、覆盖、稳定性和成本，而不只报告模型准确率。

因此，MetaWingman 最有价值的方向不是再增加几个会互相讨论的 agent，而是建设一个 **protocol-bound evidence adjudication system**：AI 默认完成定位、分解、反证、整理和可验证执行；人处理规范强制的独立决定、弃权、冲突、高风险与最终责任；规则和统计工具负责确定性执行，所有环节都有可回放的 provenance。

## 一、现有证据到底支持到哪一步

### 1. 全领域综合证据仍不支持无人监督

2025 年 GenAI evidence synthesis 系统综述纳入 19 项研究，报告搜索漏检中位数 91%、screening 错误排除中位数 28%、数据提取错误中位数 14%、RoB 错误中位数 27%；多数研究在选择、GenAI 执行和适用性方面为高或不明确偏倚风险。结论是除搜索外若干任务可辅助人工，但证据不支持无人工介入。

更新的 readiness review 只把“human-supervised title/abstract screening”判断为有同行评议证据支持的就绪用途。这个结论比单个产品的高 F1 更适合用作产品边界。

### 2. 端到端系统的高指标不能直接互换

| 系统/研究 | 重要进展 | 需要注意的分母与未覆盖项 |
|---|---|---|
| TrialMind | 100 个 SR、2,220 个研究；search、ranking、source-linked extraction；human-AI pilot 显示节时和性能改善 | screening 是向混入真阳性的 2,000 条候选集排序；extraction ground truth 来自原综述表和 forest plot；没有完整 RoB/GRADE、谱系和真实数据库全覆盖验证 |
| A4SLR | 8 模块，从 search 到 report；2 个 HEOR/HTA use cases；报告很高 screening、extraction 和 RoB 指标 | 仅两个应用场景，外部验证、真实跨设计泛化、错误严重度和完整人工工作量证据仍不足 |
| otto-SR | 在 5 个 screening datasets 上报告高 sensitivity；复现/更新 12 个 Cochrane reviews，并做人工纠错参考标准 | 主文不读取补充表/图；抽取准确率部分由 LLM-as-judge 评估；筛选与抽取 benchmark 数量有限；作者披露产品股权；全自动 RoB/GRADE 不是该研究的已验证贡献 |
| Manalyzer | 729 篇、3 个领域、10,000+ 数据点；hierarchical extraction、source-proving、checker ablation | 复杂 Level-3 计算字段经完整机制后 hit rate 仅 3.4%；论文承认没有下载、分析和报告 benchmark；“相关性/质量评分”不能代替协议化纳排 |
| AutoSynthesis | 从自然语言问题到 random-effects meta-analysis、heterogeneity、RoB 和 PRISMA report；采用 agent + 确定性统计模块 | 目前预印本只展示约 28 项研究、20 余个 quantitative claims 的应用，并非多疾病、多设计的端到端 benchmark；检索到的 expert study recall 仍约为七成，不能据 pooled effect 接近就推断全流程正确 |
| MetaSyn v6 | 422 个 Nature Portfolio source reviews、86 个测试实例、140,585 条 PubMed corpus；把 retrieval、selection、criteria 和 written synthesis 分阶段评价 | ProtoMA trace 中约 20.7% 参考文献损失于检索、40.0% 损失于显式筛选，39.3% 进入最终清单；仅评分 PubMed-linked article，且不覆盖全文提取、RoB、统计复算和 GRADE |
| ROBoto2 | 521 份儿科试验报告、8,954 个 RoB 2 signaling questions；RAG + evidence passages + human correction | 证明“问题级、证据锚定、人机交互”是正确粒度；尚不能据此声称 RoB 可无人自动化 |
| Quicker | 在真实指南数据上尝试 screening、RoB、data extraction 和 GRADE profile | 与 guideline development group 的总体 RoB downgrade agreement 很低（quadratic weighted kappa 0.190），揭示上下文阈值和综合判断难以从表面 rubric 直接恢复 |

### 3. 通用科研 agents 提供了一个重要反证

端到端科学 agent 的瓶颈不是缺少角色名称，而是长程任务中错误累积和验证不足。ScienceAgentBench 用 44 篇同行评议论文构造 102 个真实任务；最佳 agent 在三次机会下独立解决 32.4%，给专家知识后为 34.3%。PaperBench 中最佳被测 agent 的平均复现分数为 21.0%。这些结果支持“先逐任务验证，再宣称端到端”的研发方式。

## 二、全流程能力矩阵

成熟度定义：A 可确定性自动化；B 适合 AI-first 执行并按风险抽样/独立核验；C 由 AI 完成 dossier、规范或高风险要求人作最终判断；D 当前证据不足或需高强度专家仲裁。

| 阶段 | 现有 agent 常见能力 | 真正难点 | 建议成熟度 | MetaWingman 的目标形态 |
|---|---|---|---|---|
| 选题与可行性 | 生成 PICO、关键词、novelty summary | “没人做过”不等于有决策价值；已有 review 的时效、重叠和证据可得性 | C | evidence-gap map + existing-review/registry/retraction audit + 人工 go/no-go |
| 协议 | 自动起草 eligibility、outcomes、analysis plan | target estimand、时间点、最小重要差异、amendment policy 常被后见之明改变 | C | 可执行 protocol schema；版本冻结；任何改动产生 diff、理由和影响范围 |
| 检索设计 | 扩展同义词、生成 Boolean query | 数据库语法、主题词、validated filters、灰色文献、known-item recall | C/B | source-specific query compiler + PRESS-like critique + sentinel recall + 原始导出/hash |
| 自动检索/API | PubMed、Europe PMC、Crossref、registries | licensed databases、账号、CAPTCHA、接口漂移、漏检不可见 | A/B | 公共 API 自动执行；机构数据库采用用户登录/导出 handoff；不冒充已检索 |
| 去重 | DOI/PMID/题名去重 | preprint-to-journal、语言版本、校正/撤稿、同一试验不同报告 | A/B | conservative exact dedupe；fuzzy matches 进入人工队列，不自动删 |
| 题录筛选 | PICO relevance/ranking | hard negatives、摘要缺信息、协议逻辑组合、漏检成本不对称 | B | 逐 criterion verdict + evidence + uncertainty；规则汇总；高召回阈值与强制弃权 |
| 全文筛选 | 长文本问答、理由生成 | 信息分散、否定证据、补充材料、翻译、排除理由首个/主因规则 | B/C | AI-first criterion dossier；assurance 模式保留规范要求的独立人工终判；evaluation 模式研究替代；全文页码锚点 |
| 文献获取 | OA/API 下载、批量上传 | 许可、机构访问、机器人限制、补充材料和版本身份 | A/B | lawful resolver、license/checksum；账号操作隔离；失败原因可追踪 |
| 报告-研究谱系 | 相似度/注册号聚类 | companion、follow-up、重复 cohort、共享样本、多个 registry IDs | C | `record-report-study-arm-result-synthesis-claim` graph；AI 提候选边与反证；高影响冲突才升级 |
| 数据提取 | schema extraction、source snippets | arm/outcome/timepoint 对齐；表/图/脚注；derived values；单位与方向 | B/C | AI 先提取 reported primitives 和 anchors；assurance 模式执行 profile 规定的独立提取；代码复算派生值 |
| RoB | 回答 signaling questions、给 justification | RoB 2 是 result-level；缺失信息、目标效应、多个报告和审评阈值 | C/D | AI 完成证据/反证、signaling answers、规则检查与 proposed judgment；assurance 或高风险节点由人签署/override |
| 可合并性/estimand | 通常直接选模型 | 干预版本、结局定义、时间点、效应方向、条件效应、依赖结构 | D | “poolability conference”：临床、方法和统计三张视图；批准后才产生 analysis set |
| 效应量与统计 | 生成 R/Python、forest/funnel plots | 输入派生、零事件、多臂、cluster、重复测量、缺失 SD、选择性分析 | A/C | LLM 填 typed plan；toolkit 计算；schema checks、unit tests、gold cases、freeze hash |
| 异质性与敏感性 | 自动跑亚组、meta-regression、trim-fill | 分析自由度、生态偏倚、低功效、多重性和后验故事 | C | protocol-bound analysis graph；区分 confirmatory/exploratory；自动标注假设和限制 |
| GRADE/SoF | 根据表格自动给等级 | body-of-evidence、决策阈值、绝对效应、indirectness、publication bias | D | 分 domain evidence dossier；人独立评级；系统检查内部一致性，不替代最终等级 |
| 写作与解释 | 生成摘要/讨论/结论 | 过度概括、因果升级、遗漏限制、effect direction 漂移 | C | claim ledger：每句结论绑定 synthesis、certainty、scope 和允许动词 |
| AI 审稿 | 多 persona 批评、checklist | 同源错误、迎合、LLM judge 偏差、prompt injection、只审文字不审工件 | B/C | 独立 evidence retrieval；deterministic checks；review finding -> artifact diff -> re-verification |
| Living update | alerts、重跑 search/screen | model/database drift、撤稿、协议漂移、结论改变阈值 | B/C | event-sourced update；新证据只更新受影响节点；预设 status/change/retirement rules |

## 三、最难的“人工评价”应拆成六类任务

把所有人工判断丢给一个 `reviewer agent` 会失去可验证性。应按判断对象、证据范围和错误代价拆分。

### 1. 协议解释与纳排

不是问“文章是否相关”，而是对每一条 criterion 回答 `met / not met / unclear / not reported`，并指出证据位置。总 verdict 由版本化规则引擎产生。AI 不确定、证据冲突或只有摘要时必须弃权。

创新点：**protocol compiler + hard-negative adversary**。先把自然语言协议编译成 typed predicates，再由一个反证检索器专门寻找最可能导致排除的证据。评价按 criterion 和 exclusion false-negative，而不是总体 accuracy。

### 2. 报告-研究-结果实体解析

这是多数系统没有正式建模的中间层，却决定是否重复计数、是否混入错误随访、是否共享对照。Cochrane 要求以 study 而非 report 为单位；注册-发表链接长期仍需人工补充。

创新点：**evidence lineage graph**。Agent 只提出实体边和置信证据（作者、中心、样本量、日期、注册号、arms）；确定性约束检测不可能组合；人批准 merge/split。所有下游数据通过 result node 引用，避免复制粘贴漂移。

### 3. 证据提取与派生

LLM 最适合定位候选证据，不应直接生成最终分析值。先保存原始计数、均值、SD、n、HR/CI 等 primitives，再由代码转换；每个 derived value 保存公式、输入节点和数值容差。图表和补充材料使用视觉/布局解析，但必须保留页图和坐标。

创新点：**dual-channel extraction**。文本通道和页面图像通道独立抽取，第三条确定性通道做算术、单位、arm-total 和跨表一致性检查；只有真实异源信息才能降低相关错误。

### 4. RoB 与 GRADE

RoB 2 的 signaling questions 可被结构化，但最终判断依赖目标结果和多个材料；GRADE 又跨越整组研究。Quicker 在真实 guideline 数据上的低 agreement 说明，让模型直接吐出一个 grade 并不可靠。

创新点：**judgment dossier，而非 judgment oracle**。系统输出支持证据、反证、缺失信息、适用规则、相似先例和影响分析；两名人类先独立判断，再看 AI。模型只检查是否漏引证据、理由与 verdict 是否矛盾、override 是否缺 justification。

### 5. 可合并性与解释

统计模型选择之前必须回答：研究是否估计同一个足够接近的效应？这是临床定义、研究设计和统计依赖的交叉判断，不能由 I-squared 阈值代理。

创新点：**estimand alignment matrix**。显式比较 population、intervention/exposure、comparator、outcome definition、time horizon、effect measure、conditioning set 和 unit of analysis；任何关键不对齐都要求人给出 pool、split 或 SWiM 的理由。

### 6. 人机仲裁

“AI 先给答案，人点确认”容易自动化偏见。人机组合在 106 项实验的 meta-analysis 中平均还劣于人或 AI 中较好的一方，尤其决策任务出现损失。认知强制研究则显示，让人先独立作答、再显示 AI，或要求排除替代解释，可以降低过度依赖，但会降低主观偏好。

治理含义：**evidence-before-signature UI**。AI 先提交完整 dossier、最强反证和弃权理由；人在高风险节点签署时必须处理这些证据。当前评测不随机化展示顺序，也不估计人工节省。

## 四、可从其他 LLM/agent 论文迁移的机制

| 外部研究方向 | 可迁移机制 | 在 MetaWingman 中的实现 |
|---|---|---|
| semantic entropy / uncertainty | 多次采样的语义分歧可发现部分 confabulation，但不能发现“稳定地错” | 用作 escalation signal 之一；与 evidence coverage、规则冲突、跨模型分歧联合，不当作真值概率 |
| selective prediction / abstention | 高风险系统应优化 risk-coverage，而非强迫每项作答 | 每个 criterion/field/domain 可单独弃权；预设最大可接受漏排/unsupported-value 风险和模型、证据获取预算 |
| self-correction limits | 无外部反馈的自我纠错可能退化；同模型 checker 共享失败模式 | verifier 必须得到不同证据视图或确定性工具；不把多角色聊天当独立验证 |
| cognitive forcing | 人先作答、延迟显示建议、明确排除替代解释可减少 overreliance | 仅作为最终签署界面的安全设计证据；不纳入当前 AI-only 实验臂或性能声明 |
| scientific-agent benchmarks | 逐任务、可执行结果、成本和污染控制比单一 end-to-end 分数更可信 | 建立 stage-attributed benchmark；每个阶段都有 gold artifact、failure taxonomy 和 contamination split |
| peer-review feedback RCT | AI 更适合改善人类 review 的具体性和可执行性，而非代替最终裁决 | reviewer agent 只反馈“证据不足/措辞模糊/检查未做”，人决定修改；输出须通过 guard tests |
| prompt-injection research | 被评文档是非可信输入，隐藏文字可操纵 LLM reviewer | PDF parser 分离 content/instructions；检测隐藏层、微小/白字和外链指令；文档内容永不获得 tool authority |
| provenance-first RAG | 结论必须追溯到可定位证据，而非仅给一个引用 | field/claim-level anchors；引用 identity verification；不支持的值直接 blocked |
| event sourcing / reproducible agents | 长程流程需要状态、版本、失败恢复和差异审计 | 每个动作保存 input/output hash、model/prompt/tool/schema version、cost、latency、reviewer 和 approval |

## 五、MetaWingman 的创新组合

单独看，检索 agent、RoB agent、R toolkit 或审稿 agent 都已有先例。更有区分度的是把以下机制组合成一套可实证验证的架构。

### 创新 1：Decision provenance graph

不仅记录“引用来自哪”，还记录“为什么这条证据导致这个决定”。图中节点至少包含 protocol criterion、record、report、study、result、raw datum、derived value、RoB answer、synthesis、GRADE domain 和 manuscript claim；边有创建者、版本、证据锚点和审批状态。

### 创新 2：Risk-adaptive human oversight

不是所有字段都双人复核，也不是所有内容都自动化。用预注册 risk score 决定：auto-accept、single verification、dual verification 或 expert adjudication。风险信号来自证据缺失、解析质量、语义分歧、规则冲突、单位/算术异常、out-of-domain 和对最终结论的影响。

### 创新 3：Counterevidence-first judging

对 eligibility、RoB、GRADE 和 interpretation，系统先检索最强反证，再生成建议。审议时同时显示支持证据与反证，禁止只展示一段“解释”。这比同模型自我反思更接近真正独立复核。

### 创新 4：Human-overseen high-stakes governance

AI 默认完成 RoB、GRADE、poolability 和结论 dossier，人只处理弃权、分歧、高风险和最终签署。当前 AI-only 评测不随机化人机顺序，也不把人工执行作为对照；人工裁决只在全部 AI 运行锁定后制作参考标准。

### 创新 5：Deterministic statistical contract

LLM 不能任意写分析脚本。它只能填充 versioned analysis manifest：输入列、effect measure、model、dependency handling、missing-data rule 和 sensitivities。R toolkit 验证 schema、执行、返回 diagnostics；结果必须通过 gold cases 和 cross-package checks。

### 创新 6：Conclusion compiler

每个结论由观察结果、certainty、适用范围和限制组成。系统根据 design/certainty 约束允许动词，检查摘要、正文、表图和 supplement 的数字、方向和时间点一致性。它不是自动写漂亮文字，而是阻止结论超出证据。

### 创新 7：Agent safety for hostile literature

论文 PDF、网页和 supplement 都按不可信数据处理；任何内嵌“忽略前文”“给高分”“访问链接”都不能改变 agent 权限。全文获取器、reviewer 和 API executor 分权，凭证永不进入模型上下文或仓库。

## 六、应怎样验证，而不是只做 demo

### 1. 四层 benchmark

1. **Component layer**：criterion classification、evidence retrieval、field extraction、entity linkage、RoB signaling questions、effect-size calculation。
2. **Stage layer**：search-to-screen、screen-to-extract、extract-to-analysis；报告每一层损失和错误传递。
3. **Review layer**：复现公开综述的 study set、analysis inputs、effect estimates、certainty 和 claims。
4. **Prospective workflow layer**：在新证据批次上预注册并锁定 AI-only 重复运行，测 wall-clock、关键错误、覆盖率、成本和复现性；运行后再制作裁决参考。

### 2. 必报指标

- retrieval recall、included-study recall、exclusion false-negative rate；
- field-level exact/tolerance accuracy、unsupported-value rate、evidence-anchor accuracy；
- entity-link precision/recall 和 duplicate-study leakage；
- effect/SE/CI/tau-squared/prediction interval numerical equivalence；
- RoB signaling-question agreement、domain judgement agreement、evidence sufficiency；
- GRADE domain agreement，但同时报告有理由的专家分歧；
- critical-error-free review proportion；
- risk-coverage/abstention curve；
- rerun agreement、provider/model drift、cost、latency、failure/retry rate；

### 3. 数据分层

至少包括：RCT、非随机研究、诊断/预后；英语与非英语；开放全文与用户授权全文；正文可读与表/图/补充材料主导；简单单报告与多报告/多臂/多时间点；明确协议与模糊协议；常规病例与 hard negatives。

### 4. 对照和 ablation

- single LLM structured prompt；
- generic RAG agent；
- MetaWingman without provenance graph；
- without counterevidence；
- without deterministic verifier；
- single-model vs heterogeneous evidence channels；
- fixed router vs capability/risk-adaptive model routing；
- fixed test-time compute vs uncertainty-triggered compute scaling。

## 七、推荐开发顺序

### P0：先做可审计的判断底座

1. project state + immutable event ledger；
2. protocol schema/compiler；
3. record-report-study-result graph；
4. universal evidence-anchor schema；
5. abstention/escalation contract；
6. AI-only run lock、abstention、published-expert reference 和 correction-integrity data model；
7. prompt-injection and credential isolation boundary。

### P1：攻克两个最有价值的高风险模块

首选组合：

1. **protocol-aware hard-negative screening with calibrated abstention**；
2. **evidence-anchored multimodal extraction with deterministic recomputation**。

这两项既有公开 benchmark 可接续，也直接决定后续 RoB 和 meta 是否有可信输入。

### P2：建立 judgment workbench

先做 RoB 2 signaling-question dossier，再扩展正式 ROBINS-I 或具名草案、ROBINS-E、QUADAS-3、PROBAST+AI；另做 ROB-ME/ROB-MEN 与 RoB NMA 分层适配；随后做 estimand alignment、poolability 和 GRADE domain dossier。每一步都将“找证据”“规则建议”“最终 judgment”分离。

### P3：验证完整闭环

选择少量可公开复现、材料齐全的 reviews，完成从协议到 claim ledger 的端到端重建。只有在 component 和 stage safety floors 通过后，才评价整条流水线的端到端可靠性、覆盖和质量-成本前沿。

### 暂不优先

- 增加更多同模型 reviewer personas；
- 自动生成长篇综述文字；
- 继续扩充统计图形数量；
- 声称无人全自动；
- 在没有 ground truth、运行锁定和完整成本日志的情况下做漂亮 demo。

## 八、一句话差异化

> MetaWingman 让 AI 在协议约束下默认执行系统综述主流程，同时把每个纳排、数值、判断和结论连接成可检查、可弃权、可复算、可更新，并能按规范与风险升级给人的证据链。

## 核验来源

### 系统综述自动化与专用 agents

- Clark J, et al. [Generative artificial intelligence use in evidence synthesis: A systematic review](https://pubmed.ncbi.nlm.nih.gov/41626912/). *Research Synthesis Methods*, 2025.
- [Artificial Intelligence Readiness to Support Evidence Synthesis by Workflow: Findings From a Review of Reviews](https://pubmed.ncbi.nlm.nih.gov/42282102/). 2026.
- Wang Z, et al. [Accelerating clinical evidence synthesis with large language models](https://www.nature.com/articles/s41746-025-01840-7). *npj Digital Medicine*, 2025.
- Lee K, et al. [A4SLR: An Agentic AI-Assisted Systematic Literature Review Framework](https://doi.org/10.1016/j.jval.2025.08.002). *Value in Health*, 2025.
- Cao C, et al. [Automation of Systematic Reviews with Large Language Models](https://ottosr.com/manuscript.pdf). preprint, 2025.
- Xu W, et al. [Manalyzer: End-to-end Automated Meta-analysis with Multi-agent System](https://arxiv.org/abs/2505.20310). preprint, 2025.
- Taherinezhad M, et al. [AutoSynthesis: An agentic system for automated meta-analysis](https://arxiv.org/abs/2607.15247). preprint, 2026.
- Xie A, Su W, Zhou Y, Liu Y, Zhang M, Ai Q. [MetaSyn: A Benchmark for LLM Agents on Meta-Analysis Articles from Nature Portfolio](https://arxiv.org/abs/2606.17041v6). arXiv v6, 2026.
- Hevia A, et al. [ROBoto2](https://aclanthology.org/2025.emnlp-demos.2/). EMNLP System Demonstrations, 2025.
- [Streamlining evidence based clinical recommendations with large language models](https://www.nature.com/articles/s41746-025-02273-y). *npj Digital Medicine*, 2025.

### 方法学与人机协作

- Cochrane. [Chapter 5: Collecting data](https://www.cochrane.org/node/97).
- Cochrane. [Chapter 8: Assessing risk of bias in a randomized trial](https://www.cochrane.org/authors/handbooks-and-manuals/handbook/current/chapter-08).
- Cochrane. [Chapter 14: Completing Summary of Findings tables and grading certainty](https://training.cochrane.org/handbook/current/chapter-14).
- Vaccaro M, et al. [When combinations of humans and AI are useful](https://www.nature.com/articles/s41562-024-02024-1). *Nature Human Behaviour*, 2024.
- Buçinca Z, et al. [To Trust or to Think](https://arxiv.org/abs/2102.09692). CHI, 2021.
- Holst M, et al. [PRISMA-trAIce](https://ai.jmir.org/2025/1/e80247/). *JMIR AI*, 2025. 同行评议的拟议报告清单，不是官方 PRISMA 扩展。

### 通用 LLM/agent 可靠性与科研评估

- Chen Z, et al. [ScienceAgentBench](https://proceedings.iclr.cc/paper_files/paper/2025/hash/f12b4df26344f3be803c06b555252efe-Abstract-Conference.html). ICLR, 2025.
- Starace G, et al. [PaperBench](https://arxiv.org/abs/2504.01848). 2025.
- Farquhar S, et al. [Detecting hallucinations in large language models using semantic entropy](https://www.nature.com/articles/s41586-024-07421-0). *Nature*, 2024.
- Huang J, et al. [Large Language Models Cannot Self-Correct Reasoning Yet](https://openreview.net/forum?id=IkmD3fKBPQ). ICLR, 2024.
- Zhou J, et al. [Can LLM feedback enhance review quality?](https://arxiv.org/abs/2504.09737). ICLR 2025 randomized deployment.
- [Prompt Injection Attacks on LLM Generated Reviews of Scientific Publications](https://arxiv.org/abs/2509.10248). preprint, 2025.

这些来源覆盖了当前最重要的系统级、任务级、方法学和人机协作证据，但不是形式上的穷尽性系统综述。随着模型和预印本更新，数值和结论应保留检索日期与版本。
