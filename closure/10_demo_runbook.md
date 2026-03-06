# Demo 运行脚本 v1（结项答辩可复现）

> 目的: 让答辩 Demo 稳到“照本宣科”。现场任何不确定性都用录屏兜底。

## 1. Demo 讲述主线（30 秒）
- 我们做的是“语义路由决策服务”: 输入自然语言需求，输出应调用的能力/智能体地址（fqdn）。
- 系统先经过 Stage R 命名空间召回，再由 Stage A/B 在候选集中区分 `primary + related` 路由。
- 在候选集约束下，Stage A 快路径能覆盖大多数请求。
- 对低置信/高风险/冲突样本，触发 Stage B 多智能体共识，输出可审计轨迹（任务书的可信标识/行为链）。

## 2. Demo 固定流程（每个案例 60-90 秒）
每个案例都按同一结构演示:
1. 展示 `query`
2. 展示 Stage R 实时生成的 `fqdn_candidates`
3. Stage A 输出 `selected_primary_fqdn + selected_related_fqdns + routing_top_k + confidence + 约束检查`
4. 是否触发 Stage B（解释触发原因）
5. Stage B 多轮轨迹（只展示关键两轮，避免拖时间）
6. 最终 `selected_primary_fqdn + selected_related_fqdns` + 简短解释
7. 下一跳发现（必须）: 展示 `selected_primary_fqdn -> {agent_fqdn列表}`，并展示 score breakdown（`final/base/health/fair/provider_fair`）与 `chosen_agent_fqdn -> endpoint`
8. 展示 trace 的“可核验字段”（agent_id/role/version/run_id/hash 等）

## 3. 推荐 3 个固定案例（v1）
### Case 1（高确定性，展示快路径）
- query: “帮我安排一个明天下午 2 点的 30 分钟会议，邀请张三李四，发个日程。”
- 预期: Stage A 直接路由到 `schedule.meeting.productivity.cn`（l3 细分）
- 卖点: 不需要每次都跑多智能体，快；并且 l3 不是只有 travel/目的地才有

### Case 2（多意图/干扰，展示共识修正）
- query: “我 4 月去云南玩 7 天游，预算 6000，做行程并顺便看看天气。”
- 预期: Stage A 可能在 `weather.cn` 与 `yunnan.itinerary.travel.cn` 间摇摆
- 触发: low_confidence / small_margin
- 卖点: 多智能体把主意图锚定到 `itinerary`，并把天气作为可接受附加建议（acceptable set）

### Case 3（高风险/治理，展示可控性与审计）
- query: “帮我做一个数据合规检查清单，看看这个流程有没有风险点。”
- 预期: 触发 Stage B（high_risk），路由到 `data.compliance.security.cn`（或回落到 `compliance.security.cn`）
- 卖点: 风险类请求强制慢路径，有迹可循，责任链可复核

## 4. 录屏兜底（必做）
- 录屏时长: 3-5 分钟
- 录屏内容: 按 Case 1->2->3 跑一遍
- 录屏要包含:
  - run_id/时间戳
  - Stage A/B 的关键输出
  - 轨迹视图（哪怕是 JSON 展示也行）

## 5. 评审常问 Q&A（答辩备份页）
- Q: “没有真实业务数据，可信么？”
  - A: 我们做的是原型验证。真实标签反馈落到: 固定命名空间 + 标注指南 + 一致性抽检 + 可复现数据集与脚本。
- Q: “多智能体太慢，怎么实装？”
  - A: 我们不把慢路径放进 DNS 数据平面。Stage B 是控制平面/冷启动/低置信兜底，结果写缓存，常规请求走快路径。我们报告 escalation_rate 与 P50/P95 延迟证明成本可控。
- Q: “为什么不用向量库？”
  - A: 向量最多是 Stage R 命名空间召回的一种实现。我们的核心贡献在候选集内的受约束决策、`primary + related` 区分、稳定性与可审计轨迹，这是向量相似度本身无法给出的。
