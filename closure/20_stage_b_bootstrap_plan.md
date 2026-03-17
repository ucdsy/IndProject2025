# Stage B Minimal Bootstrap Plan（2026-03-17）

> 目的: 在冻结 `Stage A v1` 的前提下，明确 `Stage B` 的最小工程起步范围、接口、文件落点与执行顺序。
>
> 适用范围: `Stage B v0/v1` 代码脚手架、样本池、评测器与答辩实现计划。

## 1. 当前仓库状态

### 1.1 已有
- `Stage A -> Stage B` 触发字段已经存在:
  - `escalate_to_stage_b`
  - `escalation_reasons`
- `routing_run_trace.schema.json` 已为 `stage_b` 预留 object 位
- 文档已定义 `Stage B` 目标与机制:
  - `closure/13_design_doc_agentdns_routing.md`
  - `README.md`
  - `research-project/03_experiment-plan.md`

### 1.2 尚无
- 无 `src/.../stage_b_*.py`
- 无 `scripts/run_stage_b.py`
- 无 `tests/test_stage_b.py`
- 无正式 `Stage B` 样本池文件
- 无 `Stage B` evaluator / trace writer

结论:
- 当前 `Stage B` 还处于**设计完成、工程未开工**状态。

## 2. Stage B 的最小目标
- 不做开放式多轮自由 debate
- 不做开放检索
- 不做候选集外发明新路由
- 只处理 `Stage A` 已触发 escalation 的样本
- 只在 `Stage R` 冻结候选集内做更强的结构化共识裁决

最小成功标准:
- 能消费 `Stage A trace`
- 能输出结构化 `stage_b` 字段
- 能在一批 escalated 样本上给出可回放的共识结果
- 能独立评测 `Stage B` 对 `Stage A` 难例的修复情况

## 3. 推荐输入输出

### 3.1 输入
- `sample`
- `stage_r snapshot`
- `stage_a trace`
- `fqdn_candidates`
- `candidate_scores`
- `escalation_reasons`

### 3.2 输出
- `selected_primary_fqdn`
- `selected_related_fqdns`
- `consensus_confidence`
- `consensus_margin`
- `consensus_rounds`
- `agent_votes`
- `agent_rationales`
- `feedback_scores`
- `trust_trace`
- `constraint_check`

## 4. 推荐机制

### 4.1 不做开放 debate
理由:
- 不可控
- 不可复现
- 不利于日志化与答辩

### 4.2 做结构化多角色共识
最小角色集采用文档既有口径:
- `DomainExpert`
- `GovernanceRisk`
- `CostLatency`
- `UserPreference`

最小循环:
1. Round 1: 各角色在固定候选内给 `proposal_primary + proposal_related + confidence + rationale`
2. 聚合: 对 top candidates 计算结构化 `feedback score`
3. Round 2: 若 top1-top2 差距不足，则只围绕 top2 做一次修正
4. 终止: 达到 margin 阈值或轮次上限

## 5. 最小文件落点

### 5.1 代码
- `src/agentdns_routing/stage_b_consensus.py`
  - 核心共识逻辑
- `src/agentdns_routing/stage_b_eval.py`
  - 针对 Stage B trace 的评测器

### 5.2 脚本
- `scripts/run_stage_b.py`
  - 输入 `Stage A trace`
  - 输出 `Stage B trace` 与 summary

### 5.3 测试
- `tests/test_stage_b.py`
  - 先覆盖:
    - 候选内约束
    - 多角色投票结构合法性
    - 共识终止条件
    - chain duplicate / invalid fqdn 防护

### 5.4 数据
- `data/agentdns_routing/formal/stage_b_seed_pool.jsonl`
  - 初始只放 escalated 样本及其标签视图

## 6. 样本池建议

### 6.1 第一批主池
- 直接使用 blind 中所有 `Stage A escalated` 样本
- blind `escalation_rate = 0.4857`
- `35 * 0.4857 = 17`
- 因此第一批主池可直接取 `17` 条 blind escalated 样本

### 6.2 重点难例
- 必须单列这 `5` 条:
  - `formal_blind_000019`
  - `formal_blind_000021`
  - `formal_blind_000024`
  - `formal_blind_000026`
  - `formal_blind_000031`

### 6.3 作用
- 这不是训练集
- 这是 `Stage B` v0/v1 的:
  - 开发难例池
  - demo 难例池
  - 论文 Error Analysis 对照池

## 7. 实施顺序

### 7.1 第一步
- 先写 `Stage A blind error analysis`
- 冻结 `Stage A v1` 边界

### 7.2 第二步
- 生成 `Stage B seed pool`
- 明确输入格式

### 7.3 第三步
- 先搭 `Stage B harness`
- 能够跑通:
  - `input trace -> stage_b trace -> summary`

### 7.4 第四步
- 再上最小共识算法
- 优先做 deterministic / mock-friendly 版本
- 不急着接真实 provider

### 7.5 第五步
- 在 seed pool 上做:
  - single-agent baseline
  - simple vote baseline
  - structured consensus

## 8. 当前建议
- 下一步工程**不是**继续修 `Stage A`
- 下一步工程是:
  1. 固化 `Stage A` 的 blind 误差边界
  2. 生成 `Stage B` seed pool
  3. 落 `Stage B` harness 与 evaluator

一句话:
- `Stage A` 现在负责“快路径裁决 + 不确定性探测”
- `Stage B` 接下来负责“慢路径共识 + 难例修复 + 可信轨迹”
