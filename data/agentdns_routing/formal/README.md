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

## 2. 治理文件
- `manifest.json`
  - 数据集版本、namespace 版本说明、最小规模门槛、当前统计
- `family_ledger.csv`
  - family 台账
  - 用于 split 泄漏检查、场景桶统计、family 粒度治理
- `coverage_plan.csv`
  - 扩表配额表
  - 用于按 base_fqdn / 场景桶 / 层级目标 / 主要混淆类型补样本

## 3. 校验方式
运行：
```bash
python3 scripts/validate_formal_dataset.py
```

输出：
- `artifacts/dataset/formal_validation_report.json`
- `artifacts/dataset/formal_coverage_status.csv`

## 4. 当前纪律
- 不能把 `bootstrap_seed` 混进正式主表
- 不能读取 `blind_labels.jsonl` / `challenge_labels.jsonl` 后再回改算法并继续宣称“正式结果”
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
