# 经验库 v2 能力 backlog（P-05）

本文档将 `references/experience-registry.md` 中标注为 **v2 预留**、当前 **v1 未实现** 的能力汇总为 epic 清单，便于排期；**不**改变 v1 行为。与仓库级技术债索引交叉引用见 `docs/TECH_DEBT.md`。

| 主题 | Registry 参考 | 说明 |
|------|---------------|------|
| 金丝雀验证 | 生命周期图 `[v2] 金丝雀验证` | 同类任务 1 次验证后再晋升 |
| command 升级 | 写入 command、用户确认、patch+1 | 策略可执行为自动化命令 |
| 升级回滚 | v2 回滚段 | 连续 2 次 delta≤0 从 command 移除 |
| 层级标签 strategic/procedural/tool | 标注规则、读取优先级 | OBSERVE 按层级与预算筛选 |
| 表字段扩展 | `memory_layer`、`last_validated_date` 列 | v1 用 description `@日期` 等效 |
| 策略组合与消融 | 独立章节 | 多策略 A/B 与归因 |
| 协议变更效果追踪 | 协议变更效果追踪表 | 治理与回归基线 |

实现任一主题前请更新 `experience-registry.md` 与 `loop-protocol.md`，并补契约测试。
