# Stage B Minimal Bootstrap Plan（2026-03-17）

> 目的: 在冻结 `Stage A v1` 的前提下，明确 `Stage B` 的最小工程起步范围、接口、文件落点与执行顺序。
>
> 适用范围: `Stage B v0/v1` 代码脚手架、样本池、评测器与答辩实现计划。

## 1. 当前仓库状态

### 1.1 已有
- `Stage A -> Stage B` 触发字段已经存在:
  - `escalate_to_stage_b`
  - `escalation_reasons`
- `routing_run_trace.schema.json` 已为 `stage_b` 预留 object 位
- 文档已定义 `Stage B` 目标与机制:
  - `closure/13_design_doc_agentdns_routing.md`
  - `README.md`
  - `research-project/03_experiment-plan.md`

### 1.2 尚无
- 无 `src/.../stage_b_*.py`
- 无 `scripts/run_stage_b.py`
- 无 `tests/test_stage_b.py`
- 无正式 `Stage B` 样本池文件
- 无 `Stage B` evaluator / trace writer

结论:
- 当前 `Stage B` 还处于**设计完成、工程未开工**状态。

## 2. Stage B 的最小目标
- 不做开放式多轮自由 debate
- 不做开放检索
- 不做候选集外发明新路由
- 只处理 `Stage A` 已触发 escalation 的样本
- 只在 `Stage R` 冻结候选集内做更强的结构化共识裁决

最小成功标准:
- 能消费 `Stage A trace`
- 能输出结构化 `stage_b` 字段
- 能在一批 escalated 样本上给出可回放的共识结果
- 能独立评测 `Stage B` 对 `Stage A` 难例的修复情况

## 3. 推荐输入输出

### 3.1 输入
- `sample`
- `stage_r snapshot`
- `stage_a trace`
- `fqdn_candidates`
- `candidate_scores`
- `escalation_reasons`

### 3.2 输出
- `selected_primary_fqdn`
- `selected_related_fqdns`
- `consensus_confidence`
- `consensus_margin`
- `consensus_rounds`
- `agent_votes`
- `agent_rationales`
- `feedback_scores`
- `trust_trace`
- `constraint_check`

## 4. 推荐机制

### 4.1 不做开放 debate
理由:
- 不可控
- 不可复现
- 不利于日志化与答辩

### 4.2 做结构化多角色共识
最小角色集采用文档既有口径:
- `DomainExpert`
- `GovernanceRisk`
- `CostLatency`
- `UserPreference`

最小循环:
1. Round 1: 各角色在固定候选内给 `proposal_primary + proposal_related + confidence + rationale`
2. 聚合: 对 top candidates 计算结构化 `feedback score`
3. Round 2: 若 top1-top2 差距不足，则只围绕 top2 做一次修正
4. 终止: 达到 margin 阈值或轮次上限

## 5. 最小文件落点

### 5.1 代码
- `src/agentdns_routing/stage_b_consensus.py`
  - 核心共识逻辑
- `src/agentdns_routing/stage_b_eval.py`
  - 针对 Stage B trace 的评测器

### 5.2 脚本
- `scripts/run_stage_b.py`
  - 输入 `Stage A trace`
  - 输出 `Stage B trace` 与 summary

### 5.3 测试
- `tests/test_stage_b.py`
  - 先覆盖:
    - 候选内约束
    - 多角色投票结构合法性
    - 共识终止条件
    - chain duplicate / invalid fqdn 防护

### 5.4 数据
- `data/agentdns_routing/formal/stage_b_seed_pool.jsonl`
  - 初始只放 escalated 样本及其标签视图

## 6. 样本池建议

### 6.1 第一批主池
- 直接使用 blind 中所有 `Stage A escalated` 样本
- blind `escalation_rate = 0.4857`
- `35 * 0.4857 = 17`
- 因此第一批主池可直接取 `17` 条 blind escalated 样本

### 6.2 重点难例
- 必须单列这 `5` 条:
  - `formal_blind_000019`
  - `formal_blind_000021`
  - `formal_blind_000024`
  - `formal_blind_000026`
  - `formal_blind_000031`

### 6.3 作用
- 这不是训练集
- 这是 `Stage B` v0/v1 的:
  - 开发难例池
  - demo 难例池
  - 论文 Error Analysis 对照池

## 7. 实施顺序

### 7.1 第一步
- 先写 `Stage A blind error analysis`
- 冻结 `Stage A v1` 边界

### 7.2 第二步
- 生成 `Stage B seed pool`
- 明确输入格式

### 7.3 第三步
- 先搭 `Stage B harness`
- 能够跑通:
  - `input trace -> stage_b trace -> summary`

### 7.4 第四步
- 再上最小共识算法
- 优先做 deterministic / mock-friendly 版本
- 不急着接真实 provider

