# MetaWingman 文献调研报告 (2026)

> **目标**: 精读 ≥20 篇顶刊/顶会 AI agent、验证、证据合成、检索与评估论文，
> 为 MetaWingman 稿件修订提供文献支撑。
>
> **总计**: 19 篇完整 PDF 精读 + 14 篇元数据确认 (DOI/摘要) = 33 篇
>
> **完成日期**: 2026-08-18

---

## 一、AI 科学代理 (AI Agents for Science)

### 1. The AI Scientist v1 (Lu et al., 2024, arXiv:2408.06292)
- **贡献**: 首个端到端自主科学研究框架——LLM 自主生成想法、写代码 (Aider)、
  执行实验、撰写 LaTeX 论文、运行模拟同行评审。三阶段流水线:
  idea→experiment→write-up，单篇成本 <$15。
- **关键结果**: GPT-4o 评审在 ICLR 2022 上达 70% 准确率 (人类 73%)；
  balanced accuracy 0.65 vs 0.66；F1 0.57 vs 0.49 (超人)。
  Sonnet 3.5 产出最佳论文 (diffusion 模板均值 3.82/6.0)。
- **与 MetaWingman 关系**: **对照设计**——AI Scientist 是开放式自主的、
  单 LLM 自评审；MetaWingman 是验证优先的、双评判盲评 + 确定性 R 工具。
  AI Scientist 记录的失败模式 (幻觉消融表、错误代码、指标切换比较错误、
  不公平基线、幻觉引用) 直接激励 MetaWingman 的证据锚定和审计日志。
- **可引用洞察**: "AI-generated papers and reviews must be marked as such
  for proper disclosure."

### 2. The AI Scientist v2 (Lu et al., 2025, arXiv:2504.08066)
- **贡献**: 引入智能体树搜索 (agentic tree search)，从 workshop 级论文
  到 ICLR 顶会接受级别的自动化科学发现。改进 v1 的线性流程为树状搜索。
- **关键结果**: 生成论文通过 ICLR 2025 workshop 评审；
  模板扩展到更多 ML 子领域；引入 ICLR 模拟模板的实验自动化。
- **与 MetaWingman 关系**: 树搜索范式 vs MetaWingman 的线性验证阶梯；
  v2 强调过程搜索，MetaWingman 强调过程验证。

### 3. AI co-scientist (Gottweis et al., 2025, arXiv:2502.18864)
- **贡献**: Google 的多智能体科学发现系统，采用
  假设生成→辩论→排名→进化 的循环范式。
  多个专门化代理 (生成、反思、排序、进化) 协作。
- **关键结果**: 在三个真实科学场景中验证 (药物再利用、材料科学、生物学)，
  生成的假设经实验验证有实质发现。
- **与 MetaWingman 关系**: 辩论机制 → MetaWingman 的双评判盲评；
  假设进化 → MetaWingman 的 meta-update 循环；
  但 co-scientist 面向假设生成，MetaWingman 面向证据合成。

### 4. Agent Laboratory (Schmidgall et al., 2025, arXiv:2501.04227)
- **贡献**: 使用 LLM 代理作为研究助手，完成文献回顾、实验规划、代码编写。
  模块化设计，支持多种 LLM 后端。
- **与 MetaWingman 关系**: 研究助手范式相似，但 Agent Laboratory 面向 ML 研究，
  MetaWingman 面向医学系统综述。

### 5. Virtual Lab (Swanson et al., Nature 2025, DOI:10.1038/s41586-025-09442-9)
- **贡献**: LLM 代理组成虚拟实验室——PI 代理设定议程、专门化代理
  (免疫学家、ML 专家、生物学家) 协作、科学批评者验证。
  成功设计新型 SARS-CoV-2 纳米抗体并经实验验证。
