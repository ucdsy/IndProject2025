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
- 数据与标注底座:
  - `data/agentdns_routing/README.md`
  - `data/agentdns_routing/namespace_descriptors.jsonl`
  - `data/agentdns_routing/dev.jsonl`
  - `data/agentdns_routing/test.jsonl`
  - `data/agentdns_routing/labeling_guide.md`
- Stage R 脚手架:
  - `src/agentdns_routing/stage_r.py`
  - `scripts/run_stage_r_snapshot.py`
- Schema:
  - `schemas/namespace_descriptor.schema.json`
  - `schemas/gold_routing_sample.schema.json`
  - `schemas/candidate_snapshot.schema.json`
  - `schemas/routing_run_trace.schema.json`
- 已生成的候选快照:
  - `artifacts/stage_r/dev.sr_v0_20260306.jsonl`
  - `artifacts/stage_r/test.sr_v0_20260306.jsonl`
