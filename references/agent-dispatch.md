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
T7 Quality：安全审查 + 可靠性审查 + 可维护性审查 → 必须并行（三者均通过 code-reviewer 角色化实现，见下方说明）
T8 Optimize：架构诊断 + 性能诊断 + 稳定性诊断 → 必须并行（同上）
```

**T7/T8 专业审查角色说明**：

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

verifier（T4 Phase 5 线上验收）同理：通过 prompt 参数角色化为线上验收专家，不需要独立定义文件。调度时统一使用 verifier 角色名，不使用 "browse subagent" 旧称谓。

### 必须串行（按顺序调度）

满足以下任一条件必须串行：

1. **输出依赖**：B 需要 A 的输出才能开始
2. **文件冲突**：A 和 B 修改同一个文件
3. **状态依赖**：B 的结果取决于 A 修改后的系统状态
4. **优先级依赖**：P1 问题修复完成前，不开始 P2 问题修复

**强制串行场景**：

```text
T3 Product Design：
  Phase 1（需求分析）→ Phase 2（方案设计）→ Phase 3（可行性评审）
  （方案设计依赖需求分析输出；评审依赖完整方案文档）

T4 Deliver：
  开发（Phase 1）→ 审查（2）→ 测试（3）→ 部署（4）→ 验收（5）
  （每个阶段依赖上一阶段的输出）

T7 Quality（单文件）：
  problem-1 修复 → 验证通过 → problem-2 修复
  （同一文件不能并行修复，防止冲突）

数据库迁移（T4）：
  db-migrator 先完成 → 实现层 subagent 开始开发
  （代码依赖新的数据库结构）
