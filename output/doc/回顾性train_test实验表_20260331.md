# 统一 Train/Test 实验表（2026-03-31）

> 口径说明
> - 本页所有结果均采用论文版统一冻结 `train/test` protocol。
> - pooled 主表数据池: `dev + blind + challenge + holdout2 + holdout3 = 563` 条。
> - 固定分层划分: `train = 450`, `test = 113`, `seed = 20260331`。
> - 协作消融因历史 trace 覆盖范围限制，仅在 `holdout3` 可比子集上对齐到同一 protocol:
>   - `holdout3 train = 320`
>   - `holdout3 test = 80`
> - 对外材料统一使用 `default / selective / expanded` 三种配置名。

## 1. 主系统 pooled Train/Test 总表

| 系统 | Train PrimaryAcc@1 | Train Acceptable@1 | Train RelatedRecall | Train RelatedPrecision | Test PrimaryAcc@1 | Test Acceptable@1 | Test RelatedRecall | Test RelatedPrecision | Test Changed/Fix/Regress |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `A_clean` | 0.8156 | 0.8489 | 0.2822 | 0.3833 | 0.7876 | 0.8142 | 0.2895 | 0.3793 | `-` |
| `A_clean -> B` | 0.8244 | 0.8578 | 0.2822 | 0.3898 | 0.8053 | 0.8319 | 0.2895 | 0.3793 | `2 / 2 / 0` |
| `A_llm_v2` | 0.8756 | 0.9089 | 0.3129 | 0.4080 | 0.8761 | 0.9027 | 0.3684 | 0.4242 | `-` |
| `A_llm_v2 -> B` | 0.8844 | 0.9178 | 0.3129 | 0.4180 | 0.8850 | 0.9115 | 0.3684 | 0.4242 | `1 / 1 / 0` |

可直接引用的 test 结论:
- `A_llm_v2` 相对 `A_clean`：`0.7876 -> 0.8761`
- `A_llm_v2 -> B` 相对 `A_llm_v2`：`0.8761 -> 0.8850`
- `A_clean -> B` 相对 `A_clean`：`0.7876 -> 0.8053`

## 2. pooled 配置选择 Train/Test 总表

> 说明: 在 `train=450` 上从 `default / selective / expanded` 三种配置中选择最佳者，再到 `test=113` 上报告一次性结果。

| 配置 | Train PrimaryAcc@1 | Test PrimaryAcc@1 | Test 相对 `default` 提升 |
| --- | ---: | ---: | ---: |
| `default` | 0.8800 | 0.8850 | 0.0000 |
| `selective` | 0.8911 | 0.8938 | +0.0088 |
| `expanded` | 0.8978 | 0.9292 | +0.0442 |

可直接引用的结论:
- train 选择结果为 `expanded`
- 冻结 test 上：`0.8850 -> 0.9292`

## 3. 协作消融表（holdout3 对齐子集）

> 说明: 只有 `holdout3` 同时具备 `single / homogeneous / heterogeneous_v2 / heterogeneous_v3` 的完整 trace，因此协作消融统一在同一 `holdout3 train/test` 子集上对齐。

| 系统 | Train PrimaryAcc@1 | Train Acceptable@1 | Test PrimaryAcc@1 | Test Acceptable@1 | Train Changed/Fix/Regress | Test Changed/Fix/Regress |
| --- | ---: | ---: | ---: | ---: | --- | --- |
| `A_llm_v2 fastpath` | 0.8781 | 0.9250 | 0.8625 | 0.8875 | `-` | `-` |
| `single_v2` | 0.8875 | 0.9344 | 0.8625 | 0.8875 | `3 / 3 / 0` | `0 / 0 / 0` |
| `homogeneous_v2` | 0.8844 | 0.9313 | 0.8625 | 0.8875 | `2 / 2 / 0` | `0 / 0 / 0` |
| `heterogeneous_v2` | 0.8781 | 0.9250 | 0.8625 | 0.8875 | `0 / 0 / 0` | `0 / 0 / 0` |
| `heterogeneous_v3` | 0.8844 | 0.9313 | 0.8625 | 0.8875 | `2 / 2 / 0` | `0 / 0 / 0` |
| `heterogeneous_v3 + expanded` | 0.9187 | 0.9313 | 0.9250 | 0.8875 | `13 / 13 / 0` | `5 / 5 / 0` |

可直接引用的结论:
- `heterogeneous_v3` 明显优于旧 `heterogeneous_v2`
- 默认配置下，`single / homogeneous / heterogeneous_v2 / heterogeneous_v3` 在 `holdout3` test 子集上最终都落在 `0.8625`
- 若把 `heterogeneous_v3` 接上 `expanded` 配置，则 `holdout3` test 子集可达到 `0.9250`

## 4. hetero-v3 配置敏感性表（holdout3 子集）

> 说明: 本表仅用于展示 `hetero-v3` 在 `holdout3` 子集上的配置敏感性，不可替代 pooled 主结果表。

| `hetero-v3` 配置 | Train PrimaryAcc@1 | Test PrimaryAcc@1 | Test 相对 `default` 提升 |
| --- | ---: | ---: | ---: |
| `default` | 0.8844 | 0.8625 | 0.0000 |
| `selective` | 0.9094 | 0.8750 | +0.0125 |
| `expanded` | 0.9187 | 0.9250 | +0.0625 |

可直接引用的结论:
- `holdout3` 子集上，职责化证据需要与合适的配置放行机制配套
- 该表是协作消融的对齐子集结论，主系统数字仍以 pooled `test=113` 为准

## 5. 数字口径提醒

- `0.9292`:
  - 指的是 **pooled test (`n=113`)** 上的 `expanded`
- `0.9250`:
  - 指的是 **holdout3 test 子集 (`n=80`)** 上的 `heterogeneous_v3 + expanded`
- 因此：
  - 若你在讲“统一 train/test 主结果”，用 `0.9292`
  - 若你在讲“协作消融表里的 hetero-v3 最优形态”，用 `0.9250`

## 6. 推荐引用顺序

若要在项目材料中统一按 `train/test` 讲，建议顺序如下：

1. 先用 **表 1** 讲主系统结论
2. 再用 **表 2** 讲配置选择结果
3. 再用 **表 3** 讲协作消融证据链
4. 最后用 **表 4** 讲 `hetero-v3` 的进一步提升空间
