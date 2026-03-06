# Namespace、routing_fqdn、agent_fqdn、Agent Card：一张图讲清楚

> 目的: 把“命名方式”和“注册发现怎么落地”讲成可实现、可验收的规格，并与现有 AgentDNSDemo 对齐。

## 1. 五个概念（结项口径建议固定用这套词）
- `namespace`（命名空间/标签体系）
  - 是一棵稳定的“能力树”，定义有哪些能力节点，以及它们的 canonical `routing_fqdn`。
  - 结项与论文评测主要围绕它做（有 ground truth、有约束、有一致性抽检）。
- `namespace descriptor`（命名空间节点描述）
  - 描述一个 `routing_fqdn` 节点的语义信息，而不是 agent 实例。
  - 建议字段: `fqdn/aliases/desc/examples/industry_tags/risk_tags/parent/children/allowed_l3/fallback_to`
  - Stage R 的召回对象应该是它，不是 Agent Card。
- `routing_fqdn`（能力地址 / capability fqdn）
  - 语义路由的主输出，表达“该把任务交给哪类能力”。
  - 示例: `hotel.travel.cn`、`yunnan.itinerary.travel.cn`、`verify.invoice.finance.cn`、`summary.meeting.productivity.cn`、`weather.cn`
- `agent_fqdn`（具体 Agent 实例地址）
  - 挂在 `routing_fqdn` 的受管子域下，用于“下一跳执行者选择”。
  - 规则: `{agent_code}.agent.{routing_fqdn}`
  - 示例: `agent-hotelscope-a.agent.hotel.travel.cn`
- `Agent Card`（智能体名片，A2A 常用）
  - 描述一个 agent 的身份、能力、通信方式、状态等，用于注册与发现。
  - 一个 `agent_fqdn` 应当能映射到一张 Agent Card（或其摘要）。

## 2. 最小闭环的数据关系（推荐）
建议把“路由”和“发现”拆成三步:
1. `query -> Stage R -> fqdn_candidates`（命名空间召回）
2. `fqdn_candidates -> Stage A/B -> selected_primary_fqdn + selected_related_fqdns`（决策/共识）
3. `selected_primary_fqdn -> agent_fqdn list -> chosen agent_fqdn -> endpoint`（发现/排序，纯结构化打分，通常很快，可缓存）

这样好处:
- `routing_fqdn` 稳定，便于标注与评测（结项主表）。
- `agent_fqdn` 动态，便于表达真实世界的上线需求（在线/负载/版本/灰度/公平曝光）。
- 第一跳不落到 agent registry，因此不会退化成 A2A 式“先找 agent 再决定能力”。

## 3. 与现有 AgentDNSDemo 的对应（你现在的 demo 已经实现了雏形）
AgentDNSDemo 数据库里已经有:
- `agents.fqdn`（就是 `routing_fqdn`）
- `agents.agent_fqdn`（就是 `{agent_code}.agent.{routing_fqdn}`）
- `dns_nodes`（命名空间树节点）
- `dns_records`（把 `routing_fqdn` 指向可调用 endpoint；一对多表示同一能力多 agent）

结论:
- 你现在不需要“从 0 重新设计命名”，只是把这层关系在文档/PPT 里讲清楚即可。

## 4. 命名方式怎么从“粗糙”变“可落地”（v1 建议）
v1 的目标不是完美，而是: 一致、可复现、可扩展到真实平台。

### 4.1 routing_fqdn（能力地址）的设计原则
- 足够短: 便于人读、便于做表格与审计
- 足够稳定: v1 冻结后不改（改就升版本号）
- 粒度以 “L2 能力” 为主，少量 `l2.l1` 子树启用 `L3=segment` 作为可解释细分
- `L3` 不要求全局统一语义，但必须按子树冻结含义与 allowed set（见 `closure/07_namespace_v1.md`），否则标注/复现会失控

### 4.2 agent_fqdn（实例地址）的设计原则
- 不把 UUID 硬塞进 fqdn（太长且不可读），UUID 放在 Agent Card 里
- `agent_code` 约定:
  - 建议结构: `{provider}-{role}-{variant}`（例如 `vendorA-hotel-v1`）
  - 长度限制: <= 48（demo 里已做裁剪）
- 保留 `.agent.` 作为受管子域，避免与能力节点混淆

### 4.3 多租户/环境（可选，v2）
如果你确实需要表达租户与环境，推荐加在 `agent_code` 或独立一层 label:
- 方案 A（最省改动）: `agent_code` 前缀包含租户/环境（如 `t1-prod-vendorA-hotel-v1`）
- 方案 B（更规范）: `{agent_code}.agent.{tenant}.{routing_fqdn}`（需要改 demo 逻辑与 UI）

## 5. Agent Card（参考你给的 A2A 注册发现方案）
你给的《A2A Agent 注册与发现服务技术实现方案》里对 Agent Card 的字段划分很标准，可直接复用到我们的“可信标识/行为链”里:
- 身份: `agent_id`（UUID）、`name`、`description`
- 通信: `base_url`、`version`、`authentication`
- 能力声明: `skills`（带 input/output schema）、`tags`、`capabilities`
- 状态: `status`、`created_at/updated_at`

落地建议:
- demo v1 不必做完整 A2A 协议，只要把 Agent Card 作为 registry 的记录格式即可。
- Stage C discovery v1 只做结构化过滤 + 结构化打分:
  - 按 `routing_fqdn` 精确过滤
  - 再按 schema/tag/health/fairness 排序
- 如果要做自然语言/embedding 检索，应发生在 Stage R 的 `namespace descriptor` 侧，而不是 Agent Card 侧。

## 6. 与专利/论文的关系（避免互相踩）
- 你同事的《语义专利设想》偏“语义描述框架 + 分层检索/匹配 + 动态评估优化”。
- 我们本项目的差异化建议放在:
  - 受约束的路由决策（`routing_fqdn`）如何用多智能体反馈驱动共识来“降波动、强解释”
  - 可信标识/行为链如何把“过程”变成可核验证据（结项与专利都吃这一点）
