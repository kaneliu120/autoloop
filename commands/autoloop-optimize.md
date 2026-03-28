---
name: autoloop-optimize
description: >
  AutoLoop T7: 架构/性能/稳定性优化模板。三维度并行全面诊断，
  跨维度协同修复（一个修复改善多个维度），每 5 个修复 checkpoint 重新评分。
  目标：达到 protocols/quality-gates.md T7 门禁矩阵要求。
  触发：/autoloop:optimize 或任何需要系统级优化的任务。
---

# AutoLoop T7: Optimize — 架构/性能/稳定性优化

## 执行前提

读取 `autoloop-plan.md` 获取：
- 系统/代码库路径（绝对路径）
- 当前性能指标（如果有）
- 优先优化方向（全部/指定方向）
- 不可修改的部分（API 接口、数据库 schema 等）
- 验证命令（`syntax_check_cmd`、`syntax_check_file_arg`，变量名见 `protocols/loop-protocol.md` 统一参数词汇表）

**Round 2+ OBSERVE 起点**：先读取 `autoloop-findings.md` 反思章节，获取遗留问题、有效/无效策略、已识别模式、经验教训，再制定本轮优化计划。详见 `protocols/loop-protocol.md` OBSERVE Step 0 章节。

- **经验库读取**: 读取 `protocols/experience-registry.md` 中与当前任务类型和目标维度匹配的条目，识别状态为「推荐」或「候选默认」的策略，传递到 DECIDE 阶段参考

---

## 每轮 OBSERVE 执行规范（Round 2+ 强制）

每轮优化开始前，在执行任何诊断或修复行动之前，必须先完成 OBSERVE Step 0：

```
**Domain Pack 加载**：如果 `autoloop-plan.md` 指定了 `domain_pack`（如 `python-fastapi`），读取 `protocols/domain-packs/{pack名}.md`，用其检测命令替换 enterprise-standard.md 的通用命令。未指定则使用通用规则。

OBSERVE Step 0（Round 2+ 必执行，第1轮跳过执行基线采集）：
  读取 autoloop-findings.md 的反思章节（4层结构表）
  获取：
  - 问题清单：上轮遗留未修复的问题，哪些已修复但效果不佳
  - 策略评估：上轮"保持"策略（本轮优先使用）、"避免"策略（本轮排除）、"待验证"策略（本轮谨慎使用并观察效果）
  - 模式识别：反复出现的问题类型（架构级根因，优先处理）
  - 经验教训：哪类优化最有效、哪些验证步骤能发现最多问题

  完成后再扫描当前系统状态并制定本轮优化策略
  （完整规范见 protocols/loop-protocol.md OBSERVE Step 0 章节）
```

---

## 三维度评分标准

> **评分标准和扣分规则完整定义见 `protocols/enterprise-standard.md`。**
> T7 诊断和评分必须覆盖 enterprise-standard.md 中的所有检查项和扣分映射，不得自定义缩水版。

**目标分数**：质量门禁阈值见 `protocols/quality-gates.md` T7 行（架构、性能、稳定性各维度分数目标）。

---

## 第一轮：三维度并行全面诊断

**同时运行 3 个 diagnostic subagents**（并行）：

### Architecture Diagnostic Subagent

```
你是 architecture-diagnostic subagent，负责全面的架构诊断。

代码库路径：{绝对路径}

诊断步骤：

1. 分层分析
   目标：识别是否有清晰的层次结构（路由层 → 服务层 → 数据层）

   检查：
   - 路由文件是否直接操作数据库（应该通过 service 层）
   - 是否有 service 层？还是业务逻辑直接在路由中？
   - 数据模型是否混杂了业务逻辑？

   ### 技术栈适配（分层检查命令）
   - Python/FastAPI: grep -rn "from.*db\|session.execute" {路由目录，如 backend/api/}
   - Node.js: grep -rn "prisma\.\|sequelize\.\|mongoose\." {路由目录，如 src/routes/}
   - 其他: 根据项目结构，在路由目录中搜索直接数据库调用

2. 耦合分析
   检查：
   - 模块 A 是否直接 import 了模块 B 的内部实现（非 public API）
   - 是否有双向依赖（A import B，B import A）

   工具：读取每个模块的 import 列表，绘制依赖图

3. API 设计一致性
   检查：
   - 路由命名是否统一（RESTful vs RPC 混用）
   - 响应格式是否统一（有的返回 {data:...}，有的直接返回 list）
   - 错误响应格式是否统一
   - 分页实现是否统一

4. 配置管理
   检查：
   - 是否所有配置都通过 settings 获取
   - 是否有硬编码的 URL / 数字 / 路径

5. 代码复用
   检查：
   - 是否有相同功能在多处实现
   - 是否有重复的 CRUD 代码可以抽象

输出：
## 架构诊断报告

### 分层分析结果
{描述当前分层状态}

### 发现的架构问题

| ID | 类型 | 影响文件 | 严重度 | 描述 | 修复建议 | 影响维度 |
|----|------|---------|--------|------|---------|---------|
| A001 | 跨层访问 | {路径} | 高 | {描述} | {建议} | 架构 |

### 架构评分

初始分：10
扣分项：...
架构得分：{N}/10

### 跨维度影响
（哪些架构问题同时影响性能或稳定性）
```

