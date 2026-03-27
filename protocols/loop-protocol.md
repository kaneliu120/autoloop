# Loop Protocol — OODA 迭代循环规范

## 统一参数词汇表

**规则**：所有 AutoLoop 文件（commands/、protocols/、templates/）中涉及下列概念时，必须使用下表中的变量名，不得自行发明同义词。

| 变量名 | 类型 | 用途 | 收集时机 | 适用模板 | 必填/可选 | 条件 |
|--------|------|------|---------|---------|----------|------|
| project_type | enum | 项目类型，决定哪些变量和模块被激活 | plan | T5/T6/T7 | 必填 | — |
| deploy_target | string | 部署目标主机/环境（如 sip-server、prod-01）| plan | T5 | 可选 | 仅当需要远程部署时（script/library 通常 N/A） |
| deploy_command | string | 部署执行命令（完整命令，如 gcloud compute ssh ...）| plan | T5 | 可选 | 同 deploy_target |
| service_list | string[] | 服务名称列表（如 [sip-backend, sip-worker]）| plan | T5 | 可选 | 仅当有常驻服务时（script/library = N/A） |
| service_count | int | 服务数量（自动计算 = len(service_list)，不手动填写）| 自动 | T5 | 自动 | = len(service_list)，service_list = N/A 时此项也 N/A |
| health_check_url | string | 健康检查 URL（如 https://example.com/api/health）| plan | T5 | 可选 | 仅当有 HTTP 服务时 |
| acceptance_url | string | 线上验收 URL（如 https://example.com）| plan | T5 | 可选 | 仅当有浏览器验收入口时（纯API后端可填 N/A） |
| doc_output_path | string | 方案文档输出目录（绝对路径）| plan | T5 | 必填 | 所有 project_type |
| syntax_check_cmd | string | 语法检查裸命令（如 python3 -m py_compile 或 npx tsc --noEmit），不含文件参数占位符；文件参数由 syntax_check_file_arg 控制是否追加 | plan | T5/T6/T7 | 必填 | 所有 project_type |
| syntax_check_file_arg | boolean | 语法检查命令是否接受单文件参数（python3 -m py_compile → true；npx tsc --noEmit → false）| plan | T5/T6/T7 | 必填 | 所有 project_type |
| new_router_name | string | 本次新增的 router 变量名（如 comments_router；无新路由填 N/A）| plan | T5 | 条件必填 | 仅当 project_type ∈ {backend-api, fullstack} 且有新路由时；否则填 N/A |
| main_entry_file | string | 主入口文件绝对路径（如 /project/backend/main.py 或 /project/src/app.ts）| plan | T5/T6 | 条件必填 | 仅当 project_type ∈ {backend-api, fullstack} 时；其他类型可填项目主文件或 N/A |
| output_path | string | 输出目录绝对路径（默认 {工作目录}/autoloop-output/）| plan | T4 | 必填 | T4 |
| naming_pattern | string | 文件命名规则（如 {template_name}-{index}.md）| plan | T4 | 必填 | T4 |
| key_assumptions | list[{name, current_value, unit}] | T2 对比中的关键假设（结构化列表，每项含名称+当前值+单位，用于敏感性分析）| plan | T2 | 必填 | T2 |
| migration_check_cmd | string | 数据库迁移状态验证命令（如 python -m alembic current && python -m alembic check；无迁移填 N/A）| plan | T5 | 条件必填 | 仅当 project_type ∈ {backend-api, fullstack, data-pipeline} 且有数据库迁移时；否则 N/A |
| frontend_dir | string | 前端代码目录绝对路径（如 /project/frontend）| plan | T5 | 条件必填 | 仅当 project_type ∈ {fullstack, frontend-only} 时；否则 N/A |

**project_type 枚举值**：

```
backend-api    — 后端API（有路由、有数据库）
fullstack      — 全栈（前端+后端+数据库）
frontend-only  — 纯前端（无后端路由、无数据库）
script         — 脚本/CLI工具（无服务、无路由）
data-pipeline  — 数据管线/ETL（可能有数据库但无API路由）
library        — 库/SDK（无服务、无部署、有发布）
```

