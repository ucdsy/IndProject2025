# 设计总说明 v1：受约束语义路由决策服务（AgentDNS + Stage A/B）

> 目标: 在不依赖业务审核/注册数据的前提下，按任务书在 **2026-04-30** 前完成可验收结项包，并且交付物可直接复用为论文/专利素材。
>
> 本 doc 是“总设计说明”。执行细节和实验门槛已拆成子规格；这些子规格审查通过后，我再按冻结接口/字段/公式开始编程与出表。
>
> 补充: 本文现在承担“总设计说明”的角色。执行级规格与评审门槛统一收敛到:
> - `closure/14_execution_spec_and_review_gate.md`
>
> 当前实现状态修正:
> - 仓库中旧 `bootstrap Stage R/A` 代码已从主干清理；历史结果只保留为过程记录，不再作为可运行入口。
> - 它们不能作为正式方法、正式主表、或论文/结项的主证据直接继承。
> - 当前阶段的正确顺序是: 先完成正式 gold 数据集与 blind protocol，再重做 clean Stage R / Stage A。

## 0. 结论先行（你最终交付什么）
结项包最小闭环（任务书硬指标）:
- 1 套多智能体协作原型（AgentDNSDemo 承载）
- 1 套可复现实验（自建标注集 + 3 张表 + 复现命令）
- 1 套可审计轨迹（routing_trace / audit）
- 1 件专利材料（选题 A，提交证据）
- 1 份论文体裁报告（method/exp/analysis）
- 1 份答辩 PPT + 录屏 demo

核心口径（统一对外说法）:
- 我们做的是 **受约束的语义路由决策服务**：先在命名空间节点上做召回，形成候选 `routing_fqdn` 集合；再由单智能体/多智能体决策层从中给出 `primary + related` 路由；最后执行 Stage C “下一跳发现”，把 `primary routing_fqdn` 落到 `agent_fqdn -> endpoint`（真实可调用地址），并输出可审计打分依据。

## 1. 范围与非目标（避免任务量膨胀）
### 1.1 必做范围
- 固定命名空间（namespace_v1）与两跳命名:
  - `routing_fqdn`（能力地址，主评测输出）
  - `agent_fqdn`（实例地址，demo 加分）
- Stage A/B（快慢路径）+ 触发率指标:
  - Stage A: 单智能体快决策 + 置信度 + 约束检查
  - Stage B: 多智能体异质生成 + 反馈驱动共识 + 可信轨迹
- Stage C 下一跳发现（必须有）:
  - `routing_fqdn -> agent_fqdn -> endpoint`（落到“真实地址”，并输出可审计的打分依据）
- 自建标注集 v0（300-800，工信相关场景占比 60%）+ 三张表（主表/消融/成本稳定性）
- demo 固定脚本（3 个 case）+ 录屏兜底

### 1.2 非目标
- 不把 Stage B 放进 DNS 数据平面（不做“递归解析器替换”）
- 不实现完整 A2A SDK 协议栈（只做 Agent Card 字段对齐/导出）
- 不做 bandit/RL 排序作为 v1 必需项（可作为 v2/附录）
- 不追求生产可用的高可用/多租户/权限系统（原型验证为主）

## 2. 概念与数据对象（必须在 PPT 一张图讲清楚）
### 2.1 命名空间（namespace）与两类 fqdn
参见 `closure/07_namespace_v1.md`、`closure/11_agent_registry_and_naming.md`，本 doc 复述关键点:
- `routing_fqdn`（能力地址）: `l3.l2.l1.cn`（可缺省部分 label）
  - 示例: `hotel.travel.cn`、`yunnan.itinerary.travel.cn`、`verify.invoice.finance.cn`、`summary.meeting.productivity.cn`、`weather.cn`
  - 作为 ground truth / `PrimaryAcc@1` 的监督目标（v1 以 `l2.l1.cn` 为主；`l3` 是可选 segment，只在少量“启用 l3 的子树”里出现，并用 `acceptable_fqdns` 消解争议；见 `closure/07_namespace_v1.md`）
