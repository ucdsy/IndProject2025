# AgentDNS Routing 数据与脚手架

当前目录承载 4 类文件：
- `namespace_descriptors.jsonl`: Stage R 的命名空间节点描述，不是 agent registry。
- `evidence_lexicon.json`: bootstrap 阶段使用的声明式证据词典；当前已降级，不直接进入 clean `Stage R`。
- `dev.jsonl` / `test.jsonl`: seed gold 数据集（当前 20 条，用于 Week 1-2 跑通链路；不是最终 300-800 条正式集）。
- `labeling_guide.md`: 标注与扩表规则。
- `formal/*`: 正式数据集骨架（后续 clean `Stage R/A` 只对这里的 split 生效）。

当前状态说明:
- `dev/test` 现在只是 `bootstrap_seed`，主要用于打通 schema、trace、resolver 和评测脚手架。
- 这 20 条 seed 样本不能作为正式实验集，也不能据此证明 Stage R/A 方法有效。
- `artifacts/dataset/knowledge_source_audit.md` 已完成一轮知识源泄漏审计。
- 当前冻结结论:
  - `namespace/canonical contract` 可保留
  - `namespace_descriptors.jsonl` 中与节点命名直接绑定的 aliases 可保留
  - descriptor `examples` 不进入 clean `Stage R` 主索引
  - 当前整份 `evidence_lexicon.json` 仅保留作 bootstrap 资源，不直接进入 clean `Stage R`
- 接下来的正确顺序是:
  1. 冻结正式 gold schema
  2. 构建 blind split / challenge split
  3. 冻结 descriptor 与词典的独立来源
  4. 在此基础上重做 clean Stage R / Stage A

当前 seed 集统计：
- `dev`: 12 条
- `test`: 8 条
- 工信/企业语境样本：12/20（60%）
- 启用 `l3` 的样本：10/20

正式 split 骨架:
- `formal/dev.jsonl`
- `formal/blind_input.jsonl`
- `formal/blind_labels.jsonl`
- `formal/challenge_input.jsonl`
- `formal/challenge_labels.jsonl`
- `formal/manifest.json`
- `formal/family_ledger.csv`
- `formal/coverage_plan.csv`
- `formal/README.md`

当前 formal seed（第一批）:
- `formal/dev`: 6 条
- `formal/blind_input + blind_labels`: 4 条
- `formal/challenge_input + challenge_labels`: 4 条
- 总计: 14 条
- 工信/企业语境占比: 9/14（64.29%）

机器校验：
```bash
python3 scripts/validate_formal_dataset.py
```

校验输出：
- `artifacts/dataset/formal_validation_report.json`
- `artifacts/dataset/formal_coverage_status.csv`

运行命令：
```bash
python3 scripts/run_stage_r_snapshot.py --split dev
python3 scripts/run_stage_r_snapshot.py --split test
```

输出位置：
- `artifacts/stage_r/dev.sr_v0_20260306.jsonl`
- `artifacts/stage_r/test.sr_v0_20260306.jsonl`
