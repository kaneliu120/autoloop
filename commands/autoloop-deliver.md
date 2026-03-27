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

**阻塞门禁（Blocking Gate）**：阶段 0.5 和阶段 5 必须人工确认（状态机进入 AWAIT_USER），系统不自动跳过。详见 `protocols/loop-protocol.md` 状态机章节。

---

## 阶段 0: 分析

### 目标

全面理解需求，识别技术影响面，制定实施方案。

### 执行

**并行运行以下 subagents**（调度规范见 `protocols/agent-dispatch.md`）：

**planner subagent**（调度方式见 agent-dispatch.md planner 章节）：

```text
你是 planner subagent，负责技术方案设计。

执行流程：
1. 读取 protocols/delivery-phases.md 获取各阶段要求
2. 读取 autoloop-plan.md 获取 project_type 及所有执行参数
3. 根据本次功能需求和代码库结构，生成针对性分析清单
4. 按清单逐项分析
5. 输出技术方案

功能需求：
{需求描述}

代码库路径：{绝对路径}
project_type：{从 autoloop-plan.md 读取}

以下变量仅当 ≠ N/A 时纳入分析：
main_entry_file：{从 autoloop-plan.md 读取}
new_router_name：{从 autoloop-plan.md 读取}
migration_check_cmd：{从 autoloop-plan.md 读取}
frontend_dir：{从 autoloop-plan.md 读取}

输出：
## 技术方案

### 影响范围
- 修改文件：{文件列表，绝对路径}
- 新建文件：{文件列表，绝对路径}
- 数据库变更：{描述变更内容}
- 新增路由：{路由列表}

### 实施顺序
1. {步骤 1}（依赖：无）
2. {步骤 2}（依赖：步骤 1）

### 风险识别
- {风险 1}：{描述}（缓解：{措施}）

### 接口定义
{关键函数/API 的签名}
```

**researcher subagent**（如果需要外部信息，调度方式见 agent-dispatch.md researcher 章节）：

```text
你是 researcher subagent，调研以下技术实现的最佳实践：

问题：{实现需求中有不确定方案的技术点}

要求：
1. 找到 3 个实际可用的代码示例
2. 分析各方法的优缺点
3. 推荐最适合当前项目技术栈的方案

输出：推荐方案 + 示例代码
```

### 质量门禁（阶段 0）

Phase 0 门禁见 `protocols/quality-gates.md` T5 行 及 `protocols/delivery-phases.md`。

验收要求：文件识别完整、数据库变更已描述、路由已列出、风险已识别、实施顺序已确定、验收标准已明确。

---

## 阶段 0.5: 文档化 — 阻塞门禁

### 目标

将分析结果写成方案文档，获得人工确认后才能开发。

### 生成文档

使用 `templates/delivery-template.md` 生成方案文档，写入：
`{doc_output_path}/{功能名}-{YYYY-MM-DD}.md`

其中 `{doc_output_path}` 来自 `autoloop-plan.md`（变量名见 `protocols/loop-protocol.md` 统一参数词汇表）。不得在此处硬编码任何路径。

### 质量门禁（阶段 0.5 文档化）

Phase 0.5 门禁见 `protocols/quality-gates.md` T5 行 及 `protocols/delivery-phases.md`。

验收要求：文档完整（问题描述/影响范围/具体方案/实施步骤/验收标准）+ 人工 confirmed。

### 阻塞：等待人工确认（阶段 0.5）

```text
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
阶段 0.5 阻塞点 — 需要人工确认
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

### 目标

根据确认的方案实施代码变更。

### 执行顺序

**1a. 数据库迁移（仅当 migration_check_cmd ≠ N/A 时执行）** — 最先执行，其他开发依赖数据库结构

db-migrator subagent（调度方式见 `protocols/agent-dispatch.md` db-migrator 章节）：

```text
你是 db-migrator subagent，负责创建数据库迁移脚本。

执行流程：
1. 读取 protocols/enterprise-standard.md 技术栈特定检测章节获取迁移工具用法
2. 读取 protocols/agent-dispatch.md 附录获取迁移规范
3. 根据本次变更内容，生成针对性迁移方案
4. 按方案执行迁移脚本创建
5. 运行验证命令确认迁移正确

变更内容：
{从方案文档提取的数据库变更描述}

