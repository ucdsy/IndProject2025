# 知识源泄漏审计

## 1. 审计范围
- formal 输入 query 总数: `109`
- namespace descriptor 数量: `25`
- descriptor 短语总量: `185`
- lexicon 短语总量: `0`

## 2. 结论
- `namespace/canonical contract` 可以保留。
- `descriptor examples` 已出现与 formal query 的直接重叠，不应进入 clean `Stage R` 主索引。
- 旧 bootstrap 词典已从主干清理；如果未来重新引入词典，必须来自独立术语表并重跑本审计。
- descriptor 中部分短且高频的 alias/segment alias 不构成直接泄漏，但只能做低权重 sidecar，不能作为主召回锚点。

## 3. 核心统计
- descriptor alias 命中数: `64`
- descriptor example 命中数: `1`
- segment alias 命中数: `33`
- lexicon 命中数: `0`
- lexicon 中“不在 descriptor 内但命中 formal query”的条目数: `0`

## 4. descriptor example 直接重叠
- `tutoring.education.cn`: `找个导师`，命中 `1` 条，样本示例 `formal_blind_000035`

## 5. 需降权审查的短高频 alias
- `risk.security.cn`: `风险`，命中 `14` 条，样本示例 `formal_dev_000007, formal_dev_000009, formal_dev_000011, formal_dev_000013, formal_dev_000014`
- `compliance.security.cn`: `合规`，命中 `11` 条，样本示例 `formal_dev_000007, formal_dev_000008, formal_dev_000009, formal_dev_000010, formal_dev_000011`
- `tax.finance.cn`: `税务`，命中 `10` 条，样本示例 `formal_dev_000015, formal_dev_000017, formal_dev_000019, formal_dev_000020, formal_dev_000021`
- `invoice.finance.cn`: `票据`，命中 `9` 条，样本示例 `formal_dev_000015, formal_dev_000016, formal_dev_000017, formal_dev_000018, formal_blind_000011`
- `coupon.commerce.cn`: `优惠`，命中 `7` 条，样本示例 `formal_dev_000032, formal_dev_000034, formal_dev_000035, formal_dev_000041, formal_blind_000022`
- `meeting.productivity.cn`: `安排`，命中 `7` 条，样本示例 `formal_dev_000024, formal_dev_000025, formal_dev_000026, formal_dev_000027, formal_dev_000036`
- `hotel.travel.cn`: `成都`，命中 `6` 条，样本示例 `formal_dev_000038, formal_dev_000039, formal_blind_000025, formal_blind_000026, formal_blind_000028`
- `invoice.finance.cn`: `入账`，命中 `6` 条，样本示例 `formal_dev_000018, formal_dev_000020, formal_blind_000014, formal_challenge_000007, formal_challenge_000008`

## 6. 必须移出 clean Stage R 的 lexicon 条目（节选）
- 当前仓库已无 bootstrap 词典文件，本节保留作审计占位。

## 7. clean Stage R 输入边界（冻结建议）
- 保留: namespace/canonical contract、descriptor 中与节点命名直接绑定的 aliases、segment canonical 规则、fallback chain。
- 低权重 sidecar: descriptor 中短且泛化强的 alias，例如 `安排`、`日志`、`要点`、`北京/成都/杭州` 之外的通用短词。
- 排除: descriptor examples、任何直接由 gold query 反推出来的 bootstrap 词典。
- 若后续需要恢复词典，必须从独立术语表重新生成，并重新跑本审计脚本。
