# Stage R Gate Report (sr_clean_v2_20260314_related2)

- Input: `artifacts/dataset/holdout2_joined_20260322_once.jsonl`
- Snapshot: `artifacts/stage_r_clean/holdout2_revealed_20260322/holdout2_joined_20260322_once.sr_clean_v2_20260314_related2.jsonl`
- Advance recommendation: `hold_stage_r`

## Core Metrics

- PrimaryRecall@5: 0.9815
- PrimaryRecall@10: 0.9815
- RelatedCoverage@10: 1.0
- UnionCoverage@10: 0.9815
- MRR: 0.8519
- L1Acc_top1cand: 0.9074
- L2Acc_top1cand: 0.7692
- L3PrimaryRecall@10: 1.0

## Gate 1

- PrimaryRecall@10: PASS
- UnionCoverage@10: PASS
- L1Acc_top1cand: PASS
- L2Acc_top1cand: FAIL
- L3PrimaryRecall@10: PASS
- SnapshotSchemaPassRate: PASS
- CandidateFormatPassRate: PASS
- TraceFieldPassRate: PASS
- ConfusionSourcePassRate: PASS
- Robustness: PASS

## Error Buckets

- E1_l1: 1
- E5_candidate_noise: 4
- E6_unjustified_confusion: 18
- OK: 31

## Gate 2

- confusion_type_breakdown: completed
- module_ablations: completed
- weight_sensitivity: completed
- close_score_buckets: completed
