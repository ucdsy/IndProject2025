# Conversation Orchestrator 设计说明（2026-03-30）

> 目的: 解决 `AgentDNSDemo` 当前多轮对话中“每轮都像新请求”“补信息时仍重新路由”“执行后没有任务级记忆”的问题。
>
> 定位: 这是 `Stage R/A/B/C` 之上的**对话编排层**设计，不替代现有路由与选 agent 链路。

## 1. 结论先行

不要把整段对话直接做成一个“大而全的聊天智能体”。

应该新增一个 **Conversation Orchestrator**，负责:

1. 判断当前用户输入是在:
   - 继续当前任务
   - 补充缺失信息
   - 基于上轮结果继续细化
   - 开启一个全新任务
2. 维护会话级与任务级状态
3. 决定本轮是否需要重新进入 `Stage R/A/B/C`
4. 将用户补充信息与上轮执行结果组织成稳定的多轮任务流

一句话:

> `R/A/B/C` 决定“这句话该路由到哪、选哪个 agent”；  
> `Conversation Orchestrator` 决定“这句话是不是还在同一个任务里、要不要重新路由”。

## 2. 为什么不能把整个对话做成一个大 agent

如果把整个 chat 直接交给一个自由发挥的 agent，会出现三个问题:

1. `R/A/B/C` 的可解释性会下降  
   当前系统的重要价值之一是 `routing_trace` 和 `selection_trace`。一个大对话 agent 很容易把“补信息”和“新任务”混成黑箱。

2. 多轮状态会变成隐式上下文  
   你们需要的是**任务记忆**，不是无限聊天上下文。隐式上下文难以审计，也难以控制何时 reroute。

3. 用户只是在补一个预算或品牌时，系统也可能重新进入路由  
   这会让当前任务不断漂移，前端体验也会不稳定。

## 3. 设计目标

Conversation Orchestrator 的目标不是更聪明，而是更稳:

1. 让系统能识别“这轮是在继续当前任务”
2. 让系统能识别“这轮是在回答上轮追问的缺失信息”
3. 让系统只在需要时才重新走 `R/A/B/C`
4. 让 `AgentDNSDemo` 页面展示出清晰的任务状态
5. 保持 `IndProj04` 仍是 `R/A/B/C` 真源，不在 demo 里复制一套路由逻辑

## 4. 总体架构

新增一层:

`User Turn -> Conversation Orchestrator -> (reuse current task OR call IndProj04 R/A/B/C) -> Stage C selected agent -> execution -> updated task state`

职责划分:

- `IndProj04`
  - 继续负责 `Stage R/A/B/C`
  - 继续负责 routing/selection trace
- `AgentDNSDemo`
  - 新增 Conversation Orchestrator
  - 负责会话状态、任务状态、追问补槽与最终展示

## 5. 核心对象

### 5.1 `ConversationSession`

一条用户会话，只保存当前聊天所需的最小状态。

建议结构:

```json
{
  "session_id": "sess_xxx",
  "active_task_id": "task_xxx",
  "task_order": ["task_xxx", "task_yyy"],
  "last_user_query": "最新用户输入",
  "last_assistant_message": "最新系统回复摘要",
  "status": "active",
  "created_at": "...",
  "updated_at": "..."
}
```

### 5.2 `TaskState`

任务级状态，是多轮“记忆”的核心。

建议结构:

```json
{
  "task_id": "task_xxx",
  "task_status": "running | waiting_for_user | completed | suspended",
  "task_type": "coupon | price | docs | meeting | travel | ...",
  "query_history": [
    "初始请求",
    "后续补充"
  ],
  "routing_fqdn": "coupon.commerce.cn",
  "selected_related_fqdns": [],
  "chosen_agent_fqdn": "agent-couponmate-b.agent.coupon.commerce.cn",
  "endpoint": "http://localhost:8001/mock/agent/39/invoke",
  "entities": {
    "budget": 500,
    "brand_preference": ["Sony", "Jabra"]
  },
  "missing_slots": [
    {
      "name": "budget",
      "question": "预算大概多少？",
      "required": true
    }
  ],
  "last_execution_result": {
    "execution_status": "need_more_info | success | partial",
    "result_summary": "...",
    "execution_items": []
  },
  "routing_trace": [],
  "selection_trace": {},
  "created_at": "...",
  "updated_at": "..."
}
```

