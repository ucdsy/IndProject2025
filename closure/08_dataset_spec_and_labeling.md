# 数据集规格与标注规范 v1（AgentDNS Routing）

> 目的: 给“真实标签反馈约束”一个可验收的定义: 有固定命名空间、有 ground truth、有一致性抽检、有复现方式。
> 目标规模（v1）: 300-800 条样本（先覆盖标签树，再追求自然语言多样性）
>
> 重要约束: 数据构造不固定业务场景，需覆盖 `namespace_v1` 的多个 L1 领域；难点主要来自“查询诱导的混淆候选 + 约束/风险触发 + 快慢路径”，而不是随机拼装无关候选。
>
> 领域配比（v1 冻结）: 工信相关场景占比 **60%**（企业/产业/监管语境），其余场景 40% 用于干扰与泛化。

## 1. 任务定义
- 输入: `query`（自然语言，可带 `context`）
- 输出: `selected_primary_fqdn`（必须从候选里选 1 个）+ 可选 `selected_related_fqdns`/`routing_top_k`
- 约束: 命名空间合法、格式合法、候选约束满足、风险/治理规则不冲突

说明（避免混淆）:
- v1 数据集与评测只对 `routing_fqdn` 做监督与打分。
- 具体执行到某个 `agent_fqdn`（`{agent_code}.agent.{routing_fqdn}`）属于“下一跳发现”，可以在 demo 里展示，但不作为主表的 ground truth。
补充（贴合你“返回相关 agent 列表”的最终形态）:
- 线上形态可以返回 `routing_top_k`（多个相关能力候选）以及每个候选下的 `agent_fqdn` 列表。
- 但 v1 评测仍需要一个“主路由”作为监督锚点，因此保留单一 `ground_truth_fqdn`，同时可用 `relevant_fqdns` 表达“多相关”。
- Stage R 的目标应理解为“覆盖 `{ground_truth_fqdn} ∪ relevant_fqdns`”，而 Stage A/B 的目标应理解为“区分 primary 与 related”。

关键澄清:
- 主数据集不手工写 `fqdn_candidates`。
- `fqdn_candidates` 是 Stage R 的运行时产物，不是金标样本的一部分。
- 如需做公平对比或复现实验，可把固定版本 Stage R 生成的候选另存为 `candidate snapshot`，供 Stage A/B 各方法共用。

## 1.1 工信相关场景怎么落到现有 namespace（不加新域名）
不新增 L1，只通过“query 语境 + 题材分布”把样本主打工信:
- `permit.gov.cn`: 备案/许可/资质办理（如 ICP/增值电信/短信签名与模板报备/码号资源等）
- `policy.gov.cn`: 工信相关政策/标准条款解读（不做法律结论，只做信息检索与摘要）
- `invoice.finance.cn`（含 l3 子任务）: 企业开票/验真/报销流程
- `meeting.productivity.cn`、`docs.productivity.cn`: 企业会议与文档流转
- `compliance.security.cn`: 企业信息安全与合规检查清单（不强调“网信办”语境，按“工信/行业合规要求”表述）

## 2. 文件格式
- 存储: JSONL（每行一个样本）
- 字符编码: UTF-8
- 字段尽量保持稳定，便于后续脚本评测与可复现

## 3. 样本字段（推荐最小集）
每条样本建议包含:
- `id`（string）: 唯一 id，例如 `travel_000123`
- `namespace_version`（string）: 固定为 `ns_v1_20260311`
- `query`（string）: 自然语言请求（可中文/中英混合）
- `context`（object，可选）: 结构化上下文，如 `city`、`time_window`、`budget`、`channel`
- `constraints`（array）: 规则列表（字符串枚举）
  - v1 固定至少包含: `fqdn_format_valid`
- `ground_truth_fqdn`（string）: 主真值（即 ground truth routing_fqdn；`PrimaryAcc@1` 使用）
- `relevant_fqdns`（array，可选）: 相关能力集合（用于“返回列表”口径的 Recall@K/nDCG@K 等，可作为附录指标）
- `acceptable_fqdns`（array，可选）: 容错真值集合（用于更贴近真实业务的评测口径）
- `difficulty_tags`（array，可选）: 难度标签，如 `ambiguous`, `multi_intent`, `negation`, `high_risk`
- `intended_confusion_types`（array，可选）: 该 query 预期会诱导出的混淆类型，如 `multi_intent`, `sibling_competition`, `governance_fallback`

