# 执行级规格与评审门槛 v1

> 目的: 把“语义拆解、快慢路径决策、下一跳发现、实验门槛”压缩进一份可执行规格，避免你在多份文档里来回跳。
> 定位: 这是冻结规格与约束边界文档。`closure/13_design_doc_agentdns_routing.md` 负责讲总设计，这份文档负责定义 contract 与评审门槛。

当前状态说明:
- 仓库中的旧 `bootstrap Stage R/A` 代码已从主干清理；历史结果只保留作过程记录。
- 当前这些前置工作已完成，clean `Stage R`、`Stage A clean`、`Stage A llm v2` 与 `Stage B packetv2` 均已落地。
- 因此，本文中的 `freeze / blind protocol / 重建顺序` 相关表述主要保留作冻结纪律说明，不再等同于当前实施顺序。

## 1. 总体边界
- 输入: `query`, `context`, `namespace_v1`, `agent_registry_snapshot`
- 输出:
  - `routing_top_k`
  - `selected_primary_fqdn`
  - `selected_related_fqdns`
  - `chosen_agent_fqdn`
  - `endpoint`
  - `stage_r_trace / routing_trace / selection_trace`
- 非目标:
  - 不生成最终业务答案
  - 不动态扩展 taxonomy
  - 不引入 bandit/RL

固定归因口径:
- `stage_r_miss`: `ground_truth_fqdn` 没进入 `fqdn_candidates`
- `decision_miss`: gt 在 candidates 内，但 Stage A/B 的 `primary/related` 决策有误
- `selection_miss`: `routing_fqdn` 正确，但 Stage C 选错执行者或无可用执行者

数据边界:
- gold 数据集只定义 `query/context/ground_truth_fqdn/relevant_fqdns/acceptable_fqdns`
- `fqdn_candidates` 是 Stage R 的运行时产物，不是金标样本字段
- 为了公平比较，可导出固定版本的 `candidate snapshot`，供不同 Stage A/B 方法共用
- canonical 化约束:
  - gold 数据集中的 fqdn 字段必须已经是 canonical `routing_fqdn`
  - descriptor 侧允许保留 `segments`，但工程消费一律通过 resolver 展开为 canonical catalog

历史冻结时的重建顺序（保留作纪律说明，不代表当前 live repo 的实施阶段）:
1. 先冻结正式 gold schema、split 纪律、blind protocol
2. 再冻结 descriptor/词典/行业术语表的独立来源
3. 只在上述前提下重做 clean `Stage R`
4. 基于冻结 snapshot 重做 clean `Stage A`
5. `Stage C` 与 `Stage B` 后置

## 2. Stage R：命名空间召回与候选构造
### 2.1 职责
- Stage R 不负责拍最终板。
- Stage R 负责:
  - 抽取可审计的语义证据
  - 在命名空间节点上做高召回检索
  - 构造高召回、可追溯来源的 `fqdn_candidates`

一句话定义:
- Stage R 的目标是“把 `{ground_truth_fqdn} ∪ relevant_fqdns` 尽量召回进候选集”，不是“从一开始就把唯一正确答案定死”。

### 2.2 语义证据结构
v1 固定以下槽位:
- `primary_action`
  - 示例: `apply`, `verify`, `issue`, `summarize`, `schedule`, `plan`, `check`, `lookup`
- `target_object`
  - 示例: `invoice`, `meeting`, `permit`, `policy`, `compliance`, `hotel`, `itinerary`
- `domain_hints[]`
  - 候选域: `gov`, `security`, `finance`, `productivity`, `travel`, `commerce`, `health`, `education`, `weather`
- `capability_hints[]`
  - 作为子树召回和排序的证据，不直接等于最终输出
- `segment_hints[]`
  - 只能使用 [07_namespace_v1.md](/Users/xizhuxizhu/Desktop/IndProj04/closure/07_namespace_v1.md) 中冻结的 `l3`
- `secondary_intents[]`
  - 主路由之外的相关诉求
- `risk_flags[]`
  - 示例: `regulated_service`, `high_risk_data`, `money_related`, `identity_related`
- `industry_context`
  - 示例: `enterprise_service`, `manufacturing`, `travel_consumer`
