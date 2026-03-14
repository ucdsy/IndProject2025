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
