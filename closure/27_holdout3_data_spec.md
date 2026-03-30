# `holdout3` 数据规格书（400 条 fresh validation）

> 目的: 在 `dev / blind / challenge / holdout2` 均已揭盲后，新增一份 **fresh、family-disjoint、单次揭盲** 的 `holdout3`，用于为结项论文、项目评审与后续专利材料提供更大规模的独立补充验证。
>
> 适用范围: 当前冻结主线
> - `Stage R = sr_clean_v2_20260314_related2`
> - `Stage A clean = sa_clean_v2_20260314`
> - `Stage A llm = sa_llm_v2_20260323_uncertainty`
> - `Stage B = stage_b_v1_20260323_packetv2`
>
> 口径:
> - 本规格书服务于新的 unrevealed split。
> - `holdout3` 不是 `dev / blind / challenge / holdout2` 的改写扩容版，也不是 paraphrase stress set。
> - `holdout3` 的用途是验证当前冻结方法在 **新 family + 新 query skeleton + 新表面风格** 下是否仍然成立。

## 1. 结论先行
- 建议新增一份 **400 条** 的 `holdout3`。
- `holdout3` 的核心价值不是“再多跑一点数据”，而是同时控制三层分布:
  - `eval_bucket`
  - `intent_form`
  - `surface_style`
- `holdout3` 必须明确禁止:
  - 复用旧 `dev / blind / challenge / holdout2` 的 query skeleton
  - 对已暴露错例做同义改写或换实体重写
  - 围绕当前 `Stage A / B` 成败样本定向造题
  - 把它做成“专为 `Stage B` 量身定制的难例池”

## 2. 建议文件
- `data/agentdns_routing/formal/holdout3_input.jsonl`
- `data/agentdns_routing/formal/holdout3_labels.jsonl`
- `data/agentdns_routing/formal/holdout3_manifest.json`
- `data/agentdns_routing/formal/holdout3_coverage_status.csv`
- `data/agentdns_routing/formal/holdout3_skeleton_audit.csv`

如现有治理文件可复用，则不必新开副本:
- `data/agentdns_routing/formal/family_ledger.csv`
- `data/agentdns_routing/formal/coverage_plan.csv`

## 3. 核心原则
### 3.1 必须 `family-disjoint`
- `holdout3` 的 `family_id` 不得与以下 split 重叠:
  - `formal/dev.jsonl`
  - `formal/blind_input.jsonl`
  - `formal/challenge_input.jsonl`
  - `formal/holdout2_input.jsonl`
- `family-disjoint` 不只指 query 文本不同，而是:
  - 不同 query family
  - 不同任务骨架
  - 不同实体替换模板
  - 不同语义展开路径

### 3.2 必须 `skeleton-disjoint`
- 除了 family 不重叠，还必须避免 query skeleton 重叠。
- 明确禁止:
  - 旧 query 的同义改写
  - 旧 query 的“换城市/换金额/换对象词”版本
  - 保留旧句法骨架，只替换名词短语
  - 保留旧语用骨架，例如:
    - `先做 A，另外补 B`
    - `围绕 X 先处理这一步`
    - `准备落地 / 优先看 / 顺手再补`
- 必须生成新的组织方式:
  - 新的句法结构
  - 新的任务陈述顺序
  - 新的显式/隐式约束表达

### 3.3 不扩大运行时任务边界
- `holdout3` 必须仍然服从当前 AgentDNS 任务定义:
  - 只在现有 namespace 内选 `primary / related`
  - 不新增运行时外部知识源
  - 不要求开放检索
  - 不要求候选集外发明新 fqdn
- 如果样本依赖当前 namespace 根本不存在的概念:
  - 可以保留极少量 `OOD-like` 压力样本
  - 但必须单独标记，不得与主表混算

## 4. 建议规模
- 总量: **400 条**

理由:
- 当前要同时控制 `eval_bucket / intent_form / surface_style` 三层分布
- 若总量过低，容易出现“分桶覆盖看似完整，实际还是模板重复”
- `400` 条能在不把治理成本推到失控的前提下，提供较扎实的覆盖

