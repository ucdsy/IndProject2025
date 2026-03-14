# Stage R Gate Report (sr_clean_v2_20260314_related2)

- Input: `/Users/xizhuxizhu/Desktop/IndProj04/data/agentdns_routing/formal/dev.jsonl`
- Snapshot: `/Users/xizhuxizhu/Desktop/IndProj04/artifacts/stage_r_clean/dev.sr_clean_v2_20260314_related2.jsonl`
- Advance recommendation: `advance_to_stage_a`

## Core Metrics

- PrimaryRecall@5: 1.0
- PrimaryRecall@10: 1.0
- RelatedCoverage@10: 1.0
- UnionCoverage@10: 1.0
- MRR: 0.8067
- L1Acc_top1cand: 0.96
- L2Acc_top1cand: 0.8333
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
- E6_unjustified_confusion: 33
- OK: 9

## Gate 2

- confusion_type_breakdown: completed
- module_ablations: completed
- weight_sensitivity: completed
- close_score_buckets: completed
