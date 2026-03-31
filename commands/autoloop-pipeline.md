# autoloop-pipeline — 多模板链式执行

**触发词**：`pipeline`、`链式执行`、`调研到交付`、`端到端管道`

---

## 执行流程

### Step 1: 确定 Pipeline 模式

**用户已指定链**：直接解析节点序列。
**用户描述目标**：推荐匹配的预定义 Pipeline（见 `references/orchestration.md` 预定义模板）。

预定义 Pipeline 快速选择：
```
A) Research-to-Deliver: T1→T2→T4→T7（调研→对比→交付→审查）
B) Quality-then-Optimize: T7→T8（审查→优化）
C) Research-to-Report: T1→T6（调研→批量生成）
D) 自定义：手动指定节点序列
```

### Step 2: 为每个节点收集参数

对 Pipeline 中的每个节点：
1. 从 Pipeline 目标拆解该节点的具体目标
2. 确认输入来源（首节点=用户输入，后续节点=上游输出）
3. 确认门禁是否需要覆盖（默认不覆盖）

参数收集完成后，调用 `/autoloop:plan` 生成 `autoloop-plan.md`，其中 `type: pipeline`。

### Step 3: 初始化 Pipeline

1. 在工作目录创建 `autoloop-pipeline-progress.md`（格式见 `references/orchestration.md`）
2. 为每个节点创建独立的 plan 文件 `autoloop-plan-node{N}.md`
3. 创建标准运行时文件（findings/progress/results.tsv）

### Step 4: 逐节点执行

```text
for each node in pipeline:
  1. [Handoff] 读取上游节点输出，映射为本节点输入
     - 映射规则见 references/orchestration.md "输出→输入映射"表
     - 首节点跳过此步

  2. [Execute] 调度对应模板的 command 执行
     - T1 → /autoloop:research
     - T2 → /autoloop:compare
     - T3 → /autoloop:design
     - T4 → /autoloop:deliver
     - T5 → /autoloop:iterate
     - T6 → /autoloop:generate
     - T7 → /autoloop:quality
     - T8 → /autoloop:optimize

  3. [Gate Check] 节点完成后检查门禁
     - 全部通过 → 提取输出字段，更新 pipeline-progress.md，继续下一节点
     - 未通过 → 按失败策略处理（见下方）

  4. [Handoff Log] 记录传递的字段和值到 pipeline-progress.md
```

### Step 5: 失败处理

失败策略由 `autoloop-plan.md` 中的 `node_failure` 字段决定：

| 策略 | 行为 |
|------|------|
| `retry_then_pause`（默认）| 重试 1 次 → 仍失败 → 暂停，报告用户选择：重试/跳过/终止 |
| `skip_and_continue` | 标记跳过，下游节点使用已有的部分输出 |
| `abort_pipeline` | 整条 Pipeline 终止，输出当前已完成节点的结果 |

**跨节点回退**：不自动回退。暂停并报告用户决策。

### Step 6: Pipeline 完成

1. 汇总所有节点的结果到最终报告
2. 在 `experience-registry.md` 记录 Pipeline 级经验
3. 输出完成摘要

```text
Pipeline 完成摘要：
  目标：{goal}
  节点：{completed}/{total}
  总耗时：{N} 轮（跨 {M} 个节点）
  最终结果：{description}
```

---

## 节点间数据传递规则

### 自动映射（无需配置）

| 上游模板 | 下游模板 | 传递字段 | 说明 |
|---------|---------|---------|------|
| T1 | T2 | `key_conclusions` → 候选选项列表 | T1 发现 → T2 对比 |
| T2 | T4 | `recommendation` → 需求描述 | T2 推荐 → T4 实现 |
| T4 | T7 | 代码路径 → 扫描目标 | T4 交付 → T7 审查 |
| T7 | T8 | `remaining_issues` → 优化起点 | T7 遗留 → T8 优化 |

### 手动映射（Pipeline 配置中指定）

```markdown
| 从节点 | 到节点 | 字段 |
|--------|--------|------|
| node_1 | node_3 | node_1.findings_path → node_3.reference_doc |
```

---

## 约束

- 最多 5 个节点
- 仅支持线性链（不支持分支/并行）
- 不支持嵌套 Pipeline
- 每个节点内部完全复用单模板逻辑，Pipeline 不干预
