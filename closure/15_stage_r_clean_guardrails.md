# clean Stage R 设计护栏 v1

> 目的: 约束 `stage_r_clean.py` 的后续演进，避免把 clean baseline 重新做成“先看 dev 数据再造规则”的伪 clean 方案。
>
> 适用范围: `src/agentdns_routing/stage_r_clean.py`、`scripts/run_stage_r_clean_snapshot.py` 及其依赖的 clean 知识源。
>
> 生效时间: 2026-03-06 起，直到 blind 版本冻结前持续有效。

## 1. 总原则
- clean Stage R 的目标是做一个**干净、可解释、可复现的 hierarchical recall baseline**，不是为当前 `formal/dev` 专门拧出来的命中器。
- Stage R 的职责仍然是:
  - 从 query/context 中抽取通用证据
  - 在命名空间节点上做高召回候选生成
  - 为后续 Stage A 提供 `fqdn_candidates`
- Stage R 不是本项目的唯一主创新承载位。
  - 它必须足够强，但不必承担最激进的创新叙事。
  - 主创新仍优先放在 `routing_fqdn -> agent_fqdn` 两跳解析框架、Stage A/B 的受约束决策与共识、以及可审计 trace。

## 2. 允许修改的内容（白名单）
后续增强只允许落在以下机制层面，且必须能脱离具体样本单独成立。

### 2.1 命名空间与层级结构
- 使用 canonical `routing_fqdn` 的层级先验
- 聚合 `l1/l2` 子树分数
- 控制 `segment` 只在父节点支持时展开
- 通用 `parent_fallback` / `fallback_chain` 逻辑

### 2.2 检索打分机制
- alias / descriptor / context 的一般性匹配方法
- node type bias
  - base node
  - segment node
  - parent fallback node
- evidence budget / duplicate discount
- generic overspecific penalty

### 2.3 通用上下文字段
- 只允许使用数据协议中稳定存在、跨样本可解释的 context 字段
- 当前允许的典型字段:
  - `city`
  - `industry`
  - `time_window`
  - `budget`
  - `channel`
- 如果新增 context 字段，必须先在数据协议文档中说明，不允许只在实现里偷偷消费

### 2.4 `industry` 的使用边界
- `industry` 可以作为数据协议中的稳定 context 字段存在。
- `industry_tags` 也可以作为 namespace descriptor 的节点元数据存在。
- 但 clean Stage R 的算法层**不应把 `industry` 当成享有单独待遇的特权特征**。
- 更准确的做法是:
  - 把 `industry` 视为 `metadata facet` 的一个实例
  - 与 `channel`、`goal`、`service`、`destination` 等稳定字段一起进入统一的 facet alignment 框架
  - 算法层尽量避免写出“只对 `industry` 这一类 facet 单独赋权”的逻辑
- 允许保留的特殊性只有一种:
  - `segment` / parent / fallback 这类与 namespace 拓扑直接相关的结构先验
  - 原因是它们属于 canonical routing contract，而不是业务语义维度本身
- 因此，后续如需使用 `industry`，必须满足:
  - 能被解释为“通用 metadata 对齐”的一部分
  - 若把 `industry` 替换成另一个稳定 facet，方法论仍然成立
  - 不依赖 dev 中某些高频行业词或某个行业字段的样本分布

### 2.5 独立知识源
- `closure/07_namespace_v1.md`
- `data/agentdns_routing/namespace_descriptors.jsonl`
- `artifacts/dataset/knowledge_source_audit.md`
- 命名空间结构本身推导出的 parent/segment/fallback 关系

## 3. 禁止修改的内容（黑名单）
以下做法一律视为“先射箭再画靶”，不得进入 clean Stage R。

### 3.1 数据反向拟合
- 从 `formal/dev.jsonl` 的 query 文本里反抄触发词加入检索规则
- 针对某个 miss 样本加 query 级特判
- 为某几个 family 单独设计 pattern
- 看到某条 dev 样本错了，就只为这一条补 alias/desc 词

### 3.2 holdout 泄漏
- 在 blind/challenge 标签揭盲前读取其 label 文件来调规则
- 依据 blind/challenge 的结果回填 descriptor、heuristic 或阈值
- 使用 `acceptable_fqdns`、`ground_truth_fqdn` 作为运行时特征

