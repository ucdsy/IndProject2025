# IndProj04（2026-04-30 结项）工作区索引

> 目标: 按任务书在 2026-04-30 前形成“可验收结项包”，并可复用为论文与专利素材。

## 1. 你现在该看哪些（按优先级）
- 主审文档（优先只看这 2 份）:
  - `closure/13_design_doc_agentdns_routing.md`
  - `closure/14_execution_spec_and_review_gate.md`
- 结项讲法与硬交付:
  - `closure/01_deliverables_checklist.md`
  - `closure/02_taskbook_mapping.md`
  - `closure/06_review_ppt_outline.md`
- 本周必须冻结（M1: 2026-03-11）:
  - `closure/07_namespace_v1.md`
  - `closure/08_dataset_spec_and_labeling.md`
  - `closure/09_eval_protocol.md`
  - `closure/10_demo_runbook.md`
  - `closure/15_stage_r_clean_guardrails.md`
  - `closure/16_stage_a_strategy_and_execution.md`
- 命名/注册发现（把命名讲清楚，方便接真实平台）:
  - `closure/11_agent_registry_and_naming.md`
- clean Stage R 护栏（防过拟合 / 防伪 clean）:
  - `closure/15_stage_r_clean_guardrails.md`
- clean Stage A 方法与执行分工:
  - `closure/16_stage_a_strategy_and_execution.md`
- 材料复用（只取加速结项的部分）:
  - `closure/12_materials_reuse_notes.md`
- 论文/专利主线:
  - `closure/04_paper_blueprint.md`
  - `closure/03_patent_blueprint.md`
- 8 周倒排（到 2026-04-30）:
  - `closure/05_12week_plan.md`

## 2. 研究过程材料（写论文用）
- `research-project/01_problem-framing.md`
- `research-project/02_feasibility.md`
- `research-project/03_experiment-plan.md`
- `research-project/04_execution-log.md`
- `research-project/05_paper-outline.md`
- `research-project/06_related-work.md`
- `research-project/07_rebuttal-risks.md`

## 3. 任务书摘录
- `closure/00_taskbook_extract.md`

## 4. 执行入口（已落地）
说明:
- 下面这些“已落地”内容目前只表示 `contract/schema/脚手架` 已跑通。
- 旧 `bootstrap Stage R/A` 代码与默认入口已清理出主干，只保留历史执行日志与少量结论说明，不再作为可运行入口。
- 接下来按“先数据集与 blind protocol，后 clean Stage R/A”的顺序重做算法实现。

- 数据与标注底座:
  - `data/agentdns_routing/README.md`
  - `data/agentdns_routing/namespace_descriptors.jsonl`
  - `artifacts/dataset/knowledge_source_audit.md`
  - `data/agentdns_routing/dev.jsonl`
  - `data/agentdns_routing/test.jsonl`
  - `data/agentdns_routing/formal/manifest.json`
  - `data/agentdns_routing/formal/family_ledger.csv`
  - `data/agentdns_routing/formal/coverage_plan.csv`
  - `data/agentdns_routing/formal/README.md`
  - `data/agentdns_routing/labeling_guide.md`
- clean Stage R（descriptor-only baseline）:
  - `src/agentdns_routing/stage_r_clean.py`
  - `scripts/run_stage_r_clean_snapshot.py`
  - `artifacts/stage_r_clean/dev.sr_clean_v1_20260307.jsonl`
  - `artifacts/stage_r_clean/dev.sr_clean_v1_20260307.gate_summary.json`
  - `artifacts/stage_r_clean/dev.sr_clean_v1_20260307.gate_report.md`
  - `artifacts/stage_r_clean/dev.snapshot_freeze.json`
- clean Stage A（deterministic adjudicator）:
  - `src/agentdns_routing/stage_a_clean.py`
  - `scripts/run_stage_a_clean.py`
  - `artifacts/stage_a_clean/dev.sa_clean_v2_20260314.jsonl`
  - `artifacts/stage_a_clean/dev.sa_clean_v2_20260314.summary.json`
- clean Stage A（structured LLM, mock）:
  - `src/agentdns_routing/stage_a_llm.py`
  - `scripts/run_stage_a_llm.py`
  - `artifacts/stage_a_llm_mock/dev.sa_llm_v1_20260314.jsonl`
  - `artifacts/stage_a_llm_mock/dev.sa_llm_v1_20260314.summary.json`
- Canonical routing contract:
  - `src/agentdns_routing/namespace.py`
  - `scripts/export_routing_catalog.py`
  - `artifacts/namespace/routing_catalog.ns_v1_20260311.jsonl`
- Schema:
  - `schemas/namespace_descriptor.schema.json`
  - `schemas/gold_routing_sample.schema.json`
  - `schemas/formal_dev_sample.schema.json`
  - `schemas/formal_blind_input_sample.schema.json`
  - `schemas/formal_blind_label_sample.schema.json`
  - `schemas/formal_challenge_input_sample.schema.json`
  - `schemas/formal_challenge_label_sample.schema.json`
  - `schemas/candidate_snapshot.schema.json`
  - `schemas/routing_run_trace.schema.json`
- 数据校验入口:
  - `scripts/validate_formal_dataset.py`
- 历史 bootstrap 结果:
  - 只保留在 `research-project/04_execution-log.md` 作为过程记录，不再提供默认运行入口

## 5. 当前放行边界
- 已完成:
  - canonical `routing_fqdn` contract
  - clean `Stage R` snapshot
- 但当前状态仅代表:
  - schema、trace、resolver、脚手架已通
  - 不代表 Stage R/A 方法已经成立
- 尚未开始（按设计后置）:
  - Stage B 多角色共识
  - Stage C deterministic selector
- 接口边界:
  - Stage B 只能消费 `Stage A trace + fqdn_candidates`
  - Stage C 只能消费 canonical `selected_primary_fqdn`

## 6. 重建顺序（当前冻结）
1. 先保留 `namespace/canonical contract`，不再继续沿现有 `Stage R/A` 补功能。
2. 先完成正式 gold 数据集、blind split、freeze protocol。
3. 只允许使用独立于 gold query 的命名空间知识源，重建 clean `Stage R`（当前 `descriptor examples` 与旧 bootstrap 词典均已排除出 clean baseline 输入）。
4. 在冻结的 Stage R snapshot 上重建 clean `Stage A`。
5. 通过 blind test 后，再进入 Stage C；Stage B 最后做。

当前冻结结论:
- `clean Stage A v1` 的 `dev` 输入版本固定为 `sr_clean_v1_20260307`
- 冻结清单见 `artifacts/stage_r_clean/dev.snapshot_freeze.json`
- 后续如继续迭代 `Stage R`，必须升新版本，不得覆盖当前冻结产物
