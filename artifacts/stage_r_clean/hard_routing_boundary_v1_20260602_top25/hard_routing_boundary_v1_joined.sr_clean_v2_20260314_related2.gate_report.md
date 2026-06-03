# Stage R Gate Report (sr_clean_v2_20260314_related2)

- Input: `artifacts/dataset/hard_routing_boundary_v1_20260602/hard_routing_boundary_v1_joined.jsonl`
- Snapshot: `artifacts/stage_r_clean/hard_routing_boundary_v1_20260602_top25/hard_routing_boundary_v1_joined.sr_clean_v2_20260314_related2.jsonl`
- Advance recommendation: `hold_stage_r`

## Core Metrics

- PrimaryRecall@5: 0.774
- PrimaryRecall@10: 0.99
- RelatedCoverage@10: 1.0
- UnionCoverage@10: 0.99
- MRR: 0.6091
- L1Acc_top1cand: 0.738
- L2Acc_top1cand: 0.4735
- L3PrimaryRecall@10: 0.9583

## Gate 1

- PrimaryRecall@10: PASS
- UnionCoverage@10: PASS
- L1Acc_top1cand: FAIL
- L2Acc_top1cand: FAIL
- L3PrimaryRecall@10: PASS
- SnapshotSchemaPassRate: PASS
- CandidateFormatPassRate: PASS
- TraceFieldPassRate: PASS
- ConfusionSourcePassRate: PASS
- Robustness: PASS

## Error Buckets

- E3_l3: 5
- E5_candidate_noise: 10
- E6_unjustified_confusion: 483
- OK: 2

## Gate 2

- confusion_type_breakdown: completed
- module_ablations: completed
- weight_sensitivity: completed
- close_score_buckets: completed
