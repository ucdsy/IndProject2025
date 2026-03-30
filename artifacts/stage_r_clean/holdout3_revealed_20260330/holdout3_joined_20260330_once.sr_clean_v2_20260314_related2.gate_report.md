# Stage R Gate Report (sr_clean_v2_20260314_related2)

- Input: `artifacts/dataset/holdout3_joined_20260330_once.jsonl`
- Snapshot: `artifacts/stage_r_clean/holdout3_revealed_20260330/holdout3_joined_20260330_once.sr_clean_v2_20260314_related2.jsonl`
- Advance recommendation: `hold_stage_r`

## Core Metrics

- PrimaryRecall@5: 0.9475
- PrimaryRecall@10: 0.97
- RelatedCoverage@10: 0.3897
- UnionCoverage@10: 0.8688
- MRR: 0.8529
- L1Acc_top1cand: 0.8775
- L2Acc_top1cand: 0.8072
- L3PrimaryRecall@10: 0.9412

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

- E1_l1: 4
- E2_l2: 8
- E5_candidate_noise: 77
- OK: 311

## Gate 2

- confusion_type_breakdown: completed
- module_ablations: completed
- weight_sensitivity: completed
- close_score_buckets: completed
