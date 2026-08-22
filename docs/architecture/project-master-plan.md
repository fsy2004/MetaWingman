# MetaWingman 项目总纲

> 方案流程 · 剩余工作 · 创新点 · 方法 · 算力选型。
> 事实来源：仓库文件、Git 状态、真实测试输出与既有架构文档，不含未经验证的性能或科学有效性声明。
> 历史基线：2026-08-16。当前科学主线与服务器执行权威入口见
> `clinical-question-synthesis-co-design.md` 和
> `../superpowers/plans/2026-08-20-question-synthesis-server-mainline.md`；
> 本文中的旧测试数、分支状态和两组件算力结论不代表当前 live 状态。

## 0. 一句话定位

MetaWingman 是一个**方法学优先、可审计的医学全科证据综合系统**：从"该做什么综述"到"结论有多大把握"，把选题、协议、检索、全文获取、纳排、提取谱系、偏倚评价、Meta/SWiM 综合、GRADE、写作、AI 审稿与 living update 放进同一套带类型约束和 hard gate 的状态工作流。**北极星：AI 执行十阶段全流程的可逆、可验证、可审计主路径，人工只做审查复核**（协议冻结、纳排终审、RoB 终判、GRADE 定级、结论签署、账号授权、不可逆提交）。逐阶段方法矩阵见 `ai-first-full-workflow-plan.md`。

## 1. 方案流程（完整）

### 1.1 双产品线

| 产品 | 说明 |
|---|---|
| 独立 skill | 使用宿主模型与现有工具，**不含任何厂商模型 API client**，先发布 |
| 多 agent runtime | 后续通过 provider-neutral contract 外接商业/国产/机构/本地模型，共享同一套方法学、schema、证据图、verifier、R toolkit 与 benchmark |

两者从单一 canonical source（`metawingman/` + `toolkit/`）生成内容相同的 repo skill 与 plugin skill，聚合哈希防漂移。

### 1.2 十阶段端到端流程

```
选题与可行性 → 协议与注册 → 检索与合法获取 → 双人筛选 → 提取与研究谱系
→ RoB 与数据冻结 → Meta/SWiM 综合 → GRADE 与写作 → AI 审稿与修订 → Living update
```

每阶段留输入、决策者、时间戳、证据锚点、版本与校验结果；前一阶段 hard gate 通过才进入下一阶段。三模式：`assurance`（权威要求的人工独立决策保留）/ `evaluation`（唯一可检验替代人工任务的模式，需预注册标准）/ `rapid`（记录每条捷径、不得声称全面）。

### 1.3 研发路线（P0 → P3，2026-08-20 收束）

- **P0 联合设计契约与封存 benchmark**：临床决策语境、问题框架、综述类型、estimand、综合方法、数据要求和弃权进入同一状态；完成时间/家族隔离和目标泄漏封存。
- **P1 临床问题—综合方法联合搜索**：证据图种子、方法路由、proposal-opposition-judge、外部 verifier、风险自适应 test-time compute 与候选组合输出。
- **P2 全流程科学状态**：持久 Review Case State 贯穿检索、筛选、多模态全文、report-study-result lineage、RoB/GRADE/poolability、R 分析、写作与 AI 审稿。
- **P3 有界学习与 living 验证**：训练问题—方法 ranker、来源支持 verifier、风险—成本 router；开展 AI-only 时间切分重建、消融、重复运行与前瞻选题/living update。

### 1.4 可复现训练范式（首个本地可训练的组件）

```
metadata intake（4,098 篇顶刊优先语料）
→ 保守家族聚类注册表（3,876 家族，自动确认关闭）
→ 医学分层 2,048-record metadata-only 计划（12 专科 × 问题类型 × 设计 × 综合路线）
→ 文章级许可/撤稿核验后下载 OA PDF/XML
→ 证据锚定弱监督 freeze → hard-negative 导出 → 组件 job 冻结
→ 两个 BiomedBERT-base 组件：section-role 分类 + evidence retrieval（tied bi-encoder）
→ 四级 AI-only 消融（general-model-baseline / biomedical-schema / biomedical-routing / full-stack）
```

## 2. 已完成（2026-08-16 历史基线）

- 当时记录为 Python **214/214 OK**、R adapters **61/61**、系统/医学 coverage 审计 valid、依赖锁 valid；使用前必须以当前测试重跑结果为准。
- 医学全科应用契约、领域解析路由、项目迁移、医学分层计划、hard negatives、两个组件训练 job、四级消融、living drift、metadata-only 服务器交接（`local_ready_pending_server_preflight`）全部落地。
- 冻结决策已固化为 `training-freeze-decisions.md`；标签/held-out 验证协议固化为 `label-and-heldout-validation-protocol.md`。
- 分支 `codex/github-beta` 已推送（含本次 2 个文档提交 `f13380e`）；DRAFT PR #1 待评审合并。
- 医学 coverage 的声明上限正确保持 `implemented_not_scientifically_validated`（无越权声明）。

