# 两段式检索评测结果（2026-08-18）

评测对象：TF-IDF 召回 + 12k 重训 BiomedBERT 重排的两段式检索，与单段式基线对比。
数据：dev 10,882 查询 × 10,882 文档（`evidence_retrieval` / `development` 切分）。
本文件所有数字逐项取自服务端结果文件
`/root/autodl-tmp/two-stage-results.json`（本地副本
`validation-output/two-stage-2026-08-18/two-stage-results.json`，MD5
`b3d46487093303d0b53103c5ba5c89e7`，服务端与本地一致）。

## 结论摘要

1. **两段式未超过 TF-IDF 全库基线。** 最佳为 K=50 时 MRR **0.10298**，仍低于
   TF-IDF 全库 MRR **0.219944**（约为其 0.47 倍）。
2. **召回天花板（关键数字）**：K=50 / 100 / 200 时，正样本进入 TF-IDF top-K
   的比例仅 **42.4% / 47.1% / 52.0%** —— 近半数查询的正样本根本不在候选集内，
   任何重排器都无法挽救这部分查询。
3. **重排器在语料规模下是负贡献，且 K 越大越差**：MRR 随 K 递减
   （0.10298 → 0.0706 → 0.045952）。训练目标（每查询 1 正 + ≤3 硬负）使模型在
   小候选集上判别力强（候选集 MRR 0.962/0.933，见 training-run-report §14），
   但无法在几十上百个真实语料邻居中把正样本排到前面。
4. **复现校验通过**：重算单段 TF-IDF 0.219944 / 0.314832 / 0.170189 与已知
   0.220 / 0.315 / 0.170 一致；重算单段模型全库 0.004518 / 0.005973 / 0.000551
   与已知 0.00452 / 0.00597 / 0.00055 一致。

## 设置（与 mw-baseline-v3.py 完全一致）

- 语料：`/root/autodl-tmp/mw/validation-output/training-corpus/training-examples.jsonl`
- 查询构造：`instruction + " Review: " + review_title`（无 title 时仅 instruction）
- 正样本：查询 i 的正样本为 `dev_examples[i].input_text`；同族文档
  （`family_id` 相同且 j≠i）掩蔽为 -inf
- TF-IDF：`TfidfVectorizer(stop_words="english")`，拟合于查询集
- 重排模型：`/root/autodl-tmp/mw/validation-output/training-runs/evidence-retrieval/final`
  （12k 重训 BiomedBERT；CLS + L2 归一；查询 max_len 256、文档 512；点积排序）。
  实现上把全部 10,882 查询与文档各编码一次并缓存（与逐查询编码候选向量完全
  等价，仅省去冗余前向），总耗时 **124.6 s**（GPU cuda）。
- 指标语义：MRR = mean(1/rank)；R@10 / P@1 在全库排序（单段式）或重排后的
  top-K 列表（两段式）上计算；正样本不在候选集时计 rank 0（贡献 0）。

## 结果对比表

| 方法 | MRR | Recall@10 | Precision@1 |
|---|---|---|---|
| 单段 TF-IDF 全库（重算） | **0.219944** | **0.314832** | **0.170189** |
| 单段 12k 模型全库（重算） | 0.004518 | 0.005973 | 0.000551 |
| 两段式 K=50 | 0.10298 | 0.265484 | 0.03878 |
| 两段式 K=100 | 0.0706 | 0.188109 | 0.02132 |
| 两段式 K=200 | 0.045952 | 0.111009 | 0.011487 |

## 召回天花板（每 K 正样本是否在 TF-IDF top-K 内）

| K | n_positive_in_topk | n_positive_missing | recall_ceiling |
|---|---|---|---|
| 50 | 4617 | 6265 | 0.424279 |
| 100 | 5122 | 5760 | 0.470686 |
| 200 | 5663 | 5219 | 0.520401 |

解读：

- 即使 K=200 也只有 52.0% 查询的正样本被 TF-IDF 召回；其余 48.0% 是纯召回
  失败，重排无济于事。
- 对比 TF-IDF 全库 R@10 = 0.314832：31.5% 的查询正样本已排在全库前 10（必然
  在 top-200 内），意味着约 20.5 个百分点的查询，其正样本落在全库第 200 名
  之外——词汇重叠不足，需要更强的召回（BM25 变体 / SPLADE / 稠密检索），
  而非更大的 K。
- 重排器在已召回集内也把正样本往下压：K=50 时 R@10 0.265484（天花板
  0.424279），K=200 时 R@10 0.111009（天花板 0.520401）——增大的候选集带入
  的干扰项被重排器排到了正样本之前（MRR 随 K 单调下降的机制）。

## 结论 / 验收判定

- 验收标准（`next-steps-2026-08-18.md` P0#1：「dev 全库 MRR 超过 TF-IDF 基线
  （0.220）为最低目标」）**未达成**：两段式最佳 MRR 0.10298 < 0.219944。
- 瓶颈在**召回阶段**（天花板仅 42–52%），且当前重排器在语料规模下为负贡献。
- 按证据排序的下一步：(1) 替换召回（BM25/SPLADE/稠密）后重测天花板；
  (2) 以全库 in-batch 负样本重训重排器（24 GiB 显存受限，需分块负采样）；
  (3) cross-encoder 重排或在 top-K 内做更精细的排序学习。
- 与既有文档衔接：本结果落实 `training-run-report-2026-08-17.md` §14 的
  「two-stage retrieve-then-rank 设计」推测，并给出该设计的实测表现；
  关联 `hallucination-audit-2026-08-18.md` 两段式检索条目。

## 文件与溯源

| 项 | 路径 |
|---|---|
| 服务端评测脚本 | `/root/autodl-tmp/two-stage-retrieval-eval.py`（本地副本 `tools/two-stage-retrieval-eval.py`） |
| 服务端启动脚本（setsid 分离） | `/root/autodl-tmp/launch_two_stage.sh`（本地副本 `tools/launch_two_stage.sh`） |
| 结果 JSON（权威） | `/root/autodl-tmp/two-stage-results.json` → 本地 `validation-output/two-stage-2026-08-18/two-stage-results.json` |
| 运行日志 | `/root/autodl-tmp/two-stage-eval.log` |
| 评测耗时 | 124.6 s（含全量模型编码 43 s；重排各 K 约 1.1–1.3 s） |