## 4. 运行时证据（不一定写进数据集，但必须落日志）
为满足任务书“可信标识/行为链”，每次运行至少落盘:
- `stage_r` 输出: `fqdn_candidates`、`descriptor_scores`、`confusion_sources`
- `run_id`、模型版本、提示版本、随机种子
- `stage_a` 输出: `top_k`、`confidence`、`escalate_to_stage_b`、失败原因（若有）
- `stage_b`（如触发）多轮 `routing_trace`（每轮候选、理由、打分、选择）

如需做可复现实验或公平对比，可额外导出:
- `candidate snapshot`（固定版本 Stage R 在某个 split 上生成的 `fqdn_candidates`）
- 用途: 让 `StageA-only / Vote / StageB / A->B gating` 共用同一版召回输入，隔离决策层差异

## 5. 标注规范（怎么写 ground truth）
### 5.1 标注目标
ground truth 标注的是“应该路由到的能力/地址”，不是最终业务执行结果。
- 示例: “我想吃汉堡王，帮我找离我最近的门店并看看有没有优惠。”
  - 建议标注为 `restaurant.travel.cn`（主意图是找餐厅/门店）
  - 可把 `coupon.commerce.cn` 放进 `acceptable_fqdns`，并标 `difficulty_tags=["multi_intent"]`
  - 不建议标注成“汉堡王专属 agent”，避免能力粒度过细导致不可复现

### 5.2 v1 粒度原则
- v1 的路由粒度以 L2 能力为主（`l2.l1.cn`）
- `l3` 只在少量样本中使用（建议总体 15%-30%），并且必须满足:
  - 该 `l2.l1` 在 `closure/07_namespace_v1.md` 的“l3 启用子树”里
  - `l3` 在该子树的 allowed set 里
  - query/context 明确出现该细分维度（例如目的地/子任务/对象类型）
  - 同时用 `acceptable_fqdns` 允许回落到对应的 `l2.l1.cn`（用于消解争议）
- 多意图句子:
  - 如果必须拆成多个 need，v1 先不做“多标签多输出”的复杂评测
  - 统一策略: 标注“主意图路由”，并把其它意图写进 `difficulty_tags=["multi_intent"]`

### 5.3 l3 的“可复现”纪律（避免被质疑拍脑袋）
- 不要求 `l3` 全局统一含义，但要求在同一个 `l2.l1` 子树下含义一致（例如 `invoice.finance.cn` 的 `l3` 就不要同时混用“发票类型”和“城市”）。
- 不在 v1 临时加新的 `l3` 值；如需新增，按 `ns_v2_*` 升版本。

### 5.4 acceptable_fqdns 的使用
当边界确实模糊时允许多真值（用于减少无意义争议）:
- 例如“云南 7 天游玩 + 每天看天气”
  - 如果任务定义要求只选 1 个，可把 `travel.itinerary` 作为 ground truth
  - acceptable 可包含 `weather.cn`（作为可接受的附加路由），并在分析中说明

## 6. Query 设计原则（让评审信服的关键）
主数据集不手工规定 `fqdn_candidates`，而是要求 query 本身足以诱导 Stage R 召回出一批合理会竞争的候选。

每条样本的 query 应尽量具备以下一种或多种特征:
- 多意图: 主诉求之外带次要诉求
- 兄弟节点竞争: 动作词/对象词能同时命中同子树多个能力
- 粗细粒度并存: 允许细粒度节点与父级回落节点同时有理由被召回
- 风险/治理伴随召回: 合规、备案、审查、风险等词会把治理类节点一并带出
- 少量跨域词面重叠: 但必须仍然可解释，不能变成随机噪声

关键纪律:
- 主表样本不允许依赖人工预塞无关候选来“制造难度”。
- 每条 query 都应能预期对应到一种或多种“混淆来源”，例如 `multi_intent / lexical_overlap / sibling_competition / governance_fallback / cross_domain_overlap`。
- 如果后续想证明更强鲁棒性，可以另建 `adversarial_negatives` 附录 split，但不要和主表混在一起。

