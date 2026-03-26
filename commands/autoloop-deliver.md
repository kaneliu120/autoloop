---
name: autoloop-deliver
description: >
  AutoLoop T5: 全流程交付模板。从需求到生产的完整 7 阶段交付流程，
  严格映射 CLAUDE.md 强制开发流程。阶段 0.5（文档化）必须人工确认。
  每个阶段有明确质量门禁，不通过不进入下一阶段。
  触发：/autoloop:deliver 或任何需要端到端功能交付的任务。
---

# AutoLoop T5: Deliver — 全流程交付

## 执行前提

读取 `autoloop-plan.md` 获取：
- 功能需求（详细描述）
- 代码库路径（绝对路径）
- 技术栈信息（框架、数据库）
- 部署目标（deploy_target）
- 部署命令（deploy_command）
- 服务列表（service_list）
- 文档输出路径（doc_output_path，默认：工作目录）
- 健康检查 URL（health_check_url）
- 线上验收 URL（acceptance_url）
- 语法检查命令（syntax_check_cmd）
- 主入口文件（main_entry_file）
- 新路由变量名（new_router_name）

**严格遵守 CLAUDE.md 强制开发流程，不可跳步。**

---

## 阶段概览

```
阶段 0  → 分析（planner + researcher）
阶段 0.5 → 文档化（必须人工确认才能继续）⚠️
阶段 1  → 开发（backend-dev + frontend-dev + db-migrator）
阶段 2  → 审查（code-reviewer）
阶段 3  → 测试验证（verifier）
阶段 4  → 部署（git push + deploy.sh）
阶段 5  → 线上验收（verifier + 人工确认）
```

**阻塞门禁（Blocking Gate）**：阶段 0.5 和阶段 5 必须人工确认，系统不自动跳过。

---

## 阶段 0: 分析

### 目标
全面理解需求，识别技术影响面，制定实施方案。

### 执行

**并行运行以下 subagents**（独立，可并行）：

**planner subagent**：
```
你是 planner subagent，负责技术方案设计。

功能需求：
{需求描述}

代码库路径：{绝对路径}

任务：
1. 读取代码库的相关模块（主要读 import 链和调用关系）
2. 识别需要修改的现有文件
3. 识别需要新建的文件
4. 识别数据库变更需求（新增表/列/索引）
5. 识别新增 API 路由（路径、方法、认证要求）
6. 估计实施复杂度和潜在风险

输出：
## 技术方案

### 影响范围
- 修改文件：{文件列表，绝对路径}
- 新建文件：{文件列表，绝对路径}
- 数据库变更：{表结构变更}
- 新增路由：{路由列表}

### 实施顺序
1. {步骤 1}（依赖：无）
2. {步骤 2}（依赖：步骤 1）

### 风险识别
- {风险 1}：{描述}（缓解：{措施}）

### 接口定义
{关键函数/API 的签名}
```

**researcher subagent**（如果需要外部信息）：
```
你是 researcher subagent，调研以下技术实现的最佳实践：

问题：{如：{技术栈} 如何实现 WebSocket 认证 / {ORM} 如何做批量 upsert}

要求：
1. 找到 3 个实际可用的代码示例
2. 分析各方法的优缺点
3. 推荐最适合当前技术栈（{从 autoloop-plan.md 读取的技术栈}）的方案

输出：推荐方案 + 示例代码
```

### 质量门禁（阶段 0）
- [ ] 所有需要修改的文件已识别（通过读取代码确认，不是猜测）
- [ ] 数据库变更已描述（变更内容和原因，无需 SQL — SQL 在阶段 0.5 方案文档中产出）
- [ ] 新增/修改路由已列出（路径和方法，无需完整 schema — schema 在阶段 0.5 方案文档中产出）
- [ ] 风险已识别
- [ ] 实施顺序已确定（解决依赖关系）
- [ ] 验收标准已明确（可测量的功能验收条件）

---

## 阶段 0.5: 文档化 ⚠️ 阻塞门禁

### 目标
将分析结果写成方案文档，获得人工确认后才能开发。

### 生成文档

写入 `{doc_output_path}/{功能名}-{YYYY-MM-DD}.md`（路径来自 autoloop-plan.md 的 doc_output_path，默认为工作目录）。

