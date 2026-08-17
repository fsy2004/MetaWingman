# Revision Plan Grounded in Top-Journal Literature (2026-08-17)

> 评审面板（reviewer-panel-2026-08-17.md）的 R1-R8 修订路线图，逐条绑定
> 顶刊/顶会文献与可执行改动。原则：改动可验证、按证据门推进、不越权声明。

## R1 — 声明-证据对齐（CRITICAL）

- **文献**：OpenScholar（Nature 2025）的贡献表述纪律——系统论文按"已实现/
  已评估/已前瞻验证"分层报告，不把能力矩阵条目写成已验证能力；贡献叙事
  契约自带 claim ladder（"Now / After reconstruction / After held-out /
  After prospective"）。
- **改动**：README"项目现状"改为三级证据表——① 已执行（检索下载、确定性
  重算、R 综合、两个组件训练）；② 组件级评估（dev 规则一致性）；③ 设计级
  （筛选/RoB/GRADE/审稿/living = 类型化契约 + fixtures）。同步修订
  `system-capability-matrix.json` 的对外表述与 `top-journal-contribution-story.md`
  的 claim ladder 引用。**验证**：全文 grep 无"全流程可执行"类绝对表述。

## R2 — 验证臂（AI 标注 + 已发表文献对照）与措辞纪律（CRITICAL）

- **文献**：Zheng et al. NeurIPS 2023（LLM 判断不可替代独立人评——按
  `human-window-policy.md` 战略口径，本项目的验证 = AI 标注 + 与已发表综述
  决策对照，真实人工为可选）；时间切分重建协议（AI-only benchmark
  protocol）；Thomas et al. 2021 的漏检率报告范式。
- **改动**：① 200 条盲标任务由 AI 完成标注（复用 C3 全栈配置），与已有
  `published_expert_reference`（benchmark materials）逐条对照，报告一致率
  与分歧归因；② 完成前全仓措辞从"准确率/性能"改为"与弱标签的规则一致性"；
  ③ 披露声明模板随稿件输出（模糊口径，见 human-window-policy §2）。
- **验证**：AI 标注对照报告落盘 `validation-output/independent-validation/`。

## R3 — 筛选组件对标 Cochrane 范式（MAJOR）

- **文献**：Thomas, McDonald, Noel-Storr, et al., J Clin Epidemiol 2021
  （doi:10.1016/j.jclinepi.2020.11.003）——工作量削减 @ 近零漏检率的评估
  协议；其公开语料（Cochrane Crowd）可作为外部 sanity 集。
- **改动**：筛选准则组件的评估协议先于训练冻结：recall 优先阈值、人工
  复核工作量削减曲线、missed-studies 归因。训练数据 = 已发表综述纳排表
  （benchmark materials 的 carbon-pricing 包先行）+ 我们的弱监督。
- **验证**：协议文档 + 首个 recall-first 阈值报告。

## R4 — 区间估计与调参纪律（MAJOR）

- **文献**：paired bootstrap by review family（协议已定义）；统计报告标准
  （reviewer skill 的 statistical_reporting_standards：效应量、CI、多重比较
  红标）；可复现运行规范（ML 可复现清单，如 Pineau et al.）。
- **改动**：① 组件 dev 指标全部补 95% paired bootstrap CI（按 family 聚合）；
  ② 检索/分类各跑 3 seed，报均值±CI；③ 把"查询修订、硬负样本开关、指标
  重定义"等已发生决策补记入预注册日志（retrospective registration 声明）。
- **验证**：CI 计算脚本 + 报告表格更新。

## R5 — export 向量化（MAJOR）

- **文献**：ANN 负样本挖掘（ANCE, Xiong et al. ICLR 2021）与 token-overlap
  批处理（scikit-learn 稀疏矩阵 / FAISS）；目标 109k 样本 < 10 分钟。
- **改动**：general-medicine 大桶内改 numpy 批处理（TF-IDF 矩阵一次内积，
  替代逐对 set 交集），保持选择结果与现实现完全一致（同谓词同 top-3，用
  现有测试 + 服务器差分对拍验证）。
- **验证**：单测 + 服务器 109k 实测时长。

## R6 — 全流程蓝图优先级 1-3 落实（MAJOR）

- **文献**：PRM（Setlur et al. ICLR 2025，arXiv:2410.08146——分数门控而非
  裸预测，修复 F8）；conformal 弃权（Tayebati et al. AISTATS 2025，
  arXiv:2502.06884——风险控制阈值）；grammar-constrained decoding（outlines/
  Willard & Louf 2023——生成时约束替代事后修复）。
- **改动**：① 筛选组件（R3 协议 + 训练）；② 提取字段分类器；③ 检索组件
  加 PRM 式打分头（同弱标签数据训练，输出分数 + 阈值门 + 升级路径）。
- **验证**：各组件 TDD + dev 报告，指标按 R2/R4 纪律报告。

## R7 — pilot 补对照与成本区间（MINOR）

- **文献**：HELM（Liang et al. TMLR 2023）多指标报告纪律；Snell et al.
  arXiv:2408.03314 的成本-质量曲线；FrugalGPT 级联（Chen et al. 2023）。
- **改动**：C0 补 few-shot（3 示例）对照；C3 改为"verifier 分数 + 阈值门
  控"版本再跑一次；四配置补 95% CI（bootstrap over 200 样本）与单位质量
  成本（$ / F1点、$ / MRR点）。
- **验证**：pilot 报告 v2 落盘。

## R8 — 基线补全（MINOR）

- **文献**：DPR（Karpukhin et al. EMNLP 2020）的基线套件惯例；BM25
  （Anserini/Pyserini）。
- **改动**：加"未训练 BiomedBERT 随机头"（分类）与 BM25 全语料（检索）
  两行基线；服务器脚本已含 TF-IDF，补 BM25 与随机头即可。
- **验证**：基线表更新。

## 执行顺序

```
R1+R2（措辞与验证臂，立即） → R5（export 向量化，服务器空闲即做）
→ R4（CI 与多 seed，12k 重训后重跑） → R3+R6（筛选组件 + PRM verifier）
→ R7/R8（pilot/基线补全） → 全部完成后重跑评审面板（re-review 模式）
```
