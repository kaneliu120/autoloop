# Agent Dispatch — Subagent 调度规范

## 概述

本文档定义 AutoLoop 调度 subagent 的规则：什么情况并行，什么情况串行，每次调度必须提供什么上下文。

**核心原则**：每个 subagent 必须能够独立工作，不依赖你告诉它"上下文在哪儿"——你必须把上下文直接放在指令里。

---

## 并行 vs 串行判断规则

### 必须并行（同时调度）

满足以下任一条件即可并行：

1. **输出独立**：subagent A 的输出不是 subagent B 的输入
2. **文件独立**：两个 subagent 操作完全不同的文件集合
3. **维度独立**：调研不同维度/检查不同模块
4. **层次独立**：backend-dev 操作后端文件，frontend-dev 操作前端文件

**强制并行场景**：

```text
T1 Research：多个 researcher 搜索不同维度 → 必须并行
T2 Compare：多个 analyzer 分析不同选项 → 必须并行
T6 Quality：安全审查 + 可靠性审查 + 可维护性审查 → 必须并行（三者均通过 code-reviewer 角色化实现，见下方说明）
T7 Optimize：架构诊断 + 性能诊断 + 稳定性诊断 → 必须并行（同上）
```

**T6/T7 专业审查角色说明**：

security-reviewer、reliability-reviewer、maintainability-reviewer 等**不是独立的 agent 定义文件**，而是通过 Agent tool 的 `prompt` 参数向通用 code-reviewer 传递角色化指令实现的。调度示例：

```python
# 安全审查
Agent(
  subagent_type='code-reviewer',
  prompt='你是安全审查专家，只关注安全维度（SQL注入/命令注入/XSS/路径穿越/敏感数据暴露）。
          使用 quality-gates.md 的安全性门禁评分规则（P1/P2/P3）。
          忽略可靠性和可维护性维度。'
)

# 可靠性审查
Agent(
  subagent_type='code-reviewer',
  prompt='你是可靠性审查专家，只关注可靠性维度（静默失败/缺少异常处理/无超时配置/缺少降级回退）。
          使用 quality-gates.md 的可靠性门禁评分规则。
          忽略安全性和可维护性维度。'
)

# 可维护性审查
Agent(
  subagent_type='code-reviewer',
  prompt='你是可维护性审查专家，只关注可维护性维度（路由注册/模块导出/类型规范/代码重复）。
          使用 quality-gates.md 的可维护性门禁评分规则。
          忽略安全性和可靠性维度。'
)
```

verifier（T5 Phase 5 线上验收）同理：通过 prompt 参数角色化为线上验收专家，不需要独立定义文件。调度时统一使用 verifier 角色名，不使用 "browse subagent" 旧称谓。

### 必须串行（按顺序调度）

满足以下任一条件必须串行：

1. **输出依赖**：B 需要 A 的输出才能开始
2. **文件冲突**：A 和 B 修改同一个文件
3. **状态依赖**：B 的结果取决于 A 修改后的系统状态
4. **优先级依赖**：P1 问题修复完成前，不开始 P2 问题修复

**强制串行场景**：

```text
T5 Deliver：
  分析（阶段 0）→ 文档化（0.5）→ 开发（1）→ 审查（2）→ 部署（4）
  （每个阶段依赖上一阶段的输出）

T6 Quality（单文件）：
  problem-1 修复 → 验证通过 → problem-2 修复
  （同一文件不能并行修复，防止冲突）

数据库迁移（T5）：
  db-migrator 先完成 → 实现层 subagent 开始开发
  （代码依赖新的数据库结构）
```

---

## Subagent 角色定义

### researcher

**职责**：信息收集、网络调研、竞品分析

**触发场景**：T1 全程，T2 选项分析，T5 阶段 0（如需调研最佳实践）

**标准指令模板**：

```text
你是 researcher subagent，负责以下信息收集任务。

调研主题：{主题}
调研维度：{具体维度}
目标：{要回答的具体问题}

信息来源要求：
- 至少找到 3 个独立来源
- 优先：官方文档 > 权威报告 > 技术媒体
- 标注每个来源的可信度（高/中/低）

输出格式：
## 调研结果：{维度名}

### 关键发现（按重要性排序）
1. {发现}（来源：{URL}，可信度：{级别}）
2. ...

### 数据点
- {指标}：{值}（来源：{URL}）

### 信息缺口
- {找不到的关键信息}

### 相关发现（范围外但有价值）
- {意外发现}
```

