# Stage B 协作消融实验设计（2026-03-30）

> 目的: 补齐“单智能体复核 vs 同质多智能体复核 vs 异质多智能体复核”的证据链，支持《面向互联网基础资源的大模型多智能体协作与可信认知标识技术研究》的项目评审、论文主表与答辩表述。
>
> 定位: 本文不是新算法设计页，而是标准化消融实验设计页。核心目标不是再改系统架构，而是在**相同输入契约**下，证明异质性多智能体协作是否优于单智能体与同质多智能体。
>
> 历史设计分支: `codex/stage-b-ablation-experiments`
>
> 2026-03-31 状态补充:
> - 旧 `single / homogeneous / heterogeneous_v2` 已完成。
> - `heterogeneous_v3` 与跨 split gate replay 的结果，已单独整理到 `29_stage_b_retrospective_eval_and_registry.md`。
> - 本页保留为“消融设计页”，不承担最终结果汇总职能。

## 1. 要回答的核心问题
- `Stage A llm v2` 已经证明自己是当前更强的 fast path。
- `Stage B packetv2` 已在多个 split 上显示出小幅、零回归优先的 primary 增益。
- 当前仍缺少的关键证据不是“`Stage B` 能否工作”，而是:
  - 第二次 LLM 复核本身是否有价值
  - 多个 reviewer 但不分工，是否已经足够
  - 真正的异质角色分工，是否比同质多 reviewer 更强
  - `Stage A uncertainty handoff` 是否是 `Stage B` 取得增益的必要条件

## 2. 设计原则

### 2.1 同输入，不换系统
- 所有 `Stage B` 消融都统一消费:
  - `Stage R` 冻结候选集
  - `Stage A llm v2` trace
  - `Stage A uncertainty handoff`
  - `Stage B packet v2`
- 不采用 `R -> B` 直连作为当前体系主消融。
- 理由:
  - 当前 `Stage B packetv2` 明确依赖 `Stage A` 下传的语义摘要与困惑点
  - 拿掉 `Stage A` 会改变 `Stage B` 的输入契约，不再是当前系统的干净消融

### 2.2 同预算，同 provider
- 所有 `Stage B` 消融统一使用同一 provider、同一模型、同一 prompt 版本族、同一最大 token 预算和同一 controller。
- 不允许通过“某组调用更多轮次、更多 tokens、更多模型差异”制造虚假增益。

### 2.3 同 controller，不比较 runtime knob
- 当前要比较的是协作结构，不是:
  - `temperature`
  - `max_tokens`
  - `timeout`
  - `parallelism`
- runtime knob 继续固定，只记为 appendix / ablation 附表。

## 3. 标准对照矩阵

### 3.1 系统级基线
1. `R -> A_clean`
2. `R -> A_llm_v2`

作用:
- 给出 deterministic fast path 与强单智能体 fast path 的系统级对照。
- 其中 `A_llm_v2` 是后续所有 `Stage B` 消融的共同上游。

### 3.2 Stage B 协作消融主表
3. `R -> A_llm_v2 -> B_single`
4. `R -> A_llm_v2 -> B_homogeneous`
5. `R -> A_llm_v2 -> B_heterogeneous`
6. `R -> A_llm_v2 -> B_heterogeneous_no_handoff`

这 4 组是当前最关键的证据链。

## 4. 四组 Stage B 变体定义

### 4.1 `B_single`
- 一个 reviewer。
- reviewer 类型: `GeneralReviewer`
- 输入:
  - 完整 `packet v2`
- 输出:
  - 与当前 `Stage B` 相同的结构化 proposal
- 作用:
  - 回答“第二次 LLM 复核本身”有没有价值

### 4.2 `B_homogeneous`
- 四个 reviewer。
- reviewer 类型:
  - `GeneralReviewer_1`
  - `GeneralReviewer_2`
  - `GeneralReviewer_3`
  - `GeneralReviewer_4`
- 差异:
  - 编号不同
  - 调用独立
- 不同点严格限制为:
  - 独立采样噪声
  - 独立调用顺序
- 相同点:
  - 相同 system prompt
  - 相同 user prompt
  - 相同角色职责
  - 相同输入 packet
- 作用:
  - 回答“光靠多 reviewer 投票”能否替代真正的角色异质性

### 4.3 `B_heterogeneous`
- 四个 reviewer。
- reviewer 类型采用当前主线角色:
  - `DomainExpert`
  - `GovernanceRisk`
  - `HierarchyResolver`
  - `UserPreference`
- 输入:
  - 完整 `packet v2`
- 作用:
  - 当前主系统慢路径
  - 用来证明异质性角色分工是否比 `B_homogeneous` 更强

### 4.4 `B_heterogeneous_no_handoff`
- reviewer 角色与 `B_heterogeneous` 相同。
- 但剔除 `Stage A llm` 下传的:
  - `primary_rationale`
  - `secondary_rationale`
  - `challenger_notes`
  - `uncertainty_summary`
  - `confusion_points`
  - `override_sensitivity`
