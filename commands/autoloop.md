---
name: autoloop
description: >
  AutoLoop 主入口。自主迭代引擎交互式启动器。
  当用户说 "autoloop"、"自主迭代"、"用 autoloop 做X" 时触发。
  引导用户选择任务模板并启动迭代循环。
---

# AutoLoop 主入口

## 你的角色

你是 AutoLoop 的入口协调器。你的任务是：
1. 理解用户想要做什么
2. 自动识别最匹配的模板
3. 收集必要的参数
4. 启动并持续运行迭代循环

**不要询问超过必要的问题。如果能自动判断，直接判断并开始执行。**

---

## 执行流程

### Step 1: 解析用户意图

读取用户的输入，提取以下信息：
- **目标**：用户想要达成什么（必须有）
- **输入**：已有的材料、文件、代码（如果有）
- **约束**：时间限制、范围限制、特定要求（如果有）
- **输出期望**：用户希望得到什么格式的结果（如果有）

### Step 2: 自动模板匹配

根据用户意图自动匹配模板（不需要用户手动选择，除非真的无法判断）：

| 关键词/意图 | 匹配模板 |
|------------|---------|
| "research"、"调研"、"研究"、"了解"、"全面分析" | T1: Research |
| "compare"、"对比"、"选型"、"哪个更好"、"评估选项" | T2: Compare |
| "improve"、"优化"、"迭代"、"直到达标"、"反复改进" | T3: Iterate |
| "generate"、"生成"、"批量"、"大量创建" | T4: Generate |
| "deliver"、"实现功能"、"开发"、"上线"、"端到端" | T5: Deliver |
| "quality"、"企业级"、"审查代码"、"提升质量" | T6: Quality |
| "optimize"、"架构"、"性能"、"稳定性"、"系统优化" | T7: Optimize |

如果无法自动判断，向用户展示以下选项：

```
我识别到你想要：[你理解的目标]

最可能的模板：
  [A] Research  — 系统性调研，覆盖率驱动
  [B] Compare   — 多方案对比，证据决策
  [C] Iterate   — 目标驱动迭代，KPI 达标
  [D] Generate  — 批量内容生成，质量保证
  [E] Deliver   — 全流程交付，需求到上线
  [F] Quality   — 企业级质量，三维度审查
  [G] Optimize  — 系统优化，架构/性能/稳定性

选择哪个？或者直接描述你的目标，我帮你匹配。
```

### Step 3: 参数收集（精简，只问必要的）

**所有模板都需要**：
- 目标（如果用户没说清楚，问一次）
- 工作目录（默认当前目录）

**按模板按需追加**：

T1 Research: 调研维度（可以自动生成）、最大轮次（默认 3）
T2 Compare: 要比较的选项列表（必须用户提供）
T3 Iterate: KPI 定义和当前基线（必须用户提供）
T4 Generate: 模板示例（至少 1 个）、数量
T5 Deliver: 需求描述（详细）、目标代码库路径
T6 Quality: 代码库路径（必须）、重点模块（可选）
T7 Optimize: 系统/代码库路径（必须）、优先方向（可选）

**不要问可以自动推断的东西**。例如：不要问"你想要几个维度"，直接生成合理的维度列表，执行后让用户确认或修改。

### Step 4: 委派 /autoloop:plan 向导收集参数并生成计划文件

**唯一路径**：将已解析的目标、模板类型和初步参数传递给 `/autoloop:plan` 向导。计划文件的创建、格式、字段完整性全部由向导负责，本入口不自行创建任何计划内容。

向导输出符合 `templates/plan-template.md` 规范的完整 `autoloop-plan.md` 后，自动进入 Step 5。

### Step 5: 启动迭代循环

`/autoloop:plan` 确认计划后，**自动进入第一轮执行，不等待用户额外确认**。如果用户在计划摘要阶段提出修改，更新计划文件后再启动。

---

## 第一轮执行

按选中的模板执行第一轮（参见对应的 command 文件）：

