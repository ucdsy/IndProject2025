# 实验执行日志

| 日期 | 运行 ID | 配置 | 关键结果 | 备注 |
|---|---|---|---|---|
| 2026-03-06 | SR-BOOT-01 | `Stage R bootstrap`，25 个 namespace descriptors，seed gold: dev=12/test=8，`top_k=10`，`stage_r_version=sr_v0_20260306` | dev: `PrimaryRecall@10=1.00`，`RelatedCoverage@10=1.00`；test: `PrimaryRecall@10=1.00`，`RelatedCoverage@10=1.00` | 已生成 `artifacts/stage_r/*.jsonl`，供后续 Stage A/B 共用 candidate snapshot |
| 2026-03-__ | R01 | baseline: single-agent |  |  |
| 2026-03-__ | R02 | baseline: vote |  |  |
| 2026-03-__ | R03 | baseline: debate |  |  |
| 2026-03-__ | R04 | ours: feedback-consensus |  |  |
| 2026-03-__ | R05 | ours ablation: -heterogeneity |  |  |
| 2026-03-__ | R06 | ours ablation: -feedback |  |  |
| 2026-03-__ | R07 | ours ablation: -trust-id |  |  |

## 运行元数据清单
每次跑实验至少记录这些字段，避免最后写报告/论文时“数据找不到”：
- code/version: git commit, tag
- model: model_name, provider, quantization (if any)
- prompt: template version, system prompt hash
- retrieval: corpus version, top-k, rerank config
- agents: number of agents, role set, heterogeneity config
- consensus: policy name, scoring function, rounds
- trust: logging schema version, hash-chain enabled (Y/N)
- dataset: dataset name/version, split, #samples
- randomness: seed, temperature, top_p
- cost: tokens, latency, $ cost (if API)

## 主张-证据对照表
| 主张 | 证据（实验/表格） | 状态 |
|---|---|---|
| 协作机制优于单智能体 | R01 vs R04 的主指标对比表 | TODO |
| 反馈驱动优于无反馈 | R04 vs R06 | TODO |
| 异质性有贡献 | R04 vs R05 | TODO |
| 可信标识提升审计能力且成本可控 | R04 vs R07 + 轨迹完整率/篡改检测结果 | TODO |
