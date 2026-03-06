# 知识源泄漏审计

## 1. 审计范围
- formal 输入 query 总数: `105`
- namespace descriptor 数量: `25`
- descriptor 短语总量: `185`
- lexicon 短语总量: `136`

## 2. 结论
- `namespace/canonical contract` 可以保留。
- `descriptor examples` 已出现与 formal query 的直接重叠，不应进入 clean `Stage R` 主索引。
- 当前 `evidence_lexicon.json` 中存在一批不在 descriptor/contract 内、但又直接命中 formal query 的短语；它不能直接进入 clean `Stage R`。
- descriptor 中部分短且高频的 alias/segment alias 不构成直接泄漏，但只能做低权重 sidecar，不能作为主召回锚点。

## 3. 核心统计
- descriptor alias 命中数: `65`
- descriptor example 命中数: `1`
- segment alias 命中数: `38`
- lexicon 命中数: `216`
- lexicon 中“不在 descriptor 内但命中 formal query”的条目数: `26`

## 4. descriptor example 直接重叠
- `clinic.health.cn`: `去哪里挂号`，命中 `1` 条，样本示例 `formal_dev_000048`

## 5. 需降权审查的短高频 alias
- `risk.security.cn`: `风险`，命中 `11` 条，样本示例 `formal_dev_000007, formal_dev_000009, formal_dev_000011, formal_dev_000013, formal_dev_000014`
- `compliance.security.cn`: `合规`，命中 `9` 条，样本示例 `formal_dev_000007, formal_dev_000008, formal_dev_000009, formal_dev_000010, formal_dev_000011`
- `invoice.finance.cn`: `入账`，命中 `8` 条，样本示例 `formal_dev_000018, formal_dev_000020, formal_blind_000011, formal_blind_000013, formal_blind_000014`
- `invoice.finance.cn`: `票据`，命中 `8` 条，样本示例 `formal_dev_000015, formal_dev_000016, formal_dev_000017, formal_dev_000018, formal_blind_000012`
- `tax.finance.cn`: `税务`，命中 `8` 条，样本示例 `formal_dev_000015, formal_dev_000017, formal_dev_000019, formal_dev_000020, formal_dev_000021`
- `meeting.productivity.cn`: `安排`，命中 `7` 条，样本示例 `formal_dev_000024, formal_dev_000027, formal_dev_000042, formal_dev_000043, formal_dev_000044`
- `coupon.commerce.cn`: `优惠`，命中 `6` 条，样本示例 `formal_dev_000032, formal_dev_000034, formal_dev_000035, formal_dev_000041, formal_blind_000021`
- `hotel.travel.cn`: `成都`，命中 `6` 条，样本示例 `formal_dev_000038, formal_dev_000039, formal_blind_000024, formal_blind_000025, formal_blind_000027`

## 6. 必须移出 clean Stage R 的 lexicon 条目（节选）
- `industry_context/enterprise_service`: `企业`，命中 `20` 条，样本示例 `formal_dev_000001, formal_dev_000003, formal_dev_000005, formal_dev_000008, formal_dev_000012`
- `primary_action/check`: `看看`，命中 `20` 条，样本示例 `formal_dev_000004, formal_dev_000006, formal_dev_000011, formal_dev_000013, formal_dev_000032`
- `industry_context/manufacturing`: `设备`，命中 `19` 条，样本示例 `formal_dev_000006, formal_dev_000007, formal_dev_000010, formal_dev_000011, formal_dev_000013`
- `industry_context/enterprise_service`: `客户`，命中 `17` 条，样本示例 `formal_dev_000003, formal_dev_000008, formal_dev_000012, formal_dev_000018, formal_dev_000020`
- `industry_context/enterprise_service`: `平台`，命中 `9` 条，样本示例 `formal_dev_000002, formal_dev_000004, formal_dev_000007, formal_dev_000027, formal_dev_000029`
- `primary_action/check`: `检查`，命中 `8` 条，样本示例 `formal_dev_000007, formal_dev_000012, formal_dev_000014, formal_blind_000005, formal_blind_000010`
- `risk_flags/money_related`: `付款`，命中 `7` 条，样本示例 `formal_dev_000009, formal_dev_000014, formal_dev_000018, formal_blind_000006, formal_blind_000013`
- `secondary_intents/docs.productivity.cn`: `提纲`，命中 `6` 条，样本示例 `formal_dev_000024, formal_dev_000028, formal_dev_000030, formal_blind_000018, formal_blind_000019`
- `secondary_intents/docs.productivity.cn`: `材料`，命中 `6` 条，样本示例 `formal_dev_000024, formal_dev_000029, formal_dev_000031, formal_blind_000018, formal_blind_000020`
- `industry_context/enterprise_service`: `系统`，命中 `4` 条，样本示例 `formal_dev_000013, formal_dev_000049, formal_blind_000009, formal_challenge_000005`
- `primary_action/verify`: `核验`，命中 `4` 条，样本示例 `formal_dev_000009, formal_blind_000006, formal_blind_000007, formal_challenge_000003`
- `industry_context/manufacturing`: `工业互联网`，命中 `3` 条，样本示例 `formal_dev_000002, formal_dev_000004, formal_blind_000001`

## 7. clean Stage R 输入边界（冻结建议）
- 保留: namespace/canonical contract、descriptor 中与节点命名直接绑定的 aliases、segment canonical 规则、fallback chain。
- 低权重 sidecar: descriptor 中短且泛化强的 alias，例如 `安排`、`日志`、`要点`、`北京/成都/杭州` 之外的通用短词。
- 排除: descriptor examples、当前整份 `evidence_lexicon.json`。
- 若后续需要恢复 lexicon，必须从独立术语表重新生成，并重新跑本审计脚本。
