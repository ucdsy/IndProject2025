# 评测协议与指标 v1（Stage R / A / B）

> 目的: 把“不会每次都慢、可以实装”的质疑提前用指标回答掉。
> 结项最小闭环: 3 张表（主表/消融/成本稳定性）+ 2 个可复现案例轨迹

## 1. 系统分层（必须在 PPT 里画一张图）
- Stage R（命名空间召回）:
  - 方式: 命名空间节点描述上的词法检索/元数据检索/向量检索（v1 可先用轻量 lexical+metadata，接口预留 dense）
  - 输出: `fqdn_candidates`（Top-K），其主表分布应接近“query 对 namespace descriptors 检索后自然出现的候选”，而不是随机拼装噪声
- Stage A（快路径决策）:
  - 单智能体在候选集中给出 `primary + related` 路由，并输出 `confidence` 与 `constraint_check`
  - 若通过触发规则，则直接返回（不跑多智能体）
- Stage B（慢路径共识）:
  - 多角色异质生成 + 多轮交互 + 反馈函数打分 + 收敛
  - 输出 `selected_primary_fqdn + selected_related_fqdns + routing_trace`（可信标识/行为链核心证据）
  - 结果写入缓存/表项，后续同类请求可走 Stage A

Stage C（demo 必备，不进入主表评测）:
- 在 `selected_primary_fqdn` 下发现候选 `agent_fqdn`（`{agent_code}.agent.{routing_fqdn}`），基于在线状态/公平曝光等可解释打分选最终执行者。
- 输出建议包含 score breakdown（例如 `final/base/health/fair/provider_fair`），便于审计与复现。

主表与压力测试的边界:
- 主表只使用“query 诱导的混淆候选”。
- 如果需要展示鲁棒性上限，可单独报告 `adversarial_negatives` 压测结果，但不得与主表混合解释“线上可用性”。

数据与快照边界:
- gold 数据集不手工提供 `fqdn_candidates`
- `fqdn_candidates` 由 Stage R 在线生成
- 若要公平比较多个决策器，可先运行固定版本 Stage R，再冻结一份 `candidate snapshot`

## 2. 触发规则（Stage A -> Stage B）
v1 用可解释的规则触发，便于答辩:
- `low_confidence`: `confidence < tau`（tau 可取 0.55/0.6，后续调参）
- `small_margin`: `top1_score - top2_score < delta`
- `constraint_failed`: 约束检查失败（格式/候选/治理规则等）
- `high_risk`: 候选或上下文触发高风险标签（如 `security.*`）
- `multi_intent_conflict`: `primary` 与 `related` 之间存在强竞争且 coverage 不足

必须统计:
- `escalation_rate`（触发率）: 触发 Stage B 的样本比例

阈值策略（v1 推荐）:
- 把 `tau/delta` 当作超参，在 `dev` 上做小范围网格搜索，目标是把 `escalation_rate` 控制在合理区间（例如 15%-35%），并优先优化 `PrimaryAcc@1/ConstraintPassRate`。
- 最终采用的 `tau/delta` 必须写进复现日志与结项包（避免被质疑“阈值拍脑袋”）。

## 3. 对比设置（最少 2 个强基线 + 你的方法）
建议 v1 的“可验收对比集”:
- B1: Stage A-only（single-agent）
- B2: Stage B vote（多角色独立 + 投票，一轮）
- Ours-1: Stage B feedback-driven consensus（结构化提案/投票 + 反馈函数打分；非开放式 debate）
- Ours-2: Stage A->B gating（快慢路径，强调可实装）

可选（不作为 v1 blocker）:
- B3: Stage B multi-round w/o feedback（多轮但不计算 F，只做讨论/仲裁），用于隔离“多轮”与“反馈函数”的贡献（来得及就做，来不及不影响结项闭环）。