## 3. 剩余工作（按轨道）

### 轨道 A：本地科学验证（无需服务器，优先）
1. 独立标签验证（`label-and-heldout-validation-protocol.md` Part A）：≥200 条跨 ≥20 分层的独立人工重标注，kappa≥0.8 才升 gold；修复 v2 标注里 PMC9533950 的 2 条非精确锚定。
2. 家族 held-out 审计（Part B）：人工逐条确认 281 条候选边 → 重算连通分量 → 开启家族隔离 held-out（当前 0 held-out-ready）。
3. 实现 `audit_review_families.py`（读确认、重算家族、产出 held-out 候选），补 TDD。

### 轨道 B：服务器训练（你另外租 GPU，逐级授权）
按 `server-training-runbook.md` 执行顺序：只读 preflight → 下载 OA 全文 → freeze → 审计 → export → 重建 job → `--validate-only` → 训练 → 组件/端到端 benchmark（匹配成本）。当前仅缺 `server_hardware_unverified` / `cuda_runtime_unverified` / `python_packages_unverified` 三项现场核验，无科学阻塞。

### 轨道 C：AI-only benchmark 与选题引擎（路线图未勾选项）
- `VAL-1` 选首批已发表综述重建家族并做许可审查（4 正式识别、5 个 immutable 材料计划，均未晋升）。
- `VAL-2b` 冻结任务手册/损失权重/发布阈值/配置哈希/停止规则；`VAL-3` 跑 AI-only 消融 pilot。
- `VAL-4b` 真实综述反事实案例；`VAL-5` 在 held-out 家族上校准结论导向采集。
- `TOPIC-1..4` 多学科时间图 → 15-target 注册表晋升泄漏审计案例 → 基线对比 → 前瞻注册随访。
- `VAL-0` 冻结 profile 级能力声明，任何广度/验证声明不得超过 capability matrix。

### 轨道 D：论文与发布
- 论文五图（贡献叙事契约）：架构图 / Top-K 选题重发现 + 假机会对照 / 覆盖地图 / 端到端 stage-loss 瀑布 / 风险-覆盖-成本前沿。
- 公开提交前需真实 benchmark、许可证审查、公开 URL、发布者身份材料；第一版不需要 MCP 服务器。

## 4. 创新点（两项主贡献）

- **C1 临床问题—Meta 方法联合设计**：不是先定题再套统计方法，而是在临床决策语境中联合搜索问题范围、综述类型、estimand、证据可得性、效应量和综合路线；允许缩窄、扩展、拆题、换型、SWiM 或 no-pooling，并保留每次变更的证据依据。
- **C2 像专业研究者一样反思的全流程证据状态**：一个持久、可回放的 Review Case State 贯穿选题到 living update；反思只有在原文锚点、标识符核验、谱系检查或确定性 R/Python 工具观察后才能改变科学状态。
- **训练与评测基础设施**：顶刊已发表综述的时间切分重建、published_reference 标签、协议扰动、首次分歧重放和 AI-only 重复运行，用来验证 C1/C2，不另包装为主创新。
- **借鉴机制**：ReAct、检索增强、树搜索、辩论、动态路由、语义熵、conformal risk control 和多模态解析均是支撑件；对应来源、边界、直接对照和消融见 `clinical-question-synthesis-co-design.md`。

## 5. 方法（技术栈）

- **语言/契约**：Python 3.12 + JSON Schema 2020-12（closed object、`additionalProperties: false`）+ `jsonschema` + 标准库 CLI（无网络、原子写、fail-closed）。
- **统计**：独立 R toolkit 26 模块 + 15 任务适配器 + 61 分析清单（Pairwise/NMA/DTA/比例/剂量反应/Bayesian/多层 RVE/序贯/SWiM；metafor/netmeta/mada/dosresmeta 等）。
- **训练**：`microsoft/BiomedNLP-BiomedBERT-base-uncased-abstract-fulltext`（revision `e1354b7a…`，MIT），section-role 用 `AutoModelForSequenceClassification`+Trainer，检索用 tied encoder + in-batch negatives + cosine；accelerate/datasets/torch/transformers 锁定，seed `20260815`。
- **外接 Agent**：provider-neutral contract（OpenAI 兼容），无密钥配置、schema 门控、单次修复弃权、内容无关遥测；当前批量运行固定 `deepseek-v4-flash` 单 API，Codex 负责主要交互式研发与审查，第二商业 provider 不构成 P0-P3 前置条件。
- **可复现**：哈希链事件账本、逐文件/聚合哈希 bundle、依赖锁、SPDX SBOM + in-toto provenance（未签名声明）。
- **方法学锚定**：系统综述行为由 `human-methodology-training-registry.json` 中的官方手册、原始方法论文和专业流程约束；AI 顶会/顶刊论文与 GitHub 实现只提供工程机制，见 `methods-bibliography.md`。

