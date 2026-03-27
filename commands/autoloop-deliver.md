---
name: autoloop-deliver
description: >
  AutoLoop T5: 全流程交付模板。从需求到生产的完整 7 阶段交付流程，
  严格映射 CLAUDE.md 强制开发流程。阶段 0.5（文档化）必须人工确认。
  每个阶段有明确质量门禁，不通过不进入下一阶段。
  质量门禁阈值见 protocols/quality-gates.md T5 行。
  触发：/autoloop:deliver 或任何需要端到端功能交付的任务。
---

# AutoLoop T5: Deliver — 全流程交付

## 执行前提

读取 `autoloop-plan.md` 获取所有执行参数。T5 参数见 `protocols/loop-protocol.md` 统一参数词汇表。

**严格遵守 CLAUDE.md 强制开发流程，不可跳步。**

**Round 2+ OBSERVE 起点**：如本次交付是对上次未完成任务的继续，先读取 `autoloop-findings.md` 的 REFLECT 章节（第1层问题登记、第2层策略复盘、第3层模式识别），获取遗留问题、有效/无效策略和已识别模式，再开始阶段 0 分析。详见 `protocols/loop-protocol.md` OBSERVE Step 0 章节。

---

## 阶段概览

```text
阶段 0   → 分析（planner + researcher）
阶段 0.5 → 文档化（必须人工确认才能继续）
阶段 1   → 开发（backend-dev + frontend-dev + db-migrator）
阶段 2   → 审查（code-reviewer）
阶段 3   → 测试验证（verifier）
阶段 4   → 部署（git push + {deploy_command}）
阶段 5   → 线上验收（verifier + 人工确认）
```

**暂停确认点（Pause Gate）**：阶段 0.5 和阶段 5 必须人工确认（状态机进入 AWAIT_USER，任务状态变为"暂停等待确认"），系统不自动跳过。详见 `protocols/loop-protocol.md` 状态机章节。

---

## 阶段 0: 分析

### 派遣

角色：planner + researcher（职责定义见 `protocols/agent-dispatch.md`）

### 本次范围

- 功能需求：{需求描述}
- 代码库路径：{绝对路径}
- project_type：{从 autoloop-plan.md 读取}
- 条件变量（仅当 ≠ N/A 时纳入分析）：main_entry_file、new_router_name、migration_check_cmd、frontend_dir

### 执行流程

1. **planner** 和 **researcher** 并行运行（并行判断见 `protocols/agent-dispatch.md` 协作规则）
2. planner 读取 `protocols/delivery-phases.md` 获取各阶段要求，分析影响范围、接口定义、实施顺序、风险
3. researcher（按需）调研不确定技术点的最佳实践，找 3 个实际代码示例
4. 输出合并为技术方案（影响范围 + 实施顺序 + 风险识别 + 接口定义）

### 质量门禁

Phase 0 门禁见 `protocols/quality-gates.md` T5 行及 `protocols/delivery-phases.md`。

验收要求：文件识别完整、数据库变更已描述、路由已列出、风险已识别、实施顺序已确定、验收标准已明确。

---

## 阶段 0.5: 文档化 — 暂停确认点

### 目标

将分析结果写成方案文档，获得人工确认后才能开发。

### 生成文档

使用 `templates/delivery-template.md` 生成方案文档，写入：
`{doc_output_path}/{功能名}-{YYYY-MM-DD}.md`

其中 `{doc_output_path}` 来自 `autoloop-plan.md`（变量名见 `protocols/loop-protocol.md` 统一参数词汇表）。不得在此处硬编码任何路径。

### 质量门禁

Phase 0.5 门禁见 `protocols/quality-gates.md` T5 行及 `protocols/delivery-phases.md`。

验收要求：文档完整（问题描述/影响范围/具体方案/实施步骤/验收标准）+ 人工 confirmed。

### 暂停：等待人工确认

