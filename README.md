# MetaWingman

> 面向 Codex 的、方法学优先且可审计的系统综述与 Meta 分析全流程项目。

MetaWingman 不把系统综述简化成“让 AI 搜文献、做森林图”。它把选题与可行性判断、协议与注册、实时数据库检索、合法全文获取、双人筛选、数据提取和研究谱系、偏倚风险评价、统计或 SWiM 综合、GRADE、统一写作、AI 审稿与 living update 放进同一套有状态工作流。

[![Codex Skill](https://img.shields.io/badge/Codex-skill-111827)](metawingman/SKILL.md)
[![R Toolkit](https://img.shields.io/badge/R_toolkit-26_modules-276DC3)](toolkit/R)
[![Analysis manifests](https://img.shields.io/badge/manifests-61-0A7BBC)](metawingman/scripts/r/manifests)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

## 为什么做成 skill，而不是另一个 Meta 软件

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
└── install.ps1                # 组装并安装自包含 skill
```

仓库中 skill 和 toolkit 分开维护，避免方法代码被埋在 agent 指令里。安装时 `install.ps1` 会把 toolkit 复制到 skill 的 `scripts/r/toolkit/`，得到可独立运行的个人 skill。

## 能做什么

| 阶段 | 核心能力 | 不允许 AI 静默替代的决定 |
|---|---|---|
| 选题 | PICO/PECO 等问题框架、估计目标、既有综述与注册核查、证据可得性 | 研究范围与继续/停止 |
| 协议 | 资格标准、结局、检索源、偏倚工具、综合和偏离政策 | 协议冻结与修订批准 |
| 检索 | PubMed、Europe PMC、ClinicalTrials.gov 可审计检索；Crossref/DOI 身份核验 | 商业数据库最终检索确认 |
| 获取 | Unpaywall/开放链接和用户授权渠道；保存许可证、URL、哈希和时间 | 登录、验证码、机构许可 |
| 纳排 | 保守去重、双人题录/全文筛选、冲突与逐篇排除理由 | 最终排除与冲突仲裁 |
| 提取 | `record → report → study/trial → result` 谱系，多臂、多时间点和共享对照 | 原文定位、关键数值复核 |
| 评价 | RoB 2、ROBINS-I、QUADAS-2 等设计匹配评价，支持证据锚点 | 最终领域判断 |
| 综合 | Pairwise、NMA、DTA、比例/率、剂量反应、Bayesian、多层/RVE、序贯分析或 SWiM | 可合并性、模型和效应量选择 |
| 报告 | GRADE/SoF、PRISMA、统一数字/术语/图表样式、AI 多视角审稿闭环 | 结论强度、作者责任和投稿确认 |

## 科研真实性原则

- 对指南、注册、撤稿、参考文献和时效性事实执行实时联网核验。
- 逐条核验题名、作者、年份、期刊、DOI/PMID/注册号及其与论点的对应关系。
- 不虚构数据库权限、检索条数、PDF、筛选决定、提取值、模型输出、置信区间或 GRADE 等级。
- 摘要不能支撑全文资格、详细方法、数值结果或偏倚判断时，明确标记为待全文核验。
- AI 可以排序、标注和提出建议，但不得静默替代双人筛选、冲突仲裁、提取复核或最终 RoB 判断。
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

默认安装到 `C:\Users\<用户名>\.agents\skills\metawingman`。安装脚本会验证目标路径、组装 toolkit，并调用 Codex 官方 skill validator。

安装后在 Codex 中调用：

```text
$metawingman

研究问题：……
当前阶段：选题 / 协议 / 检索 / 纳排 / 提取 / 评价 / 分析 / 写作 / 审稿 / 更新
已有材料：协议、检索式、RIS/CSV、PDF、提取表或分析数据
期望输出：决策记录、可复现项目、图表、GRADE 表、稿件或审稿报告
```

## 开发与验证

```powershell
# 校验 skill 元数据
python C:\Users\<用户名>\.codex\skills\.system\skill-creator\scripts\quick_validate.py .\metawingman

# 生成实时 R 工具目录
python .\metawingman\scripts\build_tool_catalog.py .\metawingman

# 运行所有声明的 R 示例（需要对应 R 包）
python .\metawingman\scripts\test_r_adapters.py .\metawingman --outdir .\validation-output
```

成功执行只证明接口和依赖在当前环境可工作，不证明某个具体综述已经达到科研完成标准。

## 自动化与账号边界

公开 API 可以由脚本直接调用；API key 只从环境变量或经用户批准的密钥存储读取。需要机构登录、验证码或人工协议确认的数据库，采用“AI 准备检索式与操作 → 用户接管登录/导出 → AI 接续导入与审计”，不会把浏览器登录态、cookie 或密码写入仓库。

## 当前研究方向

MetaWingman 的下一阶段不是继续堆分析按钮，而是建立可评估的 evidence-synthesis agent：状态机、证据锚定、人机双审、可复现实验和公开 benchmark。参见 [全流程能力、判断瓶颈与创新地图](research/full-workflow-agent-landscape-and-innovation-map.md)；早期竞品与工程审计保留在 [Meta agent 缺口与研究路线](research/meta-agent-gaps-and-paper-roadmap.md)。

## License

项目代码使用 [MIT License](LICENSE)。调用的 R 包、数据库、全文和方法各自遵循其许可证和引用要求。
