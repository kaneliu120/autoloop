# {功能名} 实施方案

**日期**：{YYYY-MM-DD}
**状态**：待确认 / 开发中 / 已上线
**任务 ID**：autoloop-{YYYYMMDD-HHMMSS}
**作者**：AutoLoop T5 Deliver

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

```sql
-- 新增表（如有）
CREATE TABLE IF NOT EXISTS {table_name} (
    id BIGSERIAL PRIMARY KEY,
    {column} {type} NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 新增列（如有）
ALTER TABLE {table_name}
ADD COLUMN IF NOT EXISTS {column} {type};

-- 新增索引（如有）
CREATE INDEX IF NOT EXISTS idx_{table}_{column}
ON {table_name} ({column});
```

**Alembic 迁移**：新建迁移文件，支持 upgrade() 和 downgrade()

### API 变更

| 方法 | 路径 | 认证 | 请求 Body | 响应格式 | 说明 |
|------|------|------|----------|---------|------|
| GET | /api/v1/{resource} | API Key | — | {schema} | 列表查询 |
| POST | /api/v1/{resource} | API Key | {schema} | {schema} | 创建 |
| PATCH | /api/v1/{resource}/{id} | API Key | {schema} | {schema} | 更新 |

### 前端变更（如有）

| 页面/组件 | 路径 | 改动说明 |
|---------|------|---------|
| {组件名} | {前端路径} | {改动} |

---

## 具体方案

### 后端实现

{描述后端实现方案，包括数据模型设计、路由逻辑、关键函数签名}

#### 数据模型（示例，以实际技术栈为准）

```
# Python/SQLAlchemy 示例：
class {ModelName}(Base):
    __tablename__ = "{table_name}"
    id = mapped_column(BigInteger, primary_key=True)
    {field} = mapped_column({type}, nullable=False)

# Node.js/Prisma 示例：
model {ModelName} {
    id    Int    @id @default(autoincrement())
    {field} {type}
}

# 其他技术栈按对应 ORM/ODM 规范实现
```

#### API 路由（示例，以实际技术栈为准）

```
# Python/FastAPI 示例：
@router.get("/{resource}", response_model=list[{SchemaName}])
async def list_{resource}(session: AsyncSession = Depends(get_session)):
    ...

# Node.js/Express 示例：
router.get('/{resource}', async (req, res) => { ... })

# 主入口注册：{main_entry_file}
```

### 前端实现（如有）

{描述前端实现方案，包括组件结构、状态管理、API 调用方式}

#### 前端代码（示例，以实际技术栈为准）

```
# React/TanStack Query 示例：
const { data } = useQuery({ queryKey: ['{resource}'], queryFn: ... })

# Vue/Pinia 示例：
const store = use{Resource}Store()
await store.fetch{Resource}()

# 其他框架按项目规范实现
```

### 数据库迁移（示例，以实际技术栈为准）

```
# Alembic (Python) 示例：
def upgrade(): op.create_table('{table_name}', ...)
def downgrade(): op.drop_table('{table_name}')

# Prisma 示例：npx prisma migrate dev --name {migration_name}

# 其他按项目实际迁移工具执行
```

---

## 实施步骤

**Step 0**：读取现有相关代码，确认理解现有架构
**Step 1**：创建 Alembic 迁移脚本（数据库先行）
**Step 2**：实现数据模型（{model 文件路径}）
**Step 3**：实现 Schema（Pydantic 模型）
**Step 4**：实现路由函数（{路由文件路径}）
**Step 5**：在 `{main_entry_file}` 注册路由（Python: `include_router`；TypeScript/Node: 按框架规范；其他: 按项目规范）
**Step 6**：实现前端组件（如有，可与 Step 2-5 并行）
**Step 7**：运行所有修改文件的语法检查（`{syntax_check_cmd}`，按 `{syntax_check_file_arg}` 决定是否附加单文件参数）
**Step 8**：代码审查（安全/可靠/接口一致性）
**Step 9**：提交并部署
**Step 10**：线上验收

---

## 风险与缓解

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|---------|
| {风险 1} | 高/中/低 | 高/中/低 | {缓解措施} |
| 数据库迁移失败 | 高 | 低 | downgrade() 支持回滚 |
| 前后端接口不一致 | 中 | 中 | 开发前确认接口 schema |

---

## 验收标准

**功能验收**：
- [ ] {验收标准 1}
- [ ] {验收标准 2}
- [ ] {验收标准 3}

**技术验收**：
- [ ] 所有修改文件通过语法检查（{syntax_check_cmd}，视技术栈而定）
- [ ] 新路由已注册（grep 验证 {main_entry_file}）
- [ ] 代码审查 P1/P2 = 0
- [ ] Health check（{health_check_url}）返回 200
- [ ] {service_list} 中所有服务全部 active

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

# 3. 数据库回滚（如有迁移，以下示例基于 Alembic，以实际技术栈为准）
# Alembic: python -m alembic downgrade -1
# Prisma: npx prisma migrate reset（谨慎使用）
# 其他: 根据技术栈执行对应回滚命令
```

**回滚预计耗时**：{N} 分钟

---

## 审阅记录

| 时间 | 审阅者 | 意见 | 状态 |
|------|--------|------|------|
| {时间} | Kane | {意见} | {待确认/已确认/需修改} |