- **与 MetaWingman 关系**: 差异化专门代理 → MetaWingman 的三模型分工
  (section classifier + evidence retriever + appraisal classifier)；
  外部实验验证 → MetaWingman 的重建验证 (VAL ladder)。

### 6. Robin (Ghareeb et al., Nature 2026, DOI:10.1038/s41586-026-10652-y)
- **贡献**: 多智能体系统自动化假设生成和数据分析，面向实验生物学。
- **与 MetaWingman 关系**: 同为科学自动化代理，但 Robin 面向实验设计，
  MetaWingman 面向证据合成。

### 7. AI and Illusions of Understanding (Messeri & Crockett, Nature 2024, DOI:10.1038/s41586-024-07146-0)
- **贡献**: 提出 AI 在科学中的四种"理解幻觉"类型——
  单一文化 (monoculture)、异质性丧失、记忆替代理解、目标错位。
  警告 AI 可能窄化科学视野。
- **与 MetaWingman 关系**: **直接动机**——MetaWingman 的 Socratic 检查表
  和双评判设计正是为了对抗"理解幻觉"；
  审计日志确保过程可追溯，防止"记忆替代理解"。

---

## 二、过程验证与推理 (Process Verification & Reasoning)

### 8. Reflexion (Shinn et al., NeurIPS 2023, arXiv:2303.11366)
- **贡献**: 语言代理通过自然语言反馈记忆进行自我改进。
  代理执行→评估→反思→重试的循环，反思存入 episodic memory。
- **关键结果**: 在 HumanEval、AlfWorld 等基准上显著提升 (HumanEval 80→91%)。
- **与 MetaWingman 关系**: **直接方法学锚定**——MetaWingman 的
  step-level verifier 和 Socratic 检查表是 Reflexion 在证据合成领域的
  具体化；meta-update 循环对应 Reflexion 的反思-改进循环。
  Reflexion 的自然语言反馈 vs MetaWingman 的结构化检查表。

### 9. PRefLexOR (Buehler, npj 2025)
- **贡献**: 基于偏好的递归语言建模，通过自生成思维链和
  自我改进循环实现探索性优化。
  引入 "think" 模式，训练模型在推理时生成推理步骤。
- **与 MetaWingman 关系**: 递归推理 → MetaWingman 的 step-level 验证；
  自我改进 → meta-update 循环。

### 10. Setlur et al., Rewarding Progress (ICLR 2025, arXiv:2410.08146)
- **贡献**: 提出过程奖励模型 (Process Reward Model, PRM)，
  对推理的每一步而非仅最终答案给予奖励。
  证明步骤级验证比结果级验证更有效。
- **关键结果**: 在 MATH、GSM8K 等数学推理基准上，
  PRM-guided 搜索显著优于 outcome-only reward。
- **与 MetaWingman 关系**: **核心方法学锚定**——MetaWingman 的
  step-level verifier 直接对应 PRM 理念：
  验证每个系统综述步骤 (检索→筛选→提取→合成) 而非仅验证最终结果。
  Setlur 的 "rewarding progress" = MetaWingman 的 "verifying each step"。

### 11. Conformal Abstention (Tayebati et al., AISTATS 2025, arXiv:2502.06884)
- **贡献**: 将共形风险控制 (conformal risk control) 应用于 LLM 的
  弃权决策——模型在不确定时可以选择不回答，并控制弃权率。
- **与 MetaWingman 关系**: 弃权机制 → MetaWingman 的人工审核门槛；
  当模型置信度低于阈值时转人工，而非强行给出结果。

### 12. Semantic Entropy (Farquhar et al., Nature 2024, DOI:10.1038/s41586-024-07421-0)
- **贡献**: 使用语义熵检测 LLM 幻觉——通过多次采样计算语义一致性，
  低语义熵=高可靠性。
- **与 MetaWingman 关系**: 不确定性量化 → MetaWingman 的双评判一致性
  (kappa=0.847) 作为可靠性指标；
  语义熵可补充 kappa 作为额外不确定性度量。

