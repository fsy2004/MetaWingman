# GitHub 同步运维说明（内部，不进 README）

本文档记录 MetaWingman 仓库的 GitHub 同步通道，供维护者参考；对外 README
不包含这些内容。

## 通道结构

部分网络直连 `github.com` 会被阻断。本机 git 已配置按域走本地代理
（`127.0.0.1:7892`，浏览器同款）：

```powershell
git config --global http.https://github.com/.proxy http://127.0.0.1:7892
```

代理不可用时自动兜底：本地 → Gitee（SSH，`git@gitee.com:fsy2004/meta-wingman.git`，
公开仓库）→ GitHub（服务器端 Actions 桥，`.github/workflows/sync-gitee.yml`，
每 30 分钟 cron + 手动触发，推送认证用仓库 Secret `GH_SYNC_TOKEN`，推送前
强制对齐 `main` 与 `codex/github-beta`）。桥接存在期间 Gitee 是事实来源，
GitHub 侧对这两个分支的直接改动会被覆盖。

## 一键同步

```powershell
pwsh tools/github-sync.ps1
```

脚本流程：推 Gitee → 直连推 GitHub（代理）→ SHA 校验；直连失败自动转桥接
（触发 workflow → 轮询 → 校验）。兼容 Windows PowerShell 5.1 与 pwsh 7。

## 历史背景

- 2026-08-17：直连 github.com 被重置（亚太 IP 20.205.243.166 阻断），
  `api.github.com` 与 `ssh.github.com:443` 可达；先建 Gitee 镜像 + Actions
  桥接（GITHUB_TOKEN 不能改 workflow 文件，故用 PAT Secret），后发现本机
  代理可达 github.com，改为直连优先。
- 删除自动同步：删除 `.github/workflows/sync-gitee.yml` 并移除 Secret
  `GH_SYNC_TOKEN`。