---

### planner

**职责**：任务分解、架构设计、方案制定

**触发场景**：T5 阶段 0（技术方案设计），复杂任务开始前

**标准指令模板**：

```text
你是 planner subagent，负责技术方案设计。

功能需求：{详细描述}
代码库路径：{codebase_path}
技术栈：{tech_stack}

任务：
1. 读取以下关键文件，理解现有架构：
   - {main_entry_file}（来自 plan，见 loop-protocol.md 统一参数词汇表）
   - {相关模块文件路径}

2. 制定实施方案

输出：
## 技术方案

### 影响范围
- 修改文件：{绝对路径列表}
- 新建文件：{绝对路径列表}
- 数据库变更：{变更说明，如无则"无"}
- 新增端点/接口：{路径 + 方法 + 说明}

### 接口定义
（关键函数签名）

### 实施顺序与依赖
1. {步骤}（前置：无）
2. {步骤}（前置：步骤 1）

### 风险识别
- {风险}：{影响}（缓解：{措施}）
```

---

### backend-dev

**职责**：后端/服务端代码实现

**触发场景**：T5 阶段 1，T6/T7 修复时

**标准指令模板**：

```text
你是 backend-dev subagent，负责后端实现。

修改文件（绝对路径）：
- {文件 1}：{改什么}
- {文件 2}：{改什么}

新建文件（绝对路径）：
- {文件}：{实现什么功能}

接口约定（必须遵守）：
{tech_constraints}

约束：
- {不可修改的接口}
- {不可修改的文件}

验证步骤（每个文件修改后立即执行）：
{syntax_check_cmd}

输出：
- 修改/新建的每个文件的具体内容
- 语法验证结果（全部通过才算完成）
- 入口文件注册确认（如有新路由/模块）
```

---

### frontend-dev

**职责**：前端实现

**触发场景**：T5 阶段 1，T6/T7 修复时（前端部分）

**标准指令模板**：

```text
你是 frontend-dev subagent，负责前端实现。

前端目录：{绝对路径}
修改/新建文件（绝对路径）：
{文件列表 + 改动说明}

技术约定（必须遵守）：
{tech_constraints}

验证步骤：
{syntax_check_cmd}

输出：
- 修改/新建文件的内容
- 语法验证结果（必须通过）
```

---

### db-migrator

**职责**：数据库迁移脚本创建和验证

**触发场景**：T5 阶段 1（有数据库变更时），T7（数据库结构优化时）

**标准指令模板**：

```text
你是 db-migrator subagent，负责数据库迁移管理。

代码库路径：{codebase_path}
迁移验证命令：{migration_check_cmd}（来自 plan，见 loop-protocol.md 统一参数词汇表；迁移目录和配置文件在 plan 中定义）

需要的数据库变更：
{具体变更描述，包含 DDL}

任务：
1. 创建新的迁移版本
2. 实现 upgrade()（使用 IF NOT EXISTS 防止重复执行）
3. 实现 downgrade()（必须实现，支持回滚）
4. 验证迁移脚本语法正确

输出：
- 迁移文件路径
- upgrade() 实现
- downgrade() 实现
- 验证结果（{syntax_check_cmd}）
```

---

### code-reviewer

**职责**：安全+质量审查

**触发场景**：T5 阶段 2，T6 每轮扫描，T7 checkpoint

**标准指令模板**：

```text
你是 code-reviewer subagent，负责代码审查。

审查范围：{审查类型：安全/可靠性/可维护性/全量}
代码库路径：{绝对路径}
重点文件（绝对路径）：
{文件列表，留空则全量扫描}

审查清单：
{从 quality-gates.md 对应部分提取}

评分规则：
{从 enterprise-standard.md 对应维度提取}

输出格式：
## 审查报告

### 问题清单
| ID | 文件 | 行号 | 类型 | 严重级别 | 描述 | 修复建议 |
（严重级别：P1/P2/P3）

### 评分
{维度}得分：{N}/10
扣分项：{列表}

### 总结
P1: {N} 个，P2: {N} 个，P3: {N} 个
结论：{通过/需修复}
```

---

### generator

**职责**：批量内容生成

**触发场景**：T4 全程

**标准指令模板**：