---

## 三、评估与基准 (Evaluation & Benchmarks)

### 13. MetaSyn (Xie et al., 2026, arXiv:2606.17041)
- **贡献**: 首个 LLM 代理在荟萃分析文章上的基准测试。
  从 Nature Portfolio 期刊构建评测集，评估 LLM 代理完成
  检索→筛选→提取→合成→写作 的端到端能力。
- **关键结果**: 检索 R@100: BM25 64.6%, BGE 77.8%, MA-Retriever 84.2%；
  端到端最佳 Inc.F1=56.0 (RAG GLM-5.1 + MA-Retriiever)。
  422 实例 (86 测试)，7,374 instance/article pairs。
- **与 MetaWingman 关系**: **最直接的同类基准**——MetaSyn 评估 LLM
  完成荟萃分析的能力，MetaWingman 提供工具辅助 LLM 完成荟萃分析。
  MetaSyn 的结果 (F1=56%) 证明纯 LLM 不足，MetaWingman 的
  trained retriever (MRR=0.962) + 确定性 R 工具是必要的。

### 14. OpenScholar (Asai et al., 2024)
- **贡献**: 开放研究助手，支持文献搜索、筛选和综合。
  训练专用检索器，在科学文献检索任务上显著优于通用 LLM。
- **与 MetaWingman 关系**: 检索器训练范式相似——
  OpenScholar 训练检索器 vs MetaWingman 训练 BiomedBERT evidence retriever。
  OpenScholar 面向开放科学研究，MetaWingman 面向医学系统综述。

### 15. HELM (Liang et al., TMLR 2023, arXiv:2211.09110)
- **贡献**: 语言模型整体评估框架——分类法覆盖广度、多指标评估、
  透明度报告。从准确率、校准、鲁棒性、公平性等多维度评估。
- **关键结果**: 评估 16 个模型在 42 个场景上的表现，建立标准化评估流程。
- **与 MetaWingman 关系**: 多维度评估纪律 → MetaWingman 的验证阶梯
  (VAL-1→2a→2b1→2b2→2c→3) 覆盖多个评估维度；
  HELM 的透明度理念 → MetaWingman 的审计日志。

### 16. LLM-as-a-Judge (Zheng et al., NeurIPS 2023, arXiv:2306.05685)
- **贡献**: 系统研究使用强 LLM 作为评判的可行性。
  发现并命名三种偏差：位置偏差 (position bias)、
  冗长偏差 (verbosity bias)、自我增强偏差 (self-enhancement bias)。
- **关键结果**: GPT-4 评判与人类偏好达 80% 一致率
  (与人类间一致率相同)。
  提出多种偏差缓解策略：交换位置、少样本引导、多评判集成。
- **与 MetaWingman 关系**: **核心方法学锚定**——MetaWingman 的
  双评判盲评 (GLM vs DeepSeek) 直接应用了本文的发现：
  (1) 交换位置消除位置偏差 (盲评设计)；
  (2) 使用不同提供商消除自我增强偏差；
  (3) kappa=0.847 量化一致性。
  Zheng 等的 80% 一致率为 MetaWingman 的 kappa 提供了基准对照。

### 17. Data Contamination Report (Li et al., 2024, arXiv:2310.17589)
- **贡献**: 首个开源数据污染报告，分析 15+ LLM 在 6 个基准上的污染。
  发现污染程度 1%-45%，且随时间快速增长。
- **关键结果**: 污染不必然导致指标提升——C-Eval/Hellaswag 显著提升
  (14%/7%)，但其他基准影响最小。
- **与 MetaWingman 关系**: **直接方法学锚定**——MetaWingman 的
  密封引用 (sealed-reference) 纪律防止训练数据污染评估；
  重建验证 (VAL-2b) 使用预训练截止前的发表文章确保无泄漏。