文档结构（使用 `templates/delivery-template.md`）：

```markdown
# {功能名} 实施方案

**日期**：{YYYY-MM-DD}
**状态**：待确认

---

## 问题描述

{用户的需求，用自己的话重述，确认理解正确}

---

## 影响范围

### 修改文件
| 文件 | 类型 | 改动内容 |
|------|------|---------|
| {绝对路径} | 修改 | {改动说明} |
| {绝对路径} | 新建 | {新建说明} |

### 数据库变更
```sql
-- 新增表/列
{ALTER TABLE 或 CREATE TABLE 语句}
```

### API 变更
| 方法 | 路径 | 认证 | 说明 |
|------|------|------|------|
| POST | /api/v1/... | API Key | ... |

---

## 具体方案

### 后端实现
{设计说明}

### 前端实现（如有）
{设计说明}

### 数据库迁移
{迁移方案}

---

## 实施步骤

1. {步骤 1}
2. {步骤 2}
...

---

## 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| {风险} | {高/中/低} | {措施} |

---

## 验收标准

- [ ] {验收标准 1}
- [ ] {验收标准 2}
- [ ] {验收标准 3}

---

## 回滚方案

{如果部署后出现问题，如何回滚}
```

### 阻塞：等待人工确认

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️  阶段 0.5 阻塞点 — 需要人工确认
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

**1a. 数据库迁移（如有）** — 最先执行，其他开发依赖数据库结构

db-migrator subagent：
```
你是 db-migrator subagent。

任务：创建数据库迁移脚本。

变更内容：
{从方案文档提取的数据库变更}

代码库路径：{绝对路径}
迁移工具：{从 autoloop-plan.md 读取的数据库/ORM 类型}

### 技术栈适配（迁移命令）
根据实际迁移工具执行对应操作：

- Python/Alembic:
  迁移目录：{项目根目录}/backend/db/migrations/
  1. 创建新版本文件（alembic revision --autogenerate 或手动创建）
  2. 实现 upgrade() 和 downgrade()
  3. 使用 IF NOT EXISTS 防止重复执行报错
  4. 验证：python -m alembic upgrade head

- Node.js/Prisma:
  1. 编辑 schema.prisma
  2. 运行 npx prisma migrate dev --name {migration_name}
  3. 验证 migration 文件内容正确

- Node.js/Knex 或 TypeORM:
  1. 创建迁移文件（npx knex migrate:make / npx typeorm migration:generate）
  2. 实现 up() 和 down()
  3. 验证：npx knex migrate:latest 或等效命令

- 其他: 按项目规范执行迁移，必须有回滚方案

通用要求：
- 必须有回滚（downgrade/down/revert）实现
- 使用幂等操作（IF NOT EXISTS / IF EXISTS）

输出：
- 迁移文件路径
- 迁移内容摘要（新增/修改的表/列）
- 回滚方案
- 验证结果
```

**1b. 后端开发** — 数据库迁移后执行

backend-dev subagent：
```
你是 backend-dev subagent，负责后端代码实现。

方案文档：{路径}
技术栈：{从 autoloop-plan.md 读取}
syntax_check_cmd：{从 autoloop-plan.md 读取}
main_entry_file：{从 autoloop-plan.md 读取}

通用要求：
- 所有外部调用有 try/except，不允许静默失败
- 新文件在模块导出文件中声明（__init__.py / index.ts / 其他）
- 新路由在主入口文件（{main_entry_file}）中注册
- 每修改一个文件立即运行 {syntax_check_cmd} 验证

### 技术栈适配
根据 plan 中确认的技术栈执行对应验证：

**Python/FastAPI**:
- 所有路由使用 async def
- 数据库操作使用 SQLAlchemy 2.0 async session
- 运行 python3 -m py_compile {文件路径} 验证每个文件
- 新路由在 `{main_entry_file}` 中 `include_router`

**Node.js/Express 或 Fastify**:
- 路由函数使用 async/await
- 运行 npx tsc --noEmit（如使用 TypeScript）验证
- 新路由在入口文件（app.ts / index.ts）注册

**其他技术栈**:
- 运行 {syntax_check_cmd} 验证
- 按项目规范注册新路由/模块

对每个文件的修改：
1. 读取现有文件（不盲改）
2. 实施修改
3. 运行 {syntax_check_cmd} 验证
4. 报告修改内容

输出：
- 修改/新建的文件列表（绝对路径）
- 每个文件的关键变更摘要
- {syntax_check_cmd} 验证结果（全部通过）
- 主入口路由注册确认（如有新路由）
```

