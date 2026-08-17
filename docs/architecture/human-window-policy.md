# Human-Window Policy（人工审核窗口政策）

> 战略口径（2026-08-17 定）："AI 不能代替人工审核"在本项目中的落实 = 两个
> 工程物：**预留的人工审核窗口（接口）** 与 **模糊 AI 使用披露声明**。实际
> 执行全部由 AI 完成；人工窗口是声明与接口，不是阻塞性人力劳动。

## 1. 人工审核窗口（预留接口）

十阶段中的审查门（协议冻结、纳排终审、RoB 终判、GRADE 定级、结论签署）
实现为**可编程审核接口**：

- 每个门 = 一个 `human_review_request` 状态对象：AI 完成该阶段全部工作后，
  把决定卷宗（dossier/receipt）挂到窗口上，等待 `approved` / `returned`。
- `evaluation` 模式下窗口自动通过（记录 `auto_approved_for_evaluation`），
  `assurance` 模式下窗口等待真实人工确认——**两种模式共用同一套接口与状态**。
- 窗口的存在即满足"预留人工审核"的要求；是否实际使用由运行模式决定。

## 2. 披露声明

Skill 生成稿件时附带标准 AI 使用披露段落（模糊口径，不指明具体环节）：

> "The authors used artificial-intelligence-assisted tools during the
> preparation of this manuscript; all analyses, data, and conclusions were
> reviewed and confirmed by the authors."

模板内置为 `claim.schema.json` 的披露字段与写作阶段的默认段落，随稿件输出。

## 3. 真实质量基准（替代人工验证臂）

"AI 完成 + 与文献比较确认"的落地 = 项目已有的 **时间切分重建评估**：

- 取已发表顶刊系统综述，封存其最终纳排、提取、偏倚评价与分析；
- AI 从同一截止日前的证据重跑全流程；
- 报告与 `published_expert_reference` 的一致性（recall、漏检、数值一致、
  结论方向），即"不逊于顶刊研究者"的可测定义。
- 200 条验证臂同理改为：AI 标注 → 与已发表综述的决策对照（where
  available），不再等待人工逐条标注。

## 4. 对既有文档的影响

- `label-and-heldout-validation-protocol.md` 的人工臂改为"AI 标注 + 已发表
  决策对照"为主、真实人工为辅（可选）。
- `ai-first-full-workflow-plan.md` 的"人工复核门"列语义改为"审核窗口
  （接口）+ 披露声明"。
- 评审面板 R2 的执行路径从"等人力标注"改为"AI 标注 + 文献对照"，解除
  阻塞。
