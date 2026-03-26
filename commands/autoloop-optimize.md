---
name: autoloop-optimize
description: >
  AutoLoop T7: 架构/性能/稳定性优化模板。三维度并行全面诊断，
  跨维度协同修复（一个修复改善多个维度），每 5 个修复 checkpoint 重新评分。
  目标：架构≥8/10、性能≥8/10、稳定性≥8/10。
  触发：/autoloop:optimize 或任何需要系统级优化的任务。
---

# AutoLoop T7: Optimize — 架构/性能/稳定性优化

## 执行前提

读取 `autoloop-plan.md` 获取：
- 系统/代码库路径（绝对路径）
- 当前性能指标（如果有）
- 优先优化方向（全部/指定方向）
- 不可修改的部分（API 接口、数据库 schema 等）

---

## 三维度评分标准

### 架构（Architecture）目标：≥ 8/10

| 评分 | 标准 |
|------|------|
| 10 | 完美分层，零循环依赖，统一抽象，部署配置即代码 |
| 9  | 清晰分层，无循环依赖，API 设计一致 |
| 8  | 基本分层清晰，耦合合理，少量不一致 |
| 7  | 分层存在，有些耦合，API 不一致 |
| ≤6 | 混乱耦合，无分层，不可接受 |

**扣分项**：
- 循环依赖：-2 分/每个循环
- 跨层直接访问（路由层直接操作 DB）：-2 分
- API 命名不一致（混合 camelCase/snake_case）：-1 分
- 硬编码配置（非 settings）：-0.5 分/每处
- 重复的业务逻辑（多处实现同一功能）：-1 分
- 巨型文件（> 500 行单文件）：-1 分

### 性能（Performance）目标：≥ 8/10

| 评分 | 标准 |
|------|------|
| 10 | 零 N+1，完善缓存，连接池配置合理，API P95 < 100ms |
| 9  | 无 N+1，主要路径有缓存，连接池配置正确 |
| 8  | 无明显 N+1，有缓存，性能可接受 |
| 7  | 少量 N+1，缓存不完整，某些路径慢 |
| ≤6 | 大量 N+1，无缓存，性能差，不可接受 |

**扣分项**：
- N+1 查询（循环中执行 DB 查询）：-2 分/每处
- 无连接池（每次请求建新连接）：-3 分
- 热路径缺少缓存（频繁查询的数据未缓存）：-1 分
- 同步阻塞调用在 async 函数中：-2 分/每处
- 大列表一次性加载（应该分页）：-1 分
- 前端：未使用 CDN / 图片未优化 / 未代码分割：-1 分/每项

### 稳定性（Stability）目标：≥ 8/10

| 评分 | 标准 |
|------|------|
| 10 | 全链路错误处理，降级策略，健康检查，告警，自动恢复 |
| 9  | 所有外部依赖有降级，健康检查完善，有告警 |
| 8  | 主要路径有降级，基础健康检查，有日志 |
| 7  | 部分降级，健康检查简单，日志不完整 |
| ≤6 | 无降级，无健康检查，不可接受 |

**扣分项**：
- 外部依赖无降级（Redis 宕机 → 500）：-2 分/每个依赖
- 无健康检查端点：-2 分
- 错误日志不完整（catch 了但没有 logger.error 带上下文）：-1 分/每处
- 无超时配置（HTTP 请求、Redis 操作）：-1 分/每处
- 无重试逻辑（应该重试的操作，如发邮件）：-1 分
- 单点故障（无冗余的关键路径）：-2 分

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
   - 路由文件（backend/api/）是否直接操作数据库（应该通过 service 层）
   - 是否有 service 层？还是业务逻辑直接在路由中？
   - 数据模型是否混杂了业务逻辑？

   工具：grep -rn "from backend.db\|from db\|session.execute" backend/api/

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

4. 同步阻塞检测
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
| Redis | 是/否 | 是/否 | 是/否 | 高/中/低 |

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
- 修改后必须通过 py_compile 验证

执行步骤：
1. 读取相关文件（读全，不要猜）
2. 分析影响范围（修改这个会影响哪些调用者）
3. 实施最小化修复
4. 运行验证
5. 报告修改内容

输出：
- 修改文件列表
- 每个文件的关键修改说明
- 验证结果
- 预期对三维度评分的影响
- 是否需要测试关联功能
```

### 常见优化方案模板

**N+1 查询修复**：
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
```

**Redis 降级回退修复**：
```python
# 修复前（Redis 失败直接崩溃）
async def get_cached_data(key: str) -> dict:
    return await redis.get(key)  # RedisError 会 500

# 修复后（有降级）
async def get_cached_data(key: str) -> dict | None:
    try:
        result = await redis.get(key)
        return result
    except RedisError as e:
        logger.warning(f"Redis cache miss for {key}: {e}")
        return None  # 降级到数据库查询
```

**服务层提取修复**：
```python
# 修复前（路由层直接操作 DB）
@router.get("/companies")
async def list_companies(session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(Company))  # 直接在路由层
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

```
全部达标：
  架构 {N}/10 ≥ 8 ✓
  性能 {N}/10 ≥ 8 ✓
  稳定性 {N}/10 ≥ 8 ✓

→ 终止，生成优化报告
```

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