**1c. 前端开发（如有）** — 可与后端并行

frontend-dev subagent：
```
你是 frontend-dev subagent，负责前端代码实现。

方案文档：{路径}
技术栈：{从 autoloop-plan.md 读取}
syntax_check_cmd：{从 autoloop-plan.md 读取}
前端目录：{从 autoloop-plan.md 读取}

通用要求：
- 类型必须正确，无 any 滥用（TypeScript 项目）
- API 调用通过项目规定的代理/封装层
- 每修改一个文件立即运行 {syntax_check_cmd} 验证
- 新组件在 barrel export 文件中导出（如项目有此规范）

### 技术栈适配
根据 plan 中确认的技术栈执行对应验证：

**Next.js/React**:
- API 调用通过 /api/* 路由（Next.js Rewrite 代理）
- 使用项目实际的状态管理库（TanStack Query / SWR / Zustand / 其他）
- 运行 npx tsc --noEmit 验证

**Vue/Nuxt**:
- 运行 vue-tsc --noEmit（如使用 TypeScript）验证
- 使用 Pinia 或项目规范的状态管理

**其他框架**:
- 运行 {syntax_check_cmd} 验证

输出：
- 修改/新建的文件列表（绝对路径）
- {syntax_check_cmd} 验证结果（通过）
```

### 质量门禁（阶段 1）

验证命令根据技术栈执行（参见 plan 中的 `syntax_check_cmd` 和 `main_entry_file`）：
- Python: `python3 -m py_compile {file}` 验证每个修改文件；检查 `__init__.py` 导出；在 `{main_entry_file}` 中检查 `include_router` 注册
- TypeScript/Node: `npx tsc --noEmit`（项目级）；检查 `index.ts` barrel export；在 `{main_entry_file}` 中检查路由注册
- 其他: `{syntax_check_cmd}`（按 `syntax_check_file_arg` 决定是否附加文件参数）

- [ ] 语法验证通过（对每个修改文件运行 `{syntax_check_cmd}`，按 `syntax_check_file_arg` 决定是否附加文件名）
- [ ] 新路由已在 `{main_entry_file}` 注册（`grep -n "include_router.*{new_router_name}" {main_entry_file}` 或等效命令）
- [ ] 新文件已在模块导出文件中声明（Python: `__init__.py`；TypeScript: `index.ts` barrel；其他: 按项目规范）
- [ ] 数据库迁移脚本有 downgrade()
- [ ] 无 except: pass / # type: ignore / any 滥用

---

## 阶段 2: 审查

code-reviewer subagent（对所有修改文件逐一审查）：

```
你是 code-reviewer subagent，对以下文件进行安全+质量审查。

审查文件列表：
{阶段 1 产出的所有修改/新建文件的绝对路径}

审查清单：
□ 安全性：
  - SQL 注入（原始字符串拼接到查询）
  - 命令注入（未校验的参数传入 shell 命令）
  - 路径穿越（用户输入影响文件路径）
  - 敏感数据暴露（密钥/密码在日志或响应中）
  - 输入验证（所有外部输入有类型检查）

□ 可靠性：
  - 所有外部调用（网络/文件/数据库）有 try/except
  - 无静默失败（except: pass 或 except: logger.debug）
  - 数据库操作有事务（关键写操作）
  - Redis 等缓存有降级回退（缓存失败不应该崩溃主流程）

□ 接口一致性：
  - 路由函数使用 async def
  - 返回类型有标注（或有 response_model）
  - 函数命名遵循 snake_case
  - 参数命名语义清晰

□ 代码质量：
  - 无重复代码（DRY 原则）
  - 无硬编码的配置值（应用 settings）
  - 复杂逻辑有注释

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
- [ ] P1 问题（安全漏洞、数据丢失风险）= 0
- [ ] P2 问题（功能缺陷、错误处理缺失）= 0
- [ ] P3 问题（代码质量）≤ 3 个（必须记录，不强制修复）

P1/P2 问题必须修复后重审（返回阶段 1 针对性修复，最多 3 轮）。

---

## 阶段 3: 测试验证

verifier subagent：

```
你是 verifier subagent，负责运行所有测试和验证。