### 3.3 伪通用规则
- 规则存在的唯一理由是“能命中现在的这批 dev”
- 新逻辑无法用 namespace contract、descriptor schema、context schema、或通用检索原则解释
- 规则只在 1-2 条样本上成立，却被包装成一般机制

### 3.4 facet 特权化
- 不能因为 `industry` 在当前数据协议中常见，就把它写成算法层的专属特征通道
- 不能把 `industry` 写成“默认比其他 metadata facet 更可信/更强”的隐式先验，除非有独立的 schema 级论证
- 不能围绕 `industry` 单独堆一组只服务于当前 dev 分布的权重和匹配规则
- 不能用“现在很多样本都带 `industry`”作为保留 `industry` 特判的理由

## 4. clean Stage R 的正确增强方向
允许做的增强，优先按以下顺序推进:

1. 层级展开
   - 先聚合 `l1/l2` 子树分数，再决定是否展开 `segment`
2. node-type aware scoring
   - base / segment / fallback 节点使用不同偏置
3. evidence de-duplication
   - 防止 alias、desc、context 反复为同一证据加分
4. generic context alignment
   - 将 `city/industry/time_window` 等字段作为通用对齐信号，而不是样本热词
5. parent-support gating
   - `segment` 不能靠局部匹配单飞，必须有父节点支持
6. generic metadata facet matching
   - context 和 descriptor 的对齐应尽量通过统一 facet matcher 完成
   - 避免在算法代码中把 `industry`、`channel`、`goal` 等字段分别写成独立特判

当前不优先做:
- 为当前数据集专门补词
- 复杂 query-specific heuristic
- 依赖 dev 文本表述的手工模板
- 以 blind 结果为导向的二次修辞性改动

## 5. 版本迭代纪律
每次修改 clean Stage R，必须同时记录 4 件事。

### 5.1 修改目标
- 这次修改解决的是哪一类错误
- 这类错误的定义是否能脱离具体样本成立

### 5.2 理由来源
理由只能来自以下四类之一:
- namespace 结构
- descriptor schema
- context schema
- 通用检索/排序原则

不允许写:
- “因为某条 dev 样本错了”
- “因为这个词在当前数据里经常出现”

### 5.3 回归指标
每次变更至少记录:
- `PrimaryRecall@5`
- `PrimaryRecall@10`
- `RelatedCoverage@10`
- `UnionCoverage@10`
- `MRR`
- `L1Acc_top1cand`
- `L2Acc_top1cand`
- 按 `intended_confusion_types` 分层的 recall/coverage（如可提供）
- 至少 1 个“metadata facet 相关 shortcut 风险”观察结论

### 5.4 决策准则
- 若修改只能修复个别样本而无法解释一类错误，则回滚
- 若修改显著提升某个局部 case，但削弱 clean 性或增加泄漏风险，则回滚
- 若修改使规则解释开始依赖当前数据措辞而不是结构机制，则回滚

## 6. 评审问题模板
每次准备合入 clean Stage R 改动前，必须回答:

1. 这是不是一个 query-specific 特判？
2. 这条逻辑是否能只看 namespace/descriptor/context schema 也讲得通？
3. 如果把当前 dev 样本换一批同分布数据，这条逻辑大概率还成立吗？
4. 这条逻辑是在改善一种错误类型，还是只是在修几个具体样本？
5. 这条逻辑是否会诱导 future leakage？
6. 这条逻辑是不是把某个具体 facet（尤其是 `industry`）提升成了算法层的特权通道？
7. 如果把 `industry` 换成另一个稳定字段，这条逻辑还讲得通吗？

只要其中任意 1 条回答为“否”或“高风险”，该改动就不应进入 clean baseline。

## 7. 对外口径
对外统一说法:
- clean Stage R 是一个 descriptor-driven、hierarchical、auditable recall baseline
- 它的价值是:
  - 提供干净候选集
  - 维持误差归因清晰
  - 为 Stage A/B 提供可靠输入
- `industry` 等字段可以作为 schema/context 的一部分存在，但不应成为算法层的特权捷径
- 它不是为当前 50 条 `formal/dev` 定制的路由器，也不是项目唯一主创新所在

## 8. 当前执行结论
- 后续所有 clean Stage R 改动一律围绕 `src/agentdns_routing/stage_r_clean.py`
- 默认拒绝“补词式修正”
- 优先接受“机制式修正”
- blind 版本冻结前，不允许因为追求更好 dev 分数而破坏 clean 性