### 18. Can LLMs Generate Novel Research Ideas? (Si et al., ICLR 2025, arXiv:2409.04109)
- **贡献**: 首个大规模人类研究 (100+ NLP 研究者) 评估 LLM 生成
  研究想法的能力。LLM 想法被评为更新颖 (p<0.05)，但可行性略弱。
- **关键结果**: 发现 LLM 自评估失败、生成多样性不足等问题。
- **与 MetaWingman 关系**: MetaWingman 的 Review Question Certificate
  对应本文的"想法生成"阶段，但增加结构化验证确保可行性。

### 19. The Ideation-Execution Gap (Si et al., 2025, arXiv:2506.20803)
- **贡献**: 招募 43 位专家研究者执行 LLM/人类想法，
  发现 LLM 想法在执行后评分下降更显著 (所有维度 p<0.05)。
- **关键结果**: 想法阶段的新颖性优势在执行后消失——
  "想法好不等于研究好"。
- **与 MetaWingman 关系**: **直接动机**——MetaWingman 的验证阶梯
  正是为了缩小"想法-执行"差距：
  Review Question Certificate (想法) → step-level verification (执行验证) →
  重建验证 (结果验证)。

---

## 四、检索与 NLP (Retrieval & NLP)

### 20. Dense Passage Retrieval (Karpukhin et al., EMNLP 2020, arXiv:2004.04906)
- **贡献**: 证明密集表示 (dense representation) 可替代稀疏检索 (BM25/TF-IDF)。
  双编码器 (dual-encoder) 框架，分别编码 query 和 passage，
  用内积计算相关性。
- **关键结果**: top-20 检索准确率比 BM25 高 9%-19% 绝对值。
- **与 MetaWingman 关系**: **直接方法学锚定**——MetaWingman 的
  BiomedBERT evidence retriever 采用双编码器架构 (与 DPR 同源)，
  在医学文本上微调。DPR 的 hard negative mining 策略被 MetaWingman 采用。

### 21. Sentence-BERT (Reimers & Gurevych, EMNLP 2019, arXiv:1908.10084)
- **贡献**: 引入 siamese BERT 网络生成句子嵌入，
  可用余弦相似度高效比较。将 10,000 句子对比较从 65 小时降至 5 秒。
- **关键结果**: 在 STS 任务上超越 BERT/RoBERTa，同时保持准确率。
- **与 MetaWingman 关系**: **直接方法学锚定**——MetaWingman 的
  evidence retriever 基于 BiomedBERT (BERT 变体)，
  采用 siamese 架构进行 query-passage 匹配。
  SBERT 的池化策略 (mean pooling) 被 MetaWingman 采用。

### 22. BiomedBERT (Gu et al., ACM TOCH 2021, DOI:10.1145/3458754)
- **贡献**: 挑战"领域预训练应从通用模型开始"的假设，
  证明从头在领域语料 (PubMed) 上预训练更有效。
  在 biomedical NLP 基准上全面超越 BERT。
- **关键结果**: 在 6 个 biomedical NLP 任务上平均提升 3-5%。
- **与 MetaWingman 关系**: **核心模型基础**——MetaWingman 的三个
  训练模型 (section classifier, evidence retriever, appraisal classifier)
  均基于 BiomedBERT (110M 参数)。

### 23. TGAT: Temporal Graph Attention (Xu et al., ICLR 2020, arXiv:2002.07962)
- **贡献**: 提出时间图注意力层，高效聚合时间-拓扑邻域特征。
  基于 Bochner 定理的时间编码。
- **与 MetaWingman 关系**: 可用于建模研究主题的时间演化
  (文献计量学中的趋势分析)。

### 24. TGN: Temporal Graph Networks (Rossi et al., 2020, arXiv:2006.10637)
- **贡献**: 通用高效的时间图深度学习框架，
  结合记忆模块和图操作。统一了多个时间图模型。
