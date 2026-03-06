# 命名空间冻结 v1（namespace_v1）

> 目的: 把“语义路由决策服务”做成可验收、可复现的任务。后续数据集、实验、专利、PPT 都引用这一版。
> 冻结时间目标: 2026-03-11（Week 1 里程碑 M1）

## 1. 版本号
- namespace_version: `ns_v1_20260311`
- country_root: `cn`

## 2. FQDN 规则（能力/智能体地址）
- 统一格式: `l3.l2.l1.cn`
- 允许空缺:
  - 无 `l3` 时: `l2.l1.cn`
  - 无 `l2` 时: `l1.cn`（不推荐作为 ground truth，仅用于候选兜底）
- 层级说明:
  - v1 先冻结为“最多 3 层 label”（`l1/l2/l3`）以控制任务量
  - 如确实需要更深层级或改语义，必须升 `namespace_version`（例如 `ns_v2_*`），不要在 v1 上原地改
- 字符集:
  - `l1/l2/l3` 仅使用 `[a-z0-9-]` 小写（需要中文时做映射，如 `云南 -> yunnan`）

## 2.1 routing_fqdn 与 agent_fqdn 的关系（关键口径）
v1 里把“命名空间/标签体系”和“具体 Agent 实例”分开，避免后续争议:
- `routing_fqdn`（也可叫 `capability_fqdn`）:
  - 含义: “能力/类别”的语义地址，用于路由决策与验收评测的 ground truth
  - 例子: `itinerary.travel.cn`、`beijing.hotel.travel.cn`、`verify.invoice.finance.cn`、`summary.meeting.productivity.cn`、`data.compliance.security.cn`、`weather.cn`
- `agent_fqdn`:
  - 含义: “某个具体 Agent 实例”的地址，挂在对应 `routing_fqdn` 的受管子域下
  - 规则: `{agent_code}.agent.{routing_fqdn}`
  - 例子: `agent-skyroute-planner-a.agent.itinerary.travel.cn`

结项/论文评测建议:
- 主任务评测输出用 `routing_fqdn`（稳定、可标注、可复现）。
- demo/工程扩展可进一步在 `routing_fqdn` 下做 agent discovery（从一组 `agent_fqdn` 里再选最终执行者）。

## 2.2 canonical routing_fqdn 合同（v1 新增，防返工）
v1 明确把 `l3` 的“数据维护形式”和“工程消费形式”分开:
- descriptor 数据层:
  - 只存 base row，例如 `invoice.finance.cn`、`compliance.security.cn`、`meeting.productivity.cn`
  - `l3` 作为 `segments` 字典挂在 base row 下
- 工程消费层:
  - 一律通过 resolver 物化成 canonical `routing_fqdn`
  - 规则固定为: `<segment>.<base_fqdn>`
  - 示例:
    - `verify.invoice.finance.cn`
    - `data.compliance.security.cn`
    - `schedule.meeting.productivity.cn`
    - `yunnan.hotel.travel.cn`

约束:
- gold 数据集中的 `ground_truth_fqdn/relevant_fqdns/acceptable_fqdns` 必须已经使用 canonical 表示
- Stage A 的 exact match、Stage C 的 registry 过滤、评测脚本的合法性检查，全部针对 canonical `routing_fqdn`
- 不允许一部分地方用 `segments`，另一部分地方用展开后的 fqdn，避免后续 exact match 返工

## 3. L1 领域（domain）
来自现有 AgentDNSDemo 的 domain 规划（保证与你半成品一致）:
- `travel` 旅行出行
- `weather` 天气
- `finance` 财务/税务/发票/预算
- `security` 风险/合规/审计/反欺诈
- `productivity` 会议/文档/效率
- `commerce` 价格/优惠/采购
- `health` 健康/营养/健身/就医
- `education` 课程/学习/辅导
- `gov` 政策/许可/政务

## 4. L2 能力（capability）
### travel
- `itinerary.travel.cn` 行程规划
- `hotel.travel.cn` 酒店
- `flight.travel.cn` 机票/航班
- `restaurant.travel.cn` 餐厅
- `activity.travel.cn` 景点/活动
- `transport.travel.cn` 交通/通勤

### weather
- `weather.cn` 天气查询（该能力在 v1 允许缺省 `l2`，与现有 demo 一致；见第 6 节）

### finance
- `budget.finance.cn` 预算
- `invoice.finance.cn` 发票
- `tax.finance.cn` 税务
- `invest.finance.cn` 投资

### security
- `risk.security.cn` 风险
- `compliance.security.cn` 合规
- `fraud.security.cn` 反欺诈

### productivity
- `meeting.productivity.cn` 会议纪要/安排
- `docs.productivity.cn` 文档总结/写作

### commerce
- `price.commerce.cn` 比价/价格
- `coupon.commerce.cn` 优惠/折扣

### health
- `nutrition.health.cn` 营养
- `fitness.health.cn` 健身
- `clinic.health.cn` 就医/门诊

### education
- `course.education.cn` 课程学习
- `tutoring.education.cn` 辅导/导师

### gov
- `policy.gov.cn` 政策查询
- `permit.gov.cn` 许可/审批

## 5. L3 细分（可选）
v1 允许 `l3` 作为“可选细分 label”（segment）。关键规则:
- `l3` 不要求像 `l1/l2` 那样全局统一含义。
- 但 `l3` 必须在同一个 `l2.l1` 子树下保持含义一致，并且需要冻结一个小字典（allowed set），否则标注与复现会失控。
- v1 只对少量 `l2.l1` 开启 `l3`（跨多个 L1 领域），其余能力默认不用 `l3`。

### 5.1 v1 启用 l3 的子树与字典（冻结）
travel（`l3=destination`，目的地/城市）:
- `hotel.travel.cn`:
  - `beijing/shanghai/chengdu/xian/hangzhou/guangzhou/shenzhen/yunnan`
- `itinerary.travel.cn`:
  - `beijing/shanghai/chengdu/xian/hangzhou/guangzhou/shenzhen/yunnan`

finance（`l3=subtask`，发票子任务）:
- `invoice.finance.cn`:
  - `issue/verify/reimburse`

productivity（`l3=task_type`，会议子任务）:
- `meeting.productivity.cn`:
  - `schedule/summary/action-items`

security（`l3=object_type`，合规对象）:
- `compliance.security.cn`:
  - `data/account/transaction`

## 6. 候选生成与兼容规则（用于 demo/评测）
为了兼容现有 demo 的候选形式，允许候选集中出现以下“别名/兜底” fqdn。标注口径建议:
- v1 的主评测粒度以 `l2.l1.cn` 为主；当 query/context 明确出现某个 `l3` 维度，并且该 `l2.l1` 在第 5 节被标记为启用 `l3` 时，允许用 `l3.l2.l1.cn` 作为 ground truth，并把 `l2.l1.cn` 放进 `acceptable_fqdns` 用于消解争议。
- 其它领域优先用第 4 节列出的能力 fqdn（`l2.l1.cn` 或 `l1.cn`）。
- 天气候选:
  - `weather.cn`
  - `weather.travel.cn`
- 对启用 `l3` 的子树（见第 5 节）:
  - 候选集必须包含:
    - `{l3}.{l2}.{l1}.cn`（多个不同 `l3` 的强干扰）
    - `{l2}.{l1}.cn`（粗粒度回落）

## 7. 风险/治理标签（v1 最小集）
用于 Stage B 触发与结项口径（可信标识/可控性）:
- `risk_level`: `low | medium | high`
- v1 规则:
  - 默认 `low`
  - `security.*` 默认 `high`
  - `gov.*` 默认 `medium`