## 6.1 数据构造建议（v1：先定真值再“反向造 query”）
由于 v1 要在有限时间内覆盖 taxonomy、控制争议并保证可复现，推荐 label-first 生成法:
- Step 1: 先选 `ground_truth_fqdn`（主路由）+ 可选 `relevant_fqdns`（其它相关能力）
- Step 2: 选一个场景模板（按 fqdn 分桶），填充 slot 生成 query（必要时加一条“次要诉求”制造 `multi_intent`）
- Step 3: 给该样本标一个或多个 `intended_confusion_types`
  - 例如: `multi_intent / sibling_competition / governance_fallback`
- Step 4: 人工抽检与复标，冻结 gold 数据集版本
- Step 5（运行时/评测时）: 由 Stage R 根据 query 真实生成 `fqdn_candidates`
- Step 6（可选）: 导出 `candidate snapshot` 供公平对比使用

这样好处:
- taxonomy 覆盖度可控（不会出现某些 fqdn 永远没样本）
- query 难度可控（避免“看一眼就知道答案”的数据）
- 多相关/多意图可以通过 `relevant_fqdns` + `acceptable_fqdns` 统一表达；Stage A/B 则负责把这些候选区分成 `primary` 与 `related`

## 7. 质量控制（最小可验收）
- 抽检比例: 10%-20% 样本做复标
- 统计:
  - 一致性（简单一致率即可，或 Cohen's kappa 加分）
  - 争议样本列表（写在附录里反而加分，说明你认真对待标签）
- 变更纪律:
  - 一旦进入 Week 2 以后，`namespace_version` 不再变
  - 如必须变更，必须升版本号（例如 `ns_v2_*`）并保留旧数据

## 8. 示例样本（v1）
### 8.1 Gold sample（不含候选）
```json
{
  "id": "travel_000001",
  "namespace_version": "ns_v1_20260311",
  "query": "我想 4 月去云南玩 7 天游，预算 6000，帮我做个行程并顺便看看天气。",
  "context": {"start_city": "Shanghai", "budget_rmb": 6000},
  "constraints": ["fqdn_format_valid"],
  "ground_truth_fqdn": "yunnan.itinerary.travel.cn",
  "relevant_fqdns": ["weather.cn"],
  "acceptable_fqdns": ["yunnan.itinerary.travel.cn", "itinerary.travel.cn"],
  "difficulty_tags": ["multi_intent"],
  "intended_confusion_types": ["multi_intent", "sibling_competition"]
}
```

```json
{
  "id": "finance_000001",
  "namespace_version": "ns_v1_20260311",
  "query": "我拿到一张发票，帮我验真并判断能不能报销。",
  "context": {"channel": "wechat"},
  "constraints": ["fqdn_format_valid"],
  "ground_truth_fqdn": "verify.invoice.finance.cn",
  "relevant_fqdns": ["reimburse.invoice.finance.cn"],
  "acceptable_fqdns": ["verify.invoice.finance.cn", "invoice.finance.cn"],
  "difficulty_tags": ["multi_intent"],
  "intended_confusion_types": ["multi_intent", "sibling_competition", "fallback"]
}
```

```json
{
  "id": "productivity_000001",
  "namespace_version": "ns_v1_20260311",
  "query": "把今天的会议内容总结成三条要点，并列出待办。",
  "context": {"time_window": "today"},
  "constraints": ["fqdn_format_valid"],
  "ground_truth_fqdn": "summary.meeting.productivity.cn",
  "relevant_fqdns": ["action-items.meeting.productivity.cn"],
  "acceptable_fqdns": ["summary.meeting.productivity.cn", "meeting.productivity.cn"],
  "difficulty_tags": [],
  "intended_confusion_types": ["multi_intent", "sibling_competition"]
}
```

### 8.2 Stage R candidate snapshot（运行时导出，不属于 gold 数据集）
```json
{
  "id": "finance_000001",
  "stage_r_version": "sr_v1_20260311",
  "fqdn_candidates": [
    {"fqdn": "verify.invoice.finance.cn", "score_r": 0.91, "source": ["lexical", "slot"]},
    {"fqdn": "reimburse.invoice.finance.cn", "score_r": 0.84, "source": ["secondary_intent", "slot"]},
    {"fqdn": "issue.invoice.finance.cn", "score_r": 0.63, "source": ["sibling_competition"]},
    {"fqdn": "invoice.finance.cn", "score_r": 0.59, "source": ["fallback"]},
    {"fqdn": "docs.productivity.cn", "score_r": 0.31, "source": ["cross_domain_overlap"]}
  ],
  "confusion_sources": ["multi_intent", "sibling_competition", "fallback"]
}
```
