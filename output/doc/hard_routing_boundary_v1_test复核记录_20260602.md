# hard_routing_boundary_v1 500条测试集复核记录

生成日期：2026-06-02

## 1. 数据与校验结论

本轮使用新构造的 `hard_routing_boundary_v1_20260602` 作为独立 test，不改动原冻结主集合。

数据文件：

| 项目 | 路径 |
|---|---|
| 输入 | `data/agentdns_routing/formal/hard_routing_boundary_v1_input.jsonl` |
| 标签 | `data/agentdns_routing/formal/hard_routing_boundary_v1_labels.jsonl` |
| manifest | `data/agentdns_routing/formal/hard_routing_boundary_v1_manifest.json` |
| joined eval | `artifacts/dataset/hard_routing_boundary_v1_20260602/hard_routing_boundary_v1_joined.jsonl` |
| validation | `artifacts/dataset/hard_routing_boundary_v1_validation_report.json` |

校验结果：

| 项目 | 结果 |
|---|---:|
| 样本数 | 500 |
| validation ok | true |
| errors | 0 |
| warnings | 0 |
| distinct ground truth FQDN | 35 |
| distinct base FQDN | 25 |
| segment primary count | 165 |
| secondary intent count | 183 |
| high risk case count | 163 |

stress slice 分布：

| slice | n |
|---|---:|
| low_rank_gold | 80 |
| parent_child_granularity | 90 |
| primary_secondary_conflict | 90 |
| cross_domain_overlap | 90 |
| high_risk_governance_tone | 80 |
| near_duplicate_descriptors | 70 |

结论：当前没有发现数据格式、标签字段或覆盖统计层面的硬错误。后续结果不理想时，不能直接归因为“数据坏了”；更准确的判断是测试集和对比协议是否支撑论文想证明的结论。

## 2. Stage R 召回与候选质量

Stage R 使用 `sr_clean_v2_20260314_related2`，top-k=25。

| 指标 | 数值 |
|---|---:|
| PrimaryRecall@5 | 0.7740 |
| PrimaryRecall@10 | 0.9900 |
| RelatedCoverage@5 | 0.9139 |
| RelatedCoverage@10 | 1.0000 |
| UnionCoverage@10 | 0.9900 |
| OraclePrimary@10 | 1.0000 |
| MRR | 0.6091 |
| L1Acc_top1cand | 0.7380 |
| L2Acc_top1cand | 0.4735 |
| L3PrimaryRecall@10 | 0.9583 |

Stage R top1 作为直接路由时：

| 方法 | PrimaryAcc@1 | AcceptablePrimary@1 | correct |
|---|---:|---:|---:|
| Stage R top1 | 0.4640 | 0.4820 | 232/500 |

结论：gold 基本能被召回到 top10，说明主要瓶颈不是候选召回缺失，而是候选排序、父子粒度选择和最终判别。

## 3. 主实验与基线结果

模型口径：DeepSeek `deepseek-chat`。Stage B 复用 Stage A LLM trace；related provider 为 deterministic。

| 方法 | PrimaryAcc@1 | AcceptablePrimary@1 | correct | RelatedRecall | RelatedPrecision | changed | fixed | regressed |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| BM25 top1 | 0.5060 | 0.5360 | 253/500 | - | - | - | - | - |
| Stage A clean | 0.3360 | 0.4320 | 168/500 | 0.0787 | 0.0700 | - | - | - |
| Stage A LLM | 0.5340 | 0.5900 | 267/500 | 0.2622 | 0.1675 | - | - | - |
| Stage B single | 0.6300 | 0.6860 | 315/500 | 0.2547 | 0.1823 | 50 | 48 | 0 |
| Stage B homogeneous | 0.6300 | 0.6860 | 315/500 | 0.2547 | 0.1823 | 50 | 48 | 0 |
| Stage B heterogeneous | 0.6220 | 0.6780 | 311/500 | 0.2584 | 0.1830 | 46 | 44 | 0 |
| Gate replay responsibility_only | 0.6240 | 0.6800 | 312/500 | - | - | 47 | 45 | 0 |
| Gate replay conservative | 0.6760 | 0.6800 | 338/500 | - | - | 75 | 72 | 1 |
| Gate replay aggressive / expanded | 0.7220 | 0.7260 | 361/500 | - | - | 105 | 95 | 1 |
| Flat LLM top10 | 0.8440 | 0.8520 | 422/500 | - | - | - | - | - |
| Flat LLM self-consistency | 0.8480 | 0.8560 | 424/500 | - | - | - | - | - |