```

---

## Subagent 角色定义

### researcher

**职责**：信息收集、网络调研、竞品分析

**触发场景**：T1 全程，T2 选项分析，T3 Phase 1（如有信息缺口需补充背景知识或技术约束）

**模板**：指令含调研主题/维度/目标/来源要求(≥3独立源)/输出格式(关键发现+数据点+信息缺口+相关发现)。可信度计算引用 quality-gates.md。

---

### planner

**职责**：任务分解、架构设计、方案制定

**触发场景**：复杂任务开始前（技术方案设计），T3 Phase 1（需求提炼与 JTBD 定义），T3 Phase 2（技术方案设计，兼任 technical-architect 职责）

**模板**：指令含功能需求/代码库路径/技术栈，读取 main_entry_file + 相关模块。输出：影响范围(修改/新建文件+DB变更+新端点) + 接口定义 + 实施顺序与依赖 + 风险识别。

---

### backend-dev

**职责**：后端/服务端代码实现

**触发场景**：T4 阶段 1，T7/T8 修复时

**模板**：指令含修改/新建文件(绝对路径)+改动说明、tech_constraints、约束(不可修改项)、syntax_check_cmd。输出：文件内容 + 语法验证结果 + 入口注册确认。

---

### frontend-dev

**职责**：前端实现

**触发场景**：T4 阶段 1，T7/T8 修复时（前端部分）

**模板**：同 backend-dev 结构，额外含前端目录路径。输出：文件内容 + 语法验证结果。

---

### db-migrator

**职责**：数据库迁移脚本创建和验证

**触发场景**：T4 阶段 1（有数据库变更时），T8（数据库结构优化时）

**模板**：指令含 codebase_path、migration_check_cmd、DDL 变更描述。必须实现 upgrade(IF NOT EXISTS) + downgrade(回滚)。输出：迁移文件路径 + 实现 + 验证结果。

---

### code-reviewer

**职责**：安全+质量审查

**触发场景**：T4 阶段 2，T7 每轮扫描，T8 checkpoint

**模板**：指令含审查类型(安全/可靠性/可维护性/全量)、代码库路径、重点文件列表。审查清单引用 quality-gates.md，评分规则引用 enterprise-standard.md。输出：问题清单(ID/文件/行号/类型/P级别/描述/修复建议) + 维度评分 + P1/P2/P3 统计。

---

### generator

**职责**：批量内容生成

**触发场景**：T6 全程

**模板**：指令含完整模板(变量用 {{name}} 标记)、本单元变量值、质量标准(N/10)、常见错误。输出格式：`---UNIT-START-{unit_id}---` 内容 `---UNIT-END---` + `---QUALITY---` 评分 `---QUALITY-END---`。

---

### verifier

**职责**：语法验证、路由注册验证、线上验收（T4 Phase 5 统一使用此角色，不使用 "browse subagent" 旧称谓）

**触发场景**：T4 阶段 3+5，T7/T8 每次修复后

**调用方式**：`Agent(subagent_type="code-reviewer", prompt="你是 verifier subagent...")`

注意：verifier 不是独立角色，是 code-reviewer 的角色化调用。T4 Phase 5 线上验收时可选用 Chrome DevTools MCP 工具（如已配置）。

**模板**：指令含验证类型(编译/路由/线上验收)、代码库路径、验证步骤+期望结果。输出：每步通过/失败 + 总体结论。

**T4 Phase 5 线上验收**：输入 acceptance_url + 验收标准列表，输出每项通过/失败 + 截图证据。最终确认须等待用户输入 `用户确认（线上验收）`。

---

### cross-verifier（交叉验证者）

**职责**：对多个 researcher subagent 的发现进行矛盾检查与多源验证

**触发场景**：T1 每轮结束后，T2 选项分析完成后

**调用方式**：`Agent(subagent_type="researcher", prompt="你是 cross-verifier subagent...")`

**适用模板**：T1, T2

**模板**：输入 findings.md 发现列表。任务：识别矛盾点 → 分析原因(时间/场景/方法论/真实争议) → 处理建议。输出：矛盾报告表(编号/维度/说法A+B/分析/建议) + 验证状态汇总(已确认/矛盾/未验证数)。

---

### option-analyzer（选项分析者）

**职责**：对对比任务中的单个候选方案进行深度分析

**触发场景**：T2 第一轮，为每个候选选项并行分配

**调用方式**：`Agent(subagent_type="researcher", prompt="你是 option-analyzer subagent...")`

**适用模板**：T2

**模板**：指令含选项名/对比主题/评估维度/分析角度(正向或批判性，同一选项分配两角度确保偏见检查)。每维度需证据支撑，识别核心优势/劣势(各≤3) + 适用场景。输出：维度评分表 + 综合得分 + 置信度(引用 quality-gates.md)。

---

### neutral-reviewer（中立审查者）

**职责**：检查选项分析结果是否存在评分偏见

**触发场景**：T2 所有选项分析完成后

**调用方式**：`Agent(subagent_type="researcher", prompt="你是 neutral-reviewer subagent...")`

**适用模板**：T2

**模板**：输入所有 option-analyzer 输出。检查：评分异常(全≥9或≤3) / 证据质量均衡性 / 选择性引用 / 评分标准一致性。输出：偏见风险(低/中/高) + 需重评维度 + 增补建议 + 结论(通过/需补充)。

---

### template-extractor（模板提取者）

**职责**：从用户提供的示例中提取可复用的生成模板

**触发场景**：T6 第一步，批量生成前的模板标准化

**调用方式**：`Agent(subagent_type="planner", prompt="你是 template-extractor subagent...")`

**适用模板**：T6

**模板**：输入用户示例。任务：识别固定/变量部分(用 {{name}} 标记) + 提取质量标准(1-10分) + 识别常见错误。输出：模板结构 + 变量定义表 + 质量标准 + 常见错误。

---

### quality-checker（质量检查者）

**职责**：对批量生成的内容单元进行独立质量评分

**触发场景**：T6 每个生成单元完成后

**调用方式**：`Agent(subagent_type="code-reviewer", prompt="你是 quality-checker subagent...")`

**适用模板**：T6

**模板**：输入生成内容 + 质量标准。评分规则：8-10通过 / 7及格标注改进 / 5-6需改进 / 1-4重生成。独立于生成者自评，分歧>2分以 checker 为准。输出：得分 + 主要问题 + 改进建议。

---

### 独立评分器角色（全模板适用）

**原则**：executor（执行者）和evaluator（评分者）必须是不同的subagent实例。evaluator只接收产出物，不接收执行过程信息（盲评），按 quality-gates.md 的锚点和证据要求打分。

| 模板 | executor | evaluator | 评分维度 |
|------|----------|-----------|---------|
| T1 Research | researcher | research-evaluator | 覆盖率/可信度/一致性 |
| T2 Compare | option-analyzer | compare-evaluator | 偏见/覆盖/一致性 |
| T3 Design | planner | feasibility-reviewer | 设计完整度/可行性/需求覆盖/范围精度/验证证据 |
| T5 Iterate | optimizer | kpi-evaluator | KPI达成/策略有效性/副作用 |
| T6 Generate | generator | quality-checker | 内容质量/格式规范/变量覆盖 |
| T4 Deliver | implementer | code-reviewer | 安全性/可靠性/可维护性 |
| T7 Quality | code-reviewer(修复) | security/reliability/maintainability-reviewer | 同T4 |
| T8 Optimize | optimizer | architecture/performance/stability-reviewer | 架构/性能/稳定性 |

**evaluator盲评约束**：
- evaluator的prompt只包含：产出物内容 + 评分标准（quality-gates.md）
- 不包含：本轮策略名称、执行过程、预期改善目标
- 目的：避免确认偏误，确保评分基于产出物本身质量

---

### feasibility-reviewer（可行性评审者）

**职责**：对 T3 产品设计方案进行独立可行性评审，覆盖 5 个质量门禁维度

**触发场景**：T3 Phase 3（独立可行性评审，在方案文档完成后执行）

**调用方式**：`Agent(subagent_type="planner", prompt="你是 feasibility-reviewer subagent...")`

**适用模板**：T3

**模板**：输入完整的方案文档（PRD/spec）+ 质量门禁标准（gate-manifest.json T3 段）。评分维度：

- `design_completeness`（7/10）：需求条目与设计方案的对应覆盖比例
- `feasibility_score`（7/10）：技术架构、依赖、风险是否可行
- `requirement_coverage`（7/10）：每条需求是否可追溯到文档章节
- `scope_precision`（7/10）：IN/OUT 范围是否明确、依赖是否已识别
- `validation_evidence`（7/10）：可行性检查 + 风险评估是否已完成

输出：5 个维度评分（0-10）+ 主要问题清单 + 通过/未通过总判定。

---

### T7 审查角色（三个并行，均通过 code-reviewer 角色化实现）

| 角色 | 职责 | 调用方式 |
| ---- | ---- | -------- |
| security-reviewer | 注入/XSS/路径穿越/敏感数据暴露 | `Agent(subagent_type="code-reviewer", prompt="你是 security-reviewer...")` |
| reliability-reviewer | 静默失败/异常处理/超时/降级回退 | `Agent(subagent_type="code-reviewer", prompt="你是 reliability-reviewer...")` |
| maintainability-reviewer | 入口注册/模块导出/类型规范/代码重复 | `Agent(subagent_type="code-reviewer", prompt="你是 maintainability-reviewer...")` |

**触发场景**：T7 第一轮并行扫描。完整指令模板见 `commands/autoloop-quality.md`。

### T7 统一评审框架

三个reviewer收到相同文件列表，输出统一格式：`| problem_id | 文件 | 行号 | 类型 | 优先级(P1/P2/P3) | 描述 | 修复建议 |`

**聚合**：合并去重(同文件+行号+类型) → 重复取最高优先级 → 按 `quality-gates.md` T7复合判定。
**冲突仲裁**：不同优先级取最高；修复建议冲突安全优先(记录trade-off)；分数差>2分触发第三方仲裁。

---

### fix-{type}（质量问题修复者）

**职责**：针对 T7 扫描发现的具体问题执行最小化修复

**触发场景**：T7 第 2-N 轮，按 P1→P2→P3 顺序为每个问题分配

**调用方式**：`Agent(subagent_type="backend-dev" 或 "frontend-dev", prompt="你是 fix-{类型} subagent...")`

后端/服务端问题使用 `backend-dev`；前端/客户端问题使用 `frontend-dev`。

**适用模板**：T7

**模板**：指令含问题ID/文件/行号/描述/建议/轮次/上下文摘要。约束：只改标注问题、不改函数签名/API、修改后立即 syntax_check_cmd。输出：diff + 验证结果 + 是否引入新问题。

---

### T8 诊断角色（三个并行，均通过 code-reviewer 角色化实现）

| 角色 | 职责 | 调用方式 |
| ---- | ---- | -------- |
| architecture-diagnostic | 分层/耦合/API一致性/配置管理/代码复用 | `Agent(subagent_type="code-reviewer", prompt="你是 architecture-diagnostic...")` |
| performance-diagnostic | N+1查询/连接池/缓存/同步混用/查询效率 | `Agent(subagent_type="code-reviewer", prompt="你是 performance-diagnostic...")` |
| stability-diagnostic | 外部依赖降级/错误处理/健康检查/超时 | `Agent(subagent_type="code-reviewer", prompt="你是 stability-diagnostic...")` |

**触发场景**：T8 第一轮并行诊断。完整指令模板见 `commands/autoloop-optimize.md`。

---

### optimization-fix（优化修复执行者）

**职责**：执行 T8 诊断发现的架构/性能/稳定性问题修复

**触发场景**：T8 第 2-N 轮，按综合优先级顺序执行

**调用方式**：`Agent(subagent_type="backend-dev" 或 "frontend-dev", prompt="你是 optimization-fix subagent...")`

后端/服务端修复使用 `backend-dev`；前端/客户端修复使用 `frontend-dev`。

**适用模板**：T8

**模板**：指令含问题ID/类型(架构/性能/稳定性)/描述/影响文件/建议/轮次/上下文摘要。约束：不改 public API 签名、不改 DB schema(除非方案明确)、修改后 syntax_check_cmd。执行：读文件 → 分析影响 → 最小化修复 → 验证。输出：修改列表 + 说明 + 验证结果 + 三维度影响预估。

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

> **技术栈变量填充**：各技术栈的变量填充值见 `references/domain-pack-*.md` 和 `references/loop-protocol.md` 统一参数词汇表。通用规则：所有变量从 plan 中读取，不在调度时硬编码。