### 7.5 第五步
- 在 seed pool 上做:
  - single-agent baseline
  - simple vote baseline
  - structured consensus

## 8. 当前建议
- 下一步工程**不是**继续修 `Stage A`
- 下一步工程是:
  1. 固化 `Stage A` 的 blind 误差边界
  2. 生成 `Stage B` seed pool
  3. 落 `Stage B` harness 与 evaluator

一句话:
- `Stage A` 现在负责“快路径裁决 + 不确定性探测”
- `Stage B` 接下来负责“慢路径共识 + 难例修复 + 可信轨迹”

## 9. 2026-03-17 执行进展

### 9.1 已落地
- `scripts/build_stage_b_seed_pool.py`
- `data/agentdns_routing/formal/stage_b_seed_pool.jsonl`
- `src/agentdns_routing/stage_b_consensus.py`
- `src/agentdns_routing/stage_b_eval.py`
- `scripts/run_stage_b.py`
- `tests/test_stage_b.py`

### 9.2 当前 `v0` 的真实定位
- 当前 `Stage B v0` 已不是“未开工”
- 但它也不是正式的 `Stage B v1` 共识算法
- 当前更准确的定位是:
  - `seed pool + harness + trace writer + evaluator`
  - 默认保守，不主动推翻 `Stage A primary`
  - 用于把慢路径工程接口先跑通

### 9.3 当前已验证
- `tests/test_stage_b.py`
  - `4` 个测试通过
- `seed pool` 试跑产物:
  - `artifacts/stage_b/stage_b_seed_pool.stage_b_v0_20260317.jsonl`
  - `artifacts/stage_b/stage_b_seed_pool.stage_b_v0_20260317.summary.json`
- 当前 `summary`:
  - `samples = 17`
  - `stage_b_applied = 17`
  - `stage_b_changed_primary = 0`
  - `StageBPrimaryAcc@1 = 0.7059`
  - `StageBRelatedRecall = 0.7143`
  - `StageBRelatedPrecision = 0.8333`
  - `trace_validation.valid = true`

### 9.4 因此，下一步不再是“先补文件”
- 文件和评测骨架已经有了
- 下一步应是:
  1. 单开 `Stage B v1` 的真正共识策略
  2. 目标性验证能否修复 blind 中的 `decision_primary_miss`
  3. 再决定是否接 `mock / real-provider` 多角色实现

## 10. 2026-03-17 对齐 13 号设计文档的实现更新

### 10.1 已实现的核心变化
- `Stage B` 不再只有 deterministic `v0 harness`
- 当前 live code 已在同一文件内支持两种路径:
  - deterministic `v0`
  - `mock / deepseek / openai` 的 `LLM multi-role consensus v1`
- 对应实现文件:
  - `src/agentdns_routing/stage_b_consensus.py`
  - `src/agentdns_routing/stage_b_eval.py`
  - `src/agentdns_routing/routing_chain.py`
- 当前 `Stage A` 也已完成双轨 formalization:
  - `A_clean`
  - `A_llm`
  - 二者都会输出统一的:
    - `final_primary_fqdn`
    - `final_related_fqdns`
    - `final_decision_source`
    - `entered_stage_b`

### 10.2 当前统一 runner
- 已新增:
  - `scripts/run_routing_ab_experiment.py`
- 当前 runner 可以在同一份 frozen `Stage R snapshot` 上直接产出四条链路:
  - `R -> A_clean`
  - `R -> A_llm`
  - `R -> A_clean -> B`
  - `R -> A_llm -> B`
- 这一步解决了此前“看起来所有样本都进了 `Stage B`”的误解:
  - 现在完整 split 会先跑 `Stage A`
  - 只有 `escalate_to_stage_b = true` 的样本才真正进入 `Stage B`

### 10.3 当前 `mock` 全量对照
- 已生成:
  - `artifacts/routing_ab/dev_compare_mock_20260317/`
- 这批结果的意义是:
  - 证明四条链路已经都能端到端跑通
  - 证明 summary/trace/schema/评测契约已经打通
  - 不是证明 `Stage B mock` 已优于 `Stage A`
- 当前最准确的状态判断:
  - `Stage B v1` 的工程底座和 provider 接口已建立
  - `Stage B` 的真实能力验证还需要 `deepseek` 等 real-provider smoke

### 10.4 当前下一步
- 先不再补新的 deterministic 规则
- 下一步应转为:
  1. 用 `deepseek` 在 hard-case / blind escalated 子集做 `Stage B` provider smoke
  2. 校准 `Stage B` 的角色 prompt、feedback aggregation、override policy
  3. 再决定是否做全量 blind `R -> A_llm -> B`

## 11. 2026-03-17 `Stage B + deepseek` 首轮 hard-case smoke 结果

