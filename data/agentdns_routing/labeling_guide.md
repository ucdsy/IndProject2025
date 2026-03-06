# 标注指南 v0

当前状态修正:
- 现有 `data/agentdns_routing/dev.jsonl` 与 `test.jsonl` 只属于 `bootstrap_seed`。
- 接下来正式数据构造一律面向 `data/agentdns_routing/formal/*`。

## 1. 标注目标
每条样本都要先定：
- `ground_truth_fqdn`: 主路由，后续必须能落到 Stage C 的 `agent_fqdn -> endpoint`
- `relevant_fqdns`: 与 query 真实相关、但不作为主执行入口的能力
- `acceptable_fqdns`: 用于粒度回落容错，不等价于 `relevant_fqdns`

## 2. primary / relevant / acceptable 的区别
- `primary`: 当前 query 的主执行入口。问自己一句：如果系统只能真正调用一个能力节点，应该先落到哪里。
- `relevant`: 与 query 明显相关，系统可以作为列表返回，但不是第一执行入口。
- `acceptable`: 用于减少无意义争议，通常是父级回落，如 `verify.invoice.finance.cn -> invoice.finance.cn`。

## 3. v1 的 l3 使用纪律
- 只有 `closure/07_namespace_v1.md` 冻结的子树可以用 `l3`
- `l3` 必须由 query/context 明确提供证据
- 若存在 `l3` ground truth，必须把对应 `l2.l1.cn` 放进 `acceptable_fqdns`

## 4. intended_confusion_types 填写规则
推荐从以下枚举中选择 1-3 个：
- `multi_intent`
- `lexical_overlap`
- `sibling_competition`
- `governance_fallback`
- `cross_domain_overlap`
- `fallback`

## 5. 工信 60% 的扩表方向
优先补这 4 桶：
- `permit.gov.cn` / `policy.gov.cn`: 许可、备案、标准、规范
- `*.compliance.security.cn` / `risk.security.cn`: 数据、账号、交易对象、风控
- `*.invoice.finance.cn` / `tax.finance.cn`: 验真、报销、开票、税务
- `meeting.productivity.cn` / `docs.productivity.cn`: 企业会议、方案整理、项目材料

## 6. Split 纪律
- 不允许把同一模板仅换同义词后同时放进 dev/test
- 同一 query 族（同场景、同主对象、同动作骨架）应固定在一个 split
- `dev` 用于阈值与词典修正，`test` 不应基于结果回写标签

正式 split 约定:
- `formal/dev`: 可见、可调
- `formal/blind_input`: 可见、不可调标签
- `formal/blind_labels`: 冻结前禁读
- `formal/challenge_input`: 可见、附录鲁棒性
- `formal/challenge_labels`: 冻结前禁读

## 6.1 family 标注要求
每条样本在进入 formal split 前，都应先归到一个 `family_id`。

一个 family 的典型特征:
- 相同主对象
- 相同主动作骨架
- 相同 primary/related 结构
- 只是做句式改写、同义词替换、口语化改写

纪律:
- 一个 `family_id` 只能属于一个 split
- blind/challenge 不允许出现 dev 的同题改写

## 6.2 泄漏黑名单
标注与算法实现时，禁止以下行为:
- 从 gold query 反抄触发词回填到词典
- 看过 blind/challenge label 后再改规则
- 为个别样本单独写 heuristic
- 用 `acceptable_fqdns` 去指导运行时排序

标注人员自检问题:
- 这条规则是否可以在不看这条样本答案的情况下存在？
- 如果去掉这条样本，这条规则是否仍然合理？

## 7. 复标检查表
人工抽检时至少确认：
- `ground_truth_fqdn` 是否能解释“为什么是 primary”
- `relevant_fqdns` 是否真的是相关而非噪声
- `acceptable_fqdns` 是否只承担回落容错
- `intended_confusion_types` 是否真的能从 query 本身解释