代码库路径：{绝对路径}

验证步骤：

1. Python 语法检查（所有修改文件）
   python3 -m py_compile {每个文件}

2. TypeScript 类型检查（如有前端修改）
   cd {前端目录} && npx tsc --noEmit

3. 路由注册检查（根据技术栈执行对应命令）
   # Python: grep -n "include_router.*{new_router_name}" {main_entry_file}
   # Node.js: grep -n "use\|route" {main_entry_file}
   # 其他: 按项目规范检查主入口的路由注册

4. 新路由功能验证（如果服务器在运行）
   curl -X {方法} {URL} -H "X-API-Key: {key}" {-d "{body}"}
   期望：HTTP 2xx，响应格式正确

5. 数据库迁移验证（如有）
   python -m alembic current
   python -m alembic check

输出：
每步验证结果（通过/失败+错误信息）
总体结论：通过 / 失败（{失败步骤}）
```

### 质量门禁（阶段 3）
- [ ] 语法验证通过（`{syntax_check_cmd}`，按 `syntax_check_file_arg` 决定是否附加文件参数）
- [ ] tsc --noEmit 通过（如有前端 TypeScript）
- [ ] 新路由已在 `{main_entry_file}` 注册（grep 确认）
- [ ] 数据库迁移状态正确

---

## 阶段 4: 部署

```
部署执行：

1. 提交代码
   git add {所有修改文件}
   git status（确认无误）
   git commit -m "{功能描述}

   Co-Authored-By: AutoLoop <noreply@autoloop>"
   git push origin main

2. 线上部署
   {deploy_command}（来自 autoloop-plan.md）

3. 部署后检查
   检查 service_list 中所有服务全部 active：
   {service_list}（来自 autoloop-plan.md）

4. Health check
   curl {health_check_url}
   期望：HTTP 200，{"status": "ok"}
```

### 质量门禁（阶段 4）
- [ ] git push 成功
- [ ] {service_list} 中所有服务全部 active
- [ ] Health check（{health_check_url}）返回 200

---

## 阶段 5: 线上验收 ⚠️ 阻塞门禁

verifier subagent（线上功能验证，统一角色名，参见 protocols/agent-dispatch.md）：

```
你是 verifier subagent，负责线上功能验证。

线上环境：{acceptance_url}（来自 autoloop-plan.md）

验证清单（逐项执行）：
1. 新功能正常工作：{具体步骤}
2. 现有功能无回归：{检查关键功能}
3. 浏览器 Console 零错误
4. API 响应时间正常（< 500ms）

输出：
每个验证项的结果（通过/失败+截图或日志）
```

### 阻塞：等待人工确认

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️  阶段 5 阻塞点 — 需要 Kane 线上确认
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

自动验证结果：{通过/有问题}

请在浏览器（桌面+手机）访问线上环境确认：
1. {验收标准 1}
2. {验收标准 2}
3. {验收标准 3}

确认无误后输入 "verified" 完成任务。
如有问题，描述问题后回滚或继续修复。
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## 每轮 REFLECT 执行规范

在每个阶段完成（EVOLVE/阶段门禁判断）之后，执行：

```
REFLECT:
- 问题登记: 记录本轮发现的代码问题、修复是否引入新问题、审查遗漏
- 策略复盘: 修复策略/审查方法/验证命令的效果评估（保持/避免）
- 模式识别: 反复出现的代码问题类型（说明有架构级根因）、修复→新问题的因果链
- 经验教训: 哪类修复最有效、哪些验证步骤能发现最多问题
将反思结果写入 autoloop-findings.md 的反思章节
```

---

## 交付完成报告

文件名遵循 `commands/autoloop.md` 最终输出文件命名规则（T5: `autoloop-delivery-{feature}-{date}.md`）。

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
{迁移脚本名称}

### 新增 API 路由
{路由列表}

## 发现的问题

本次交付过程中发现但未修复的问题（P3 级）：
{列表}

## 后续建议

{如有遗留事项或优化建议}
```