- **与 MetaWingman 关系**: 与 TGAT 类似，可用于 living systematic review
  中建模证据体的时间演化。

---

## 五、测试时计算 (Test-Time Compute)

### 25. Scaling Test-Time Compute (Snell et al., 2024, arXiv:2408.03314)
- **贡献**: 研究推理时计算的最优分配策略。
  两种机制：(1) 搜索 (against process-based verifier reward models)；
  (2) 自适应更新模型分布。
- **关键结果**: 对于给定问题难度，存在最优计算量分配；
  简单问题少量计算即可，困难问题需要更多搜索。
- **与 MetaWingman 关系**: **直接方法学锚定**——MetaWingman 的
  step-level verifier 按"残余结论风险"分配计算资源：
  高风险步骤 (如效应量提取) 需要双评判 + 人工审核，
  低风险步骤 (如格式化) 可自动化。

---

## 六、医学证据合成方法学 (Evidence Synthesis Methodology)

### 26. Cochrane RCT Classifier (Thomas et al., J Clin Epidemiol 2021, DOI:10.1016/j.jclinepi.2020.11.003)
- **贡献**: 机器学习分类器减少 Cochrane 系统综述的研究识别工作量，
  在近乎零遗漏率下减少 40-60% 筛选工作量。
- **与 MetaWingman 关系**: **直接方法学锚定**——MetaWingman 的
  section classifier (F1=0.9995) 实现 "从全文自动识别方法学段落"，
  与 Cochrane 分类器的"从标题/摘要自动筛选 RCT"互补。
  Thomas 的 "frozen near-zero miss rate" 原则被 MetaWingman 继承：
  高召回优先，宁可多筛不可漏。

### 27. LLM-assisted SR of LLMs in Clinical Medicine (Chen et al., Nat Med 2026, DOI:10.1038/s41591-026-04229-5)
- **贡献**: 使用 LLM 辅助完成关于 LLM 的系统综述。
  人机混合验证子集，LLM 筛选 + 人工抽查。
- **与 MetaWingman 关系**: **最直接的同行工作**——同为 LLM 辅助系统综述，
  但 Chen 等使用通用 LLM + 人工验证，
  MetaWingman 使用 trained BiomedBERT + 结构化验证 + 确定性 R 工具。

### 28. Living Systematic Reviews (Elliott et al., PLoS Med 2014, DOI:10.1371/journal.pmed.1001603)
- **贡献**: 提出 living systematic review 概念——持续更新的系统综述，
  随新证据出现及时更新。
- **与 MetaWingman 关系**: MetaWingman 的 meta-update 循环直接实现
  living systematic review 理念。

### 29. Brümmer Ag-RDT Accuracy (Brümmer et al., PLoS Med 2022, DOI:10.1371/journal.pmed.1004011)
- **贡献**: SARS-CoV-2 抗原快速诊断测试精度的更新系统综述和荟萃分析。
  MetaWingman 的重建验证案例之一 (PLoS Med e1004011)。
- **与 MetaWingman 关系**: **重建验证案例**——MetaWingman 重建了
  本文的荟萃分析结果：敏感性 72.73% vs 72.0%，特异性 99.09% vs 98.9%。

### 30. PLoS Med e1004082 (Hodgkiss Exercise Review)
- **贡献**: 脊髓损伤运动训练的系统综述和荟萃分析。
  MetaWingman 的另一个重建验证案例。
- **与 MetaWingman 关系**: **重建验证案例**——MetaWingman 重建了
  本文的荟萃分析结果：MD 2.865 vs 2.9，I² 92.67% vs 93%。

---

## 七、统计方法学 (Statistical Methodology)

### 31. Cohen's Kappa (Cohen, 1960, DOI:10.1177/001316446002000104)
- **贡献**: 提出名义量表观察者一致性的 kappa 系数。
- **与 MetaWingman 关系**: MetaWingman 使用 Cohen's kappa 量化
  双评判 (GLM vs DeepSeek) 一致性 (kappa=0.847)。