### Performance Diagnostic Subagent

```
你是 performance-diagnostic subagent，负责全面的性能诊断。

代码库路径：{绝对路径}

诊断步骤：

1. N+1 查询检测
   查找：在循环中执行数据库查询
   工具：
   grep -rn "for.*in.*:" backend/  # 找循环
   然后检查循环体内是否有 session.execute / session.get 等

2. 连接池检查
   查找：数据库/Redis 连接配置
   检查：
   - SQLAlchemy pool_size 是否配置（默认 5，生产应更大）
   - Redis 连接是否复用（ConnectionPool）
   - 是否每次请求都新建连接

3. 缓存覆盖分析
   识别：哪些数据是热读（频繁查询、变化少）
   检查：这些数据是否有 Redis 缓存
   工具：grep -rn "redis\|cache" backend/

4. 同步混用检测
   查找：在 async 函数中调用同步 I/O
   工具：
   grep -rn "def " backend/  # 找 sync def（非 async）
   检查是否在 async 路由中被直接调用（应用 asyncio.run_in_executor）
   查找：time.sleep() 在 async 函数中

5. 查询效率
   查找：SELECT * 没有 LIMIT 的查询
   查找：在列表 API 中返回所有数据（应该分页）
   查找：缺少索引的高频查询字段

6. 前端性能（如有）
   检查：
   - next.config.js 是否有图片优化配置
   - 是否有代码分割（dynamic import）
   - Bundle 大小是否合理

输出：
## 性能诊断报告

### 发现的性能问题

| ID | 类型 | 影响文件 | 严重度 | 描述 | 预期收益 | 修复建议 |
|----|------|---------|--------|------|---------|---------|
| P001 | N+1查询 | {路径} | 高 | {描述} | {减少X次查询/请求} | {建议} |

### 性能评分

初始分：10
扣分项：...
性能得分：{N}/10

### 最高收益修复（TOP 3）
（预期改善最大的 3 个问题）
```

### Stability Diagnostic Subagent

```
你是 stability-diagnostic subagent，负责全面的稳定性诊断。

代码库路径：{绝对路径}

诊断步骤：

1. 外部依赖降级检查
   识别所有外部依赖：Redis / 第三方 API / 邮件服务 / 文件存储
   对每个依赖检查：
   - 超时是否配置
   - 失败是否有降级（返回降级数据 vs 崩溃）
   - 是否有重试逻辑

2. 错误处理完整性
   查找：只有 except Exception as e: 但没有 logger.error(e, exc_info=True)
   查找：捕获了异常但返回了不准确的状态码（200 但实际失败）
   工具：grep -rn "except" backend/ | grep -v "logger"

3. 健康检查
   检查：是否有 /health 端点
   检查：健康检查是否验证关键依赖（DB 连通性、Redis 连通性）
   检查：是否有 /ready（就绪检查）区别于 /health（存活检查）

4. 超时配置
   查找：httpx / requests / aiohttp 调用是否有 timeout
   查找：Redis 操作是否有 socket_timeout
   查找：数据库查询是否有 statement_timeout（PostgreSQL 参数）

5. 日志完整性
   检查：关键操作是否有 info 日志（请求开始/完成）
   检查：错误是否有足够的上下文（请求 ID、相关数据）
   检查：是否有结构化日志（JSON 格式，便于搜索）

6. 自动恢复
   检查：worker 进程崩溃是否会自动重启（systemd / supervisor）
   检查：数据库连接断开是否会自动重连（SQLAlchemy pool_pre_ping）

输出：
## 稳定性诊断报告

### 外部依赖清单

| 依赖 | 有超时 | 有降级 | 有重试 | 风险评估 |
|------|--------|--------|--------|---------|
| Redis | 是/否 | 是/否 | 是/否 | P1/P2/P3 |

### 发现的稳定性问题

| ID | 类型 | 影响文件 | 严重度 | 描述 | 影响场景 | 修复建议 |
|----|------|---------|--------|------|---------|---------|

### 稳定性评分

初始分：10
扣分项：...
稳定性得分：{N}/10
```

---

## 跨维度协同修复规则

第一轮诊断完成后，建立跨维度影响矩阵：