## 5. 三层控制维度
### 5.1 `eval_bucket`（问题结构）
这是样本设计与误差分析分桶，不是模型运行时预测标签。

固定 5 类，每类 `80` 条:
- `ordinary_fast_path`
  - 主意图明确、候选竞争弱、按理应由 fast path 直接解决
- `sibling_hierarchy`
  - 主竞争发生在 sibling / parent-child / base-segment 之间
- `primary_secondary_disentanglement`
  - query 同时含主请求与补充请求，难点是区分 `primary` 与 `related`
- `cross_domain_overlap`
  - 主要竞争跨 `l1`，难点是跨域语义边界
- `high_risk_governance`
  - 含合规/身份/资金/安全等高风险约束

### 5.2 `intent_form`（语用形态）
固定 5 类，每类建议全局约 `80` 条，允许各 bucket 内不完全平均，但必须覆盖。

- `direct_request`
  - 直接命令/直接要求
- `scene_description`
  - 先交代场景，再隐含任务
- `stepwise_instruction`
  - 多步任务，但不沿用旧固定骨架
- `constraint_first`
  - 先讲限制、边界、风险，再讲目标
- `goal_then_support`
  - 先讲主目标，再补辅助诉求或上下文

### 5.3 `surface_style`（表面语言风格）
固定 6 类，允许不完全均分，但必须都有覆盖。

- `colloquial`
- `formal`
- `enterprise`
- `compressed`
- `indirect`
- `mixed`

说明:
- `surface_style` 控制的是语言表现，不是任务类型
- 同一 `eval_bucket` 中必须出现多种 `surface_style`

## 6. 配额与覆盖要求
### 6.1 主配额
- `ordinary_fast_path`: `80`
- `sibling_hierarchy`: `80`
- `primary_secondary_disentanglement`: `80`
- `cross_domain_overlap`: `80`
- `high_risk_governance`: `80`

### 6.2 交叉覆盖要求
对每个 `eval_bucket`，至少满足:
- 覆盖不少于 `4` 种 `intent_form`
- 覆盖不少于 `4` 种 `surface_style`
- 不允许同一 bucket 中某一种 query skeleton 占比超过 `20%`

### 6.3 namespace 覆盖要求
- 至少覆盖 `25` 个不同 `base_fqdn`
- 不允许某一个 `l1` 占比超过 `35%`
- `multi-intent` 样本占比建议控制在 `30%-45%`
- `l3 / child / segment` 样本占比建议不低于 `25%`

## 7. 样本设计要求
### 7.1 每条样本必须满足
- 存在唯一 `ground_truth_fqdn`
- 若存在真实 secondary intent，则提供 `relevant_fqdns`
- `ground_truth_fqdn` 必须属于当前 namespace
- query/context 必须能被人类在当前 namespace 范围内合理解释

### 7.2 难度来自结构，不来自噪声
- 可以有隐式语义，但不能故意写成不可判定句子
- 难度应主要来自:
  - hierarchy/sibling 冲突
  - primary/secondary 解耦
  - cross-domain 竞争
  - governance/high-risk 边界
- 难度不应主要来自:
  - 纯拼写噪声
  - 故意残缺输入
  - 超出当前 namespace 的完全 OOD 任务

### 7.3 `related` 设计原则
- 只有存在真实 secondary intent 时，才标 `relevant_fqdns`
- 不要把“常识上可能有帮助”的邻近节点都算 `related`
- `related` 必须与 query 中可解释的 secondary signal 对齐

## 8. 字段要求
### 8.1 `holdout3_input.jsonl`
每条至少包含:
- `id`
- `query`
- `context`

推荐增加:
- `metadata`
- `source_bucket`
- `difficulty_tag`
- `intent_form`
- `surface_style`

### 8.2 `holdout3_labels.jsonl`
每条至少包含:
- `id`
- `ground_truth_fqdn`
- `acceptable_fqdns`
- `relevant_fqdns`
- `eval_bucket`
- `bucket_tags`
- `family_id`
- `intent_form`
- `surface_style`

推荐增加:
- `primary_granularity`
- `secondary_intent_present`
- `high_risk_case`
- `notes_for_audit`

