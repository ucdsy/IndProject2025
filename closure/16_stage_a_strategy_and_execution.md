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
- 这一节记录的是**当时的临时补丁阶段**，不是当前 live code 的最终表达。
- 当时为压制 `sibling_competition` 的残差，先补了两类定向 guard:
  - `stage_a_clean.py`: 针对 `meeting/schedule` child 的临时惩罚项
    - 若只有泛词 `安排/安排会议`，但 query 没有显式 `时间/会场/会议室/排期` 等排期证据，则不允许 `schedule.meeting.productivity.cn` 靠泛词越过 `meeting.productivity.cn`
  - `stage_a_llm.py`: 对两类 child 误抬增加后置回退
    - `scene-only city segment` 不允许越过强 base parent
    - `generic meeting schedule child` 不允许在 LLM 重新校准后再越过 `meeting.productivity.cn`
- 后续在 `10.10` 中，上述 `meeting/schedule` 临时补丁已经改写为 schema-driven 的 `explicit cue guard`；因此这里的参数名和函数口径应视为**历史痕迹**，不代表当前源码仍保留同名实现。
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

### 10.10 2026-03-14 深夜 sibling 线硬编码清洗
- 已将 `meeting/schedule` 这条 `sibling` 校准相关的业务硬编码从引擎层抽离到 namespace schema
  - `namespace_descriptors.jsonl` 中，`schedule.meeting.productivity.cn` 现在通过 `routing_constraints` 声明:
    - `requires_explicit_primary_cues`
    - `generic_trigger_aliases`
  - `stage_a_clean.py` 与 `stage_a_llm.py` 不再出现 `l2 == "meeting"` / `segment == "schedule"` 这类领域判断
  - 当前 guard 语义改写为通用的 `schema-injected explicit cue guard`
- 这里的“硬编码清洗”**只覆盖 `meeting/schedule` 这条 sibling 线**，不应被解读为 `Stage A` 全部业务约束都已完成 schema 化。

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
  - 这意味着 `sibling` 相关的 `primary routing` 修正不仅实证上成立，而且表达上也更适合答辩/论文
  - 下一步可正式把重点切到:
    1. `decision_related_miss`
    2. `stage_r_related_miss`
    3. `Stage B` 设计与升级策略

### 10.11 2026-03-14 深夜 related 治理收口
- 已围绕 `decision_related_miss` 做两轮 related 侧修正，保持 `primary routing` 不动:
  - `docs.productivity.cn`
    - 补充 `提纲 / 材料提纲 / 会议材料` descriptor 支持
  - `fitness.health.cn`
    - 补充 `运动 / 运动建议 / 训练建议` alias，避免 `运动建议` 只被弱 desc overlap 召回
  - `stage_a_llm.py`
    - 新增 `same-l1 deterministic secondary anchor`
    - 允许同 `l1`、有 `secondary_hits`、且 deterministic related 分数足够的候选，在 LLM 未显式选中时仍可进入 related
  - `stage_a_clean.py`
    - 对 `RISK_L1` related 增加显式二级意图要求，不再让结构化多意图单独放行

- 对应回归测试已扩到 `27` 个，全部通过

- `Stage A clean` 全量复跑 (`sa_clean_v6_20260314_related2`):
  - `PrimaryAcc@1 = 1.0`
  - `AcceptablePrimary@1 = 1.0`
  - `RelatedRecall = 0.8621`
  - `RelatedRecall@Covered = 1.0`
  - `RelatedPrecision = 1.0`
  - `related_overpredict_rate = 0.0`
  - `escalation_rate = 0.60`
  - 当前只剩 `stage_r_related_miss = 4`

- `Stage A llm mock` 全量复跑 (`sa_llm_v1_20260314_tight7_related2`):
  - `PrimaryAcc@1 = 0.98`
  - `AcceptablePrimary@1 = 0.98`
  - `RelatedRecall = 0.8621`
  - `RelatedRecall@Covered = 1.0`
  - `RelatedPrecision = 1.0`
  - `related_overpredict_rate = 0.0`
  - `escalation_rate = 0.74`
  - 当前只剩:
    - `decision_primary_miss = 1` (`formal_dev_000036`)
    - `stage_r_related_miss = 4`