### 项目类型与变量激活矩阵

| 变量 | backend-api | fullstack | frontend-only | script | data-pipeline | library |
|------|:-----------:|:---------:|:-------------:|:------:|:-------------:|:-------:|
| deploy_target | ✓ | ✓ | ✓ | ○ | ✓ | ○ |
| deploy_command | ✓ | ✓ | ✓ | ○ | ✓ | ○ |
| service_list | ✓ | ✓ | ○ | ○ | ○ | ○ |
| health_check_url | ✓ | ✓ | ○ | ○ | ○ | ○ |
| acceptance_url | ○ | ✓ | ✓ | ○ | ○ | ○ |
| new_router_name | ✓ | ✓ | ○ | ○ | ○ | ○ |
| main_entry_file | ✓ | ✓ | ○ | ○ | ○ | ○ |
| migration_check_cmd | ✓ | ✓ | ○ | ○ | ✓ | ○ |
| frontend_dir | ○ | ✓ | ✓ | ○ | ○ | ○ |
| syntax_check_cmd | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |

✓ = 必填（必须提供有效值） ○ = 可选（填 N/A 跳过相关流程）

---

## 统一状态枚举

所有文件中涉及问题状态和策略评价时，必须使用下列枚举值，不得使用其他说法。

**问题状态（Problem Status）**：
```
新发现 | 已修复 | 待处理 | 跨轮遗留
```

**策略评价（Strategy Rating）**：
```
保持 | 避免 | 待验证
```

**生命周期状态（Lifecycle Status）**：
```
准备开始 | 进行中 | 完成 | 预算耗尽 | 用户中断 | 阻塞终止 | 达标终止
```

**终止原因（Termination Reason）**：
```
达标终止 | 预算耗尽 | 用户中断 | 阻塞终止
```

---

## 统一输出文件命名规则（规范来源）

所有文件在引用最终报告文件名时，必须引用本表，不得在其他文件中重新定义。

| 模板 | 最终报告文件名 | 过程文件 |
|------|--------------|---------|
| T1 Research | `autoloop-report-{topic}-{date}.md` | plan + findings + progress + results.tsv |
| T2 Compare | `autoloop-report-{topic}-{date}.md` | 同上 |
| T3 Iterate | `autoloop-report-{topic}-{date}.md` | 同上 |
| T4 Generate | `{output_path}/{naming_pattern}` (生成内容) + `autoloop-report-{topic}-{date}.md` (汇总报告) | 同上 |
| T5 Deliver | `autoloop-delivery-{feature}-{date}.md` | 同上 |
| T6 Quality | `autoloop-audit-{date}.md` | 同上 |
| T7 Optimize | `autoloop-audit-{date}.md` | 同上 |

其中 `{date}` = `YYYYMMDD`，`{topic}` / `{feature}` 从 plan 的一句话目标中提取（空格替换为 `-`，小写）。

---

## 统一 TSV Schema（规范来源）

所有模板写入 `autoloop-results.tsv` 时必须使用以下统一列结构，不得在其他文件中重新定义。

```
iteration	phase	status	metric_name	metric_value	delta	details
```

| 列 | 说明 | 示例 |
|---|---|---|
| iteration | 轮次编号（从 1 开始）；T4 用 unit_id 填入 | 1 |
| phase | 阶段或子步骤标识 | scan / generate / compare |
| status | 状态：pass / fail / pending / review | pass |
| metric_name | 指标名称 | score / coverage / pass_rate |
| metric_value | 指标值（数字或字符串） | 8.5 |
| delta | 与上轮的变化（首轮填 — ） | +1.2 |
| details | 备注（原因、来源、问题描述） | 重试1次后通过 |

**使用约定（各模板行粒度）**：
- T1/T3/T5/T6/T7：每轮一行，`iteration` = 轮次号
- T2 Compare：每选项每维度一行，`iteration` = 轮次号，`details` 包含选项名（如 `option=选项A`）
- T4 Generate：每生成单元一行，`iteration` = unit_id，`metric_name` = `score`，`details` 包含单元状态摘要