- `agent_fqdn`（实例地址）: `{agent_code}.agent.{routing_fqdn}`
  - 示例: `agent-hotelscope-a.agent.hotel.travel.cn`
  - 用于下一跳执行者选择（可缓存、可按在线状态/公平性/多样性排序）

### 2.2 Stage R/A/B/C（控制平面 vs 数据平面）
- Stage R（命名空间召回层）: `query + context -> fqdn_candidates`
  - 检索对象是命名空间节点/`routing_fqdn` 描述，不是 agent card
  - v1 采用“命名空间节点描述 + 词法/元数据打分”的轻量召回；向量召回是可插拔增强，不是单独一层大工程
- Stage A（快路径决策）: `query + candidates -> selected_primary_fqdn + selected_related_fqdns + confidence`
- Stage B（慢路径共识）: 低置信/高风险/冲突样本触发，输出共识后的 `primary + related` 路由 + `routing_trace`
- Stage C（下一跳发现）: `selected_primary_fqdn -> agent_fqdn list -> chosen agent_fqdn -> endpoint`

说明:
- 结项“不会太慢”的论据来自:
  - `escalation_rate`（Stage B 触发率）
  - `Latency/Calls/Tokens`（成本表）
  - “Stage B 仅用于控制平面/冷启动/兜底，结果写缓存”

## 3. 数据集与字段（可复现实验的根）
数据集规格见 `closure/08_dataset_spec_and_labeling.md`，这里补充“运行时证据字段”与 split。
强调: 数据构造不固定成 travel 单一场景，应覆盖 `namespace_v1` 的多个 L1 领域；重点是“候选内的受约束决策 + 快慢路径触发 + 可审计轨迹”的证据闭环。
补充: 为避免“只有两层太简略”的质疑，v1 会在少量子树上启用 `l3`（跨多个 L1 领域），并在评测里增加 l3 子集指标（FineAcc@1/HierDistance）作为附表证据。
领域占比（v1，按“主打工信场景”冻结）:
- 工信相关场景 60%: 用企业/产业/监管语境写 query（许可/备案/合规/发票/流程/系统接入等），主要落在 `gov/security/finance/productivity`。
- 其它场景 40%: 保留 travel/weather/commerce 等作为干扰与泛化验证。

### 3.1 文件
- `data/agentdns_routing/dev.jsonl`
- `data/agentdns_routing/test.jsonl`
- `data/agentdns_routing/labeling_guide.md`（标注指南）

当前冻结的重建顺序:
1. 保留 `namespace/canonical contract`
2. 先完成正式 gold 数据集、blind split、challenge split
3. 冻结“可用于算法的知识源”与“不可使用的金标泄漏源”
4. 在冻结数据上重做 clean Stage R
5. 在冻结 Stage R snapshot 上重做 clean Stage A
6. Stage C 后置，Stage B 最后实现

### 3.2 每条样本（最小字段）
- `id`, `namespace_version`, `query`, `context`(opt)
- `ground_truth_fqdn`（routing_fqdn）
- `relevant_fqdns`(opt)
- `acceptable_fqdns`(opt)
- `intended_confusion_types`(opt)
- `constraints[]`, `difficulty_tags[]`(opt)

说明:
- `fqdn_candidates` 不属于 gold 数据集字段，而是 Stage R 的运行时输出。
- 为了可复现实验与公平比较，可把某个固定版本 Stage R 生成的 `fqdn_candidates` 另存为 `candidate snapshot`，供 Stage A/B 各方法共用。

### 3.3 Stage A/B 运行输出（必须落 trace）
每条样本每次运行必须落:
- `run_id`, `model`, `prompt_version`, `seed`, `temperature`
- Stage R:
  - `fqdn_candidates[{fqdn, score_r, source[]}]`
  - `descriptor_scores`
  - `confusion_sources[]`
- Stage A:
  - `routing_top_k[{fqdn, score, role}]`
  - `selected_primary_fqdn`
  - `selected_related_fqdns`
  - `confidence`
  - `constraint_check{pass, reasons[]}`
  - `escalate_to_stage_b` + `escalation_reasons[]`
