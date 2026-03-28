# Loop Protocol — OODA 迭代循环规范

**协议版本**：1.0.0

> 版本格式：{major}.{minor}.{patch} — major=流程变更，minor=维度/门禁/参数变更，patch=锚点/样本/经验补充。变更记录见 evolution-rules.md。

## 统一参数词汇表

**规则**：所有 AutoLoop 文件（commands/、protocols/、templates/）中涉及下列概念时，必须使用下表中的变量名，不得自行发明同义词。

| 变量名 | 类型 | 用途 | 收集时机 | 适用模板 |
|--------|------|------|---------|---------|
| deploy_target | string | 部署目标主机/环境（如 sip-server、prod-01）| plan | T5 |
| deploy_command | string | 部署执行命令（完整命令，如 gcloud compute ssh ...）| plan | T5 |
| service_list | string[] | 服务名称列表（如 [sip-backend, sip-worker]）| plan | T5 |
| service_count | int | 服务数量（自动计算 = len(service_list)，不手动填写）| 自动 | T5 |
| health_check_url | string | 健康检查 URL（如 https://example.com/api/health）| plan | T5 |
| acceptance_url | string | 线上验收 URL（如 https://example.com）| plan | T5 |
| doc_output_path | string | 方案文档输出目录（绝对路径）| plan | T5 |
| syntax_check_cmd | string | 语法检查命令（如 python3 -m py_compile {file} 或 npx tsc --noEmit）| plan | T5/T6/T7 |
| syntax_check_file_arg | boolean | 语法检查命令是否接受单文件参数（python3 -m py_compile → true；npx tsc --noEmit → false）| plan | T5/T6/T7 |
| new_router_name | string | 本次新增的 router 变量名（如 comments_router；无新路由填 N/A）| plan | T5 |
| main_entry_file | string | 主入口文件绝对路径（如 /project/backend/main.py 或 /project/src/app.ts）| plan | T5/T6 |
| output_path | string | 输出目录绝对路径（默认 {工作目录}/autoloop-output/）| plan | T4 |
| naming_pattern | string | 文件命名规则（如 {template_name}-{index}.md）| plan | T4 |
| key_assumptions | list[{name, current_value, unit}] | T2 对比中的关键假设（结构化列表，每项含名称+当前值+单位，用于敏感性分析）| plan | T2 |
| migration_check_cmd | string | 数据库迁移状态验证命令（如 python -m alembic current && python -m alembic check；无迁移填 N/A）| plan | T5 |
| frontend_dir | string | 前端代码目录绝对路径（如 /project/frontend）| plan | T5 |

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
iteration	phase	status	dimension	metric_value	delta	strategy_id	action_summary	side_effect	evidence_ref	unit_id	protocol_version	score_variance	confidence	details
```

| 列 | 说明 | 示例 |
|---|---|---|
| iteration | 轮次编号（从 1 开始） | 1 |
| phase | 阶段或子步骤标识 | scan / generate / compare |
| status | 状态（检查结果枚举）：通过 / 未通过 / 待检查 / 待审查 | 通过 |
| dimension | 评分维度名 | 安全性 / 覆盖率 / score |
| metric_value | 指标值（数字或百分比） | 8.5 / 85% |
| delta | 与上轮的变化（首轮填 — ） | +1.2 |
| strategy_id | 本轮使用的策略标识（与 findings.md 策略评估表一致） | S01-sql-scan |
| action_summary | 具体执行动作摘要 | 扫描全部SQL拼接并替换为参数化 |
| side_effect | 对其他维度的影响（无副作用填"无"） | 可维护性-0.5 |
| evidence_ref | 证据引用（findings.md 中的问题ID） | S001, R003 |
| unit_id | T2选项名/T4单元编号（其他模板填 —） | 选项A / 001 / — |
| protocol_version | 当前协议版本号 | 1.0.0 |
| score_variance | 多evaluator评分方差（单evaluator填0） | 0.5 |
| confidence | 评分置信度百分比 | 85% |
| details | 补充说明 | 首轮基线采集 |

**使用约定（各模板行粒度）**：

- T1/T3/T5/T6/T7：每轮**每维度**一行，确保每个维度的分数变化和策略归因都可追踪
- T2 Compare：每轮每选项每维度一行，`unit_id` = 选项名
- T4 Generate：每生成单元一行，`unit_id` = 生成单元 ID（001/002/...），`dimension` = `score`
- strategy_id 必须与 findings.md 中策略评估表的策略名一致
- side_effect 字段强制填写（无副作用填"无"）
- 首轮基线采集时，strategy_id 填"baseline"，action_summary 填"基线测量"

额外的原始数据（变量值、证据来源等）写入 `autoloop-findings.md`，不放在 results.tsv。

### 跨文件主键规范

所有AutoLoop输出文件（results.tsv、findings.md、progress.md、plan.md）共享以下主键体系，确保跨文件可追溯、可join：

| 主键 | 格式 | 定义时机 | 贯穿文件 |
|------|------|---------|---------|
| iteration | 整数（从1递增） | 每轮开始时自动递增 | 全部四文件 |
| strategy_id | S{NN}-{简短描述} | DECIDE阶段命名 | 全部四文件 |
| problem_id | {维度缩写}{NNN}（如S001） | findings发现时命名 | findings + results.tsv |
| dimension | 与quality-gates.md维度名完全一致 | quality-gates.md定义 | results.tsv + findings |

**引用规则**：
- results.tsv 的 evidence_ref 必须引用 findings.md 中已定义的 problem_id
- progress.md 每轮记录必须在标题中注明 iteration 编号
- plan.md 策略历史的 strategy_id 必须与 findings.md 策略评估表一致
- 任何文件中出现的 dimension 名称必须与 quality-gates.md 完全匹配，不得使用同义词

---

## Bootstrap 规则（plan 完成后立即执行）

**plan 向导完成后，立即创建以下文件（不等待第 1 轮 OBSERVE）：**

```
1. autoloop-plan.md         （已由向导创建）
2. autoloop-findings.md     （包含：执行摘要、每轮发现记录、工程问题清单、信息缺口汇总、拓展方向、策略评估、模式识别、经验教训）
3. autoloop-progress.md     （包含：质量门禁总览、基线记录、每轮 8 阶段迭代循环、任务完成记录、策略历史）
4. autoloop-results.tsv     （写入表头行：iteration\tphase\tstatus\tdimension\tmetric_value\tdelta\tstrategy_id\taction_summary\tside_effect\tevidence_ref\tunit_id\tprotocol_version\tscore_variance\tconfidence\tdetails）
```

所有 4 个文件必须在第 1 轮 OBSERVE 开始前存在。创建后在 autoloop-plan.md 的"输出文件"表中将状态从"待创建"更新为"已创建"。

### SSOT 可选模式

当 `autoloop-plan.md` 设置 `ssot_mode: true` 时，启用结构化单一事实源模式：

- **数据源**：`autoloop-state.json`（JSON 格式），包含 plan/iterations/findings/results 全部数据
- **写操作**：所有状态变更通过 `scripts/autoloop-state.py` 写入 JSON，不直接编辑 MD 文件
- **渲染**：每轮结束时运行 `scripts/autoloop-render.py` 从 JSON 生成 4 个可读 MD 文件
- **读操作**：OBSERVE 阶段仍可读取 MD 文件（渲染后与 JSON 同步）
- **向后兼容**：未设置 `ssot_mode` 时，行为完全不变，直接读写 4 个 MD 文件
- **优势**：消除跨文件信息重复和不一致，支持 `query` 命令快速检索任意字段
- **初始化**：使用 `autoloop-state.py init` 替代 `autoloop-init.py`，自动创建 JSON + 4 个 MD

---

## 概述

每次 AutoLoop 执行都遵循标准的 8 阶段 OODA 循环。本文档定义每个阶段的具体行为、输入输出规范和状态机转换规则。

---

## 三层架构职责定义

AutoLoop 的所有文件分属三个层次，每层有明确的身份、职责边界和依赖方向。三层职责不可混用。

### Protocol 层（制度层）

- **身份**：公司制度 — 规则、标准、枚举的唯一真源
- **包含**：质量门禁阈值、流程控制参数、生命周期枚举、严重级别定义、角色定义、进化规则、评分方法论
- **不包含**：执行步骤、角色调度指令、工单格式、具体执行上下文
- **依赖方向**：不依赖 commands 和 templates（最上层，无向上依赖）
- **修改权限**：仅通过 REFLECT 进化机制修改，需用户确认

### Command 层（编排层）

- **身份**：施工方案/调度器 — 编排执行流程并生成派工单
- **三步职责**：
  1. **编排逻辑** — 定义流程步骤、执行顺序、阶段划分
  2. **工单生成** — 读取 protocol + 当前上下文 → 组装派工单（含格式要求和执行说明）
  3. **结果收集** — 收回 subagent 产出，传递到下一步
- **包含**：执行流程、角色调度指令、工单格式示例、给 subagent 的上下文说明、阶段间衔接逻辑
- **不包含**：规则定义、阈值数值、评判标准、评分权重 — 这些必须引用 protocol，不可在 command 中独立定义
- **依赖方向**：读取 protocols（向上依赖），输出使用 templates（向下引用）

### Template 层（格式层）

- **身份**：报告格式 — 纯输出结构，给用户看的交付物
- **包含**：章节标题、表头、占位符、格式说明
- **不包含**：条件逻辑、执行步骤、bash 命令、规则引用
- **依赖方向**：被 commands 引用填充（最下层）

### 三层关系图

```
Protocol（制度）← 唯一规则源，不依赖任何层
    ↑ 读取
