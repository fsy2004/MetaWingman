# MetaWingman

A methodology-first, auditable pipeline for systematic reviews and
meta-analysis. It turns the whole evidence-synthesis workflow — topic
selection, protocol, search, lawful full-text retrieval, screening,
extraction with study lineage, risk of bias, quantitative synthesis,
GRADE, writing, AI review, and living update — into one state machine
with hard gates between stages.

[![Skill](https://img.shields.io/badge/skill-cross--LLM-111827)](metawingman/SKILL.md)
[![R toolkit](https://img.shields.io/badge/R_toolkit-26_modules-276DC3)](toolkit/R)
[![Analysis manifests](https://img.shields.io/badge/manifests-61-0A7BBC)](metawingman/scripts/r/manifests)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

## What it is

MetaWingman is distributed as a **skill**: a self-contained package of
instructions, schemas, and tooling that runs on top of the LLM host you
already use. Skills are portable across LLM hosts by design, and this
one is too — nothing in the package is bound to a specific model vendor
or API. The host model does the work; there is no extra API key,
fine-tuning, or managed service to sign up for.

- **Full workflow, hard gates.** Ten stages from topic to living update;
  a stage cannot start until the previous one passes its gate.
- **Typed contracts.** JSON Schema contracts for every handoff (search,
  screening, extraction, lineage, RoB, GRADE, review).
- **Deterministic statistics.** A 26-module R toolkit recomputes effect
  sizes and heterogeneity from raw study data instead of trusting
  published aggregates.
- **Auditable evidence.** Full texts are downloaded with per-record
  license and retraction checks; claims carry lineage to their source
  studies.
- **Trained verifiers.** Two 110M BiomedBERT components (section-role
  classification, evidence retrieval) that beat hosted-model baselines
  at zero API cost on the dev set.
- **Human review, where it matters.** Review is a reserved checkpoint
  plus an AI-disclosure statement at each gate — an interface, not a
  manual redo of the pipeline. See
  `docs/architecture/human-window-policy.md`.

## Status (evidence, as it stands)

| Level | What exists |
|---|---|
| **Executed** | Auditable search; license/retraction-checked full-text download; deterministic effect-size recomputation; 26-module R toolkit; two trained 110M BiomedBERT components; pre-registered four-config AI-only pilot |
| **Component-level eval** | Dev-set consistency with weak labels (not a gold standard): section-role macro-F1 **0.983** (0.670 without title lines); retrieval MRR **0.954**; trained components beat all hosted-model configs at zero API cost |
| **Designed, not yet end-to-end validated** | Schemas, hard gates, and fixtures for screening, lineage, RoB, GRADE, review, and living update; end-to-end evidence pending time-split reconstruction evaluation |

- **Corpus and data**: 27,046 open-access records, a 12,000-record
  training plan, and 109,028 weak-supervision examples (the 12k retrain
  runs autonomously on the training server).
- Measured numbers, receipt hashes, fixes, and adversarial review:
  `docs/architecture/training-run-report-2026-08-17.md`,
  `docs/architecture/adversarial-review-2026-08-17.md`,
  `docs/architecture/reviewer-panel-2026-08-17.md`.

## Deliverables

Two products share one methodology, schema set, evidence graph,
deterministic verifiers, R toolkit, and benchmark. Packaging,
credentials, data flows, and capability claims stay separate.

1. **Skill (primary, for most users)** — runs with your existing host
   model; no additional model API required. Ships with the 26-module R
   toolkit and 61 analysis manifests.
2. **Multi-agent runtime (later)** — a provider-neutral contract for
   any local or hosted model, aimed at batch automation and evaluation.

## Why a skill instead of another app

Traditional software starts from a tidy extraction table, so it cannot
constrain the earlier research decisions where errors actually happen.
The north star is a reversible, verifiable, auditable **AI-executed main
path across all ten stages**, with quality benchmarked against
top-journal researchers. Human review is implemented as reserved review
windows (interfaces) and a brief AI-disclosure statement; execution is
carried out by the AI end to end. Stage-by-stage AI methods, review
windows, and priorities:
`docs/architecture/ai-first-full-workflow-plan.md`.

```mermaid
flowchart LR
    A[Topic & feasibility] --> B[Protocol & registration]
    B --> C[Search & lawful retrieval]
    C --> D[Dual screening]
    D --> E[Extraction & lineage]
    E --> F[RoB & data freeze]
    F --> G[Meta or SWiM]
    G --> H[GRADE & writing]
    H --> I[AI review & revision]
    I --> J[Living update]
```

## Trained components (first training gate)

Two 110M `BiomedBERT` components cover two narrow subtasks of the
pipeline:

| Component | Task | Measured (dev, weak labels) |
|---|---|---|
| section-role | paragraph → 8 workflow roles (search/eligibility/selection/extraction/appraisal/synthesis/certainty/protocol) | macro-F1 **0.983** (0.670 without title lines; majority-class baseline 0.046) |
| evidence retrieval | fields + review title → supporting paragraph (in-batch + hard negatives) | candidate MRR **0.954** / P@1 0.919 (TF-IDF baseline 0.712 / 0.549) |

Four-config AI-only pilot (C0 raw prompt / C1 +schema / C2 +medical
context / C3 +trained verifier; DeepSeek; 400 calls each): the trained
components beat **every** hosted-model configuration on both tasks at
zero API cost (section-role 0.983 vs 0.967; retrieval MRR 0.954 vs
0.495). More trainable components (screening-criterion classification,
extraction-field classification, lineage resolution) and priorities:
`docs/architecture/improvement-review-2026-08-17.md`.

**Claim boundary.** All numbers above are dev-set consistency against
weak labels: no held-out set, no independent human validation, no
publisher certification. They are not claims of scientific validity.

## Built-in statistics toolkit

`toolkit/` ships 26 R modules covering: effect-size and uncertainty
conversion; pairwise random-effects meta-analysis; heterogeneity,
prediction intervals, subgroup, meta-regression, permutation; funnel,
Egger, trim-and-fill, PET-PEESE; leave-one-out, Baujat, GOSH,
cumulative meta-analysis; network meta-analysis, rankings, league
tables, node splitting, component NMA; bivariate DTA, SROC, HSROC;
prevalence, proportions, means, rates; Bayesian; three-level, RVE;
dose-response; E-value; sequential analysis; plus PRISMA, RoB, and
GRADE/SoF output. Manifests do not license running everything: methods
must follow the protocol, estimand, design, dependency structure, and
current methodological evidence.

## Repository layout

```text
MetaWingman/
├── README.md                  # project front page
├── metawingman/               # installable skill (canonical source, cross-LLM)
│   ├── SKILL.md               # triggers, workflow, research red lines
│   ├── references/            # per-stage methodology, domain packs, capability matrix
│   ├── schemas/               # JSON Schema 2020-12 typed contracts
│   └── scripts/               # search, download, dedup, verification, training, eval CLIs
├── toolkit/                   # standalone R meta-analysis toolkit (26 modules + docs)
├── .agents/skills/            # repo skill generated from the canonical source
├── plugins/metawingman/       # skills-only plugin generated from the same source
├── docs/architecture/         # blueprints, roadmap, training reports, reviews, method maps
├── research/                  # corpus, family registry, training plan, benchmark registry
├── tests/                     # control-plane, corpus, adversarial-boundary tests
└── scripts/                   # deterministic packaging, hash verification, release metadata
```

## Install

```powershell
git clone https://github.com/fsy2004/MetaWingman.git
cd MetaWingman
.\install.ps1        # installs to ~\.agents\skills\metawingman
```

Or add it as a local plugin marketplace:

```powershell
codex plugin marketplace add .
codex plugin add metawingman@metawingman-local
```

Invoke `$metawingman` with your research question, current stage, and
existing materials (protocol, search string, RIS/CSV, PDFs, extraction
tables, or analysis data). Expected outputs: decision records,
reproducible projects, figures, GRADE tables, manuscripts, or review
reports.

The skill format itself is host-agnostic: the same package loads in any
host that supports skills. The Codex plugin above is one packaging of
it.

## Development & verification

```powershell
python -m unittest discover -s .\tests -v                      # full test suite
python .\metawingman\scripts\test_r_adapters.py .\metawingman  # R adapters
python .\scripts\build_skill_bundle.py                          # rebuild both skill artifacts
python .\scripts\verify_skill_bundle.py .\.agents\skills\metawingman
python .\scripts\verify_dependency_locks.py                     # dependency lock check
python .\metawingman\scripts\audit_system_coverage.py           # capability coverage audit
python .\metawingman\scripts\audit_biomedical_coverage.py       # biomedical coverage audit
```

A green run proves the interfaces and dependencies work in the current
environment; it does not prove that a given review meets scientific
completion standards.

## Data & training assets

- Corpus: `research/top-journal-training-corpus-v2.json` (27,046
  Europe PMC OA records, per-record license/retraction-checked
  download) plus the 22-journal stratified original.
- Training plan: `research/training-corpus-plan-biomedical-v3.json`
  (12,000 records; 9,590 train / 2,410 dev; family-separated).
- Run artifacts: 109,028 weak-supervision examples, 30,272 retrieval
  pairs (2,048-record run) plus the 12k pair export, and component
  receipts with all checkpoint hashes, archived in `validation-output/`
  (git-ignored; kept on the server and locally).
- Reproducibility entry points:
  `docs/architecture/server-training-runbook.md` (including crash
  recovery) and `docs/architecture/training-freeze-decisions.md`
  (freeze decisions and revisions).

## Automation & account boundaries

The skill requires no model API account. Open search works anonymously
with Europe PMC, ClinicalTrials.gov, and Crossref; open full-text
download needs `UNPAYWALL_EMAIL`, and PubMed prefers `NCBI_EMAIL`.
Embase, CENTRAL, Web of Science, and Scopus exports still require
institutional logins. Agent model credentials are read only from
environment variables, OS credential stores, or deployment key
services — never from the repository.

## GitHub sync (direct first, Gitee bridge fallback)

Direct access to `github.com` is blocked on some networks. On this
machine, git uses the local proxy (`127.0.0.1:7892`, the same one the
browser uses):

```powershell
git config --global http.https://github.com/.proxy http://127.0.0.1:7892
```

If the proxy is unavailable, sync falls back to
local → Gitee (SSH) → GitHub through a server-side Actions bridge
(`.github/workflows/sync-gitee.yml`: 30-minute cron plus manual
trigger, push auth via the `GH_SYNC_TOKEN` repo secret, force-aligning
`main` and `codex/github-beta`). While the bridge is active, Gitee is
the source of truth and direct GitHub-side edits to those two branches
are overwritten.

One command pushes and verifies SHAs (falls back automatically):

```powershell
pwsh tools/github-sync.ps1
```

## Research directions

Two falsifiable contributions lead: **conclusion-oriented evidence
control** (scientific responsibility graph + state-transition verifier
+ "residual omission risk × downstream conclusion impact") and a
**time- and decision-aware topic opportunity engine** (deadline-aware
evidence graph + opposing search + frozen value/risk gates +
prospective registration). Supporting work: the full-lifecycle system,
multimodal document state, and time-capsule / protocol-perturbation
evaluation. The AI-only benchmark reconstructs published reviews from
time-split inputs and reports consistency with
`published_expert_reference`, not absolute-truth accuracy.

Entry points:

- [End-to-end methodology blueprint](docs/architecture/end-to-end-methodology-blueprint.md)
- [AI-first Architecture Roadmap (P0-P3)](docs/architecture/ai-first-roadmap.md)
- [Top-journal contribution story](docs/architecture/top-journal-contribution-story.md)
- [Innovation and falsification matrix](docs/architecture/innovation-and-falsification-matrix.md)
- [AI-only benchmark protocol](docs/architecture/ai-only-benchmark-protocol.md) and [pre-registered component pilot](docs/architecture/ai-only-pilot-preregistration.md)
- [Training run report](docs/architecture/training-run-report-2026-08-17.md) and [adversarial review](docs/architecture/adversarial-review-2026-08-17.md)
- [Full-project improvement review](docs/architecture/improvement-review-2026-08-17.md)
- [Methodology bibliography and GitHub references](docs/architecture/methods-bibliography.md)
- [Server training runbook](docs/architecture/server-training-runbook.md)
- [Compute and deployment budget](docs/architecture/compute-and-deployment-budget.md)
- [Skill and plugin release plan](docs/architecture/distribution-and-skill-release.md)

## License

The code in this repository is [MIT licensed](LICENSE). R packages,
databases, full texts, and methods follow their own licenses and
citation requirements.

---

## 中文说明

# MetaWingman

方法学优先、可审计的系统综述与 Meta 分析全流程管线：把选题、协议、检索、
合法全文获取、纳排、带研究谱系的提取、偏倚评价、定量综合、GRADE、写作、
AI 审稿与 living update 装进同一条带硬门槛的状态工作流。

[![Skill](https://img.shields.io/badge/skill-跨LLM通用-111827)](metawingman/SKILL.md)
[![R toolkit](https://img.shields.io/badge/R_工具箱-26_模块-276DC3)](toolkit/R)
[![Analysis manifests](https://img.shields.io/badge/分析清单-61-0A7BBC)](metawingman/scripts/r/manifests)
[![License](https://img.shields.io/badge/许可-MIT-green)](LICENSE)

## 这是什么

MetaWingman 以 **skill** 形式分发：一个自带说明、schema 与工具的资源包，
跑在你已有的 LLM 宿主之上。skill 天然跨 LLM 通用，这个项目同样如此——包里
没有任何内容绑定特定模型厂商或 API。宿主模型负责执行，无需额外 API key、
微调或托管服务。

- **全流程 + 硬门槛**：选题到 living update 十个阶段，前一阶段不过关，
  后一阶段不启动。
- **类型化契约**：每个交接点（检索、筛选、提取、谱系、RoB、GRADE、审稿）
  都有 JSON Schema 契约。
- **确定性统计**：26 模块 R 工具箱从原始研究数据重算效应量与异质性，
  不直接采信已发表的汇总值。
- **证据可审计**：全文逐篇核验许可与撤稿后下载；每条结论带谱系，可追溯
  到来源研究。
- **训练过的验证器**：两个 110M BiomedBERT 组件（section-role 分类、证据
  检索），在 dev 集上零 API 成本超过托管模型基线。
- **人工审核在关键处**：每个门槛预留审核窗口（接口）与简短 AI 披露声明，
  是接口而非把管线人工重做一遍。见 `docs/architecture/human-window-policy.md`。

## 项目现状（三级证据，如实）

| 级别 | 内容 |
|---|---|
| **① 已执行** | 可审计检索；逐篇许可/撤稿核验的全文下载；确定性效应量重算；26 模块 R 工具箱；两个 110M BiomedBERT 组件训练；预注册四配置 AI-only pilot |
| **② 组件级评估** | dev 集与弱标签的规则一致性（非金标准）：section-role macro-F1 **0.983**（剥离标题行 0.670）；检索 MRR **0.954**；训练组件以零 API 成本超过全部托管模型配置 |
| **③ 设计级，尚未端到端验证** | 筛选、谱系、RoB、GRADE、审稿、living update 的 schema、硬门槛与 fixtures 就绪，端到端证据待时间切分重建评估产出 |

- **语料与数据**：27,046 条 OA 元数据语料、12,000 条训练计划、109,028 条
  弱监督样本（12k 重训在训练服务器上自主推进）。
- 实测数字、receipt 哈希、缺陷修复与对抗审查见
  `docs/architecture/training-run-report-2026-08-17.md`、
  `docs/architecture/adversarial-review-2026-08-17.md`、
  `docs/architecture/reviewer-panel-2026-08-17.md`。

## 交付物

两条产品线共享同一套方法学、schema、证据图、确定性验证器、R 工具箱与
benchmark；打包、凭证、数据流与能力声明分开。

1. **Skill（主入口，多数用户）**：用你现有的宿主模型运行，不要求额外模型
   API；内置 26 个 R 统计模块与 61 个分析清单。
2. **多 agent runtime（后续）**：provider-neutral contract，可接任意厂商或
   本地模型，面向批量自动化与评估。

## 为什么做成 skill，而不是另一个软件

传统软件从"已经整理好的分析表"开始，约束不到此前最容易出错的科研决策。
北极星是一条可逆、可验证、可审计的 **AI 执行十阶段主路径**，完成质量对标
顶刊研究者；人工审查复核落实为预留的审核窗口（接口）与简短 AI 披露声明，
执行由 AI 端到端完成。逐阶段的 AI 执行方法、审核窗口与优先级见
[AI-First 全流程执行蓝图](docs/architecture/ai-first-full-workflow-plan.md)。

```mermaid
flowchart LR
    A[选题与可行性] --> B[协议与注册]
    B --> C[检索与合法获取]
    C --> D[双人筛选]
    D --> E[提取与研究谱系]
    E --> F[RoB 与数据冻结]
    F --> G[Meta 或 SWiM]
    G --> H[GRADE 与写作]
    H --> I[AI 审稿与修订]
    I --> J[Living update]
```

## 已训练的领域组件（训练门第一阶段）

两个 110M `BiomedBERT` 组件覆盖全流程中的两个窄子任务：

| 组件 | 任务 | 实测（dev，弱监督标签） |
|---|---|---|
| section-role 分类 | 段落 → 8 类工作流角色（search/eligibility/selection/extraction/appraisal/synthesis/certainty/protocol） | macro-F1 **0.983**（剥离标题行后 0.670；多数类基线 0.046） |
| 证据检索 | 字段 + 综述标题 → 支撑段落（in-batch + hard negatives） | 候选集 MRR **0.954** / P@1 0.919（TF-IDF 基线 0.712 / 0.549） |

四配置 AI-only pilot（C0 裸提示 / C1 +schema / C2 +医学上下文 / C3 +训练
verifier；DeepSeek；各 400 调用）：训练组件在两项任务上**全部超过托管模型
配置**，零 API 成本（section-role 0.983 vs 0.967；检索 MRR 0.954 vs 0.495）。
更多可训练组件（筛选准则分类、提取字段分类、谱系消解）与优先级见
`docs/architecture/improvement-review-2026-08-17.md`。

**声明边界**：以上均为开发集上对弱标签的一致性；无 held-out、标签未经独立
人工验证、无 publisher 认证——不构成科学有效性声明。

## 内置统计工具箱

`toolkit/` 提供 26 个 R 模块：效应量与不确定性转换；Pairwise random-effects
Meta；异质性/预测区间/亚组/Meta 回归/permutation；funnel/Egger/trim-and-fill/
PET-PEESE；leave-one-out/Baujat/GOSH/累计 Meta；Network Meta/排名/league
table/node splitting/component NMA；DTA 双变量/SROC/HSROC；患病率/比例/均值/
发生率；Bayesian；三层/RVE；剂量反应；E-value；序贯分析；以及 PRISMA、RoB、
GRADE/SoF 输出。清单数量不等于推荐全自动跑完——方法必须服从协议、estimand、
设计、依赖结构与最新方法学证据。

## 项目结构

```text
MetaWingman/
├── README.md                  # 项目首页
├── metawingman/               # 可安装的 skill（canonical source，跨 LLM 通用）
│   ├── SKILL.md               # 触发规则、工作流和科研红线
│   ├── references/            # 按阶段加载的方法学说明、领域包、能力矩阵
│   ├── schemas/               # JSON Schema 2020-12 类型化契约
│   └── scripts/               # 检索、下载、去重、校验、训练、评测 CLI
├── toolkit/                   # 独立 R Meta 分析工具箱（26 模块 + 文档）
├── .agents/skills/            # 从 canonical source 生成的 repo skill
├── plugins/metawingman/       # 同一来源生成的 skills-only plugin
├── docs/architecture/         # 方法学蓝图、路线图、训练报告、审查与文献映射
├── research/                  # 语料、家族注册表、训练计划、基准候选注册表
├── tests/                     # 控制面、训练语料、对抗边界等全套测试
└── scripts/                   # 确定性打包、哈希核验、发布元数据
```

## 安装

```powershell
git clone https://github.com/fsy2004/MetaWingman.git
cd MetaWingman
.\install.ps1        # 默认安装到 ~\.agents\skills\metawingman
```

或作为本地 plugin marketplace：

```powershell
codex plugin marketplace add .
codex plugin add metawingman@metawingman-local
```

调用 `$metawingman`，给出研究问题、当前阶段与已有材料（协议、检索式、
RIS/CSV、PDF、提取表或分析数据），期望输出为决策记录、可复现项目、图表、
GRADE 表、稿件或审稿报告。

skill 格式本身与宿主无关：同一个包可在任何支持 skill 的主机加载，上面的
Codex plugin 只是它的封装形式之一。

## 开发与验证

```powershell
python -m unittest discover -s .\tests -v                      # 全量测试
python .\metawingman\scripts\test_r_adapters.py .\metawingman  # R 适配器
python .\scripts\build_skill_bundle.py                          # 重建双 skill 产物
python .\scripts\verify_skill_bundle.py .\.agents\skills\metawingman
python .\scripts\verify_dependency_locks.py                     # 依赖锁核验
python .\metawingman\scripts\audit_system_coverage.py           # 能力覆盖审计
python .\metawingman\scripts\audit_biomedical_coverage.py       # 医学覆盖审计
```

成功执行只证明接口和依赖在当前环境可工作，不证明某个具体综述达到科研完成
标准。

## 数据与训练资产

- 语料：`research/top-journal-training-corpus-v2.json`（27,046 条，Europe PMC
  OA，逐篇许可/撤稿核验下载）与 22 期刊分层原始版。
- 训练计划：`research/training-corpus-plan-biomedical-v3.json`（12,000 条，
  9,590 train / 2,410 dev，家族隔离）。
- 运行产物：109,028 条弱监督样本、30,272 对检索样本（2,048 篇版）与 12k
  版对导出、两个组件 receipt（含全部 checkpoint 哈希），归档于
  `validation-output/`（git 忽略，服务器与本地各一份）。
- 复现入口：`docs/architecture/server-training-runbook.md`（含中断恢复流程）、
  `docs/architecture/training-freeze-decisions.md`（冻结决策与修订）。

## 自动化与账号边界

skill 不要求模型 API 账号。开放检索可匿名使用 Europe PMC、
ClinicalTrials.gov 与 Crossref；开放全文下载需要 `UNPAYWALL_EMAIL`，PubMed
建议设置 `NCBI_EMAIL`。Embase、CENTRAL、Web of Science、Scopus 等仍由机构
账号人工登录导出。外接 Agent 的模型凭证只从环境变量、操作系统凭证库或部署
方密钥服务读取，不写入仓库。

## GitHub 同步（直连优先 + Gitee 桥接兜底）

部分网络直连 `github.com` 会被阻断。本机 git 已配置走本地代理
（`127.0.0.1:7892`，浏览器同款）：

```powershell
git config --global http.https://github.com/.proxy http://127.0.0.1:7892
```

代理不可用时自动兜底：本地 → Gitee（SSH）→ GitHub（服务器端 Actions 桥，
`.github/workflows/sync-gitee.yml`，每 30 分钟 cron + 手动触发，推送认证用
仓库 Secret `GH_SYNC_TOKEN`，推送前强制对齐 `main` 与
`codex/github-beta`）。桥接存在期间 Gitee 是事实来源，GitHub 侧对这两个
分支的直接改动会被覆盖。

一键同步并校验 SHA（直连失败自动转桥接）：

```powershell
pwsh tools/github-sync.ps1
```

## 当前研究方向

研发叙事以两项可证伪的方法贡献为主：**结论导向的证据控制**（scientific
responsibility graph + 状态转移 verifier + "残余遗漏风险 × 下游结论影响"）
与**时间与决策感知的选题机会引擎**（截止日前 evidence graph + 反对检索 +
冻结价值/风险门 + 前瞻注册）。全生命周期系统、多模态文档状态与时间封存/
协议扰动评测是支撑贡献。AI-only 评测以已发表综述的时间切分重建为主任务
来源，报告与 `published_expert_reference` 的一致性而非绝对真值准确率。

研究入口：

- [端到端方法学蓝图](docs/architecture/end-to-end-methodology-blueprint.md)
- [AI-first Architecture Roadmap（P0-P3）](docs/architecture/ai-first-roadmap.md)
- [顶刊式贡献叙事契约](docs/architecture/top-journal-contribution-story.md)
- [创新与可证伪矩阵](docs/architecture/innovation-and-falsification-matrix.md)
- [AI-only benchmark protocol](docs/architecture/ai-only-benchmark-protocol.md) 与 [预注册组件 pilot](docs/architecture/ai-only-pilot-preregistration.md)
- [训练运行报告](docs/architecture/training-run-report-2026-08-17.md) 与 [对抗审查](docs/architecture/adversarial-review-2026-08-17.md)
- [全项目改进审查](docs/architecture/improvement-review-2026-08-17.md)
- [方法学文献与 GitHub 参照映射](docs/architecture/methods-bibliography.md)
- [服务器训练 runbook](docs/architecture/server-training-runbook.md)
- [算力与部署预算](docs/architecture/compute-and-deployment-budget.md)
- [Skill 与 plugin 发布方案](docs/architecture/distribution-and-skill-release.md)

## License

项目代码使用 [MIT License](LICENSE)。调用的 R 包、数据库、全文和方法各自
遵循其许可证与引用要求。