```text
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
阶段 0.5 暂停等待确认 — 需要人工确认
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

方案文档已生成：
{文档路径}

请审阅方案，确认后输入 "confirmed" 开始开发。
如需修改，说明需要调整的内容。

不确认则不进入开发阶段。
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## 阶段 1: 开发

### 派遣

角色：db-migrator → backend-dev + frontend-dev（职责定义见 `protocols/agent-dispatch.md`）

### 本次范围

- 方案文档：{路径}
- 代码库路径：{绝对路径}
- 条件变量：syntax_check_cmd、syntax_check_file_arg、main_entry_file、new_router_name、migration_check_cmd、frontend_dir

### 执行流程

1. **db-migrator**（仅当 migration_check_cmd ≠ N/A）：读取 `protocols/enterprise-standard.md` 迁移规范，创建迁移脚本，必须实现 downgrade()
2. **backend-dev**（串行于 db-migrator 之后）：读取 `protocols/enterprise-standard.md` 后端规范，按方案逐项实现，每个文件修改后立即 `{syntax_check_cmd}` 验证
3. **frontend-dev**（仅当 frontend_dir ≠ N/A，可与 backend-dev 并行）：读取 `protocols/enterprise-standard.md` 前端规范，按方案逐项实现
4. 每个角色按 `protocols/agent-dispatch.md` 中定义的输出格式交付结果

### 质量门禁

Phase 1 门禁见 `protocols/quality-gates.md` 工程类任务门禁章节：

- [ ] 语法验证通过（对每个修改文件运行 `{syntax_check_cmd}`，按 `syntax_check_file_arg` 决定是否附加文件名）
- [ ] （当 new_router_name ≠ N/A 时）[L1] 路由注册验证通过
- [ ] 新文件已在模块导出文件中声明
- [ ] （当 migration_check_cmd ≠ N/A 时）迁移脚本有 downgrade 实现
- [ ] 无静默失败（空 catch/except）/ 无类型逃逸（any / type:ignore）滥用

---

## 阶段 2: 审查

### 派遣

角色：code-reviewer（职责定义见 `protocols/agent-dispatch.md`）

### 本次范围

审查文件列表：{阶段 1 产出的所有修改/新建文件的绝对路径}

### 执行流程

1. 读取 `protocols/quality-gates.md` 安全性/可靠性/可维护性门禁章节
2. 读取 `protocols/enterprise-standard.md` 获取评分规则和检测项
3. 根据本次审查范围生成针对性检查清单
4. 按清单逐项审查，按角色定义的输出格式（问题清单表 + 维度评分 + 结论）交付报告

### 质量门禁

Phase 2 门禁见 `protocols/quality-gates.md` T5 行。

P1/P2 问题必须修复后重审（返回阶段 1 针对性修复）。重试上限见 `protocols/loop-protocol.md` 统一重试规则（T5 Phase 2 审查-修复循环最多 3 轮）。

---

## 阶段 3: 测试验证

### 派遣

角色：verifier（职责定义见 `protocols/agent-dispatch.md`）

### 本次范围

- 代码库路径：{绝对路径}
- 条件变量：syntax_check_cmd、syntax_check_file_arg、main_entry_file、new_router_name、migration_check_cmd

### 执行流程

1. 读取 `protocols/quality-gates.md` 工程类任务门禁章节和路由注册门禁章节
2. 读取 `protocols/delivery-phases.md` 获取各阶段验证要求
3. 根据本次修改范围和 plan 参数生成针对性验证清单
4. 按清单逐项执行验证，输出每步结果 + 总体结论

### 质量门禁

Phase 3 门禁见 `protocols/quality-gates.md` T5 行：

- [ ] 语法验证通过
- [ ] [L1] 路由注册验证通过（无新路由则 N/A）
- [ ] 数据库迁移状态正确（无迁移则 N/A）

---

## 阶段 4: 部署

### 执行流程

1. 提交代码：`git add {所有修改文件}`（明确列出，不使用 git add -A）→ `git status` 确认 → `git commit` → `git push origin main`
2. 线上部署：`{deploy_command}`（来自 autoloop-plan.md）
3. 服务健康检查：检查 `{service_list}` 全部 active（service_list = N/A 则跳过）
4. Health check：`curl {health_check_url}` 期望 HTTP 200（health_check_url 为空则标记 N/A）

### 质量门禁

Phase 4 门禁见 `protocols/quality-gates.md` T5 行：

- [ ] git push 成功
- [ ] `{deploy_command}` 执行无报错
- [ ] `{service_list}` 中所有服务全部 active（N/A 则跳过）
- [ ] Health check 返回 200（为空则标记 N/A）

---

## 阶段 5: 线上验收 — 暂停确认点

### 派遣

角色：verifier（职责定义见 `protocols/agent-dispatch.md`）

### 本次范围

- project_type：{从 autoloop-plan.md 读取}
- acceptance_url：{从 autoloop-plan.md 读取}

### 执行流程

1. 读取 `protocols/delivery-phases.md` Phase 5 条件化规则
2. 读取 `protocols/quality-gates.md` T5 验收门禁
3. 根据 project_type 和本次交付内容生成针对性验收清单
4. 按清单逐项验证，输出验收报告

### 暂停：等待人工确认

```text
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
阶段 5 暂停等待确认 — 需要人工确认
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

