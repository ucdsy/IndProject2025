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
- 命名/注册发现（把命名讲清楚，方便接真实平台）:
  - `closure/11_agent_registry_and_naming.md`
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
- 其中 `Stage R` 与 `Stage A-only` 的当前实现已降级为 `bootstrap baseline`，不得作为正式方法或主表证据直接复用。
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
- Stage R 脚手架:
  - `src/agentdns_routing/stage_r.py`
  - `scripts/run_stage_r_snapshot.py`
- clean Stage R（descriptor-only baseline）:
  - `src/agentdns_routing/stage_r_clean.py`
  - `scripts/run_stage_r_clean_snapshot.py`
  - `artifacts/stage_r/formal_dev.sr_clean_v0_20260306.jsonl`
  - `artifacts/stage_r/formal_dev.sr_clean_v0_20260306.summary.json`
  - `artifacts/stage_r/formal_blind_input.sr_clean_v0_20260306.jsonl`
  - `artifacts/stage_r/formal_challenge_input.sr_clean_v0_20260306.jsonl`
- Canonical routing contract:
  - `src/agentdns_routing/namespace.py`
  - `scripts/export_routing_catalog.py`
  - `artifacts/namespace/routing_catalog.ns_v1_20260311.jsonl`
- Stage A-only 基线:
  - `src/agentdns_routing/stage_a.py`
  - `scripts/run_stage_a_eval.py`
  - `tests/test_stage_a.py`
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
- 已生成的候选快照:
  - `artifacts/stage_r/dev.sr_v0_20260306.jsonl`
  - `artifacts/stage_r/test.sr_v0_20260306.jsonl`
- 已生成的 Stage A 评测产物:
  - `artifacts/stage_a/dev.sa_v0_20260306.jsonl`
  - `artifacts/stage_a/dev.sa_v0_20260306.summary.json`
  - `artifacts/stage_a/test.sa_v0_20260306.jsonl`
  - `artifacts/stage_a/test.sa_v0_20260306.summary.json`

## 5. 当前放行边界
- 已完成:
  - canonical `routing_fqdn` contract
  - Stage R snapshot
  - Stage A-only 排序/trace/eval
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
3. 只允许使用独立于 gold query 的命名空间知识源，重建 clean `Stage R`（当前 `descriptor examples` 与 `evidence_lexicon.json` 已被排除出 clean baseline 输入）。
4. 在冻结的 Stage R snapshot 上重建 clean `Stage A`。
5. 通过 blind test 后，再进入 Stage C；Stage B 最后做。