```text
你是 generator subagent，负责内容生成。

模板：
{完整模板内容，变量用 {{name}} 标记}

本单元变量：
{{variable_1}}: {值}
{{variable_2}}: {值}

质量标准：
1. {标准 1}：评分 {N/10}
2. {标准 2}：评分 {N/10}

注意避免：
- {常见错误 1}
- {常见错误 2}

输出格式：
---UNIT-START-{unit_id}---
{生成内容}
---UNIT-END---

---QUALITY---
标准1得分: {N}/10 — {理由}
综合得分: {N}/10
---QUALITY-END---
```

---

### verifier

**职责**：语法验证、路由注册验证、线上验收（T5 Phase 5 统一使用此角色，不使用 "browse subagent" 旧称谓）

**触发场景**：T5 阶段 3+5，T6/T7 每次修复后

**调用方式**：`Agent(subagent_type="code-reviewer", prompt="你是 verifier subagent...")`

注意：verifier 不是独立角色，是 code-reviewer 的角色化调用。T5 Phase 5 线上验收时可选用 Chrome DevTools MCP 工具（如已配置）。

**标准指令模板**：

```text
你是 verifier subagent，负责验证。

验证类型：{编译验证/路由验证/线上验收}
代码库路径：{绝对路径}

验证步骤：
1. {具体命令或操作}
2. {具体命令或操作}

期望结果：
1. {期望输出}
2. {期望输出}

输出：
每步结果：{通过/失败+具体输出}
总体结论：{通过/失败（失败步骤：{步骤名}，错误：{内容}）}
```

**T5 Phase 5 线上验收专用调度**：

```text
调用方式: Agent(subagent_type="code-reviewer", prompt="你是线上验收测试员。使用浏览器工具验证以下功能...")
可选工具: Chrome DevTools MCP（如果已配置）
输入: acceptance_url, 验收标准列表
输出: 每项验收标准的通过/失败状态 + 截图证据（如可用）
最终确认: 必须等待用户输入 'verified'
```

---

### cross-verifier（交叉验证者）

**职责**：对多个 researcher subagent 的发现进行矛盾检查与多源验证

**触发场景**：T1 每轮结束后，T2 选项分析完成后

**调用方式**：`Agent(subagent_type="researcher", prompt="你是 cross-verifier subagent...")`

**适用模板**：T1, T2

**标准指令模板**：

```text
你是 cross-verifier subagent，负责对以下调研发现进行交叉验证。

待验证的发现（来自 autoloop-findings.md）：
{发现列表}

任务：
1. 识别同一事实的不同说法（矛盾点）
2. 对每个矛盾分析原因（时间差异/场景差异/方法论差异/真实争议）
3. 给出处理建议（采用哪个/两者保留/需要进一步调研）

输出格式：
## 矛盾报告

| 编号 | 维度 | 说法 A（来源） | 说法 B（来源） | 分析 | 处理建议 |
|------|------|-------------|-------------|------|---------|

验证状态汇总：
- confirmed（多源一致）：{N} 条
- contradicted（存在矛盾）：{N} 条
- unverified（单一来源）：{N} 条
```

---

### option-analyzer（选项分析者）

**职责**：对对比任务中的单个候选方案进行深度分析

**触发场景**：T2 第一轮，为每个候选选项并行分配

**调用方式**：`Agent(subagent_type="researcher", prompt="你是 option-analyzer subagent...")`

**适用模板**：T2

**标准指令模板**：

```text
你是 option-analyzer subagent，负责深度分析以下候选方案。

选项名称：{选项名}
对比主题：{主题}
评估维度（必须全部覆盖）：{维度列表}
分析角度：{正向分析/批判性分析}（同一选项分配两个不同角度确保偏见检查）

要求：
1. 每个维度有具体证据支撑（数据、引用、案例）
2. 识别核心优势（最多 3 个）
3. 识别核心劣势/风险（最多 3 个）
4. 识别最适合/不适合的使用场景

输出格式：
## 选项分析：{选项名}

### 维度评分
| 维度 | 得分 (1-10) | 证据摘要 | 来源 |
|------|------------|---------|------|

### 核心优势 / 核心劣势 / 适用场景
{内容}

### 综合得分（加权前）
总分：{X}/10，置信度：{高/中/低}（基于 {N} 个信息来源）
```

---

### neutral-reviewer（中立审查者）

**职责**：检查选项分析结果是否存在评分偏见

**触发场景**：T2 所有选项分析完成后

