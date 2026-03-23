# Related Miss 治理表（2026-03-14）

> 目的: 将 `decision_related_miss` 与 `stage_r_related_miss` 的责任边界、当前状态、以及后续动作拆清楚。
>
> 适用范围: `clean Stage A` related 决策修正、`clean Stage R` related 召回修正、以及 `Stage B` 升级样本池准备。
>
> 当前口径:
> - 本文前半部分保留 `Stage A clean v6 / Stage R v1` 冻结线上的 related miss 治理判断
> - 当前 live repo 的 `Stage A clean` 主线已前移到 `sa_clean_v8_20260314_riskschema_on_sr_v2`
> - 当前 `Stage R` 主线已前移到 `sr_clean_v2_20260314_related2`
> - 因此，本文应主要作为责任边界与误差治理方法记录阅读，不应再被当作当前主结果表

## 1. 分类定义

- `decision_related_miss`
  - `Stage R` 已召回 relevant related candidate
  - `Stage A` 未将其写入 `selected_related_fqdns`
  - 主责: `Stage A`

- `stage_r_related_miss`
  - relevant related candidate 未进入 `Stage R` 候选集
  - `Stage A` 无法补救
  - 主责: `Stage R`

## 2. 当前总表状态

### 2.1 `Stage A clean` 当前结果
- 冻结 `sr_clean_v1_20260307` 上的 related 决策收口版本:
  - `artifacts/stage_a_clean/dev.sa_clean_v6_20260314_related2.summary.json`
- 当前 end-to-end clean 主线版本:
  - `artifacts/stage_a_clean/dev.sa_clean_v7_20260314_related3_on_sr_v2.summary.json`
- 指标:
  - `PrimaryAcc@1 = 1.0`
  - `AcceptablePrimary@1 = 1.0`
  - `RelatedRecall = 1.0`
  - `RelatedRecall@Covered = 1.0`
  - `RelatedPrecision = 1.0`
  - `related_overpredict_rate = 0.0`
  - `escalation_rate = 0.54`
- 当前误差桶:
  - `OK = 50`

### 2.2 `Stage A llm mock` 当前结果
- 产物: `artifacts/stage_a_llm_mock/dev.sa_llm_v1_20260314_tight8_related3_on_sr_v2.summary.json`
- 指标:
  - `PrimaryAcc@1 = 0.98`
  - `AcceptablePrimary@1 = 0.98`
  - `RelatedRecall = 1.0`
  - `RelatedRecall@Covered = 1.0`
  - `RelatedPrecision = 1.0`
  - `related_overpredict_rate = 0.0`
  - `escalation_rate = 0.62`
- 当前唯一非 related 残差:
  - `decision_primary_miss = 1` (`formal_dev_000036`)

## 3. 7 样本治理表

| sample_id | 旧问题归类 | relevant fqdn | 当前状态 | 主责阶段 | 下一步动作 |
| --- | --- | --- | --- | --- | --- |
| `formal_dev_000001` | `stage_r_related_miss` | `policy.gov.cn` | 已修复 | `Stage R` | `policy.gov.cn` 补 `依据` 后进入 `sr_clean_v2_related2` |
| `formal_dev_000003` | `stage_r_related_miss` | `policy.gov.cn` | 已修复 | `Stage R` | 同 `000001` |
| `formal_dev_000027` | `decision_related_miss` | `docs.productivity.cn` | 已修复 | `Stage A` | `clean` 与 `deepseek target5` 均已恢复 |
| `formal_dev_000035` | `stage_r_related_miss` | `price.commerce.cn` | 已修复 | `Stage R` | `price.commerce.cn` 补 `差价` 后进入 `sr_clean_v2_related2` |
| `formal_dev_000037` | `decision_related_miss` | `weather.cn` | 已修复 | `Stage A` | 保持 `non-risk cross-l1 secondary` 护栏，不回退 |
| `formal_dev_000043` | `stage_r_related_miss` | `hotel.travel.cn` | 已修复 | `Stage R` | `hotel.travel.cn` 补 `住处` 后进入 `sr_clean_v2_related2` |
| `formal_dev_000045` | `decision_related_miss` | `itinerary.travel.cn` | 已修复 | `Stage A` | 保持 `non-risk cross-l1 secondary` 护栏，不回退 |

## 4. 本轮新增边角样本

这些样本不是 `10.7` 原始 7 个残差的一部分，但在 related 治理过程中暴露出来，已一并处理。

| sample_id | 暴露的问题 | 当前状态 | 处理动作 |
| --- | --- | --- | --- |
| `formal_dev_000046` | `fitness.health.cn` 已召回但未入 related | 已修复 | 为 `fitness.health.cn` 补 `运动/运动建议/训练建议` alias；`clean`、`mock`、`deepseek target5/target1` 均恢复 |
| `formal_dev_000009` | `fraud.security.cn` 被误挂为 extra related | 已修复 | 风险簇 related 仅接受显式 `secondary_hits`，不再让结构化多意图单独放行 |

## 5. 当前策略判断

### 5.1 `Stage A` 侧
- `primary routing` 已可视为冻结
- `related` 侧在冻结 snapshot 上已经做到:
  - `RelatedRecall@Covered = 1.0`
  - `RelatedPrecision = 1.0`
- 因此 `Stage A` 当前优先级从“继续修规则”切换为“做 real-provider 复核 + 保持双轨报告”

### 5.2 `Stage R` 侧
- `Stage R v2_related2` 已证明低风险 descriptor 补强足以修复 4 个 related 漏召回
- 当前不再有 `formal/dev` 上的 `stage_r_related_miss`
- 允许动作:
  - descriptor/alias 补充
  - relevant sibling / cross-domain complement 扩张
  - 与 `related` 覆盖直接相关的排序细节修正
- 不允许动作:
  - 覆盖 `sr_clean_v1_20260307`
  - 从 `formal/dev` query 反抄专用触发词
  - 为个别样本引入 query-specific 分支

## 6. 下一步执行

1. 选择是否对 `sr_clean_v2_related2 + sa_clean_v7` 做真实 provider 全量复核。
2. 将 `Stage B` 样本池重点切到 `escalate_to_stage_b = true` 的高风险/低置信样本，而不是继续修 clean baseline。
3. 保留 `mock + deepseek` 双轨报告，作为:
   - 调参观测
   - provider 偏差对照
   - 答辩/论文中的工程可信性材料
