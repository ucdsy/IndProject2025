# AgentDNS 算法脚本入口索引

本文件只整理算法实验入口，避免在论文/结项复算时混用主线、诊断线和临时探索线。

## 1. 冻结主线优先入口

### 1.1 Stage R snapshot

```bash
python3 scripts/run_stage_r_clean_snapshot.py \
  --input <joined_or_input.jsonl> \
  --output <stage_r_snapshot.jsonl> \
  --summary <stage_r_summary.json> \
  --top-k 10
```

用途：生成冻结候选集合和 Stage R 召回/覆盖统计。

### 1.2 Stage A LLM

```bash
python3 scripts/run_stage_a_llm.py \
  --input <joined.jsonl> \
  --snapshot <stage_r_snapshot.jsonl> \
  --output-dir <stage_a_output_dir> \
  --provider deepseek \
  --model deepseek-chat
```

用途：在冻结 Stage R snapshot 上运行单智能体结构化语义判别。

### 1.3 Stage B 职责化协作复核

```bash
python3 scripts/run_stage_b.py \
  --input <joined.jsonl> \
  --traces <stage_a_trace.jsonl> \
  --output-dir <stage_b_output_dir> \
  --provider deepseek \
  --model deepseek-chat \
  --collaboration-mode heterogeneous
```

用途：在 Stage A trace 上运行职责化协作复核。

### 1.4 expanded gate 回放

```bash
python3 scripts/replay_stage_b_gate.py \
  --trace <stage_b_trace.jsonl> \
  --labels <joined.jsonl> \
  --mode aggressive \
  --output <summary.json>
```

用途：从已有 Stage B trace 回放 gate 口径。用于 train/test 回顾性口径时，报告里称为 expanded gate，不再使用“激进版”这种临时说法。

## 2. 补强基线和诊断入口

### 2.1 primary 单标签基线

```bash
python3 scripts/run_primary_baselines.py \
  --input <joined.jsonl> \
  --snapshot <stage_r_snapshot.jsonl> \
  --output-dir <baseline_output_dir> \
  --methods lexical_bm25 embedding flat_llm flat_llm_self_consistency \
  --provider deepseek \
  --model deepseek-chat \
  --candidate-limit 10
```

用途：BM25、embedding、Flat LLM、Flat LLM self-consistency 等主标签基线。

候选顺序诊断：

```bash
python3 scripts/run_primary_baselines.py \
  --input <joined.jsonl> \
  --snapshot <stage_r_snapshot.jsonl> \
  --output-dir <order_diag_output_dir> \
  --methods flat_llm \
  --provider deepseek \
  --model deepseek-chat \
  --candidate-order shuffle \
  --candidate-shuffle-seed 1
```

`--candidate-order` 只影响 Flat LLM 候选展示顺序，不改变 Stage R snapshot 本身。

### 2.2 hard routing boundary v1

```bash
python3 scripts/validate_hard_routing_boundary_v1.py
```

用途：校验 hard routing boundary v1。该集合是 boundary stress set，不替代冻结 test。

## 3. 多意图集合任务入口

多意图集合任务使用 `gold_intent_fqdns`，不区分 primary/related。

```bash
python3 scripts/run_stage_a_multi_intent.py \
  --input data/agentdns_routing/formal/multi_intent_eval_v1.jsonl \
  --snapshot <multi_intent_stage_r_snapshot.jsonl> \
  --output-dir <multi_intent_stage_a_output_dir> \
  --provider deepseek \
  --model deepseek-chat
```

```bash
python3 scripts/run_stage_b_multi_intent.py \
  --input data/agentdns_routing/formal/multi_intent_eval_v1.jsonl \
  --traces <multi_intent_stage_a_trace.jsonl> \
  --output-dir <multi_intent_stage_b_output_dir> \
  --provider deepseek \
  --model deepseek-chat \
  --collaboration-mode heterogeneous
```

```bash
python3 scripts/evaluate_multi_intent_set_routing.py \
  --input data/agentdns_routing/formal/multi_intent_eval_v1.jsonl \
  --trace <trace_name>=<trace.jsonl> \
  --output-dir <eval_output_dir> \
  --prediction-mode final
```

## 4. related_v2 sidecar 入口

```bash
python3 scripts/run_related_only_from_traces.py \
  --input <joined.jsonl> \
  --traces <primary_trace.jsonl> \
  --output-dir <related_output_dir> \
  --provider deepseek \
  --model deepseek-chat
```

用途：在冻结 primary trace 上补 related_v2。当前 related 更适合作为在线推荐/用户可勾选候选或补充实验，不作为单主标签主实验的核心结论。

## 5. 不建议作为新实验首选入口

| 脚本 | 原因 |
|---|---|
| `scripts/run_routing_ab_experiment.py` | 旧式一键四链路入口，适合复现早期结果；新实验优先分步跑 Stage R/A/B |
| `scripts/run_related_only_from_traces.py` | 只用于 related sidecar，不用于 primary 主表 |
| `scripts/run_routing_service.py` | 在线服务启动入口，不是离线论文实验入口 |

## 6. 当前不要做的事

- 不要把 `multi_intent_eval_v1` 的集合指标并入 primary 单标签准确率表。
- 不要把 `hard_routing_boundary_v1` 当作冻结 test 替代品。
- 不要把 Flat LLM 描述成弱基线；它在强候选池和有序 Stage R Top-10 下是强基线。
- 不要重跑 related 后反向修改冻结 train/test 主表。
