# Grounding 与可学习升级：期刊/社区方案及本项目落地（2026-08-18）

把「一切结果必须有文献/事实联网确切依据」与「skill/预设随研究更新学习」固化到
DSH（agent 预设）、Codex（AGENTS.md）与 MetaWingman skill，并记录社区/期刊的
对应解法。

## 1. 期刊/社区怎么解决幻觉（grounding）

| 方案 | 出处 | 思路 | 我们的落地 |
|---|---|---|---|
| RARR（Research and Revising） | [Gao et al., ACL 2023, arXiv:2210.08726](https://arxiv.org/abs/2210.08726) | 生成后用检索"研究"每个事实、找到证据则"修订"、找不到则删除——把出处核查做成后处理步骤 | 已写入预设第 9 条：每条声称必须附确切来源，否则标 not verified；skill 红线同款 |
| STORM（维基式长文生成） | [Shih et al., NAACL 2024, arXiv:2402.14207](https://arxiv.org/abs/2402.14207) | 先多视角提问→检索→大纲→逐节带引用写作 | 我们检索/写作阶段的"来源锚定"同构；选题多视角提问可借鉴 |
| 步骤级验证 + 不确定性 | Setlur ICLR'25；Ye ICLR-W'25（mlanthology 已核） | 过程验证器逐步验证、验证器自身带不确定性→弃权 | R6 待办：RoB/GRADE 步骤化 verifier + abstention |
| 本会话实测教训 | glm-5.3「列表有但无权」事件 | 模型列表 ≠ 权限；搜索片段 ≠ 事实 | 预设第 9 条已含"宣称模型可用前必须先实测"；审计文档记录全经过 |

## 2. 期刊/社区怎么解决可学习升级（learnable upgrades）

| 方案 | 出处 | 思路 | 我们的落地 |
|---|---|---|---|
| Voyager 技能库 | [Wang et al., NeurIPS 2023](https://arxiv.org/abs/2305.16291) | 任务中失败→反思→把新技能写入库，后续复用 | skill/预设是版本化活文档：新方法带出处写入，变更记录在案 |
| Harness 工程（含 RetroAgent: From Solving to Evolving） | [RUCAIBox: Agent Systems with Harness Engineering](https://github.com/RUCAIBox/awesome-agent-harness) | 把 agent 的规则/工具/技能作为工程产物持续演进 | 我们的 harness 层 = DSH 预设 + Codex AGENTS.md + skill 文件，三者版本化 |
| Model-aware skill alignment | [arXiv:2605.30723](https://ar5iv.labs.arxiv.org/html/2605.30723) | 同一 skill 在不同模型上需对齐（跨模型能力） | 已接 GLM（glm-5.2 实测可用）→ 下一步 C0-C3 双 provider 对比即对齐实证 |
| 社区实践：skill 自带 references + 版本 | ModSearch 等 DSH 插件的 references/ 结构 | 插件把"配置/输出契约/安全"作为随包文档，随版本更新 | 我们的 references/ 同构；update 原则写入预设第 10 条 |

## 3. 落地清单（已完成）

1. **DSH agent 预设**（`~/.dsh/.agent-presets/research/agent.cordis.yml`）：
   - 新增第 9 条 GROUNDING（iron rule）：事实/数字/引文必须附确切来源（实际抓取的 URL/DOI 或实际读过的文件路径+行号）；无来源→标 not verified；禁止编造；宣称模型可用前必须先实测。
   - 新增第 10 条 LEARNABLE UPGRADES：skill/预设是版本化活文档；新方法带出处更新并记录，不静默偏离规则。
   - 该预设是 DSH 默认（settings.yaml `agent-presets.default: research`），**每次对话自动生效**；子代理继承（dsh-subagent composeFrom parent）。重启/新会话后生效。
   - 选择预设而非新插件的原因：DSH 内置 agent-presets 就是"每会话挂载的 standing scope"机制，persona/systemPrompt 注入、子代理继承、目录化编辑都现成；无需为此再写插件。
2. **Codex 全局**（`~/.codex/AGENTS.md`）：新增「事实依据红线」节（同款五条，含"搜索片段精读前只写定性思路"）。
3. **MetaWingman skill**（`metawingman/SKILL.md` integrity rules）：加"每条事实/数字/引文附确切来源，否则 not verified；宣称模型可用前实测"与"skill/规则是版本化活文档"两条。

## 4. 引用核实状态

RARR（arXiv:2210.08726）、STORM（arXiv:2402.14207）、Voyager（arXiv:2305.16291）均
为本轮搜索到的正式出处（arXiv/ACL 页面）；Setlur/Ye 之前已核；arXiv:2605.30723
经 ar5iv 页面、Harness Engineering 经 GitHub 仓库页——采纳前仍建议按需精读原文，
本文档只取定性思路。
