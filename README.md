<p align="center">
  <img src="plugins/metawingman/.codex-plugin/assets/logo.png" width="120" alt="MetaWingman logo"/>
</p>

<h1 align="center">MetaWingman</h1>

<p align="center">
  <b>Systematic reviews and meta-analysis, done with an agent that asks first, verifies each step, and keeps an auditable record.</b>
</p>

<p align="center">
  <a href="https://github.com/fsy2004/MetaWingman/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-MIT-green" alt="License"></a>
  <a href="https://github.com/fsy2004/MetaWingman/releases"><img src="https://img.shields.io/badge/release-v0.1.6-276DC3" alt="Release"></a>
  <a href="metawingman/SKILL.md"><img src="https://img.shields.io/badge/skill-cross--LLM-111827" alt="Skill"></a>
  <a href="toolkit/R"><img src="https://img.shields.io/badge/R_toolkit-26_modules-276DC3" alt="R toolkit"></a>
</p>

---

## What it is

MetaWingman is a portable **skill** for LLM hosts: a self-contained package
of instructions, JSON Schemas, and tooling that turns any LLM host with
skill support into a systematic-review and meta-analysis assistant. It is
host-agnostic — it runs with the model you already use, needs no extra API,
and does not lock you to a vendor.

It covers the full workflow: topic selection, protocol and registration,
literature search, lawful full-text retrieval, deduplication, dual
screening, extraction, risk of bias, quantitative synthesis, GRADE,
manuscript writing, review, and living updates. Every stage must pass a
gate before the next starts.

## Quick start

Three ways to install:

```powershell
# 1. Plugin marketplace (recommended)
codex plugin marketplace add fsy2004/MetaWingman
codex plugin add metawingman@metawingman-local

# 2. Clone + install script
git clone https://github.com/fsy2004/MetaWingman.git
cd MetaWingman
.\install.ps1        # installs to ~\.agents\skills\metawingman
```