### 5.3 `TurnDecision`

这是对当前用户一轮输入的分类结果，用来控制是否 reroute。

建议结构:

```json
{
  "turn_type": "continue_current_task | answer_missing_info | refine_previous_result | start_new_task",
  "confidence": 0.92,
  "should_reroute": false,
  "should_reexecute": true,
  "target_task_id": "task_xxx",
  "slot_updates": {
    "budget": 500
  },
  "reason": "用户在回答上轮缺失槽位"
}
```

## 6. Turn 类型定义

### 6.1 `continue_current_task`

用户仍在推进同一个目标，没有明显换题。

例子:
- “再具体一点”
- “那先看最便宜的”
- “优先官方旗舰店”

处理策略:
- 不 reroute
- 沿用当前 `TaskState`
- 直接重新执行当前 agent 或基于当前结果细化

### 6.2 `answer_missing_info`

用户在补系统刚刚追问的信息。

例子:
- “预算 500 左右”
- “品牌优先索尼”
- “最好防水”

处理策略:
- 不 reroute
- 写入 `slot_updates`
- 更新 `entities`
- 如果关键槽位已满足，重新执行当前任务

### 6.3 `refine_previous_result`

用户不一定在回答问题，但仍围绕当前结果做约束或过滤。

例子:
- “只看京东和天猫”
- “不要入耳式”
- “给我按价格排序”

处理策略:
- 默认不 reroute
- 把新约束写回当前任务
- 重新执行当前 agent

### 6.4 `start_new_task`

用户明显换题，进入新任务。

例子:
- 上一轮还在买耳机，这一轮说“顺便看看杭州周末会不会下雨”
- 上一轮还在优惠，这一轮说“帮我查发票验真”

处理策略:
- 新建 `TaskState`
- 重新进入 `IndProj04 /api/routing/resolve`

## 7. 何时 reroute

### 7.1 必须 reroute

满足以下任一情况:

1. 当前没有 active task
2. 当前输入与 active task 的领域明显不一致
3. 当前输入包含新任务锚点，且与当前任务目标冲突

### 7.2 默认不 reroute

满足以下情况时:

1. 用户在补系统明确追问的槽位
2. 用户只是增加限制条件
3. 用户在要求更详细、更便宜、更高优先级等局部 refinement

### 7.3 推荐规则

先做一个轻量 `turn classifier`，不要一上来就做复杂自由式 agent。

建议输出:

```json
{
  "turn_type": "...",
  "should_reroute": true/false,
  "should_reexecute": true/false,
  "slot_updates": {},
  "reason": "..."
}
```

## 8. 缺失槽位机制

这是多轮体验的关键，不应再靠自然语言“随缘追问”。

每次执行完成后，agent 或执行层应可返回:

```json
{
  "execution_status": "need_more_info",
  "result_summary": "已定位到优惠入口，但要继续筛选还需要更多条件。",
  "missing_slots": [
    {
      "name": "budget",
      "question": "预算大概多少？",
      "required": true
    },
    {
      "name": "brand_preference",
      "question": "有偏好的品牌吗？",
      "required": false
    }
  ],
  "next_action": "等待用户补充信息后继续执行。"
}
```

前端看到 `missing_slots` 后，应当:

1. 在执行状态区明确展示“当前等待补充信息”
2. 将这些问题可视化展示给用户
3. 用户下一轮回答时，优先走 `answer_missing_info`

## 9. API 设计

### 9.1 新增会话级入口

建议在 `AgentDNSDemo` 后端新增统一入口，而不是让前端自己决定何时 reroute:

`POST /api/conversation/turn`

请求:

```json
{
  "session_id": "sess_xxx",
  "message": "预算 500 左右，优先索尼",
  "top_k": 3
}
```

响应:

