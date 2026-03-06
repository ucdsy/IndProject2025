# 相关工作地图

| 工作方向 | 核心思路 | 局限性 | 与本项目关系 |
|---|---|---|---|
| LLM committee / voting (generic) | 多个模型/多次采样投票提升鲁棒性 | 成本高；缺少协作过程与可审计轨迹 | Baseline: Multi-Agent Vote |
| Self-Consistency (Wang et al., 2022) | 多路径推理采样并聚合 | 仍是单体思路；不显式建模角色分工 | 与“稳定性”指标相关 |
| Tree-of-Thought / search-style reasoning (Yao et al., 2023) | 把推理当作搜索/树展开 | 工程复杂；成本与剪枝策略敏感 | 可用于“共识/选择”模块对照 |
| Multi-agent debate (generic) | 智能体对抗/讨论提升推理质量 | 容易回音室或争论不收敛；缺少标签反馈闭环 | Baseline: Debate |
| Preference modeling / RLHF / RLAIF (generic) | 用偏好/反馈信号塑形模型行为 | 训练与数据成本高；线上迭代困难 | 你的“用户代理反馈”定位 |
| Constitutional AI (Bai et al., 2022/2023) | 用规则/宪法约束生成与自我批评 | 规则覆盖有限；仍需审计与外部验证 | 与“规则一致性/可控性”相关 |
| Provenance / audit logging (generic) | 为系统决策过程记录可追溯证据 | 记录不等于可信；易被篡改 | 你的“可信标识/行为链”定位 |
| Tamper-evident log / hash-chain (generic) | 用 hash 链/签名实现篡改可检测 | 只保证完整性，不保证真实性 | 作为轻量级可信实现手段 |

## 备注
- 这里先放“写作地图”，后续可按投稿方向补齐具体引用与对比（尤其是 multi-agent debate、preference evaluator agents、traceability/provenance）。
