# formal 正式数据集说明

本目录用于承载正式实验数据，而不是早期 `bootstrap_seed`。

## 1. split 文件
- `dev.jsonl`
  - 带完整标签
  - 唯一允许用于规则、阈值、特征修正
- `blind_input.jsonl`
  - 只含输入字段
  - clean `Stage R/A` 开发期间可读
- `blind_labels.jsonl`
  - 对应 blind 的标签文件
  - 冻结前禁读
- `challenge_input.jsonl`
  - 附录鲁棒性输入集
- `challenge_labels.jsonl`
  - 对应 challenge 的标签文件
  - 冻结前禁读
- `holdout2_input.jsonl`
  - 新的 unrevealed 正式验证输入集
  - 仅用于 `formal/dev`、`formal/blind`、`formal/challenge` 已揭盲后的后续版本验证
- `holdout2_labels.jsonl`
  - 对应 holdout2 的标签文件
  - 算法版本冻结前禁读，只允许单次 join
- `holdout3_input.jsonl`
  - 新的 400 条 fresh validation 输入集
  - 仅用于 `dev / blind / challenge / holdout2` 已揭盲后的后续正式验证
- `holdout3_labels.jsonl`
  - 对应 holdout3 的标签文件
  - 算法版本冻结前禁读，只允许单次 join

## 2. 治理文件
- `manifest.json`
  - 数据集版本、namespace 版本说明、最小规模门槛、当前统计
- `holdout2_manifest.json`
  - `holdout2` 的版本、目标配额、当前统计与揭盲协议
- `holdout3_manifest.json`
  - `holdout3` 的版本、三层分布目标、当前统计与揭盲协议
- `family_ledger.csv`
  - family 台账
  - 用于 split 泄漏检查、场景桶统计、family 粒度治理
- `coverage_plan.csv`
  - 扩表配额表
  - 用于按 base_fqdn / 场景桶 / 层级目标 / 主要混淆类型补样本
- `holdout2_coverage_status.csv`
  - `holdout2` 的 base coverage 与 bucket 覆盖状态
- `holdout3_coverage_status.csv`
  - `holdout3` 的 base coverage 与三层分布覆盖状态
- `holdout3_skeleton_audit.csv`
  - `holdout3` 的 skeleton 审核结果与近邻旧 family 审计记录

## 3. 校验方式
运行：
```bash
python3 scripts/validate_formal_dataset.py
python3 scripts/validate_holdout2_dataset.py
python3 scripts/validate_holdout3_dataset.py
```

输出：
- `artifacts/dataset/formal_validation_report.json`
- `artifacts/dataset/formal_coverage_status.csv`
- `artifacts/dataset/holdout2_validation_report.json`
- `artifacts/dataset/holdout3_validation_report.json`

## 4. 当前纪律
- 不能把 `bootstrap_seed` 混进正式主表
- 不能读取 `blind_labels.jsonl` / `challenge_labels.jsonl` 后再回改算法并继续宣称“正式结果”
- 不能读取 `holdout2_labels.jsonl` 后继续调参还宣称“正式 holdout 结论”
- 不能读取 `holdout3_labels.jsonl` 后继续调参还宣称“正式 fresh validation 结论”
- 如揭盲后继续调参，必须升版本

## 5. 当前状态（2026-03-06）
- `formal_v1_1_20260306` 已达到第一版可稳定评测门槛：
  - `dev=50`
  - `blind=35`
  - `challenge=24`
  - 总量 `109`
- 当前统计：
  - 工信/企业语境占比 `0.5780`
  - `l3` 占比 `0.2018`
  - `multi_intent` 占比 `0.4954`
  - `ground-truth base coverage = 25/25`
  - `blind base coverage = 25/25`
  - `validator = ok=true, warnings=[]`
- 最新校验结果见：
  - `artifacts/dataset/formal_validation_report.json`
  - `artifacts/dataset/formal_coverage_status.csv`

## 6. `holdout2` 状态（2026-03-22）
- `holdout2_v0_20260322` 已完成构建并保持 unrevealed：
  - `holdout2=54`
  - `distinct_base_fqdn=25`
  - `l3_ratio=0.3148`
  - `multi_intent_ratio=0.3704`
  - bucket 分布 `hierarchy/cross-domain/multi-intent/high-risk/fast-path/long-tail = 12/10/10/8/8/6`
- 当前约束：
  - family-disjoint 于 `formal/dev`、`formal/blind`、`formal/challenge`
  - query 文本与现有 formal split 无完全重复
  - `validator = ok=true, warnings=[]`
- 最新校验结果见：
  - `artifacts/dataset/holdout2_validation_report.json`

## 7. `holdout3` 状态（2026-03-30）
- `holdout3_v0_20260330` 已完成构建并保持 unrevealed：
  - `holdout3=400`
  - `distinct_base_fqdn=25`
  - `l3_ratio=0.3400`
  - `multi_intent_ratio=0.3400`
  - `eval_bucket=80/80/80/80/80`
  - `intent_form=80/80/80/80/80`
- 当前约束：
  - family-disjoint 于 `formal/dev`、`formal/blind`、`formal/challenge`、`formal/holdout2`
  - query 文本与既有 formal split 无完全重复
  - `skeleton_overlap_flag_count=0`
  - `validator = ok=true, warnings=[]`
- 最新校验结果见：
  - `artifacts/dataset/holdout3_validation_report.json`