**调用方式**：`Agent(subagent_type="researcher", prompt="你是 neutral-reviewer subagent...")`

**适用模板**：T2

**标准指令模板**：

```text
你是 neutral-reviewer subagent，负责检查对比分析是否存在偏见。

所有选项的分析结果：
{所有 option-analyzer 输出}

检查清单：
1. 评分是否有明显异常（某选项在所有维度都 ≥9 或 ≤3）
2. 证据质量是否均衡（某选项引用了更权威的来源）
3. 是否存在选择性引用（只引用对某选项有利的信息）
4. 评分标准是否一致（同等水平在不同选项中评分是否相同）

输出：
- 偏见风险评估：{低/中/高}
- 需要重新评估的维度：{列表，如无则"无"}
- 建议增补的对立证据：{列表，如无则"无"}
- 结论：{通过偏见检查 / 需要补充分析}
```

---

### template-extractor（模板提取者）

**职责**：从用户提供的示例中提取可复用的生成模板

**触发场景**：T4 第一步，批量生成前的模板标准化

**调用方式**：`Agent(subagent_type="planner", prompt="你是 template-extractor subagent...")`

**适用模板**：T4

**标准指令模板**：

```text
你是 template-extractor subagent，负责从示例中提取生成模板。

用户提供的示例：
{示例内容}

任务：
1. 识别固定部分（所有单元相同）和变量部分（每单元不同）
2. 用 {{variable_name}} 标记变量位置
3. 提取质量标准（什么让这个示例是"好的"，可量化为 1-10 分）
4. 识别常见错误（什么会让输出变差）

输出格式：
## 模板结构
{提取的模板，变量用 {{name}} 标记}

## 变量定义
| 变量名 | 说明 | 取值规则 | 示例 |
|--------|------|---------|------|

## 质量标准（可量化）
1. {标准 1}：{如何判断 1-10 分}
2. {标准 2}：{如何判断 1-10 分}

## 常见错误
- {错误 1}：{如何避免}
```

---

### quality-checker（质量检查者）

**职责**：对批量生成的内容单元进行独立质量评分

**触发场景**：T4 每个生成单元完成后

**调用方式**：`Agent(subagent_type="code-reviewer", prompt="你是 quality-checker subagent...")`

**适用模板**：T4

**标准指令模板**：

```text
你是 quality-checker subagent，对以下生成内容进行独立质量评分。

内容：
{生成的内容}

质量标准：
1. {标准 1}：{评分说明}
2. {标准 2}：{评分说明}
3. {标准 3}：{评分说明}

评分规则：
- 8-10：优秀，直接通过
- 7：及格，标注改进点
- 5-6：需要改进，标注主要问题
- 1-4：需要重新生成，说明原因

注意：你的评分独立于生成者的自评。分歧 > 2 分时，以你的评分为准。

输出：
得分: {N}/10（{通过/需改进/重生成}）
主要问题（如有）：{列表}
改进建议：{具体建议}
```

---

### security-reviewer（安全审查专家）

**职责**：专注安全维度的代码审查（注入/XSS/路径穿越/敏感数据暴露）

**触发场景**：T6 第一轮并行扫描（与 reliability-reviewer / maintainability-reviewer 并行）

**调用方式**：`Agent(subagent_type="code-reviewer", prompt="你是 security-reviewer subagent...")`

**适用模板**：T6

使用 `autoloop-quality.md` 中定义的完整 Security Reviewer 指令模板（含审查清单和评分规则）。

---

### reliability-reviewer（可靠性审查专家）

**职责**：专注可靠性维度（静默失败/缺少异常处理/无超时/缺少降级回退）

**触发场景**：T6 第一轮并行扫描

**调用方式**：`Agent(subagent_type="code-reviewer", prompt="你是 reliability-reviewer subagent...")`

**适用模板**：T6

使用 `autoloop-quality.md` 中定义的完整 Reliability Reviewer 指令模板。

---

### maintainability-reviewer（可维护性审查专家）

**职责**：专注可维护性维度（入口注册/模块导出/类型规范/代码重复）

**触发场景**：T6 第一轮并行扫描

**调用方式**：`Agent(subagent_type="code-reviewer", prompt="你是 maintainability-reviewer subagent...")`

**适用模板**：T6

使用 `autoloop-quality.md` 中定义的完整 Maintainability Reviewer 指令模板。

---

### fix-{type}（质量问题修复者）

