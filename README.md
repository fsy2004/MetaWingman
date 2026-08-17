# MetaWingman

> 方法学优先、可审计的系统综述与 Meta 分析全流程项目：面向医学全科证据综合，
> 把选题、协议、检索、全文获取、纳排、提取谱系、偏倚评价、统计综合、GRADE、
> 写作、AI 审稿与 living update 放进同一条带 hard gate 的状态工作流。

[![Codex Skill](https://img.shields.io/badge/Codex-skill-111827)](metawingman/SKILL.md)
[![R Toolkit](https://img.shields.io/badge/R_toolkit-26_modules-276DC3)](toolkit/R)
[![Analysis manifests](https://img.shields.io/badge/manifests-61-0A7BBC)](metawingman/scripts/r/manifests)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

## 项目现状（三级证据，如实）

| 级别 | 内容 |
|---|---|
| **① 已执行** | 可审计检索与逐篇许可/撤稿核验全文下载；确定性效应量重算；26 模块 R 统计综合；两个 110M BiomedBERT 组件训练（section-role 分类、证据检索）；预注册四配置 AI-only pilot |
| **② 组件级评估** | dev 集上训练组件与弱标签的规则一致性（非金标准）：section-role macro-F1 0.983（剥离标题行 0.670）；检索候选集 MRR 0.954；pilot 中零 API 成本超过托管模型 |
| **③ 设计级（类型化契约 + fixtures，未端到端验证）** | 筛选、提取谱系、RoB、GRADE、审稿、living update 的 schema、hard gate 与测试就绪，端到端执行证据待时间切分重建评估产出 |

- **语料与数据**：27,046 条 OA 元数据语料、12,000 条训练计划、109,028 条
  弱监督样本（12k 重训在服务器自动推进中）。
- 所有实测数字、receipt 哈希、缺陷修复与对抗审查见
  `docs/architecture/training-run-report-2026-08-17.md`、
  `docs/architecture/adversarial-review-2026-08-17.md` 与
  `docs/architecture/reviewer-panel-2026-08-17.md`。

## 两个交付物：skill 面向多数用户，agent 面向纵深

两条产品线共享同一套方法学、schema、证据图、确定性 verifier、R toolkit 与
benchmark；发布包、凭证、数据流与能力声明分开。

1. **独立 skill（主入口，多数人使用）**：使用宿主模型（Codex 等）与现有
   工具，不要求额外模型 API；内置 26 个 R 统计模块与 61 个分析清单。
2. **多 agent runtime（后续）**：provider-neutral contract 外接任意厂商或
   本地模型，面向自动化批量与评估场景。

## 为什么先做成 skill，而不是另一个"Meta 软件"

传统软件通常从"已经整理好的分析表"开始，难以约束之前最容易出错的科研
决策。MetaWingman 的北极星是：**AI 执行十阶段全流程的可逆、可验证、可审计
主路径**，完成质量对标顶刊研究者；人工审查复核落实为**预留的审核窗口
（接口）与模糊 AI 披露声明**（`docs/architecture/human-window-policy.md`），
实际执行全部由 AI 完成。每一阶段只有通过 hard gate 才进入下一阶段。逐阶段
的 AI 执行方法、审核窗口与落实优先级见
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

两个 110M `BiomedBERT` 组件，覆盖全流程中的两个窄子任务：

| 组件 | 任务 | 实测（dev，弱监督标签） |
|---|---|---|
| section-role 分类 | 段落 → 8 类工作流角色（search/eligibility/selection/extraction/appraisal/synthesis/certainty/protocol） | macro-F1 **0.983**（剥离标题行后 0.670；多数类基线 0.046） |
| 证据检索 | 字段 + 综述标题 → 支撑段落（in-batch + hard negatives） | 候选集 MRR **0.954** / P@1 0.919（TF-IDF 基线 0.712 / 0.549） |

四配置 AI-only pilot（C0 裸提示 / C1 +schema / C2 +医学上下文 / C3 +训练
verifier，DeepSeek，各 400 调用）：训练组件在两项任务上**全部超过托管模型
配置**且零 API 成本（section-role 0.983 vs 0.967；检索 MRR 0.954 vs 0.495）。
更多可训练组件（筛选准则分类、提取字段分类、谱系消解）与优先级见
`docs/architecture/improvement-review-2026-08-17.md`。

**声明边界**：以上均为开发集上的弱标签一致性；held-out 未启用、标签未经
独立人工验证、无 publisher 认证——不构成科学有效性声明。

## 内置统计工具箱

`toolkit/` 提供 26 个 R 模块，覆盖：效应量与不确定性转换、Pairwise random-
effects Meta、异质性/预测区间/亚组/Meta 回归/permutation、funnel/Egger/
trim-and-fill/PET-PEESE、leave-one-out/Baujat/GOSH/累计 Meta、Network Meta/
排名/league table/node splitting/component NMA、DTA 双变量/SROC/HSROC、患病率/
比例/均值/发生率、Bayesian、三层/RVE、剂量反应、E-value、序贯分析，以及
PRISMA、RoB、GRADE/SoF 输出。清单数量不等于推荐自动运行全部分析——方法
必须服从协议、estimand、设计、依赖结构与最新方法学证据。

## 项目结构

```text
MetaWingman/
├── README.md                  # GitHub 项目首页
├── metawingman/               # 可安装的 Codex skill（canonical source）
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

在 Codex 中调用 `$metawingman`，给出研究问题、当前阶段与已有材料（协议、
检索式、RIS/CSV、PDF、提取表或分析数据），期望输出为决策记录、可复现项目、
图表、GRADE 表、稿件或审稿报告。

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
- 运行产物：109,028 条弱监督样本、30,272 对检索样本（2,048 篇版）与
  12k 版对导出、两个组件 receipt（含全部 checkpoint 哈希），归档于
  `validation-output/`（git 忽略，服务器与本地各一份）。
- 复现入口：`docs/architecture/server-training-runbook.md`（含中断恢复流程）、
  `docs/architecture/training-freeze-decisions.md`（冻结决策与修订）。

## 自动化与账号边界

独立 skill 不要求模型 API 账号。开放检索可匿名使用 Europe PMC、
ClinicalTrials.gov 与 Crossref；开放全文下载需要 `UNPAYWALL_EMAIL`，PubMed
建议设置 `NCBI_EMAIL`。Embase、CENTRAL、Web of Science、Scopus 等仍由机构
账号人工登录导出。外接 Agent 的模型凭证只从环境变量、操作系统凭证库或部署
方密钥服务读取，不写入仓库。

## GitHub 同步（Gitee 桥接）

本地网络直连 `github.com` 会被重置/阻断（`api.github.com` 与 `gitee.com`
可达）。同步走稳定通道：本地 → Gitee（SSH）→ GitHub（服务器端 Actions
桥，`.github/workflows/sync-gitee.yml`，每 30 分钟 cron + 手动触发，
推送认证用仓库 Secret `GH_SYNC_TOKEN`，推送前强制对齐
`main` 与 `codex/github-beta`）。Gitee 是事实来源，GitHub 侧对这两个分支
的直接改动会被覆盖。

一键同步并校验 SHA：

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
