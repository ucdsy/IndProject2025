# Stage R Gate Report (sr_clean_v2_20260314_related2)

- Input: `artifacts/dataset/challenge_joined_20260320_once.jsonl`
- Snapshot: `artifacts/stage_r_clean/challenge_recheck_20260322/challenge_joined_20260320_once.sr_clean_v2_20260314_related2.jsonl`
- Advance recommendation: `hold_stage_r`

## Core Metrics

- PrimaryRecall@5: 0.8333
- PrimaryRecall@10: 0.9167
- RelatedCoverage@10: 1.0
- UnionCoverage@10: 0.9375
- MRR: 0.6615
- L1Acc_top1cand: 0.7917
- L2Acc_top1cand: 0.6957
- L3PrimaryRecall@10: 1.0

## Gate 1

- PrimaryRecall@10: FAIL
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

- E2_l2: 2
- E5_candidate_noise: 5
- E6_unjustified_confusion: 12
- OK: 5

## Gate 2

- confusion_type_breakdown: completed
- module_ablations: completed
- weight_sensitivity: completed
- close_score_buckets: completed
