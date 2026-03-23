# 实验计划

> 注:
> - 本文是早期研究 framing 与实验计划，不代表当前 frozen 实验矩阵。
> - 当前 live repo 的实现与结果，应以 `research-project/04_execution-log.md`、`closure/20_stage_b_bootstrap_plan.md` 与 `closure/24_stage_a_uncertainty_and_stage_b_packet_v2_design.md` 为准。
> - 文中的样本规模目标、早期基线命名与未来式表述主要保留作研究过程记录。

## 待验证主张
围绕任务书的三段式路径（异质生成 -> 共识演化 -> 可信标识）验证 3 类主张：
1. 质量: 多智能体协作在真实/准真实标签约束下，优于单智能体或简单投票。
2. 稳定性与可控性: 共识机制在多轮交互/反馈下更稳定（更低方差）且更能满足规则/约束。
3. 可审计性: 轻量级可信标识/行为链能让过程可复核，且额外成本可控。

## 数据集
由于拿不到注册信息/审核数据，本项目把“典型任务”收敛到**智能体命名与寻址/路由（AgentDNS 风格）**，数据可自建且可复现。

### 主任务: Agent 路由与共识选择
- 输入: 用户自然语言请求（可包含时间/地点/预算/偏好等上下文）。
- 中间过程:
  - Stage R: `query/context -> namespace recall -> fqdn_candidates`
  - Stage A/B: 在候选内决定 `primary + related`
  - Stage C: `selected_primary_fqdn -> chosen agent_fqdn -> endpoint`
- 输出:
  - Top-1 主路由选择（`selected_primary_fqdn`）
  - 可选: `selected_related_fqdns` 与 `routing_top_k`
  - 结构化轨迹: `stage_r_trace / routing_trace / selection_trace`
- 标签:
  - 每条样本固定 1 个 `ground_truth_fqdn`
  - 可选: `relevant_fqdns`
  - 可选: `acceptable_fqdns`

### 数据构建方案（不依赖业务注册信息，以下规模目标属早期规划）
- L1（推荐）: 自建小规模标注集（300-800 条）
  - 来源: 基于现有 AgentDNS 标签体系做 label-first 构造:
    - 先选 `ground_truth_fqdn`
    - 再补 `relevant_fqdns`
    - 再反向生成 query
    - 再标注 `intended_confusion_types`
  - 标注: 先由规则/LLM 生成初标，再进行人工复核；至少做 2 人交叉抽检，记录一致性与争议样例。
  - 注意:
    - gold 数据集不手工写 `fqdn_candidates`
    - `fqdn_candidates` 由 Stage R 在运行时生成
    - 为公平对比，可额外导出 `candidate snapshot`
- L2（加分）: 引入公开“工具路由/意图到工具选择”数据集，映射到你的 capability tags，用于泛化性小实验。

### Stage R 独立评测
- `L1Acc`
- `L2Acc`
- `L3Acc`（仅 `l3` 子集）
- `PrimaryRecall@5/10`
- `RelatedCoverage@5/10`
- `UnionCoverage@10`
- `OraclePrimary@K`


## 基线设置（早期规划命名，非当前唯一实验矩阵）
- Single-Agent Prompting: 单智能体 + 最佳提示（含检索或规则提示）。
- Multi-Agent Vote: 多角色独立判断 + 多数投票/加权投票。
- No-Feedback Consensus: 多轮但不计算反馈函数。
- (Ours) Preference/Label-Driven Consensus: 引入用户代理/偏好模型（或标签反馈函数）对候选决策打分，驱动多轮“提案-修正-收敛”。
- Trust/Audit Baseline: 与 Ours 相同但移除可信标识/行为链，仅保留普通日志（用于对比审计能力与开销）。

## 指标体系
质量类（路由任务）:
- Primary Accuracy@1: `selected_primary_fqdn` 是否等于 `ground_truth_fqdn`。
- Primary Recall@K: ground-truth 是否落在 top-K 候选中（K=3/5 常用）。
- Relevant Recall@K: `relevant_fqdns` 是否被 top-K 覆盖。
- Taxonomy Validity: 输出 fqdn/tag 路径在你的命名空间中合法存在的比例。

稳定性/一致性:
- Disagreement Rate: 同一输入重复运行 N 次（不同 seed/temperature）路由选择不一致比例。
- Convergence: 共识轮次、修订次数、分数边际提升（体现“演化/收敛”而不是拍脑袋）。

可解释/可审计:
- Explanation Quality: 人评打分（理由充分性、与标签路径一致性、可操作性）。
- Trace Completeness: 轨迹字段完整率（每轮输入/输出、候选、打分、选择理由）。
- Tamper Evidence (if hash-chain): 篡改可检测率（对日志改动是否能被校验发现）。

成本:
- Token/Latency: 平均 token、时延、调用次数；以及“审计增强”带来的相对开销。
- SelectionLatency: Stage C 下一跳发现耗时。
- ProviderMaxShare / ProviderCoverage: provider 公平曝光指标。

## 消融矩阵
- Remove Heterogeneity: 角色/认知风格统一（看异质性贡献）。
- Remove Feedback: 去掉用户代理/标签反馈，仅一次性讨论/投票（看演化贡献）。
- Remove Coverage Term: 去掉多相关覆盖项（看列表返回能力的贡献）。
- Remove Trust ID: 去掉 hash-chain/身份标识，仅普通日志（看可信标识贡献）。
- Vary #Agents: 2/3/4 个智能体（质量-成本曲线）。
- Vary Consensus Policy: 多数票 vs 无反馈多轮 vs 反馈驱动（策略对比）。

## 算力预算
- 以 1 台 4090 级别主机为基准（任务书设备预算对应）。
- 采用“缓存 + 小数据集 + 控温度”的设置优先保证可复现与迭代速度。

## 复现设置
- 固定随机种子与温度区间（例如 temperature=0.2/0.7 两档）。
- 记录: 模型版本、提示模板版本、检索语料版本、代码 commit、运行参数、硬件信息。
- 所有实验输出落盘为结构化 JSON/CSV + 自动生成表格脚本（便于报告/论文复用）。
