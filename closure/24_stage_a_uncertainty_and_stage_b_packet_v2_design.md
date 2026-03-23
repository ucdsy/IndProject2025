# Stage A 不确定性下传与 Stage B Packet v2 设计（2026-03-23）

> 目的: 在不打破 `candidate-internal` 约束的前提下，为 `Stage B` 提供比当前分数摘要更强的语义输入。
>
> 背景: `Stage B relatedguard` 在 `dev / blind / challenge / holdout2` 上已完成一轮真实 provider 验证，但对 fresh holdout 的稳定纠错增益未证成。当前主要瓶颈不是 provider runtime，而是 `Stage B` 看到的 candidate packet 过薄、prompt 过硬。
>
> 当前状态说明:
> - 本文是当前方法设计页，不是统一结果页。
> - 已落地: `sa_llm_v2_20260323_uncertainty` 的 uncertainty handoff 字段，以及 `stage_b_v1_20260323_packetv2` 的 revealed 评测。
> - 尚未证明: `Stage B` 已稳定压过所有上游线路。
> - `Stage C` 本轮仍只保留为已定义但未实现的下一步工程闭环，不在本文展开外部 repo 联动细节。

## 1. 当前问题判断
- 当前 `Stage B` 的输入主要由:
  - `Stage A candidate_scores`
  - `Stage A query_packet / decision_packet`
  - `Stage R snapshot` 中的层级与 descriptor 信息
- 这套输入虽然满足候选内约束，但仍然过于偏向:
  - `score_a / score_related / primary_fit / hierarchy_fit` 等压缩分数
  - `primary_hits / secondary_hits / scene_hits` 等弱正证据
- 当前缺口不在“是否允许候选外新路由”，而在:
  - `Stage B` 看不到 `Stage A LLM` 的真实困惑点
  - `Stage B` 看不到 `Stage A LLM` 对 top challengers 的语义判断摘要
  - `Stage B` 看不到结构化负证据与竞争簇信息

## 2. 设计原则
- 继续坚持:
  - `candidate-internal`
  - 不允许发明候选外 fqdn
  - 不允许用 `Stage B` 掩盖 `Stage R miss`
- 允许放松的不是输出边界，而是:
  - prompt 的推理语气
  - 上游语义分析痕迹的下传
- 因此，`Stage B` 的正确升级方向是:
  - `hard output constraints`
  - `softer reasoning instructions`
  - `richer semantic packet`

## 3. Stage A LLM 应新增的下传字段
以下字段面向 `Stage B` 使用，不要求长篇 CoT，只要求短、受约束、可回放。

### 3.1 语义判断摘要
- `primary_rationale`
  - 1-2 句
  - 说明为什么当前 `selected_primary_fqdn` 最符合主任务
- `secondary_rationale`
  - 1 句
  - 若存在 `selected_related_fqdns`，说明为什么它们是 secondary 而非 primary

### 3.2 竞争者注释
- `challenger_notes`
  - 针对 top2/top3 challengers 的短注释列表
  - 每条应包含:
    - `fqdn`
    - `why_competitive`
    - `why_not_selected`

### 3.3 不确定性信息
- `uncertainty_summary`
  - 1-2 句
  - 直接说明当前为什么需要升级到 `Stage B`
- `confusion_points`
  - 固定枚举列表，建议允许:
    - `primary_vs_secondary_ambiguous`
    - `sibling_granularity_conflict`
    - `hierarchy_parent_child_conflict`
    - `cross_domain_overlap`
    - `insufficient_primary_cues`
    - `high_risk_uncertainty`
- `override_sensitivity`
  - 建议枚举:
    - `safe_to_override`
    - `needs_strong_evidence`
    - `prefer_related_recovery`

## 4. Stage B Packet v2 应新增的字段
`Stage B` 仍只看候选内对象，但 packet 不再只是一张分数表。

### 4.1 从 Stage A LLM 下传
- `stage_a_llm.primary_rationale`
- `stage_a_llm.secondary_rationale`
- `stage_a_llm.challenger_notes`
- `stage_a_llm.uncertainty_summary`
- `stage_a_llm.confusion_points`
- `stage_a_llm.override_sensitivity`

### 4.2 候选竞争簇
- `competition_clusters`
  - 显式列出:
    - sibling cluster
    - parent-child cluster
    - base-segment cluster
- 作用:
  - 帮助 `HierarchyResolver` 理解“谁和谁是真竞争”，而不是从散乱候选里自己猜

### 4.3 结构化负证据
- `negative_evidence_card`
  - 对每个重点候选给出短列表，建议字段:
    - `missing_primary_cues`
    - `secondary_only_signal`
    - `overspecific_risk`
    - `underspecific_risk`
    - `cross_domain_mismatch`

### 4.4 Secondary 恢复卡
- `secondary_recovery_card`
  - 对每个候选补:
    - `secondary_anchor_strength`
    - `cross_domain_secondary_ok`
    - `chain_duplicate_risk`
    - `can_only_be_related`

## 5. Prompt 调整原则
### 5.1 不改的部分
- 不改变:
  - 只能从给定 candidates 中输出 `proposal_primary_fqdn`
  - `proposal_related_fqdns` 不能包含 primary
  - 输出必须是结构化 JSON

### 5.2 需要放松的部分
- 将 prompt 中过硬的“只能/必须/不要”语气改为:
  - `请优先基于候选内证据判断`
  - `若证据充分，可以建议 override`
  - `请明确说明 incumbent 为什么不足，challenger 为什么更优`
- 目的不是放弃约束，而是减少 LLM 的“默认维持原判”锚定倾向

## 6. 明确不采用的方案
- 不采用自由 CoT 全文下传
  - 原因:
    - 不稳定
    - 难评测
    - 容易把幻觉下传到 `Stage B`
- 不采用候选外新 fqdn
  - 原因:
    - 会破坏 `Stage R / Stage B` 职责边界
    - 会让 `Stage B` 变成隐式重检索器
- 不采用只调 `temperature / timeout / max_tokens`
  - 原因:
    - 这些属于 runtime knob
    - 已证实只会引起边缘样本波动，不会解决 packet 过薄问题

## 7. 与现有实验历史的关系
- `Stage B v1.0 / relatedguard`
  - 证明过:
    - 在 revealed `challenge` 上存在小幅 exploratory gain
  - 暴露过:
    - 对 fresh holdout 没有稳定增益
- `Stage B v1.1 / v1.2 exploratory`
  - 说明单纯改 `override policy`、改 `obligation-style prompt`、改 runtime 参数，并不能稳定打开能力
- 因此，当前正式判断是:
  - 继续留在 `candidate-internal`
  - 但要把 `Stage B` 的输入从“分数摘要”升级为“语义摘要 + 竞争簇 + 负证据卡”

## 8. 对外报告建议
- 若用于报告或论文方法节，可将本设计表述为:
  - `Stage A uncertainty handoff`
  - `semantic packet enrichment for Stage B`
  - `candidate-internal evidence augmentation`
- 重点不要写成“放开 Stage B 自由发挥”，而应写成:
  - 在保留可审计边界的前提下，提高 `Stage B` 的语义可判性
