# Enterprise Standard — 企业级标准定义

## 概述

本文档定义 AutoLoop T6（Quality）和 T7（Optimize）使用的企业级标准评分体系。所有评分规则是具体、可量化的，消除主观判断。

---

## 安全性评分体系（Security）

### 目标分数：≥ 9/10

### 满分条件（10/10）
全部满足：
- 零已知漏洞（SQL注入/命令注入/XSS/路径穿越）
- 所有外部输入有 Pydantic 模型验证（FastAPI）或类型检查（TypeScript）
- 无敏感数据（密码/密钥/令牌）出现在日志/API 响应中
- 生产环境 CORS 配置了具体域名（非 `*`）
- 文件上传有类型检查和大小限制
- 有安全相关的操作审计日志

### 扣分规则（明确量化）

| 问题 | 扣分 | 严重级别 | 示例 |
|------|------|---------|------|
| SQL 注入（原始字符串拼接）| -4 | P1 | `f"SELECT * FROM users WHERE id={user_id}"` |
| 命令注入（shell 执行用户输入）| -4 | P1 | `subprocess.run(f"ls {path}")` |
| 密钥/密码出现在 API 响应中 | -3 | P1 | 返回的 user 对象包含 password_hash |
| 密钥/密码出现在日志中 | -3 | P1 | `logger.info(f"Auth with key {api_key}")` |
| XSS（前端直接注入用户输入）| -3 | P1 | `dangerouslySetInnerHTML={{__html: userInput}}` |
| 路径穿越（未验证文件路径）| -3 | P1 | `open(f"/uploads/{filename}")` 无路径验证 |
| 外部输入无类型验证 | -2 | P2 | FastAPI 路由接受 `Any` 类型参数 |
| CORS `allow_origins=["*"]` 在生产 | -1 | P3 | — |
| 文件上传无类型/大小限制 | -1 | P2 | — |
| 缺少操作审计日志（敏感操作）| -0.5 | P3 | 删除操作无日志记录 |

### 检测命令

```bash
# SQL 注入检测
grep -rn "execute(f\|execute(\".*{" {路径}
grep -rn "text(f\|text(\".*{" {路径}

# 命令注入检测
grep -rn "subprocess\|os.system\|os.popen" {路径}
grep -rn "shell=True" {路径}

# 敏感数据检测
grep -rn "password\|secret\|api_key\|token" {路径} | grep -i "log\|print\|response"

# CORS 检测
grep -rn "allow_origins" {路径}

# XSS 检测（前端）
grep -rn "dangerouslySetInnerHTML\|innerHTML" {路径}
```

---

## 可靠性评分体系（Reliability）

### 目标分数：≥ 8/10

### 满分条件（10/10）
全部满足：
- 所有外部调用（HTTP/Redis/DB/文件/第三方 API）有 try/except
- 无静默失败（except: pass 或只有 debug 日志的关键路径）
- 所有外部依赖有降级回退（Redis 宕机不崩溃主流程）
- 关键写操作有事务保护
- 所有 HTTP 客户端调用有超时配置
- 重要操作有重试逻辑（带退避）
- 服务有健康检查端点（验证 DB + Redis 连通性）

### 扣分规则

| 问题 | 扣分 | 严重级别 | 示例 |
|------|------|---------|------|
| 静默失败（`except: pass`）| -2 | P1 | `except Exception: pass` |
| 未捕获的外部 HTTP 调用 | -2 | P1 | `httpx.get(url)` 无 try/except |
| 未捕获的 Redis 操作 | -2 | P1 | `await redis.get(key)` 无 try/except |
| Redis 失败导致主流程崩溃（无降级）| -2 | P1 | 缓存读取失败 → 500 |
| 外部 API 调用无超时 | -1 | P2 | `httpx.get(url)` 无 timeout 参数 |
| 关键写操作无事务 | -1 | P2 | 多表写入无 `async with session.begin()` |
| 无重试逻辑（应该重试的操作）| -1 | P2 | 发邮件失败直接放弃，无重试 |
| 无健康检查端点 | -1 | P2 | 没有 `/health` 或 `/api/health` |
| 错误日志缺少上下文 | -0.5 | P3 | `logger.error("Error")` 没有 exc_info |
| 资源泄漏（连接/文件未关闭）| -1 | P2 | 使用 `open()` 而非 `with open()` |

### 检测命令

```bash
# 静默失败检测
grep -rn "except.*pass" {路径}
grep -rn "except:" {路径}

# HTTP 调用检测（然后检查是否有 try/except）
grep -rn "httpx\|aiohttp\|requests\." {路径}

# Redis 操作检测
grep -rn "redis\." {路径}

# 超时检测（HTTP 调用）
grep -rn "httpx.get\|httpx.post\|client.get" {路径} | grep -v "timeout"

# 健康检查检测
grep -rn "/health\|health_check\|healthcheck" {路径}
```

---

## 可维护性评分体系（Maintainability）

### 目标分数：≥ 8/10

### 满分条件（10/10）
全部满足：
- TypeScript/Python 类型标注完整，无 `any`/`Any` 滥用
- 无重复代码块（> 10 行完全相同的代码）
- 所有配置通过 settings 获取（无硬编码）
- 新文件有 `__init__.py` 导出
- 新路由在 `main.py` 注册
- 函数单一职责（主要逻辑函数 < 50 行）
- 命名语义清晰（无单字母变量名，无缩写）
- 有测试覆盖（关键路径）

### 扣分规则

