# Python/FastAPI Domain Pack

## 适用范围

- 技术栈：Python 3.10+ / FastAPI / SQLAlchemy 2.0 / Pydantic v2
- 适用模板：T6 Quality / T7 Optimize

---

## 检测命令覆盖

### 安全性检测

```bash
# SQL 注入（SQLAlchemy text() + f-string）
grep -rn "text(f\|text(\".*{" {路径} --include="*.py"
grep -rn "execute(f\|execute(\".*{" {路径} --include="*.py"

# 命令注入
grep -rn "subprocess\.\|os\.system\|os\.popen" {路径} --include="*.py"
grep -rn "shell=True" {路径} --include="*.py"

# 敏感数据泄露
grep -rn "password\|secret\|api_key\|token" {路径} --include="*.py" | grep -i "log\|print\|response\|json"

# Pydantic 模型验证（确认 API 入口有 schema）
grep -rn "def .*request\b\|Body(\|Query(\|Path(\|Depends(" {路径} --include="*.py"

# CORS 配置
grep -rn "allow_origins\|CORSMiddleware" {路径} --include="*.py"

# 路径穿越
grep -rn "open(\|Path(\|os\.path\.join" {路径} --include="*.py" | grep -v "test\|spec"
```

### 可靠性检测

```bash
# 静默失败
grep -rn "except.*pass\|except:$" {路径} --include="*.py"

# 外部 HTTP 调用无 try/except
grep -rn "httpx\.\|aiohttp\.\|requests\." {路径} --include="*.py"

# Redis/缓存操作无异常处理
grep -rn "redis\.\|aioredis\." {路径} --include="*.py"

# HTTP 超时检测
grep -rn "httpx\.get\|httpx\.post\|client\.get\|client\.post\|AsyncClient(" {路径} --include="*.py" | grep -v "timeout"

# 健康检查
grep -rn "/health\|healthcheck\|health_check" {路径} --include="*.py"

# SQLAlchemy session 泄漏（确认使用 async with / context manager）
grep -rn "AsyncSession\|get_db\|session" {路径} --include="*.py" | grep -v "async with\|Depends\|yield"
```

### 可维护性检测

```bash
# Any 类型滥用
grep -rn "from typing import.*Any\|: Any\b\|-> Any" {路径} --include="*.py"

# type: ignore
grep -rn "# type: ignore" {路径} --include="*.py"

# 路由注册检查
grep -n "include_router\|app\.add_route" {main_entry_file}

# __init__.py 导出
find {路径} -name "__init__.py" -exec grep -l "." {} \;

# 硬编码 URL/密钥
grep -rn "http://\|https://\|sk-\|pk_" {路径} --include="*.py" | grep -v ".md\|test\|#\|来源\|comment"

# 长函数检测
awk '/^    def |^def /{if(lines>80)print FILENAME":"fn": "lines" lines"; fn=$0; lines=0} {lines++}' {路径}/**/*.py
```

### 架构检测（T7）

```bash
# 路由层直接访问 DB
grep -rn "session\.\|\.execute\|\.query" {api_路径} --include="*.py" | grep -v "Depends\|get_db"

# 循环依赖
python3 -c "import importlib; importlib.import_module('{模块名}')" 2>&1 | grep -i "circular\|ImportError"

# API 命名一致性（RESTful）
grep -rn "@router\.\(get\|post\|put\|delete\|patch\)" {路径} --include="*.py"
```

### 性能检测（T7）

```bash
# 同步混用（async 函数中调用同步库）
grep -rn "time\.sleep\|requests\.get\|requests\.post\|open(" {路径} --include="*.py" | grep -v "aiofiles\|async"

# SQLAlchemy 连接池配置
grep -rn "create_engine\|create_async_engine" {路径} --include="*.py" | grep -v "pool_size"

# N+1 查询（循环中的查询）
grep -rn "for.*await.*session\|for.*\.query" {路径} --include="*.py"

# 无分页
grep -rn "\.all()\|fetchall()" {路径} --include="*.py" | grep -v "limit\|offset\|paginate"
```

### 稳定性检测（T7）

```bash
# 健康检查依赖验证
grep -rn "/health" {路径} --include="*.py" -A 10 | grep -i "redis\|db\|session"

# 自动重启配置
systemctl status {服务名} 2>/dev/null | grep "Restart="

# 连接池预检
grep -rn "create_async_engine" {路径} --include="*.py" | grep -v "pool_pre_ping"

# 结构化日志
grep -rn "logging\.\|logger\." {路径} --include="*.py" | head -5
```

---

## 权重调整

| 检测项 | 通用扣分 | 本 pack 扣分 | 调整原因 |
|--------|---------|-------------|---------|
| async 混用同步调用 | -2/处 | -3/处 | FastAPI 全异步架构，同步混用直接阻塞事件循环 |
| SQLAlchemy session 泄漏 | — | -2/处（P1） | 未正确关闭 session = 连接池耗尽 |
| Pydantic model 缺失 | — | -1/处（P2） | FastAPI 的类型安全核心，无 model = 无验证 |

## 新增检测项

| 检测项 | 扣分 | 严重级别 | 说明 |
|--------|------|---------|------|
| Alembic 迁移缺失（新增列无 migration） | -2 | P1 | 线上 DB 与代码不同步 |
| Pydantic model 未用于 API 入口 | -1/处 | P2 | 绕过类型验证 |
| SQLAlchemy session 未用 context manager | -2/处 | P1 | 连接泄漏风险 |
| BackgroundTask 无异常处理 | -1/处 | P2 | 后台任务静默失败 |
