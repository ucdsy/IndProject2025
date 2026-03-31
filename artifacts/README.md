# Artifacts Index

This directory contains historical experiment outputs, the 2026-03-23
packet-v2 review runs, and the 2026-03-31 Stage-B heterogeneity /
retrospective evaluation outputs.

## Current 2026-03-23 Layout

- `routing_ab/review_packetv2_20260323/`
  - Canonical packet-v2 review runs used for the latest analysis.
  - Contains:
    - `dev_compare_deepseek_packetv2_iter1_20260323/`
    - `blind_compare_deepseek_packetv2_iter1_20260323/`
    - `challenge_compare_deepseek_packetv2_iter1_20260323/`
    - `holdout2_samplewise_packetv2_iter1_20260323/`

- `routing_ab/scratch_packetv2_20260323/`
  - Temporary or partial packet-v2 runs kept only for debugging / provenance.
  - Contains:
    - `dev_smoke_uncertainty_packetv2_20260323/`
    - `holdout2_compare_deepseek_packetv2_iter1_20260323/`
    - `holdout2_chunks_packetv2_iter1_20260323/`

- `stage_b/ablations_20260323/`
  - Stage-B-only ablation reruns for `max_tokens=3000`.
  - Contains:
    - `challenge_llm_b_maxtok3000_20260323/`
    - `holdout2_llm_b_maxtok3000_20260323/`

- `dataset/scratch_20260323/`
  - Temporary dataset sharding used to recover long-running `holdout2` jobs.
  - Contains:
    - `holdout2_chunks_20260323/`

## Current 2026-03-31 Layout

- `stage_b/collab_ablations_20260330_v2/`
  - Frozen `holdout3` collaboration ablation traces for:
    - `single`
    - `homogeneous`
    - `heterogeneous_v2`
  - Kept locally in this branch so later summary/regression tables can be regenerated without rerunning providers.

- `stage_b/collab_ablations_20260331_v3/`
  - `hetero-v3` holdout3 raw trace and summary.

- `stage_b/gate_replay_20260331_v3/`
  - Cross-split `hetero-v3` raw traces for:
    - `dev`
    - `blind`
    - `challenge`
    - `holdout2`
  - Each split directory also includes:
    - `replay_conservative.summary.json`
    - `replay_aggressive.summary.json`

- `dataset/retrospective_stage_b_train_test_20260331/`
  - Fixed-seed retrospective pooled train/test split.
  - Contains:
    - `manifest.json`
    - `train_ids.json`
    - `test_ids.json`
    - `train_joined.jsonl`
    - `test_joined.jsonl`
    - `per_sample_correctness.json`

- `stage_b/experiment_registry_20260331.json`
  - Machine-readable index of:
    - packet-v2 canonical Stage-A traces
    - `single / homogeneous / heterogeneous_v2`
    - `heterogeneous_v3`
    - gate replay root
    - retrospective split root

## Historical Outputs

Older experiment directories remain in their original locations because they are
already referenced by notes and analysis documents.

## Recommended Usage

- Use `routing_ab/review_packetv2_20260323/` for reporting and comparison.
- Use `stage_b/ablations_20260323/` only for runtime-parameter sensitivity checks.
- Use `stage_b/gate_replay_20260331_v3/` for `hetero-v3` cross-split replay analysis.
- Use `dataset/retrospective_stage_b_train_test_20260331/` only as a retrospective supplementary result set.
- Treat everything under `scratch_*` as non-canonical.
