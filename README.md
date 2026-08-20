<p align="center">
  <img src="plugins/metawingman/.codex-plugin/assets/logo.png" width="112" alt="MetaWingman logo"/>
</p>

<h1 align="center">MetaWingman</h1>

<p align="center"><b>先把问题问对，再把系统综述与 Meta 分析做成可追溯、可复查、可持续更新的研究流程。</b></p>

<p align="center">Question-first, evidence-grounded, human-overseen systematic reviews and meta-analysis.</p>

<!-- readme-metrics:start -->
[![license](https://img.shields.io/badge/license-MIT-15803D)](LICENSE)
[![release](https://img.shields.io/badge/release-v0.1.6-2563EB)](https://github.com/fsy2004/MetaWingman/releases)
![R toolkit](https://img.shields.io/badge/R_modules-26-276DC3)
![manifests](https://img.shields.io/badge/manifests-61-7C3AED)
![schemas](https://img.shields.io/badge/schemas-78-0F766E)
<!-- readme-metrics:end -->

## 这是什么

MetaWingman 是一个可移植的 Agent Skill。它把系统综述从选题到持续更新拆成有输入契约、阶段门禁、来源谱系和人工审核点的工作流。Skill 使用当前宿主模型；确定性统计由随仓库发布的 R 工具箱完成。

它适合系统综述、范围综述、证据图谱、快速综述、诊断/预后/干预 Meta 分析、网络 Meta、比例/患病率、剂量反应、贝叶斯和复杂依赖结构。方法选择服从研究问题、方案和数据结构，不以“工具齐全”为理由运行所有分析。

## Quick start

### Codex plugin

```powershell
codex plugin marketplace add fsy2004/MetaWingman
codex plugin add metawingman@metawingman-local
```

### Clone and install

```powershell
git clone https://github.com/fsy2004/MetaWingman.git
cd MetaWingman
.\install.ps1
```

安装后给出研究问题、当前阶段和已有材料：

```text
$metawingman

研究问题：……
当前阶段：选题 / 方案 / 检索 / 筛选 / 提取 / 评价 / 分析 / 写作 / 更新
已有材料：方案、检索式、RIS/CSV、PDF、提取表或分析数据
期望输出：决策记录、可复现项目、图表、GRADE 表、稿件或审查报告
```

确定性 ZIP 和 SHA-256 校验和见 [GitHub Releases](https://github.com/fsy2004/MetaWingman/releases)。

## 工作流

```mermaid
flowchart LR
    A[问题与可行性] --> B[方案与注册]
    B --> C[检索与合法获取]
    C --> D[双路筛选]
    D --> E[提取与研究谱系]
    E --> F[偏倚风险]
    F --> G[Meta 或 SWiM]
    G --> H[GRADE 与写作]
    H --> I[审查与修订]
    I --> J[持续更新]
```

| 阶段 | Skill 负责 | 人类必须确认 |
|---|---|---|
| 问题与方案 | 问题证书、可行性、新颖性、estimand、资格标准、预设分析 | 临床意义、范围、方案冻结和重大偏离 |
| 检索与获取 | 可复现检索、查询/时间戳/响应留档、开放全文和许可检查 | 商业数据库登录、CAPTCHA、机构权限和最终检索确认 |
| 筛选与提取 | 确定性去重、双路判定、冲突队列、`record → report → study → result` 谱系 | 独立判断、冲突仲裁、关键数值复核 |
| 评价与综合 | 设计匹配的偏倚工具、效应量重算、异质性/敏感性、Meta 或 SWiM | 偏倚域最终判断、效应量/模型选择、是否合并 |
| GRADE 与写作 | 绝对效应、证据确定性草案、PRISMA 报告、数字与引文一致性检查 | 结论强度、临床解释、作者责任和投稿前核验 |
| 持续更新 | 新证据监测、影响分析、版本化变更记录 | 是否改方案、是否重跑、是否发布更新 |

## 可信机制

- **问题证书。** 从临床原语生成可回答的综述问题；方向性可证伪要求只用于适合的假设检验问题。
- **阶段门禁。** 十阶段苏格拉底清单和步骤级验证器在证据不足时允许弃权并进入人工队列。
- **类型化契约。** JSON Schema 约束阶段间交接、研究谱系、评价和重建记录。
- **确定性统计。** 26 个 R 模块从研究级输入重算效应量、异质性和常用扩展分析。
- **来源追踪。** 查询、文件哈希、许可、撤稿状态、提取值、变更提案和审核结果进入审计记录。
- **盲法诊断。** 评分轮次隐藏生成器元数据和自评分；分数用于诊断流程，不作为真值。

## 当前证据边界

仓库处于持续开发阶段。接口测试、弱监督一致性、方法复现和 AI-only pilot 分属不同证据层级；任何一层通过都不等于外部临床有效性。

- 当前可运行部分包括可审计检索、许可核验的获取路径、阶段门禁、确定性效应量重算和 R 适配器。
- 已锁定的重建、训练和 pilot 结果保存在 `docs/architecture/`；README 不复制全部数字，以免结果报告和主页漂移。
- 100 项评价抽检曾触发方法学重标注转向；这类失败信号保留在验证阶梯中，不被“平均分”掩盖。
- 具体综述仍需真实数据库检索、双人判断、来源定位、统计适配和作者签字。

当前单一状态入口：[`docs/architecture/final-status-2026-08-18.md`](docs/architecture/final-status-2026-08-18.md)。方法学约束的训练与评估规则：[`docs/architecture/methodology-grounded-evaluation-contract.md`](docs/architecture/methodology-grounded-evaluation-contract.md)。

## 项目结构

```text
MetaWingman/
├── metawingman/               # canonical Skill source
│   ├── SKILL.md
│   ├── references/
│   ├── schemas/
│   └── scripts/
├── toolkit/R/                 # 确定性 Meta 分析工具箱
├── .agents/skills/            # 生成的 Skill bundle
├── plugins/metawingman/       # 生成的 Codex plugin
├── docs/architecture/         # 方法学、验证、部署和状态报告
├── research/                  # 语料、注册表和计划
├── tests/                     # 控制面、边界和回归测试
└── scripts/                   # 构建、校验、发布与 README 维护
```

`metawingman/` 是唯一源码；`.agents/skills/` 和 `plugins/` 由构建脚本生成。修改 Skill 后必须重建并验证，不能只改生成副本。

## 开发

```powershell
python -m unittest discover -s .\tests -v
python .\metawingman\scripts\test_r_adapters.py .\metawingman
python .\scripts\build_skill_bundle.py
python .\scripts\verify_skill_bundle.py .\.agents\skills\metawingman
python .\scripts\verify_dependency_locks.py
python .\scripts\update_readme.py --check
```

绿色测试证明当前环境中的接口、schema、依赖或回归契约成立；它不验证任何具体综述的科学结论。

## 核心文档

| 主题 | 入口 |
|---|---|
| 当前科学主线：临床问题与综合方法联合设计 | [`clinical-question-synthesis-co-design.md`](docs/architecture/clinical-question-synthesis-co-design.md) |
| 服务器实施计划 | [`2026-08-20-question-synthesis-server-mainline.md`](docs/superpowers/plans/2026-08-20-question-synthesis-server-mainline.md) |
| 服务器选型与初始化 | [`server-mainline-runbook.md`](docs/architecture/server-mainline-runbook.md) |
| 算力与部署配置 | [`compute-and-deployment-budget.md`](docs/architecture/compute-and-deployment-budget.md) |
| 端到端方法学蓝图 | [`end-to-end-methodology-blueprint.md`](docs/architecture/end-to-end-methodology-blueprint.md) |
| 方法学训练与评估契约 | [`methodology-grounded-evaluation-contract.md`](docs/architecture/methodology-grounded-evaluation-contract.md) |
| 人类方法学机器注册表 | [`human-methodology-training-registry.json`](metawingman/references/human-methodology-training-registry.json) |
| README 写作与更新 | [`README_MAINTENANCE.md`](docs/README_MAINTENANCE.md) |
| 隐私、可接受使用与安全 | [`PRIVACY.md`](PRIVACY.md) · [`ACCEPTABLE_USE.md`](ACCEPTABLE_USE.md) · [`SECURITY.md`](SECURITY.md) |

## README 持续更新

动态徽章由 `scripts/update_readme.py` 从 canonical source、R 工具箱和 Git 标签生成。GitHub Actions 在 push、pull request 和每周计划任务中检查漂移；能力、安装方式、验证等级或主线文档变化时，维护者同步复核人工段落。完整范式见 [`docs/README_MAINTENANCE.md`](docs/README_MAINTENANCE.md)。

## English summary

MetaWingman is a portable agent skill for auditable systematic reviews and meta-analysis. It combines question formulation, protocol gates, lawful evidence retrieval, dual screening, typed study lineage, design-matched appraisal, deterministic R analysis, GRADE, writing checks, and living updates. Human reviewers retain responsibility for database access, eligibility decisions, extracted values, risk-of-bias judgments, model choice, interpretation, and publication.

## 贡献与许可

请先搜索现有 Issue/PR，保持改动范围清晰，并运行上面的开发检查。缺陷与建议通过 [GitHub Issues](https://github.com/fsy2004/MetaWingman/issues) 提交。

仓库代码采用 [MIT License](LICENSE)。R 包、数据库、全文和方法遵循各自许可。
