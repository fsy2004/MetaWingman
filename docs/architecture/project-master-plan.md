# MetaWingman 项目总纲

> 方案流程 · 剩余工作 · 创新点 · 方法 · 算力选型。
> 事实来源：仓库文件、Git 状态、真实测试输出与既有架构文档，不含未经验证的性能或科学有效性声明。
> 最后核对：2026-08-16（分支 `codex/github-beta` 已与 origin 同步）。

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

### 1.3 研发路线（P0 → P3）

- **P0 审计内核**：可回放、类型化、可停止。review_state / event_ledger / evidence_anchor / model_registry / tool_contract / abstention / protocol / lineage 等 schema，state_store、schema_guard、method_contract、capability_router、provenance_graph 模块。
- **P1 两个垂直切片**：A) 协议感知的 hard-negative 筛选（protocol_compiler、query_swarm、criterion_agents、hard_negative_adversary、protocol_judge、screening_escalator）；B) 多模态提取 + 确定性重算（document_ingestor、layout_parser、lineage_resolver、global_state_solver、effect_recalculator）。
- **P2 判断工作台**：RoB 2/ROBINS/QUADAS/ROB-ME 证据卷宗、estimand 对齐、poolability 会议、GRADE 卷宗、claim_compiler（把高风险判断变成证据卷宗而非 oracle 标签）。
- **P3 living 系统 + 前瞻评价**：living_monitor、impact_analyzer、amendment_manager、prospective_workflow_logger，以及时间切分重建 + 组件 benchmark + AI-only 重复运行对比。

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

## 2. 已完成（当前基线，本次已实测）

- Python 全量测试 **214/214 OK**；R adapters **61/61**；系统/医学 coverage 审计 valid；依赖锁 valid。
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

## 4. 创新点（四项贡献 + 支撑机制）

- **C1 决策感知的选题机会控制**：时间边界多学科证据图 + 价值/风险冻结门 + 多样性感知 portfolio + 前瞻注册，把"值得做"变成可审计决策。
- **C2 全生命周期系统**：单一体类型化证据状态贯穿选题到 living update，`record → report → study/trial → arm → result → synthesis → certainty → claim` 谱系。
- **C3 结论导向的证据控制**：按"准则层残余遗漏风险 × 下游结论影响"动态分配检索/全文/复核/test-time compute，可返回 `continue/stop_candidate/abstain`，但不得终结生产性综述的停止决策。
- **C4 已发表专家 + 反事实协议 benchmark**：时间切分重建 + published_expert_reference（仅用核验修正版）+ 单准则扰动 + 首次分歧点干预重放，测因果归因。
- **支撑机制**（不单独包装成算法）：证据编译器、反证据锦标赛、多模态全局状态求解器、living graph、时间封存/协议扰动评测。
- **可证伪边界**：复用 ReAct/辩论/路由/语义熵/conformal/多模态解析为基础；每项创新绑定直接对照、消融与失败条件，见 `innovation-and-falsification-matrix.md`。

## 5. 方法（技术栈）

- **语言/契约**：Python 3.12 + JSON Schema 2020-12（closed object、`additionalProperties: false`）+ `jsonschema` + 标准库 CLI（无网络、原子写、fail-closed）。
- **统计**：独立 R toolkit 26 模块 + 15 任务适配器 + 61 分析清单（Pairwise/NMA/DTA/比例/剂量反应/Bayesian/多层 RVE/序贯/SWiM；metafor/netmeta/mada/dosresmeta 等）。
- **训练**：`microsoft/BiomedNLP-BiomedBERT-base-uncased-abstract-fulltext`（revision `e1354b7a…`，MIT），section-role 用 `AutoModelForSequenceClassification`+Trainer，检索用 tied encoder + in-batch negatives + cosine；accelerate/datasets/torch/transformers 锁定，seed `20260815`。
- **外接 Agent**：provider-neutral contract（OpenAI 兼容），无密钥配置、schema 门控、单次修复弃权、内容无关遥测；DeepSeek 仅为第一个 adapter。
- **可复现**：哈希链事件账本、逐文件/聚合哈希 bundle、依赖锁、SPDX SBOM + in-toto provenance（未签名声明）。
- **方法学锚定**：每一步对应的 AI 顶会/顶刊论文与 GitHub 实现见 `methods-bibliography.md`（DPR/SBERT/BiomedBERT/Zhang&Stratos/LLM-as-Judge/HELM/TGAT/TGN/test-time compute 等）。

## 6. 算力选型（对应你的预算 GPU 需求）

- **结论**：本任务微调 110M 的 BERT-base，**单卡 24 GB 即可，无需 5090、无需多卡**。
- **首选**：RTX 4090（24 GB）@ AutoDL；**更省**：RTX 3090（24 GB）。
- 16 GB（A4000/L4）能跑，但 bi-encoder + in-batch negatives 场景余量偏小；L40S/A100 严重过剩。
- 精度耦合：4090（Ada）原生 bf16、吞吐约 3090 的 2×；3090（Ampere）仅 fp16——选 3090 需把冻结的 `precision` 从 `bf16` 改为 `fp16` 再 preflight。
- 参考价（近似、时效敏感，下单前核实 spot 价）：3090 约 $0.07–0.20/hr，4090 约 $0.30–0.70/hr。
- 平台：AutoDL（国内通常最便宜）、Vast.ai、RunPod、Lambda。组件 job 已声明 24 GB GPU 需求，与选型一致。

## 7. 声明边界（始终遵守）

当前只能声明"已实现架构 + 类型化契约 + fixture 测试机制 + 明确验证缺口"。不得声称 first / 全自动 / 人类水平 / 超人类 / 全面验证 / 节省人工，除非有直接、适当功效的对照。训练未运行，无性能结论、无 checkpoint、无科学有效性声明。