- Stage B（触发时）:
  - 每轮 `round_i` 的:
    - `agent_id/agent_fqdn/role/version`
    - `proposal{primary_fqdn, related_fqdns, rationale, confidence, cited_tags[]}`
    - `criticisms[]` / `revisions[]`（可简化）
    - `feedback_scores{...}`（见第 5 节）
  - `final_selected_primary_fqdn`
  - `final_selected_related_fqdns`
  - `convergence{rounds, stop_reason}`

## 4. Stage R：命名空间召回（recall 层）
执行细化: 见 `closure/14_execution_spec_and_review_gate.md`
### 4.1 v1 实现（不加任务量）
- v1 不把第一跳做成 “agent card 检索”，而是对命名空间节点做召回。
- 离线维护一份 `namespace descriptor` / `routing node profile`:
  - `fqdn`
  - `aliases`
  - `desc`
  - `examples`
  - `industry_tags`
  - `risk_tags`
  - `parent/children`
  - `allowed_l3`
  - `fallback_to`
- 在线召回时，先抽结构化证据，再对上述节点描述做检索/打分，形成 `fqdn_candidates`。
- 主数据集只负责定义 `ground_truth_fqdn/relevant_fqdns/query`，不手工预塞 `fqdn_candidates`。
- 如需公平比较 Stage A/B，不同方法共用一份固定版本 Stage R 导出的 `candidate snapshot`。
- 现有 AgentDNSDemo 的 planner/标签抽取可以复用为“证据抽取器”的雏形，但不能作为最终的硬编码路由器。
- 若后续被质疑“为什么不用向量库”:
  - 口径: “向量是 Stage R 的一种可插拔召回实现；我们的核心贡献在候选集上的受约束决策、`primary + related` 区分、稳定性与可审计轨迹”
  - 指标: 增加 `PrimaryRecall@K / RelatedCoverage@K / UnionCoverage@K`

补充: v1 的“语义拆解”服务于 Stage R 和 Stage A/B，但第一跳的主任务不是“拍板决策”，而是把 query 映射成可检索的证据并构造高质量候选集:
- 1) 结构化证据抽取: `query + context -> evidence`
  - `primary_action`
  - `target_object`
  - `secondary_intents`
  - `risk_flags`
  - `industry_context`
  - `evidence_spans`
- 2) 命名空间节点召回（Namespace Recall）:
  - 先基于 evidence 对 `namespace descriptor` 做词法/元数据检索与打分，得到 3-8 个“强相关候选”
  - 再按“query 诱导的混淆规则”补入 5-15 个“混淆候选”，来源只能是 query 中真实存在的歧义、兄弟节点竞争、风险回落或节点描述重叠，不允许随机塞无关节点

边界澄清:
- Stage R 解决的是 `recall/coverage` 问题: 尽量把 `{ground_truth_fqdn} ∪ relevant_fqdns` 找进候选集。
- Stage A/B 解决的是 `selection` 问题: 在候选已经给定的情况下，判断哪个是 `primary`、哪些应保留为 `related`、何时需要升级到慢路径、如何在冲突中修正。
- 因此，Stage A/B 不是专门用来“补救 Stage R 拆不准”的。如果 `ground_truth_fqdn` 根本没进 candidates，那是 `stage_r_miss`，应单独归因，不能靠 Stage B 糊过去。

现实口径必须说清:
- 线上系统里不会“凭空长出一堆难题”。混淆候选来自 Stage R 对命名空间节点的真实检索结果:
  - query 自身多意图或表述不完整
  - 多个节点共享相近关键词/标签/描述
  - 粗粒度节点与细粒度节点并存
  - 治理/风险节点会因 `risk_flags` 被一并召回
- 因此，离线数据集里的混淆候选不能是随机构造的“题海战术”，而应当模拟“相同 query 经过 Stage R 检索后自然会一起出现的候选”。
- 如果需要证明更强鲁棒性，可以单独做 `adversarial negatives` 压测，但那应放附录/备份页，不与主表混在一起。

v1 输出的 `evidence/tags` 不是评测目标，但会写入 trace，作为“可解释/可审计”的一部分。