额外的原始数据（变量值、证据来源等）写入 `autoloop-findings.md`，不放在 results.tsv。

---

## Bootstrap 规则（plan 完成后立即执行）

**plan 向导完成后，立即创建以下文件（不等待第 1 轮 OBSERVE）：**

```
1. autoloop-plan.md         （已由向导创建）
2. autoloop-findings.md     （从 templates/findings-template.md 创建空白实例）
3. autoloop-progress.md     （从 templates/progress-template.md 创建空白实例）
4. autoloop-results.tsv     （写入表头行：iteration\tphase\tstatus\tmetric_name\tmetric_value\tdelta\tdetails）
```

所有 4 个文件必须在第 1 轮 OBSERVE 开始前存在。创建后在 autoloop-plan.md 的"输出文件"表中将状态从"待创建"更新为"已创建"。

---

## 概述

每次 AutoLoop 执行都遵循标准的 8 阶段 OODA 循环。本文档定义每个阶段的具体行为、输入输出规范和状态机转换规则。

---

## 状态机

```
[INIT]
  ↓ Bootstrap：创建 plan + findings + progress + results.tsv
[OBSERVE] ←─────────────────────────────────────────────┐
  ↓ Step 0（Round 2+）：读取 findings.md 反思章节           │
  ↓ 扫描现状                                              │
[ORIENT]                                                 │
  ↓ 分析差距，制定策略                                    │
[DECIDE]                                                 │
  ↓ 确定本轮行动计划                                      │
[ACT]                                                    │
  ↓ 调度 subagents 执行                                  │
[VERIFY]                                                 │
  ↓ 核查输出质量                                         │
[SYNTHESIZE]                                             │
  ↓ 整合输出，解决矛盾                                    │
[EVOLVE]                                                 │
  ↓ 判断终止 or 进入下一轮                                │
[REFLECT]                                                │
  ↓ 写入 findings.md 4层结构表 ──── 继续 ─────────────────┘
    ↓ 终止
  [TERMINATE]
      ↓
  生成最终报告

[AWAIT_USER]  ← 从 EVOLVE / Phase 0.5 / Phase 5 进入
  ↓ 等待人工输入（"confirmed" / "verified" / 修改意见）
  ↓ 收到输入后恢复到下一阶段
```

**AWAIT_USER 状态**：当需要人工确认时（T5 Phase 0.5 文档确认、T5 Phase 5 线上验收、以及任何 blocking gate），状态机进入 AWAIT_USER。系统在此状态停止自动推进，等待用户输入。用户输入 `confirmed`（Phase 0.5）或 `verified`（Phase 5）后，恢复到下一阶段。用户提出修改意见时，先处理修改，再自动恢复。

**状态不可逆**：不能从 ACT 回退到 DECIDE（当轮的决策在 ACT 开始后锁定）。
**错误处理**：任何阶段发生错误 → 写入 progress.md → 尝试恢复 → 如无法恢复则进入 TERMINATE 并说明原因。

---

## OBSERVE — 观察

### 输入
- `autoloop-plan.md`（任务计划）
- `autoloop-progress.md`（历史进度）
- `autoloop-findings.md`（已有发现，包含上轮 REFLECT 记录）
- 代码库当前状态（如果是工程类任务）

### OBSERVE Step 0: 读取上轮反思（Round 2+ 必执行）

在扫描当前状态之前，先读取 `autoloop-findings.md` 中的反思章节（**4 层结构表**）：

1. **遗留问题** → 本轮优先处理（状态为"待处理"或"跨轮遗留"的问题）
2. **有效策略** → 本轮 DECIDE 优先选用（评价为"保持"的策略）
3. **无效策略** → 本轮 DECIDE 排除，不重复尝试（评价为"避免"的策略）
4. **已识别模式** → 如果有系统性根因，本轮需要改变方法论而非继续修补
5. **瓶颈信息** → 如果某维度连续卡住，本轮尝试突破性策略
6. **经验教训** → 调整本轮的方法和预期

