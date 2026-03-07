# Stage R Gate Report (sr_clean_v1_20260307)

- Input: `data/agentdns_routing/formal/dev.jsonl`
- Snapshot: `artifacts/stage_r_clean/dev.sr_clean_v1_20260307.jsonl`
- Advance recommendation: `advance_to_stage_a`

## Core Metrics

- PrimaryRecall@5: 1.0
- PrimaryRecall@10: 1.0
- RelatedCoverage@10: 0.8621
- UnionCoverage@10: 0.96
- MRR: 0.8183
- L1Acc_top1cand: 0.96
- L2Acc_top1cand: 0.875
- L3PrimaryRecall@10: 1.0

## Gate 1

- PrimaryRecall@10: PASS
- UnionCoverage@10: PASS
- L1Acc_top1cand: PASS
- L2Acc_top1cand: PASS
- L3PrimaryRecall@10: PASS
- SnapshotSchemaPassRate: PASS
- CandidateFormatPassRate: PASS
- TraceFieldPassRate: PASS
- ConfusionSourcePassRate: PASS
- Robustness: PASS

## Error Buckets

- E5_candidate_noise: 8
- E6_unjustified_confusion: 32
- OK: 10

## Gate 2

- confusion_type_breakdown: completed
- module_ablations: completed
- weight_sensitivity: completed
- close_score_buckets: completed
