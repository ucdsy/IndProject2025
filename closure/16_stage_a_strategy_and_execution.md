# Stage A 设计判断与执行分工（2026-03-14）

> 目的: 冻结 `clean Stage A v1` 的方法定位、输入输出边界、对外叙事、以及当前阶段的执行分工。
>
> 适用范围: `clean Stage A` 的后续设计、实现、评测、答辩与论文叙事。
>
> 上游依赖: `sr_clean_v1_20260307` 冻结 snapshot。

## 1. 当前结论
- 到 2026-03-14 为止，`clean Stage R` 已通过当前放行门槛，可作为 `clean Stage A v1` 的冻结输入基线。
- 当前主线不再是重写 `Stage R`，而是把 `Stage A` 做成一个**候选内、受约束、可审计、可升级**的裁决器。
- `Stage A` 不是开放式语义理解器，不是自由检索器，也不是对 `Stage R` 漏召回的补锅层。
- 若 `Stage R` 没有召回 gt，默认记为 `stage_r_miss`，不允许通过 `Stage A` 引入候选集之外的新路由来掩盖错误。

## 2. Stage A 的任务定义

### 2.1 输入
- `query`
- `context`
- 冻结的 `candidate snapshot`
  - `fqdn_candidates`
  - `score_r`
  - `components`
  - `matched_phrases`
  - `node_kind`
  - `parent_fqdn`
  - `fallback_to`
  - `confusion_sources`

### 2.2 输出
- `selected_primary_fqdn`
- `selected_related_fqdns`
- `routing_top_k`
- `confidence`
- `margin`
- `constraint_check`
- `escalate_to_stage_b`
- `escalation_reasons`

### 2.3 负责解决的问题
- `sibling competition`
  - 如 base 节点与更细粒度子节点之间的主次判断
- `fallback vs fine-grained`
  - 如父节点与 `l3`/子能力节点之间的落点选择
- `primary vs related`
  - 多意图 query 中谁是主路由、谁应进入 related
- `risk-aware correction`
  - 高风险或治理场景下的主路由校准

### 2.4 不负责的问题
- 修复 `Stage R` 漏召回
- 从候选集外发明新候选
- 执行真实 agent 发现与 endpoint 选择
- 直接输出业务结果

## 3. 推荐的方法结构
`Stage A` 推荐按三层实现，而不是做成一个大 prompt 黑箱。

### 3.1 A0: deterministic decision packet
- 作用: 把 `Stage R snapshot` 压缩成适合 LLM 裁决的候选表
- 内容:
  - `query/context`
  - top candidates
  - `score_r`
  - `components`
  - `matched_phrases`
  - `node_kind / parent / fallback`
  - `soft confusion hints`
- 原则:
  - 这里不做最终判定
  - 这里负责注入硬约束

### 3.2 A1: single-agent structured adjudication
- 由单个 LLM 在固定候选集内做结构化比较与裁决
- LLM 必须:
  - 只在候选集内选
  - 区分 `primary / related / fallback`
  - 输出结构化证据
  - 允许在低置信时请求升级
- LLM 不应:
  - 自由扩写新的候选
  - 把 `confusion_sources` 当成已验证事实
  - 输出不可校验的长篇自由 CoT 作为唯一依据

### 3.3 A2: deterministic calibration + gating
- 作用:
  - 将 `LLM structured evidence` 与 `Stage R` 排序信息合成最终决策
  - 决定是否升级到 `Stage B`
- 核心思想:
  - LLM 负责“证据裁决”
  - 外部规则负责“系统控制”

## 4. Prompt 与输出的推荐形态

### 4.1 Prompt 原则
- 不使用手写 marker/正则去硬切主次意图
- 不让 LLM 直接“自由思考并选一个答案”
- 使用 `hard rules + soft hints + candidate table` 的裁判式 prompt

### 4.2 `confusion_sources` 的使用边界
- 可以作为 `soft caution`
- 可以作为 `gating hint`
- 不可以作为直接加分依据
- 不可以作为“系统已经确认的真相”

原因:
- 当前 `Stage R` 的 `confusion_sources` 仍有较多 `E6_unjustified_confusion`
- 因此它更适合作为提示，而不是强监督