主要观察：

1. Stage B 对 Stage A LLM 有明确增益：默认 hetero 从 0.5340 提升到 0.6220；expanded gate replay 可到 0.7220。
2. Stage B 的修复是净正向的：heterogeneous 为 fixed 44、regressed 0；expanded replay 为 fixed 95、regressed 1。
3. single 与 homogeneous 在 primary 决策上完全相同，整批都是 0.6300；trace 差异检查显示 `final_primary_fqdn` 0 条不同，仅 `final_related_fqdns` 2 条不同。因此这两个消融不能作为强区分实验解释。
4. Flat LLM top10 明显强于当前多阶段系统，说明这版 hard set 不能支撑“多智能体协作优于一步式强 LLM 候选选择”的叙事。

## 4. 未完成或不可用项

embedding baseline 当前不可用，原因是本地 `.venv_embed` 和 `.venv_baselines` 环境中 `sentence_transformers` import 均阻塞。

复核命令：

```bash
perl -e 'alarm 20; exec @ARGV' .venv_embed/bin/python -c "import time; print('before import', flush=True); import sentence_transformers; print('after import', sentence_transformers.__version__, flush=True)"
```

输出只到：

```text
before import
... NotOpenSSLWarning ...
```

20 秒后进程被 timeout 终止，没有进入 `after import`。该问题是依赖/运行环境问题，不是 hard 500 数据问题。若必须补 embedding baseline，建议新建干净 venv 或改用不依赖 `sentence_transformers` 的轻量 embedding 实现后再跑。

补充复核：`.venv_baselines` 在同一 import 位置同样 20 秒超时；设置 `TRANSFORMERS_NO_TF=1 TRANSFORMERS_NO_FLAX=1 USE_TF=0 USE_FLAX=0` 后，45 秒内仍未完成 import。

另尝试使用系统 `python3` 3.13.5 创建干净临时 venv，`python3 -m venv .venv_st_baseline_313` 本身超过 4 分钟未完成，目录仅生成约 8KB；该临时目录已清理。因此本轮没有继续现场修复 embedding baseline 环境。

## 5. 对论文与结项展示的建议

这版 hard 500 可以用于说明“边界压力条件下，Stage B 职责化复核能对 Stage A 产生净修复”，但不适合用于证明“多智能体协作全面超过一步式强 LLM baseline”。

更稳妥的论文口径：

1. 主张多智能体协作提升结构化语义路由链路的可控性与修复能力，而不是声称超过所有 LLM baseline。
2. 使用 expanded gate 作为 train 调优后的 test replay 结果时，需要明确它是 gate replay，不是重新发起 LLM 的新运行。
3. Flat LLM baseline 必须保留，因为它是当前最强对比；如果要继续挑战它，应补充 shuffle top10、去排序、去描述或受限候选信息等公平性实验。
4. single/homogeneous 与 heterogeneous 的消融目前不够漂亮：single/homogeneous 几乎等价，heterogeneous 默认还略低。论文中更适合强调 Stage B 相对 Stage A 的净修复，而不是强调三种协作模式之间的显著差异。

## 6. 当前结论

没有发现足以停止实验的数据质量问题；已发现的是实验结论风险：hard 500 对 flat LLM 仍然不够 hard，现有结果不支持“协作系统超过强一步式 LLM”的主叙事。

如果后续要继续增强论文说服力，下一步优先级是：

1. 补跑 Flat LLM shuffle top10，验证排序泄露影响。
2. 若 shuffle 后 Flat LLM 仍高，调整论文叙事，不再以超越 Flat LLM 为核心。
3. 若需要完整 baseline 表，再修复 embedding 环境后补 embedding 检索 baseline。
