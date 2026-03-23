# Stage R Gate Report (sr_clean_v2_20260314_related2)

- Input: `artifacts/dataset/blind_joined_20260315_once.jsonl`
- Snapshot: `artifacts/stage_r_clean/blind_recheck_20260322/blind_joined_20260315_once.sr_clean_v2_20260314_related2.jsonl`
- Advance recommendation: `advance_to_stage_a`

## Core Metrics

- PrimaryRecall@5: 0.9714
- PrimaryRecall@10: 0.9714
- RelatedCoverage@10: 1.0
- UnionCoverage@10: 0.9714
- MRR: 0.8295
- L1Acc_top1cand: 0.9714
- L2Acc_top1cand: 0.8529
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

- E2_l2: 1
- E5_candidate_noise: 3
- E6_unjustified_confusion: 27
- OK: 4

## Gate 2

- confusion_type_breakdown: completed
- module_ablations: completed
- weight_sensitivity: completed
- close_score_buckets: completed