- `evidence_spans[]`
  - 直接来自 query 的触发短语，用于审计和错误分析

### 2.3 解析与召回策略
v1 使用“证据抽取 + 命名空间节点召回”的两层策略，避免把方法做成大段 `if-else`:
- Layer 1: 声明式证据抽取
  - 用小型词典/规则抓高精度显式信号
  - 作用是生成 `primary_action / target_object / secondary_intents / risk_flags / evidence_spans`
  - 这些规则是证据源，不是最终分类器
- Layer 2: 命名空间节点召回与打分
  - 检索对象是 `namespace descriptor` / `routing node profile`
  - 打分由词法匹配、槽位对齐、元数据命中、风险匹配、行业适配组成
  - 如时间允许，可在同一层增加 dense embedding 相似度；这是 Stage R 的实现细节，不另起新阶段

约束:
- Layer 1 只能输出固定字段和值
- Layer 1 不能直接生成新 `fqdn`
- Stage R 的第一跳检索对象不能是 agent card；A2A/Agent Card 只进入 Stage C

### 2.4 命名空间节点打分与层级读出
先对每个命名空间节点 `f` 计算:
```text
score_R(f) =
  a_lex * lexical_match(q, desc_f) +
  a_slot * slot_match(parse, schema_f) +
  a_meta * metadata_match(q, aliases_f, tags_f, examples_f) +
  a_risk * risk_alignment(q, f) +
  a_ind * industry_fit(q, f) +
  a_dense * dense_similarity(q, emb_f) -
  a_over * overspecific_penalty(f)
```

默认权重（v1，`a_dense` 可先取 0）:
- `a_lex=0.28`
- `a_slot=0.27`
- `a_meta=0.20`
- `a_risk=0.10`
- `a_ind=0.10`
- `a_dense=0.00`
- `a_over=0.05`

`L1/L2/L3` 不是先验硬分类结果，而是从高分节点聚合后的审计读出:
```text
score_l1(d) = max_{f in subtree(d)} score_R(f)
score_l2(c) = max_{f in subtree(c)} score_R(f)
```

`L3` 只在以下条件全部满足时展开:
- 该 `l2.l1` 启用了 `l3`
- `segment_hints` 命中冻结 allowed set
- query/context 明确提供了对应细分证据

否则一律回落到 `l2.l1.cn`。

### 2.5 候选构造算法
固定步骤:
1. `query/context -> semantic_parse`
2. 对 `namespace descriptors` 计算 `score_R(f)`，召回 top-N 节点
3. 聚合得到 top-L1/top-L2 子树分数，用于审计与回落
4. 仅对启用 `l3` 且有证据的子树展开到 `l3`
5. 保留 3-8 个强相关候选，要求尽量覆盖 `{ground_truth_fqdn} ∪ relevant_fqdns`
6. 基于 query 诱导的混淆源，加入 5-15 个混淆候选
7. 去重、排序，写入 `stage_r_trace`

说明:
- 第 5-6 步是 Stage R 的系统行为，不是数据标注行为。
- gold 数据集只要求 query 足以诱导出这些竞争关系，不手工预写 `fqdn_candidates`。
- 若要做可复现实验，可把第 7 步产物冻结成 `candidate snapshot`。

### 2.6 查询诱导的混淆候选规则
主表中的候选集必须模拟“同一个 query 经过真实 Stage R 检索后自然会一起出现什么”，而不是人工随机塞难题。

每个混淆候选都必须至少满足以下一条:
- 能被 `evidence_spans[]` 或 `secondary_intents[]` 解释
- 能被命名空间节点描述的字段重叠解释（`aliases/desc/tags/examples/risk_level`）
- 能被粗粒度/细粒度并存的回落规则解释

固定混淆来源:
- `C1_multi_intent`: query 自身含次要诉求
  - 例: “验真并判断能不能报销” 会同时诱导 `verify.invoice.finance.cn` 与 `reimburse.invoice.finance.cn`
- `C2_lexical_overlap`: 多个节点共享表面词或同义表达
  - 例: “备案/资质/办理清单” 会同时诱导 `permit.gov.cn` 与 `policy.gov.cn`
