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

#### 数据模型

```python
# {模型文件路径}
class {ModelName}(Base):
    __tablename__ = "{table_name}"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    {field}: Mapped[{type}] = mapped_column({SQLAlchemy type}, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
```

#### API 路由

```python
# {路由文件路径}
@router.get("/{resource}", response_model=list[{SchemaName}])
async def list_{resource}(
    session: AsyncSession = Depends(get_session)
) -> list[{SchemaName}]:
    try:
        result = await session.execute(select({ModelName}))
        return result.scalars().all()
    except SQLAlchemyError as e:
        logger.error(f"Database error in list_{resource}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Database error")
```

#### main.py 注册

```python
from backend.api.{module} import router as {module}_router
app.include_router({module}_router, prefix="/api/v1", tags=["{tag}"])
```

### 前端实现（如有）

```typescript
// {组件文件路径}
// 使用 TanStack Query 获取数据
const { data, isLoading } = useQuery({
  queryKey: ['{resource}'],
  queryFn: () => fetch('/api/v1/{resource}').then(r => r.json())
})
```

### 数据库迁移

```python
# backend/db/migrations/versions/{hash}_{description}.py
def upgrade() -> None:
    op.create_table(
        '{table_name}',
        sa.Column('id', sa.BigInteger(), nullable=False),
        # ...
        sa.PrimaryKeyConstraint('id')
    )

def downgrade() -> None:
    op.drop_table('{table_name}')
```

---

## 实施步骤

**Step 0**：读取现有相关代码，确认理解现有架构
**Step 1**：创建 Alembic 迁移脚本（数据库先行）
**Step 2**：实现数据模型（{model 文件路径}）
**Step 3**：实现 Schema（Pydantic 模型）
**Step 4**：实现路由函数（{路由文件路径}）
**Step 5**：在 main.py 注册路由
**Step 6**：实现前端组件（如有，可与 Step 2-5 并行）
**Step 7**：运行所有修改文件的 py_compile / tsc --noEmit
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
- [ ] 所有修改文件 py_compile 通过
- [ ] 新路由在 main.py 注册（grep 验证）
- [ ] 代码审查 P1/P2 = 0
- [ ] Health check 返回 200
- [ ] 4 个服务全部 active

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

# 2. 线上更新
gcloud compute ssh sip-server --zone=asia-southeast1-b \
  --command="cd /opt/sip && git pull origin main && sudo bash deploy.sh"

# 3. 数据库回滚（如有迁移）
python -m alembic downgrade -1
```

**回滚预计耗时**：{N} 分钟

---

## 审阅记录

| 时间 | 审阅者 | 意见 | 状态 |
|------|--------|------|------|
| {时间} | Kane | {意见} | {待确认/已确认/需修改} |
