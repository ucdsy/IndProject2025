# `holdout2` 数据规格书（历史规格；`holdout2` 已揭盲）

> 目的: 在 `formal/dev`、`formal/blind`、`formal/challenge` 已分别于 **2026-03-15** 与 **2026-03-20** 揭盲后，补充一份新的、未参与当前调参的正式验证集，用于重新评估 `Stage A / Stage B` 是否存在真实泛化增益。
>
> 适用范围: `Stage A vNext`、`Stage B` 后续版本的正式验证。
>
> 口径: 本规格书服务于 **新的 unrevealed split**。任何基于当前 `dev / blind / challenge` 的继续调参结果，都只能算 `exploratory`，不能替代本规格书定义的 `holdout2`。
>
> 当前状态补充:
> - 本文记录的是 `holdout2` 生成前交给数据负责人的历史规格。
> - `holdout2` 已于 **2026-03-22** 完成单次 join / 揭盲。
> - 因此，本文现在应被阅读为“数据生成与泄漏治理依据”，而不是当前仍待执行的未揭盲计划。

## 1. 结论先行
- 需要新增一份 **`family-disjoint`、未揭盲、可单次 join** 的 `holdout2`。
- `holdout2` 的用途不是继续给算法负责人“找可修样本”，而是回答一个更硬的问题:
  - 后续版本是否真的比当前冻结基线更好
  - 还是只是在已看过的 `dev / blind / challenge` 上继续收口
- `holdout2` 必须明确禁止:
  - 针对已暴露错例补样本
  - 按已知失败 `fqdn` / family 定向出题
  - 把 `holdout2` 做成另一个“为 Stage B 量身定做的难例池”

## 2. 建议文件
- `data/agentdns_routing/formal/holdout2_input.jsonl`
- `data/agentdns_routing/formal/holdout2_labels.jsonl`
- `data/agentdns_routing/formal/holdout2_manifest.json`
- `data/agentdns_routing/formal/holdout2_coverage_status.csv`

如现有治理文件可复用，则不必新开副本:
- `data/agentdns_routing/formal/family_ledger.csv`
- `data/agentdns_routing/formal/coverage_plan.csv`

## 3. 核心原则
### 3.1 必须 `family-disjoint`
- `holdout2` 中的样本 family，不得与以下 split 重叠:
  - `formal/dev.jsonl`
  - `formal/blind_input.jsonl`
  - `formal/challenge_input.jsonl`
- `family-disjoint` 不只指 query 文本不同，而是:
  - 不同 query family
  - 不同模板变体
  - 不同同义改写
  - 不同“换地名/换参数/换实体”的轻微改写

### 3.2 不允许按已揭盲失败样本反向造题
- 明确禁止以下做法:
  - 看到 `formal_blind_000019 / 000021 / 000024 / 000031` 后，按其结构造“相似新题”
  - 围绕已知 `Stage B` 成败样本，复制其 domain 组合或 query skeleton
  - 让 `holdout2` 专门偏向当前 `Stage B` 好发挥或好翻车的模式
- 允许的做法是:
  - 依据抽象 confusion type 配额采样
  - 依据 namespace coverage 缺口采样
  - 依据 family-disjoint 约束采样

### 3.3 不扩大运行时任务边界
- `holdout2` 必须仍然服从当前 AgentDNS 任务定义:
  - 只在现有 namespace 内选 `primary / related`
  - 不新增运行时外部知识源
  - 不要求开放检索
  - 不要求候选集外发明新 fqdn
- 如果样本依赖当前 namespace 根本不存在的业务概念:
  - 可以保留极少量作为 `OOD-like` 压力样本
  - 但必须单独标注，不得与主表混算

## 4. 建议规模
- 建议总量: **48-60 条**
- 推荐默认值: **54 条**

理由:
- 少于 `40` 条，难以稳定比较 `Stage B` 是否真有增益
- 多于 `60` 条，会增加标注与泄漏治理成本，但未必带来等比例信息增益

## 5. 建议组成
`holdout2` 不应全是 hard cases。建议保留“可升级慢路径样本”和“本应 fast-path 直接解决的样本”两类。

推荐配额:
- `12` 条: `hierarchy / sibling competition`
- `10` 条: `cross-domain overlap / cross-l1 conflict`
- `10` 条: `multi-intent primary-secondary disentanglement`
- `8` 条: `high-risk / governance / compliance`
- `8` 条: `ordinary fast-path` 样本
- `6` 条: `mixed long-tail but in-namespace`

额外要求:
- 至少 `20` 个不同 `base_fqdn`
- 不得让某一 `l1` 顶级域占比过高
- `multi_intent` 建议占比控制在 `35%-50%`
- `l3 / child / segment` 样本占比建议不低于 `25%`