| 问题 | 扣分 | 严重级别 | 示例 |
|------|------|---------|------|
| 新路由未在 main.py 注册 | -2 | P1 | 路由文件存在但 main.py 没有 include_router |
| 新文件未在 __init__.py 导出 | -1 | P1 | 新建了 service 文件但 __init__.py 未更新 |
| `any` 类型（TypeScript）| -1/处 | P2 | 最多 -3 |
| `Any` 类型（Python，from typing）| -1/处 | P2 | 最多 -3 |
| `# type: ignore` | -0.5/处 | P2 | 最多 -2 |
| 重复代码块（> 10 行）| -1/处 | P2 | 最多 -3 |
| 硬编码 URL/端口 | -0.5/处 | P2 | `"http://localhost:8000"` 直接在代码中 |
| 硬编码超时/限制数字 | -0.5/处 | P3 | `time.sleep(3600)` 应用 INTERVAL 常量 |
| 函数过长（> 80 行）| -0.5/处 | P3 | 最多 -2 |
| 命名不清晰 | -0.5/处 | P3 | `d`, `tmp`, `x`, `res` 作为变量名 |
| 无返回类型标注（关键函数）| -0.5/函数 | P3 | 最多 -1.5 |

### 检测命令

```bash
# any 类型检测（TypeScript）
grep -rn ": any\b\|<any>\|as any" {路径}

# Any 类型检测（Python）
grep -rn "from typing import.*Any\|: Any\b" {路径}

# type: ignore 检测
grep -rn "# type: ignore" {路径}

# main.py 路由注册检测
grep -n "include_router" {main.py}

# 硬编码 URL 检测
grep -rn "http://\|https://" {路径} | grep -v ".md\|test\|#\|来源"

# 长函数检测（Python，粗略）
awk '/^    def |^def /{if(lines>50)print FILENAME":"fn": "lines" lines"; fn=$0; lines=0} {lines++}' {文件}
```

---

## 架构评分体系（Architecture）

### 目标分数：≥ 8/10（T7）

### 满分条件（10/10）
- 清晰三层分离：路由层 → 服务层 → 数据层
- 零循环依赖
- API 命名和响应格式统一
- 所有配置集中管理（settings）
- 功能按域划分（不是按技术类型混合）
- 新功能通过注册表添加（注册表驱动架构）

### 扣分规则

| 问题 | 扣分 | 示例 |
|------|------|------|
| 循环依赖 | -2/个 | A import B，B import A |
| 路由层直接访问数据库 | -2 | router 文件中有 `session.execute` |
| 业务逻辑在路由层（不在 service 层）| -1 | 超过 10 行的数据处理在路由函数中 |
| API 命名不一致（RESTful 混用 RPC）| -1 | `/getCompanies` 和 `/companies` 并存 |
| 响应格式不一致 | -1 | 有的返回 `{data: []}` 有的返回 `[]` |
| 功能按技术类型混合（不按业务域）| -0.5 | 所有 DB 操作在一个文件，不按功能分 |
| 配置硬编码（非 settings）| -0.5/处 | — |
| 巨型文件（> 500 行）| -1/个 | — |

---

## 性能评分体系（Performance）

### 目标分数：≥ 8/10（T7）

### 满分条件（10/10）
- 零 N+1 查询（包括隐藏的 ORM 懒加载）
- 数据库连接池配置合理（pool_size ≥ 10，生产）
- Redis 连接池（不每次新建连接）
- 热路径有缓存（频繁读、低更新的数据）
- 分页查询（列表 API 不一次性返回所有数据）
- 无同步阻塞在 async 函数中
- 索引覆盖高频查询字段

### 扣分规则

| 问题 | 扣分 | 示例 |
|------|------|------|
| N+1 查询（明显的循环查询）| -2/处 | 最多 -6 |
| 无连接池 | -3 | 每次请求 `create_engine()` 新建连接 |
| 同步阻塞在 async 函数 | -2/处 | `time.sleep()` 或 `requests.get()` 在 async def |
| 热路径无缓存 | -1/处 | 每次请求都查询几乎不变的配置数据 |
| 分页缺失（大量数据无限制返回）| -1/处 | `SELECT * FROM leads` 无 LIMIT |
| Redis 无连接池 | -1 | `redis.from_url()` 在每次函数调用中 |

---

## 稳定性评分体系（Stability）

### 目标分数：≥ 8/10（T7）

### 满分条件（10/10）
- 所有外部依赖有超时 + 降级 + 重试
- 健康检查验证所有关键依赖
- 结构化日志（JSON 格式，含 request_id）
- 关键操作有告警机制
- 服务进程崩溃自动重启（systemd）
- 数据库连接池有 `pool_pre_ping=True`

### 扣分规则

| 问题 | 扣分 | 示例 |
|------|------|------|
| 外部依赖无降级（失败 = 500）| -2/个 | Redis 宕机 → 整个 API 不可用 |
| 无健康检查端点 | -2 | 没有 /health |
| 健康检查不验证依赖 | -1 | /health 只返回 {"status":"ok"} 不检查 DB |
| HTTP 调用无超时 | -1/处 | 第三方 API 慢 → 请求永久挂起 |
| Redis 无超时配置 | -1 | Redis 慢 → 阻塞所有缓存操作 |
| 无自动重启配置 | -1 | 进程崩溃需手动重启 |
| 日志无请求上下文 | -0.5 | 无法追踪特定请求的完整链路 |
| 无重试逻辑（关键操作）| -1 | 发邮件失败不重试直接丢失 |
