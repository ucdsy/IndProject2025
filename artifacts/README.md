# Artifacts Index

This directory contains both historical experiment outputs and the latest
2026-03-23 packet-v2 review runs.

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

## Historical Outputs

Older experiment directories remain in their original locations because they are
already referenced by notes and analysis documents.

## Recommended Usage

- Use `routing_ab/review_packetv2_20260323/` for reporting and comparison.
- Use `stage_b/ablations_20260323/` only for runtime-parameter sensitivity checks.
- Treat everything under `scratch_*` as non-canonical.
