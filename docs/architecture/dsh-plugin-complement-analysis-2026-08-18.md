# DSH Agent 日常科研能力插件使用指南（2026-08-18）

视角：DSH 是你日常科研的 agent 工作台。本文件说明新装 5 个插件**补上了哪些
日常科研能力**、每个插件**怎么用**（调用方式/入口），以及与已有插件的配合。

## 1. 能力全景：装之前 vs 装之后

| 日常科研需求 | 装之前的 DSH | 装之后 |
|---|---|---|
| 查文献、查方法、查基因/药物/试剂信息 | 无网搜能力（agent 只能查你给的本地文件） | **ModSearch**：多引擎联网搜索 |
| 看实验图、论文图、软件界面截图 | 纯文本，看图只能靠 OCR 外部工具 | **vision-toolkit**：直接读图、长截图 OCR |
| 把 Claude Code / Codex / Kimi 里的科研会话搬进来继续干 | 无法导入 | **chat-import**：14 种外部会话导入续跑 |
| 远程（手机/别处电脑）用 Web GUI 时读写本机科研文件 | dsh-files 只能摸主机 | **browser-fs**：读写浏览器所在机器的文件 |
| 检查自己装的第三方插件是否健康 | 无 | **plugin-check**：插件仓库体检（只读） |

已有插件继续各司其职：`dsh-files`（主机文件）、`dsh-codex-bridge`（Codex 实时桥）、
`dshmarket`（装/卸插件）、`web-ui-notify`（通知）、`dsh-open-in-vscode`（IDE 打开）。

## 2. 每个插件怎么用（agent 视角）

### ModSearch —— 日常查一切
- 用法：直接在对话里让 agent "查一下 XXX"，agent 会调用 ModSearch 工具联网搜索
  （默认 Antigravity 引擎免费，可配 Tavily/Exa/Firecrawl/Grok 与自动 failover）。
- 科研场景举例：
  - "查一下 IL-6 抑制剂治疗 SSc-ILD 的最新试验"（文献/试验动态）
  - "这个基因在哪个数据库有表达数据"（数据库/工具信息）
  - "某篇论文的撤稿状态 / 作者单位 / 期刊信息"（事实核验）
- 注意：Tavily/Exa/Firecrawl 需要各自 API key（放环境变量，不要写进对话和文件）。
- 与 MetaWingman 的关系：选题/检索阶段也可以用它做联网核查，但它的本职是你的日常搜索。

### vision-toolkit —— 让 agent 看图
- 用法：把图粘贴到对话框（或让 agent 截图），直接问图里的内容；长截图自动分段 OCR。
- 科研场景举例：
  - 把论文里的森林图/火山图/UMAP 截图丢给 agent："解读这张图、提取图例数据"
  - 数据库/软件界面截图："这个页面怎么导出 RIS""这个按钮在哪"
  - 打印版问卷/表格照片 → OCR 转文本

### chat-import —— 会话搬家
- 用法：在侧边栏导入外部会话（Claude Code / Codex / Kimi 等 14 种），导入后按 DSH
  会话继续追问；也可以反向导出/同步回源或互换包。
- 科研场景举例：
  - 在 Codex 里做到一半的单细胞分析，搬进 DSH 继续（跨模型续跑）
  - 把 Kimi 里的文献讨论搬过来统一管理

### plugin-check —— 插件体检
- 用法：让 agent 运行 `plugin_check`（check/scan/schema 三个动作），产出合规章报告
  （cordis 版本、patch 格式、构建陷阱、hub 收录），只读不修改。
- 场景：装了新插件不放心时先体检；把自己的插件发 hub 前自查。

### browser-fs —— 远程读文件
- 用法：Web GUI 里授权一个目录（File System Access API，句柄存 IndexedDB），之后
  agent 可用 browser_fs_list/read/write 三个工具读写该目录。
- 场景：人在外面用手机/别的电脑开 DSH Web，让 agent 读本机数据/写结果文件。

## 3. 常见科研任务 → 插件组合

| 任务 | 组合 |
|---|---|
| 日常查文献/查事实 | ModSearch（+ 已有 dsh-files 读本地 PDF） |
| 读图/OCR | vision-toolkit |
| 跨 host 续跑分析 | chat-import 搬会话 + dsh-codex-bridge 回 Codex |
| 远程办公读写文件 | browser-fs |
| 插件维护 | plugin-check + dshmarket |
| 系统综述/meta（MetaWingman） | ModSearch（联网核查）+ vision-toolkit（读 PRISMA/森林图）+ chat-import（跨 host 迁移） |

## 4. 注意

- 插件安装已完成，**重启/刷新 DSH GUI 后生效**。
- GitHub 托管的 plugin-check 与 browser-fs 经本地代理安装；`allowBuilds: ["*"]`
  已写入 web profile 的 pnpm-workspace.yaml。
- 所有 API key 只放环境变量（本机已 setx GLM_API_KEY），不写进对话与文件。
