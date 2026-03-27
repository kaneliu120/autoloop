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

### 数据库变更

{数据库变更内容，无则标注"不涉及"}

### API 变更

{API 变更内容，无则标注"不涉及"}

| 方法 | 路径 | 说明 |
|------|------|------|
| {方法} | {路径} | {说明} |

### 前端变更

{前端变更内容，无则标注"不涉及"}

| 页面/组件 | 路径 | 改动说明 |
|---------|------|---------|
| {组件名} | {前端路径} | {改动} |

---

## 具体方案

### 核心实现

{实现方案描述}

### 数据库迁移

{迁移方案描述，无则标注"不涉及"}

### 路由注册

{路由注册描述，无则标注"不涉及"}

### 前端实现

{前端实现描述，无则标注"不涉及"}

---

## 实施步骤

**Step 0**：读取现有相关代码，确认理解现有架构

**Step 1**：{数据库迁移，不涉及则标注"跳过"}

**Step 2**：{核心功能实现}

**Step 3**：{路由注册，不涉及则标注"跳过"}

**Step 4**：{前端实现，不涉及则标注"跳过"}

**Step 5**：对所有修改文件运行语法检查（`{syntax_check_cmd}`）

**Step 6**：代码审查（安全 / 可靠性 / 接口一致性），P1/P2 = 0 才可继续

**Step 7**：{提交代码并部署，不涉及则标注"跳过"}

**Step 8**：人工验收（验收方式见 `protocols/delivery-phases.md` Phase 5）

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
- [ ] 路由注册验证通过（不涉及则标注 N/A）
- [ ] 数据库迁移状态正确（不涉及则标注 N/A）
- [ ] 代码审查 P1/P2 = 0
- [ ] Health check 返回 200（不涉及则标注 N/A）
- [ ] 所有服务全部 active（不涉及则标注 N/A）

**线上验收**（验收方式由 command 根据 project_type 填充，规则见 `protocols/delivery-phases.md` Phase 5）：
- [ ] {验收项 1}
- [ ] {验收项 2}
- [ ] {验收项 3}
- [ ] 现有功能无回归

---

## 回滚方案

**触发条件**：部署后发现严重 Bug，影响生产

**回滚步骤**：

```bash
# 1. Git 回滚
git revert {commit_hash}
git push origin main

# 2. 重新部署（不涉及则跳过）
{deploy_command}

# 3. 数据库回滚（不涉及则跳过）
{数据库回滚命令}
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
python3 -m py_compile
# 裸命令，不含文件参数占位符；文件参数由 syntax_check_file_arg 控制是否追加
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
