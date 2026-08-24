---
name: readme-maintainer
kind: dsh
description: 自述文件(README)创建/重写/持续维护范式。融合 docs/README_MAINTENANCE.md 契约与社区经验(reader contract / generated blocks / bind claims / maintenance contract)。触发词：自述文件、README、readme、重写自述、维护 readme、更新 readme、写自述文件、readme maintain。
---

# README / 自述文件更新范式(Readme Maintainer)

## 定位
README 是**产品入口**,不是目录堆砌或营销页。为"第一次打开仓库的用户"和"贡献者"两条读者服务;为内部读者保留 `docs/` 的完整契约、receipt 与结果表。

本项目 README 的**唯一权威契约**:`docs/README_MAINTENANCE.md`(本项目适用时应以其为准,并与之保持同步)。

---

## 1. 从 live authority 出发
- 读 `AGENTS.md`(若存在)、现有 README、贡献/状态/路线、manifest、入口、测试、release。
- `git status --short --branch`、remote、默认分支、PR、检查与分支保护;保留无关的 dirty 工作。
- 识别真实面向用户的表面:产品 / agent / skill / CLI-API / 安装路径 / examples / 生成的 bundle / 有日期的评估报告。
- 仓库能力/数字未经代码、可执行检查或版本化报告支撑前,标注"未验证"。

## 2. 先学习再重写
- 审视 3–5 个可比的开源仓库(同类:系统评价软件 / 文献 agent / 可复现分析引擎 / 研究 agent 框架)。记录 URL 与访问日期。
- 只借鉴**信息架构与视觉层级**;绝不复制 claims、metrics、截图、能力声明。
- 优先有"清晰首屏承诺 + 短可运行 quick start + 可见能力状态 + 可导航文档 + 维护的 release/贡献流程"的参考仓库。

## 3. 定义 readers contract
按顺序写:
1. 解决什么问题、给谁;
2. 用户得到什么(产品/agent/skill/工作流/库);
3. 最短已验证的可用路径;
4. 工作原理;
5. 已实现 / 实验评估 / 计划;
6. 证据、文档、安全、引用、贡献在哪里。

用**最少**的 badge 和截图;避免穷举文件、重复 caveat、夸大的新颖性语言、无来源的数字。

## 4. 分离"人工撰写"与"生成内容"
- 建 source-to-section 表。定位/解释/限制/科学结论**人工复核**并明确"非生成";只自动生成机制事实(版本、组件数、bundle 清单、测试数)。
- 生成块用 marker:
  `<!-- BEGIN GENERATED: component-status -->` … `<!-- END GENERATED: component-status -->`
- updater 只替换命名块内的文本;跑两次,第二次必须无 diff;绝不生成/覆盖科学结论。

## 5. 把 claim 绑定到证据
- 每个研究性能声明必须链接到**有日期、版本化**的报告,并说明数据集/评估包、样本/家族数、指标定义、模型/配置、种子、commit/release、scope 限制。
- 单测、冒烟、schema 校验、成功安装 = **工程证据**,不是科学性能证据。
- 描述创新 = 机制或工作流的**具体差异** + 当前支撑它的证据;未做对比与来源审计前,不用 priority / superiority 表述。

## 6. 建立维护契约
以下任何变化都应在**同一变更**里更新 README:
- 产品范围、agent/skill 目录、CLI/API、安装、配置、model/provider、license、隐私、安全、数据处置;
- 版本、release、bundle、文档化输出、quick-start 行为、仓库布局;
- 评估数据集、指标、结果、限制、证据状态、引用、联系、贡献路径。

为每个生成块加**一条 canonical 命令**与 `--check` 漂移检查(CI 可报告漂移,但不得发明/改写科学散文)。

## 7. 发布前核验
- 干净环境跑 quick start/安装(可行时);
- 生成块二次运行幂等 + 漂移检查;
- 本地链接、锚点、图片路径、抽查外链;
- 动态计数/版本 vs 其权威源;
- 引用的报告与 claim-binding 字段;
- 相关测试、bundle/build 校验、`git diff --check`;
- staged-scope 审查、secret 扫描、大文件扫描、绝对本地路径扫描。
- 有 `scripts/audit_readme.py <README>` 就跑它(marker/本地链接/凭据模式/Windows 路径),作为聚焦门禁。

## 8. 安全发布
- 只 stage 显式文件;优先**focused branch + PR**(需要保护/评审时)。
- 若用户已建立"接受的工作合并到默认分支"的偏好,在必需检查通过后合并,验证远程默认分支 SHA 与渲染 README。
- 用 fast-forward 或仓库常规合并;绝不 force-push、覆盖未知工作、绕过必需检查。

## 9. 报告
报告:改动的 README 段落、canonical 来源、命令与测试结果、merge/remote 状态、仍**未验证**的 claims、下次维护触发点。

---

## 本项目( MetaWingman )特别规则
- 证据默认写 `research/`,注明**日期 + 版本**(file + receipt sha256);任何结果声明必须绑定到该版本化文件。
- README 的机制事实(组件数/测试数/结果文件)与人工内容分离;人工复核定位、解释、限制、科学结论。
- 参考仓库见 `docs/github-repo-survey-2026-08-19.md`(社区 survey);主题契约见 `docs/README_MAINTENANCE.md`。
- 不写内部代号、服务器凭据、本地绝对路径、无法服务用户的操作历史。
