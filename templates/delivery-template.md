# {功能名} 实施方案

**日期**：{YYYY-MM-DD}
**状态**：待确认
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

### 数据库变更（当 migration_check_cmd ≠ N/A 时填写，否则删除本节）

{数据库变更SQL — 根据实际技术栈编写。如有新增表、新增列、新增索引，在此写出完整 DDL 语句（包含幂等保护，如 IF NOT EXISTS）。}

使用 `{migration_check_cmd}` 验证迁移状态。

### API 变更（当 new_router_name ≠ N/A 时填写，否则删除本节）

| 方法 | 路径 | 说明 |
|------|------|------|
| {方法} | {路径} | {说明} |

### 前端变更（当 frontend_dir ≠ N/A 时填写，否则删除本节）

| 页面/组件 | 路径 | 改动说明 |
|---------|------|---------|
| {组件名} | {前端路径} | {改动} |

---

## 具体方案

### 核心实现

{描述主要的实现方案。根据 project_type 组织内容：
- backend-api/fullstack：数据模型 → API路由 → 业务逻辑
- frontend-only：组件结构 → 状态管理 → API调用
- script：入口 → 核心逻辑 → 输出处理
- data-pipeline：数据源 → 转换逻辑 → 目标写入
- library：公共API → 内部实现 → 导出}

### 数据库迁移（当 migration_check_cmd ≠ N/A 时）

{迁移方案：新表/列/索引，迁移文件组织，回滚支持。}
使用 `{migration_check_cmd}` 验证迁移状态。

### 路由注册（当 new_router_name ≠ N/A 时）

在 `{main_entry_file}` 注册 `{new_router_name}`。

### 前端实现（当 frontend_dir ≠ N/A 时）

{组件结构、状态管理、API调用方式。}

---

## 实施步骤

**Step 0**：读取现有相关代码，确认理解现有架构

**Step 1**（当 migration_check_cmd ≠ N/A 时）：创建数据库迁移脚本
- 迁移文件包含 upgrade 和 downgrade 实现
- 使用幂等操作防止重复执行报错

**Step 2**：实现核心功能模块
{根据 project_type 描述主要实现，不预设固定步骤序列}

**Step 3**（当 new_router_name ≠ N/A 时）：在 `{main_entry_file}` 注册 `{new_router_name}`

**Step 4**（当 frontend_dir ≠ N/A 时）：实现前端组件（可与 Step 2 并行）

**Step 5**：对所有修改文件运行语法检查（`{syntax_check_cmd}`）

**Step 6**：代码审查（安全 / 可靠性 / 接口一致性），P1/P2 = 0 才可继续

**Step 7**（当 deploy_command ≠ N/A 时）：提交代码并部署

**Step 8**（当 acceptance_url ≠ N/A 时）：线上验收，人工确认

---

## 风险与缓解

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|---------|
| {风险 1} | 高/中/低 | 高/中/低 | {缓解措施} |
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
- [ ] （当 new_router_name ≠ N/A 时）路由注册验证通过 — 见下方验证说明
- [ ] （当 migration_check_cmd ≠ N/A 时）数据库迁移状态正确
- [ ] 代码审查 P1/P2 = 0
- [ ] （当 health_check_url ≠ N/A 时）Health check 返回 200
- [ ] （当 service_list ≠ N/A 时）所有服务全部 active

**线上验收**：
- [ ] 浏览器（桌面）功能正常
- [ ] 浏览器（手机）布局正常
- [ ] Console 零红色错误
- [ ] 现有功能无回归

---

## 回滚方案

**触发条件**：部署后发现严重 Bug，影响生产

**回滚步骤**：

```bash
# 1. Git 回滚
git revert {commit_hash}
git push origin main

# 2. 线上重新部署（deploy_command 来自 autoloop-plan.md）
{deploy_command}

# 3. 数据库回滚（如有迁移，使用项目实际的迁移工具执行 downgrade）
# 具体命令参见附录技术栈示例
```

**回滚预计耗时**：{N} 分钟

---

## 审阅记录

| 时间 | 审阅者 | 意见 | 状态 |
|------|--------|------|------|
| {时间} | {审阅者} | {意见} | 待确认 / 已确认 / 需修改 |

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

**迁移验证命令**：
```bash
python -m alembic current && python -m alembic check
```

**语法检查命令**：
```bash
python3 -m py_compile {文件路径}
```

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

**数据库迁移（Prisma）**：
```bash
npx prisma migrate dev --name add_examples
```

**迁移验证命令**：
```bash
npx prisma migrate status
```

**语法检查命令**：
```bash
npx tsc --noEmit
```
