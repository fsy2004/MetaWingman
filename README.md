# MetaWingman

> **Skill-driven, decision-object agent for evidence synthesis.** 面向系统评价 / meta 分析的"决策驱动"自主证据合成 agent：把临床流行病学家做系统评价时必须做的**三类判断**——该用哪种设计、该不该 pooling、还差多少证据该停——做成 agent 的**第一等决策对象**，并让 agent 贯穿全流程。

当前状态：**实验性 / 开发中**（decision-object 架构 + 证据链已跑通；详见 [实验评估](#实验评估) 与 [research/](research/) 的版本化结果）。

<!-- readme-metrics:start -->
[![license](https://img.shields.io/badge/license-MIT-15803D)](LICENSE)
[![release](https://img.shields.io/badge/release-v0.1.6-2563EB)](https://github.com/fsy2004/MetaWingman/releases)
![R toolkit](https://img.shields.io/badge/R_modules-26-276DC3)
![manifests](https://img.shields.io/badge/manifests-61-7C3AED)
![schemas](https://img.shields.io/badge/schemas-88-0F766E)
<!-- readme-metrics:end -->

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

> 开发证据（非同行评议）。结果详见 [research/](research/) 的版本化文件；报告以"与真实顶刊系统评价（published_expert_reference）的贴合度"为标准，OOD（与训练/开发不同论文）、严格解析（解析失败计 0，绝不 fallback 到参考）；**黄金基准 v2 = 从论文 methods 正文独立抽取结构信号**（剥离一切数值结果、禁预置 meta 分类；v1 标题式抽取保留为历史）。

| 场景 | 结果 | 证据文件 | 说明 |
|---|---|---|---|
| 黄金基准(v2) | dev 40 / holdout 39 / 多样 196 / **living 35**（OOD,与其余零重叠） | research/method-trace-{gold,holdout,large,living}-signal-v2.jsonl + research/living-review-catalog.json | methods 正文结构信号抽取,outcome-stripped,15 字段 |
| 规则 agent(v2 OOD) | holdout 加权 **0.794**（95% CI 0.685–0.899）；多样 196 **0.780**（0.728–0.828）；living **0.620**（0.499–0.729）；三任务平均 holdout 0.855 / 多样 **0.847**（0.811–0.881） | research/fidelity-v2-*.json + research/bootstrap-v2-ci.json | 校准的七维 estimand 对齐 guard + 保守默认 EVPI |
| **pooling 风险保证(v2,可证)** | 校准:dev 阈值 0.1296,经验误并 0.038（1/26),CP 90% 界 0.142；**OOD 审计:多样 196 中 6/125 误并 ⇒ 经验 0.048,CP 0.083 ≤ α=0.10**；pooling 一致率多样 **0.832**（v1 标量 guard 0.571,**+0.261**） | research/guard-v2-{calibration,ood-risk}.json + fidelity-v2-*.json | 有限样本 (α,δ) 风险控制：接受集内误并风险可控且被审计 |
| **消融(v2,机制归因)** | 去 estimand-first 多样 **−0.063**（CI −0.114,−0.011）/holdout −0.110；去 guard **+0.101**（CI +0.041,+0.165）= 风险保证的贴合度代价（安全-一致收益互换,如实报告）；去 EVPI +0.114 | research/ablation-v2.json | 成本-收益显式化；estimand-first 是真正的判断引擎 |
| **停止层(v2,测量而非假设)** | 结构信号可识别性 **AUC 0.453**（310 例,43 living）≈ 随机 ⇒ 需时间窗式证据累积信号（全系统 acquisition 环已提供,静态基准不能）；受控机制验证:600/600 模拟进程 ±1 周期内达到价值最优停止 | research/evpi-v2-{identifiability,oos-stop}.json + research/evpi-mechanism-tests.json | 识别出信号需求 + 机制受控验证；living 基准(35)发布供下一步 |
| **裸模型多任务对拍(v2)** | 同一提示三问（design/pooled/living):holdout 规则 **0.855** vs 裸 **0.889**；多样 规则 **0.847** vs 裸 **0.871**（CI 重叠）；同输入重跑 0.889→0.915（±0.026）；设计一致率:规则 0.725 vs 裸 0.918；pooling:规则 0.832 vs 裸 0.730 | research/cross-ds-multitask-*-v2.json + research/multitask-compare-v2.json | 诚实结论：**架构增量 = 可证风险保证 + 确定性 + 可验证性 + 跨模型可实现**,而非协议优势 |
| 训练 / 跨模型可实现(v2) | 1.5B+40 条 **0.0**（40/40 解析失败）→ 1.5B+**210 条 0.571**（严格无 fallback;parse_fail 8/39;design 0.513;pairwise n=15 全对,no_pooling 0.050） | research/method-trace-fidelity-lora-honest-v2.json + scripts/evaluate_lora_design_honest.py | 训练=可实现性证据；低于规则（0.780）,20% 输出不可解析 |

> 依据（方法）：真实系统评价 methods 正文结构信号独立抽取（剥离结果、禁预置 meta 分类）；gold 独立于 agent 映射表；贴合度逐维对齐；bootstrap 2000 次 × 5 seed（20260826–20260830）；严格解析、无 fallback；校准分割（guard=dev-40；EVPI=分层随机 50/50）在评估前冻结。
> 深读文献（12 篇全文精读,笔记 `_deliverables/deep-study/notes/`,私有）：MetaSyn / Cochrane RCT classifier / FirstResearch / AI co-scientist / Conformal Abstention / PRM(Setlur) / Test-Time Compute / Semantic Entropy / HELM / LLM-as-judge / AI Scientist v1 / Reflexion / Data Contamination——评测纪律与能力矩阵见稿件 §2。

---

<!-- readme-inventory:start -->
| Repository metric | Current |
|---|---:|
| Python entry points | 88 |
| JSON schemas | 88 |
| R analysis modules | 26 |
| R adapter manifests | 61 |
| R adapters | 15 |
<!-- readme-inventory:end -->

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
