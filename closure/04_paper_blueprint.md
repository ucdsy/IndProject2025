# 论文落地蓝图（把结项写成可投稿版本）

## 1. 一句话论文题目（可选）
- 面向智能体命名与寻址路由的多智能体反馈驱动共识与可审计轨迹框架
- Trust-Trace: Feedback-Driven Consensus with Tamper-Evident Traces for Multi-Agent Naming and Routing

## 2. “论文主线”建议（写作时别散）
1. **问题**: 单一大模型在标签体系/路由约束下不稳定且不可审计（同一 query 的候选 fqdn/能力标签选择会波动，过程不可复核）。
2. **方法**: 异质角色 + 反馈函数驱动的共识演化 + 轻量可信标识/行为链。
3. **证据**: 主表（质量）+ 稳定性 + 成本 + 审计能力。

## 3. 最小结果集（没有这些不建议投稿）
必须至少产出:
- Table 1: 主结果（single-agent / vote / debate / ours）在主指标上的对比
- Table 2: 消融（-heterogeneity / -feedback / -trust-id）
- Table 3: 成本（token/latency/调用次数）
- Figure 1: 系统架构图（生成-选择-共识-可信标识-可视化）
- Figure 2: Case study（展示 1 个样例的多轮轨迹与最终解释）

加分项:
- 固定 token budget 的质量对比曲线（反驳“堆调用”）
- 小规模跨任务/跨模型复现（泛化性）
- 人评一致性统计（解释质量/可控性）

## 4. 写作节奏（与 8 周结项计划对齐）
- Week 1-2: Introduction + Method（先写，边写边逼你把方法讲清楚）
- Week 3-6: Experiments（跑主表 + 消融 + 成本/稳定性）
- Week 7: Analysis/Case study（挑案例画图，把“共识演化”讲清楚）
- Week 8: Related work（最低可用版本）+ Limitations/Safety + 全文封版 PDF

结项后（可选）:
- 补齐 related work 与引用、补泛化 mini 表、改稿投稿

## 5. 与专利的关系（避免互相踩）
- 专利: 更强调“系统/流程/模块”与可落地的实施例。
- 论文: 更强调“实验对比 + 机制分析 + 可复现”。
- 共享素材: 架构图、流程图、数据结构图、实验表格（但对外披露注意内部敏感信息与脱敏）。

## 6. 当前结果口径补充（2026-03-23）
- `Stage B` 当前不应再写成“全局 accuracy booster”。
- 更准确的论文表述应为:
  - `Stage A` 负责 fast-path routing
  - `Stage B` 负责异质性多智能体 slow-path 审核/纠错尝试
  - 当前 revealed split 上存在 exploratory gain
  - fresh `holdout2` 上尚未证成稳定净增益
- 因此，若论文必须强调异质性多智能体协作框架，方法写作重点应转向:
  - `uncertainty handoff`
  - `semantic packet enrichment`
  - `candidate-internal evidence augmentation`
- 也就是说，后续方法节的主增量不再是继续堆 runtime knob，而是:
  - 把 `Stage A LLM` 的困惑点和语义摘要正式传给 `Stage B`
  - 让 `Stage B` 在候选内做更有信息量的复核
