# 项目下一步方案（2026-08-18）

基于已核实证据（训练报告 §12-§14、R2-AI 结果、审计文档）与 2026 年文献线索。
全部排序按"实测短板优先、用户重点优先"。

## 2026 文献线索（本轮核实到的，供后续深读）

| 来源 | 关联点 |
|---|---|
| [Benchmarking LLM Agents on Meta-Analysis Articles from Nature Portfolio](https://arxiv.org/abs/2606.17041)（2026） | 直接对标：meta 分析文章上的 agent 基准——我们的 AI-only 评测可对齐其任务设计 |
| [ICML 2026 Oral: Measuring Agents in Production (MAP)](https://icml.cc/virtual/2026/oral/71172) | 生产指标视角：token/成本/弃权率——我们已有 token 记录，扩展为生产测量 |
| [ICML 2026 Oral: Bad Seeing or Bad Thinking?（含 Structured Verbal Verification）](https://icml.cc/virtual/2026/oral/71095) | 结构化验证替代 LLM 打分——对应 R6 verifier 的验证粒度 |
| [ICLR 2026 Workshop: Lifelong Agents](https://iclr.cc/virtual/2026/events/workshop) | 可学习升级的学术锚点：持续学习、对齐、演进 |
| [icml-iclr-2026-agent-papers 索引（632+457 篇）](https://github.com/jiaxianyan/icml-iclr-2026-agent-papers) | 后续 2026 调研的索引库 |

## P0 —— 实测短板，直接开工

1. **两段式检索**：TF-IDF/BM25 召回 + 12k 模型重排。
   证据：全库 MRR 0.0045 vs TF-IDF 0.220（召回弱）；候选集 0.962（重排强）。
   验收：dev 全库 MRR 超过 TF-IDF 基线（0.220）为最低目标。
2. **GLM 双 provider C0-C3 对比**：glm-5.2（已实测可用）跑同配置四组，与 DeepSeek
   历史对比，产出跨模型一致性实证（对应 model-aware skill alignment 方向）。

## P1 —— 用户指定重点（选题 + 系统评价）

3. **R6 步骤级评价 verifier**：RoB/GRADE 链拆步骤，每步可验证 + 不确定性弃权
   （Setlur PRM 定性思路 + 2026 Structured Verbal Verification 线索）。
4. **选题新颖性审计单**：候选选题输出"既有综述/注册联网比对 + 覆盖缺口 + 时间
   窗口"证据链。ModSearch 已装，落地条件成熟。

## P2 —— 评测与研究层

5. **VAL-2b 手册冻结** → 时间切分重建（复现能力实证，当前最大卡点）。
6. **对标 2606.17041 基准**：评估我们的 AI-only 任务是否覆盖其任务类型。
7. **Lifelong upgrades 机制化**：skill/预设版本化 + 变更日志（已起步）→ 扩展为
   "新文献线索 → 带出处提案 → 更新文件 → 记录"的循环（对应 ICLR 2026 lifelong
   agents 方向）。

## 近期环境事项

- validate CI 已删除（反复失败，用户决定）；sync-gitee 桥保留（推送通道）。
- 桌面插件 dsh-desktop-windowos 已装；guard 已删、原生启动。
- browser-fs 授权建议：最小必要范围，先授权 `C:\Users\fsy\Documents\Codex`；
  授权 = agent 可读写该范围全部文件，敏感目录（凭证/密码）不要纳入。