## 4. 指标（写进报告/论文，也写进结项 PPT）
### 4.1 质量（决策正确性）
- `PrimaryAcc@1`: `selected_primary_fqdn == ground_truth_fqdn`
- `AcceptablePrimary@1`（可选）: `selected_primary_fqdn in acceptable_fqdns`
- `PrimaryRecall@K`（Stage R 指标）: `ground_truth_fqdn in fqdn_candidates[:K]`
- `RelatedCoverage@K`（Stage R 指标）: `|relevant_fqdns ∩ fqdn_candidates[:K]| / |relevant_fqdns|`
- `UnionCoverage@K`（Stage R 指标）: `|({ground_truth_fqdn} ∪ relevant_fqdns) ∩ fqdn_candidates[:K]| / |{ground_truth_fqdn} ∪ relevant_fqdns|`
- `Validity`: 输出 fqdn 格式合法比例（且在命名空间中存在）

细粒度子集（只在 ground truth 含 `l3` 的样本上计算，用来防“太简略”的质疑）:
- `FineAcc@1`（l3 子集）: `selected_primary_fqdn == ground_truth_fqdn`
- `Acc_L2@1`（l3 子集，可选）: 忽略 `l3` 后，`selected_primary_l2.l1 == gt_l2.l1`
- `HierDistance`（l3 子集，可选）: 预测节点与真值节点在 taxonomy 树上的最短路径长度（edge distance）
  - 计算方式: 把 fqdn 映射到路径 `l1 -> l2 -> l3`（缺省层级就截断），distance = `len(p)+len(g)-2*len(lcp(p,g))`
  - 直观解释: 0=完全正确；1=只错在 `l3`；2/3=错到 `l2` 或跨域

多相关（可选，贴合“返回相关能力列表”的线上形态，建议放附录）:
- `RelevantRecall@K`: `relevant_fqdns ∩ routing_top_k[:K] != ∅` 或按覆盖率计算（按你数据集里 `relevant_fqdns` 的定义统一）
- `nDCG@K`（可选）: 如果你愿意给 `relevant_fqdns` 设定主次权重（graded relevance），可以加分；来不及就不做

### 4.2 约束与可控性
- `ConstraintPassRate`: 约束检查通过比例（必须从候选里选等）
- `HighRiskBlockRate`（可选）: 高风险样本是否被正确触发/正确路由

### 4.3 稳定性与可复现
- `DisagreementRate`: 同一 query 重复运行 N 次（不同 seed/温度），top1 不一致比例
- `ConvergenceSteps`: Stage B 的轮次、修订次数、分数边际提升

### 4.4 成本与时延
- `Latency_p50/p95`（或粗粒度均值也行）
- `CallsPerSample`（LLM 调用次数）
- `TokensPerSample`（或成本估算）
- `CostDelta`: 相对 Stage A-only 的成本增量

## 5. 三张表模板（v1）
### Table 1 主表（质量 + 约束）
列建议:
- 方法（B1/B2/B3/Ours）
- PrimaryAcc@1 / AcceptablePrimary@1
- RelevantRecall@K（推荐放进主表，体现“不是只选唯一 fqdn”）
- Validity / ConstraintPassRate
- DisagreementRate（可放到 Table 3）

可选附表（推荐放附录或备份页）:
- Table 1b（l3 子集）: FineAcc@1、Acc_L2@1、HierDistance_avg

### Table 2 消融（证明任务书每块有贡献）
行建议:
- Ours（完整）
- -heterogeneity
- -feedback
- -trust-trace（仅普通日志）
列建议: PrimaryAcc@1、RelevantRecall@K、ConstraintPassRate、Tokens/Latency

### Table 3 成本稳定性（回答“是不是堆调用”）
列建议:
- 方法
- escalation_rate（只对 A->B 有意义）
- Latency_p50/p95
- CallsPerSample / TokensPerSample
- DisagreementRate

## 6. 复现实验最小要求（结项必备）
- 每个 run 固定:
  - `namespace_version`
  - 数据集版本与 split
  - `stage_r_version`（若使用快照则记录 snapshot 版本）
  - 模型版本、提示版本、参数（temperature/seed）
  - 输出: JSONL trace + 汇总表（CSV/Markdown）
- 把“复现命令”写进结项包（评审看一眼就知道你不是 PPT 工程）
