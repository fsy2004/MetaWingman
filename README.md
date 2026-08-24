# MetaWingman

> **Skill-driven, decision-object agent for evidence synthesis.** 面向系统评价 / meta 分析的"决策驱动"自主证据合成 agent：把临床流行病学家做系统评价时必须做的**三类判断**——该用哪种设计、该不该 pooling、还差多少证据该停——做成 agent 的**第一等决策对象**，并让 agent 贯穿全流程。

当前状态：**实验性 / 开发中**（decision-object 架构 + 证据链已跑通；详见 [实验评估](#实验评估) 与 [research/](research/) 的版本化结果）。

---

## Why MetaWingman

系统评价不是"检索后取一个均值"，而是在证据不确定性下做**可负责的判断**。真实临床实践里有三个高代价问题：

1. **设计选择被忽视** —— 常默认用"配对 meta"，而干预比较 / 诊断准确性 / 预后预测 / 患病率 / 暴露-结局性质不同，该用不同设计；**选错设计 → 结论不可靠**。
2. **误导性 pooling** —— 异质、不连通、不同构的证据硬拼成一个 pooled 数，给临床医生"伪精确、实则误导"的答案，比"不够精确"更危险。
3. **无限期更新 / 人工重** —— 系统评价高度依赖人工，更新节奏与"证据是否真的需要更新"脱节。

---

## What you get

- **Agent 架构**：`metawingman/agent/` —— 决策对象（E-R-V：estimand→risk→value）、可证风险控制、信息价值停止、网状搜索、开放思考、全流程编排。
- **Skill**：`metawingman` Skill —— 系统评价 / 证据合成的方法学与门控（PRISMA / GRADE / 风险 / 临床可及性）。
- **方法学**：三类临床判断 = 一等决策对象；方法轨迹学习（从真实系统评价学"过程"、剥离结果）；贴合度基准。
- **可运行脚本**：`scripts/` —— 抽取真实系统评价方法轨迹、构建训练数据、跑设计选择 / 贴合度 / 对照。

---

## Quick start

```bash
# 安装（Windows PowerShell）
./install.ps1

# 设计选择基准（8-strata，决策对象 vs 无条件基线）
python scripts/run_design_selection_benchmark.py

# 真实 meta 贴合度（OOD，严格解析、不 fallback）
python scripts/run_fidelity_real.py --signal research/method-trace-holdout-signal.jsonl \
    --out research/method-trace-fidelity-holdout.json

# 决策对象 vs 裸模型（方法增量）
python scripts/run_bare_llm_fidelity.py
```

测试：

```bash
python -m unittest discover -s tests -p "test_design_selection.py"
python -m unittest discover -s tests -p "test_design_selection_eval.py"
python -m unittest discover -s tests -p "test_design_selection_benchmark.py"
python -m unittest discover -s tests -p "test_agent_workflow.py"
```

---

## How it works：把从业者判断做成一等决策对象

每个决策对象暴露统一接口：**输入**（临床问题 + 证据结构）→ **决策**（类型化）→ **证据**（reason-codes）→ **校验**（失败→abstain/开放）→ **反馈**（下一最有信息的问题）→ **保证**（α 风险或 abstain）。

- **判断 A — 该用哪种设计**（estimand-first）：从临床问题性质与证据结构（比较臂数 / 参照标准 / 预测模型 / 结果度量）先识别 estimand 与识别假设，再定合成路线；异质/不连通 → 叙述综合（SWiM），**不硬 pooling**。
- **判断 B — 该不该 pooling**（可证风险控制）：在 **α 风险保证**下对（人群/对比/结局/时间/效应度量/分析单位/条件集）做 estimand 对齐；任一不可比/未覆盖 → 强制叙述综合/abstain。
- **判断 C — 还差多少证据 / 何时停**（信息价值）：对每个证据缺口算 **EVPI**；最高 EVPI ≤ 信息成本 → 停（把"更新节奏"从时间驱动改为证据价值驱动）。

**全流程（专业团队）**：提案/反对/裁判；PICO → 网状检索 → 筛选 → 偏倚 → estimand → 综合 → pooling 守卫 → GRADE → 结论/更新。每阶段产出**可保存、可复现、可逐环节校验**的中间对象。

**方法轨迹学习**：从**真实顶刊系统评价**学习"方法轨迹"（用了哪种设计/如何处理异质性/是否 pooling/何时停），**剥离一切数值结果**——agent 只能学过程，不能背答案；以"与真实系统评价做法的一致性（agreement, published_expert_reference）"为标准，报告 agreement 而非真理准确率。

---

## 实验评估

> 开发证据（非同行评议）。结果详见 [research/](research/) 的版本化文件；报告以"与真实顶刊系统评价（published_expert_reference）的贴合度"为标准，OOD holdout（与训练/开发不同论文）、严格解析（解析失败计 0，绝不 fallback 到参考）。

| 场景 | 结果 | 证据文件 | 说明 |
|---|---|---|---|
| 规则 agent 基线（8-strata） | dev **0.649**；guard_consistency 0.525（短板） | research/method-trace-fidelity-real.json | 决策对象在真实 meta 上的贴合度 |
| 规则 agent（OOD holdout） | **0.911**（按 profile 分层：exposure 0.15–0.20 / diagnostic 0.225 为短板） | research/method-trace-fidelity-holdout.json | 构成偏 pairwise；需按 profile 分层看 |
| **方法增量**（同模型同数据） | 裸模型 **0.725** vs 决策对象 **0.900**，Δ=**+0.175** | research/bare-llm-holdout.json | 尤其补齐"该不该 pooling"（裸模型在 narrative 全错） |
| 训练 / 跨模型可实现 | 1.5B+40 条 **0.0**（40/40 解析失败）→ 1.5B+**210 条 0.594**（parse_fail 3/40；短板 exposure 0.20→0.95） | research/method-trace-fidelity-real.json + 方法学设计文档 | **"训练量不够"成立**；方法轨迹学习+加数据可行（honest eval：`scripts/run_design_lora_sft.py` + `honest_rerun`，原始结果文件在训练服务器、未入库） |

> 依据（方法）：真实系统评价结构信号独立抽取（剥离线果、禁预置 meta 分类）；gold 独立于 agent 映射表；贴合度逐维对齐。

---

## 目录结构

```
metawingman/
  agent/        决策对象架构（decision_core / poolability_guard / evpi_director /
                graph_search_director / open_deliberation / flow_director）
  training/     方法轨迹学习（method_trace_extractor / normalizer / fidelity / expert_judge / align_dpo）
  benchmark/    设计选择（gold_loader / landscape_builder / cli）
scripts/        CLI 实验与数据构建（run_* / build_*）
research/       版本化证据（gold、signals、fidelity 结果）
tests/          单元测试（decision-object、fidelity、基准 CLI）
docs/           文档
```

---

## 文档与治理

- **完整性 / 使用**：[ACCEPTABLE_USE.md](ACCEPTABLE_USE.md)、[PRIVACY.md](PRIVACY.md)、[SUPPORT.md](SUPPORT.md)。
- **安全**：[SECURITY.md](SECURITY.md)。
- **许可**：[LICENSE](LICENSE)。

---

## 引用

项目处于开发阶段；引用格式一经定稿会将方法学与证据文件一并归档。社区/教程/贡献细则见 [SUPPORT.md](SUPPORT.md) 与 [docs/](docs/)。

---

## 维护提示（对贡献者）

- 本仓库的**定位 / 解释 / 限制 / 科学结论**由人工复核；**机制事实**（版本、组件数、测试数、结果文件）自动维护。
- 实验证据默认写入 `research/`，并注明**日期与版本**（file + receipt sha256）；**任何结果声明必须绑定到该版本化证据文件**。
- 更新 README 的范式见本项目 `docs/README_MAINTENANCE.md` 与 `.agents/skills/readme-maintainer/`（自述文件契约 + skill）。
