# AgentDNS Routing 数据与脚手架

当前目录承载 4 类文件：
- `namespace_descriptors.jsonl`: Stage R 的命名空间节点描述，不是 agent registry。
- `evidence_lexicon.json`: 声明式证据词典，供 Stage R 做结构化证据抽取。
- `dev.jsonl` / `test.jsonl`: seed gold 数据集（当前 20 条，用于 Week 1-2 跑通链路；不是最终 300-800 条正式集）。
- `labeling_guide.md`: 标注与扩表规则。

当前 seed 集统计：
- `dev`: 12 条
- `test`: 8 条
- 工信/企业语境样本：12/20（60%）
- 启用 `l3` 的样本：10/20

运行命令：
```bash
python3 scripts/run_stage_r_snapshot.py --split dev
python3 scripts/run_stage_r_snapshot.py --split test
```

输出位置：
- `artifacts/stage_r/dev.sr_v0_20260306.jsonl`
- `artifacts/stage_r/test.sr_v0_20260306.jsonl`
