# MetaWingman

> 面向 Codex 的、方法学优先且可审计的系统综述与 Meta 分析全流程项目。

MetaWingman 不把系统综述简化成“让 AI 搜文献、做森林图”。它面向医学全科证据综合，把选题与可行性判断、协议与注册、实时数据库检索、合法全文获取、筛选、数据提取和研究谱系、偏倚风险评价、统计或 SWiM 综合、GRADE、统一写作、AI 审稿与 living update 放进同一套有状态工作流。

[![Codex Skill](https://img.shields.io/badge/Codex-skill-111827)](metawingman/SKILL.md)
[![R Toolkit](https://img.shields.io/badge/R_toolkit-26_modules-276DC3)](toolkit/R)
[![Analysis manifests](https://img.shields.io/badge/manifests-61-0A7BBC)](metawingman/scripts/r/manifests)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

## 两个交付物，先发布 skill

MetaWingman 分成两条产品线：第一条是使用 Codex/宿主模型和现有工具的独立 skill，不要求额外模型 API；第二条是后续可外接任意厂商或本地模型的多 agent runtime。两者共享方法学、schema、证据图、确定性 verifier、R toolkit 和 benchmark，但发布包、凭证、数据流与能力声明分开。DeepSeek 只是当前研发区的第一个 adapter，不是 Agent 架构绑定。

## 为什么先做成 skill，而不是另一个 Meta 软件

传统软件通常从“已经整理好的分析表”开始，难以约束之前最容易出错的科研决策。MetaWingman 从研究问题开始，要求每个阶段留下输入、决策者、时间戳、证据锚点、版本和校验结果；只有前一阶段的 hard gate 通过，才进入下一阶段。

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

## 项目结构

```text
MetaWingman/
├── README.md                  # GitHub 项目首页
├── metawingman/               # 可安装的 Codex skill
│   ├── SKILL.md               # 触发规则、工作流和科研红线
│   ├── agents/openai.yaml     # Codex UI 元数据
│   ├── references/            # 按阶段加载的方法学说明
│   └── scripts/               # 检索、下载、去重、校验和 R 适配器
├── toolkit/                   # 独立 R Meta 分析工具箱
│   ├── R/                     # 26 个统计与绘图模块
│   ├── docs/                  # 效应量、规范、引用和顶刊标准
│   └── examples/              # 端到端示例
├── .agents/skills/            # 从 canonical source 生成的 repo skill
├── plugins/metawingman/       # 从同一来源生成的 skills-only plugin
├── scripts/                   # 确定性打包与哈希核验
└── install.ps1                # 校验并原子安装自包含 skill
```

仓库中 skill 和 toolkit 分开维护，避免方法代码被埋在 agent 指令里。`scripts/build_skill_bundle.py` 从这两个 canonical source 生成内容相同的 repo skill 与 plugin skill；`install.ps1` 逐文件核验发布清单后再原子替换个人 skill。

`metawingman/` 是当前唯一的 skill 指令源，`toolkit/` 是统计源码。Codex 可从 `.agents/skills/` 发现 repo-scoped skill，也可通过 `plugins/metawingman/` 安装本地 plugin；两份产物带相同聚合哈希，避免多份 `SKILL.md` 漂移。详见[发布与分发方案](docs/architecture/distribution-and-skill-release.md)。

## 能做什么

| 阶段 | 核心能力 | 不允许 AI 静默替代的决定 |
|---|---|---|
| 选题 | PICO/PECO 等问题框架、估计目标、既有综述与注册核查、证据可得性 | 研究范围与继续/停止 |
| 协议 | 资格标准、结局、检索源、偏倚工具、综合和偏离政策 | 协议冻结与修订批准 |
| 检索 | PubMed、Europe PMC、ClinicalTrials.gov 可审计检索；Crossref/DOI 身份核验 | 商业数据库最终检索确认 |
| 获取 | Unpaywall/开放链接和用户授权渠道；保存许可证、URL、哈希和时间 | 登录、验证码、机构许可 |
| 纳排 | 保守去重、双人题录/全文筛选、冲突与逐篇排除理由 | 最终排除与冲突仲裁 |
| 提取 | `record → report → study/trial → arm/cohort → result → synthesis → claim` 谱系，多臂、多时间点和共享对照 | 原文定位、关键数值复核 |
| 评价 | RoB 2、正式 ROBINS-I 或具名草案、ROBINS-E、QUADAS-3、PROBAST+AI、ROB-ME/ROB-MEN 等分层评价 | 最终领域判断 |
| 综合 | Pairwise、NMA、DTA、比例/率、剂量反应、Bayesian、多层/RVE、序贯分析或 SWiM | 可合并性、模型和效应量选择 |
| 报告 | GRADE/SoF、PRISMA、统一数字/术语/图表样式、AI 多视角审稿闭环 | 结论强度、作者责任和投稿确认 |

## 科研真实性原则

- 对指南、注册、撤稿、参考文献和时效性事实执行实时联网核验。
- 逐条核验题名、作者、年份、期刊、DOI/PMID/注册号及其与论点的对应关系。
- 不虚构数据库权限、检索条数、PDF、筛选决定、提取值、模型输出、置信区间或 GRADE 等级。
- 摘要不能支撑全文资格、详细方法、数值结果或偏倚判断时，明确标记为待全文核验。
- AI 默认执行可逆、可审计、可核验的主流程；在 `assurance` 模式遵守所选权威要求的独立人工程序，高风险判断与最终责任不得被静默替代。AI 替代人工任务的主张只在预注册的 `evaluation` 模式检验。
- 分析前冻结数据并保存哈希；冻结后的改变必须记录修订并重新运行。
- 只使用开放 API、开放获取、用户提供文件或已授权机构路径，不绕过付费墙、验证码、robots 或许可条款。

## 内置统计工具箱

`toolkit/` 提供 26 个 R 模块；`metawingman/scripts/r/` 提供 15 个任务适配器、61 个分析清单和声明的示例输入。覆盖：

- 效应量和不确定性转换、Pairwise random-effects Meta；
- 异质性、预测区间、亚组、Meta 回归和 permutation；
- funnel、Egger/Begg、trim-and-fill、PET-PEESE；
- leave-one-out、Baujat、GOSH、累计 Meta 和影响诊断；
- Network Meta、排名、league table、node splitting、net heat 和 component NMA；
- DTA 的双变量模型、SROC/HSROC、敏感度/特异度、LR 与 DOR；
- 患病率、比例、均值和发生率；
- Bayesian、三层模型、RVE、剂量反应、E-value 和 trial sequential analysis；
- PRISMA、RoB 和 GRADE/SoF 输出。

清单数量不等于推荐自动运行全部分析。方法必须服从协议、estimand、设计、依赖结构、样本量和最新方法学证据。

## 安装

在 PowerShell 中运行：

```powershell
git clone https://github.com/fsy2004/MetaWingman.git
cd MetaWingman
.\install.ps1
```

默认安装到 `C:\Users\<用户名>\.agents\skills\metawingman`。安装脚本会重建确定性 bundle、核验逐文件与聚合哈希、调用 Codex 官方 skill validator，并在失败时保留原安装。

也可把仓库作为本地 plugin marketplace 安装：

```powershell
codex plugin marketplace add .
codex plugin add metawingman@metawingman-local
```

安装后在 Codex 中调用：

```text
$metawingman

研究问题：……
当前阶段：选题 / 协议 / 检索 / 纳排 / 提取 / 评价 / 分析 / 写作 / 审稿 / 更新
已有材料：协议、检索式、RIS/CSV、PDF、提取表或分析数据
期望输出：决策记录、可复现项目、图表、GRADE 表、稿件或审稿报告
```

仓库已包含 repo skill、本地 marketplace、skills-only plugin、正负触发样例和隐私/安全/支持/使用边界。公开提交仍需真实 benchmark、许可证审查、公开 URL、发布者身份材料和远端提交流程；第一版不需要 MCP 服务器。

## 算力需求

当前方法学开发、状态管理、检索导入、去重、证据图、PDF 预处理和常规 R Meta 分析不需要模型 API 或本地 GPU，普通 4-8 核 CPU、16 GB RAM 和 SSD 即可。独立 skill 直接使用宿主 agent 的模型与工具，不含任何厂商模型 API client。后续外接 Agent 通过统一 provider contract 接入商业、国产、机构或本地模型；接入不等于训练新模型，也不替代任务校准、跨提供商验证或多模态能力验证。真实工作流验证须同步测量成本、隐私、延迟、校准与路由收益。

首批 2,048 篇元数据计划和两个 BiomedBERT 组件任务适合单卡 24-48 GB VRAM。推荐起步为 1×24 GB GPU、16 vCPU、64 GB RAM、500 GB NVMe；更舒适为 1×48 GB GPU、24-32 vCPU、128 GB RAM、1 TB NVMe。多张低显存卡不会自动合并显存，当前更适合把 OCR、解析器消融、分类、检索和 benchmark 重复实验拆成独立并行任务，而不是把一个小模型跨卡切分。

本机的 i9-13900HX、16 GB RAM、RTX 4060 Laptop 8 GB 足够当前开发、R 分析、OCR/layout 实验和小型量化模型；批量全文解析时 RAM 比 GPU 更先成为瓶颈。只有计划全本地运行多个大语言/视觉模型时，才建议 64 GB RAM 与 24-48 GB VRAM 级别。完整分档和 benchmark 指标见[算力与部署预算](docs/architecture/compute-and-deployment-budget.md)。

## 开发与验证

```powershell
# 校验 skill 元数据
python -X utf8 C:\Users\<用户名>\.codex\skills\.system\skill-creator\scripts\quick_validate.py .\metawingman

# 生成并逐文件核验 repo/plugin 两份 skill bundle
python .\scripts\build_skill_bundle.py
python .\scripts\verify_skill_bundle.py .\.agents\skills\metawingman
python .\scripts\verify_skill_bundle.py .\plugins\metawingman\skills\metawingman

# 生成可分享的独立 skill ZIP 与 SHA256 校验文件
python .\scripts\package_skill_release.py

# 生成绑定 ZIP 哈希的 SPDX SBOM 与明确未签名的 in-toto provenance
python .\scripts\generate_release_metadata.py

# 验证当前 Python/R 运行时是否匹配精确依赖锁
python .\scripts\verify_dependency_locks.py

# 运行本地控制面与方法模块测试
python -m unittest discover -s .\tests -v

# 从 Europe PMC 构建顶刊优先的系统综述训练/开发元数据语料
python .\metawingman\scripts\harvest_top_journal_corpus.py --out .\research\top-journal-training-corpus.json

# 生成保守的综述家族候选注册表；建议 split 在完成家族审计前不可使用
python .\metawingman\scripts\cluster_review_families.py .\research\top-journal-training-corpus.json --out .\research\top-journal-review-family-registry.json

# 生成可重放的 OA 训练/开发计划；held-out 保持关闭
python .\metawingman\scripts\plan_training_corpus.py --corpus .\research\top-journal-training-corpus.json --families .\research\top-journal-review-family-registry.json --out .\research\training-corpus-plan-v1.json --maximum-records 24 --seed 20260815

# 生成医学分层的 2,048-record metadata-only 计划，不下载全文
python .\metawingman\scripts\plan_training_corpus.py --corpus .\research\top-journal-training-corpus.json --families .\research\top-journal-review-family-registry.json --specialty-registry .\metawingman\references\domain-packs\specialty-registry.json --out .\research\training-corpus-plan-biomedical-v2.json --maximum-records 2048 --seed 20260815 --created-at-utc 2026-08-15T00:00:00Z

# 下载文章级许可核验后的 OA PDF/XML，并冻结弱监督训练集
python .\metawingman\scripts\fetch_training_corpus.py .\research\training-corpus-plan-v1.json --out .\validation-output\training-corpus\documents
python .\metawingman\scripts\freeze_training_dataset.py .\validation-output\training-corpus\documents\training-document-manifest.json --artifact-root .\validation-output\training-corpus\documents --examples-out .\validation-output\training-corpus\training-examples.jsonl --run-plan-out .\validation-output\training-corpus\training-run-plan.json
python .\metawingman\scripts\audit_training_dataset.py --plan .\research\training-corpus-plan-v1.json --manifest .\validation-output\training-corpus\documents\training-document-manifest.json --examples .\validation-output\training-corpus\training-examples.jsonl --run-plan .\validation-output\training-corpus\training-run-plan.json --artifact-root .\validation-output\training-corpus\documents

# 外接 Agent：通过无密钥配置探测任意兼容 provider
python .\metawingman\scripts\probe_provider.py .\metawingman\references\deepseek-provider-config.json

# 外接 Agent：按调用/输出预算运行可恢复的 schema-gated JSONL 批任务
python .\metawingman\scripts\run_structured_batch.py .\tasks.jsonl --provider-config .\provider.json --out .\runs.jsonl --max-provider-calls 20 --max-reserved-output-tokens 81920 --allow-hosted-data-transfer

# 审计生命周期、综述类型、统计路线与验证等级的实际覆盖
python .\metawingman\scripts\audit_system_coverage.py
python .\metawingman\scripts\audit_biomedical_coverage.py

# 在本地只做组件训练完整性预检；不导入训练 runtime，不启动训练
python .\metawingman\scripts\preflight_component_training.py .\validation-output\training-corpus\jobs\section-role.json --root . --out .\validation-output\training-corpus\jobs\section-role.preflight.json

# 构建仅含元数据、schema、锁文件和作业清单的服务器交接包
python .\metawingman\scripts\build_server_training_handoff.py --source-root . --plan .\research\training-corpus-plan-biomedical-v2.json --job .\validation-output\training-corpus\jobs\section-role.json --job .\validation-output\training-corpus\jobs\evidence-retrieval.json --preflight .\validation-output\training-corpus\jobs\section-role.preflight.json --preflight .\validation-output\training-corpus\jobs\evidence-retrieval.preflight.json --lock .\metawingman\references\dependencies\python-training.lock.txt --out .\validation-output\server-training-handoff-v2

# 生成实时 R 工具目录
python .\metawingman\scripts\build_tool_catalog.py .\metawingman

# 运行所有声明的 R 示例（需要对应 R 包）
python .\metawingman\scripts\test_r_adapters.py .\metawingman --outdir .\validation-output
```

成功执行只证明接口和依赖在当前环境可工作，不证明某个具体综述已经达到科研完成标准。

## 自动化与账号边界

独立 skill 不要求模型 API 账号。开放检索可匿名使用 Europe PMC、ClinicalTrials.gov 和 Crossref；开放全文下载需要 `UNPAYWALL_EMAIL`，PubMed 建议设置 `NCBI_EMAIL`，高频请求可选 `NCBI_API_KEY`，Crossref 礼貌池可选 `CROSSREF_EMAIL`。Embase、CENTRAL、Web of Science、Scopus 等仍由机构账号人工登录并导出。后续外接 Agent 的模型凭证只从环境变量、操作系统凭证库或部署方密钥服务读取，不写入仓库；任何单一 provider 都只能支持开发，不能满足高风险判断的跨提供商独立性门槛。

## 当前研究方向

MetaWingman 的下一阶段是建立可评估的 AI-first evidence-synthesis agent：模型默认完成可逆、可验证、可审计的主流程，人类处理弃权、分歧、高风险判断、账号授权、不可逆提交和最终责任签署。这不是无条件无人化，而是在预设安全阈值下报告 AI 覆盖率、关键错误率、成本、漂移和复现性。

研发叙事以两项可证伪的方法贡献为主：**结论导向的证据控制**把 scientific responsibility graph、状态转移 verifier 和“残余遗漏风险 × 下游结论影响”结合起来，动态分配检索、全文、复核与 test-time compute；**时间与决策感知的选题机会引擎**用截止日前 evidence graph、反对检索、冻结价值/风险门和前瞻注册发现值得综合的问题。全生命周期系统、多模态全局文档状态和时间封存/协议扰动评测是支撑这两项方法的系统与评价贡献，不单独包装成第三个算法。当前 coverage audit 证明的是工件和边界已显式化，不等于所有综述类型都已原生实现、模型已经训练或通过真实科学验证。

AI-only 评测以已发表系统综述/Meta-analysis 的时间切分重建为主要任务来源：封存原综述答案和截止日后证据，重跑检索、纳排、谱系、提取与分析。顶刊综述团队公开的最终纳排、提取、偏倚评价和分析作为 `published_expert_reference`；有正式更正时只使用核验后的修正版，撤稿、版本冲突或重大内部矛盾未解决时不进入 held-out 评分，不再常规新增双人裁决。实验只比较预先冻结的 AI 配置与消融，每个配置重复运行，并在综述家族完成聚类后隔离训练、开发和测试。报告的是与已发表专家参考的一致性，不是绝对真值准确率；由于没有人工执行臂，不得声称优于人工或节省人工劳动时间。

研究入口：

- [端到端方法学蓝图](docs/architecture/end-to-end-methodology-blueprint.md)：来源权威分层、`assurance/evaluation/rapid` 三种模式、全流程缺陷审查、科学状态对象、风险门与评测设计。
- [方法学与 AI 原始来源注册表](metawingman/references/methodology-source-registry.md)：逐条记录正式身份、来源层级、可迁移机制和禁止外推。
- [AI 原生多模态 Agent 架构](research/ai-native-multimodal-agent-architecture.md)：顶刊/顶会机制核验、系统总架构、AI-first 与 human-overseen 边界。
- [选题机会引擎](docs/architecture/topic-opportunity-engine.md)与[跨领域历史目标注册表](research/topic-rediscovery-target-registry.json)：时间边界图谱、模型提案/独立评分分离、价值风险门、Top-K 重发现、前瞻性选题注册与严格污染边界。当前 15 个目标只属于分层开发入口；3 个具备初步历史边界，尚无目标晋升为密封测试案例。
- [AI-first Architecture Roadmap](docs/architecture/ai-first-roadmap.md)：P0/P1/P2/P3 路线、首批 schema/module、benchmark、对照和消融 backlog。
- [顶刊式贡献叙事契约](docs/architecture/top-journal-contribution-story.md)：把选题机会控制、全流程系统、结论风险控制和时间封存/反事实评价组织为一条可证伪的科学故事，并规定每项所需证据。
- [创新与可证伪矩阵](docs/architecture/innovation-and-falsification-matrix.md)：区分方法复用与 MetaWingman 特有优化，并为每个候选创新绑定直接对照、消融和失败条件。
- [机器可审计能力矩阵](metawingman/references/system-capability-matrix.json)：分别登记十阶段生命周期、21 类 review profile、19 条 synthesis route、跨阶段控制及其验证等级，防止把 workflow coverage 写成已验证能力。
- [AI-only benchmark protocol](docs/architecture/ai-only-benchmark-protocol.md)、[顶刊训练/开发语料](research/top-journal-training-corpus.json)、[综述家族候选注册表](research/top-journal-review-family-registry.json)、[选题目标注册表](research/topic-rediscovery-target-registry.json)、[广泛复现发现目录](research/meta-reproduction-discovery-catalog.json)与[严格全流程候选注册表](research/benchmark-candidate-registry.json)：官方 API 当前收录 4,098 条元数据，其中 3,534 条为开发候选、388 条等待完整性审计、9 条撤稿排除、167 条评论/来信/指南声明等非参考材料排除；家族层只给出 281 条待审计边和 split 建议，尚无 family 可进入 held-out。期刊层级只用于抽样和分层，不进入质量评分。
- [可重复训练语料与训练范式](docs/architecture/reproducible-training-corpus.md)及[冻结 v1 采样计划](research/training-corpus-plan-v1.json)：从文章级许可/撤稿核验、OA PDF/XML 下载、家族隔离、证据锚定弱监督、完整性审计到 chat-SFT/检索正样本导出；当前只是 24-family 本地 pilot，不是已训练模型或科学验证集。
- [医学分层 v2 训练计划](research/training-corpus-plan-biomedical-v2.json)与[服务器训练 runbook](docs/architecture/server-training-runbook.md)：冻结 2,048 条 metadata-only 训练候选、组件作业、hard negatives、离线 preflight 和 metadata-only handoff；服务器硬件、CUDA 与精确依赖仍须现场核验，尚未启动训练。
- [Skill 与 plugin 发布方案](docs/architecture/distribution-and-skill-release.md)：单一 skill 源、repo 自动发现、个人安装、skills-only plugin 和公共发布门槛。
- [Skill/Agent 双产品边界](docs/architecture/two-product-boundary.md)：规定 skill 使用宿主模型且不含模型 API client，后续 Agent 通过 provider-neutral contract 接入任意模型。
- [模型 provider 与数据流矩阵](docs/architecture/model-provider-support-matrix.md)：区分 DeepSeek 实时连通、通用兼容接口测试、本地 loopback 合同测试和未支持原生 API，并规定密钥、托管传输、schema 校验与候选接纳边界。
- [算力与部署预算](docs/architecture/compute-and-deployment-budget.md)：cloud-first、hybrid、全本地和团队服务的硬件、成本与 benchmark 方案。
- [全流程能力、判断瓶颈与创新地图](research/full-workflow-agent-landscape-and-innovation-map.md)：系统综述与 Meta-analysis 全流程能力矩阵和方法学边界。
- [Meta agent 缺口与研究路线](research/meta-agent-gaps-and-paper-roadmap.md)：早期竞品、工程审计要求和论文路线保留稿。

## License

项目代码使用 [MIT License](LICENSE)。调用的 R 包、数据库、全文和方法各自遵循其许可证和引用要求。