代码库路径：{绝对路径}
migration_check_cmd：{从 autoloop-plan.md 读取，变量名见 protocols/loop-protocol.md}
syntax_check_cmd：{从 autoloop-plan.md 读取}

输出：
- 迁移文件路径
- 迁移内容摘要（新增/修改的表/列/索引）
- 回滚方案
- 验证结果（{syntax_check_cmd}）
```

**1b. 核心开发** — 数据库迁移后执行

backend-dev subagent（调度方式见 `protocols/agent-dispatch.md` backend-dev 章节）：

```text
你是 backend-dev subagent，负责核心代码实现。

执行流程：
1. 读取 protocols/enterprise-standard.md 技术栈特定检测章节获取编码规范
2. 读取 protocols/quality-gates.md 工程类任务门禁章节获取验证要求
3. 根据方案文档和代码库现状，生成针对性实现清单
4. 按清单逐项实现，每个文件修改后立即运行语法验证
5. 输出修改报告

方案文档：{路径}
代码库路径：{绝对路径}
syntax_check_cmd：{从 autoloop-plan.md 读取}
syntax_check_file_arg：{从 autoloop-plan.md 读取（true/false）}

以下变量仅当 ≠ N/A 时适用：
main_entry_file：{从 autoloop-plan.md 读取}
new_router_name：{从 autoloop-plan.md 读取}

输出：
- 修改/新建的文件列表（绝对路径）
- 每个文件的关键变更摘要
- 语法验证结果（全部通过）
-（当 new_router_name ≠ N/A 时）[L1] 主入口文件注册确认（验证方法见 protocols/quality-gates.md 路由注册门禁，L1 近似检查）
```

**1c. 前端开发（仅当 frontend_dir ≠ N/A 时执行）** — 可与核心开发并行

frontend-dev subagent（调度方式见 `protocols/agent-dispatch.md` frontend-dev 章节）：

```text
你是 frontend-dev subagent，负责前端代码实现。

执行流程：
1. 读取 protocols/enterprise-standard.md 技术栈特定检测章节获取前端编码规范
2. 读取 protocols/quality-gates.md 工程类任务门禁章节获取验证要求
3. 根据方案文档和前端目录现状，生成针对性实现清单
4. 按清单逐项实现，每个文件修改后立即运行语法验证
5. 输出修改报告

方案文档：{路径}
前端目录：{从 autoloop-plan.md 读取 frontend_dir}
syntax_check_cmd：{从 autoloop-plan.md 读取}

输出：
- 修改/新建的文件列表（绝对路径）
- {syntax_check_cmd} 验证结果（通过）
```

### 质量门禁（阶段 1）

Phase 1 门禁见 `protocols/quality-gates.md` 工程类任务门禁章节：

- [ ] 语法验证通过（对每个修改文件运行 `{syntax_check_cmd}`，按 `syntax_check_file_arg` 决定是否附加文件名）
- [ ] （当 new_router_name ≠ N/A 时）[L1] 路由注册验证通过（L1 近似检查，已知局限见 protocols/quality-gates.md 验证层级章节）
- [ ] 新文件已在模块导出文件中声明
- [ ] （当 migration_check_cmd ≠ N/A 时）迁移脚本有 downgrade 实现
- [ ] 无静默失败（空 catch/except）/ 无类型逃逸（any / type:ignore）滥用

---

## 阶段 2: 审查

code-reviewer subagent（调度方式见 `protocols/agent-dispatch.md` code-reviewer 章节）对所有修改文件审查，审查清单和评分规则见 `protocols/quality-gates.md` 安全性/可靠性/可维护性门禁章节及 `protocols/enterprise-standard.md`：

```text
你是 code-reviewer subagent，负责安全+质量审查。

执行流程：
1. 读取 protocols/quality-gates.md 安全性/可靠性/可维护性门禁章节
2. 读取 protocols/enterprise-standard.md 获取评分规则和检测项
3. 根据本次审查范围（以下文件列表），生成针对性检查清单
4. 按清单逐项审查每个文件
5. 按 protocols/quality-gates.md 的严重级别分类输出报告

审查文件列表：
{阶段 1 产出的所有修改/新建文件的绝对路径}

输出格式：
## 审查报告

### 通过项
- {文件}: {通过的方面}

### 问题清单

