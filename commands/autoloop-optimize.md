---
name: autoloop-optimize
description: >
  AutoLoop T7: 架构/性能/稳定性优化模板。三维度并行全面诊断，
  跨维度协同修复（一个修复改善多个维度），每 5 个修复 checkpoint 重新评分。
  目标阈值见 protocols/quality-gates.md T7 行。
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

---

## 每轮 OBSERVE 执行规范（Round 2+ 强制）

每轮优化开始前，在执行任何诊断或修复行动之前，必须先完成 OBSERVE Step 0：

```
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

执行流程：
1. 读取 protocols/enterprise-standard.md 架构维度获取完整诊断项和扣分规则
2. 读取 protocols/enterprise-standard.md 架构维度检测命令章节获取检测方法
3. 根据代码库结构，生成针对性架构诊断清单
4. 按清单逐项诊断，运行检测命令
5. 输出架构诊断报告，标注跨维度影响

代码库路径：{绝对路径}

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

执行流程：
1. 读取 protocols/enterprise-standard.md 性能维度获取完整诊断项和扣分规则
2. 读取 protocols/enterprise-standard.md 性能维度检测命令章节获取检测方法
3. 根据代码库结构，生成针对性性能诊断清单
4. 按清单逐项诊断，运行检测命令
5. 输出性能诊断报告，标注最高收益修复项

代码库路径：{绝对路径}

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

执行流程：
1. 读取 protocols/enterprise-standard.md 稳定性维度获取完整诊断项和扣分规则
2. 读取 protocols/enterprise-standard.md 稳定性维度检测命令章节获取检测方法
3. 根据代码库结构，生成针对性稳定性诊断清单
4. 按清单逐项诊断，运行检测命令
5. 输出稳定性诊断报告

代码库路径：{绝对路径}

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

执行流程：
1. 读取 protocols/enterprise-standard.md 获取该问题类型的修复规范和检测方法
2. 读取 protocols/quality-gates.md 获取验证通过标准
3. 根据问题描述和修复建议，制定最小化修复方案
4. 实施修复并运行语法验证
5. 评估修复对三维度的影响

问题 ID：{ID}
类型：{架构/性能/稳定性}
描述：{问题描述}
影响文件：{绝对路径列表}
修复建议：{具体建议}
syntax_check_cmd：{从 autoloop-plan.md 读取}
syntax_check_file_arg：{从 autoloop-plan.md 读取}

约束（不可违反）：
- 不改变 public API 签名（路由路径、请求/响应格式）
- 不改变数据库 schema（除非方案中明确说明）
- 修改后必须通过语法验证

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

### 三维度验证命令

各维度验证命令见 `protocols/enterprise-standard.md` 对应维度的检测命令章节（架构/性能/稳定性），按实际技术栈执行。每个 Checkpoint 必须基于实际运行的命令输出更新分数。

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
全部达标（目标阈值见 protocols/quality-gates.md T7 行）：
  架构 {N}/10  ✓/✗
  性能 {N}/10  ✓/✗
  稳定性 {N}/10  ✓/✗

全部 ✓ → 终止，生成优化报告
任一 ✗ → 继续修复轮次
```

---

## 每轮 REFLECT 执行规范

每个 checkpoint（5 个修复后）完成后，在 EVOLVE 判断之后执行。REFLECT 必须写入文件，不能只在思考中完成（规范见 `protocols/loop-protocol.md` REFLECT 章节）：

写入 `autoloop-findings.md` 的4层反思结构表（问题登记/策略复盘/模式识别/经验教训），格式见 `templates/findings-template.md`：

- **问题登记**：记录本轮发现的架构/性能/稳定性问题、修复是否引入新问题、诊断遗漏、未能修复的遗留项
- **策略复盘**：修复策略/优化方法/验证命令的效果评估（保持 | 避免 | 待验证），实际改进量 vs 预期改进量（策略评价枚举见 protocols/loop-protocol.md 统一状态枚举）
- **模式识别**：反复出现的问题类型（说明有架构级根因）、修复→新问题的因果链、哪些问题有跨维度联动效应
- **经验教训**：哪类优化最有效、哪些验证步骤能发现最多问题、架构/性能/稳定性三维度的系统性教训

---

## 最终优化报告

```markdown
# 系统优化报告

## 评分总览

| 维度 | 优化前 | 优化后 | 目标 | 状态 |
|------|--------|--------|------|------|
| 架构 | {N}/10 | {N}/10 | {阈值见 quality-gates.md T7 行} | 达标 |
| 性能 | {N}/10 | {N}/10 | {阈值见 quality-gates.md T7 行} | 达标 |
| 稳定性 | {N}/10 | {N}/10 | {阈值见 quality-gates.md T7 行} | 达标 |

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
