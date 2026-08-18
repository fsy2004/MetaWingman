# MetaWingman 方法学创新白皮书：从"执行者"到"提问-推导-验证-反思-进化"的科学协作者（2026-08-18）

## 0. 理念总纲

顶刊趋势（本白皮书依据，均下载/精读）：AI 在科学中的角色正从"执行流水线"
转向"提出可审计的问题、显式推导、逐步验证、反思进步"的协作者。代表：

- **FirstResearch**（arXiv:2607.05682, 2026）：可审计研究问题形成——核心产物是
  **Research Question Certificate**（原始定义/假设/机制模型/矛盾张力/可证伪假设/
  最小决定性实验/预期观察/失败更新规则），消融证明证书核心贡献绝大部分质量
  （去证书后评分 4.76→0.92）。
- **AI co-scientist**（arXiv:2502.18864）：假设的生成-辩论-排名-进化。
- **PRefLexOR**（Nature npj, s44387-025-00003-z）：把"思考+反思"显式化为
  迭代推理与自改进科学推理。
- **Reflexion**（arXiv:2303.11366）：口头反馈记忆改进后续试验；**苏格拉底式
  提问框架**（Holub et al., arXiv 2026，见 LLM-Metacognition 综述）。
- **AI Scientist**（arXiv:2408.06292）/**AI Scientist-v2**（arXiv:2504.08066，
  agentic tree search）：端到端自动科研 + 自动评审。

MetaWingman 的北极星对应更新为：**系统综述/meta 的每个阶段都不是"跑工具"，
而是"先提问、显式推导、步骤验证、反思归档"**。人工仍是审核窗口（既有政策
不变）；AI 的能力边界由可审计性决定，而非输出字数。

## 1. 核心创新 ①：Review Question Certificate（选题证书）——学习顶刊思维选题

把 FirstResearch 的证书迁移到临床证据综合的选题环节（现有"时间与决策感知
选题引擎"的证据图/反对检索/冻结门之上，加一层**推导可审计性**）：

| 证书字段 | 临床证据综合对应物 |
|---|---|
| primitive definitions | PICOT 要素、暴露/结局的操作化定义、结局层级（patient-important vs surrogate） |
| first-principle assumptions | 临床前提（机制假设、人群同质性、效应修饰假设）、证据前提（可合并性判断依据） |
| mechanism model | 疾病机制模型：暴露→中间机制→结局的因果链与节点 |
| tension / contradiction | 临床矛盾或证据缺口：指南分歧、效应方向不一、人群异质性、证据过时 |
| research question | 综述问题（含各要素） |
| falsifiable hypothesis | 可证伪的效应假设（方向、幅度、异质性模式，能被证据拒绝） |
| minimal decisive test | 最小决定性检验：界定"什么证据组合能推翻假设"（如某结局的高质量 RCT 证据、剂量-反应方向） |
| expected observations | 预期观察（含更新阈值） |
| failure update rule | 失败更新规则：阴性/异质结果如何更新选题（降级为叙述综述、改亚组、终止） |
| novelty gate + repair | 联网比对既有综述/注册（ModSearch+Europe PMC+Cochrane/CRD）→ 缺口证据 → 时间窗 → 硬门：无缺口则拒绝或降级为 living update 子题；软修复：向边界条件收紧（阈值效应、人群×干预交互、失败区间） |

- 硬门规则（借鉴 FirstResearch）：可证伪观察非空、机制摘要非空、推导分≥阈值、
  可证伪分≥阈值；不满足 → 打回推导。
- 落地：`schemas/review_question_certificate.schema.json` + 选题阶段产出该证书
  （JSON，可审计），人类窗口审证书而非审长篇叙述。

## 2. 核心创新 ②：苏格拉底式阶段自问（Socratic stage reflection）——不只是工作，更是提问

每个十阶段阶段进入前，agent 先生成**该阶段的方法学关键问题清单**（如纳排：
"是否存在按语言/年份的偏倚风险？排除标准是否可能在证据图上制造选择性缺口？
亚组纳排是否与证书假设一致？"）；执行时**逐步作答**并记录；阶段结束做
Reflexion 式**口头反思**（偏差、意外、可改进项）写入阶段记忆。问题清单与
答案随 skill 版本化（learnable upgrades 的原料）。

- 问题来源三类：证书字段推导、方法学规范（Cochrane/PRISMA/GRADE 映射的检查
  问题）、上轮 audit log 的失败教训。
- 落地：`references/socratic-checklists/`（每阶段一个问题清单文件）+ 阶段 gate
  检查"清单是否逐项作答"。

## 3. 核心创新 ③：全流程步骤级验证链（PRM-style hard gates）+ 不确定性弃权

- 把 RoB/GRADE/提取等链拆成**步骤级**（域判断→信号问题→域风险→总体判断；
  每个信号问题=一个可验证步骤），每步有验证器（先规则/弱标签组件，后训练
  PRM 组件——Setlur ICLR'25 思路的组件级落地）。
- 双层 gate（FirstResearch 式）：硬门（必答、来源锚定、无缺失关键字段）+ 软
  修复（低置信度→复核/弃权）。验证器输出置信度；低于阈值 → abstention →
  人工窗口（与既有 abstention schema 接线）。
- 训练规划（"训练要大"）：评价步骤验证器 = 下一个 110M 组件（标签来自
  12k 语料的 appraisal 段落 + 弱监督规则）；纳排分类器同理（Cochrane RCT
  分类器范式）。

## 4. 核心创新 ④：Meta-update & audit log（进步机制）

每次执行产出 **audit log**（偏差、失败、修复、问题清单答案、证书更新），
由 meta 层总结为 skill/references 的更新提案（带出处）→ 人工/自动审 →
写入版本化文件（lifelong agents 方向，ICLR 2026 workshop）。已有的
`training-freeze-decisions.md` 修订模式推广到全 skill。

## 5. 科学严谨与可复现（贯穿约束）

- 每个数字/结论附确切来源（已固化的 GROUNDING 红线）；证书/清单/验证链全
  JSON 化、哈希化、时间封存（既有 receipt 机制扩展）。
- 评测：选题证书质量用盲评协议（FirstResearch 的双法官盲评协议可迁移：两个
  不同模型盲评证书质量，报告一致性）；阶段自问与验证链用时间切分重建对照
  已发表综述。
- 全部弱标签声明保持"dev/弱监督、非金标准"边界（既有政策不变）。

## 6. 训练与数据路线（"训练要大"）

1. 语料（2026-08-18 服务器实测）：`training-examples.jsonl` **109,028 例**
   （section-role 54,514 + evidence-retrieval 54,514；train 87,264 / dev
   21,764；标签全部为确定性弱监督，8.2 GB 含 7 个文档分片）；
2. 新组件：评价步骤验证器 ✅（6 域 RoB 分类 V3，dev macro-F1 0.8500）、
   纳排分类器（筛选切片规则引擎已落地，训练版待标签）、证书质量评判器
   （待盲评数据积累）——共用 BiomedBERT 基座与冻结管线；
3. 规模：有效 batch 16（梯度累积）；下一步负样本扩到全库 in-batch
   （需显存优化或双卡）；epochs 由弱标签收敛曲线决定（以 dev 为准，不做
   拍脑袋）；
4. 复现：全部 receipt/checkpoint 哈希归档（既有规范；首个重建案例已
   三重复跑通并评分通过）。

## 7. 实施顺序（自主推进）

1. `review_question_certificate.schema.json` + 选题证书生成器（LLM 配置 +
   novelty gate 联网比对）——P1 选题审计单的升级版；**已落地 + 冒烟通过**；
2. `socratic-checklists/` 十阶段问题清单 —— **已完成全十阶段**：topic /
   protocol / search / screening / extraction / appraisal / analysis /
   writing / reproducibility / update（每阶段 10 问，9 必答 + 1 可选项），
   门禁 `check_socratic_checklist.py --stage <stage>` 全覆盖；
3. R6 评价步骤验证器（规则版先行，训练版入组件管线）；**规则版 + 6 域训练
   组件 V3 已落地**（dev macro-F1 0.8500，规则一致性；VAL-2c 人类盲评抽检集
   已冻结待评分）；
4. audit log + meta-update 回路接入 skill 版本化流程；**已落地并实跑一条
   完整闭环**（教训记录 → 提案 → 应用 → 提交）；
5. 证书质量双法官盲评协议脚本。**已落地 + 双 provider 冒烟通过**。

## 8. 落地状态总览（2026-08-18，活文档）

| 创新/路线项 | 落地物 | 状态 | 声明边界 |
|---|---|---|---|
| ① RQC 选题证书 | `review_question_certificate.schema.json` + `generate_review_question_certificate.py` + 双法官盲评 `blind_judge_certificates.py` | ✅ 落地，冒烟通过（门禁通过、双 provider 盲评 4.0/4.4） | 推导链可审计；新颖性 verdict 不独立宣称 |
| ② 十阶段苏格拉底清单 | `references/socratic-checklists/`（10 阶段 × 10 问，9 必答）+ `check_socratic_checklist.py` 全门禁 | ✅ 全十阶段落地，回归通过 | 问题清单为方法学检查，非自动裁决 |
| ③ 步骤级验证器 | 规则版 `verify_appraisal_steps.py`（10 步，弃权/人工窗口）+ 6 域 RoB 分类组件 V3（BiomedBERT 110M） | ✅ 规则版 + 训练版落地：dev macro-F1 **0.8500**（规则一致性）；**VAL-2c 评分 kappa 0.311（95% CI 0.191–0.431）→ 按协议判定规则需修订并重冻结新一代；V4 训练推迟** | 弱标签规则一致性，非独立验证；kappa < 0.41 = 规则与准则判断不符 |
| ④ audit log + meta-update | `record_audit_log.py`（JSONL + 人工窗口应用 + 提交回填） | ✅ 实跑 3 条完整闭环（glm-5.3 教训、权重 bug、重建机制教训） | 提案带出处；应用经窗口记录 |
| ⑤ 检索/语料组件 | section-role（macro-F1 0.9995）+ evidence-retrieval（候选集 MRR 0.962）+ 开集检索方向实测 | ✅ 两组件训练完成；**开集检索定论：BM25 单阶段（dev MRR 0.2649，实测 2026-08-18）；训练重排器仅限 curated 候选集（开放语料负贡献）** | dev 弱标签；重排器非召回器；~50% 召回天花板为任务语义固有限制 |
| 复现机制 | VAL-1 晋升 + VAL-2b1 冻结 + VAL-2c 抽检 + 重建案例 harness + 首个案例 | ✅ **首个重建案例评分通过**（PLoS Medicine e1004082，R V̇O2peak 切片：MD 2.865 vs 2.9、I² 92.67% vs 93%、k=16 精确，3 次锁定重复） | 确定性 R 管线复算（同 metafor 引擎）；AI-only 端到端仍未跑 |
| 评测对标 | MetaSyn（arXiv:2606.17041v6）任务映射 | ✅ 15 项映射（covered 6/partial 7/gap 2） | 黄金语料接入待评估（HF 许可未核实） |
| 跨模型实证 | GLM glm-5.2 C3 与 DeepSeek C3-R2 同盲集对比 | ✅ **完成**（`glm-cross-provider-results-2026-08-18.md`）：section-role 0.9003 vs 0.9385；检索选择准确率 0.96 vs 0.93；跨 provider kappa **0.872（95% CI 0.848–0.896）**——提示栈的 provider 不变性高但非完美；GLM 仅 C3 执行（范围收缩已记录） | 弱标签一致性；跨 provider 一致≠科学验证 |

**待办主线**（详见 `next-steps-2026-08-18.md`）：GLM 结果整合 → VAL-2c
人工评分（kappa 决定规则天花板）→ ag-rdt 第二晋升（heiDATA 清单核实中）→
AI-only 端到端重建（VAL-3）。

## 9. 参考文献（已下载/精读）

1. Wang, Y. *FirstResearch: Auditable Question Formation for LLM Scientific
   Discovery Agents*. arXiv:2607.05682 (2026).（全文精读）
2. Gottweis et al. *Towards an AI co-scientist*. arXiv:2502.18864 (2025).
   （PDF 已下载 research/method-literature/）
3. Lu et al. *The AI Scientist*. arXiv:2408.06292 (2024).（PDF 已下载）
4. Yamada et al. *AI Scientist-v2*. arXiv:2504.08066 (2025).
5. Buehler. *PRefLexOR*. npj Materials/Science, s44387-025-00003-z.（PDF 已下载）
6. Shinn et al. *Reflexion*. arXiv:2303.11366 (2023).
7. Setlur et al. *Rewarding Progress: Scaling Automated Process Verifiers*.
   ICLR 2025.
8. Holub et al. *Reflecting in the Reflection: Integrating a Socratic
   Questioning Framework into Automated AI-Based Question Generation*.
   arXiv 2026（LLM-Metacognition 综述收录）.
9. Schmidgall et al. *Agent Laboratory*. arXiv:2501.04227 (2025).
10. Xie, A. et al. *MetaSyn: A Benchmark for LLM Agents on Meta-Analysis
    Articles from Nature Portfolio*. arXiv:2606.17041v6 (2026)
    （评测设计对标；任务映射见 research/benchmark-2606-17041-task-map.md）.

（PDF 存放：`research/method-literature/`，git 忽略、本地留档。）