- 专项治理表已单开:
  - `closure/17_related_miss_governance.md`

### 10.12 当前 real-provider 复核进度
- 已完成 `deepseek-chat` 的 related target 子集复跑 (`sa_llm_v1_20260314_tight7_related_target5`)
- `target5` 汇总:
  - `samples = 5`
  - `PrimaryAcc@1 = 1.0`
  - `AcceptablePrimary@1 = 1.0`
  - `RelatedRecall = 1.0`
  - `RelatedRecall@Covered = 1.0`
  - `RelatedPrecision = 1.0`
  - `related_overpredict_rate = 0.0`
  - `escalation_rate = 0.4`
  - `error_buckets = {"OK": 5}`
- 已确认恢复的样本:
  - `formal_dev_000009`
    - `selected_related_fqdns = ["risk.security.cn"]`
    - 不再误挂 `fraud.security.cn`
  - `formal_dev_000027`
    - `selected_related_fqdns = ["docs.productivity.cn"]`
  - `formal_dev_000037`
    - `selected_related_fqdns = ["weather.cn"]`
  - `formal_dev_000045`
    - `selected_primary_fqdn = "weather.cn"`
    - `selected_related_fqdns = ["itinerary.travel.cn"]`
  - `formal_dev_000046`
    - `selected_primary_fqdn = "nutrition.health.cn"`
    - `selected_related_fqdns = ["fitness.health.cn"]`
- 另有 `target1` one-shot (`sa_llm_v1_20260314_tight7_related_target1`) 再次确认:
  - `formal_dev_000046` 单样本结果为 `OK`
  - `escalation_rate = 0.0`

- 当前执行判断再次更新:
  - 冻结 snapshot 上，`Stage A clean` 的 related 决策面已基本收口
  - 后续主要误差来源已收敛到 `Stage R` 未覆盖 related
  - 下一步主线应转为:
    1. 完成剩余 real-provider 复核
    2. 单开 `sr_clean_v2_related1`
    3. 只处理 `stage_r_related_miss` 的 4 个样本

### 10.13 2026-03-14 深夜 `Stage R v2` 低风险补召回
- 已在不改 `Stage R` 主逻辑的前提下，只通过 schema/descriptor 补充完成 `stage_r_related_miss` 审计与修正
- 本轮补充:
  - `policy.gov.cn`
    - 增加 `依据`
  - `price.commerce.cn`
    - 增加 `差价`
  - `hotel.travel.cn`
    - 增加 `住处`
- 为避免新召回候选污染 `Stage A`：
  - `docs.productivity.cn`
    - 从 alias 中移除过宽的裸 `提纲`
  - `Stage A clean`
    - 增加通用的 `multi_intent_secondary_primary_penalty`
    - secondary-only 候选可做 related，但不应轻易翻成 primary

- 新 snapshot (`sr_clean_v2_20260314_related2`) gate 结果:
  - `PrimaryRecall@10 = 1.0`
  - `RelatedCoverage@10 = 1.0`
  - `UnionCoverage@10 = 1.0`
  - `L1Acc_top1cand = 0.96`
  - `L2Acc_top1cand = 0.8333`
  - gate 继续通过，`advance_recommendation = "advance_to_stage_a"`

- 新 snapshot 接 `Stage A clean` (`sa_clean_v7_20260314_related3_on_sr_v2`)：
  - `PrimaryAcc@1 = 1.0`
  - `AcceptablePrimary@1 = 1.0`
  - `RelatedRecall = 1.0`
  - `RelatedRecall@Covered = 1.0`
  - `RelatedPrecision = 1.0`
  - `related_overpredict_rate = 0.0`
  - `escalation_rate = 0.54`
  - `error_buckets = {"OK": 50}`

- `mock` 双轨对照 (`sa_llm_v1_20260314_tight8_related3_on_sr_v2`)：
  - `PrimaryAcc@1 = 0.98`
  - `RelatedRecall = 1.0`
  - `RelatedPrecision = 1.0`
  - `related_overpredict_rate = 0.0`
  - 当前仅剩 `decision_primary_miss = 1`

