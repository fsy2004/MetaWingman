# 评价步骤验证器组件预注册（2026-08-18）

R6 训练版组件的任务定义、数据、训练计划与验收。**训练尚未执行**；本文件
冻结任务与数据来源，训练启动前不得改动（改动需版本化修订）。

## 1. 任务

- 输入：appraisal-role 段落文本（来自 12k 语料，`target.section_role ==
  "appraisal"`）。
- 输出：RoB 域 6 分类
  `{selection_bias, performance_bias, detection_bias, attrition_bias,
  reporting_bias, other}`。
- 定位：白皮书 R6 的"训练版验证器"——对规则版 `verify_appraisal_steps.py`
  的域判断步骤提供模型化判定；**只在小候选集（单段分类）上使用**（检索
  证据已证明 110M 模型的甜点区是判别而非开放检索）。

## 2. 数据（服务器已生成）

- 候选文件：`validation-output/training-corpus/appraisal-step-candidates.jsonl`
  （9,906 条）。
- 分布（实测）：selection 3,106 / other 6,298 / attrition 224 / reporting 101 /
  detection 90 / performance 87 / abstain 9（abstain 不参与训练）。
- 标签 = 确定性关键词规则（弱监督，`label_status:
  deterministic_weak_supervision_requires_independent_validation`）；**验收
  上限是规则一致性，不声称独立有效性**。
- 类别不均衡：训练 loss 用类权重（逆频率）；dev 报告宏 F1（不报告加权宏）。

## 3. 训练计划（冻结）

- 基座：BiomedBERT 110M（同现有组件，revision e1354b7a）。
- 配置：3 epochs、batch 8（有效 16 经梯度累积，显存 24GiB 约束）、lr 2e-5、
  bf16、seed 20260815、家族隔离切分（沿用 12k freeze 的 train/dev 家族）。
- 切分：candidates 按 family_id 归属 12k 冻结切分（train 家族 → train，dev
  家族 → dev），不重切。

## 4. 验收

1. dev 宏 F1 与规则标签的一致性（预期高，属循环一致；仅作管线健全检查）；
2. 独立抽检：预留 100 条 dev 候选做**人工盲评**（域判断 gold），报告模型 vs
   规则 vs 人工——这是该组件唯一能产生独立证据的环节，执行前冻结抽检集；
3. 与规则版验证器集成后，跑既有 `verify_appraisal_steps.py` 全链路回归。

## 5. 复现

- 候选生成脚本 `metawingman/scripts/build_appraisal_step_candidates.py`（已入库）；
- 训练走既有 `run_component_training.py` 管线（需为新组件扩展 job 生成）或
  独立脚本；receipt/checkpoint 哈希按既有规范归档。