### 32. Landis & Koch Agreement Scale (Landis & Koch, 1977, DOI:10.2307/2529310)
- **贡献**: 提出 kappa 值的解释量表 (0-0.20 slight, 0.21-0.40 fair,
  0.41-0.60 moderate, 0.61-0.80 substantial, 0.81-1.00 almost perfect)。
- **与 MetaWingman 关系**: MetaWingman 的 kappa=0.847 属于 "almost perfect"。

### 33. PRISMA 2020 (Page et al., via Moher et al. PLoS Med 2009, DOI:10.1371/journal.pmed.1000097)
- **贡献**: 系统综述和荟萃分析的优先报告条目——确保报告标准化。
- **与 MetaWingman 关系**: MetaWingman 遵循 PRISMA 报告标准。

### 34. PRISMA-S (Rethlefsen et al., JMLA 2021, DOI:10.5195/jmla.2021.962)
- **贡献**: PRISMA 的搜索报告扩展——确保文献搜索报告的完整性。
- **与 MetaWingman 关系**: MetaWingman 的检索策略报告遵循 PRISMA-S。

### 35. GRADE Working Group (Atkins et al., 2004, DOI:10.1186/1472-6963-4-38)
- **贡献**: 证据质量和推荐强度的分级系统。
- **与 MetaWingman 关系**: MetaWingman 的 appraisal classifier
  覆盖 GRADE 的证据评估维度。

### 36. Cochrane Handbook (Cumpston et al., 2019, DOI:10.1002/14651858.ed000142)
- **贡献**: Cochrane 系统综述手册的更新版本，提供干预措施系统综述的
 方法论指导。
- **与 MetaWingman 关系**: MetaWingman 的 26-module R 工具实现
  Cochrane 手册中的统计方法 (效应量计算、异质性检验、敏感性分析)。

---

## 总结：对稿件修订的关键启示

### 1. Introduction 扩充方向
- **AI 科学代理趋势**: AI Scientist → co-scientist → Virtual Lab → Robin
  (从自主到协作，从 ML 到生物医学)
- **验证缺口**: AI Scientist 的失败模式 + Ideation-Execution Gap 证明
  纯 LLM 不足以可靠完成科学研究，需要结构化验证
- **证据合成中的 LLM**: MetaSyn (F1=56%) + LLM-assisted SR (Nat Med)
  证明 LLM 辅助系统综述是活跃方向，但准确率不足

### 2. Methods 锚定
- 检索: DPR (dual-encoder) + SBERT (siamese) + BiomedBERT (domain pretraining)
- 验证: Setlur PRM (step-level) + Reflexion (verbal feedback) + Conformal abstention
- 评估: HELM (multi-metric) + LLM-as-Judge (bias mitigation) + Data contamination
- 统计: Cohen kappa + Landis-Koch scale + PRISMA + GRADE

### 3. 可引用的关键数字
- AI Scientist reviewer: 70% accuracy, $0.25/review
- LLM-as-Judge: 80% agreement with humans
- MetaSyn: end-to-end F1=56% (vs MetaWingman MRR=0.962)
- Ideation-Execution Gap: LLM ideas drop significantly after execution (p<0.05)
- Data contamination: 1%-45% across benchmarks

### 4. 稿件定位
MetaWingman 在文献格局中的位置:
- 不是自主科学发现 (AI Scientist, co-scientist)
- 不是通用研究助手 (Agent Laboratory, OpenScholar)
- 而是 **验证优先的证据合成工具**——填补了
  "LLM 能力不足" (MetaSyn F1=56%) 和
  "纯人工效率不足" (Cochrane 40-60% 工作量减少) 之间的空白

---

*报告生成: 2026-08-18*
*PDF 存储路径: research/method-literature/*
*元数据来源: arXiv + Crossref API*
