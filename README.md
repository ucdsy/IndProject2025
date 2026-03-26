# IndProj04（2026-04 结项）工作区索引

> 目标: 按任务书形成可验收结项包，并把当前原型、实验和材料沉淀成可复用的论文/专利素材。

## 1. 现在先看哪些
- 当前主线与状态入口:
  - `closure/README.md`
  - `research-project/README.md`
- 当前最关键的状态文档:
  - `closure/19_stage_a_blind_error_analysis.md`
  - `closure/20_stage_b_bootstrap_plan.md`
  - `closure/24_stage_a_uncertainty_and_stage_b_packet_v2_design.md`
  - `closure/25_stage_c_agentdnsdemo_integration_plan.md`
- 结项交付与讲法:
  - `closure/01_deliverables_checklist.md`
  - `closure/02_taskbook_mapping.md`
  - `closure/06_review_ppt_outline.md`

## 2. 当前版本线（2026-03-24）
- `Stage R`
  - `sr_clean_v2_20260314_related2`
- `Stage A clean`
  - `sa_clean_v2_20260314`
- `Stage A llm`
  - `sa_llm_v2_20260323_uncertainty`
- `Stage B`
  - `stage_b_v1_20260323_packetv2`
- `Stage C`
  - 尚未开始

## 3. 当前主结果（review packet v2）

- 当前 `Stage A / Stage B` revealed 对照的主引用目录唯一以 `artifacts/routing_ab/review_packetv2_20260323/` 为准。
- 当前 `main` 代码中 `Stage B` 的默认 runtime 参数已包含后续敏感性调整（例如更高 `llm_max_tokens` 与角色温度）。
- 这些 runtime knob 变动**不自动覆盖**本节主表；若无特别说明，对外主结果仍以 `review_packetv2_20260323` 为 canonical frozen result，后续 runtime 变体只记入 `artifacts/stage_b/ablations_20260323/`。

| split | `A_clean` | `A_clean -> B` | `A_llm_v2` | `A_llm_v2 -> B` |
|---|---:|---:|---:|---:|
| dev `PrimaryAcc@1` | `1.0000` | `1.0000` | `0.9600` | `0.9600` |
| blind `PrimaryAcc@1` | `0.8286` | `0.8571` | `0.9143` | `0.9143` |
| challenge `PrimaryAcc@1` | `0.2917` | `0.4167` | `0.6250` | `0.6667` |
| holdout2 `PrimaryAcc@1` | `0.7407` | `0.7407` | `0.8889` | `0.9074` |

当前可直接说的结论:
- `Stage R` 已经是稳定主召回基线
- `Stage A clean` 仍是强 fast-path 基线，但 fresh `holdout2` 上不够强
- `Stage A llm v2` 已成为当前更强的主裁决线
- `Stage B packetv2` 已完成 `dev / blind / challenge / holdout2` 评测
  - 对 `A_clean`：在 blind、challenge 上有提升；在 dev、holdout2 上无增益
  - 对 `A_llm_v2`：在 challenge、holdout2 上有提升；在 dev、blind 上基本持平
- 因此，`Stage B` 现在可以说“有选择性的正向增益”，但还不能说“已经稳定压过上游所有线路”

## 4. 执行入口（当前可运行）
- 数据与协议:
  - `data/agentdns_routing/formal/README.md`
  - `data/agentdns_routing/formal/manifest.json`
  - `data/agentdns_routing/formal/holdout2_manifest.json`
  - `data/agentdns_routing/labeling_guide.md`
- `Stage R`:
  - `src/agentdns_routing/stage_r_clean.py`
  - `scripts/run_stage_r_clean_snapshot.py`
  - `artifacts/stage_r_clean/dev.sr_clean_v2_20260314_related2.summary.json`
  - `artifacts/stage_r_clean/blind_revealed_20260315_once.sr_clean_v2_20260314_related2.summary.json`
  - `artifacts/stage_r_clean/challenge.sr_clean_v2_20260314_related2.summary.json`
  - `artifacts/stage_r_clean/holdout2_revealed_20260322/holdout2_joined_20260322_once.sr_clean_v2_20260314_related2.gate_summary.json`
- `Stage A clean`:
  - `src/agentdns_routing/stage_a_clean.py`
  - `scripts/run_stage_a_clean.py`
- `Stage A llm`:
  - `src/agentdns_routing/stage_a_llm.py`
  - `scripts/run_stage_a_llm.py`
- `Stage B`:
  - `src/agentdns_routing/stage_b_consensus.py`
  - `src/agentdns_routing/stage_b_eval.py`
  - `scripts/run_stage_b.py`
  - `scripts/run_routing_ab_experiment.py`
- 当前主对照产物目录:
  - `artifacts/routing_ab/review_packetv2_20260323/`
  - `artifacts/stage_b/ablations_20260323/`

## 5. 当前状态判断
- 已完成:
  - canonical `routing_fqdn` contract
  - formal `dev / blind / challenge` 协议
  - `holdout2` 新增与校验
  - clean `Stage R`
  - clean `Stage A`
  - `Stage A llm v2`
  - `Stage B packetv2`
  - `dev / blind / challenge / holdout2` 的一轮 revealed 对照
- 已有但仍属 exploratory / review 结论:
  - `Stage B` 的净增益判断
  - `Stage A llm v2` 与 `Stage B` 的正式主线地位
- 尚未完成:
  - 统一 frozen-lineage 的 paper-ready 主结果表
  - `Stage B` 的系统性 ablation
  - `Stage C`

## 6. 当前边界
- `Stage A` 与 `Stage B` 都仍然坚持 `candidate-internal`
- `Stage B` 不允许掩盖 `Stage R miss`
- `holdout2` 已揭盲；后续若继续用其调参，只能算 `exploratory`
- 现在不应再把仓库描述成“只有 contract/schema/脚手架”

## 7. 历史与当前的关系
- `closure/15-20` 中部分文档起点是 2026-03-14 到 2026-03-17 的冻结/立项判断
- 当前 live repo 以:
  - `closure/20_stage_b_bootstrap_plan.md`
  - `closure/24_stage_a_uncertainty_and_stage_b_packet_v2_design.md`
  - `research-project/04_execution-log.md`
  为准来理解最新进展
