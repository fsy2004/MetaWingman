# DSH 插件互补分析（2026-08-18）

新装 5 个插件与现有插件栈的互补关系，以及它们在 MetaWingman 全流程中的落点。

## 新装插件

| 插件 | 功能 | 与现有插件的关系 | MetaWingman 落点 |
|---|---|---|---|
| **ModSearch**（@liustack/modsearch） | 多引擎 web 搜索（Antigravity CLI 免费默认 / Tavily / Exa / Firecrawl / Grok X / local）+ 自动 failover；自带 skill（configure / output-schema / security） | 此前**无搜索插件**——补上 DSH 的网搜能力 | **核心**：选题阶段联网核查既有综述/注册/关键研究；检索阶段的实时核验（时效性事实、撤稿、参考文献）；补充 Europe PMC 之外的网页证据 |
| **dsh-vision-toolkit**（@anionex/dsh-vision-toolkit） | 给纯文本模型视觉：图像问答、长截图 OCR、UI 还原、GUI 视觉任务，内置免费 vision | 与本地 RapidOCR/Umi-OCR 工具链互补（本地管线 vs DSH 内嵌视觉） | 读取期刊/数据库网页截图、PRISMA 流程图、已发表综述的图表；复现综述时"看图"比对 |
| **dsh-chat-import** | 导入 14 种外部 agent 会话（Claude Code/Codex/Kimi 等）为可续会话；导出/同步回源或互换包 | 与 dsh-codex-bridge 互补（bridge 是实时桥，chat-import 是历史会话迁移） | **跨模型能力**：MetaWingman 项目状态在不同 host 之间迁移、交接与续跑 |
| **dsh-plugin-check**（@deepseek-ai/dsh-plugin-check） | 插件仓库健康检查：cordis 双版本 / patch 格式 / 构建陷阱 / hub 收录，只读输出合规章报告 | 与自有 `scripts/verify_skill_bundle.py` 互补（自有校验 + 第三方质量门） | MetaWingman 发布前的第三方质量门（plugin_check check plugins/metawingman） |
| **dsh-browser-fs** | agent 读写**浏览器所在机器**的本地文件（File System Access API + WS 转发） | 与 dsh-files（主机文件）互补：远程部署时浏览器在另一台机器 | 用户远程用 Web GUI 时导入文献 PDF/RIS/提取表 |

## 使用顺序建议

1. **选题/检索**：ModSearch 联网核查 → 与 Europe PMC/PubMed 的可审计检索互补；
2. **读图表/网页**：vision-toolkit OCR 截图 → 复现比对；
3. **跨 host 迁移**：chat-import 导入其他 agent 的 MetaWingman 会话继续推进；
4. **发布前**：plugin-check + 自有 verify_skill_bundle 双重质量门；
5. **远程场景**：browser-fs 让 agent 访问用户浏览器侧的文件。

## 注意

- 新插件需要重启/刷新 DSH GUI 后生效（client 插件无热重载）。
- ModSearch 默认引擎 Antigravity CLI 免费；Tavily/Exa/Firecrawl 需各自 API key（凭证只放环境变量，不进仓库）。
- GitHub 托管的两个插件（plugin-check、browser-fs）经代理安装，`allowBuilds: ["*"]` 已写入 web profile 的 pnpm-workspace.yaml。
