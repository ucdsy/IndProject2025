# 算法侧盘点与瘦身记录（2026-06-03）

## 1. 当前算法主线

当前应保持一条冻结主线，避免把后续 related、多意图和 hard-set 诊断混入同一口径：

```text
Stage R 候选集合构造
  -> Stage A 单智能体结构化语义判别
  -> Stage B 职责化协作复核
  -> expanded gate 回放/报告口径
```

对应论文/结项口径：

- `Stage R`：候选集合构造与候选说明包生成，提供 Top-K 候选和排序先验。
- `Stage A`：单智能体结构化语义判别，输出结构化语义裁决包、候选级结构化判断表、主标签和不确定性。
- `Stage B`：职责化协作复核，使用异质 reviewer、显式授权改判和过程轨迹记录。
- `expanded gate`：训练侧调优后确定的补充改判口径，报告时作为最终扩展配置，不再和 default/conservative/aggressive 混写。

## 2. 当前代码分层

### 2.1 主线模块

| 文件 | 定位 | 当前处理 |
|---|---|---|
| `src/agentdns_routing/stage_r_clean.py` | Stage R 候选构造与召回统计 | 保留 |
| `src/agentdns_routing/stage_a_llm.py` | Stage A LLM 结构化语义判别主线 | 保留 |
| `src/agentdns_routing/stage_b_consensus.py` | Stage B 多智能体职责化协作复核 | 保留 |
| `src/agentdns_routing/routing_chain.py` | R/A/B trace final 字段归一和链路评价 | 保留 |
| `src/agentdns_routing/stage_a_eval.py` | Stage A 评价 | 保留 |
| `src/agentdns_routing/stage_b_eval.py` | Stage B 评价 | 保留 |
| `src/agentdns_routing/namespace.py` | 能力命名空间与节点解析 | 保留 |

### 2.2 工程演示/服务模块

| 文件 | 定位 | 当前处理 |
|---|---|---|
| `src/agentdns_routing/service_api.py` | 在线服务 API；支持 Stage A/B/related_v2 调度 | 保留，但不作为论文离线主实验入口 |
| `src/agentdns_routing/stage_c_selector.py` | 路由后执行实例映射/agent 选择 | 保留，属于工程链路，不混入主标签实验 |
| `src/agentdns_routing/related_v2.py` | related 子线；当前更适合在线补充能力/用户勾选，不作为冻结主实验主指标 | 保留为实验/工程 sidecar |

### 2.3 新任务/压力测试模块

| 文件 | 定位 | 当前处理 |
|---|---|---|
| `src/agentdns_routing/stage_a_multi_intent.py` | 多意图集合路由 Stage A | 单列为新任务 |
| `src/agentdns_routing/stage_b_multi_intent.py` | 多意图集合路由 Stage B | 单列为新任务 |

多意图任务不再强制 primary/related 拆分，gold 使用 `gold_intent_fqdns`，评价用集合指标；不要把它混回单主标签 `ground_truth_fqdn` 主表。

## 3. scripts 入口分层

### 3.1 主实验入口

| 脚本 | 用途 |
|---|---|
| `scripts/run_stage_r_clean_snapshot.py` | 生成冻结 Stage R snapshot |
| `scripts/run_stage_a_llm.py` | 在冻结 snapshot 上跑 Stage A LLM |
| `scripts/run_stage_b.py` | 在 Stage A trace 上跑 Stage B |
| `scripts/replay_stage_b_gate.py` | 从已有 Stage B trace 回放责任化/保守/扩展 gate |
| `scripts/run_routing_ab_experiment.py` | 旧式一键跑 R/A/B 四链路；保留用于复现早期结果，新结果优先用分步入口 |
| `scripts/generate_retrospective_figures.py` | 生成回顾性 train/test 图表 |
| `scripts/generate_historical_cumulative_curve.py` | 生成历史累计曲线 |
| `scripts/generate_eval_scale_stability.py` | 生成规模稳定性图 |

### 3.2 补强基线与诊断入口

| 脚本 | 用途 |
|---|---|
| `scripts/run_primary_baselines.py` | primary 单标签基线：BM25/embedding/Flat LLM/Flat LLM SC；支持候选顺序诊断 |
| `scripts/build_hard_routing_boundary_v1.py` | 构造单主标签边界压力测试集 |
| `scripts/validate_hard_routing_boundary_v1.py` | 校验 hard routing boundary v1 |
| `scripts/evaluate_stage_r_clean.py` | Stage R 召回/覆盖诊断 |

### 3.3 多意图集合任务入口