### 4.2 可选增强（不作为 v1 blocker）
- 若时间允许再做向量召回（Embedding + ANN），否则只在文档/PPT 里说明接口预留即可。

## 5. Stage A/B：快慢路径与共识方法（核心）
执行细化: 见 `closure/14_execution_spec_and_review_gate.md`
### 5.1 Stage A 输出格式（统一 JSON）
Stage A 必须输出结构化结果，避免“拍脑袋”:
```json
{
  "selected_primary_fqdn": "yunnan.itinerary.travel.cn",
  "selected_related_fqdns": ["weather.cn"],
  "routing_top_k": [
    {"fqdn": "yunnan.itinerary.travel.cn", "score": 0.74, "role": "primary"},
    {"fqdn": "weather.cn", "score": 0.71, "role": "related"},
    {"fqdn": "itinerary.travel.cn", "score": 0.60, "role": "fallback"}
  ],
  "confidence": 0.58,
  "constraint_check": {"pass": true, "reasons": []}
}
```

Stage A 的“L1/L2/L3 怎么选”:
- Stage A 不要求显式分三步输出 L1/L2/L3，而是在 Stage R 给定 `fqdn_candidates` 后，做“候选内受约束排序”直接输出 `primary + related` 路由。
- 为了可解释与可调参，Stage A 需要同时输出:
  - `routing_top_k[]` 的 score（归一化到 0-1）
  - `confidence`（v1 先围绕 primary 计算；另外 `margin=top1-top2` 用于触发判定）
  - `selected_related_fqdns`（来自次要意图、覆盖项或可接受回落项）

### 5.2 Stage A -> Stage B 触发函数（必须可解释）
定义触发规则（v1 先用规则阈值，便于答辩）:
- `low_confidence`: `confidence < tau`（默认 `tau=0.60`）
- `small_margin`: `(top1_score - top2_score) < delta`（默认 `delta=0.08`）
- `constraint_failed`: `constraint_check.pass == false`
- `high_risk`: `risk_level == high`（或候选中出现 `security.*` 并且 query 涉及合规/风险）
- `multi_intent_conflict`: primary/related 之间存在强竞争且次要诉求覆盖不足

说明:
- `tau/delta` 是可调超参（不是“拍脑袋定死”）。v1 在 `dev` 上做小范围网格搜索，把 `escalation_rate` 控制在目标区间（例如 15%-35%），并以质量指标为主优化；最终采用的阈值写进结项包与复现日志。

输出:
- `escalate_to_stage_b = any(reasons)`
- `escalation_reasons = ["low_confidence", "small_margin", ...]`

必须统计:
- `escalation_rate = (#触发StageB) / (#总样本)`

### 5.3 Stage B：异质智能体 + 反馈驱动共识（v1 机制）
目标: 明确落地任务书的三段式:
- 异质生成: 多角色提出候选与理由
- 共识演化: 多轮修正直至收敛
- 可信标识: 结构化 trace +（可选）hash-chain

#### 5.3.1 角色集合（v1 固定 4 个，避免膨胀）
- `DomainExpert`（领域专家）
- `GovernanceRisk`（治理/风险）
- `CostLatency`（成本/调用控制）
- `UserPreference`（用户偏好代理，规则/标签近似即可）

#### 5.3.2 共识循环（最多 2-3 轮）
说明: v1 不做开放式 debate（不可控、不可复现、难以日志化），采用“结构化多角色提案/投票 + 反馈函数 F(c) 打分”的混合流程。
Round 1:
- 各角色输出 `proposal_primary_fqdn + proposal_related_fqdns + rationale + confidence`
Round 2（如需）:
- 汇总分歧点，要求每个角色对 top2 进行对比与修正
收敛:
- 当 top1 分数超过阈值，或 top1-top2 margin 足够大，或达到轮次上限

