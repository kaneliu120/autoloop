> **注意**：此模板原为 T5 Phase 0.5（文档化）的产出格式。T5 已瘦身为 Phase 1-5（开发→验收），
> 分析和文档化阶段已移至独立的产品设计模板。此模板现供**产品设计阶段**使用，
> T5 接收已确认的方案文档作为 Phase 1 的输入。

# {功能名} 实施方案

**日期**：{YYYY-MM-DD}
**状态**：暂停等待确认
**任务 ID**：autoloop-{YYYYMMDD-HHMMSS}
**作者**：AutoLoop T5 Deliver
**审阅者**：{审阅者}

---

## 问题描述

{用自己的话重述用户需求，确认理解正确。包含：背景、现状、期望结果}

**核心目标**：{一句话}

**不在本次范围内**：
- {排除项 1}
- {排除项 2}

---

## 影响范围

### 修改文件

| 文件路径（绝对）| 改动类型 | 改动内容摘要 |
|--------------|---------|------------|
| {路径} | 修改 | {改什么} |
| {路径} | 新建 | {实现什么} |

### 数据库变更

{数据库变更SQL — 根据实际技术栈编写。如有新增表、新增列、新增索引，在此写出完整 DDL 语句（包含幂等保护，如 IF NOT EXISTS）。无数据库变更则填写"无"。}

使用 `{migration_check_cmd}` 验证迁移状态。

### API 变更

| 方法 | 路径 | 说明 |
|------|------|------|
| {方法} | {路径} | {说明} |

### 前端变更（如有）

| 页面/组件 | 路径 | 改动说明 |
|---------|------|---------|
| {组件名} | {前端路径} | {改动} |

---

## 具体方案

### 后端实现

{描述后端实现方案，包括数据模型设计、路由逻辑、关键函数签名。使用通用描述，不依赖特定框架语法。}

#### 数据模型

{描述数据模型的字段和关系。具体实现语法参见附录技术栈示例。}

#### API 路由

{描述新增路由的路径、方法、请求参数、响应格式。}

在 `{main_entry_file}` 注册 `{new_router_name}`。

### 前端实现（如有）

{描述前端实现方案，包括组件结构、状态管理、API 调用方式。具体实现语法参见附录技术栈示例。}

### 数据库迁移

{描述迁移方案：需要创建哪些新表/列/索引，迁移文件如何组织，如何支持回滚（downgrade）。具体迁移工具用法参见附录技术栈示例。}

---

## 实施步骤

**Step 0**：读取现有相关代码，确认理解现有架构

**Step 1**：创建数据库迁移脚本（数据库先行，其他开发依赖此步骤）
- 迁移文件包含 upgrade 和 downgrade 实现
- 使用幂等操作防止重复执行报错

**Step 2**：实现数据模型（{model 文件路径}）

**Step 3**：实现请求/响应 Schema（{schema 文件路径}）

**Step 4**：实现路由函数（{路由文件路径}）
- 所有外部调用有异常处理，不允许静默失败
- 新文件在模块导出文件中声明

**Step 5**：在 `{main_entry_file}` 注册 `{new_router_name}`
- 按项目技术栈的路由注册规范操作

**Step 6**：实现前端组件（如有，可与 Step 2-5 并行）

**Step 7**：对所有修改文件运行语法检查（`{syntax_check_cmd}`，按 `{syntax_check_file_arg}` 决定是否附加单文件参数）

**Step 8**：代码审查（安全 / 可靠性 / 接口一致性），P1/P2 = 0 才可继续

**Step 9**：提交代码并部署（`{deploy_command}`）

**Step 10**：线上验收（访问 `{acceptance_url}`，人工确认）

---

## 风险与缓解

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|---------|
| {风险 1} | P1/P2/P3 | P1/P2/P3 | {缓解措施} |
| 数据库迁移失败 | 高 | 低 | downgrade 支持回滚 |
| 前后端接口不一致 | 中 | 中 | 开发前确认接口定义 |

---

## 验收标准

**功能验收**：
- [ ] {验收标准 1}
- [ ] {验收标准 2}
- [ ] {验收标准 3}

**技术验收**：
- [ ] 所有修改文件通过语法检查（`{syntax_check_cmd}`）
- [ ] 新路由已注册：`grep -n "{new_router_name}" {main_entry_file}`
- [ ] 数据库迁移状态正确：`{migration_check_cmd}`（无迁移则 N/A）
- [ ] 代码审查 P1/P2 = 0
- [ ] Health check（`{health_check_url}`）返回 200（N/A 则跳过）
- [ ] `{service_list}` 中所有服务全部 active（N/A 则跳过）

**线上验收**：
- [ ] 浏览器（桌面）功能正常
- [ ] 浏览器（手机）布局正常
- [ ] Console 零红色错误
- [ ] 现有功能无回归

---

## 回滚方案

**触发条件**：部署后发现严重 Bug，影响生产

**回滚步骤**：

1. Git 回滚：`git revert {commit_hash} && git push origin main`
2. 线上重新部署：**执行命令见 delivery-phases.md §Phase 4 部署**
3. 数据库回滚（如有迁移）：**执行命令见 delivery-phases.md §Phase 4 迁移回滚**

**回滚预计耗时**：{N} 分钟

---

## 审阅记录

| 时间 | 审阅者 | 意见 | 状态 |
|------|--------|------|------|
| {时间} | {审阅者} | {意见} | 待审查 / 通过 / 未通过 |

---

## 附录：技术栈示例（仅供参考）

> 以下内容为特定技术栈的实现示例，仅供参考。实际实现以项目技术栈为准，不得将此附录内容照搬至主体方案中。

### Python/FastAPI 示例

**数据模型（SQLAlchemy）**：
```python
# 示例，按实际技术栈调整
class ExampleModel(Base):
    __tablename__ = "examples"
    id = mapped_column(BigInteger, primary_key=True)
    name = mapped_column(String(255), nullable=False)
    created_at = mapped_column(DateTime(timezone=True), server_default=func.now())
```

**API 路由注册（main.py）**：
```python
# 示例：在 main.py 中注册新路由
from backend.api.example import example_router
app.include_router(example_router, prefix="/api/v1")
```

**数据库迁移（Alembic）**：
```python
# 示例：alembic/versions/xxxx_add_examples.py
def upgrade():
    op.create_table("examples", ...)

def downgrade():
    op.drop_table("examples")
```

**迁移验证命令**：`python -m alembic current && python -m alembic check`

**语法检查命令**：`python3 -m py_compile {文件路径}`

---

### Node.js/TypeScript 示例

**数据模型（Prisma）**：
```typescript
// 示例：schema.prisma
model Example {
  id        Int      @id @default(autoincrement())
  name      String
  createdAt DateTime @default(now())
}
```

**路由注册（app.ts）**：
```typescript
// 示例：在 app.ts/index.ts 中注册新路由
import { exampleRouter } from './routes/example'
app.use('/api/v1/examples', exampleRouter)
```

**数据库迁移（Prisma）**：`npx prisma migrate dev --name add_examples`

**迁移验证命令**：`npx prisma migrate status`

**语法检查命令**：`npx tsc --noEmit`