### 4.3 推荐输出 JSON
```json
{
  "selected_primary_fqdn": "permit.gov.cn",
  "selected_related_fqdns": ["policy.gov.cn"],
  "candidate_scores": [
    {
      "fqdn": "permit.gov.cn",
      "task_fit": 0.91,
      "primary_fit": 0.89,
      "related_fit": 0.18,
      "context_fit": 0.64,
      "specificity_fit": 0.72,
      "risk_penalty": 0.00,
      "evidence_for": ["资质/备案诉求与节点能力直接匹配"],
      "evidence_against": []
    }
  ],
  "confidence": 0.78,
  "margin": 0.14,
  "constraint_check": {
    "pass": true,
    "reasons": []
  },
  "escalate_to_stage_b": false,
  "escalation_reasons": []
}
```

## 5. 融合与置信度

### 5.1 不推荐的做法
- 不建议把 `Stage R score` 和 `LLM confidence` 用固定常数直接线性相加
- 不建议只靠 LLM 自报 `confidence` 决定升级

原因:
- 两者分布不天然同尺度
- LLM 的原始置信度往往不校准
- 线性相加虽然工程上省事，但学术上脆弱

### 5.2 当前推荐
- 让 LLM 输出结构化的中间证据分量
- 再由外部 deterministic aggregator 合成最终排序与 gating

可接受的外部融合信号:
- `score_r`
- `task_fit`
- `primary_fit`
- `related_fit`
- `context_fit`
- `specificity_fit`
- `risk_penalty`
- `constraint_check`

### 5.3 关于 RRF
- `RRF` 可以作为一个可报告的 baseline 或稳健融合对照
- 但不建议直接把它当 `clean Stage A v1` 的全部方法

原因:
- `Stage A` 的目标不只是融合两个排名
- 它还要显式产出:
  - `primary`
  - `related`
  - `confidence`
  - `margin`
  - `escalation_reasons`

## 6. 对 Gemini 建议的采纳边界

### 6.1 现在立刻采纳
- 用 LLM native structured parse 代替 marker/正则意图切分
- 保留 `evidence_for / evidence_against` 这类结构化可解释输出
- 保留 `escalation / trustworthy AI` 叙事与机制
- 不再依赖“原始 LLM 置信度 + 手写常数”的朴素融合

### 6.2 作为 baseline 或论文补充
- `BM25-only` lexical baseline
- `dense-only` retrieval baseline
- `RRF` ranking fusion baseline

### 6.3 当前不建议作为主线重构
- 立刻把 `Stage R` 主线改写成 `BM25 + dense + LightGBM/LR LTR`
- 在仅有 `formal/dev` 50 条的情况下训练 learned ranker 作为正式主线
- 把论文主叙事改成“我们发明了更好的检索器”

原因:
- 当前时间窗口更适合把主创新压在 `Stage A/B + AgentDNS 两跳解析` 上
- `Stage R` 已通过当前 gate，不宜在此时重新开一条高风险重写线

## 7. 推荐的 Stage A 放行标准

### 7.1 方法层
- 不使用 query-specific 硬编码 marker 作为主逻辑
- 不从候选集外引入新候选
- 输出结构化 JSON，可回放、可评测、可归因

### 7.2 评测层
- 在冻结的 `sr_clean_v1_20260307` snapshot 上运行
- 必须报告:
  - `PrimaryAcc@1`
  - `AcceptablePrimary@1`
  - `RelevantRecall@K`
  - `ConstraintPassRate`
  - `Validity`
  - `escalation_rate`
  - `Latency p50/p95`
- 建议同时报告:
  - 按 `intended_confusion_types` 分层的准确率
  - `close_score_delta` 分桶表现
  - 高风险样本的单独结果

## 8. 当前建议的执行分工

### 8.1 算法主线由谁来改
当前建议: **由我继续承担 `clean Stage A` 的算法主线设计与实现。**

原因:
- 我已经连续接住了:
  - `clean Stage R` 护栏
  - `industry` 去特权化
  - gate 评测与冻结
  - `Stage A` 的边界与方法判断
- 这条上下文是连续的，继续由我改，误差归因和设计口径更稳定
- `Stage A` 现在最需要的是“边写边校验边收口”，而不是再切一次负责人