自动验证结果：{通过/有问题}

验收方式（按 project_type 自动选择，规则见 protocols/delivery-phases.md Phase 5）：
{根据 project_type 生成的验收指引}

验收清单：
1. {验收标准 1}
2. {验收标准 2}
3. {验收标准 3}

确认无误后输入 "verified" 完成任务。
如有问题，描述问题后回滚或继续修复。
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

T5 完成条件：Phase 4 门禁通过 AND 用户输入 "verified"（所有 project_type 均需人工确认）。完整门禁定义见 `protocols/quality-gates.md` T5 行及 `protocols/delivery-phases.md` Phase 5 条件化规则。

---

## 每轮 REFLECT 执行规范

在每个阶段完成之后执行。REFLECT 必须写入文件，不能只在思考中完成（规范见 `protocols/loop-protocol.md` REFLECT 章节）。

写入 `autoloop-findings.md` 的 4 层反思结构表（格式见 `templates/findings-template.md`）：

- **问题登记（第 1 层）**：记录本轮发现的代码问题、修复是否引入新问题、审查遗漏
- **策略复盘（第 2 层）**：修复策略/审查方法/验证命令的效果评估（保持 | 避免 | 待验证）（策略评价枚举见 `protocols/loop-protocol.md` 统一状态枚举）
- **模式识别（第 3 层）**：反复出现的代码问题类型（说明有架构级根因）、修复导致新问题的因果链
- **经验教训（第 4 层）**：哪类修复最有效、哪些验证步骤能发现最多问题

**调度规范见 `protocols/agent-dispatch.md`。**

---

## 交付完成报告

文件名遵循 `protocols/loop-protocol.md` 统一输出文件命名章节（T5: `autoloop-delivery-{feature}-{date}.md`）。

人工确认后，输出最终交付报告：

```markdown
# 交付完成报告

## 功能
{功能名称}

## 交付内容

| 阶段 | 状态 | 耗时 |
|------|------|------|
| 0 分析 | 完成 | {时间} |
| 0.5 文档化 | 完成（已确认）| {时间} |
| 1 开发 | 完成 | {时间} |
| 2 审查 | 通过（门禁见 protocols/quality-gates.md T5 行）| {时间} |
| 3 测试 | 通过 | {时间} |
| 4 部署 | 成功 | {时间} |
| 5 验收 | 已确认 | {时间} |

## 变更清单

### 新增文件
{文件列表}

### 修改文件
{文件列表}

### 数据库迁移
{迁移脚本名称（如无则"无"）}

### 新增路由/接口
{列表（如无则"无"）}

## 发现的问题

本次交付过程中发现但未修复的问题（P3 级）：
{列表（如无则"无"）}

## 后续建议

{如有遗留事项或优化建议}
```
