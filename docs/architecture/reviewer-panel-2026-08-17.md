# Reviewer Panel Report — MetaWingman 完整项目（2026-08-17）

> 按 academic-paper-reviewer full 模式执行：5 席独立评审 + 编辑综合。评审对象
> 为项目全部声明（README、贡献叙事、训练报告、对抗审查 F1-F9、全流程蓝图、
> 方法扫描）。**只读评审**：本文件是评审输出，不改动项目本体。

## 1. Journal-Fit 评审（EIC）

- **贡献结构**：C1-C4 四项贡献（选题机会控制、全生命周期系统、结论导向证据
  控制、时间封存/反事实基准）的组织方式符合当前顶刊系统论文范式（对标 AI
  Scientist / Virtual Lab / OpenScholar 的结构），结构本身合格。
- **当前证据等级**：可发表的只是"系统 + 组件级评估"（tools/benchmark 型），
  而非方法学贡献：C1 的图未建、C3 的对照未跑、C4 的重建案例因许可被阻。
  README"十阶段全流程可执行"与 `implemented_not_scientifically_validated`
  的声明上限之间存在**措辞落差**——阶段 4-10 大量是 fixture 级类型化契约，
  不是端到端执行证据（证据锚点：
  `metawingman/references/system-capability-matrix.json` 的 validation 层级、
  `ai-first-roadmap.md` 的 checked items）。
- **双产品定位**（skill 为主 + agent 纵深）合理；"AI 全流程、人工只复核"是
  清晰的北极星，但需要端到端演示支撑，否则是愿景不是结果。
- 推荐信号：**Major Revision**（不是 Reject——可复现基础设施（哈希链账本、
  依赖锁、receipt 全哈希）是真实且罕见的质量）。

## 2. Reviewer 1 — 方法学（生物统计 + ML 评估）

- **可复现性（优点，明确承认）**：同 seed 两次检索训练 loss 2.0573/2.0567
  浮点级一致；receipt 含全部 checkpoint 哈希；preflight 双门。这是项目最
  扎实的部分。
- **M1（Major）dev 调参污染**：检索查询表示修订（rev 2026-08-17a）直接由
  dev recall@10=0.049 触发——dev 集不再是干净评估集（项目自己的 F2 已承认）。
  所有 0.983/0.954 是"调优后开发集"数字，不得作为 held-out 证据引用。
- **M2（Major）无区间估计**：全部分量为单 seed 单次运行的点估计；冻结协议
  定义了 paired bootstrap by family，但组件层未执行。
- **M3（Major）无多重比较控制**：七项修复 + 四项配置 + 两组基线在同一 dev
  上迭代，没有预注册的停止规则（pilot 预注册只覆盖 C0-C3 的提示冻结）。
- **M4（Minor）基线完备性**：多数类/TF-IDF 合理；建议补充"未训练
  BiomedBERT 随机头"作为组件训练是否有增益的直接证据，以及候选集检索的
  BM25 全语料对照。
- **M5（Minor）12k 重训未完成**：报告 §11 标"in progress"恰当；完成后需
  重复 M1-M4 的处置。

## 3. Reviewer 2 — 领域（循证医学/Cochrane）

- **先例对标缺口（Major）**：筛选组件的直接先例是 Cochrane RCT 分类器
  （Thomas et al., J Clin Epidemiol 2021，doi:10.1016/j.jclinepi.2020.11.003），
  其"工作量削减 @ 近零漏检率"评估范式是审稿人会问的第一基准。项目尚未与
  之对齐（扫描文档已列入，未实现）。
- **D1（Major）语料偏倚**：Europe PMC OA 限定导致非 OA/embargoed 文献、
  商业数据库、非英文文献系统性缺失；医学全科的"全科"声明需在协议层声明
  该边界（`biomedical-application-contract.md` 已部分覆盖）。
- **D2（Minor）临床价值未证**：两个组件的真实综述项目中的端到端收益（
  时间/工作量/漏检率）没有任何实测——Cochrane 范式要求的不只是 F1。
- **D3（优点）**：逐篇 PMC OA 许可/撤稿核验、家族隔离、held-out 硬零门
  符合循证方法学红线，方向正确。
- **D4（Minor）**：specialty registry 12 专科偏粗；SSc/风湿病学在 broad
  语料有覆盖（rheumatology 查询 1,020 条），但专科术语规范化未验证。

## 4. Reviewer 3 — 跨学科（信息学/agent 系统）

- **P1（优点）**：与 CS 前沿的对齐意识强（PRM、conformal 弃权、plan-and-
  execute、BGE-M3、τ-bench 均已映射到组件），`ai-first-full-workflow-plan.md`
  是合格的架构融合产物。
- **P2（Major）编排层缺失**：十阶段目前是脚本集合，不是有状态 plan-and-
  execute 图；"AI 全流程执行"在信息学意义上的核心机制（任务分解、工具调用
  闭环、失败恢复、跨阶段记忆）尚未实现为统一运行时。
- **P3（Major）评估缺口**：无 τ-bench 式端到端任务集；逐组件指标无法回答
  "全流程完成度/成本/漏检"这一北极星问题。
- **P4（Minor）**：export 在 109k 样本下暴露 O(bucket²) 缩放问题（60+ 分钟），
  大规模语料的可扩展性未达标（改进审查已列第一项）。
- **P5（Minor）**：C3 发现托管模型无视小 verifier（F8）与 PRM 文献一致——
  验证应输出分数门控而非裸预测，方案已写、未实现。

## 5. Devil's Advocate（专用格式）