- `C3_sibling_competition`: 同子树兄弟节点竞争
  - 例: `summary.meeting.productivity.cn` 与 `action-items.meeting.productivity.cn`
- `C4_governance_fallback`: 风险/治理触发导致相关治理节点与粗粒度回落节点一起进入候选
  - 例: `data.compliance.security.cn` 与 `compliance.security.cn`、`risk.security.cn`
- `C5_cross_domain_overlap`: 跨域但对象词重叠
  - 例: 文档/会议/合规都可能提到“记录/整理/审查”

每条样本至少覆盖 2 类混淆来源，但禁止:
- 随机加入与 query 无证据关联的节点
- 为了拉高难度而加入明显不可能被 Stage R 检出的噪声

这些混淆候选的意义不是“人为搞难”本身，而是让后续决策层接受接近真实线上检索的输入分布，检验它是否真的学会:
- 区分主意图与次要诉求
- 区分同域相近能力
- 区分同能力不同细分
- 在高风险场景下遵守治理边界

示例:
- `verify.invoice.finance.cn`
  - `C1_multi_intent`: `reimburse.invoice.finance.cn`
  - `C3_sibling_competition`: `issue.invoice.finance.cn`
  - `C4_governance_fallback`: `invoice.finance.cn`
  - `C5_cross_domain_overlap`: `docs.productivity.cn`

线上/离线一致口径:
- 线上: Stage R 通过 query 对命名空间节点描述做结构化过滤 + 词法/语义匹配，自然得到一批相近候选。
- 离线: 数据集用同一套“query 诱导的混淆规则”模拟这批候选，保证评测题型与线上来源一致。
- 附录: 如果要做更强压力测试，可另建 `adversarial_negatives` split，但不得与主表混合汇报。

### 2.7 Stage R 轨迹字段
必须记录:
- `semantic_parse`
- `descriptor_scores`
- `subtree_scores`
- `recall_sources[]`
- `candidate_generation_rules[]`
- `confusion_sources[]`
- `candidate_recall_hit`（dev/test 运行时回填）

如需冻结评测输入，可额外导出:
- `candidate_snapshot[{id, stage_r_version, fqdn_candidates, confusion_sources}]`

### 2.8 Stage R 指标
必须单独评测:
- `L1Acc`
- `L2Acc`
- `L3Acc`（仅 `l3` 子集）
- `PrimaryRecall@5`
- `PrimaryRecall@10`
- `RelatedCoverage@5`
- `RelatedCoverage@10`
- `UnionCoverage@10`
- `OraclePrimary@K`

### 2.9 Stage R 错误桶
- `E0_parse`
- `E1_l1`
- `E2_l2`
- `E3_l3`
- `E4_candidate_miss`
- `E5_candidate_noise`
- `E6_unjustified_confusion`

### 2.10 Stage R 门槛
进入大规模编码前，目标至少为:
- `PrimaryRecall@10 >= 0.92`
- `UnionCoverage@10 >= 0.85`
- `L1Acc >= 0.90`
- `L2Acc >= 0.82`
- `l3` 子集 `PrimaryRecall@10 >= 0.90`

达不到就优先修 Stage R，不允许把问题甩给 Stage B。

## 3. Stage A/B：快慢路径决策
### 3.1 Stage A 职责
- 输入: `query`, `context`, `fqdn_candidates`, `stage_r_trace`
- 输出:
  - `routing_top_k`
  - `selected_primary_fqdn`
  - `selected_related_fqdns`
  - `confidence`
  - `margin`
  - `constraint_check`
  - `escalate_to_stage_b`

Stage A 是候选内的受约束排序器，不是开放式思考器。

输入来源说明:
- 正常运行时，`fqdn_candidates` 由 Stage R 在线生成。
- 复现实验或消融时，`fqdn_candidates` 可来自冻结的 `candidate snapshot`。

边界澄清:
- 如果 Stage R 已经把 gt 和主要 relevant 召回了，Stage A/B 的价值就在于“从多个相近候选中定对 primary，并保留正确的 related”。
- 如果 Stage R 没有召回 gt，Stage A/B 原则上不应该凭空发明新候选，否则会破坏误差归因和实验可信度。