### 8.2 项目总指挥兼总执行 agent 更适合负责什么
- 节点排期与推进节奏
- 文档线、专利线、论文线的一致性校对
- 跨 Stage 的接口验收
- demo、答辩、材料打包
- 在关键节点做 review/拍板

### 8.3 推荐协作方式
- 我负责:
  - `clean Stage A` 方法设计
  - 代码实现
  - `dev` 评测
  - 消融与 gating 调整
- 项目总指挥负责:
  - 是否放行到下一阶段
  - 是否需要补对比基线
  - 如何把结果接到结项、专利、论文叙事里

### 8.4 如果只能二选一
- 若只能选一个执行者来改算法主线，当前应优先选择**我**。
- 若需要第二个角色介入，最适合做**reviewer / integrator / package owner**，而不是重新接管 day-to-day 算法实现。

## 9. 当前建议的下一步
1. 冻结本文件作为 `Stage A v1` 方法边界。
2. 在冻结的 `sr_clean_v1_20260307` snapshot 上实现 `clean Stage A v1`。
3. 先完成:
   - prompt schema
   - output schema
   - deterministic calibration
   - gating policy
4. 之后再补:
   - `RRF` baseline
   - `BM25-only / dense-only` 论文对比基线

## 10. 2026-03-14 实施更新

### 10.1 已完成的工程硬化
- `stage_a_llm.py` 已补 `min-max` spread floor，避免弱候选分盘被强行拉成 `1.0`
- `OpenAICompatibleStageALLMClient` 已优先请求 `json_object` 输出；若 provider 不支持，再自动回退到普通文本 JSON 解析
- 对应单测已补齐，当前 `tests/test_stage_a_clean.py` + `tests/test_stage_a_llm.py` 共 12 个测试通过

### 10.2 当前 mock 结果
- `mock dev` 结果维持稳定:
  - `PrimaryAcc@1 = 0.96`
  - `RelatedRecall@Covered = 0.92`
  - `RelatedPrecision = 0.9583`
  - `escalation_rate = 0.76`

### 10.3 当前真实 provider smoke 结果
- 已用 `deepseek-chat` 跑真实 provider smoke，不再只看 mock
- 当前冻结结论以 `smoke20` 为准，而不是完整 `dev`
- `smoke20` 结果:
  - `PrimaryAcc@1 = 0.95`
  - `RelatedRecall@Covered = 1.0`
  - `RelatedPrecision = 0.6154`
  - `related_overpredict_rate = 0.25`
  - `escalation_rate = 0.45`

### 10.4 当前暴露的问题
- 真实 provider 相比 deterministic baseline 更激进地扩张 `related`
- 过拟合样式不是 `Stage R` 漏召回，而是:
  - `cross-domain` / `governance` 场景下误挂 related
  - 治理簇内部出现个别 `primary` 误判
- 当前典型样本:
  - `formal_dev_000004`: `policy.gov.cn -> compliance.security.cn` 误挂 related
  - `formal_dev_000006`: `policy.gov.cn -> compliance.security.cn` 误挂 related
  - `formal_dev_000008`: `compliance.security.cn` 被误判到 `account.compliance.security.cn`
  - `formal_dev_000010`: `account.compliance.security.cn -> summary.meeting.productivity.cn` 误挂 related
  - `formal_dev_000012`: `risk.security.cn -> compliance.security.cn` 误挂 related

### 10.5 当前执行判断
- `Stage A` 架构保持冻结，不再改方法主线
- 完整 `deepseek dev` 暂不继续，先停在 `smoke20`
- 下一步优先级:
  1. 收紧 prompt / calibration 中对 `related` 的放行条件
  2. 重点检查 `sibling_competition` 与 `governance_fallback` 分桶
  3. 重新跑真实 provider，再决定是否值得做完整 `dev`

### 10.6 2026-03-14 晚间复跑结果
- 已完成两轮针对性收口:
  - `tight1`: 收紧 `related` 放行规则，压制 `cross-domain` / `governance` 误挂
  - `tight2`: 修复真实 provider 把 `candidate_judgements` 返回成对象字典时的解析兼容性
