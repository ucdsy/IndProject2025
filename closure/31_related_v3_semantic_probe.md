# Related v3 Semantic Probe（2026-04-11）

> 目的: 在**不改动当前 `related_v2` 主实现**的前提下，验证一个更“语义直驱”的 related 方案是否优于现有版本。

## 1. 为什么单开实验线

当前 `related_v2` 已经形成一套可复现结果:

- 基于 frozen primary 主线
- 使用 candidate builder
- 由单 LLM 做 related adjudication
- 带较强的结构化牵引与 guardrails

这套方案可以作为稳定基线，但仍存在一个核心疑问:

> 当前 related 的误挂与漏挂，是否部分来自“过多中间结构和后置约束”？

为避免直接破坏现有版本，本实验线单独实现 `related_v3_semantic`:

- 不改 `related_v2`
- 不改主服务默认接线
- 仅面向 frozen traces 做 related-only 对比

## 2. 与 `related_v2` 的主要差异

`related_v2`:

- 强调 secondary intent 压缩
- 给 LLM 较多结构化候选特征
- 后置 guardrails 较重

`related_v3_semantic`:

- 保留受控候选池
- 更强调完整 query 语境
- 减少预评分与中间结构对 LLM 的牵引
- 只保留薄 guardrails:
  - chain duplicate
  - obvious primary challenger

一句话:

> `related_v2` 更工程化，`related_v3_semantic` 更偏 full-query semantic adjudication。

## 3. 实验边界

本实验线只做:

- `related-only from frozen traces`

不做:

- primary 主线重跑
- 服务默认切换
- fresh split 重定义

## 4. 计划中的验证顺序

1. `test.jsonl` smoke
2. `train20 / test20` 小样本
3. 仅当明显优于 `related_v2` 时，再跑 retrospective `test=113`

## 5. 代码入口

- 实验实现:
  - `/Users/xizhuxizhu/Desktop/IndProj04/src/agentdns_routing/related_v3_semantic.py`
- 实验 runner:
  - `/Users/xizhuxizhu/Desktop/IndProj04/scripts/run_related_only_semantic_from_traces.py`
- 实验测试:
  - `/Users/xizhuxizhu/Desktop/IndProj04/tests/test_related_v3_semantic.py`
