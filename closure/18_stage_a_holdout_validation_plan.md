# Stage A Holdout 验证计划（2026-03-15）

> 目的: 将 `clean Stage A v1` 从“`formal/dev` 上的开发集闭环”推进到“有独立 holdout 证据支撑的正式验证状态”。
>
> 适用范围: `Stage A clean`、`Stage A llm mock`、`Stage A real-provider` 的正式 holdout 评测。
>
> 依赖:
> - formal 协议: [09_eval_protocol.md](/Users/xizhuxizhu/Desktop/IndProj04/closure/09_eval_protocol.md)
> - 执行门槛: [14_execution_spec_and_review_gate.md](/Users/xizhuxizhu/Desktop/IndProj04/closure/14_execution_spec_and_review_gate.md)
> - 当前方法边界: [16_stage_a_strategy_and_execution.md](/Users/xizhuxizhu/Desktop/IndProj04/closure/16_stage_a_strategy_and_execution.md)
>
> 注:
> - 本文是 2026-03-15 的历史 holdout 验证计划，不代表当前 live repo 的最新实验矩阵。
> - `blind`、`challenge` 与 `holdout2` 现已揭盲；若继续引用本文，只能把它视为历史验证路径与实验纪律说明。
> - 当前项目总状态应结合 `closure/20_stage_b_bootstrap_plan.md`、`closure/24_stage_a_uncertainty_and_stage_b_packet_v2_design.md` 与 `research-project/04_execution-log.md` 阅读。

## 1. 当前判断

- 当前 `Stage A clean` 已在 `formal/dev` 上实现 `dev-set closure`。
- 当前不能把该结果直接当作泛化结论。
- 当前下一步不是继续调 `formal/dev`，而是执行独立 holdout 验证。

## 2. 冻结对象

本轮 holdout 默认冻结以下对象:

- `namespace_descriptors.jsonl`
- `namespace.py`
- `stage_r_clean.py`
- `stage_a_clean.py`
- `stage_a_llm.py`
- `sr_clean_v2_20260314_related2`
- `sa_clean_v8_20260314_riskschema_on_sr_v2`

说明:
- `Stage A clean` 是本轮正式 holdout 的主验证对象。
- `Stage A llm mock` 与 `Stage A real-provider` 作为对照线，不作为唯一放行依据。

## 3. 数据与 split 纪律

本轮使用 formal 目录下现有 split:

- `/Users/xizhuxizhu/Desktop/IndProj04/data/agentdns_routing/formal/dev.jsonl`
- `/Users/xizhuxizhu/Desktop/IndProj04/data/agentdns_routing/formal/blind_input.jsonl`
- `/Users/xizhuxizhu/Desktop/IndProj04/data/agentdns_routing/formal/blind_labels.jsonl`
- `/Users/xizhuxizhu/Desktop/IndProj04/data/agentdns_routing/formal/challenge_input.jsonl`
- `/Users/xizhuxizhu/Desktop/IndProj04/data/agentdns_routing/formal/challenge_labels.jsonl`
- `/Users/xizhuxizhu/Desktop/IndProj04/data/agentdns_routing/formal/family_ledger.csv`

纪律:

- `dev` 只用于已有版本的解释与附录，不再用于继续追分。
- 若 `blind_labels` / `challenge_labels` 仍未参与本轮调参，则本轮可作为正式 holdout。
- 若后续在看过 `blind/challenge` 结果后继续修改:
  - 必须升 `stage_r_version` / `stage_a_version`
  - 当前 blind/challenge 结果自动降级为 `exploratory`
  - 不得继续作为正式主表泛化证据

## 4. Holdout 运行矩阵

### 4.1 主线

1. `Stage R clean` on `blind_input`
2. `Stage A clean` on frozen `Stage R snapshot`
3. join `blind_labels` 生成 blind summary

### 4.2 对照线

1. `Stage A llm mock` on same frozen blind snapshot
2. `Stage A real-provider` on same frozen blind snapshot
3. join `blind_labels` 生成 mock / real-provider blind summary

### 4.3 附录鲁棒性

1. 重复上述流程于 `challenge_input`
2. challenge 结果单独报告，不与 blind 主表混合

## 5. 必报指标

### 5.1 质量

- `PrimaryAcc@1`
- `AcceptablePrimary@1`
- `RelatedRecall`
- `RelatedRecall@Covered`
- `RelatedPrecision`
- `related_overpredict_rate`

### 5.2 约束与系统性

- `ConstraintPassRate`
- `Validity`
- `escalation_rate`

### 5.3 稳定性与成本

- `Latency p50/p95`（若本轮可稳定测得）
- provider 失败率 / `llm_error` 占比

## 6. 验证目标

本轮 holdout 的核心不是追求再次出现 `1.0`，而是回答以下问题:

1. `Stage A clean` 在未参与本轮调参的 holdout 上是否仍保持明显优于旧基线的稳定表现？
2. `Stage A clean` 的 precision-first related 策略是否在 holdout 上仍成立？
3. `Stage A real-provider` 的主要问题究竟是路由逻辑退化，还是 provider 稳定性退化？

## 7. 通过条件

若满足以下条件，可判定 `Stage A v1` 进入“验证完成”状态:

- `Stage A clean` 在 blind 上无明显结构性崩塌
- blind 上不存在集中型 `decision_miss` 家族泄漏问题
- blind/challenge 结论与当前 `dev-set closure` 方向一致
- real-provider 结果即使不满分，也能把主要风险归因为 provider 稳定性，而不是新的系统性路由错误

## 8. 失败后处理

若 blind/challenge 暴露以下问题，则当前版本不得直接作为正式主结论:

- 同一 family 集中失效
- `related` precision 明显塌陷
- `high-risk` 路由在 holdout 上大面积误挂或误拒
- provider 不稳定掩盖了真实算法能力，导致无法形成可信结论

对应动作:

1. 将当前 blind/challenge 结果标记为 `exploratory`
2. 升版本
3. 只允许基于失败类型做新一轮修订
4. 重新构造或启用新的 holdout

## 9. 当前建议执行顺序

1. 冻结当前 `Stage R/Stage A` clean 版本
2. 导出 blind snapshot
3. 跑 `Stage A clean blind`
4. 跑 `Stage A llm mock blind`
5. 跑 `Stage A real-provider blind`
6. 汇总 blind 主表
7. 再跑 challenge 附录表

## 10. 当前项目判断

- `Stage A` 现在不需要继续做方法性扩写
- `Stage A` 下一阶段的主要任务是**验证**，不是**继续补规则**
- `Stage B` 可以开始并行做样本池整理与升级策略设计，但不应挤占 holdout 验证这条主线