```json
{
  "session_id": "sess_xxx",
  "active_task_id": "task_xxx",
  "turn_decision": {
    "turn_type": "answer_missing_info",
    "should_reroute": false,
    "should_reexecute": true
  },
  "task_state": {},
  "routing_result": {},
  "execution_result": {},
  "assistant_message": "..."
}
```

### 9.2 保留现有接口

现有接口先继续保留:

- `/api/routing/resolve`
- `/api/execute`
- `/api/client/assist`

但未来 `/api/client/assist` 应该逐步退化为对 `/api/conversation/turn` 的薄封装，而不是自己直接拼整条链。

## 10. 在 `AgentDNSDemo` 中建议新增/修改的文件

### 10.1 后端建议新增

- `backend/app/services/conversation_orchestrator.py`
  - 对话编排主逻辑
- `backend/app/services/conversation_state.py`
  - session/task 状态读写
- `backend/app/services/turn_classifier.py`
  - 当前输入是继续任务还是新任务

### 10.2 后端建议修改

- `backend/app/schemas.py`
  - 新增 `ConversationTurnRequest/Response`
- `backend/app/routers/client.py`
  - 从直接拼接 `routing -> execute` 改为经由 orchestrator
- `backend/app/routers/execute.py`
  - 接受 `missing_slots`
  - 将 `execution_status / next_action / missing_slots` 写回任务状态

### 10.3 前端建议修改

- `frontend/src/lib/types.ts`
  - 新增 conversation/task 类型
- `frontend/src/lib/api.ts`
  - 新增 `conversationTurn(...)`
- `frontend/src/app/chat/page.tsx`
  - 从单轮“发送->路由->选 agent->执行”改成“发送->orchestrator 决策”

## 11. 页面改造建议

### 11.1 新增“当前任务卡”

展示:
- 当前任务类型
- 当前 `routing_fqdn`
- 当前 `chosen_agent_fqdn`
- 当前状态:
  - `running`
  - `waiting_for_user`
  - `completed`

### 11.2 新增“待补信息”区

如果存在 `missing_slots`，页面直接展示:

- 预算大概多少？
- 品牌偏好是什么？
- 是否需要某些功能？

这样用户知道自己是在**补信息**，不是在**重新开新任务**。

### 11.3 保留 `R/A/B/C` trace 展示

但要明确:
- 不是每轮用户输入都会重新产生一套 trace
- 只有在 `should_reroute=true` 时，右侧 trace 才更新为新的任务

## 12. 实施顺序

### Phase 1

先落状态对象与 turn classifier:

1. `ConversationSession`
2. `TaskState`
3. `TurnDecision`

### Phase 2

把 `missing_slots` 接入执行层:

1. 执行后返回 `missing_slots`
2. 前端可展示
3. 用户下一轮可补槽

### Phase 3

新增 `/api/conversation/turn`:

1. `continue_current_task`
2. `answer_missing_info`
3. `refine_previous_result`
4. `start_new_task`

### Phase 4

再将现有 `/api/client/assist` 收敛为 orchestrator 封装层。

## 13. 关键边界

### 13.1 不能做成黑箱

Conversation Orchestrator 的输出必须结构化，至少包含:

- `turn_type`
- `should_reroute`
- `should_reexecute`
- `target_task_id`
- `slot_updates`
- `reason`

### 13.2 不能替代 `R/A/B/C`

它只负责决定:
- 要不要重新路由
- 要不要继续当前任务

不负责替代:
- `Stage R`
- `Stage A`
- `Stage B`
- `Stage C`

### 13.3 当前阶段不做长期个性记忆

先只做:
- session memory
- task memory

长期 preference memory 可以后续再扩。

## 14. 推荐结论

当前最合理的路线是:

1. 不把整个对话直接做成一个“大聊天 agent”
2. 在 `AgentDNSDemo` 上层新增 `Conversation Orchestrator`
3. 先做任务记忆和补槽
4. 先解决“补信息不 reroute”这个核心体验问题

一句话:

> 下一步不是把 chat 变成更大的 agent，  
> 而是给现有 `R/A/B/C` 外面加一个**受约束的对话编排层**。
