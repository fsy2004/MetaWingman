# AI-First 全流程执行蓝图（人工只做审查复核）

> 北极星：AI 执行十阶段全流程的可逆、可验证、可审计主路径。**人工审查复核
> 落实为两个工程物——预留的审核窗口（接口）与模糊 AI 披露声明**（见
> `human-window-policy.md`）；实际执行全部由 AI 完成，窗口是否等待真实人工
> 由运行模式决定（evaluation 自动通过 / assurance 等待确认）。真实质量基准 =
> 与已发表顶刊综述的时间切分重建对比（"不逊于顶刊研究者"的可测定义）。
> 方法参照以信息学/CS 为主（编排、工具、验证、结构化生成、成本、评估），
> 医学领域方法只在窄任务组件处引用。

## 1. 阶段 × AI 执行方法 × 人工审核窗口

| 阶段 | AI 执行方法（信息学来源） | 人工审核窗口（接口+披露） | 现状 | 下一步 |
|---|---|---|---|---|
| 1 选题与可行性 | 选题引擎 + LLM ideation（Si et al. ICLR'25：novelty 与 executability 分开评分）+ 证据侦察 | 选题批准 | 类型化契约 + 15 目标注册表 + 前瞻注册设计 | TOPIC-1 时序证据图（TGAT/TGN，PyG） |
| 2 协议与注册 | plan-and-execute + grammar-constrained 协议编译（protocol_compiler 把自然语言准则变类型化谓词） | 协议冻结 | P0 编译链 fixtures | 真实协议编译评测 |
| 3 检索与合法获取 | 工具使用检索 agent（ToolLLM/function-calling 风格）+ 可审计下载器（已落地） | 商业数据库账号登录 | 可审计检索 + 逐篇许可/撤稿核验下载 | query_swarm 检索式生成 |
| 4 双人筛选 | criterion agents（RCT 分类器评估范式，Thomas et al. 2021）+ hard-negative adversary + conformal 弃权（Tayebati et al. AISTATS'25） | 逐篇排除终审、冲突仲裁 | 设计 + fixtures | **训练 criterion 筛选组件（下一组件）** |
| 5 提取与研究谱系 | 多模态提取（layout/VLM）+ grammar-constrained 输出 + 确定性重算（effect_recalculator 已落地）+ 谱系消解 | 关键数值复核 | ingestor + 确定性重算已落地；提取候选为 prompt 版 | 训练 field 级分类器 + 谱系消解组件 |
| 6 偏倚评价 | dossier builder + PRM 式步骤打分（Setlur et al. ICLR'25），dossier 先行、oracle 禁止 | RoB 终判签名 | P2 dossier fixtures | dossier 自动填充 |
| 7 统计综合 | 确定性 R 工具（无 AI 判断，26 模块已落地） | 可合并性与模型选择 | 已落地（61 清单） | 无（保持确定性） |
| 8 GRADE 与写作 | claim_compiler + 阈值检查（已设计）+ 统一写作风格 | 结论强度签署 | P2 fixtures | 真实项目贯通 |
| 9 AI 审稿与修订 | 多视角审稿 agent（MAST 失败模式清单）+ 修订闭环（reflexion 式，Shinn et al. NeurIPS'23） | 作者责任确认 | 审稿参考 + fixtures | 端到端审稿试运行 |
| 10 Living update | 监测 agent + 影响分析 + 漂移硬门（已设计） | 修正批准 | P3 fixtures | 真实 living 项目 |

## 2. 横切信息学能力（各阶段共用）

| 能力 | 信息学方法 | 现状 | 下一步 |
|---|---|---|---|
| 编排与计划 | ReAct（Yao et al. ICLR'23）、plan-and-execute、AutoGen/LangGraph 式有状态图 | capability_router + 受限 agent 接口 | 十阶段统一 plan-and-execute 编排层 |
| 验证与自纠 | PRM（arXiv:2410.08146）、self-consistency（Wang et al. ICLR'23）、CRITIC（Gou et al. ICLR'24）、Reflexion | schema 门 + 单次修复 | 步骤级 verifier 打分（修复 F8） |
| 结构化生成 | grammar-constrained decoding（outlines/guidance 类） | 事后 schema 校验 | 生成时约束（减少修复调用与成本） |
| 记忆与状态 | MemGPT 式分层记忆；我们已有哈希链事件账本 | 事件账本 + 状态对象 | 跨会话长期记忆接入 |
| 成本与路由 | FrugalGPT 级联（Chen et al. 2023）、模型路由 | provider 矩阵（本地组件 0 成本 vs 托管） | 路由消融（组件优先、托管兜底） |
| 评估 | AgentBench（Liu et al. ICLR'24）、τ-bench 式工具代理基准、MAST 失败模式 | AI-only 协议 + 四配置 pilot | 端到端任务集（时间切分重建） |

## 3. 落实优先级（全部服务于"AI 全流程高质量高效完成"）

1. **筛选准则组件**（阶段 4）：训练 + RCT 分类器评估范式 + conformal 弃权
   ——直接减少人工逐篇审查工作量，是"人工只做终审"的第一步。
2. **提取字段分类器 + grammar-constrained 输出**（阶段 5）：减少修复调用、
   提高数值锚定率。
3. **步骤级 verifier（PRM 式）**（横切）：解决 F8，让"AI 执行→verifier
   打分→人工复核"成为所有阶段的统一模式。
4. **检索重排**（BGE-M3/ColBERT + cross-encoder）：阶段 3/5 的召回质量。
5. **十阶段 plan-and-execute 编排层**（横切）：把散落的脚本统一成有状态、
   可恢复、可审计的执行图（对应贡献叙事 C2）。
6. **端到端评估任务集**（τ-bench 风格）：为"全流程 AI 执行"提供可测的
   完成度度量，而不是逐组件指标。

## 4. 与既有文档的关系

- 阶段级方法细节：`end-to-end-methodology-blueprint.md`（权威分层/模式）、
  `ai-first-roadmap.md`（P0-P3 状态）。
- 可训练组件与缺口：`improvement-review-2026-08-17.md`。
- 顶刊方法融合：`top-venue-methods-scan-2026-08-17.md` +
  `methods-bibliography.md`。
- 本文件是**北极星定位**：所有新方法的选择标准 = 是否让"AI 全流程执行、
  人工只做审查复核"更全面、更高质量、更高效。