- 保留:
  - `Stage R` 候选
  - `Stage A` 的 primary / related / score 结果
  - `Stage B` 其他 packet v2 字段
- 作用:
  - 回答 `uncertainty handoff` 是否是 `Stage B` 提升的关键来源

## 5. 为什么不把 `Stage A llm` 当成 `B_single`
- `Stage A llm` 是一审主裁决器。
- `B_single` 是二审复核器。
- 两者差别不只是“agent 数量”，还包括:
  - 输入内容
  - 输出边界
  - 是否拿到 `Stage A` 的 uncertainty handoff
  - 是否处在 slow path 场景
- 因此:
  - `Stage A llm` 可以作为系统级单智能体基线
  - 但不能代替 `B_single` 这个慢路径单智能体消融

## 6. 标准化控制条件

### 6.1 固定不变
- provider
- model
- `Stage R` snapshot
- `Stage A llm v2` version
- `Stage B packet v2` schema
- candidate shortlist / controller 规则
- max rounds
- output schema

### 6.2 只允许变化的因素
- reviewer 数量
- reviewer 是否异质
- uncertainty handoff 是否可见

### 6.3 controller 比较口径
- 不使用绝对票数作为跨配置比较主指标。
- 对 `B_single / B_homogeneous / B_heterogeneous` 的对比，以以下为主:
  - `support_ratio`
  - `override authorization satisfied`
  - `fix / regress / net gain`
- 理由:
  - `1` 个 reviewer 与 `4` 个 reviewer 无法用绝对票数公平对齐

## 7. 评测指标

### 7.1 系统级主指标
- `PrimaryAcc@1`
- `AcceptablePrimary@1`
- `RelatedRecall`
- `RelatedPrecision`

### 7.2 Stage B 协作指标
- `StageBOverrideRate`
- `stage_b_changed_primary`
- `stage_b_fixed_primary`
- `stage_b_regressed_primary`
- `NetGain = fixed - regressed`
- `slow_path_rate`
- `final_decision_source_counts`

### 7.3 分桶指标
必须按以下 bucket 分开报:
- `ordinary_fast_path`
- `sibling_hierarchy`
- `primary_secondary_disentanglement`
- `cross_domain_overlap`
- `high_risk_governance`

重点观察:
- `primary_secondary_disentanglement`
- `cross_domain_overlap`
- `sibling_hierarchy`
- `high_risk_governance`

### 7.4 成本与稳定性
- mean / p95 latency
- total model calls
- total output tokens
- per-sample slow-path token cost
- trace completeness / schema validity

## 8. 预期证据链

### 8.1 若要支持“异质性多智能体协作有效”
至少应满足以下其中两条:
- `B_heterogeneous` 的 `PrimaryAcc@1` 高于 `B_single`
- `B_heterogeneous` 的 `NetGain` 高于 `B_homogeneous`
- `B_heterogeneous` 在 hard buckets 上的增益高于 `B_homogeneous`
- `B_heterogeneous_no_handoff` 明显弱于 `B_heterogeneous`

### 8.2 若结果不满足
- 若 `B_homogeneous ≈ B_heterogeneous`
  - 说明多 reviewer 可能有价值，但异质角色分工证据不足
- 若 `B_single ≈ B_heterogeneous`
  - 说明主要增益来自“第二次复核”，而非协作结构
- 若 `B_heterogeneous_no_handoff ≈ B_heterogeneous`
  - 说明当前 `uncertainty handoff` 价值不足

## 9. 推荐运行顺序
1. `holdout3`
   - 当前最新 fresh split，优先级最高
2. `holdout2`
   - 对照先前已知正增益
3. `challenge`
   - 验证异质协作在更难 revealed split 上是否仍成立
4. `blind`
   - 用作保守性检查，不作为主结论来源

## 10. 报告与论文里的表述方式
- 主表不要只写“ours vs baseline”。
- 应写成:
  - `A_clean`
  - `A_llm_v2`
  - `A_llm_v2 + B_single`
  - `A_llm_v2 + B_homogeneous`
  - `A_llm_v2 + B_heterogeneous`
  - `A_llm_v2 + B_heterogeneous_no_handoff`
- 这样 reviewer 才能看见:
  - 强单智能体 fast path
  - 单智能体二审
  - 同质多 reviewer
  - 异质多 reviewer
  - uncertainty handoff 的作用

## 11. 当前执行判断
- 当前 `holdout3` 已证明:
  - `A_llm_v2` 明显强于 `A_clean`
  - `Stage B` 对 `A_llm_v2` 存在小幅、零回归 primary 增益
- 因此，下一步最值得补的不是继续调 runtime，而是完成这组协作消融。
- 这组消融若成立，能够直接补齐项目题目中“多智能体协作”部分最薄弱的证据链。
