# Stage C 与 AgentDNSDemo 联动实施说明（2026-03-26）

> 目的: 将当前已经成型的 `Stage R / A / B` 路由链，正式延伸到 `routing_fqdn -> agent_fqdn -> endpoint` 的下一跳执行选择，并明确 `IndProj04` 与 `AgentDNSDemo` 的分工、接口与实施顺序。
>
> 定位: 这是 `Stage C` 的工程实施说明，不是新的算法研究提案。
>
> 当前假设:
> - `IndProj04` 继续作为算法真源、评测真源与 contract 真源。
> - `AgentDNSDemo` 作为运行承载、UI 展示、registry/card 导出与最终 endpoint 调用方。
> - `Stage C` 继续坚持纯结构化选择，不走 LLM，不改写 `routing_fqdn`。

## 1. 结论先行

当前最合理的推进方式不是在 `IndProj04` 内单独做一个“自转版 Stage C”，而是直接做成 **双仓联动**:

1. `IndProj04` 提供统一的 `R -> A -> B -> C` 选择逻辑与 trace contract。
2. `AgentDNSDemo` 提供 registry snapshot、Agent Card 导出、UI 展示与最终执行。
3. 两边通过稳定接口对接，避免各自长出一套不同版本的 `Stage A/B/C`。

一句话:

> `IndProj04` 是 source of truth，`AgentDNSDemo` 是 runtime shell。

## 2. 这次到底要交付什么

交付目标不是“把 Stage C 写个示意脚本”，而是把 demo 与工程链路直接打到真实下一跳。

最终链路应为:

`query -> fqdn_candidates -> selected_primary_fqdn -> chosen_agent_fqdn -> endpoint`

并且全链路都能输出可审计 trace:

- `stage_r_trace`
- `routing_trace`
- `selection_trace`

## 3. 两个仓库各自负责什么

### 3.1 `IndProj04`

负责:

- `Stage R / A / B / C` 的核心逻辑
- 当前正式版本线与参数
- 统一 JSON contract
- 统一 trace 结构
- 评测脚本与结果口径

这意味着:

- `AgentDNSDemo` 不应自行复制或改写 `Stage A/B/C` 的核心判定逻辑
- 所有“当前主方法”的解释都应回到 `IndProj04`

### 3.2 `AgentDNSDemo`

负责:

- 接收 query 与 context
- 提供可消费的 registry snapshot / Agent Card
- 展示 `Stage R/A/B/C` 的关键中间结果
- 调用 `chosen_agent_fqdn -> endpoint`
- 在 UI 中展示为什么选了这个 agent

这意味着:

- `AgentDNSDemo` 是运行承载层
- 不是算法真源

## 4. 联动方式选择

本次明确采用 **服务边界联动**，不采用“双边各写一套逻辑”的方式。

### 4.1 选择服务边界，而不是代码复制

推荐形态:

- `AgentDNSDemo` 调用 `IndProj04` 暴露的 routing service
- `IndProj04` 返回完整的 `R/A/B/C` 结构化结果

这样做的好处:

- 版本线唯一
- 评测与 demo 逻辑一致
- 不会在两个 repo 中出现两套 `Stage A/B/C`

### 4.2 不采用的方式

- 不在 `AgentDNSDemo` 中重新 hardcode 一套 `Stage A/B/C`
- 不让 `AgentDNSDemo` 只显示最终 answer 而不显示 `routing_fqdn / agent_fqdn`
- 不把 `Stage C` 做成独立于 `IndProj04` contract 的 ad-hoc selector

## 5. 系统调用链

### 5.1 请求流

1. 用户请求进入 `AgentDNSDemo`
2. `AgentDNSDemo` 收集:
   - `query`
   - `context`
   - 当前 `agent_registry_snapshot`
3. `AgentDNSDemo` 调用 `IndProj04` 的 routing service
4. `IndProj04` 依次执行:
   - `Stage R`
   - `Stage A`
   - `Stage B`（若触发）
   - `Stage C`
5. `IndProj04` 返回:
   - `selected_primary_fqdn`
   - `selected_related_fqdns`
   - `chosen_agent_fqdn`
   - `endpoint`
   - `stage_r_trace / routing_trace / selection_trace`
6. `AgentDNSDemo`:
   - 展示 trace
   - 调用最终 endpoint

### 5.2 展示流

`AgentDNSDemo` 页面必须能同时看到:

- `routing_fqdn`
- `agent_fqdn`
- `Stage A confidence`
- `是否触发 Stage B`
- `Stage C top_k_agents`
- `chosen_agent_fqdn -> endpoint`

## 6. 接口定义

### 6.1 `AgentDNSDemo -> IndProj04`

建议新增 routing service:

`POST /api/routing/resolve`

请求体最小字段:

```json
{
  "query": "用户请求",
  "context": {},
  "agent_registry_snapshot": {
    "snapshot_id": "registry_20260326_001",
    "generated_at": "2026-03-26T10:00:00+08:00",
    "agents": []
  }
}
```

响应体最小字段:

```json
{
  "run_id": "route_20260326_xxx",
  "selected_primary_fqdn": "verify.invoice.finance.cn",
  "selected_related_fqdns": ["tax.finance.cn"],
  "final_decision_source": "stage_a_llm",
  "chosen_agent_fqdn": "vendorB-invoice-verify-v2.agent.verify.invoice.finance.cn",
  "endpoint": "https://vendorb.example/api/invoice/verify",
  "top_k_agents": [],
  "stage_r_trace": {},
  "routing_trace": {},
  "selection_trace": {}
}
```

