# 顶刊 AI Skill/Agent 调研与方案映射（2026-08-18）

来源：本轮调研的顶刊/顶会论文与 DSH 生态能力，映射到 MetaWingman 的
skill/agent 设计。重点四块：选题、系统评价、复现能力、跨模型。

> **引用核实状态（2026-08-18 审计）**：Setlur 与 Ye 两篇有 mlnthology 页面可查
> （之前会话已核）。Nature Medicine 与 AI Scientist 两条来自本轮 web 搜索片段，
> **尚未精读原文**——下表中的细节以搜索片段为准，采用前需读原文核对。

## 1. 调研到的论文/系统

| 来源 | 内容 | 关键思路 |
|---|---|---|
| [Nature Medicine, LLM-assisted systematic review of LLMs in clinical medicine](https://www.nature.com/articles/s41591-026-04229-5) | LLM 辅助系统综述（检索→筛选→综合），随机抽 500 篇做纳入筛选人工验证 | **人机混合验证子集**：AI 全程执行 + 随机子集人工对照，报告一致性而非声称替代 |
| [Sakana AI Scientist（Nature 报道）](https://sakana.ai/ai-scientist-nature/) | 从构思到发表全自动：想法生成/排序 → 文献 → 实验 → 写作 → 自动同行评审；顶会评审击败 55% 人类，单篇 ~15 美元 | **全流程自动化 + 自动评审闭环 + 成本核算**；新颖性过滤（与既有文献比对） |
| [Setlur et al., ICLR 2025: Rewarding Progress — Scaling Automated Process Verifiers](https://mlanthology.org/iclr/2025/setlur2025iclr-rewarding/) | 过程验证器（PRM）：步骤级奖励训练验证器，优于仅看结果 | **过程验证**：把"只验最终答案"改为"每步可验证"——对应阶段硬门槛的步骤级检查 |
| [Ye et al., ICLR-W 2025: Uncertainty-Aware Step-Wise Verification](https://mlanthology.org/iclrw/2025/ye2025iclrw-uncertaintyaware/) | 生成式奖励模型的步骤验证 + 不确定性估计 | **验证的不确定性**：验证器自己会错，需附带置信度/弃权——对应我们的 abstention 机制 |
| pi-ai / DSH（本次接入） | 跨 provider 无缝 handoff：同一会话中途换模型，保留 thinking/工具调用/工具结果 | **跨模型能力**的技术底座：provider-neutral 上下文可序列化、可迁移 |

## 2. 映射到 MetaWingman（重点：选题 + 系统评价）

### 选题（当前：时间与决策感知的选题机会引擎）
- 借鉴 AI Scientist 的构思环节：**候选选题 → 新颖性过滤（联网比对既有综述/注册）→ 排序**。我们的引擎已有"反对检索 + 冻结价值/风险门"，补上"新颖性分数的可审计证据链"（每个候选记录：已有哪些综述、覆盖缺口在哪、时间窗口）。
- ModSearch（已装）提供多引擎联网核查，正是选题环节的"新颖性过滤"执行层。
- 差距：候选排序目前偏规则；可选方向 = 用 GLM/DeepSeek 批量生成候选 + 规则门控（成本 < AI Scientist 的 $15/篇量级）。

### 系统评价（当前：RoB/GRADE 阶段 + 弱标签验证组件）
- 借鉴 Nature Med 的**随机子集人工验证**：我们的 R2-AI（200 任务盲样）就是这个范式——保持并制度化：每次模型/流程升级后自动跑一次盲样一致性。
- 借鉴 PRM 的**步骤级验证**：把 RoB/GRADE 拆成步骤链（域判断→信号问题→域风险→总体判断），每步都有可验证的中间产物（R6 待办的 PRM-style verifier 直接落地在此）。
- 借鉴 uncertainty-aware verification：验证器输出附置信度，低置信度转弃权/人工窗口（已有 abstention schema，接线到评价链）。

### 复现能力（在不知道已有综述的情况下完整复现综述）
- 现状：时间切分重建协议（AI-only benchmark 主任务）已设计，VAL-3 因任务手册未冻结而未跑。
- 本轮加强：R2-AI 已证明"盲任务集 + 弱标签键 + 完整执行"的链路可用；下一步把**复现作为流程内建评测**：任意一次 MetaWingman 执行都同时产出"与已发表综述的时间切分一致性"报告（当基准材料存在时）。
- 复现能力的两要素都已具备：选题（时间点前的证据图）+ 检索（Europe PMC 时间过滤 + ModSearch 联网核查）+ 评价（步骤级 verifier）。缺的是端到端跑一次的冻结手册（VAL-2b）。

### 跨模型能力
- 三层现状：
  1. skill 包本身 provider-neutral（任何 host 可加载）——已有；
  2. DSH 的 pi-ai 支持同会话跨 provider handoff——已接入 GLM（settings/cordis.patch 的 zhipu-glm 路由）；
  3. dsh-chat-import（已装）支持 14 种外部 agent 会话导入续跑——跨 host 项目迁移。
- 项目侧：`glm-provider-config.json`（adapter openai_compatible，`GLM_API_KEY` 环境变量），与 DeepSeek 并列，pilot/训练/验证脚本可切换 provider。

## 3. 落地顺序（建议）

1. **R6-PRM 式评价 verifier**：把 RoB/GRADE 链步骤化 + 过程验证器（对应本次调研最直接可执行的一项）；
2. **选题新颖性证据链**：候选选题输出"新颖性审计单"（联网比对 + 缺口 + 时间窗口）；
3. **复现评测内建**：冻结 VAL-2b 手册，跑通第一次时间切分重建；
4. **GLM 双 provider 回归**：pilot 重跑 C0-C3 的 GLM 配置，与 DeepSeek 对比（跨模型一致性即"跨模型能力"的实证）。
