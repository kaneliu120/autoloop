# AutoLoop 流程控制参数

> **互补关系声明**：本文档与 `quality-gates.md` 形成互补关系，共同构成 AutoLoop 迭代控制体系。
> - `quality-gates.md` 定义"结果够不够好"——质量判定，关注输出的评分标准与门禁阈值
> - `parameters.md`（本文档）定义"过程怎么控制"——流程参数，关注迭代次数、触发条件、回退上限等执行约束
>
> 修改本文档属于协议进化，须经 REFLECT 阶段提案 + 用户确认后方可执行（见 `evolution-rules.md` 协议进化流程章节）。

---

## 一、迭代控制参数

### 1.1 默认轮次表

> 来源：原 `commands/autoloop-plan.md` 模板默认参数参考表

| 参数名 | 模板 | 值 | 适用范围 | 说明 |
|--------|------|----|---------|------|
| `default_rounds.T1` | T1 Research | 3 轮 | T1 调研任务 | 调研类任务默认执行 3 轮，确保信息充分覆盖 |
| `default_rounds.T2` | T2 Compare | 2 轮 | T2 对比任务 | 对比类任务完成两轮即可收敛结论 |
| `default_rounds.T3` | T3 Iterate | 无上限 | T3 迭代任务 | 以质量门禁为终止条件，不设轮次上限；预算由用户定义 |
| `default_rounds.T4` | T4 Generate | items × 2 轮 | T4 批量生成任务 | 默认轮次 = 生成单元数量 × 2，保证每单元至少 2 次优化机会 |
| `default_rounds.T5` | T5 Deliver | 1（线性阶段制）| T5 交付任务 | 非轮次制，按 Phase 1-5 线性阶段推进 |
| `default_rounds.T6` | T6 Quality | 无上限 | T6 质量评审任务 | 以质量门禁为终止条件，不设轮次上限 |
| `default_rounds.T7` | T7 Optimize | 无上限 | T7 优化任务 | 以质量门禁为终止条件，不设轮次上限 |

**使用约定**：
- 向导在 Step 4/5 展示对应模板的默认值，用户可在计划阶段调整
- `items × 2` 中的 `items` 指 plan.md 中定义的生成单元总数
- "无上限"模板的实际终止条件见 `quality-gates.md` 对应行

---

## 二、进化触发参数

> 来源：原 `references/evolution-rules.md`

### 2.1 范围扩展允许条件

| 参数名 | 值 | 适用范围 | 说明 |
|--------|----|---------|------|
| `evolution.expand.budget_threshold` | ≥ 30% | T1、T3、T6、T7 | 剩余预算比例须达到此阈值方可允许范围扩展 |
| `evolution.expand.dimension_ceiling` | ≤ 初始维度 × 1.5 | 全部模板 | 扩展后总维度数不得超过初始维度数的 1.5 倍 |

**触发逻辑**：同时满足以下全部条件时，允许扩展：
1. 新维度重要性 = 高（影响核心结论）
2. 预算剩余 ≥ `evolution.expand.budget_threshold`（30%）
3. 扩展后总维度 ≤ `evolution.expand.dimension_ceiling`（初始 × 1.5）

### 2.2 范围收窄触发条件

| 参数名 | 值 | 适用范围 | 说明 |
|--------|----|---------|------|
| `evolution.narrow.budget_consumed` | ≥ 70% | T1、T3、T6、T7 | 已消耗预算比例达到此值时触发收窄评估 |
| `evolution.narrow.coverage_threshold` | < 60% | T1、T3、T6、T7 | 覆盖率低于此值时触发收窄评估 |
| `evolution.narrow.lag_dimensions` | ≥ 3 个维度连续 2 轮 | T1、T3 | 多维度同时落后的判定标准 |

**触发逻辑**：满足以下任一条件时，触发收窄：
1. 已消耗 ≥ `evolution.narrow.budget_consumed`（70%）且覆盖率 < `evolution.narrow.coverage_threshold`（60%）
2. 连续 2 轮在 ≥ 3 个维度同时落后
3. 发现某些维度信息极度稀缺，继续投入收益极低

### 2.3 策略切换触发条件

| 参数名 | 值 | 适用范围 | 说明 |
|--------|----|---------|------|
| `evolution.switch.consecutive_rounds` | 2 轮 | 全部模板 | 连续多少轮改进不足时触发策略切换 |
| `evolution.switch.improvement_threshold` | < 3%（相对值）| 全部模板 | 单轮改进幅度低于此相对百分比时视为"停滞"；示例：当前 80%，改善阈值 = 2.4%；当前 7/10 分，改善阈值 = 0.21 分 |