**职责**：针对 T6 扫描发现的具体问题执行最小化修复

**触发场景**：T6 第 2-N 轮，按 P1→P2→P3 顺序为每个问题分配

**调用方式**：`Agent(subagent_type="backend-dev" 或 "frontend-dev", prompt="你是 fix-{类型} subagent...")`

后端/服务端问题使用 `backend-dev`；前端/客户端问题使用 `frontend-dev`。

**适用模板**：T6

**标准指令模板**：

```text
你是 fix-{类型} subagent，修复以下代码质量问题。

问题 ID：{ID}
文件：{绝对路径}
行号：{行}
问题描述：{描述}
修复建议：{建议}
当前轮次：第 {N} 轮
上下文摘要：{前几轮已修复的问题摘要，避免冲突}

约束：
- 只修改标注的问题，不做其他改动
- 不改变函数签名和 API 接口
- 修改后立即运行语法验证命令（{syntax_check_cmd}）

修复步骤：
1. 读取文件
2. 实施最小化修复
3. 运行 {syntax_check_cmd}（必须通过才报告完成）
4. 确认修复解决了问题且未引入新问题

输出：
- 修改内容（diff 格式）
- 验证结果（必须通过）
- 是否引入新问题（是/否，如是则描述）
```

---

### architecture-diagnostic（架构诊断专家）

**职责**：全面诊断系统架构问题（分层/耦合/API一致性/配置管理/代码复用）

**触发场景**：T7 第一轮并行诊断（与 performance-diagnostic / stability-diagnostic 并行）

**调用方式**：`Agent(subagent_type="code-reviewer", prompt="你是 architecture-diagnostic subagent...")`

**适用模板**：T7

使用 `autoloop-optimize.md` 中定义的完整 Architecture Diagnostic 指令模板。

---

### performance-diagnostic（性能诊断专家）

**职责**：全面诊断系统性能问题（N+1查询/连接池/缓存覆盖/同步阻塞/查询效率）

**触发场景**：T7 第一轮并行诊断

**调用方式**：`Agent(subagent_type="code-reviewer", prompt="你是 performance-diagnostic subagent...")`

**适用模板**：T7

使用 `autoloop-optimize.md` 中定义的完整 Performance Diagnostic 指令模板。

---

### stability-diagnostic（稳定性诊断专家）

**职责**：全面诊断系统稳定性问题（外部依赖降级/错误处理/健康检查/超时配置）

**触发场景**：T7 第一轮并行诊断

**调用方式**：`Agent(subagent_type="code-reviewer", prompt="你是 stability-diagnostic subagent...")`

**适用模板**：T7

使用 `autoloop-optimize.md` 中定义的完整 Stability Diagnostic 指令模板。

---

### optimization-fix（优化修复执行者）

**职责**：执行 T7 诊断发现的架构/性能/稳定性问题修复

**触发场景**：T7 第 2-N 轮，按综合优先级顺序执行

**调用方式**：`Agent(subagent_type="backend-dev" 或 "frontend-dev", prompt="你是 optimization-fix subagent...")`

后端/服务端修复使用 `backend-dev`；前端/客户端修复使用 `frontend-dev`。

**适用模板**：T7

**标准指令模板**：

```text
你是 optimization-fix subagent，负责以下优化问题修复。

问题 ID：{ID}
类型：{架构/性能/稳定性}
描述：{问题描述}
影响文件：{绝对路径列表}
修复建议：{具体建议}
当前轮次：第 {N} 轮
上下文摘要：{前几轮已修复的问题摘要，避免冲突}

约束（不可违反）：
- 不改变 public API 签名（路由路径、请求/响应格式）
- 不改变数据库 schema（除非方案中明确说明）
- 修改后必须通过语法验证（{syntax_check_cmd}）

执行步骤：
1. 读取相关文件（读全，不要猜）
2. 分析影响范围（修改这个会影响哪些调用者）
3. 实施最小化修复
4. 运行 {syntax_check_cmd} 验证
5. 报告修改内容

输出：
- 修改文件列表
- 每个文件的关键修改说明
- 验证结果
- 预期对三维度评分的影响
- 是否需要测试关联功能
```

---

## 上下文完整性检查清单

每次调度前，确认以下内容已包含在指令中：

