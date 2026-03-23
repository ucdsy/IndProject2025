# Stage A Blind Error Analysis（2026-03-17）

> 目的: 对 `Stage A v1` 在 blind holdout 上暴露的非 `OK` 样本做正式误差分析，作为论文、答辩与 `Stage B` 立项的统一依据。
>
> 适用范围: `Stage A` blind 结果解释、Error Analysis 章节撰写、`Stage B` 样本池与动机设计。
>
> 冻结对象:
> - `sr_clean_v2_20260314_related2`
> - `sa_clean_v8_20260314_riskschema_on_sr_v2`
>
> 注:
> - 本文解释的是 2026-03-15 那轮 `Stage A clean` blind 揭盲结果。
> - 当前 repo 后续已经新增:
>   - `holdout2` fresh split
>   - `sa_llm_v2_20260323_uncertainty`
>   - `stage_b_v1_20260323_packetv2`
> - 因此，本文仍然是 `Stage A clean` 误差边界的重要依据，但已经不是理解当前项目总状态的唯一入口；最新进展请结合 `closure/20_stage_b_bootstrap_plan.md`、`closure/24_stage_a_uncertainty_and_stage_b_packet_v2_design.md` 与 `research-project/04_execution-log.md` 阅读。

## 1. Blind 总结
- blind 样本数: `35`
- `Stage R clean`:
  - `PrimaryRecall@10 = 0.9714`
  - `RelatedCoverage@10 = 1.0`
- `Stage A clean`:
  - `PrimaryAcc@1 = 0.8286`
  - `AcceptablePrimary@1 = 0.8571`
  - `RelatedRecall = 0.8333`
  - `RelatedPrecision = 0.9091`
  - `escalation_rate = 0.4857`
  - `error_buckets = {"OK": 30, "decision_primary_miss": 4, "stage_r_primary_miss": 1}`

结论:
- blind 结果明确打破了 `formal/dev` 上的 `1.0` 闭环口径。
- 但错误并非无规律散落，而是集中暴露在:
  - 隐式主意图理解
  - `primary` / `secondary` 解耦
  - 同子树 tight competition
  - 上游 `Stage R` 召回盲点

## 2. 误差分桶

### 2.1 `ontology / descriptor blind spot`
- 表现:
  - query 中存在可被人类稳定识别的主意图
  - 但当前 schema/descriptor 没有给出足够显式的承接线索
  - 最终系统被更表层的 alias 或更熟悉的节点吸走
- 对应样本:
  - `formal_blind_000019`
  - `formal_blind_000031`

### 2.2 `primary-secondary disentanglement`
- 表现:
  - query 的 primary 与 supplemental 在结构上已经可拆
  - 但系统仍把强显式关键词误判成 primary
  - 属于 `Stage A` 裁决能力上限，而不是候选集外失控
- 对应样本:
  - `formal_blind_000021`

### 2.3 `sibling tie`
- 表现:
  - 候选集中同一业务树下两个节点都“有理”
  - `Stage A` 可以识别不确定，但无法稳定做最终主次裁断
- 对应样本:
  - `formal_blind_000024`

### 2.4 `stage_r recall miss`
- 表现:
  - gt 根本没有进入 `Stage R` 候选集
  - `Stage A` 不能且不应补锅
- 对应样本:
  - `formal_blind_000026`

## 3. 五个非 `OK` 样本

| sample_id | gt | pred | bucket | 备注 |
| --- | --- | --- | --- | --- |
| `formal_blind_000019` | `summary.meeting.productivity.cn` | `docs.productivity.cn` | `ontology / descriptor blind spot` | 会后总结被“材料提纲/会议材料”吸走 |
| `formal_blind_000021` | `docs.productivity.cn` | `risk.security.cn` | `primary-secondary disentanglement` | 文档主任务被“风险”词拉偏 |
| `formal_blind_000024` | `xian.itinerary.travel.cn` | `xian.hotel.travel.cn` | `sibling tie` | 同城 `hotel` / `itinerary` 打平 |
| `formal_blind_000026` | `flight.travel.cn` | `hotel.travel.cn` | `stage_r recall miss` | `flight` 未进候选 |
| `formal_blind_000031` | `nutrition.health.cn` | `restaurant.travel.cn` | `ontology / descriptor blind spot` | “饮食调节”被吸到“吃饭/餐厅” |

## 4. 逐样本分析

### 4.1 `formal_blind_000019`
- query:
  - `“给企业客户准备项目例会”准备落地。先把会后重点梳理出来。另外，再补会议材料提纲。`
- gt / pred:
  - gt = `summary.meeting.productivity.cn`
  - pred = `docs.productivity.cn`
- 关键证据:
  - `Stage R top1 = docs.productivity.cn (1.16725)`
  - `Stage R top2 = meeting.productivity.cn (0.496202)`
  - `summary.meeting.productivity.cn` 仅以 segment node 形式进入，`score_r = 0.0`
  - `Stage A related = ["meeting.productivity.cn"]`
  - `escalation_reasons = ["low_confidence"]`
- root cause:
  - 当前 ontology 对“会后重点梳理出来”没有形成足够强的 `summary` 主意图支持
  - 相比之下，“会议材料/提纲”在 `docs.productivity.cn` 上是显式 alias，因此更容易被 Stage R/Stage A 放大
- 结论:
  - 这不是开放式幻觉，而是 `summary` 这类隐式会议后处理语义在当前 schema 下表达不足

### 4.2 `formal_blind_000021`
- query:
  - `围绕“工业软件实施说明”，先做前置梳理。先处理这一步：把材料结构和重点梳理一遍。另外，再补三条主要风险。`