### 3.2 Stage A 打分
```text
score_A(c) =
  a0 * S_stage_r(c) +
  a1 * S_slot_match(c) +
  a2 * S_context_fit(c) +
  a3 * S_specificity(c) -
  a4 * P_risk_mismatch(c) -
  a5 * P_constraint(c)
```

分量说明:
- `S_stage_r(c)`: Stage R 候选分
- `S_slot_match(c)`: `semantic_parse` 与 candidate metadata 的对齐程度
- `S_context_fit(c)`: 地点、行业、时间、预算、渠道等上下文一致性
- `S_specificity(c)`:
  - 有明确 `l3` 证据且命中时加分
  - 没有明确 `l3` 证据但 candidate 过细时轻微减分
- `P_risk_mismatch(c)`:
  - 高风险 query 却落到不具备治理/风险能力的节点时惩罚
- `P_constraint(c)`:
  - 格式不合法或不在候选集时重罚

默认权重:
- `a0=0.30`
- `a1=0.30`
- `a2=0.15`
- `a3=0.10`
- `a4=0.10`
- `a5=0.05`

### 3.3 置信度、角色与 Margin
primary 置信度必须可计算:
```text
p(c) = exp(score_A(c) / T) / sum_j exp(score_A(c_j) / T)
confidence = p(top1)
margin = p(top1) - p(top2)
```

默认:
- `T=1.0`

角色分配规则（v1）:
- `primary`: `top1`，且与 `primary_action + target_object` 最一致
- `related`: 与 `secondary_intents`、`coverage` 或可接受回落项一致的候选
- `fallback`: 粗粒度父节点或保底节点

`selected_related_fqdns` 生成规则（v1）:
- 最多保留 `m_rel=3`
- 候选需同时满足:
  - 不等于 `primary`
  - 命中 `secondary_intents` 或 `S_coverage(c) >= tau_cov`
  - `p(c) >= tau_rel`
- 默认:
  - `m_rel=3`
  - `tau_rel=0.12`
  - `tau_cov=0.50`

说明:
- `acceptable_fqdns` 是评测容错字段，不应在 Stage A 运行时直接参与打分，否则会泄漏金标。
- Stage A bootstrap 当前采用单独的 `confidence_temperature=0.25` 做触发标定；排序本身仍基于候选内 deterministic scoring。

### 3.4 Trigger Policy
触发 Stage B 的原因:
- `low_confidence`: `confidence < tau`
- `small_margin`: `margin < delta`
- `constraint_failed`
- `high_risk`
- `multi_intent_conflict`

调参目标:
- `escalation_rate` 控在 15%-35%
- 优先优化 `PrimaryAcc@1` 和 `ConstraintPassRate`
- 不允许为了“看起来快”而压低必要升级

bootstrap 配置（当前实现）:
- `temperature=1.0`
- `confidence_temperature=0.25`
- `tau=0.30`
- `delta=0.08`

### 3.5 Stage B 职责
Stage B 只处理:
- 低置信样本
- 高冲突样本
- 高风险样本
- 约束失败样本
- 多意图/coverage 不足样本

关键约束:
- Stage B 不能引入 `fqdn_candidates` 之外的新候选

否则 Stage B 会掩盖 Stage R 失败，实验无效。

### 3.6 角色设计
冻结 4 个角色:
- `DomainExpert`
- `GovernanceRisk`
- `HierarchyResolver`
- `UserPreference`

角色分工:
- `DomainExpert`: 主任务与能力归属
- `GovernanceRisk`: 风险/治理边界
- `HierarchyResolver`: 处理 `sibling / parent-child / base-segment` 的层级与粒度消歧
- `UserPreference`: 次要诉求和上下文偏好

### 3.7 角色消息结构
每轮每个角色必须输出:
```json
{
  "role": "DomainExpert",
  "proposal_primary_fqdn": "verify.invoice.finance.cn",
  "proposal_related_fqdns": ["reimburse.invoice.finance.cn"],
  "confidence": 0.78,
  "evidence": ["发票", "验真"],
  "objections": ["issue.invoice.finance.cn is for issuing, not verifying"]
}
```

