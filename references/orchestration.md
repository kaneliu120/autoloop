# Orchestration — 多模板编排协议

## 概述

多模板编排（Pipeline）是 AutoLoop 的高级能力：将多个模板按依赖关系串联为一条执行链，实现"从调研到交付"的全自动流程。单模板是 AutoLoop 的原子单位，Pipeline 是分子。

**与其他文件的关系**：
- `loop-protocol.md`：定义单模板的 OODA 循环，Pipeline 中的每个节点遵循该循环
- `quality-gates.md`：每个节点的终止条件仍由对应模板的门禁决定
- `parameters.md`：每个节点的迭代参数独立，Pipeline 不覆盖节点参数
- `evolution-rules.md`：Pipeline 级别的进化（如跳过节点、插入节点）需用户确认

---

## 核心概念

### Pipeline（管道）

一条有序的模板执行链。每个节点是一个模板实例（T1-T8），节点之间通过**输出→输入映射**连接。

```text
Pipeline = [Node_1] → [Node_2] → ... → [Node_N]
```

### Node（节点）

Pipeline 中的一个执行单元。每个节点包含：
- **template**：使用的模板（T1-T8）
- **goal**：该节点的具体目标（从 Pipeline 目标拆解）
- **input_from**：输入来源（上游节点的输出字段）
- **output_fields**：本节点产出的供下游使用的字段
- **gate_override**：可选的门禁覆盖（只允许放宽，不允许收紧）

### 输出→输入映射（Handoff）

节点之间的数据传递规则。每个模板有标准化的输出字段：

| 模板 | 标准输出字段 | 说明 |
|------|------------|------|
| T1 Research | `findings_path`, `dimensions`, `key_conclusions` | 调研结果、维度列表、关键结论 |
| T2 Compare | `recommendation`, `ranked_options`, `comparison_matrix` | 推荐选项、排名、对比矩阵 |
| T5 Iterate | `final_kpi`, `improvement_log`, `best_strategy` | 最终KPI值、改进日志、最佳策略 |
| T6 Generate | `output_files`, `pass_rate`, `average_score` | 生成文件列表、通过率、平均分 |
| T4 Deliver | `deployed_url`, `verification_status`, `delivery_report` | 部署URL、验收状态、交付报告 |
| T7 Quality | `audit_report`, `score_summary`, `remaining_issues` | 审计报告、得分摘要、遗留问题 |
| T8 Optimize | `audit_report`, `score_summary`, `optimizations_applied` | 审计报告、得分摘要、已应用优化 |

**映射规则**：
- T1 → T2：T1 的 `key_conclusions` 自动成为 T2 的候选选项列表
- T2 → T4：T2 的 `recommendation` 自动填入 T4 的需求描述
- T4 → T7：T4 的交付代码路径自动成为 T7 的扫描目标
- T7 → T8：T7 的 `remaining_issues` 自动成为 T8 的优化起点
- 自定义映射：用户可在 Pipeline 配置中定义任意映射

---

## Pipeline 配置

Pipeline 在 `autoloop-plan.md` 中配置（当 `type: pipeline` 时激活）：

```markdown
## Pipeline 配置

type: pipeline
goal: {一句话描述端到端目标}

### 节点定义

| 序号 | 模板 | 目标 | 输入来源 | 门禁覆盖 |
|------|------|------|---------|---------|
| 1 | T1 | 调研{领域}的技术方案 | — | — |
| 2 | T2 | 对比 T1 发现的 Top 3 方案 | node_1.key_conclusions | — |
| 3 | T4 | 实现 T2 推荐的方案 | node_2.recommendation | — |
| 4 | T7 | 审查 T4 交付的代码质量 | node_3.deployed_url | — |

### 失败策略

node_failure: retry_then_pause
max_retries_per_node: 1
```

---

## 执行流程

### 阶段 1：Pipeline 初始化

1. 解析 Pipeline 配置，构建执行 DAG（当前版本仅支持线性链）
2. 为每个节点生成独立的 `autoloop-plan-node{N}.md`
3. 创建 `autoloop-pipeline-progress.md` 记录 Pipeline 级进度