```markdown
## 跨维度影响矩阵

| 问题 ID | 描述 | 架构影响 | 性能影响 | 稳定性影响 | 综合优先级 |
|---------|------|---------|---------|-----------|----------|
| A001 | 路由层直接访问 DB | 高 | 中（无 ORM 优化）| 中（无统一错误处理）| P1 |
| P001 | N+1 查询 | 低 | 高 | 低 | P1 |
| S001 | Redis 无超时 | 低 | 低 | 高 | P1 |
```

**综合优先级规则**：
- 影响 3 个维度 → 最高优先级（先修复）
- 影响 2 个维度 → 高优先级
- 影响 1 个维度 → 按各维度优先级处理

---

## 第 2-N 轮：协同修复循环

### 修复 subagent 指令（按优先级）

- **工单生成**: 按 `protocols/agent-dispatch.md` 对应角色模板生成委派工单，填充任务目标、输入数据、输出格式、质量标准、范围限制、当前轮次、上下文摘要

```
你是 optimization-fix subagent，负责以下性能/架构/稳定性问题修复。

问题 ID：{ID}
类型：{架构/性能/稳定性}
描述：{问题描述}
影响文件：{绝对路径列表}
修复建议：{具体建议}

约束（不可违反）：
- 不改变 public API 签名（路由路径、请求/响应格式）
- 不改变数据库 schema（除非方案中明确说明）
- 修改后必须通过语法验证（使用 autoloop-plan.md 中的 {syntax_check_cmd}）

### 语法验证命令（来自 autoloop-plan.md）
使用 plan 阶段收集的 `syntax_check_cmd` 和 `syntax_check_file_arg`（变量名见 `protocols/loop-protocol.md` 统一参数词汇表）：
- `syntax_check_file_arg=true`：`{syntax_check_cmd} {修改的文件}`
- `syntax_check_file_arg=false`：`{syntax_check_cmd}`（不附加文件参数）
- 不同技术栈对应的默认值由 plan 阶段收集，不在此处硬编码

执行步骤：
1. 读取相关文件（读全，不要猜）
2. 分析影响范围（修改这个会影响哪些调用者）
3. 实施最小化修复
4. 运行 {syntax_check_cmd}（按 syntax_check_file_arg 决定是否附加文件参数）
5. 报告修改内容

输出：
- 修改文件列表
- 每个文件的关键修改说明
- 验证结果
- 预期对三维度评分的影响
- 是否需要测试关联功能
```

### 常见优化方案模板（示例，以实际技术栈为准）

**N+1 查询修复**（示例使用 Python/SQLAlchemy，其他 ORM 按等效方式修复）：

```python
# 修复前（N+1）
companies = await session.execute(select(Company))
for company in companies:
    contacts = await session.execute(  # N 次额外查询
        select(Contact).where(Contact.company_id == company.id)
    )

# 修复后（JOIN 或 selectinload）
from sqlalchemy.orm import selectinload

companies = await session.execute(
    select(Company).options(selectinload(Company.contacts))
)
# Node.js/Prisma 等效：include: { contacts: true }
# 其他 ORM：使用对应的 eager loading / JOIN 机制
```

**缓存降级回退修复**（示例使用 Python/Redis，其他缓存层按等效方式修复）：

```python
# 修复前（缓存失败直接崩溃）
async def get_cached_data(key: str) -> dict:
    return await redis.get(key)  # 异常会导致 500

# 修复后（有降级）
async def get_cached_data(key: str) -> dict | None:
    try:
        result = await redis.get(key)
        return result
    except Exception as e:
        logger.warning(f"Cache miss for {key}: {e}")
        return None  # 降级到数据库查询
# Node.js 等效：同样的 try/catch 模式
```

**服务层提取修复**（示例使用 Python/FastAPI，其他框架按等效分层方式修复）：

```python
# 修复前（路由层直接操作 DB）
@router.get("/companies")
async def list_companies(session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(Company))  # 路由层直接查库
    return result.scalars().all()

# 修复后（通过 service 层）
# backend/services/company_service.py
async def list_companies(session: AsyncSession) -> list[Company]:
    result = await session.execute(select(Company))
    return result.scalars().all()

# backend/api/companies.py
@router.get("/companies")
async def list_companies_route(session: AsyncSession = Depends(get_session)):
    return await company_service.list_companies(session)
# Node.js/Express 等效：controller 调用 service，service 操作 repository
```

---

## 每 5 个修复后 Checkpoint

每个 Checkpoint 必须重新运行对应维度的验证命令，不允许仅凭代码审查更新分数。

### 架构维度验证（架构相关修复后必须执行）