这确保每一轮都带着上轮的认知进入，而非从零开始。

**T6/T7 的 OBSERVE Step 0 同样适用**：T6 和 T7 在 Round 2+ 执行 OBSERVE 时，必须首先读取 findings.md 的反思章节，获取遗留问题清单、无效修复模式和已识别的系统性根因，再制定本轮修复策略。

### 第1轮 Bootstrap 规则

**第1轮 OBSERVE 没有上轮 VERIFY 的结果，必须执行基线采集（baseline collection）代替：**

- **知识类任务（T1/T2/T3/T4）**：当前发现数 = 0，已覆盖维度 = 0，所有质量门禁得分 = 0。将此作为 iteration 0 基线写入 progress.md。
- **工程类任务（T5/T6/T7）**：运行初始检测命令获取基线分数（按 `syntax_check_cmd` 扫描所有文件、code-reviewer 全量扫描），将检测结果作为 iteration 0 基线写入 progress.md。

基线写入格式：
```markdown
### 基线（Iteration 0）
- 执行时间：{ISO 8601}
- 基线来源：第1轮初始采集（无历史数据）
- 各维度得分：{每个维度: 0 或初始检测值}
- 说明：首轮无先验数据，以此基线作为第1轮 OBSERVE 的"上轮结果"
```

### 必须回答的问题

1. **目标状态是什么？** — 从 plan.md 读取质量门禁目标值
2. **当前状态是什么？** — 最新的质量门禁实际值（上轮 VERIFY 的结果；第1轮使用 iteration 0 基线）
3. **差距是什么？** — 目标值 - 当前值，每个维度
4. **时间/预算剩余多少？** — 已用轮次 / 最大轮次，计算剩余百分比
5. **上一轮有什么意外发现？** — 从 findings.md 读取上轮追加的内容（第1轮：无，填写"无历史发现"）

### 输出
OBSERVE Summary（写入 progress.md 当前轮次区块）：

```markdown
### 观察（第 N 轮）
- 维度差距：{每个维度：当前值 / 目标值 / 差距}
- 剩余预算：{X}%（已用 N 轮 / 最大 M 轮）
- 本轮观察重点：{最需要解决的 1-2 个维度}
- 上轮遗留：{如有未完成项}
```

---

## ORIENT — 定向分析

### 目标
将观察到的差距转化为可执行的分析结论：**为什么还有差距？怎么解决？**

### 分析框架

**差距成因分析**（选择适用的）：
- 信息不足（未覆盖的维度/来源）
- 质量不足（找到了但证据不够强）
- 策略无效（方法对，但在这个领域没有信息）
- 认知偏差（搜索关键词限制了结果）
- 资源约束（时间/预算不足）

**策略调整规则**：

| 场景 | 分析结论 |
|------|---------|
| 同一维度连续 2 轮无进展（改善 < 当前分数的 3%，相对值）| 当前方法已到极限，需要换方向 |
| 多个维度同时落后 | 先解决最高优先级的，不要分散 |
| 发现计划外的重要维度 | 评估是否扩展范围（考虑预算） |
| 发现 P0 问题（数据丢失/安全漏洞）| 立即提升，暂停其他工作 |

### 输出
ORIENT Summary：

```markdown
### 定向（第 N 轮）
- 主要差距原因：{原因分析}
- 本轮策略：{策略名称 + 一句话说明}
- 范围调整：{扩展/收窄/不变 + 原因}
- 预期改善：{本轮预计能提升多少分}
```

---

## DECIDE — 决策

### 目标
制定**具体可执行**的行动计划：谁做什么，用什么工具，期望什么结果。

### 决策原则

**并行优先**：能并行的任务一定并行。判断标准：
- 任务 A 的输出不是任务 B 的输入 → 并行
- 任务 A 和 B 操作不同文件 → 并行

**最小化范围**：每轮只做本轮最重要的事，不要一次性做所有事。