#### 5.3.3 反馈打分函数 F（v1 用可解释线性组合）
对每个候选 `c` 计算:
```
F(c) = w_gt * S_task(c) + w_con * S_constraints(c) + w_pref * S_preference(c)
       - w_cost * S_cost(c) - w_risk * S_risk(c)
```
其中（v1 全部可由规则/结构化信息计算，避免引入新模型）:
- `S_task`: 与 query/need 的匹配度（可用角色投票数或 Stage A 分数归一化）
- `S_constraints`: 约束满足（不在候选=0，格式不合法=0）
- `S_preference`: 根据 context（预算/地点/时间/偏好）与 candidate 的适配打分（简化规则即可）
- `S_cost`: 轮次/调用惩罚（鼓励尽快收敛）
- `S_risk`: 风险域候选惩罚（security/gov 等）

默认权重（可在 v1 固定，后续只做敏感性分析）:
- `w_gt=0.35, w_con=0.25, w_pref=0.15, w_cost=0.10, w_risk=0.15`

> 注: 这不是 bandit/RL；这是“可解释反馈函数”，足以覆盖任务书“用户代理反馈与偏好驱动过程”的验收口径。

### 5.4 是否需要 utility bandit？
v1 不需要，原因:
- bandit 的价值在 “在线长期反馈优化排序”，结项期没有真实在线反馈闭环
- 引入 bandit 会带来额外状态、离线回放与稳定性问题（反而增加工作量和风险）

如何“借用你 IndProj 里 bandit 的说法”但不实现:
- 口径: “Stage C 的 agent selection 未来可用 contextual bandit 做曝光与质量的探索-利用平衡；v1 先用可解释的公平曝光/多样性规则，并报告 exposure 分布。”

## 6. Stage C：agent discovery 与排序（必须有，快、可缓存）
执行细化: 见 `closure/14_execution_spec_and_review_gate.md`
Stage C 是“落到真实地址”的最后一跳:
- 输入: `selected_primary_fqdn`
- 输出: `chosen_agent_fqdn` + `endpoint`（以及可审计的打分依据）

要求:
- 快: 纯结构化计算，不走 LLM（不会拖慢整体响应）
- 可审计: 输出 score breakdown（避免纯口头 reason）
- 公平曝光可控: 显式约束曝光分布（不引入 bandit/RL）

### 6.1 曝光正则化的打分函数（v1）
对 `routing_fqdn` 下每个候选 agent `a` 计算（分量都可由 Agent Card + 心跳状态直接得到）:
```
base(a) = w_match * S_match(a) + w_schema * S_schema(a) + w_tag * S_tag(a)

health(a) = I(status=online) * exp(- age_seconds / T_half)

fair(a) = 1 / sqrt(1 + exposure_agent(a))
provider_fair(a) = 1 / sqrt(1 + exposure_provider(provider(a)))

final(a) = base(a) * health(a) * fair(a) * provider_fair(a)
```
默认参数（v1 固定）:
- `w_match=0.55, w_schema=0.25, w_tag=0.20`
- `T_half=120`（心跳半衰期，单位秒）

输出（必须落 trace）:
- `top_k_agents[{agent_fqdn, endpoint, base, health, fair, provider_fair, final}]`
- `chosen_agent_fqdn`
- `reason` 以结构化分数为主（例如 `final=0.61=base0.82*health1.00*fair0.87*provider0.85`）

> 注: 这是 exposure-regularized scoring，不使用在线 reward，因此不属于 bandit/RL。

### 6.2 与 Agent Card 的关系（A2A 兼容口径）
- `agent_fqdn -> Agent Card JSON`（字段对齐即可）
- 评审问 “是不是A2A”：回答 “Agent Card 是 record payload；我们的核心是 namespace/routing_fqdn 的分层治理与路由决策+审计”

## 7. 指标与三张表（结项/论文最关键证据）
完整指标定义见 `closure/09_eval_protocol.md`，这里给出 v1 最小集合:

### 7.1 Table 1 主表（质量 + 约束）
方法行:
- Stage A-only
- Vote（多角色一轮投票）
- Ours Stage B（反馈共识）
- Ours A->B gating（快慢路径）

列:
- `PrimaryAcc@1` / `AcceptablePrimary@1`（可选）
- `RelevantRecall@K`
- `ConstraintPassRate`
- `Validity`

可选附表（推荐放附录或备份页，用于回答“层级太简略”）:
- Table 1b（l3 子集）: `FineAcc@1`、`Acc_L2@1`（可选）、`HierDistance_avg`（可选）