Command（编排）← 读取制度 + 上下文 → 生成工单 → 调度执行
    ↓ 填充
Template（格式）← 被填充后成为交付物
```

### 边界判定规则

> 当不确定某内容应放哪一层时，问：**"这个内容变了，是'制度变了'还是'做法变了'？"**

- **制度变了**（如阈值从 85% 改为 90%，状态枚举新增一项）→ 放 **protocol**
- **做法变了**（如先做 A 再做 B 改成先做 B 再做 A，工单格式调整）→ 放 **command**
- **格式变了**（如报告标题措辞、表头列名）→ 放 **template**

---

## 状态机

```
[准备开始]
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
  [已完成]
      ↓
  生成最终报告

[暂停等待确认]  ← 从 EVOLVE / Phase 0.5 / Phase 5 进入
  ↓ 等待人工输入（"用户确认" / "用户确认（线上验收）" / 修改意见）
  ↓ 收到输入后恢复到下一阶段
```

**暂停等待确认状态**：当需要人工确认时（T5 Phase 0.5 文档确认、T5 Phase 5 线上验收、以及任何 blocking gate），状态机进入暂停等待确认。系统在此状态停止自动推进，等待用户输入。用户输入 `用户确认`（Phase 0.5）或 `用户确认（线上验收）`（Phase 5）后，恢复到下一阶段。用户提出修改意见时，先处理修改，再自动恢复。

**状态不可逆**：不能从 ACT 回退到 DECIDE（当轮的决策在 ACT 开始后锁定）。
**错误处理**：任何阶段发生错误 → 写入 progress.md → 尝试恢复 → 如无法恢复则进入已完成状态 并说明原因。

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

**全局经验读取**：除读取当前任务的 findings.md 外，还须读取 `protocols/experience-registry.md` 全局策略效果库中同模板 + context_tags重叠 的推荐策略（按 success_rate 降序）。context_tags重叠 = 当前任务的标签与策略的context_tags至少有2个相同标签。无重叠标签的策略不推荐，避免跨上下文误迁移。首轮冷启动时，全局经验是唯一的策略参考来源。

**协议版本检测**：OBSERVE 开始时检查当前 `protocol_version` 是否与上次任务的版本一致。如果不一致（minor/major变更），触发重基线流程（规则见 `protocols/evolution-rules.md` 重基线章节），以新基线作为本轮起点。

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
| 发现紧急 P1 问题（数据丢失/安全漏洞）| 立即提升，暂停其他工作 |
| **振荡检测**：同一维度连续 3 轮分数在 ±0.5 范围内波动 | 报告振荡，切换到完全不同的策略方向 |
| **跨维度回归**：本轮改善维度 A 但维度 B 跌破门禁阈值 | 视为回归，下轮优先修复 B，策略标记为"有副作用" |

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

**单策略隔离原则**：每轮 DECIDE 阶段只选择一个主策略执行，实现可归因的 A/B 验证。多策略并行无法归因分数变化，会导致策略效果库积累伪相关。

例外：当多个独立维度同时需要修复且互不影响时（如安全性和可维护性分属不同代码区域），可并行执行，但每个维度的策略必须独立记录和归因。并行轮次的 results.tsv strategy_id 填 `multi:{S01+S02}`，side_effect 标注"混合归因，不入策略效果库"。

**strategy_id 命名规则**：每个策略在 DECIDE 阶段命名，格式为 `S{NN}-{简短描述}`（如 `S01-sql-param`、`S02-error-handler`）。此 ID 贯穿整个轮次的 results.tsv、findings.md、progress.md 和 plan.md，确保跨文件可追溯。

**影响面分析（DECIDE阶段必执行）**：

执行策略前必须分析跨维度依赖：
1. 本轮策略的目标维度是什么？
2. 该维度与哪些其他维度有依赖关系？常见依赖：
   - 安全性 ↔ 可靠性（安全加固可能增加异常处理复杂度）
   - 性能 ↔ 可维护性（性能优化可能降低代码可读性）
   - 架构 ↔ 全部维度（架构变更影响面最广）
3. 列出所有可能受影响的维度
4. VERIFY阶段必须验证：目标维度 + 所有受影响维度
5. 任何受影响维度跌破门禁阈值 → 视为回归，下轮优先修复

side_effect字段使用强化：不允许未经验证直接填"无"，必须在VERIFY阶段实际测量受影响维度后才能确认为"无"。

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

1. **质量门禁全部达标** → 成功终止 → 已完成（达标终止）
2. **用户中断** → 暂停终止 → 已完成（用户终止），保存进度，说明恢复方法
3. **预算耗尽（达到最大轮次）** → 预算终止 → 已完成（预算耗尽），输出当前最优结果
4. **无法继续（连续 2 轮无任何维度进展）** → 无法继续 → 已完成（无法继续），上报原因，列出所需用户输入

### 决策树

```
所有质量门禁达标？
  └─ 是 → 成功终止 → 已完成（达标终止）
  └─ 否 →
      达到最大轮次？
        └─ 是 → 预算终止 → 已完成（预算耗尽）
        └─ 否 →
            连续 2 轮所有维度均无进展（所有维度改善均 < 相对 3%）？
              └─ 是 → 无法继续 → 已完成（无法继续），输出当前最优结果并通知用户
                        （列出无法继续的原因和所需的用户输入，进入暂停等待确认）
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

终止判断：{继续 / 达标终止 / 预算终止 / 无法继续}

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

**经验提取与分发**：REFLECT 完成后，从本轮发现中提取可泛化的经验条目，按 `protocols/experience-registry.md` 定义的评估标准（类型、影响层级、置信度）评估后，分发到对应文件。低风险经验直接写入，高风险经验记录为待审批。

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

**无法继续**：
1. 清楚说明无法继续的原因
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