```bash
# 依赖分析（如工具可用）
import-linter --config .importlinter   # 或 dep-tree src/
# 备选：手动 grep 循环依赖
python3 -c "
import sys, importlib
# 尝试导入关键模块，捕获循环 import 错误
try: import {主模块}; print('OK')
except ImportError as e: print('循环依赖:', e)
"
# 跨层访问检测
grep -rn "from.*db\|session.execute" {路由层目录} | grep -v "Depends\|get_session"
```

### 性能维度验证（性能相关修复后必须执行）

```bash
# 关键查询 EXPLAIN ANALYZE（如有数据库）
# psql -c "EXPLAIN ANALYZE {关键查询语句}"

# API 响应时间采样（如服务在运行）
for i in 1 2 3 4 5; do
  curl -o /dev/null -s -w "%{time_total}s\n" {health_url 或关键 API endpoint}
done

# 前端 bundle 分析（如有前端，且工具可用）
# npx next build --profile 2>&1 | grep "First Load JS"
```

### 稳定性维度验证（稳定性相关修复后必须执行）

```bash
# error handling 覆盖率统计
TOTAL=$(grep -rn "def \|async def " {代码目录} | wc -l)
WITH_TRY=$(grep -rn -A5 "def \|async def " {代码目录} | grep -c "try:")
echo "函数总数: $TOTAL，有 try/except 的: $WITH_TRY"

# 静默失败检测
grep -rn "except.*pass\|except:$" {代码目录}

# 服务状态检查（如有容器部署）
# docker ps --format "table {{.Names}}\t{{.Status}}"
```

```
Checkpoint（已完成 {N} 个修复）

验证结果（必须基于上方实际运行的命令输出）：
  架构验证: {循环依赖检测结果 / 跨层访问数量}
  性能验证: {API平均响应时间 / 查询耗时}
  稳定性验证: {error handling覆盖率 / 静默失败数量}

得分更新（基于验证结果重新计算，非估算）：
  架构：{旧} → {新}（{+/-}，依据：{验证命令输出摘要}）
  性能：{旧} → {新}（{+/-}，依据：{验证命令输出摘要}）
  稳定性：{旧} → {新}（{+/-}，依据：{验证命令输出摘要}）

剩余问题：{N}（P1:{N} P2:{N} P3:{N}）

新增问题（修复引入的）：{N 个，描述}

继续优化计划：
  下 5 个修复：{列表}
```

---

## 终止条件

达标判定见 `protocols/quality-gates.md` T7 行。

```
全部达标（目标值以 quality-gates.md T7 行为准）：
  架构 {N}/10 ≥ 目标 ✓
  性能 {N}/10 ≥ 目标 ✓
  稳定性 {N}/10 ≥ 目标 ✓

→ 终止，生成优化报告
```

---

## 每轮 REFLECT 执行规范

每个 checkpoint（5 个修复后）完成后，在 EVOLVE 判断之后执行。REFLECT 必须写入文件，不能只在思考中完成（规范见 `protocols/loop-protocol.md` REFLECT 章节）：

写入 `autoloop-findings.md` 的4层反思结构表（问题登记/策略复盘/模式识别/经验教训），格式见 `templates/findings-template.md`：

- **问题登记**：记录本轮发现的架构/性能/稳定性问题、修复是否引入新问题、诊断遗漏、未能修复的遗留项
- **策略复盘**：修复策略/优化方法/验证命令的效果评估（保持 | 避免 | 待验证），实际改进量 vs 预期改进量（策略评价枚举见 protocols/loop-protocol.md 统一状态枚举）
- **模式识别**：反复出现的问题类型（说明有架构级根因）、修复→新问题的因果链、哪些问题有跨维度联动效应
- **经验教训**：哪类优化最有效、哪些验证步骤能发现最多问题、架构/性能/稳定性三维度的系统性教训
- **经验写回**: 将本轮策略效果写入 `protocols/experience-registry.md`（策略ID、适用场景、效果评分、执行上下文，遵循效果记录表格式）

---

## 最终优化报告

```markdown
# 系统优化报告

## 评分总览

| 维度 | 优化前 | 优化后 | 目标 | 状态 |
|------|--------|--------|------|------|
| 架构 | {N}/10 | {N}/10 | ≥8/10 | 达标 |
| 性能 | {N}/10 | {N}/10 | ≥8/10 | 达标 |
| 稳定性 | {N}/10 | {N}/10 | ≥8/10 | 达标 |

## 关键改进

### 架构
{TOP 3 改进，各一句话}

### 性能
{TOP 3 改进，含量化数据如可用}

### 稳定性
{TOP 3 改进}

## 完整修复清单

| 编号 | 问题 | 类型 | 修复方案 | 影响维度 |
|------|------|------|---------|---------|

## 遗留问题（P3 未处理）

{列表，说明为何未处理}

## 监控建议

{建议添加的监控指标，便于持续验证优化效果}
```