### 7.2 Table 2 消融（证明任务书每块有贡献）
行:
- Ours（完整）
- -heterogeneity（角色统一）
- -feedback（不计算 F，仅投票/仲裁）
- -trace（不影响质量，但用来对比审计字段完整率与开销）

列:
- `PrimaryAcc@1`
- `RelevantRecall@K`
- `ConstraintPassRate`
- `Tokens/Calls/Latency`（粗粒度即可）

### 7.3 Table 3 成本稳定性（回答“是不是堆调用”）
列:
- `escalation_rate`
- `Latency_p50/p95`
- `CallsPerSample` / `TokensPerSample`
- `DisagreementRate`（同 query 重复 N 次 top1 波动）

可选（Stage C 工程证据，推荐放附录/备份页）:
- `SelectionLatency_p50/p95`（下一跳发现耗时）
- `ProviderCoverage`（被选中的 provider 数 / 总 provider 数）
- `ProviderMaxShare`（单 provider 最大占比，越低越“公平曝光”）

## 8. Demo 设计（评审 3-5 分钟能看懂）
参见 `closure/10_demo_runbook.md`，本 doc 强调演示要点:
- Case 1: 快路径直接返回（证明不慢）
- Case 2: 低置信触发共识修正（证明共识价值）
- Case 3: 高风险强制慢路径 + 审计（证明可控可审计）

每个 case 必须展示:
- `routing_fqdn`（主输出）
- `escalation_reasons`
- 轨迹字段（agent_id/role/version/run_id）
- Stage C: `chosen_agent_fqdn -> endpoint` + score breakdown（`final/base/health/fair/provider_fair`）

## 9. 具体要改哪些代码（最小改动清单）
> 原则: 不大重构；只为“可演示 + 可出表 + 可审计”补齐接口与日志。

### 9.1 AgentDNSDemo（原型承载）
改动目标:
- 把“路由决策（routing_fqdn）”和“下一跳发现（agent_fqdn）”在接口/页面上显式区分
- 固化 Stage A/B 输出 JSON 与 trace 落盘
- 增加 Agent Card 导出（字段对齐 A2A）

最小改动点（v1）:
- backend:
  - 新增/补齐: `GET /.well-known/agent-card.json`（或 `GET /api/agents/{id}/card`）
  - 在 `client_assist` 链路中加入 Stage A/B gating 与 trace 记录
  - 输出 `run_id`，并支持导出 JSONL traces
  - Stage C 下一跳发现:
    - 产出 `top_k_agents`（含 `final/base/health/fair/provider_fair`）与 `chosen_agent_fqdn -> endpoint`
    - 把 score breakdown 写入 trace（用于“可审计 reason”）
- frontend:
  - 增加一块 trace viewer（哪怕是 JSON 折叠展示）
  - demo 时能看到 stage A confidence 与是否触发 stage B
  - demo 时能看到 Stage C 的 agent 排序列表与分数拆解（为什么选它）

### 9.2 IndProj04（结项包与实验出表）
改动目标:
- 在 `IndProj04` 目录内提供:
  - 数据集 JSONL + 标注指南
  - 一键评测脚本（生成 3 张表的 markdown/csv）
  - 一键打包脚本（导出代码快照，不带构建产物）

### 9.3 IndProj（可选）
由于你说 IndProj 未完成:
- v1 不把 IndProj 作为 blocker
- 若你希望复用 IndProj 的协议/基线能力，我们再做最小接入

## 10. 里程碑与验收（按 2026-04-30 倒排）
直接对齐 `closure/05_12week_plan.md`:
- M1 2026-03-11: namespace_v1 + 数据字段 + 触发规则冻结（本 doc 审查通过）
- M2 2026-03-25: demo 端到端可跑 + 录屏
- M3 2026-04-08: 三张表可生成（哪怕小规模）
- M4 2026-04-15: 专利定稿进入提交链路
- M5 2026-04-29: 结项包封版