### 3.8 共识策略
v1 固定为“结构化提案 + 反馈打分 + 可选第二轮修正”，不做开放式 debate。

Round 1:
- 所有角色独立提案
- 汇总候选集合
- 计算 `F(c)`

Round 2:
- 只围绕 top-2 候选修正
- 角色只能在 top-2 内改票

停止条件:
- `top1_confidence >= tau_b`
- 或 `F(top1) - F(top2) >= delta_b`
- 或达到 2 轮上限

默认:
- `tau_b=0.72`
- `delta_b=0.10`

### 3.9 反馈函数
```text
F(c) = w_task * S_task(c)
     + w_con * S_constraints(c)
     + w_pref * S_preference(c)
     + w_cov * S_coverage(c)
     - w_cost * S_cost(c)
     - w_risk * S_risk(c)
```

分量说明:
- `S_task`: 主任务匹配
- `S_constraints`: 规则满足度
- `S_preference`: context 和次要诉求适配度
- `S_coverage`: 对 `relevant_fqdns` / `secondary_intents` 的覆盖程度
- `S_cost`: 轮次和复杂度惩罚
- `S_risk`: 风险错配惩罚

默认权重:
- `w_task=0.30`
- `w_con=0.22`
- `w_pref=0.15`
- `w_cov=0.13`
- `w_cost=0.08`
- `w_risk=0.12`

### 3.10 Stage A/B 最小对比和消融
最小对比:
- `StageA-only`
- `Vote-1round`
- `StageB-no-feedback`
- `A->B-gating`

最小消融:
- `-heterogeneity`
- `-feedback`
- `-coverage_term`

### 3.11 Stage A/B 错误桶
- `D0_over_specific`
- `D1_under_specific`
- `D2_secondary_bias`
- `D2b_related_miss`
- `D3_risk_over_block`
- `D4_consensus_flip_error`
- `D5_consensus_repair`

### 3.12 Stage A/B 门槛
进入大实验前:
- `StageA-only` 必须稳定可跑
- `A->B-gating` 在 dev 上必须相对 `StageA-only` 有明确收益
- `escalation_rate` 必须受控

## 4. Stage C：下一跳发现
### 4.1 职责
- 输入: `selected_primary_fqdn`, `agent_registry_snapshot`
- 输出:
  - `top_k_agents`
  - `chosen_agent_fqdn`
  - `endpoint`
  - `selection_trace`

约束:
- Stage C 不能改写 `routing_fqdn`
- Stage C 不能再走 LLM
- Stage C 必须暴露结构化分数拆解

### 4.2 注册表最小字段
每个 agent 至少具备:
- `agent_fqdn`
- `routing_fqdn`
- `provider`
- `endpoint`
- `status`
- `last_heartbeat_at`
- `skills/tags`
- `input_schema`
- `output_schema`
- `exposure_count_agent`
- `exposure_count_provider`

### 4.3 打分函数
```text
base(a) = w_match * S_match(a)
        + w_schema * S_schema(a)
        + w_tag * S_tag(a)

health(a) = I(status=online) * exp(- age_seconds / T_half)

fair_agent(a) = 1 / sqrt(1 + exposure_count_agent(a))
fair_provider(a) = 1 / sqrt(1 + exposure_count_provider(provider(a)))

final(a) = base(a) * health(a) * fair_agent(a) * fair_provider(a)
```

默认参数:
- `w_match=0.55`
- `w_schema=0.25`
- `w_tag=0.20`
- `T_half=120`

### 4.4 打分分量
`S_match`:
- 只接受 exact `routing_fqdn` match
- 父级匹配在 v1 不进入候选

`S_schema`:
- 判断声明的输入输出 schema 是否覆盖当前请求所需字段
- v1 只做布尔/计数，不做复杂类型推断

`S_tag`:
- 判断 agent tags 是否命中 `semantic_parse` 中的关键槽位
- 示例:
  - `invoice.verify`
  - `meeting.summary`
  - `compliance.data`

### 4.5 平分时的固定决策顺序
当 `final` 接近时，固定顺序:
1. `health` 更高
2. `fair_provider` 更高
3. `agent_fqdn` 字典序更小