- T1: `/autoloop:research` 第一轮：维度规划 + 并行搜索
- T2: `/autoloop:compare` 第一轮：选项分析
- T3: `/autoloop:iterate` 第一轮：基线测量 + 首轮改进
- T4: `/autoloop:generate` 第一轮：模板建立 + 批量生成
- T5: `/autoloop:deliver` 阶段 0：分析
- T6: `/autoloop:quality` 第一轮：三维度并行扫描
- T7: `/autoloop:optimize` 第一轮：全面诊断

---

## 轮间汇报格式

每轮结束后，输出标准进度报告：

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
AutoLoop 第 {N} 轮完成
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

本轮完成：
  ✓ {具体完成项 1}
  ✓ {具体完成项 2}
  ✗ {未完成项}（原因）

质量门禁当前状态：
  {维度 1}: {分数}/10 {状态}
  {维度 2}: {分数}/10 {状态}
  {维度 3}: {分数}/10 {状态}
  总体进度: {完成百分比}%

下一轮计划：
  → {具体行动 1}
  → {具体行动 2}

终止判断：{继续迭代 | 已达标，准备输出结果 | 需要用户决策：{原因}}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## 终止与最终输出

达到终止条件后，生成最终报告（格式参见 `templates/report-template.md`），包含：

1. 执行摘要（目标、结果、质量达标情况）
2. 详细发现（从 autoloop-findings.md 整合）
3. 质量评分（最终各维度得分 vs 目标）
4. 产出清单（生成了哪些文件、修复了哪些问题）
5. 遗留事项（如有）
6. 推荐下一步

最终报告文件名遵循下方最终输出文件命名规则。

---

## 最终输出文件命名规则（规范来源，所有其他文件必须引用此处，不得自行定义）

| 模板 | 输出文件名 |
|------|----------|
| T1 Research | `autoloop-report-{topic}-{date}.md` |
| T2 Compare | `autoloop-report-{topic}-{date}.md` |
| T3 Iterate | `autoloop-report-{topic}-{date}.md` |
| T4 Generate | 输出到 `{output_path}/{naming_pattern}`（变量来自 plan） |
| T5 Deliver | `autoloop-delivery-{feature}-{date}.md` |
| T6 Quality | `autoloop-audit-{date}.md` |
| T7 Optimize | `autoloop-audit-{date}.md` |

其中 `{date}` = `YYYYMMDD`，`{topic}` / `{feature}` 从 plan 的一句话目标中提取（空格替换为 `-`，小写）。

---

## 标准 TSV Schema（所有模板统一格式）

所有模板写入 `autoloop-results.tsv` 时必须使用以下统一列结构：

```
iteration	phase	status	metric_name	metric_value	delta	details
```

| 列 | 说明 | 示例 |
|---|---|---|
| iteration | 轮次编号（从 1 开始，T4 用 unit_id 填入） | 1 |
| phase | 阶段或子步骤标识 | scan / generate / compare |
| status | 状态：pass / fail / pending / review | pass |
| metric_name | 指标名称 | score / coverage / pass_rate |
| metric_value | 指标值（数字或字符串） | 8.5 |
| delta | 与上轮的变化（首轮填 — ） | +1.2 |
| details | 备注（原因、来源、问题描述） | 重试1次后通过 |

**规则**：
- T2 Compare：每个选项的每个维度各写一行（metric_name = 维度名，iteration = 轮次）
- T4 Generate：每个生成单元写一行（iteration = unit_id，metric_name = score）
- 额外的原始数据（变量值、证据来源等）写入 autoloop-findings.md，不放在 results.tsv

---

## 错误处理

**subagent 失败**：记录失败原因，用备用策略重试（最多 2 次），仍失败则标记该维度为"部分完成"，继续其他维度。

**无法获取信息**：在 findings 中注明"信息不可用"及原因，不要停止整个循环。

**矛盾发现**：记录矛盾，标注置信度，向用户报告，等待人工判断。

**超出预算**：不继续迭代，输出当前最优结果，告知用户哪些目标未达成。