## 11. 需要你拍板的 5 个点（审查 checklist）
1. namespace_v1 是否按现有 9 个领域冻结，不额外加 `food`？我觉得这个你可以来思考定夺，我agentdnsdemo这些东西定的很草率，你包括里面这些模拟agent的注册信息尤其是描述和能力标签，应都比较粗糙，场景设想也比较简单单一，而且3个层级可能还少了？
2. travel 是否允许 `l3=目的地` 作为 ground truth（并用 acceptable 收敛争议）？这个我感觉l3应该不是这么用的，而且你不用非得固定成是travel的场景。我觉得数据构造那一块可以多样一点？还是你觉得就是几个agent域名，在query构造上下功夫？
3. Stage B 角色集合是否固定 4 个（避免膨胀）？我觉得这个你也可以考虑，我觉得最少3个，但是得注意异质性得是服务于任务的，你别异质的风马牛不相及，以及你这里共识生成是vote还是debate还是混合成一个流程还是路由切换？
4. 触发阈值 `tau=0.60, delta=0.08` 是否接受（后续可在 dev 上调参）？这一块你怎么设想的？可能也得调参？
5. v1 是否明确“不实现 utility bandit”，只保留为未来工作口径？我觉得是。

## 12. 冻结结论（按你填写的意见落地到 v1 执行）
1. namespace:
- v1 先按现有 `namespace_v1` 的 9 个 L1 领域冻结（与半成品一致，避免改动引入新工作量）。
- 命名层级仍按 `l3.l2.l1.cn`（允许缺省）。如果后续确实需要更深层级或改语义，按 `ns_v2_*` 升版本而不是“原地改”。
- “模拟 agent 的注册信息/能力标签粗糙”不影响 v1 的主评测（routing_fqdn），但我们会把 Agent Card 的字段与描述写得更规整，作为可信标识/可审计口径的承载。

2. l3（segment）使用策略:
- v1 不把项目“固定成 travel 场景”。数据集覆盖多个 L1 领域；travel 只占其中一部分。
- `l3` 不是全局统一语义，而是按 `l2.l1` 子树冻结含义与 allowed set（见 `closure/07_namespace_v1.md`），v1 只对少量子树启用 `l3`，避免标注与复现失控。
- v1 启用的 `l3` 子树（冻结）:
  - travel: `hotel.travel.cn`、`itinerary.travel.cn`（`l3=destination`）
  - finance: `invoice.finance.cn`（`l3=subtask`，如 issue/verify/reimburse）
  - productivity: `meeting.productivity.cn`（`l3=task_type`，如 schedule/summary/action-items）
  - security: `compliance.security.cn`（`l3=object_type`，如 data/account/transaction）
- `l3` 只占少量样本（建议总体 15%-30%），且必须 query/context 有明确线索；同时提供 `acceptable_fqdns`（允许回落到 `l2.l1.cn`）来降低标签争议风险。

3. Stage B 角色与共识流程:
- v1 固定 4 角色（每个角色都对应反馈函数 `F(c)` 的一部分，保证异质性“服务于任务”而不是堆人头）。
- 共识不是开放 debate，而是“结构化提案/投票 + 反馈函数打分 +（可选）第二轮围绕 top2 修正”的混合流程；会提供 `-heterogeneity`（合并角色）等消融来证明贡献。

4. A->B 触发阈值:
- `tau/delta` 作为超参，先用默认值跑通端到端；再在 `dev` 上调参以控制 `escalation_rate`（目标区间例如 15%-35%）并提升主表指标，最终阈值写入复现日志。

5. bandit:
- v1 明确不实现 utility bandit；仅保留 Stage C “未来可用 contextual bandit 优化曝光/质量”的口径。

6. 数据集领域占比（按你最新要求冻结）:
- 工信相关场景占比 60%（企业/产业/监管语境，主要覆盖 `gov/security/finance/productivity`）。
- 其它场景占比 40%（travel/weather/commerce 等用于干扰与泛化）。

7. Stage C（下一跳发现）冻结要求:
- v1 必须落到 `agent_fqdn -> endpoint`，并输出可审计的 score breakdown（分数为主，替代长篇口头 reason）。
- 公平曝光采用 exposure-regularized scoring（见第 6 节），不引入 bandit/RL。