- 当前执行判断最终更新:
  - `formal/dev` 上，clean 主线已完成 end-to-end 闭环
  - 当前最值得补的不是继续调 deterministic clean，而是：
    1. 选择是否对 `sr_clean_v2_related2 + Stage A clean v7` 做一轮真实 provider 全量复核
    2. 进入 `Stage B` 设计与升级样本池整理

### 10.14 2026-03-14 执行日志勘误与口径清理
- 本文件是按时间顺序追加的执行日志，因此会保留阶段性补丁、旧参数名和当时的判断；其中一部分已不再代表当前 live code。
- 需要明确区分两类内容:
  - 已完成 schema 化的部分:
    - `meeting/schedule` 的 `sibling` 主路由修正
    - 当前 live code 通过 `routing_constraints` + 通用 `explicit cue guard` 实现
  - 尚未完成 schema 化的部分:
    - 高风险治理场景的 `risk-aware gating`
    - 截至本节记录时，live code 仍使用 engine-side 的 `RISK_L1 = {"gov", "security"}` 作为高风险簇判定
- 因此，`10.10` 中“硬编码清洗”的表述应理解为:
  - **仅 sibling 线完成了 schema-driven constraints**
  - **不代表 `Stage A` 全部业务约束都已去硬编码**
- 对当前代码最准确的状态描述应为:
  - `sibling` 相关的领域约束已完成从引擎硬编码到 schema 注入的迁移
  - `high-risk` 相关约束仍有一部分停留在引擎侧，后续还需继续清理

### 10.15 2026-03-14 深夜 `RISK_L1` 代码清理
- 已将 `Stage A` 中残留的 `RISK_L1 = {"gov", "security"}` 从引擎侧删除，改为读取 namespace schema 中的显式约束位:
  - `namespace_descriptors.jsonl` 中，相关 `gov/security` 节点现在声明 `routing_constraints.stage_a_high_risk = true`
  - `namespace.py` 新增 `RoutingNode.is_stage_a_high_risk`
  - segment 节点现在会继承 base descriptor 的 `routing_constraints`，因此如 `account.compliance.security.cn` 这类子节点也能自动继承高风险标记
- `stage_a_clean.py` 与 `stage_a_llm.py` 的 high-risk 判断已统一改为读取 schema:
  - 不再按 `l1 in {"gov", "security"}` 做引擎内分支
  - `high-risk related suppression`、`governance fallback relationship bonus`、`high-risk escalation` 现在都依赖 schema 注入的高风险标记
- 这一步的性质是**行为保持型重构**，目标是清除剩余 engine-side hardcoding，而不是改动评测目标或放松护栏
- 已完成单元回归:
  - `tests/test_stage_r_clean.py`
  - `tests/test_stage_a_clean.py`
  - `tests/test_stage_a_llm.py`
  - 当前 `34` 个测试通过
- 当前执行判断更新:
  - `Stage A` 源码层面，`meeting/schedule` 的 sibling 约束和 `gov/security` 的 high-risk 约束都已完成 schema 化
  - 若后续还需继续清理，重点不再是 `RISK_L1` 这类显式域名分簇硬编码，而是 provider 稳定性与 `Stage B` 升级策略

### 10.16 2026-03-15 凌晨 `dev-set closure` 与泛化边界说明
- 需要明确: 当前 `sr_clean_v2_related2 + sa_clean_v7/v8` 在 `formal/dev` 上出现的 `PrimaryAcc@1 = 1.0`、`RelatedRecall = 1.0`、`RelatedPrecision = 1.0`，应被解释为**开发集闭环 (`dev-set closure`)**，而不是对未知样本泛化能力的充分证明。
- 原因不是当前 live code 仍保留大量赤裸引擎硬编码；更核心的原因是:
  - 这一路结果是在同一份 `formal/dev` 上经过多轮误差分析、schema/descriptor 补充、gating 收口后得到的
  - 因而其中包含显著的 **dev-driven manual tuning** 成分
  - 这类调优即使已经从 engine-side `if/else` 迁移到 schema/descriptor，也仍然不应被表述为“纯泛化能力提升”