**最强反论（核心论证挑战）**：
> "AI 完成全流程、人工只做复核"目前是一个**标签未兑现的承诺**。十阶段里
> 只有检索下载、确定性重算、R 综合是真实可执行物；筛选、提取、RoB、GRADE、
> 审稿、living 全部是 fixture 级类型化契约（capability matrix 的 validation
> 层级自证）。把"有 schema 和测试"包装成"全流程可执行"，与项目自己写下的
> `implemented_not_scientifically_validated` 直接冲突。更尖锐地说：两个训练
> 组件的 0.983/0.954 可能主要是**学习弱标签规则本身**（0.983 剥离标题行后
> 0.670；标签由 `_section_role(title)` 规则生成）——训练在多大程度上超越了
> "复述标注规则"，项目自己也没有独立验证臂来回答。

**Issue List**：

- **DA1（CRITICAL）声明-证据落差**：README 定位"十阶段全流程可执行" vs
  capability matrix 的 fixture 级验证。锚点：README"项目现状"节 vs
  `system-capability-matrix.json` validation_counts（fixture_tested 46 /
  not_tested 10 / published_reconstruction_pending 2）。
- **DA2（CRITICAL）核心指标未经独立验证**：无一条 gold 标签；弱标签与模型
  同源（规则生成）。200 条独立验证臂已备但零标注。任何 headline 数字在独立
  验证完成前都应标注"规则一致性"而非"准确率"。
- **DA3（MAJOR）dev 调参链**：查询修订、硬负样本开关、指标重定义全在同一
  dev 上迭代决定（F2 自认），held-out 硬零。开发者既是训练者又是调参者又是
  评估者。
- **DA4（MAJOR）pilot 的对照逻辑**：C0-C3 与训练组件比"谁更接近弱标签"，
  但托管模型更接近的配置（C3 verifier 被无视）恰恰暴露 prompt 工程未被穷尽；
  单 provider、单次重复，成本比较无置信区间。
- **DA5（MINOR）**：export 缩放瓶颈 + 服务器运维戏剧性（12 轮诊断）说明
  工程成熟度距"全流程高效"仍有距离；但这些教训已如实写入 runbook，属加分项。

**被忽视的替代解释**：① 训练组件的优势可能来自微调任务与弱标签规则的
分布匹配，而非语义能力；② 托管模型在更大提示预算下（few-shot 示例）可能
逼近训练组件——pilot 未做 few-shot 对照；③ "零 API 成本"的比较忽略了训练
与推理的 GPU 租金与工程成本。

**缺失的利益相关方视角**：① 真实综述作者的工作量体验（Cochrane 工作量
削减指标完全没有）；② 期刊编辑对 AI 使用披露政策的立场；③ 机构图书馆对
数据库授权的边界。

**观察（非缺陷）**：对抗审查 F1-F9 的存在本身是罕见的自我批判文化；恢复
manifest、强制 IPv4、墙钟截止等运维教训全部入册——工程诚信值得肯定。

---

## 6. 编辑综合决定

### 共识（多席一致）

- 可复现基础设施优秀（EIC/R1/R3 一致）。
- 声明等级高于当前证据（EIC M1 + DA1/DA2 + R1）。
- 独立验证与 held-out 是下一道必须的证据门（R1/R2/DA）。
- 与 Cochrane 先例对标缺失（R2/R3 一致）。

### 分歧仲裁

- "训练组件是否有意义"：R1 认为 0.983 可能复述规则、R3 认为方向正确——
  仲裁：**两者都对**——在独立验证与 held-out 完成前，按"规则一致性"措辞；
  同时保留标题剥离 0.670 作为语义下限证据。
- "是否值得推进全流程"：EIC 与 R3 支持、DA 质疑——仲裁：支持推进，但
  以 τ-bench 式端到端任务集为先决证据，否则是持续堆组件。

### DA CRITICAL 逐条裁决

| 发现 | 裁决 | 处理 |
|---|---|---|
| DA1 声明-证据落差 | **成立** | 阻断 Accept；修订路线 R1 要求降级措辞或补端到端证据 |
| DA2 指标未独立验证 | **成立** | 阻断 Accept；R2：独立验证臂完成前全部数字标"规则一致性" |

### 编辑决定

**Major Revision（大修）**。不是 Reject：基础设施、可复现文化、对抗审查
习惯是真实资产；但北极星声明与当前证据之间的落差必须闭合。

### 修订路线图（优先级排序）

| # | 修订 | 类型 |
|---|---|---|
| R1 | 声明对齐：README"全流程可执行"→ 分阶段证据分级表述（已执行/组件级/设计级），或补两个阶段（筛选+提取）的真实端到端演示 | CRITICAL |
| R2 | 完成 200 条独立人工验证臂；完成前所有指标措辞 = "规则一致性"；held-out 家族审计推进（工具已就绪） | CRITICAL |
| R3 | 筛选组件对标 Cochrane RCT 分类器评估范式（工作量削减 @ 近零漏检） | MAJOR |
| R4 | 组件指标补 paired bootstrap CI + 多 seed 运行；预注册全部调参决策的停止规则 | MAJOR |
| R5 | export 向量化（numpy/ANNOY），目标 <10 分钟 @ 109k 样本 | MAJOR |
| R6 | 落实全流程蓝图优先级 1-3（筛选组件、提取字段分类器、PRM 式 verifier 打分） | MAJOR |
| R7 | pilot 补 few-shot 对照 + 成本-质量区间；C3 改为分数门控 | MINOR |
| R8 | 补"未训练随机头"与 BM25 全语料基线 | MINOR |

> 完成 R1-R4 后可达"系统 + 组件评估"级发表线；C1-C4 方法学贡献需
> VAL-1/2b/3/5 完成后另行评估。