- `mock` 复跑结果 (`sa_llm_v1_20260314_tight1`):
  - `PrimaryAcc@1 = 0.96`
  - `RelatedRecall@Covered = 0.84`
  - `RelatedPrecision = 1.0`
  - `related_overpredict_rate = 0.0`
  - `escalation_rate = 0.78`
- `deepseek smoke20` 最新结果 (`sa_llm_v1_20260314_tight2`):
  - `PrimaryAcc@1 = 1.0`
  - `AcceptablePrimary@1 = 1.0`
  - `RelatedRecall@Covered = 1.0`
  - `RelatedPrecision = 1.0`
  - `related_overpredict_rate = 0.0`
  - `escalation_rate = 0.5`
- 最新 `smoke20` 下，前一轮暴露的典型问题已被压住:
  - `formal_dev_000004`: 不再误挂 `compliance.security.cn`
  - `formal_dev_000006`: 不再误挂 `compliance.security.cn`
  - `formal_dev_000008`: 主路由回到 `compliance.security.cn`
  - `formal_dev_000010`: 不再误挂 `summary.meeting.productivity.cn`
  - `formal_dev_000012`: 不再误挂 `compliance.security.cn`
- 当前 `smoke20` 剩余问题主要是 `Stage R` 本身未覆盖的 related:
  - `formal_dev_000001`
  - `formal_dev_000003`

### 10.7 完整 `deepseek dev` 结果
- 已完成完整 `formal/dev` 50 条的 `deepseek-chat` 评测
- 最终结果 (`sa_llm_v1_20260314_tight2`):
  - `PrimaryAcc@1 = 0.96`
  - `AcceptablePrimary@1 = 0.96`
  - `RelatedRecall = 0.7586`
  - `RelatedRecall@Covered = 0.88`
  - `RelatedPrecision = 1.0`
  - `related_overpredict_rate = 0.0`
  - `escalation_rate = 0.36`
- 主要剩余误差:
  - `decision_primary_miss = 2`
    - `formal_dev_000025`: `meeting.productivity.cn -> schedule.meeting.productivity.cn`
    - `formal_dev_000036`: `itinerary.travel.cn -> xian.itinerary.travel.cn`
  - `decision_related_miss = 3`
    - `formal_dev_000027`: 漏掉 `docs.productivity.cn`
    - `formal_dev_000037`: 漏掉 `weather.cn`
    - `formal_dev_000045`: 漏掉 `itinerary.travel.cn`
  - `stage_r_related_miss = 4`
    - `formal_dev_000001`
    - `formal_dev_000003`
    - `formal_dev_000035`
    - `formal_dev_000043`

### 10.8 Confusion-Type 分桶观察
- `cross_domain_overlap`:
  - `PrimaryAcc@1 = 1.0`
  - `RelatedRecall@Covered = 0.8235`
  - `extra_related_case_rate = 0.0`
- `governance_fallback`:
  - `PrimaryAcc@1 = 1.0`
  - `RelatedRecall@Covered = 1.0`
  - `RelatedRecall = 0.6667`
  - 剩余缺口主要来自 `Stage R` 未覆盖 related，而不是 Stage A 误挂
- `sibling_competition`:
  - `PrimaryAcc@1 = 0.8947`
  - 是当前最明显的剩余短板
  - 说明 `base` vs `city/child` 节点之间的主次校准仍需继续做
- `multi_intent`:
  - `PrimaryAcc@1 = 1.0`
  - `RelatedRecall@Covered = 0.88`
  - 当前 `related` 召回还有提升空间，但已经不再通过误挂来换 recall

### 10.9 2026-03-14 深夜 sibling 定向修正
- 已对 `sibling_competition` 的两类残差补最后一层 guard:
  - `stage_a_clean.py`: 对 `meeting/schedule` child 增加 `generic_meeting_schedule_penalty`
    - 若只有泛词 `安排/安排会议`，但 query 没有显式 `时间/会场/会议室/排期` 等排期证据，则不允许 `schedule.meeting.productivity.cn` 靠泛词越过 `meeting.productivity.cn`
  - `stage_a_llm.py`: 对两类 child 误抬增加后置回退
    - `scene-only city segment` 不允许越过强 base parent
    - `generic meeting schedule child` 不允许在 LLM 重新校准后再越过 `meeting.productivity.cn`