- [ ] 角色定义（"你是 X subagent"）
- [ ] 具体任务（可操作的指令，不是模糊方向）
- [ ] 所有相关文件的**绝对路径**（不是相对路径）
- [ ] 必须遵守的约束（什么不能改）
- [ ] 验收标准（完成的判断条件）
- [ ] 输出格式（结构化，便于整合）
- [ ] 当前迭代轮次（让 subagent 知道这是第几轮）
- [ ] 上下文摘要（包含上轮反思记录）:
  - 遗留问题清单（待处理状态的问题）
  - 有效/无效策略（避免重复无效方法）
  - 已识别模式（让 subagent 知道系统性问题）
  - 相关经验教训

**缺少任一项 → 重写指令再调度。**

---

## 失败处理策略

| 失败类型 | 处理策略 |
| -------- | -------- |
| Subagent 无法找到信息 | 换关键词/换来源/标注"信息不可用" |
| Subagent 输出格式错误 | 提取可用部分，补充缺失字段 |
| Subagent 代码验证失败 | 返回详细错误给 subagent，要求修复（遵守统一重试上限 = 2 次，见 loop-protocol.md） |
| Subagent 超时 | 标记为"部分完成"，记录进度，继续其他任务 |
| 并行 subagents 产生冲突 | 以保守的（改动更小的）为准，记录两种方案 |

---

## 附录：技术栈示例

本附录提供具体技术栈下的变量填充示例，供各模板参考。通用角色定义本身不依赖这些示例。

### Python/FastAPI 技术栈

| 变量 | 填充值 |
|------|--------|
| `{tech_stack}` | FastAPI + SQLAlchemy 2.0 async + PostgreSQL |
| `{syntax_check_cmd}` | `python3 -m py_compile {文件路径}` |
| `{main_entry_file}` | `{codebase_path}/backend/main.py` |
| `{migration_check_cmd}` | `python -m alembic current && python -m alembic check`（迁移目录和配置文件在 plan 中定义）|
| `{tech_constraints}` | 所有路由函数使用 async def；数据库操作使用 SQLAlchemy 2.0 async session；配置从 settings 获取；新路由在 main.py 中注册 |

**planner 输出示例（影响范围）**：

```text
修改文件：/path/backend/api/items.py
新建文件：/path/backend/models/item.py
数据库变更：ALTER TABLE items ADD COLUMN tag VARCHAR(64)
新增端点：POST /api/items/{id}/tag
```

### Node.js/TypeScript 技术栈

| 变量 | 填充值 |
|------|--------|
| `{tech_stack}` | Node.js + Express/Fastify + TypeScript + PostgreSQL |
| `{syntax_check_cmd}` | `npx tsc --noEmit` |
| `{main_entry_file}` | `{codebase_path}/src/index.ts` 或 `app.ts` |
| `{migration_check_cmd}` | `npx drizzle-kit check` 或 `npx knex migrate:status`（配置文件路径在 plan 中定义）|
| `{tech_constraints}` | 使用 TypeScript，不使用 any；新路由在 index.ts/app.ts 中注册；异步操作使用 async/await |

### Next.js/前端技术栈

| 变量 | 填充值 |
|------|--------|
| `{tech_stack}` | Next.js App Router + TypeScript + TanStack Query v5 + Tailwind CSS v4 |
| `{syntax_check_cmd}` | `cd {frontend_dir} && npx tsc --noEmit`（`{frontend_dir}` 见 loop-protocol.md 统一参数词汇表）|
| `{main_entry_file}` | `{codebase_path}/app/layout.tsx` |
| `{tech_constraints}` | 使用 TypeScript，不使用 any；API 调用通过 /api/* 路由；状态管理使用 TanStack Query v5 的 useQuery/useMutation；样式使用 Tailwind CSS v4 |

### 通用/多语言技术栈

| 变量 | 填充值（按实际情况替换） |
|------|--------|
| `{tech_stack}` | 从 plan.tech_stack 填入 |
| `{syntax_check_cmd}` | 从 plan.syntax_check_cmd 填入（见 loop-protocol.md 统一参数词汇表）|
| `{main_entry_file}` | 从 plan.main_entry_file 填入（见 loop-protocol.md 统一参数词汇表）|
| `{migration_check_cmd}` | 从 plan.migration_check_cmd 填入（见 loop-protocol.md 统一参数词汇表），如无数据库则 N/A |
| `{tech_constraints}` | 从 plan.tech_stack 推导或由 planner subagent 在方案中定义 |