**有 fallback**：每个行动必须有备用策略（如果 subagent 找不到信息，下一步怎么办）。

**优先选用"保持"策略**：本轮 DECIDE 优先使用 findings.md 反思章节中标记为"保持"的策略；排除标记为"避免"的策略。

### 行动计划格式

```markdown
### 决策（第 N 轮）

本轮行动：

| # | 行动 | 执行者 | 输入 | 期望输出 | 可并行？ |
|---|------|--------|------|---------|---------|
| 1 | {具体行动} | {agent 类型} | {文件/信息} | {具体产出} | {是/否} |
| 2 | {具体行动} | {agent 类型} | {文件/信息} | {具体产出} | {是} |

执行顺序：
- 并行：行动 2 + 行动 3（独立）
- 串行：行动 1 完成后执行行动 4（4 依赖 1 的输出）

Fallback 策略：
- 行动 1 失败 → {备用方案}
- 行动 2 无结果 → {备用方案}
```

---

## ACT — 行动

### 目标
按决策计划调度 subagents 执行，收集所有输出。

### Subagent 调度规范

每次调度必须提供完整上下文（详见 `protocols/agent-dispatch.md`）：
1. 角色定义（你是 X subagent）
2. 具体任务（可操作，不是方向）
3. 输入（文件绝对路径、信息内容）
4. 约束（不可做什么）
5. 验收标准（完成的判断条件）
6. 输出格式（明确的结构）

### 执行记录

每个 subagent 完成后，记录到 progress.md：

```markdown
### 行动记录（第 N 轮）

| # | 执行者 | 任务 | 状态 | 结果摘要 |
|---|--------|------|------|---------|
| 1 | researcher | 调研{维度} | 完成 | 发现{N}个关键信息点 |
| 2 | code-reviewer | 审查{文件} | 完成 | 发现{N}个P1问题 |
| 3 | backend-dev | 修复{问题} | 失败 | 原因：{错误信息} |
```

### 统一重试上限规则

**默认重试上限 = 2 次**（适用于所有模板和所有 subagent）。

例外：delivery 模板（T5）因包含人工确认环节，允许 Phase 2 审查-修复循环最多 **3 轮**。所有其他模板遵守 2 次上限。

各协议文件中涉及重试/回退次数的描述均以本规则为准：
- `agent-dispatch.md` 中 subagent 重试 → 最多 2 次
- `delivery-phases.md` 中 Phase 2 修复-审查循环 → 最多 3 轮（仅 T5，因含人工确认）
- `delivery-phases.md` 中其他阶段回退 → 最多 2 次（与本规则对齐）

### 失败处理

subagent 失败时的处理流程：
1. 记录失败原因
2. 尝试备用策略（最多 2 次，遵守统一重试上限）
3. 如备用策略也失败 → 标记该任务为"部分完成"，继续其他任务
4. 在 VERIFY 阶段说明影响

---

## VERIFY — 验证

### 目标
客观评估本轮执行结果的质量，更新所有维度的得分。

### 验证规则

**必须量化**：不接受"好多了"，只接受"从 6.2 提升到 7.8"。

**不信任 subagent 自评**：每个 subagent 对自己工作的评价需要独立验证：
- 代码类：运行 `{syntax_check_cmd}`（按 `syntax_check_file_arg` 决定是否附加文件参数）
- 调研类：检查信息来源数量和质量
- 修复类：重新运行受影响的 reviewer

**回归检查**：本轮的修复是否引入了新问题？
- 工程类：运行所有受影响文件的编译验证
- 内容类：检查前几轮的结论是否仍然成立

### 验证输出格式

```markdown
### 验证（第 N 轮）

得分更新：
| 维度 | 上轮 | 本轮 | 变化 | 目标 | 状态 |
|------|------|------|------|------|------|
| {维度 1} | {分} | {分} | {+/-} | {目标} | 达标/未达标 |

本轮改进详情：
- {改进 1}：{具体改善了什么}
- {改进 2}：...

新发现的问题（如有）：
- {问题}：{描述，将在下轮处理}

验证结论：{本轮质量可信 / 部分结果待确认}
```