Or download the deterministic bundle (ZIP + SHA-256 checksums) from
[GitHub Releases](https://github.com/fsy2004/MetaWingman/releases).

Then invoke the skill with your research question, the current stage, and
the materials you have (protocol, search string, RIS/CSV, PDFs, extraction
tables, or analysis data). Outputs include decision records, reproducible
projects, figures, GRADE tables, manuscripts, and review reports.

## How it works

```mermaid
flowchart LR
    A[Topic & feasibility] --> B[Protocol & registration]
    B --> C[Search & retrieval]
    C --> D[Dual screening]
    D --> E[Extraction & lineage]
    E --> F[Risk of bias]
    F --> G[Meta or SWiM]
    G --> H[GRADE & writing]
    H --> I[AI review & revision]
    I --> J[Living update]
```

Five mechanisms structure the workflow; each has a script or schema and a
recorded smoke/regression run:

- **Review Question Certificate** — a seven-stage derivation (primitives →
  falsifiable hypothesis) with hard/soft gates and a novelty search.
- **Ten-stage Socratic checklists** — ten questions per stage (nine
  mandatory), gated before stage entry.
- **Step-level verifier** — ten appraisal steps with abstention and a
  human-review window.
- **Audit log + meta-update loop** — JSONL events; change proposals carry
  sources and are applied only through the review window with the commit
  recorded.
- **Dual-judge blind scoring** — certificate quality scored blind by two
  judge models.

- **Typed contracts.** Every handoff between stages is a JSON Schema
  2020-12 contract.
- **Deterministic statistics.** A 26-module R toolkit recomputes effect
  sizes and heterogeneity from raw study data.
- **Auditable evidence.** Full texts carry per-record license and
  retraction checks; claims trace back to their source study.
- **Human oversight built in.** Every stage exposes a review checkpoint.

## Trained components

Three 110M BiomedBERT models handle narrow subtasks. All results are
development-set consistency, not external validation.

| Component | Task | Development-set results |
|---|---|---|
| Section-role classifier | assigns each paragraph one of 8 workflow roles | eval macro-F1 0.9995 (weak labels) |
| Evidence retriever | maps fields plus the review title to supporting paragraphs | candidate-set MRR 0.962, P@1 0.933 |
| Appraisal domain classifier | labels an appraisal passage with one of six risk-of-bias domains | rule-label consistency 0.8500; after rubric-grounded relabeling (9,906 records) weighted-F1 0.871 |

Open-corpus retrieval uses BM25 single-stage (MRR 0.2649 on the dev
corpus); the trained retriever is used on provided candidate sets, where it
is strong. See
`docs/architecture/bm25-two-stage-results-2026-08-18.md`.

## Status

The pipeline is under active development; components carry different levels
of evidence. All numbers are development-set consistency against weakly
supervised or rubric-grounded labels, or reproduction of published values —
not externally validated benchmarks.

- **Runnable today:** auditable search, license-checked retrieval,
  deterministic effect-size recomputation, the R toolkit, and the
  stage-gate scripts.
- **Validation ladder (VAL-1 → VAL-3):** reconstruction families licensed
  and promoted (VAL-1); AI-only repeated-run plan and frozen task manual
  (VAL-2a/2b1); 100-item appraisal spot-check kappa 0.311 against
  rubric-grounded judgment, which triggered a relabeling pivot (VAL-2c);
  first AI-only screening pilot on 649 frozen records, gold recall 0.765
  (VAL-3).
- **Reconstruction:** the deterministic R pipeline reproduced a published
  random-effects meta-analysis (Hodgkiss et al., PLoS Med 2023,
  doi:10.1371/journal.pmed.1004082) within declared tolerances in three
  locked runs (pooled MD 2.865 vs 2.9; I² 92.67% vs 93%; k=16 exact).
- **Cross-provider:** GLM glm-5.2 vs DeepSeek on the same blinded set,
  section-role kappa 0.8472 (95% CI 0.8221–0.8722).

## Repository layout

```text
MetaWingman/
├── README.md                  # this file
├── metawingman/               # the skill (canonical source)
│   ├── SKILL.md               # triggers, workflow, research rules
│   ├── references/            # per-stage methodology and domain guides
│   ├── schemas/               # JSON Schema 2020-12 contracts
│   └── scripts/               # search, download, dedup, verification, training, eval
├── toolkit/                   # standalone R meta-analysis toolkit (26 modules)
├── .agents/skills/            # repo skill generated from the canonical source
├── plugins/metawingman/       # skills-only plugin generated from the same source
├── docs/architecture/         # methodology blueprints, roadmap, training reports
├── research/                  # training corpus, registries, plans
├── tests/                     # control-plane, corpus, and boundary tests
└── scripts/                   # packaging, hash verification, release metadata
```

## Development

```powershell
python -m unittest discover -s .\tests -v                      # full test suite
python .\metawingman\scripts\test_r_adapters.py .\metawingman  # R adapters
python .\scripts\build_skill_bundle.py                          # rebuild skill artifacts
python .\scripts\verify_skill_bundle.py .\.agents\skills\metawingman
python .\scripts\verify_dependency_locks.py                     # dependency locks
```

A green test run proves the interfaces and dependencies work in the
current environment; it does not validate any specific review.

## Documentation

| Topic | Link |
|---|---|
| End-to-end methodology blueprint | [docs/architecture/end-to-end-methodology-blueprint.md](docs/architecture/end-to-end-methodology-blueprint.md) |
| AI-first roadmap | [docs/architecture/ai-first-roadmap.md](docs/architecture/ai-first-roadmap.md) |
| AI-only benchmark protocol | [docs/architecture/ai-only-benchmark-protocol.md](docs/architecture/ai-only-benchmark-protocol.md) |
| Training run report | [docs/architecture/training-run-report-2026-08-17.md](docs/architecture/training-run-report-2026-08-17.md) |
| Final status (single entry) | [docs/architecture/final-status-2026-08-18.md](docs/architecture/final-status-2026-08-18.md) |
| Methodology innovation whitepaper | [docs/architecture/innovation-whitepaper-2026-08-18.md](docs/architecture/innovation-whitepaper-2026-08-18.md) |
| Release report | [docs/architecture/release-report-2026-08-18.md](docs/architecture/release-report-2026-08-18.md) |
| Privacy policy | [docs/privacy.md](docs/privacy.md) |
| Terms of service | [docs/terms.md](docs/terms.md) |

## Contributing

Bug reports and pull requests are welcome via
[GitHub issues](https://github.com/fsy2004/MetaWingman/issues). Keep
changes scoped, and run the development checks above before submitting.

## License

The code is [MIT licensed](LICENSE). R packages, databases, full texts,
and methods follow their own licenses.

---

## 中文说明

<p align="center">
  <img src="plugins/metawingman/.codex-plugin/assets/logo.png" width="120" alt="MetaWingman 标志"/>
</p>

<h1 align="center">MetaWingman</h1>

<p align="center">
  <b>系统综述与 Meta 分析，交给一个先提问、逐步验证、并留下可审计记录的智能体。</b>
</p>

<p align="center">
  <a href="https://github.com/fsy2004/MetaWingman/blob/main/LICENSE"><img src="https://img.shields.io/badge/许可-MIT-green" alt="License"></a>
  <a href="https://github.com/fsy2004/MetaWingman/releases"><img src="https://img.shields.io/badge/发布-v0.1.6-276DC3" alt="Release"></a>
  <a href="metawingman/SKILL.md"><img src="https://img.shields.io/badge/skill-跨LLM通用-111827" alt="Skill"></a>
  <a href="toolkit/R"><img src="https://img.shields.io/badge/R_工具箱-26_模块-276DC3" alt="R toolkit"></a>
</p>

---

## 这是什么

MetaWingman 是一个可移植的 **skill**：自带指令、JSON Schema 与工具的独立
包，让任何支持 skill 的 LLM 宿主都能成为系统综述与 Meta 分析助手。它跨
模型通用——用你现有的宿主模型即可运行，无需额外 API，不锁定厂商。

它覆盖完整工作流：选题、方案与注册、文献检索、合法全文获取、去重、双人
筛选、提取、偏倚风险、定量综合、GRADE、论文写作、审稿与持续更新。每一
阶段必须通过关卡，下一阶段才会启动。

## 快速开始

三种安装方式：

```powershell
# 1. 插件市场（推荐）
codex plugin marketplace add fsy2004/MetaWingman
codex plugin add metawingman@metawingman-local

# 2. 克隆 + 安装脚本
git clone https://github.com/fsy2004/MetaWingman.git
cd MetaWingman
.\install.ps1        # 默认安装到 ~\.agents\skills\metawingman
```

也可以从 [GitHub Releases](https://github.com/fsy2004/MetaWingman/releases)
下载确定性打包产物（ZIP + SHA-256 校验和）。

随后调用 skill，给出研究问题、当前阶段与已有材料（协议、检索式、RIS/CSV、
PDF、提取表或分析数据）。输出包括决策记录、可复现项目、图表、GRADE 表、
稿件与审稿报告。

## 工作原理

```mermaid
flowchart LR
    A[选题与可行性] --> B[方案与注册]
    B --> C[检索与获取]
    C --> D[双人筛选]
    D --> E[提取与谱系]
    E --> F[偏倚风险]
    F --> G[Meta 或 SWiM]
    G --> H[GRADE 与写作]
    H --> I[AI 审稿与修订]
    I --> J[持续更新]
```

五个机制组织工作流，各自有脚本或 schema 与已记录的冒烟/回归运行：

- **综述问题证书**——七阶段推导（原语 → 可证伪假设），带硬/软门与新颖性检索。
- **十阶段苏格拉底清单**——每阶段十个问题（九个必答），进入阶段前过门禁。
- **步骤级验证器**——十个评价步骤，带弃权与人工审核窗口。
- **审计日志 + 元更新回路**——JSONL 事件；变更提案带出处，仅经审核窗口应用
  并记录提交号。
- **双法官盲评**——证书质量由两个法官模型盲评。

- **类型化契约。** 阶段之间每个交接点都有 JSON Schema 2020-12 契约。
- **确定性统计。** 26 模块 R 工具箱从原始研究数据重算效应量与异质性。
- **证据可审计。** 全文逐篇核验许可与撤稿；每条结论可追溯到来源研究。
- **内置人工监督。** 每个阶段提供审核检查点。

## 已训练组件

三个 110M BiomedBERT 模型处理窄子任务。所有结果均为开发集一致性，不是
外部验证。

| 组件 | 任务 | 开发集结果 |
|---|---|---|
| 段落角色分类器 | 为每个段落分配 8 种工作流角色之一 | eval macro-F1 0.9995（弱标签） |
| 证据检索器 | 由字段加综述标题映射到支撑段落 | 候选集 MRR 0.962，P@1 0.933 |
| 评价域分类器 | 为评价段落标注六个偏倚域之一 | 规则标签一致性 0.8500；经准则重标注（9,906 条）后 weighted-F1 0.871 |

开集检索使用 BM25 单阶段（开发语料 MRR 0.2649）；训练检索器在给定候选集上
使用（该场景下表现强）。见
`docs/architecture/bm25-two-stage-results-2026-08-18.md`。

## 现状

管线在持续开发中，各组件证据级别不同。所有数字均为开发集上与弱监督/准则
标签的一致性，或对已发表数值的复现——不是外部验证的基准成绩。

- **当前可运行**：可审计检索、经许可核验的全文获取、确定性效应量重算、
  R 工具箱、阶段关卡脚本。
- **验证阶梯（VAL-1 → VAL-3）**：重建家族许可与晋升（VAL-1）；AI-only
  重复运行计划与冻结任务手册（VAL-2a/2b1）；100 项评价抽检对准则判断评分
  kappa 0.311，触发重标注转向（VAL-2c）；首个 AI-only 筛选 pilot（649 条
  冻结记录）黄金召回 0.765（VAL-3）。
- **复现**：确定性 R 管线以三次锁定运行、在声明容差内复现了已发表的随机
  效应 Meta 分析（Hodgkiss 等，PLoS Med 2023，
  doi:10.1371/journal.pmed.1004082；合并 MD 2.865 对 2.9；I² 92.67% 对
  93%；k=16 精确）。
- **跨模型**：GLM glm-5.2 与 DeepSeek 同盲集段落角色 kappa 0.8472（95% CI
  0.8221–0.8722）。

## 项目结构

```text
MetaWingman/
├── README.md                  # 本文件
├── metawingman/               # skill 本体（canonical source）
│   ├── SKILL.md               # 触发规则、工作流与研究规范
│   ├── references/            # 分阶段方法学与领域指南
│   ├── schemas/               # JSON Schema 2020-12 契约
│   └── scripts/               # 检索、下载、去重、校验、训练、评测
├── toolkit/                   # 独立 R Meta 分析工具箱（26 模块）
├── .agents/skills/            # 由 canonical source 生成的 repo skill
├── plugins/metawingman/       # 由同一来源生成的 skills-only plugin
├── docs/architecture/         # 方法学蓝图、路线图、训练报告
├── research/                  # 训练语料、注册表、计划
├── tests/                     # 控制面、语料与边界测试
└── scripts/                   # 打包、哈希核验、发布元数据
```

## 开发

```powershell
python -m unittest discover -s .\tests -v                      # 全量测试
python .\metawingman\scripts\test_r_adapters.py .\metawingman  # R 适配器
python .\scripts\build_skill_bundle.py                          # 重建 skill 产物
python .\scripts\verify_skill_bundle.py .\.agents\skills\metawingman
python .\scripts\verify_dependency_locks.py                     # 依赖锁核验
```

测试通过只证明接口与依赖在当前环境可工作，不验证任何具体综述。

## 文档

| 主题 | 链接 |
|---|---|
| 端到端方法学蓝图 | [docs/architecture/end-to-end-methodology-blueprint.md](docs/architecture/end-to-end-methodology-blueprint.md) |
| AI-first 路线图 | [docs/architecture/ai-first-roadmap.md](docs/architecture/ai-first-roadmap.md) |
| AI-only 评测协议 | [docs/architecture/ai-only-benchmark-protocol.md](docs/architecture/ai-only-benchmark-protocol.md) |
| 训练运行报告 | [docs/architecture/training-run-report-2026-08-17.md](docs/architecture/training-run-report-2026-08-17.md) |
| 终版状态（单一入口） | [docs/architecture/final-status-2026-08-18.md](docs/architecture/final-status-2026-08-18.md) |
| 方法学创新白皮书 | [docs/architecture/innovation-whitepaper-2026-08-18.md](docs/architecture/innovation-whitepaper-2026-08-18.md) |
| 发布报告 | [docs/architecture/release-report-2026-08-18.md](docs/architecture/release-report-2026-08-18.md) |
| 隐私政策 | [docs/privacy.md](docs/privacy.md) |
| 服务条款 | [docs/terms.md](docs/terms.md) |

## 参与贡献

欢迎通过 [GitHub issues](https://github.com/fsy2004/MetaWingman/issues)
提交缺陷报告与拉取请求。改动请保持范围聚焦，提交前运行上述开发检查。

## License

代码采用 [MIT License](LICENSE)。R 包、数据库、全文与方法各自遵循其许可证。