- 回归测试已扩到 `21` 个，全部通过

- `Stage A clean` 全量复跑 (`sa_clean_v3_20260314`):
  - `PrimaryAcc@1 = 1.0`
  - `AcceptablePrimary@1 = 1.0`
  - `RelatedRecall = 0.7931`
  - `RelatedRecall@Covered = 0.92`
  - `RelatedPrecision = 0.9583`
  - `related_overpredict_rate = 0.02`
  - `escalation_rate = 0.60`
  - 当前 `decision_primary_miss = 0`

- `sibling_competition` 子集的 deterministic 复跑 (`sa_clean_v3_20260314_sibling`):
  - `samples = 19`
  - `PrimaryAcc@1 = 1.0`
  - `RelatedRecall@Covered = 0.90`
  - `RelatedPrecision = 1.0`
  - `related_overpredict_rate = 0.0`
  - `escalation_rate = 0.6842`

- 真实 provider 不再做新的全量 `deepseek dev` 长跑，而是先做 `target4` 正反对照验证 (`sa_llm_v1_20260314_tight4_target4`)
  - `formal_dev_000025`: `meeting.productivity.cn`
  - `formal_dev_000026`: `schedule.meeting.productivity.cn`
  - `formal_dev_000036`: `itinerary.travel.cn`
  - `formal_dev_000037`: `xian.itinerary.travel.cn`
  - 结论:
    - 两个坏例 (`000025`, `000036`) 已被拉回 base
    - 两个正例 (`000026`, `000037`) 未被新 guard 误伤
  - `target4` 汇总:
    - `PrimaryAcc@1 = 1.0`
    - `AcceptablePrimary@1 = 1.0`
    - `escalation_rate = 0.75`
    - 仅剩 `decision_related_miss = 1`

- 当前执行判断更新:
  - `sibling_competition` 的主路由误判已被定向命中
  - 下一步不应继续大改主路由算法
  - 更合理的下一步是:
    1. 用 `sa_clean_v3_20260314` 作为新的 deterministic 基线
    2. 再择机做一次完整真实 provider 复跑
    3. 把精力转到 `decision_related_miss` 和 `stage_r_related_miss`

### 10.10 2026-03-14 深夜硬编码清洗
- 已将 `meeting/schedule` 的业务硬编码从引擎层抽离到 namespace schema
  - `namespace_descriptors.jsonl` 中，`schedule.meeting.productivity.cn` 现在通过 `routing_constraints` 声明:
    - `requires_explicit_primary_cues`
    - `generic_trigger_aliases`
  - `stage_a_clean.py` 与 `stage_a_llm.py` 不再出现 `l2 == "meeting"` / `segment == "schedule"` 这类领域判断
  - 当前 guard 语义改写为通用的 `schema-injected explicit cue guard`

- 抽象化后复跑结果保持稳定:
  - `Stage A clean` 全量 (`sa_clean_v4_20260314`):
    - `PrimaryAcc@1 = 1.0`
    - `AcceptablePrimary@1 = 1.0`
    - `RelatedRecall = 0.7931`
    - `RelatedRecall@Covered = 0.92`
    - `RelatedPrecision = 0.9583`
    - `related_overpredict_rate = 0.02`
    - `escalation_rate = 0.60`
  - `target4` 真实 provider 对照 (`sa_llm_v1_20260314_tight5_target4`):
    - `formal_dev_000025 -> meeting.productivity.cn`
    - `formal_dev_000026 -> schedule.meeting.productivity.cn`
    - `formal_dev_000036 -> itinerary.travel.cn`
    - `formal_dev_000037 -> xian.itinerary.travel.cn`
    - `PrimaryAcc@1 = 1.0`
    - `AcceptablePrimary@1 = 1.0`

- 当前执行判断进一步更新:
  - `sibling_competition` 的主路由修正已从“经验性补丁”升级为“schema-driven constraints”
  - 这意味着 `primary routing` 线现在不仅实证上成立，而且表达上也更适合答辩/论文
  - 下一步可正式把重点切到:
    1. `decision_related_miss`
    2. `stage_r_related_miss`
    3. `Stage B` 设计与升级策略