- 因此，对当前结果最准确的研究口径应为:
  - `clean Stage A` 已在固定 namespace、固定 schema、固定 snapshot、固定 `formal/dev` 开发集上完成工程闭环
  - 当前证据支持“受约束裁决器在封闭候选路由任务中可被工程化收口”
  - 当前证据**不直接支持**“该方法已被证明对未见 query family/未见语义变体具有强泛化能力”
- 这也意味着，后续不宜再把继续追高 `formal/dev` 分数作为主目标；更有价值的下一步应是:
  1. 冻结当前代码、schema 与 snapshot
  2. 构造不参与本轮调参的 `blind holdout` / `family-split holdout`
  3. 在 holdout 上同时报告 deterministic clean、mock provider、real provider 三条线结果
  4. 将 `formal/dev` 成绩定位为“development closure evidence”，而非最终泛化结论

### 10.17 2026-03-15 凌晨 `Stage A v1` 完成度判断
- 对 `Stage A` 当前状态，需区分“实现完成”与“验证完成”两层口径:
  - 若按 **`clean Stage A v1` 的方法实现、工程表达、与开发集闭环** 判断:
    - 当前可视为**基本完成**
    - 可冻结对象为:
      - `sr_clean_v2_20260314_related2`
      - `sa_clean_v8_20260314_riskschema_on_sr_v2`
    - 当前已满足:
      - 候选内裁决边界明确
      - `sibling` 与 `high-risk` 约束完成 schema 化
      - deterministic clean 链路在 `formal/dev` 上可回放、可归因、可复现
  - 若按 **正式研究验证与对外泛化结论** 判断:
    - 当前**尚未完成**
    - 缺口主要不在算法功能，而在:
      - 独立 holdout 证据尚未跑完
      - real-provider 全量结果仍受 provider 稳定性影响
      - `formal/dev` 高分仍只能解释为 `dev-set closure`
- 因此，当前最合适的项目判断应为:
  - `Stage A v1` 的**实现阶段**可以冻结
  - `Stage A v1` 的**验证阶段**尚未收官
  - 后续默认不再继续面向 `formal/dev` 增量调规则；若必须继续调参，必须升新版本并重置 blind 口径
- 下一步执行重心也应同步切换:
  1. 按 formal 协议完成 holdout 验证
  2. 保留 `clean / mock / real-provider` 三轨对照
  3. 将新增研发精力优先投向 `Stage B` 设计与 provider 稳定性，而不是继续堆 `Stage A dev` 分数

### 10.18 2026-03-15 上午 holdout 主线已启动
- 已按冻结版本在 `blind_input` 上启动 formal holdout 主线，但当前仍**未 join `blind_labels`**，因此尚未形成可宣称的 blind 质量结论。
- 已完成的无标签执行产物:
  - `Stage R blind snapshot`:
    - `artifacts/stage_r_clean/blind.sr_clean_v2_20260314_related2.jsonl`
    - `artifacts/stage_r_clean/blind.sr_clean_v2_20260314_related2.summary.json`
    - 当前仅记录:
      - `samples = 35`
      - `labels_available = false`
  - `Stage A clean blind trace`:
    - `artifacts/stage_a_clean/blind_input.sa_clean_v8_20260314_riskschema_on_sr_v2.jsonl`
    - `artifacts/stage_a_clean/blind_input.sa_clean_v8_20260314_riskschema_on_sr_v2.summary.json`
    - 当前仅记录:
      - `labeled = false`
      - `trace_validation.valid = true`
- 这一步的意义是:
  - 证明冻结版本已经可以在 blind 输入上无标签执行
  - 先把 holdout 所需 snapshot/trace 固化下来
  - 在不破坏盲测纪律的前提下，把“计划”推进为“已执行到一半的 formal holdout pipeline”
- 下一步最直接的动作是:
  1. 在保持 freeze 不变的前提下，对 blind trace 与 `blind_labels` 做单次 join 评测
  2. 再补 `Stage A llm mock blind`
  3. 再视 provider 稳定性决定 `Stage A real-provider blind` 的执行窗口

### 10.19 2026-03-15 上午 blind 单次揭盲结果
- 已完成一次性 blind join 评测:
  - `artifacts/dataset/blind_joined_20260315_once.jsonl`
  - 当前 blind 结果若后续继续调参，应自动降级为 `exploratory`
