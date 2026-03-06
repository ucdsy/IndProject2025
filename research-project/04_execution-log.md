# 实验执行日志

| 日期 | 运行 ID | 配置 | 关键结果 | 备注 |
|---|---|---|---|---|
| 2026-03-06 | SR-BOOT-01 | `Stage R bootstrap`，25 个 namespace descriptors，seed gold: dev=12/test=8，`top_k=10`，`stage_r_version=sr_v0_20260306` | dev: `PrimaryRecall@10=1.00`，`RelatedCoverage@10=1.00`；test: `PrimaryRecall@10=1.00`，`RelatedCoverage@10=1.00` | 已生成 `artifacts/stage_r/*.jsonl`，供后续 Stage A/B 共用 candidate snapshot |
| 2026-03-06 | SA-BOOT-01 | `StageA-only`，canonical resolver + deterministic scoring，`temperature=1.0`，`confidence_temperature=0.25`，`tau=0.30`，`delta=0.08`，`tau_rel=0.12` | dev: `PrimaryAcc@1=0.9167`，`RelatedRecall=0.90`，`escalation_rate=0.5833`；test: `PrimaryAcc@1=0.75`，`RelatedRecall=0.5714`，`escalation_rate=0.375` | 当前已降级为 `bootstrap` 结果，只保留作脚手架自检，不再作为正式主表依据 |
| 2026-03-06 | DATA-PROTOCOL-01 | 冻结 `formal` split 协议；新增 `formal/dev`、`formal/blind_input`、`formal/blind_labels`、`formal/challenge_input`、`formal/challenge_labels`；写入 freeze protocol 与泄漏黑名单 | 正式实验顺序改为“先数据协议与 holdout，再重做 clean Stage R/A” | `bootstrap_seed` 与 formal split 边界已写入 `closure/08`、`closure/09`、`data/agentdns_routing/README.md`；后续不再沿旧 `Stage R/A` 继续补功能 |
| 2026-03-06 | DATA-BUILD-01 | 首批 `formal` 样本入库；`family_id` 已启用；`dev=6`、`blind=4`、`challenge=4` | family 无跨 split；所有 gold fqdn 均在 current namespace catalog 中存在；工信/企业语境占比 `9/14=64.29%` | 这是正式数据集的第一批 seed，不是最终规模；后续先继续扩表，再开始 clean `Stage R` |
| 2026-03-06 | DATA-VALIDATE-01 | 新增 split 级 schema、统一 validator、family ledger、coverage plan；generic gold schema 已要求 `family_id` | 机器校验通过，无结构性错误；当前警告: `dev=6<50`、`blind=4<30`、`challenge=4<20`、`miit_ratio=0.7143`、`l3_ratio=0.5714`、`multi_intent_ratio=0.9286`、`gt_base_coverage=10/25` | 已生成 `artifacts/dataset/formal_validation_report.json` 与 `formal_coverage_status.csv`；后续扩表按 coverage plan 执行 |
| 2026-03-06 | DATA-BUILD-02 | 按 `coverage_plan.csv` 重建 `formal` 数据；统一中文 query 生成逻辑为“场景句 + 主请求句 + 可选补充句”；新增 `scripts/rebuild_formal_dataset.py` | `dev=50`、`blind=31`、`challenge=24`、总量 `105`；`miit_ratio=0.6000`、`l3_ratio=0.2095`、`multi_intent_ratio=0.5143`；`gt_base_coverage=25/25` | 正式数据资产已达到第一版可稳定评测门槛；validator 无错误无警告；当前 `Stage R/A` 仍保持 bootstrap 降级，不得据此宣称正式结果 |
| 2026-03-06 | DATA-AUDIT-01 | 对 `namespace_descriptors.jsonl`、`evidence_lexicon.json` 与 `formal` 输入 query 做知识源泄漏审计；新增 `scripts/audit_knowledge_sources.py` | `descriptor example` 直接重叠 `1` 条；`lexicon` 命中 `216` 条，其中“不在 descriptor 内但命中 formal query”共 `26` 条 | 冻结结论：descriptor `examples` 不进入 clean `Stage R` 主索引；当前整份 `evidence_lexicon.json` 降级为 bootstrap 资源；详见 `artifacts/dataset/knowledge_source_audit.md` |
| 2026-03-06 | DATA-VALIDATE-02 | 修复 `manifest.json` 的工信占比回写；validator 新增 manifest 回算一致性、blind base coverage、split 模板前缀偏置检查 | validator 现为 `ok=true`，但保留 4 条 warning：blind base coverage 仅 `21/25`；`dev/blind/challenge` 均存在明显模板前缀偏置 | 现在不能再说“validator 绿灯就代表 manifest 口径正确”；也不能说“blind 主表覆盖了全部 taxonomy”或“query 已具备充分自然语言多样性” |
| 2026-03-06 | R-CLEAN-01 | clean `Stage R`（descriptor-only lexical+metadata recall）；不读取 descriptor `examples`，不使用 `evidence_lexicon.json`；新增 `src/agentdns_routing/stage_r_clean.py` 与 `scripts/run_stage_r_clean_snapshot.py` | `formal/dev` 上 `PrimaryRecall@10=0.9600`、`RelatedCoverage@10=0.7742`；blind/challenge 仅生成输入 snapshot，不揭盲 | 当前 miss 主要暴露的是 descriptor 覆盖不足而非 query 级特判缺失：`docs.productivity.cn` 对“材料”类表达召回弱，`nutrition.health.cn` 对“低油低糖”类表达缺别名；下一步应补独立来源的 descriptor 词汇覆盖，而不是回到 bootstrap lexicon |
| 2026-03-06 | DATA-BUILD-03 | 针对 formal v1 剩余风险做最小修复：`coverage_plan.csv` 为 blind 补齐 `invest/fitness/clinic/tutoring`；`scripts/rebuild_formal_dataset.py` 打散 split 专属 query 起始模板，并修复 `itinerary/hotel` 的 `scene/context` 与 l3 segment 对齐 | `dev=50`、`blind=35`、`challenge=24`、总量 `109`；`miit_ratio=0.5780`、`l3_ratio=0.2018`、`multi_intent_ratio=0.4954`；`gt_base_coverage=25/25`；`blind_base_coverage=25/25` | `relevant_fqdns` 与 `ground_truth_fqdn` 的重合样本已清零；dataset version 升为 `formal_v1_1_20260306` |
| 2026-03-06 | DATA-VALIDATE-03 | 在 patch 后重跑 formal validator；校验 split 级 schema、family ledger、manifest 回算一致性、blind coverage、template bias 与 travel l3 城市对齐 | `ok=true`，`warnings=[]`；`dev` 前缀最大占比 `0.18`，`blind` 最大占比 `0.1714`，`challenge` 最大占比 `0.3333` | 现在可以再说“formal 数据资产已完成第一版构建，并已收掉 blind coverage / 模板偏置这两个 blocker” |
| 2026-03-06 | R-CLEAN-02 | 基于 `formal_v1_1_20260306` 重跑 clean `Stage R` snapshot；继续坚持 descriptor-only lexical+metadata recall，不读取 descriptor `examples`，不使用 `evidence_lexicon.json` | `formal/dev` 上 `PrimaryRecall@10=0.9800`、`RelatedCoverage@10=0.6897`；blind/challenge snapshot 已按新数据重导出 | `R-CLEAN-01` 对应旧版 formal 数据；后续主表与调参一律引用 patch 后 snapshot 与 summary |
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