- gt / pred:
  - gt = `docs.productivity.cn`
  - pred = `risk.security.cn`
- 关键证据:
  - `query_packet.primary_request_text = "先处理这一步：把材料结构和重点梳理一遍"`
  - supplemental = `["另外，再补三条主要风险"]`
  - `Stage R top1 = risk.security.cn (0.3055)`
  - `Stage R top2 = docs.productivity.cn (0.119)`
  - `Stage A score_a`:
    - `risk.security.cn = 0.435500`
    - `docs.productivity.cn = 0.435310`
  - `escalation_reasons = ["high_risk", "low_confidence", "multi_intent_conflict", "small_margin"]`
- root cause:
  - 主因不是 gating 把正确 primary 挡掉
  - 主因是 `Stage A` 自身在 primary/secondary 解耦上失手:
    - 文档结构整理应是 primary
    - 风险补充应是 secondary
    - 但当前系统对显式 `风险` 词和高风险域给了过高主路由牵引
- 结论:
  - 这是最典型的 `primary-secondary disentanglement` 难例

### 4.3 `formal_blind_000024`
- query:
  - `这一步先落到“去西安待四天”上。先处理这一步：理一遍西安这趟怎么走。另外，再补几个可去的活动点。`
- gt / pred:
  - gt = `xian.itinerary.travel.cn`
  - pred = `xian.hotel.travel.cn`
- 关键证据:
  - `Stage R`:
    - `activity.travel.cn = 0.1885`
    - `xian.hotel.travel.cn = 0.172675`
    - `xian.itinerary.travel.cn = 0.172675`
  - `Stage A score_a`:
    - `xian.hotel.travel.cn = 0.825782`
    - `xian.itinerary.travel.cn = 0.825782`
  - `related` 恢复了 `activity.travel.cn`
  - `escalation_reasons = ["close_score_delta", "low_confidence", "small_margin"]`
- root cause:
  - 这是标准 `sibling tie`
  - 系统知道这是 travel 场景，也知道活动点是次意图
  - 但对同城 `hotel` 与 `itinerary` 缺乏稳定的最终主次裁断能力
- 结论:
  - 属于单裁决器在 tight sibling competition 下的已知上限

### 4.4 `formal_blind_000026`
- query:
  - `接下来要推进“去成都看比赛”。优先看什么时间和班次更顺。`
- gt / pred:
  - gt = `flight.travel.cn`
  - pred = `hotel.travel.cn`
- 关键证据:
  - `Stage R` 候选中没有 `flight.travel.cn`
  - `Stage R top candidates` 集中在:
    - `chengdu.hotel.travel.cn`
    - `chengdu.itinerary.travel.cn`
    - `hotel.travel.cn`
    - `itinerary.travel.cn`
  - `Stage A` 只能在这些候选内做选择
- root cause:
  - 纯上游 `Stage R recall miss`
- 结论:
  - 必须与 `decision_primary_miss` 分桶报告，不能归到 `Stage A` 理解失败

### 4.5 `formal_blind_000031`
- query:
  - `“想把饮食先调得清淡一点”准备落地。先把吃饭这件事调一调。`
- gt / pred:
  - gt = `nutrition.health.cn`
  - pred = `restaurant.travel.cn`
- 关键证据:
  - `Stage R top1/top2`:
    - `nutrition.health.cn = 0.1885`
    - `restaurant.travel.cn = 0.1885`
  - `Stage A score_a`:
    - `restaurant.travel.cn = 0.668823`
    - `nutrition.health.cn = 0.547944`
  - `escalation_reasons = ["close_score_delta", "low_confidence", "multi_intent_conflict"]`
- root cause:
  - 当前 schema 中，“吃饭”更容易被解释为餐厅/消费行为，而不是饮食管理
  - 在人类看来这更接近营养/饮食调整，但系统缺乏稳定把“吃饭这件事调一调”映射到 `nutrition` 的语义护栏
- 结论:
  - 这是典型跨域语义边界盲区

## 5. 最适合写入论文的典型样本

### 5.1 `formal_blind_000021`
- 代表问题:
  - 单裁决器在 `primary` / `secondary` 解耦上的极限
- 为什么适合写:
  - query 结构清楚
  - top1/top2 分数极近
  - 能明确说明不是召回 miss，而是裁决失手

### 5.2 `formal_blind_000031`
- 代表问题:
  - 跨域语义边界的隐式歧义
- 为什么适合写:
  - 人类直觉与系统落点存在清晰对照
  - 很适合说明 `Stage A` 在长尾语义上的理解上限

## 6. 对 Stage B 的直接启示
- 这 5 个非 `OK` 样本全部触发了 `escalate_to_stage_b = true`
- 因此，当前最重要的不是继续把 `Stage A` 硬修成 100%，而是承认:
  - `Stage A` 已经是一个有效的受约束裁决器
  - 同时它也是一个有效的不确定性探测器
  - 但它还不是处理长尾跨域与 tight sibling 歧义的充分求解器

对 `Stage B` 的要求应收敛为:
- 只消费 `Stage A trace + fqdn_candidates`
- 重点处理:
  - 隐式主意图
  - primary/secondary 解耦
  - sibling tie
  - 高风险低 margin 冲突样本

## 7. 当前建议
- 冻结这份 blind 误差分析，作为 `Stage A v1` 的正式误差边界
- 不再继续改 `Stage A v1` 代码去追这 4 个 blind miss
- 把后续工程主线切到 `Stage B` 的最小可运行版本