---

## SYNTHESIZE — 整合

### 目标
合并所有 subagent 的输出，解决矛盾，更新核心文件。

### 整合步骤

1. **合并发现**：将本轮所有 subagent 的输出追加到 `autoloop-findings.md`
2. **解决矛盾**：
   - 同一事实不同说法 → 列出两者，说明依据
   - 同一文件的不同问题 → 合并，避免重复
   - 冲突的修复建议 → 选择更安全的（改动更小、影响更小）
3. **更新结构化数据**：如果有 autoloop-results.tsv，同步更新
4. **归档本轮**：将本轮产出标注轮次，便于后续追溯

### 矛盾解决规则

| 矛盾类型 | 解决规则 |
|---------|---------|
| A 说"有问题"，B 说"没问题" | 以更保守的（有问题）为准，记录 B 的理由 |
| 两个 subagent 对同一代码的评分差 > 2 | 运行第三次验证（或人工判断） |
| 修复方案互相冲突 | 选择改动最小的，记录弃用的原因 |

---

## EVOLVE — 进化

### 目标
基于本轮结果，决定下一轮策略（或终止）。

### 终止层级

AutoLoop 有四种终止路径，按优先级排列：

1. **质量门禁全部达标** → 成功终止 → TERMINATE（达标）
2. **用户中断** → 暂停终止 → TERMINATE（中断），保存进度，说明恢复方法
3. **预算耗尽（达到最大轮次）** → 预算终止 → TERMINATE（预算耗尽），输出当前最优结果
4. **阻塞（连续 2 轮无任何维度进展）** → 阻塞终止 → TERMINATE（阻塞），上报原因，列出所需用户输入

### 决策树

```
所有质量门禁达标？
  └─ 是 → 成功终止 → TERMINATE（达标）
  └─ 否 →
      达到最大轮次？
        └─ 是 → 预算终止 → TERMINATE（预算耗尽，输出当前最优结果）
        └─ 否 →
            连续 2 轮所有维度均无进展（所有维度改善均 < 相对 3%）？
              └─ 是 → 阻塞终止 → TERMINATE（阻塞），输出当前最优结果并通知用户
                        （列出阻塞原因和所需的用户输入，进入 AWAIT_USER）
              └─ 否 →
                  连续 2 轮同一维度无进展（改善 < 当前分数的 3%，相对值）？
                    （示例：当前 80%，阈值 = 2.4%；当前 7/10 分，阈值 = 0.21 分）
                    └─ 是 → 换策略（记录已尝试方法到策略历史）
                    └─ 否 →
                        剩余预算 < 20%？
                          └─ 是 → 聚焦最高优先级维度
                          └─ 否 → 继续标准策略
              → 进入下一轮 OBSERVE
```

### 进化输出

```markdown
### 进化决策（第 N 轮结束）

终止判断：{继续 / 达标终止 / 预算终止 / 阻塞终止}

如继续：
- 下一轮重点：{维度}
- 策略调整：{调整内容 + 原因}
- 范围变更：{变更内容 + 原因}
- 预计达标轮次：{估计}

如终止：
- 终止原因：{具体原因}
- 未达标维度：{列表 + 差距}
- 建议后续行动：{用户可以做什么}
```

---

## REFLECT — 反思

### Phase 8: REFLECT（反思）

> 每轮结束的认知沉淀。不是可选步骤，是强制环节。反思的价值在于被下一轮 OBSERVE Step 0 读取和使用。

**输入**: 本轮所有阶段的执行结果、VERIFY 的质量分数、EVOLVE 的决策

**4 层反思（必须写入 findings.md 的 4 层结构表，不得只写 bullet points）：**

#### 第 1 层：问题登记（Problem Registry）

写入 findings.md 的"问题清单（REFLECT 第 1 层）"表：

| 轮次 | 问题描述 | 来源 | 严重度 | 状态 | 根因分析 |
|------|---------|------|--------|------|---------|
| R{N} | {问题} | {subagent/验证步骤} | P1/P2/P3 | **新发现** / **已修复** / **待处理** / **跨轮遗留** | {为什么} |

