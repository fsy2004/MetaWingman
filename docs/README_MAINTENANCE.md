# README 写作与持续更新规范

MetaWingman 的主页先服务第一次到访的研究者，再服务安装者和贡献者。读者应在一分钟内看懂：产品定位、最短安装、十阶段工作流、人工责任边界和验证证据在哪。

## 固定结构

1. 名称、单句价值、动态徽章。
2. 三行内说明“是什么”和“适合谁”。
3. 可复制的安装与调用示例。
4. 工作流与能力地图。
5. 安全边界、验证状态和人类检查点。
6. 仓库结构、开发命令、核心文档、贡献和许可。

正文采用中文，保留关键英文术语；不维护一份逐段重复的英文镜像。段落写一个主题，主动句优先，数字紧邻其证据链接。

## 单一事实来源

- `metawingman/` 是 Skill 的 canonical source；`.agents/skills/` 与 `plugins/` 是生成物。
- `<!-- readme-metrics:* -->` 区块由 `scripts/update_readme.py` 从 canonical source、`toolkit/R` 和 Git 标签生成。
- 训练/验证数字来自 `docs/architecture/` 中的冻结报告，README 只保留理解边界所需的摘要。
- 新能力先更新源码、schema、测试和报告，再更新 README；主页不能先于实现宣布完成。

## 更新流程

```powershell
python .\scripts\update_readme.py
python .\scripts\update_readme.py --check
python -m unittest discover -s .\tests -p "test_readme_update.py" -v
python .\scripts\build_skill_bundle.py
python .\scripts\verify_skill_bundle.py .\.agents\skills\metawingman
git diff --check
```

CI 在 push、pull request 与每周计划任务中检查派生指标。发布、安装命令、canonical source、验证等级或主线文档变化时，维护者必须同步检查 README 的人工段落。

## 结构参照

本规范只借鉴信息架构：nf-core/rnaseq 的用法与输出导航、Scanpy 的短首屏、Snakemake 的文档入口、OpenAI Skills 的安装路径、metafor 的可运行示例、revtools 的任务导向说明。

- https://github.com/nf-core/rnaseq/blob/master/README.md
- https://github.com/scverse/scanpy/blob/main/README.md
- https://github.com/snakemake/snakemake/blob/main/README.md
- https://github.com/openai/skills/blob/main/README.md
- https://github.com/wviechtb/metafor/blob/master/README.md
- https://github.com/mjwestgate/revtools/blob/master/README.md