- `Stage R clean` blind 结果 (`blind_revealed_20260315_once.sr_clean_v2_20260314_related2.summary.json`):
  - `samples = 35`
  - `PrimaryRecall@10 = 0.9714`
  - `RelatedCoverage@10 = 1.0`
- `Stage A clean` blind 结果 (`blind_joined_20260315_once.sa_clean_v8_20260314_riskschema_on_sr_v2.summary.json`):
  - `samples = 35`
  - `PrimaryAcc@1 = 0.8286`
  - `AcceptablePrimary@1 = 0.8571`
  - `RelatedRecall = 0.8333`
  - `RelatedRecall@Covered = 0.8333`
  - `RelatedPrecision = 0.9091`
  - `related_overpredict_rate = 0.0286`
  - `escalation_rate = 0.4857`
  - `error_buckets = {"OK": 30, "decision_primary_miss": 4, "stage_r_primary_miss": 1}`
- 当前 blind 暴露的 5 个非 `OK` 样本:
  - `formal_blind_000019`
    - `summary.meeting.productivity.cn -> docs.productivity.cn`
  - `formal_blind_000021`
    - `docs.productivity.cn -> risk.security.cn`
  - `formal_blind_000024`
    - `xian.itinerary.travel.cn -> xian.hotel.travel.cn`
  - `formal_blind_000026`
    - `flight.travel.cn` 未被 `Stage R` 召回进主候选
  - `formal_blind_000031`
    - `nutrition.health.cn -> restaurant.travel.cn`
- 当前执行判断发生实质更新:
  - `formal/dev` 上的 `1.0` 结论已被 blind 结果明确打破
  - 这进一步验证了 `10.16` 中对 `dev-set closure` 的判断是必要且正确的
  - `Stage A v1` 目前**不能**按“验证完成”放行
  - 当前最合理的后续动作不再是继续写 `Stage A 已完成` 的结论，而是:
    1. 冻结并保留本轮 blind 结果作为第一份 holdout 证据
    2. 对 5 个 blind 失败样本做 family/root-cause 复盘
    3. 明确决定是升 `Stage A v2` 继续修订，还是把当前版本作为 `dev-closed but holdout-failed` 的中间态保留

### 10.20 2026-03-17 `Stage A blind` 正式误差分析已落文档
- 已将 blind 非 `OK` 样本的正式误差分析单开为:
  - `closure/19_stage_a_blind_error_analysis.md`
- 当前正式分桶:
  - `ontology / descriptor blind spot`
  - `primary-secondary disentanglement`
  - `sibling tie`
  - `stage_r recall miss`
- 五个非 `OK` 样本中:
  - `decision_primary_miss = 4`
  - `stage_r_primary_miss = 1`
- 最适合写入论文 Error Analysis 的典型样本:
  - `formal_blind_000021`
    - 文档主任务被显式 `风险` 词拉偏
  - `formal_blind_000031`
    - `nutrition` 与 `restaurant` 的跨域语义边界歧义
- 当前执行判断进一步收敛为:
  - `Stage A v1` 的 blind 证据已经足以支持“单裁决器存在明确理解上限”的叙事
  - 后续不应再修改 `Stage A v1` 去追这 4 个 blind miss

### 10.21 2026-03-17 `Stage B` 最小工程起步方案已落文档
- 已确认当前仓库中:
  - 存在 `Stage B` 文档设计与 schema 预留位
  - 不存在 `Stage B` 代码、脚本、测试与样本池
- 已将最小工程起步方案单开为:
  - `closure/20_stage_b_bootstrap_plan.md`
- 当前推荐的 `Stage B` 最小实现顺序:
  1. 生成 `Stage B seed pool`
     - 先用 blind 中全部 escalated 样本
  2. 落 `Stage B harness`
     - `input trace -> stage_b trace -> summary`
  3. 再实现最小结构化多角色共识
     - 不做开放 debate
     - 只做候选内 structured consensus
- 当前项目执行重心正式切换为:
  - `Stage A` 封板
  - `Stage B` 开工