**触发逻辑**：同一维度连续 `evolution.switch.consecutive_rounds`（2）轮改进 < `evolution.switch.improvement_threshold`（3%，相对值），触发策略切换。

---

## 三、范围扩展上限

> 来源：原 `references/evolution-rules.md` 进化约束章节

| 参数名 | 值 | 适用范围 | 说明 |
|--------|----|---------|------|
| `evolution.expand.max_count` | 2 次 | 全部模板 | 整个任务周期内最多允许范围扩展的次数 |
| `evolution.expand.dimension_ceiling` | ≤ 初始维度 × 1.5 | 全部模板 | 每次扩展后总维度数上限（同 2.1，此处明确为约束） |
| `evolution.expand.cumulative_limit` | ≤ 初始维度数的 50% | 全部模板 | 累计扩展维度数上限（防止无限蔓延） |

**约束说明**：超过 `evolution.expand.max_count`（2 次）后，即使条件满足也不允许继续扩展，须向用户报告并等待人工决策。

---

## 四、流程回退限制

> 来源：原 `references/delivery-phases.md` 回退机制章节

| 参数名 | 值 | 适用范围 | 说明 |
|--------|----|---------|------|
| `flow.rollback.max_per_phase` | 2 次 | T5 各阶段（Phase 1-5）| 每个阶段最多允许的回退次数，超过上限须向用户报告并等待人工决策 |
| `flow.rollback.phase2_exception` | 3 轮 | T5 Phase 2（修复-审查循环）| Phase 2 的修复-审查循环例外上限，允许最多 3 轮 |

**回退路径参考**：

| 发现问题的阶段 | 回退到 | 回退范围 |
|-------------|--------|---------|
| Phase 2 发现 P1/P2 | Phase 1 | 仅修复对应文件 |
| Phase 3 验证失败 | Phase 1 或 Phase 2 | 修复 + 重审 |
| Phase 4 部署失败 | Phase 3（修复后重测试）| 修复 + 重测 + 重部署 |
| Phase 5 线上有问题 | Phase 4（回滚）或 Phase 1（修复）| 用户决定回滚还是热修复 |

---

## 五、验证与矛盾解决参数

> 来源：原 `references/loop-protocol.md` 矛盾解决规则

| 参数名 | 值 | 适用范围 | 说明 |
|--------|----|---------|------|
| `verification.conflict.score_diff` | > 2 | 全部模板 | 两个 subagent 对同一代码的评分差超过此值时，触发第三次验证或人工判断 |
| `oscillation.window` | 3 轮 | 全部模板 | 连续多少轮在 ±band 范围内波动视为振荡 |
| `oscillation.band` | ±0.5 分 | 全部模板 | 振荡判定的分数波动带宽 |
| `regression.threshold` | 跌破门禁阈值 | 全部模板 | 任何受影响维度跌破门禁阈值视为跨维度回归 |

**矛盾解决规则**：

| 矛盾类型 | 解决规则 |
|---------|---------|
| A 说"有问题"，B 说"没问题" | 以更保守的（有问题）为准，记录 B 的理由 |
| 两个 subagent 对同一代码的评分差 > `verification.conflict.score_diff`（2） | 运行第三次验证（或人工判断） |
| 修复方案互相冲突 | 选择改动最小的，记录弃用的原因 |

---

## 六、模板级停滞检测参数

> 来源：R7评审建议#3 — T3/T6/T7 需要独立停滞阈值

### 6.1 停滞阈值（按模板独立）

| 参数名 | 模板 | 值 | 说明 |
|--------|------|----|------|
| `stagnation.T3.threshold` | T3 Iterate | < 2%（相对值） | KPI 改善幅度低于当前值的 2% 视为停滞 |
| `stagnation.T3.max_explore` | T3 Iterate | 3 轮 | 停滞后最多尝试 3 种新策略 |
| `stagnation.T6.threshold` | T6 Quality | < 0.3 分（绝对值） | 安全/可靠/可维护任一维度改善 < 0.3 分视为停滞 |
| `stagnation.T6.max_explore` | T6 Quality | 2 轮 | 停滞后最多尝试 2 种新策略 |
| `stagnation.T7.threshold` | T7 Optimize | < 0.5 分（绝对值） | 架构/性能/稳定任一维度改善 < 0.5 分视为停滞 |
| `stagnation.T7.max_explore` | T7 Optimize | 2 轮 | 停滞后最多尝试 2 种新策略 |