| 脚本 | 用途 |
|---|---|
| `scripts/build_multi_intent_eval_v1.py` | 构造多意图集合评测集 |
| `scripts/validate_multi_intent_eval_v1.py` | 校验多意图集合评测集 |
| `scripts/run_stage_a_multi_intent.py` | 跑多意图 Stage A |
| `scripts/run_stage_b_multi_intent.py` | 跑多意图 Stage B |
| `scripts/evaluate_multi_intent_set_routing.py` | 集合指标评价 |
| `scripts/run_multi_intent_baselines.py` | 多意图 baseline |

### 3.4 related sidecar 入口

| 脚本 | 用途 |
|---|---|
| `scripts/run_related_only_from_traces.py` | 在冻结 primary trace 上补跑 related_v2 |

当前建议：related 先作为“在线补充推荐/可勾选候选”或补充实验，不再强行作为主线准确率证明点。

### 3.5 数据治理入口

| 脚本 | 用途 |
|---|---|
| `scripts/rebuild_formal_dataset.py` | 早期 formal 数据集重建 |
| `scripts/validate_formal_dataset.py` | formal 主数据校验 |
| `scripts/build_holdout2_dataset.py` / `scripts/validate_holdout2_dataset.py` | holdout2 构造与校验 |
| `scripts/build_holdout3_dataset.py` / `scripts/validate_holdout3_dataset.py` | holdout3 构造与校验 |
| `scripts/build_stage_b_retrospective_split.py` | 统一回顾性 train/test split |
| `scripts/build_stage_b_seed_pool.py` | Stage B seed pool |

## 4. 当前实验口径整理

### 4.1 主论文/结项主表

建议只保留统一 train/test 口径：

- Stage R rule/top-k 或规则基线
- Stage A 结构化语义判别
- Stage A + Stage B 默认职责化协作
- Stage A + Stage B expanded gate
- Flat LLM ordered Top-10 作为强基线

其中 Flat LLM 不应被描述为弱基线。113 测试集上 ordered Top-10 达到 0.9292，去排序后下降但仍较强，说明它吃到 Stage R 排序先验，也受益于强候选池和候选说明。

### 4.2 协作机制诊断

重点报告：

- `Corrected Error Rate = fixed / Stage A wrong and gold in candidates`
- `Regression Rate = regressed / Stage A correct and entered review`
- `Net Correction = fixed - regressed`

这比单看 overall accuracy 更贴近 Stage B 的创新点：Stage B 是受控改判器，不是全量替代分类器。

### 4.3 hard routing boundary v1

定位为 boundary stress set，不替代冻结 test。当前结论应谨慎写成：

- hard set 能暴露边界样本中 Stage A/B 与 Flat LLM 的差距。
- 它证明“边界类型更难”，但不能证明当前 Stage B 全面超过一步式 LLM。
- 后续如果要强化协作优势，需要构造 boundary correction set，而不是一般 hard routing set。

### 4.4 multi_intent_eval_v1

这是独立集合路由任务：

- gold 字段是 `gold_intent_fqdns`
- 输出是集合 `selected_fqdns`
- 指标是 ExactSetAcc、SetPrecision、SetRecall、SetF1、Jaccard
- 不应与 primary 单标签准确率直接并表比较

## 5. 瘦身原则

本轮不删除历史脚本和 artifacts，原因是：

1. 许多结果已经写入报告/论文草稿，需要保留可追溯性。
2. trace schema 与版本号被下游统计脚本引用，贸然删除或重命名会破坏复算。
3. 当前真正的问题不是代码执行路径不存在，而是入口太多、实验口径容易混。

本轮可安全瘦身动作：

- 清理 `src/agentdns_routing/__pycache__` 与 `scripts/__pycache__`
- 抽取 `src/agentdns_routing/llm_json.py`，统一 Stage A/B、related_v2、多意图 A/B 中重复的 LLM JSON 响应解析与 `response_format=json_object` 兼容回退判断
- 新增脚本入口索引，降低误跑概率
- 给 related 设计文档加当前状态标记
- 保持主线代码和历史 artifact 不动

## 6. 下一步建议

1. 若要继续工程化，优先把 `scripts/run_stage_a_llm.py`、`scripts/run_stage_b.py`、`scripts/replay_stage_b_gate.py` 固化为 Makefile 或 shell recipe，减少手工拼命令。
2. 若要继续论文补强，优先补“协作改判条件指标”表，而不是继续增加普通 LLM baseline。
3. 若要继续 related，应把它定位为在线 sidecar：系统推荐 related 候选并允许用户勾选，而不是强行用当前 gold 去证明 related precision/recall。
4. 若要继续多意图，应单独成节，使用集合路由指标，不并入 primary 单标签主表。