### 6.2 `AgentDNSDemo` registry snapshot

`AgentDNSDemo` 至少提供:

`GET /api/registry/snapshot`

每个 agent 最小字段:

- `agent_fqdn`
- `routing_fqdn`
- `provider`
- `endpoint`
- `status`
- `last_heartbeat_at`
- `skills`
- `tags`
- `input_schema`
- `output_schema`
- `exposure_count_agent`
- `exposure_count_provider`

### 6.3 Agent Card 导出

`AgentDNSDemo` 额外提供:

- `GET /.well-known/agent-card.json`
- 或 `GET /api/agents/{id}/card`

这次只做字段对齐，不做完整 A2A 协议实现。

## 7. Stage C 核心逻辑

### 7.1 输入

- `selected_primary_fqdn`
- `agent_registry_snapshot`

### 7.2 硬过滤

必须先过滤:

1. `routing_fqdn` 非 exact match 的 agent
2. `status != online` 的 agent
3. 缺失 `endpoint` 的 agent
4. schema 明显不匹配的 agent

说明:

- 不允许父级 fallback
- 不允许跨 `routing_fqdn` 借候选
- 不允许在 Stage C 再走 LLM

### 7.3 评分公式

固定采用当前规格:

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

### 7.4 平分规则

若 `final` 接近，固定顺序:

1. `health` 更高
2. `fair_provider` 更高
3. `agent_fqdn` 字典序更小

## 8. `selection_trace` 要求

`selection_trace` 必须足够强，能直接用于:

- demo 展示
- 工程排障
- 结项答辩

建议最小字段:

- `routing_fqdn`
- `snapshot_id`
- `registry_generated_at`
- `candidate_count_before_filter`
- `candidate_count_after_filter`
- `filtered_out`
- `top_k_agents`
- `chosen_agent_fqdn`
- `chosen_endpoint`
- `tie_break_applied`
- `selection_latency_ms`

`filtered_out` 中每个对象至少包含:

- `agent_fqdn`
- `reason`

`reason` 可取:

- `routing_fqdn_mismatch`
- `status_offline`
- `endpoint_missing`
- `schema_mismatch`

## 9. `IndProj04` 需要新增的工程内容

建议新增:

- `src/agentdns_routing/stage_c_selector.py`
- `src/agentdns_routing/stage_c_eval.py`
- `scripts/run_stage_c.py`
- `tests/test_stage_c.py`

同时需要把 `Stage C` 接到现有统一链路上:

- `routing_chain`
- `routing_run_trace.schema.json`
- `run_routing_ab_experiment.py` 的输出 contract

这次 `IndProj04` 侧的目标不是另写 demo，而是提供:

- 可被 `AgentDNSDemo` 调用的 routing service
- 可被测试与评测脚本验证的 `Stage C`

## 10. `AgentDNSDemo` 需要新增的工程内容

### 10.1 backend

- registry snapshot 导出接口
- Agent Card 导出接口
- 调用 `IndProj04` routing service
- 执行最终 `endpoint`
- 落 `run_id + stage traces + selection trace`

### 10.2 frontend

- 增加 `routing_fqdn / agent_fqdn` 双层展示
- 增加 `Stage R/A/B/C` trace viewer
- 增加 `Stage C top_k_agents` 排行展示
- 高亮 `chosen_agent_fqdn`
- 展示 `final/base/health/fair_agent/fair_provider`

## 11. 验收标准

### 11.1 工程验收

- `AgentDNSDemo` 能调用 `IndProj04` routing service
- `selected_primary_fqdn -> chosen_agent_fqdn -> endpoint` 全链路打通
- `selection_trace` 可落盘、可展示

### 11.2 指标验收

至少输出:

- `SelectionLatency_p50/p95`
- `ProviderCoverage`
- `ProviderMaxShare`
- `UnavailableAgentSkipRate`
- `TieRate`

### 11.3 demo 验收

至少 2-3 个正式 case 可展示:

1. `Stage A` 直接通过，进入 `Stage C`
2. `Stage B` 触发后再进入 `Stage C`
3. 多 agent 竞争时，`Stage C` 的排序和选择理由可展示

## 12. 实施顺序

### Phase 1

先在 `IndProj04` 完成:

- `Stage C selector`
- `selection_trace`
- `Stage C tests`
- routing service contract

### Phase 2

在 `AgentDNSDemo` 完成:

- registry snapshot
- Agent Card export
- routing service 调用
- UI 展示

### Phase 3

打通端到端:

- `query -> routing_fqdn -> agent_fqdn -> endpoint`

### Phase 4

补答辩证据:

- `SelectionLatency`
- fairness 指标
- 2-3 个完整 trace 样例

## 13. Owner 建议

这一步建议由我主推进实现，算法负责人负责 review。

原因:

- `Stage C` 已有明确 contract
- 它的核心不是继续发明新算法
- 它更像跨仓联动与结构化工程实现

推荐分工:

- 我:
  - 负责 `IndProj04` 的 `Stage C`
  - 负责 `AgentDNSDemo` 联动改造
  - 负责 trace / API / UI 对齐
- 算法负责人:
  - 审评分函数
  - 审 fairness / health / schema 逻辑
  - 审 `Stage C` 是否与当前 `A_llm_v2 + B_packetv2` 口径一致

## 14. 当前不做的事

- 不把 `Stage C` 做成新的研究课题
- 不引入 bandit / RL
- 不在 `Stage C` 引入 LLM
- 不实现完整 A2A SDK
- 不在 `AgentDNSDemo` 中复制一套独立的 `Stage A/B/C`