## 6. 算力选型（完整服务器主线）

- 旧结论“单卡 24 GB”只适用于现有两个 110M 级编码器组件训练。
- 完整研发主线首选 **2 × L40S 48 GB、32–48 vCPU、128–256 GB RAM、4 TB NVMe、1 Gbps 网络**；预算档为 **1 × L40S 48 GB、24–32 vCPU、96–128 GB RAM、2 TB NVMe**。
- NVIDIA 官方规格给出 L40S 单卡 48 GB ECC 且不支持 NVLink，因此双卡用于并行独立 worker，不得写成单个 96 GB 显存模型（[NVIDIA L40S](https://www.nvidia.com/en-us/data-center/l40s/)）。
- RTX 5090 32 GB 可作为经济型开发节点；A100 80 GB 只在实测显示需要更大单卡显存或带宽时升级。完整配置、存储分区和 API 边界见 `compute-and-deployment-budget.md`。

## 7. 声明边界（始终遵守）

当前可声明既有架构、类型化契约、fixture/组件测试、已记录的两个有界编码器训练结果，以及证据账本允许的有界直接结果；实时声明上限由 `../../research/innovation-evidence-ledger-v1.json` 和 `dual-innovation-evidence-and-full-workflow-plan-2026-08-22.md` 控制。不得声称 first / 全自动 / 人类水平 / 超人类 / 全面验证 / 节省人工，除非有直接、适当功效且预先冻结的评价。

## 8. Live-evidence addendum（2026-08-22）

- **病例准入**：训练/开发病例必须来自权威期刊或权威 living-review 平台，能恢复精确历史截止日、published answer 与可审计输入；优先覆盖常见重大健康问题和方法学差异明显的综述类型。罕见或小众病例只能作为补充压力测试，不能单独支撑训练有效性或主科学结论。
- **开发—留出隔离**：Ag-RDT 与 COVID-19 自伤/自杀 living review 用于端到端和采集机制开发；JAMA Pediatrics 儿童睡眠病例仅用于选题机制校准；Lancet 成人重度抑郁症 21 种抗抑郁药 network meta-analysis 作为权威代表性 held-out，不允许按其结果调参。
- **选题直接证据**：时间图候选必须覆盖冻结历史池；候选生成、外部审计、锁定和评分分开。记录 mapping ceiling、known-item recall、假机会率、provider calls、tokens、wall time 与 cost；缺失成本/时间必须写 `null`/`unknown`，不得估算补值。
- **Agent 蒸馏准入**：只蒸馏来源清洁、目标无泄漏、阶段输入/输出/证据锚点/决策理由齐全、锁定后独立评分通过的轨迹。目标知情词表、事后修复、诊断性反事实和失败轨迹可保留作拒答/错误分类训练或审计，不得标为正向 gold demonstration。
- **结果处理**：预注册或锁定结果不佳时保留原结果，先定位覆盖、层级聚合、检索截断、验证器或决策门的机制性失败；改进只在 development case 上完成并重新冻结，再进入新的 held-out family。不得降低阈值、删候选或按已见留出答案挑参。
- **当前直接证据**：JAMA Pediatrics development calibration 暴露并修复了研究设计硬编码、检索截断和层级别名问题；随后冻结的 Lancet 成人抑郁症抗抑郁药 NMA held-out 中，旧完整 control 在 Top-1/Top-3 命中，而 bibliometric、graph-only 和 LLM-order controls 在 Top-3 均未命中。该历史结果早于并不满足当前 record-level domain、显式 study/source-family 和 verified pre-cutoff decision-anchor 构念合同，现只保留为 legacy shared-candidate diagnostic，不是当前控制器阳性证据。
- **2026-08-22 全项目纠偏**：Lancet 结果只比较共享候选集上的排序/门控，未测试 unbiased candidate generation；其 false-opportunity 标签由同一 frozen gates 定义，不能作为独立临床效度；按当前构念重算应 incomplete/abstain。两病例旧 runner 只完成 protocol、metadata/abstract screening/extraction 和 free-text synthesis，不得称十阶段端到端。
- **版本与 split**：Ag-RDT 旧运行把 2022 workbook/2021-08-31 cutoff 与 2021 report/axes 混配，科学评分降为 invalid diagnostic；June-7 自伤/自杀目标绑定 version 1，version 2 是 post-cutoff descendant。两例均为 development，不能支撑 held-out 泛化。
- **统一总案**：两项主创新固定为 TOPIC decision-aware opportunity control 与 REVIEW conclusion-risk-controlled execution。完整 typed landscape、真实 risk × impact action loop、联合十阶段盲态协议、12-family 分层确认集和 agent distillation 证据链见 `dual-innovation-evidence-and-full-workflow-plan-2026-08-22.md`。