### 11.1 已执行
- 当前已生成 `dev hard-case` 子集:
  - `data/agentdns_routing/formal/dev_stage_b_hard13_20260317.jsonl`
- 当前已完成:
  - `A_llm(mock) -> B(deepseek)` on `hard13`
- 产物:
  - `artifacts/routing_ab/dev_stage_b_hard13_a_llm_to_b_deepseek_20260317/`

### 11.2 当前结论
- 这轮结果证明:
  - `Stage B` 的 real-provider 接口已经打通
  - `candidate-internal` 约束、trace、summary 都能在真实 provider 下落地
- 但这轮结果也明确说明:
  - 当前 `Stage B` 的 `override policy` 还不成熟
  - 真实 provider 当前过于激进地翻动 `Stage A primary`

### 11.3 当前结果摘要
- `A_llm(mock)` baseline:
  - `PrimaryAcc@1 = 0.9231`
  - `RelatedRecall = 0.8571`
  - `RelatedPrecision = 1.0`
- `A_llm(mock) -> B(deepseek)`:
  - `PrimaryAcc@1 = 0.6923`
  - `AcceptablePrimary@1 = 0.7692`
  - `RelatedRecall = 0.7143`
  - `RelatedPrecision = 0.7143`
  - `stage_b_changed_primary = 4`
  - `stage_b_regressed_primary = 3`
  - `stage_b_fixed_primary = 0`

### 11.4 因此
- 当前不应直接扩 full `dev`
- 下一步应先做:
  1. 收紧 `Stage B` 的 primary override 门槛
  2. 给 `sibling` / `high-risk` 加更明确的角色级约束
  3. 再重跑 `hard13`

## 12. 2026-03-18 `Stage B` 实验纪律补充

### 12.1 明确禁止
- 明确禁止 `hardcoding + 面向测试集 overfit`
- 对 `Stage B` 来说，以下行为都视为违规:
  - 根据 `hard13` 或已揭盲 blind 个案补 `fqdn` 特判
  - 根据某个已知失败样本追加 node-specific / family-specific 补丁
  - 以“把当前已看见样本做对”为主目标来迭代 prompt 或规则

### 12.2 允许的改动边界
- 只允许:
  - 通用 `override protocol` 调整
  - 通用共识终止条件
  - 与具体样本无关的抽象约束
  - provider 稳定性与 trace/evaluator 工程修复
- 不允许:
  - case-level patch
  - fqdn-level patch
  - sample-id-level patch

### 12.3 结果口径
- 从本节开始，任何基于已揭盲 `blind / hard-case` 继续调出来的 `Stage B` 新版本:
  - 默认标记为 `exploratory`
  - 不得作为干净 holdout 结论
  - 若后续要声称泛化改进，必须再上新的未参与调参 split

## 13. 2026-03-23 当前 `Stage B` 的真实瓶颈判断

### 13.1 不是 runtime knob
- 已对以下运行参数做过多轮调整:
  - provider timeout
  - role-specific temperature
  - parallel role calls
- 当前结论:
  - 这些改动会引起边缘样本波动
  - 但不会从根本上把 `Stage B` 变成稳定纠错器

### 13.2 真正瓶颈是 packet 太薄
- 当前 `Stage B` 看到的 packet 主要仍是:
  - `score_a / score_related`
  - `primary_fit / context_fit / hierarchy_fit`
  - `primary_hits / secondary_hits / scene_hits`
- 当前缺的是:
  - 上游 `Stage A LLM` 的语义判断摘要
  - 上游 `Stage A LLM` 的不确定性与困惑点
  - 候选竞争簇信息
  - 显式负证据卡

## 14. 2026-03-23 `Stage A uncertainty handoff + Stage B packet v2` 正式纳入后续设计

### 14.1 新的升级原则
- 保留:
  - `candidate-internal`
  - 硬输出边界
- 调整:
  - prompt 语气不再过硬
  - `Stage B` 输入不再只有分数摘要

### 14.2 需要新增的上游下传
- `Stage A LLM` 计划新增:
  - `primary_rationale`
  - `secondary_rationale`
  - `challenger_notes`
  - `uncertainty_summary`
  - `confusion_points`
  - `override_sensitivity`

### 14.3 需要新增的候选内证据卡
- `Stage B packet v2` 计划新增:
  - `competition_clusters`
  - `negative_evidence_card`
  - `secondary_recovery_card`

### 14.4 目的
- 不是放开 `Stage B` 到候选外自由生成
- 而是在保持可审计边界的前提下，提高:
  - `PrimaryAcc` 的可判性
  - `RelatedRecall` 的可恢复性
  - `RelatedPrecision` 的可解释性

### 14.5 对应设计文档
- 当前正式设计见:
  - `closure/24_stage_a_uncertainty_and_stage_b_packet_v2_design.md`