### 4.6 输出结构
```json
{
  "routing_fqdn": "verify.invoice.finance.cn",
  "top_k_agents": [
      {
        "agent_fqdn": "vendorB-invoice-verify-v2.agent.verify.invoice.finance.cn",
      "endpoint": "https://vendorb.example/api/invoice/verify",
      "base": 0.82,
      "health": 1.00,
      "fair_agent": 0.87,
      "fair_provider": 0.85,
      "final": 0.61
    }
  ],
  "chosen_agent_fqdn": "vendorB-invoice-verify-v2.agent.verify.invoice.finance.cn",
  "reason": "final=0.61=base0.82*health1.00*fair_agent0.87*fair_provider0.85"
}
```

### 4.7 Stage C 指标
Stage C 不进主表，但必须作为工程证据产出:
- `SelectionLatency_p50/p95`
- `ProviderCoverage`
- `ProviderMaxShare`
- `UnavailableAgentSkipRate`
- `TieRate`

### 4.8 Stage C 错误桶
- `S0_registry_missing`
- `S1_health_stale`
- `S2_fairness_over_penalty`
- `S3_schema_miss`

### 4.9 Stage C 门槛
- 每个 demo 用到的 `routing_fqdn` 至少有 2 个 candidate agents
- `SelectionLatency_p95` 必须显著低于 Stage B latency
- score breakdown 必须能在 UI 或 trace 中直接展示

## 5. 实验矩阵与评审门槛
### 5.1 主张-证据映射
每个主张都必须对应证据:
- `C1 Stage R 有效`
  - 证据: `L1Acc/L2Acc/L3Acc/PrimaryRecall@K/RelatedCoverage@K/UnionCoverage@K/OraclePrimary@K`
- `C2 Stage A/B 有效`
  - 证据: `PrimaryAcc@1/AcceptablePrimary@1/RelevantRecall@K/ConstraintPassRate/escalation_rate`
- `C3 Stage B 不是堆调用`
  - 证据: 相对 `StageA-only` 的收益 + `Latency/Calls/Tokens`
- `C4 Stage C 真落到真实地址`
  - 证据: `chosen_agent_fqdn -> endpoint` + `SelectionLatency` + provider fairness 指标
- `C5 可审计`
  - 证据: `trace completeness` + 至少 2 个完整案例

### 5.2 最小实验矩阵
必须跑:
- `B0 StageR-only`
- `B1 StageA-only`
- `B2 Vote-1round`
- `B3 StageB-no-feedback`
- `Ours A->B gating + StageC`

可选增强:
- `Ours + l3-subset analysis`
- `Ours + provider fairness appendix`

### 5.3 误差归因表
所有失败必须归到 3 层之一:
- `candidate layer`
  - gt 未进入 candidates
- `decision layer`
  - gt 在 candidates 内但路由选错
- `execution layer`
  - routing 正确但 next-hop 选错或不可用

报告里至少要有一张误差分布表:
- `stage_r_miss`
- `decision_miss`
- `selection_miss`

### 5.4 不允许的偷懒方式
- 不允许把 Stage B 当黑箱补丁，替 Stage R 擦屁股
- 不允许把第一跳做成 agent card 检索并冒充“命名空间路由”
- 不允许只报最终主表，不报 Stage R recall/coverage
- 不允许只有 routing，没有 `agent_fqdn -> endpoint`
- 不允许只有自然语言 reason，没有结构化分数
- 不允许把数据构造失败和模型决策失败混成一个数字

### 5.5 开工前评审门槛
开始大改代码前，必须冻结:
- namespace/l3 schema
- Stage R 规格
- Stage A/B 规格
- Stage C 规格
- experiment matrix

### 5.6 封版前评审门槛
结项封版前，必须满足:
- 3 张主表可复现
- 2 个完整 trace 案例可复现
- 1 个失败案例能清楚归因
- demo 全链路能展示:
  - `query`
  - `routing_top_k`
  - `selected_primary_fqdn`
  - `selected_related_fqdns`
  - `escalation_reasons`
  - `chosen_agent_fqdn`
  - `endpoint`
  - `score breakdown`
