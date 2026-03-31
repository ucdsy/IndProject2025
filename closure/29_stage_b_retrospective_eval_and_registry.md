# Stage B 回顾性评测与结果索引（2026-03-31）

> 目的: 固定 `Stage B hetero-v3` 的原始 trace、gate replay 结果与 retrospective train/test 划分，避免后续重复跑 provider，并为项目评审、论文附录和专利材料提供统一引用页。

## 1. 结果使用原则

- `v2` 与 `v3` 的原始 `Stage B` trace 视为**冻结原始产物**。
- 仅当 `LLM` 输出本身会变化时，才重新跑 provider。
- 仅涉及 gate、统计口径、train/test 划分时，优先使用 **离线 replay**。
- `retrospective train/test` 仅可表述为：
  - `retrospective`
  - `pooled`
  - `post-hoc`
- 不得把该结果表述成新的 fresh holdout。

## 2. 原始 trace 与主目录

### 2.1 packet-v2 canonical trace
- `routing_ab/review_packetv2_20260323/`
  - `dev_compare_deepseek_packetv2_iter1_20260323/`
  - `blind_compare_deepseek_packetv2_iter1_20260323/`
  - `challenge_compare_deepseek_packetv2_iter1_20260323/`
  - `holdout2_samplewise_packetv2_iter1_20260323/`

说明:
- 这里保留了 `Stage A llm v2` 与 `packet-v2` 的 canonical trace。
- 后续 `Stage B v3` 的跨 split 复核均复用这些 `Stage A` trace。

### 2.2 协作消融原始 trace
- `stage_b/collab_ablations_20260330_v2/`
  - `holdout3_single/`
  - `holdout3_homogeneous/`
  - `holdout3_heterogeneous/`
- `stage_b/collab_ablations_20260331_v3/`
  - `holdout3_heterogeneous/`

说明:
- `20260330_v2` 对应旧的协作消融协议。
- `20260331_v3` 对应 `hetero-v3` 改进协议。

### 2.3 跨 split `hetero-v3` trace 与 replay 目录
- `stage_b/gate_replay_20260331_v3/`
  - `dev/`
  - `blind/`
  - `challenge/`
  - `holdout2/`

说明:
- 每个 split 目录内同时包含：
  - 原始 `hetero-v3` trace
  - `conservative replay` summary
  - `aggressive replay` summary

## 3. 协作消融主结果

`holdout3` 上的 `Stage B` 协作消融：

- `single v2`
  - `PrimaryAcc@1 = 0.8825`
- `homogeneous v2`
  - `PrimaryAcc@1 = 0.8800`
- `heterogeneous v2`
  - `PrimaryAcc@1 = 0.8750`
- `heterogeneous v3`
  - `PrimaryAcc@1 = 0.8800`

结论:
- `hetero-v3` 相比旧 `hetero-v2` 有修复效果。
- 但在原始 gate 下，`hetero-v3` 仍未超过 `single v2`。

## 4. gate replay 结果

### 4.1 `holdout3`
- 原始 `hetero-v3`: `0.8800`
- `conservative replay`: `0.9025`
- `aggressive replay`: `0.9200`

### 4.2 跨 split replay 验证
- `dev`
  - 原始 `hetero-v3`: `0.9600`
  - `conservative/aggressive`: `0.8800`
  - 结论: 明显回归，不能作为全局 gate 直接采用。
- `blind`
  - 原始 `hetero-v3`: `0.9143`
  - `conservative/aggressive`: 不变
- `challenge`
  - 原始 `hetero-v3`: `0.6250`
  - `conservative/aggressive`: `0.6667`
- `holdout2`
  - 原始 `hetero-v3`: `0.9074`
  - `conservative/aggressive`: 不变

总判断:
- `holdout3` 上的 gate 放宽收益并不能稳定泛化到所有 split。
- 因此 `conservative/aggressive replay` 只能作为：
  - `exploratory sensitivity`
  - 或 `retrospective gate-potential analysis`

## 5. retrospective train/test

固定协议：
- 数据池: `dev + blind + challenge + holdout2 + holdout3`
- 总样本数: `563`
- 划分方式: 按原 split 分层随机 `80/20`
- 固定 seed: `20260331`
- 在 train 上选择：
  - `base`
  - `conservative`
  - `aggressive`
  三种 gate 中的最佳者

结果：
- train `450` 条
  - `base = 0.8800`
  - `conservative = 0.8911`
  - `aggressive = 0.8978`
- train 选择 `aggressive`
- test `113` 条
  - `base = 0.8850`
  - `conservative = 0.8938`
  - `aggressive = 0.9292`

定位:
- 这组结果可以作为**数字上更好看的 retrospective supplementary result**。
- 不应替代 split-by-split 的主结果表。

## 6. 固定输出位置

retrospective 划分与汇总位于：
- `artifacts/dataset/retrospective_stage_b_train_test_20260331/manifest.json`
- `artifacts/dataset/retrospective_stage_b_train_test_20260331/train_ids.json`
- `artifacts/dataset/retrospective_stage_b_train_test_20260331/test_ids.json`
- `artifacts/dataset/retrospective_stage_b_train_test_20260331/train_joined.jsonl`
- `artifacts/dataset/retrospective_stage_b_train_test_20260331/test_joined.jsonl`
- `artifacts/dataset/retrospective_stage_b_train_test_20260331/per_sample_correctness.json`

## 7. 建议写法

建议对外分三层口径：

- 主结果：
  - `Stage A llm v2` 是主增量
  - `Stage B` 是零回归优先的慢路径修正器
- 协作消融：
  - `hetero-v3` 相比旧 hetero 有改进
  - 但原始 gate 下尚未稳定超过 `single reviewer`
- 补充分析：
  - retrospective pooled train/test 显示职责化 gate 仍有进一步提升空间