### 阶段 2：节点执行

对每个节点按序执行：

```text
1. 读取上游节点的输出（首节点跳过）
2. 将输入映射到本节点的 plan 参数
3. 执行标准 OODA 循环（完全复用单模板逻辑）
4. 节点完成后，提取输出字段存入 pipeline-progress.md
5. 进入下一个节点
```

**关键原则**：节点内部的执行逻辑**完全不变** — Pipeline 只管节点之间的衔接，不干预节点内部的 OODA 循环。

### 阶段 3：Pipeline 完成

所有节点完成后：
1. 生成 Pipeline 最终报告（汇总所有节点的结果）
2. 在 `experience-registry.md` 中记录 Pipeline 级别的经验

---

## 失败处理

### 节点失败策略

| 策略 | 行为 | 适用场景 |
|------|------|---------|
| `retry_then_pause` | 节点失败→重试 1 次→仍失败则暂停等用户决策 | 默认策略 |
| `skip_and_continue` | 节点失败→标记为跳过→继续下一节点 | 非关键节点 |
| `abort_pipeline` | 节点失败→整条 Pipeline 终止 | 关键路径节点 |

### 回退规则

- **单节点回退**：节点内部按 `loop-protocol.md` 的标准回退机制处理
- **跨节点回退**：不支持自动跨节点回退。如果 T4 发现 T2 的推荐有问题，暂停 Pipeline，报告用户决策
- **理由**：跨节点回退涉及重新执行上游节点，成本高且不可预测。人工判断是否值得回退。

---

## 预定义 Pipeline 模板

### Research-to-Deliver（调研到交付）

```
T1 Research → T2 Compare → T4 Deliver → T7 Quality
```
适用：需要先调研技术方案，对比候选项，然后实现并审查。

### Quality-then-Optimize（质量后优化）

```
T7 Quality → T8 Optimize
```
适用：先审查现有代码质量，再针对发现的问题进行架构/性能优化。

### Research-to-Report（调研到报告）

```
T1 Research → T6 Generate
```
适用：先调研，然后基于调研结果批量生成内容（报告、文案等）。

---

## 约束

1. **线性链限制**：当前版本仅支持线性 Pipeline（A→B→C），不支持分支或并行节点。未来版本可扩展为 DAG。
2. **最大节点数**：单条 Pipeline 最多 5 个节点。超过 5 个建议拆分为多条 Pipeline。
3. **嵌套禁止**：Pipeline 节点不能包含另一个 Pipeline。
4. **门禁继承**：每个节点使用对应模板的标准门禁。`gate_override` 只能放宽（如覆盖率从 85% 降到 70%），不能收紧。

**gate_override 约束**:
- 仅允许将 Hard Gate 降级为 Soft Gate（记录但不阻塞），不允许完全移除门禁
- 必须在 pipeline plan 中声明 override 原因
- 不允许 override 安全性维度的 Hard Gate（P1=0 规则不可降级）
5. **经验独立**：每个节点独立产出经验条目到 `experience-registry.md`，Pipeline 级别仅记录整体执行效率。

---

## Pipeline 进度文件格式

`autoloop-pipeline-progress.md` 记录 Pipeline 级别的进度：

```markdown
# Pipeline Progress

## 概览
- Pipeline: {goal}
- 节点数: {N}
- 当前节点: {M}/{N}
- 状态: 执行中 / 已完成 / 已暂停

## 节点状态

| 节点 | 模板 | 状态 | 门禁得分 | 耗时（轮次）| 输出摘要 |
|------|------|------|---------|-----------|---------|
| 1 | T1 | 已完成 | 覆盖率92% | 3轮 | 发现5个候选方案 |
| 2 | T2 | 执行中 | — | 1轮 | — |
| 3 | T4 | 待执行 | — | — | — |
| 4 | T7 | 待执行 | — | — | — |

## Handoff 日志

| 从 | 到 | 传递字段 | 值摘要 |
|----|----|---------|--------|
| Node 1 | Node 2 | key_conclusions | [方案A, 方案B, 方案C] |
```
