# MetaWingman 结果图清单 (Figure Checklist)

> **基于真实数据可用性规划** — 每张图的数据源均映射到 `validation-output/` 中的执行回执文件。
>
> **目标**: 5 张顶刊质量图（PDF + PNG），色盲安全配色，无误导轴截断。

---

## Figure 1: MetaWingman 架构总览图

- **类型**: 流程图/架构图（非数据图，用 TikZ 或 draw.io 生成）
- **内容**: 五组件 + 控制平面 + 数据流
  - Review Question Certificate → Socratic Checklist (10 stages) → Step-level Verifier → Audit Log + Meta-update Loop
  - Retrieval Components (Section Classifier + Evidence Retriever) 横跨 search/screening 阶段
  - Control Plane: protocol state / event ledger / human responsibility record
  - VAL ladder 标注在底部
- **数据源**: 稿件 §2.1 Table 1 + docs/architecture/
- **工具**: TikZ (LaTeX 原生) 或 draw.io + Python
- **状态**: 待生成

## Figure 2: 验证阶梯与组件指标

- **类型**: 组合图（条形图 + 表格嵌入）
- **内容**: 
  - (A) Section-role classifier per-class F1 (8 classes) — 条形图
    - 数据源: `validation-output/r2-ai-2026-08-18/scoring-results.json` → hosted_per_class_f1
    - 值: appraisal 0.947, certainty 1.0, eligibility 0.818, extraction 0.934, protocol 0.979, search 0.970, selection 0.906, synthesis 0.954
    - macro-F1: 0.9385 (hosted) / 1.0 (verifier) — 用 dev macro-F1 0.9995 (稿件报告值)
  - (B) Appraisal classifier generations comparison — 分组条形图
    - V3 dev macro-F1: 0.8500 (rule labels)
    - Rubric V2 dev macro-F1: 0.3777, weighted-F1: 0.871
    - VAL-2c kappa: 0.311 (95% CI 0.191–0.431)
  - (C) Cross-provider agreement — 混淆矩阵热力图或 kappa 条形图
    - kappa 0.8472 (95% CI 0.8221–0.8722, n=999)
    - F1 0.8816 vs 0.9385
- **数据源**: scoring-results.json, judge-report-smoke.json, audit-log.jsonl
- **工具**: Python matplotlib + seaborn + SciencePlots
- **配色**: colorblind-safe (Wong 2011 palette: #0072B2, #D55E00, #009E73, #CC79A7)
- **状态**: 待生成

## Figure 3: 检索比较 — BM25 vs Trained Retriever

- **类型**: 多面板组合图 (2 panels)
- **内容**:
  - (A) Single-stage retrieval MRR comparison — 条形图
    - BM25: 0.2649, TF-IDF: 0.2199, Trained: 0.0045
    - 数据源: `validation-output/bm25-two-stage-results.json` → single_stage_*
  - (B) Two-stage MRR vs K (candidate set size) — 折线图
    - K=50: MRR 0.128, K=100: 0.090, K=200: 0.058
    - Recall ceiling: 0.430, 0.466, 0.507
    - 数据源: 同上 → two_stage_bm25_recall
- **数据源**: bm25-two-stage-results.json
- **工具**: Python matplotlib + SciencePlots
- **状态**: 待生成

## Figure 4: 重建验证 — Hodgkiss et al. 复现结果

- **类型**: 森林图 + 对比表
- **内容**:
  - (A) Forest plot: 16 RCT study-level effects + pooled estimate
    - 展示 MetaWingman 重建的 pooled MD (2.865) vs published (2.9)
    - 数据源: `validation-output/reconstruction-runs/sci-exercise/rep-1/execution-receipt.json`
    - 3 runs byte-identical
  - (B) Comparison table: 5 scored dimensions
    - Pooled MD: 2.865 vs 2.9 (±0.05) ✓
    - CI: 1.795–3.935 vs 1.8–3.9 ✓
    - I²: 92.67% vs 93% (±1.0pp) ✓
    - k: 16 vs 16 ✓
    - Egger p: 0.483 vs 0.54 ✓ (same side, non-significant)
  - (C) Three-run hash verification: 3 identical SHA-256 hashes
- **数据源**: execution-receipt.json, sealed-reference/reported-estimates.sealed.json
- **工具**: R forest plot (metafor) 或 Python matplotlib
- **状态**: 待生成

## Figure 5: VAL-3 筛选试点结果

- **类型**: 饼图/堆叠条形图 + 混淆矩阵
- **内容**:
  - (A) Screening decision distribution: include / exclude / abstain
    - Gold recall: 0.765 (114/149)
    - Abstention: dominant loss (26/149 = 17.4%)
    - 数据源: `validation-output/ag-rdt-corpus/val3-run-1/screening-runs.jsonl`
  - (B) Confusion matrix: AI decision vs gold label
    - TP, FP, FN, Abstain-Gold, TN
  - (C) Loss decomposition: false exclusion vs abstention
    - False exclusion: 9/149 = 6.0%
    - Abstention on gold: 26/149 = 17.4%
- **数据源**: screening-runs.jsonl (649 records, 149 gold)
- **工具**: Python matplotlib + seaborn
- **状态**: 待生成

---

## 配色规范

- 色盲安全: Wong (2011) Nature Methods palette
  - Blue: #0072B2
  - Vermillion: #D55E00
  - Green: #009E73
  - Pink: #CC79A7
  - Sky Blue: #56B4E9
  - Orange: #E69F00
  - Yellow: #F0E442
- 灰度预览: 所有图必须通过灰度打印测试
- 字体: Arial/Helvetica (science standard), 8pt minimum
- 输出: PDF (vector) + PNG (300 dpi raster)

## 数据溯源

每张图的 source data CSV 必须与图一同存放于 `validation-output/figures/source-data/`。