### 8.3 `holdout3_skeleton_audit.csv`
每条至少包含:
- `id`
- `family_id`
- `eval_bucket`
- `intent_form`
- `surface_style`
- `suspected_nearby_old_family`
- `skeleton_overlap_flag`
- `auditor_note`

## 9. `eval_bucket` 的判定规则
- `ordinary_fast_path`
  - 若主要难点不在跨域、主次分离、层级竞争、高风险约束，则归此类
- `sibling_hierarchy`
  - 若主要竞争来自同一树内 sibling / parent-child / base-segment，归此类
- `primary_secondary_disentanglement`
  - 若主要难点是区分主请求与补充请求，归此类
- `cross_domain_overlap`
  - 若主要竞争跨 `l1`，归此类
- `high_risk_governance`
  - 若高风险/治理约束是主要决定因素，归此类

若一题同时满足多类:
- 选择主冲突来源作为 `eval_bucket`
- 其他写入 `bucket_tags`

## 10. 泄漏治理
### 10.1 标注人不应看到
- 当前 `Stage A / Stage B` 的失败样本榜单
- 当前模型在哪些 case 上会修、在哪些 case 上会翻车
- 已揭盲 split 的逐样本误差分析细节

### 10.2 不允许的做法
- 看过 `formal_blind_000019 / 000021 / 000024 / 000031` 后，按其结构造相似题
- 围绕当前 `holdout2` 成败样本复制 domain 组合或 query 组织方式
- 把 `holdout3` 做成另一个“为 `Stage B` 量身定制的 hard pool”

### 10.3 skeleton 审核要求
- 所有样本必须经过一次 skeleton 审核
- 若 `skeleton_overlap_flag = true`，该样本不得进入正式 `holdout3`

## 11. 揭盲协议
### 11.1 开发期
- 算法负责人可读取:
  - `holdout3_input.jsonl`
- 算法负责人不得读取:
  - `holdout3_labels.jsonl`

### 11.2 冻结后
- 冻结对象至少包括:
  - `stage_r_version`
  - `stage_a_version`
  - `stage_b_version`
  - descriptor/schema 版本
- 冻结后对 `holdout3_labels.jsonl` 只允许做**单次 join**
- 生成一次:
  - `holdout3_joined_YYYYMMDD_once.jsonl`

### 11.3 若揭盲后继续调参
- 必须升版本
- 该次 `holdout3` 结果自动降级为 `exploratory`
- 不得继续对外表述为“正式 fresh validation 结论”

## 12. 建议验收门槛
数据负责人交付前，至少满足:
- validator `ok = true`
- `family-disjoint` 检查通过
- `skeleton_overlap_flag = true` 的样本数为 `0`
- 样本总数达到 `400`
- 各 `eval_bucket` 达到 `80`
- 各 bucket 的 `intent_form` 与 `surface_style` 覆盖达标
- `base_fqdn` 覆盖达到目标

## 13. 建议交付清单
- `holdout3_input.jsonl`
- `holdout3_labels.jsonl`
- `holdout3_manifest.json`
- `holdout3_coverage_status.csv`
- `holdout3_skeleton_audit.csv`
- 一份简短说明:
  - 样本总量
  - bucket 分布
  - `intent_form` 分布
  - `surface_style` 分布
  - `family-disjoint` 是否通过
  - `skeleton` 审核是否通过
  - 是否含 `OOD-like` 压力样本，以及数量

## 14. 一句话执行指令
给数据负责人的最短口径可以直接写成:

> 请基于现有 namespace 与 formal 协议，生成一份新的 `holdout3`。  
> 规模固定为 `400` 条，要求 `family-disjoint` 于当前 `dev / blind / challenge / holdout2`，并且必须 `skeleton-disjoint`，不得复用旧 query 的组织方式。  
> 数据设计需同时覆盖 `eval_bucket / intent_form / surface_style` 三层维度；其中 `eval_bucket` 固定为 `ordinary_fast_path / sibling_hierarchy / primary_secondary_disentanglement / cross_domain_overlap / high_risk_governance` 五类，每类 `80` 条。  
> 算法组开发阶段只读取 `input`，`labels` 在冻结后单次揭盲。