| ID | 文件 | 行号 | 类型 | 严重级别 | 描述 | 修复建议 |
|----|------|------|------|---------|------|---------|
| 001 | {路径} | {行} | 安全 | P1 | {描述} | {建议} |

### 结论
- P1 问题（必须修复）：{N} 个
- P2 问题（应该修复）：{N} 个
- P3 问题（建议修复）：{N} 个
- 结论：{通过 / 需要修复后重审}
```

### 质量门禁（阶段 2）

Phase 2 门禁见 `protocols/quality-gates.md` T5 行：

Phase 2 通过标准见 `protocols/quality-gates.md` T5 行（P1/P2 计数要求）。P3 问题不强制修复，记入最终报告。

P1/P2 问题必须修复后重审（返回阶段 1 针对性修复）。重试上限见 `protocols/loop-protocol.md` 统一重试规则（T5 Phase 2 审查-修复循环最多 3 轮）。

---

## 阶段 3: 测试验证

verifier subagent（调度方式见 `protocols/agent-dispatch.md` verifier 章节）：

```text
你是 verifier subagent，负责运行所有测试和验证。

执行流程：
1. 读取 protocols/quality-gates.md 工程类任务门禁章节和路由注册门禁章节
2. 读取 protocols/delivery-phases.md 获取各阶段验证要求
3. 根据本次修改范围和 plan 参数，生成针对性验证清单
4. 按清单逐项执行验证
5. 输出验证报告

代码库路径：{绝对路径}
syntax_check_cmd：{从 autoloop-plan.md 读取}
syntax_check_file_arg：{从 autoloop-plan.md 读取（true/false）}
main_entry_file：{从 autoloop-plan.md 读取}
new_router_name：{从 autoloop-plan.md 读取}
migration_check_cmd：{从 autoloop-plan.md 读取}

输出：
每步验证结果（通过/失败+错误信息）
总体结论：通过 / 失败（{失败步骤}）
```

### 质量门禁（阶段 3）

Phase 3 门禁见 `protocols/quality-gates.md` T5 行：

- [ ] 语法验证通过（按 `syntax_check_file_arg` 决定是否附加文件参数）
- [ ] [L1] 路由注册验证通过（无新路由则 N/A）（验证方法见 protocols/quality-gates.md 路由注册门禁）
- [ ] 数据库迁移状态正确：`{migration_check_cmd}`（无迁移则 N/A）

---

## 阶段 4: 部署

```text
部署执行：

1. 提交代码
   git add {所有修改文件（明确列出，不使用 git add -A）}
   git status（确认只有预期的文件）
   git commit -m "{功能描述}

   Co-Authored-By: AutoLoop <noreply@autoloop>"
   git push origin main

2. 线上部署
   {deploy_command}（来自 autoloop-plan.md，变量名见 protocols/loop-protocol.md）

3. 服务健康检查
   检查 {service_list} 中每个服务全部 active（来自 autoloop-plan.md）
   如 service_list = N/A，则跳过此步骤

4. Health check
   curl {health_check_url}
   期望：HTTP 200
   如 health_check_url 为空，则标记 N/A
```

### 质量门禁（阶段 4）

Phase 4 门禁见 `protocols/quality-gates.md` T5 行：

- [ ] git push 成功
- [ ] `{deploy_command}` 执行无报错
- [ ] `{service_list}` 中所有服务全部 active（service_list = N/A 则跳过）
- [ ] Health check（`{health_check_url}`）返回 200（health_check_url 为空则标记 N/A）

---

## 阶段 5: 线上验收 — 阻塞门禁

verifier subagent（调用方式见 `protocols/agent-dispatch.md` verifier 章节），按 project_type 条件化：

```text
你是 verifier subagent，负责线上功能验证。

执行流程：
1. 读取 protocols/delivery-phases.md Phase 5 条件化规则
2. 读取 protocols/quality-gates.md T5 验收门禁
3. 根据 project_type 和本次交付内容，生成针对性验收清单
4. 按清单逐项验证
5. 输出验收报告

project_type：{从 autoloop-plan.md 读取}
acceptance_url：{从 autoloop-plan.md 读取}

输出：
每个验证项的结果（通过/失败+截图或日志）
```

### 阻塞：等待人工确认（阶段 5）

```text
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
阶段 5 阻塞点 — 需要人工确认
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
| 2 审查 | 通过（P1/P2 = 0）| {时间} |
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