## 6. 样本设计要求
### 6.1 每条样本必须满足
- 存在唯一 `ground_truth_fqdn`
- 如存在真实 secondary intent，则提供 `relevant_fqdns`
- `ground_truth_fqdn` 必须属于当前 namespace
- query/context 必须能被人类在当前 namespace 范围内合理解释

### 6.2 不要把“模糊”误当“难”
- 可以有隐式语义，但不能故意写成不可判定句子
- 难度应该来自:
  - hierarchy/sibling 混淆
  - primary/secondary 解耦
  - cross-domain 竞争
  - governance/high-risk guard
- 不应该来自:
  - 纯拼写噪声
  - 故意残缺输入
  - 明知 namespace 无定义的完全 OOD 任务

### 6.3 `related` 设计原则
- 只有存在真实 secondary intent 时，才标 `relevant_fqdns`
- 不要把“常识上可能有帮助”的邻近节点都算 `related`
- `related` 必须与 query 中的 secondary signal 对齐

## 7. 字段要求
### 7.1 `holdout2_input.jsonl`
每条至少包含:
- `id`
- `query`
- `context`

可选但推荐:
- `metadata`
- `source_bucket`
- `difficulty_tag`

### 7.2 `holdout2_labels.jsonl`
每条至少包含:
- `id`
- `ground_truth_fqdn`
- `acceptable_fqdns`
- `relevant_fqdns`
- `intended_confusion_types`
- `family_id`

推荐增加:
- `primary_granularity`
- `secondary_intent_present`
- `high_risk_case`
- `notes_for_audit`

## 8. `family_id` 与泄漏治理
### 8.1 `family_id` 的定义
`family_id` 应表示“同一语义骨架”，而不是仅表示 domain。

同 family 的典型例子:
- 只是换城市名
- 只是换金额/人数/时长
- 只是把“帮我安排路线”改成“先规划行程”
- 只是 query/context 互换轻微措辞

### 8.2 验收要求
- `holdout2` 的 `family_id` 不得出现在:
  - `dev`
  - `blind`
  - `challenge`
- 必须输出一份 family 泄漏检查结果

## 9. 标注纪律
### 9.1 标注人不应看到
- 当前 `Stage A / Stage B` 的失败样本榜单
- 当前模型在哪些 case 上会修、在哪些 case 上会翻车
- 当前 exploratory split 的具体误差分析文档

### 9.2 标注口径固定
- 标 `primary` 时，不参考当前模型输出
- 标 `related` 时，不以“模型是否容易召回”为标准
- 不因当前 schema 稀疏就人为放宽 primary 边界

## 10. 揭盲协议
### 10.1 开发期
- 算法负责人可读取:
  - `holdout2_input.jsonl`
- 算法负责人不得读取:
  - `holdout2_labels.jsonl`

### 10.2 冻结后
- 冻结对象至少包括:
  - `stage_r_version`
  - `stage_a_version`
  - `stage_b_version`
  - descriptor/schema 版本
- 冻结后对 `holdout2_labels.jsonl` 只允许做**单次 join**
- 生成一次:
  - `holdout2_joined_YYYYMMDD_once.jsonl`

### 10.3 若揭盲后继续调参
- 必须升版本
- 该次 `holdout2` 结果自动降级为 `exploratory`
- 不得继续对外表述为“正式 holdout 结论”

## 11. 建议验收门槛
数据负责人交付前，至少满足:
- validator `ok = true`
- `family-disjoint` 检查通过
- 样本总数达到目标区间
- 各 confusion bucket 达到最小配额
- `base_fqdn` 覆盖达到目标
- `notes_for_audit` 不为空的样本比例低于 `10%`

## 12. 建议交付清单
- `holdout2_input.jsonl`
- `holdout2_labels.jsonl`
- `holdout2_manifest.json`
- `holdout2_coverage_status.csv`
- 一份简短说明:
  - 样本总量
  - bucket 分布
  - `family-disjoint` 检查是否通过
  - 是否含 `OOD-like` 压力样本，以及数量

## 13. 一句话执行指令
给数据负责人的最短口径可以直接写成:

> 请基于现有 namespace 与 formal 协议，生成一份新的 `holdout2`。  
> 要求 `family-disjoint` 于当前 `dev / blind / challenge`，禁止按已揭盲错例反向造题，规模控制在 `48-60` 条，并按 hierarchy/sibling、cross-domain、multi-intent、high-risk、ordinary fast-path 做平衡覆盖。  
> 算法组开发阶段只读取 `input`，`labels` 在冻结后单次揭盲。