**注**：T1/T2 使用通用停滞阈值 `evolution.switch.improvement_threshold`（< 3%），因为调研类任务的停滞特征与迭代优化类不同。

### 6.2 统一停滞状态机

```text
正常迭代
  ↓ 连续 2 轮改善 < 模板阈值
[停滞检测] → 标记维度为"停滞"
  ↓
[策略切换] → 从 experience-registry 或策略矩阵选择新策略
  ↓ 执行新策略
[探索验证] → 新策略是否有效？
  ├── 有效（改善 ≥ 阈值）→ 回到正常迭代
  ├── 无效但未达 max_explore → 继续探索（换另一个策略）
  └── 无效且达 max_explore → [终止评估]
        ├── 距离门禁 ≤ 10% → 输出当前最优，标注未达标项
        └── 距离门禁 > 10% → 上报用户，建议调整目标或追加预算
```

---

## 七、参数索引（快速查阅）

| 参数名 | 值 | 所属分组 |
|--------|----|---------|
| `default_rounds.T1` | 3 轮 | 迭代控制 |
| `default_rounds.T2` | 2 轮 | 迭代控制 |
| `default_rounds.T3` | 无上限 | 迭代控制 |
| `default_rounds.T4` | items × 2 轮 | 迭代控制 |
| `default_rounds.T5` | 1（线性阶段制）| 迭代控制 |
| `default_rounds.T6` | 无上限 | 迭代控制 |
| `default_rounds.T7` | 无上限 | 迭代控制 |
| `evolution.expand.budget_threshold` | ≥ 30% | 进化触发 |
| `evolution.expand.dimension_ceiling` | ≤ 初始 × 1.5 | 进化触发 / 扩展上限 |
| `evolution.narrow.budget_consumed` | ≥ 70% | 进化触发 |
| `evolution.narrow.coverage_threshold` | < 60% | 进化触发 |
| `evolution.narrow.lag_dimensions` | ≥ 3 个维度连续 2 轮 | 进化触发 |
| `evolution.switch.consecutive_rounds` | 2 轮 | 进化触发 |
| `evolution.switch.improvement_threshold` | < 3%（相对值）| 进化触发 |
| `evolution.expand.max_count` | 2 次 | 扩展上限 |
| `evolution.expand.cumulative_limit` | ≤ 初始维度数 50% | 扩展上限 |
| `flow.rollback.max_per_phase` | 2 次 | 流程回退 |
| `flow.rollback.phase2_exception` | 3 轮 | 流程回退 |
| `verification.conflict.score_diff` | > 2 | 矛盾解决 |
| `stagnation.T3.threshold` | < 2%（相对值） | 停滞检测 |
| `stagnation.T3.max_explore` | 3 轮 | 停滞检测 |
| `stagnation.T6.threshold` | < 0.3 分（绝对值） | 停滞检测 |
| `stagnation.T6.max_explore` | 2 轮 | 停滞检测 |
| `stagnation.T7.threshold` | < 0.5 分（绝对值） | 停滞检测 |
| `stagnation.T7.max_explore` | 2 轮 | 停滞检测 |
| `oscillation.window` | 3 轮 | 振荡检测 |
| `oscillation.band` | ±0.5 分 | 振荡检测 |
| `regression.threshold` | 跌破门禁阈值 | 回归检测 |
| `routing.high_confidence_threshold` | 0.8 | 路由匹配 |
| `routing.confirm_threshold` | 0.5 | 路由匹配 |
| `routing.ambiguity_gap` | 0.2 | 路由匹配 |

---

## 八、路由匹配参数

> 来源：入口命令 `commands/autoloop.md` 的置信度路由匹配机制

| 参数名 | 值 | 说明 |
|--------|----|------|
| `routing.high_confidence_threshold` | 0.8 | 匹配得分 ≥ 此值时自动选择模板，无需用户确认 |
| `routing.confirm_threshold` | 0.5 | 匹配得分在此值与 high_confidence 之间时，显示匹配结果请用户确认 |
| `routing.ambiguity_gap` | 0.2 | Top 2 模板得分差距 < 此值时，视为歧义，展示多个选项 |

**路由逻辑**：
- 得分 ≥ `high_confidence_threshold`（0.8）且无歧义 → 自动匹配
- 得分 ≥ `high_confidence_threshold`（0.8）但 Top 2 差距 < `ambiguity_gap`（0.2）→ 展示 Top 2-3 让用户选
- 得分在 `confirm_threshold`（0.5）到 `high_confidence_threshold`（0.8）之间 → 请用户确认
- 得分 < `confirm_threshold`（0.5）→ 展示全部模板