状态字段必须使用统一状态枚举（新发现 / 已修复 / 待处理 / 跨轮遗留）。

#### 第 2 层：策略复盘（Strategy Review）

写入 findings.md 的"策略评估（REFLECT 第 2 层）"表：

| 轮次 | 策略 | 效果评分(1-5) | 分数变化 | 保持 \| 避免 \| 待验证 | 原因 |
|------|------|-------------|---------|---------------------|------|
| R{N} | {策略描述} | {1-5} | {+/-分数} | **保持** / **避免** / **待验证** | {为什么有效/无效} |

评价字段必须使用统一策略评价枚举（保持 / 避免 / 待验证）。

#### 第 3 层：模式识别（Pattern Recognition）

写入 findings.md 的"模式识别（REFLECT 第 3 层）"部分：
- 反复出现的问题类型（系统性根因分析）
- 收益递减信号（连续轮次改善幅度下降趋势）
- 跨维度关联（改 A 导致 B 变化）
- 瓶颈识别（哪个维度/领域一直卡住）

#### 第 4 层：经验沉淀（Lessons Learned）

写入 findings.md 的"经验教训（REFLECT 第 4 层）"部分：
- 本轮验证了什么假设（成立 / 推翻）
- 可泛化的方法论（下次类似任务可直接复用）
- 对 AutoLoop 自身流程的改进建议

**关键规则**:
- REFLECT 必须写入 `autoloop-findings.md` 的 4 层结构表，不能只在思考中完成
- 每轮的反思记录是下一轮 OBSERVE Step 0 的必读输入
- 问题清单是累积的（跨轮追踪状态变化）
- 策略评估构建"策略效果知识库"供 DECIDE 使用
- 状态和评价字段必须使用本文档定义的统一枚举值

---

## TERMINATE — 终止

### 终止类型处理

**达标终止**：
1. 更新 plan.md 状态为"完成"
2. 生成最终报告（文件名见本文档"统一输出文件命名规则"表）
3. 清理临时文件（可选）

**预算终止**：
1. 更新 plan.md 状态为"预算耗尽"
2. 生成"当前最优结果"报告
3. 明确标注哪些目标未达成

**用户中断**：
1. 立即保存当前进度
2. 生成中间报告（标注"用户中断"）
3. 说明恢复方法（下次运行如何从当前状态继续）

**阻塞终止**：
1. 清楚说明阻塞原因
2. 列出需要用户提供的信息
3. 说明提供后如何继续

---

## 循环日志格式

每次完整循环在 `autoloop-progress.md` 产生标准格式日志：

```markdown
---

## 迭代循环 #{N}
**开始时间**：{ISO 8601}
**状态**：{进行中 → 完成}

### 观察
{OBSERVE 输出}

### 定向
{ORIENT 输出}

### 决策
{DECIDE 输出}

### 行动记录
{ACT 输出}

### 验证
{VERIFY 输出}

### 整合（SYNTHESIZE）
发现的矛盾：{矛盾列表，无则填"无"}
解决的矛盾：{解决方式，无则填"无"}
合并的数据：{追加到 findings.md 的条数 + 其他更新文件}
新洞察：{整合后才显现的模式或规律，无则填"无"}

### 进化决策
{EVOLVE 输出}

### 反思（REFLECT）
- **问题登记**: {本轮新发现 N 个，修复 M 个，遗留 K 个} — 已写入 findings.md 第 1 层表
- **策略复盘**: {本轮策略} — 效果评分 {1-5}/5，{保持/避免/待验证} — 已写入 findings.md 第 2 层表
- **模式识别**: {新发现的模式 / 无新模式} — 已写入 findings.md 第 3 层
- **经验教训**: {本轮最重要的一条经验} — 已写入 findings.md 第 4 层
- **下轮指导**: {基于反思，下轮应该重点做什么、避免做什么}

**结束时间**：{ISO 8601}
**耗时**：{分钟}

---
```
