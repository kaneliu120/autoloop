# Enterprise Standard — 企业级标准定义

## 概述

本文档定义 AutoLoop T6（Quality）和 T7（Optimize）使用的企业级标准评分体系。所有评分规则是具体、可量化的，消除主观判断。

评分维度（Security / Reliability / Maintainability / Architecture / Performance / Stability）及其目标分数均为**技术栈无关**的通用标准。各维度下设"技术栈特定检测"子节，列出针对具体技术栈的检测命令示例。

---

## 安全性评分体系（Security）

### 目标分数：≥ 9/10

### 满分条件（10/10）

全部满足：

- 零已知注入漏洞（SQL注入/命令注入/XSS/路径穿越）
- 所有外部输入有结构化验证（类型检查/Schema 校验）
- 无敏感数据（密码/密钥/令牌）出现在日志/API 响应中
- 生产环境 CORS 配置了具体域名（非通配符）
- 文件上传有类型检查和大小限制
- 有安全相关的操作审计日志

### 扣分规则（通用）

| 问题 | 扣分 | 严重级别 |
|------|------|---------|
| SQL 注入（原始字符串拼接构造 SQL）| -4 | P1 |
| 命令注入（shell 执行用户输入）| -4 | P1 |
| 密钥/密码出现在 API 响应中 | -3 | P1 |
| 密钥/密码出现在日志中 | -3 | P1 |
| XSS（前端直接注入未转义用户输入）| -3 | P1 |
| 路径穿越（未验证文件路径）| -3 | P1 |
| 外部输入无结构化验证 | -2 | P2 |
| 生产环境 CORS 允许通配符来源 | -1 | P3 |
| 文件上传无类型/大小限制 | -1 | P2 |
| 缺少操作审计日志（敏感操作）| -0.5 | P3 |

### 技术栈特定检测

#### Python/FastAPI

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

# 外部输入验证检测（Pydantic）
grep -rn "def .*request\|Body(\|Query(\|Path(" {路径}
```

#### Node.js/TypeScript

```bash
# SQL 注入检测（原始查询）
grep -rn "query(\`\|query(\".*\${" {路径}

# 命令注入检测
grep -rn "exec(\|spawn(\|execSync(" {路径}

# 敏感数据检测
grep -rn "password\|secret\|apiKey\|token" {路径} | grep -i "console\|log\|res\.json"

# CORS 检测
grep -rn "cors\|origin" {路径} | grep -i "\\*"

# XSS 检测
grep -rn "dangerouslySetInnerHTML\|innerHTML" {路径}
```

#### 通用

```bash
# 硬编码密钥检测
grep -rn "sk-\|pk_\|secret.*=.*['\"]" {路径}

# 路径穿越检测
grep -rn "\.\./\|path\.join\|open(" {路径}
```

---

## 可靠性评分体系（Reliability）

### 目标分数：≥ 8/10

### 满分条件（10/10）

全部满足：

- 所有外部调用（HTTP/缓存/DB/文件/第三方 API）有错误处理
- 无静默失败（只有空 except/catch 或仅 debug 日志的关键路径）
- 所有外部依赖有降级回退（缓存服务宕机不崩溃主流程）
- 关键写操作有事务保护
- 所有 HTTP 客户端调用有超时配置
- 重要操作有重试逻辑（带退避）
- 服务有健康检查端点（验证关键依赖连通性）

### 扣分规则（通用）

| 问题 | 扣分 | 严重级别 |
|------|------|---------|
| 静默失败（空 catch/except 吞掉异常）| -2 | P1 |
| 未处理的外部 HTTP 调用 | -2 | P1 |
| 未处理的缓存操作 | -2 | P1 |
| 缓存失败导致主流程崩溃（无降级）| -2 | P1 |
| 外部 API 调用无超时 | -1 | P2 |
| 关键写操作无事务 | -1 | P2 |
| 无重试逻辑（应该重试的操作）| -1 | P2 |
| 无健康检查端点 | -1 | P2 |
| 错误日志缺少上下文 | -0.5 | P3 |
| 资源泄漏（连接/文件未正确关闭）| -1 | P2 |

### 技术栈特定检测

#### Python/FastAPI

```bash
# 静默失败检测
grep -rn "except.*pass" {路径}
grep -rn "except:" {路径}

# HTTP 调用检测（然后检查是否有 try/except）
grep -rn "httpx\|aiohttp\|requests\." {路径}

# Redis/缓存操作检测
grep -rn "redis\." {路径}

# 超时检测（HTTP 调用）
grep -rn "httpx.get\|httpx.post\|client.get" {路径} | grep -v "timeout"

# 健康检查检测
grep -rn "/health\|health_check\|healthcheck" {路径}
```

#### Node.js/TypeScript

```bash
# 静默失败检测
grep -rn "catch.*{}" {路径}
grep -rn "\.catch(() =>" {路径}

# HTTP 调用检测
grep -rn "fetch(\|axios\.\|got(" {路径}

# 超时检测
grep -rn "fetch(\|axios\." {路径} | grep -v "timeout\|AbortController"

# 健康检查检测
grep -rn "/health\|healthCheck" {路径}
```

---

## 可维护性评分体系（Maintainability）

### 目标分数：≥ 8/10

### 满分条件（10/10）

全部满足：

- 类型标注完整，无 `any`/`Any` 滥用
- 无重复代码块（> 10 行完全相同的代码）
- 所有配置通过配置管理机制获取（无硬编码 URL/密钥/数字常量）
- 新模块/文件已在入口文件/导出文件中注册
- 函数单一职责（主要逻辑函数 < 50 行）
- 命名语义清晰（无单字母变量名，无缩写）
- 有测试覆盖（关键路径）

### 扣分规则（通用）

| 问题 | 扣分 | 严重级别 |
|------|------|---------|
| 新模块/路由未在入口文件注册 | -2 | P1 |
| 新文件未在导出文件注册 | -1 | P1 |
| `any` 类型（TypeScript）| -1/处，最多 -3 | P2 |
| `Any` 类型（Python）| -1/处，最多 -3 | P2 |
| `# type: ignore` / `@ts-ignore` | -0.5/处，最多 -2 | P2 |
| 重复代码块（> 10 行）| -1/处，最多 -3 | P2 |
| 硬编码 URL/端口 | -0.5/处 | P2 |
| 硬编码超时/限制数字 | -0.5/处 | P3 |
| 函数过长（> 80 行）| -0.5/处，最多 -2 | P3 |
| 命名不清晰 | -0.5/处 | P3 |
| 无返回类型标注（关键函数）| -0.5/函数，最多 -1.5 | P3 |
| 测试覆盖率 < 60%（关键路径）| -1 | P2 |
| 测试覆盖率 < 40%（关键路径）| -2 | P2 |

### 技术栈特定检测

#### Python/FastAPI

```bash
# Any 类型检测
grep -rn "from typing import.*Any\|: Any\b" {路径}

# type: ignore 检测
grep -rn "# type: ignore" {路径}

# [L1] 入口注册检测（main.py）（L1 近似检查，已知局限见 quality-gates.md 验证层级章节）
grep -n "include_router" {main.py路径}

# __init__.py 导出检测
find {路径} -name "__init__.py" -exec grep -l "." {} \;

# 硬编码 URL 检测
grep -rn "http://\|https://" {路径} | grep -v ".md\|test\|#\|来源"

# 长函数检测（粗略）
awk '/^    def |^def /{if(lines>50)print FILENAME":"fn": "lines" lines"; fn=$0; lines=0} {lines++}' {文件}
```

#### Node.js/TypeScript

```bash
# any 类型检测
grep -rn ": any\b\|<any>\|as any" {路径}

# ts-ignore 检测
grep -rn "@ts-ignore\|@ts-expect-error" {路径}

# [L1] 入口注册检测（L1 近似检查，已知局限见 quality-gates.md 验证层级章节）
grep -n "import\|require" {main_entry_file}

# 硬编码 URL 检测
grep -rn "http://\|https://" {路径} | grep -v ".md\|test\|//"
```

---

## 架构评分体系（Architecture）

### 目标分数：≥ 8/10（T7）

### 满分条件（10/10）

- 清晰分层：入口层 → 业务逻辑层 → 数据层，各层职责不越界
- 零循环依赖
- API 命名和响应格式统一
- 所有配置集中管理（无分散硬编码）
- 功能按域划分（不是按技术类型混合）
- 新功能通过注册表添加（注册表驱动架构）

### 扣分规则（通用）

| 问题 | 扣分 |
|------|------|
| 循环依赖 | -2/个 |
| 入口层直接访问数据库 | -2 |
| 业务逻辑在入口层（不在逻辑层）| -1 |
| API 命名不一致（RESTful 混用 RPC）| -1 |
| 响应格式不一致 | -1 |
| 功能按技术类型混合（不按业务域）| -0.5 |
| 配置硬编码（非集中管理）| -0.5/处 |
| 巨型文件（> 500 行）| -1/个 |

### 技术栈特定检测

#### Python/FastAPI

```bash
# 路由层直接访问 DB 检测
grep -rn "session.execute\|session.query" {api路径}

# 循环依赖检测
python3 -c "import {模块名}" 2>&1 | grep "circular\|ImportError"

# API 命名一致性检测
grep -rn "@router\.\(get\|post\|put\|delete\)" {路径} | grep -E "/[a-z]+[A-Z]"
```

#### Node.js/TypeScript

```bash
# 路由层直接访问 DB 检测
grep -rn "prisma\.\|db\.\|query(" {routes路径}

# 循环依赖检测（使用 madge 或类似工具）
npx madge --circular {路径}
```

---

## 性能评分体系（Performance）

### 目标分数：≥ 8/10（T7）

### 满分条件（10/10）

- 零 N+1 查询（包括隐藏的 ORM 懒加载）
- 数据库连接池配置合理（生产环境 pool_size ≥ 10）
- 缓存连接池（不每次新建连接）
- 热路径有缓存（频繁读、低更新的数据）
- 分页查询（列表接口不一次性返回所有数据）
- 无同步阻塞在异步函数中
- 索引覆盖高频查询字段

### 扣分规则（通用）

| 问题 | 扣分 |
|------|------|
| N+1 查询（明显的循环查询）| -2/处，最多 -6 |
| 无连接池（每次请求新建连接）| -3 |
| 同步阻塞在异步函数中 | -2/处 |
| 热路径无缓存 | -1/处 |
| 分页缺失（大量数据无限制返回）| -1/处 |
| 缓存层无连接池 | -1 |
| 高频查询字段无索引（EXPLAIN 验证）| -1 |

### 技术栈特定检测

#### Python/FastAPI（SQLAlchemy）

```bash
# 同步阻塞检测
grep -rn "time.sleep\|requests.get\|requests.post" {路径}

# 无连接池检测
grep -rn "create_engine\|create_async_engine" {路径} | grep -v "pool_size\|NullPool"

# 无分页检测（粗略）
grep -rn "\.all()\|fetchall()" {路径}
```

#### Node.js/TypeScript（Prisma/Drizzle）

```bash
# 同步阻塞检测
grep -rn "\.sync\b\|readFileSync\|execSync" {路径}

# N+1 查询检测（循环中含 DB 调用）
grep -rn "for.*await.*find\|map.*await.*find" {路径}

# 无分页检测
grep -rn "findMany\|find(\)" {路径} | grep -v "take\|limit\|skip"
```

---

## 稳定性评分体系（Stability）

### 目标分数：≥ 8/10（T7）

### 满分条件（10/10）

- 所有外部依赖有超时 + 降级 + 重试
- 健康检查验证所有关键依赖
- 结构化日志（含请求追踪 ID）
- 关键操作有告警机制
- 服务进程崩溃自动重启
- 数据库连接池有连接预检（pool_pre_ping 或等效配置）

### 扣分规则（通用）

| 问题 | 扣分 |
|------|------|
| 外部依赖无降级（失败 = 500）| -2/个 |
| 无健康检查端点 | -2 |
| 健康检查不验证依赖 | -1 |
| HTTP 调用无超时 | -1/处 |
| 缓存服务无超时配置 | -1 |
| 无自动重启配置 | -1 |
| 日志无请求上下文 | -0.5 |
| 无重试逻辑（关键操作）| -1 |
| 无告警配置（关键操作）| -1 |
| 数据库连接池无预检 | -0.5 |

### 技术栈特定检测

#### Python/FastAPI

```bash
# 健康检查检测
grep -rn "/health\|healthcheck" {路径}

# 自动重启检测（systemd）
systemctl status {服务名} | grep "Restart="

# 连接池预检检测
grep -rn "create_async_engine" {路径} | grep -v "pool_pre_ping"

# HTTP 调用无超时检测
grep -rn "httpx.get\|httpx.post\|client.get\|client.post" {路径} | grep -v "timeout"
```

#### Node.js/TypeScript

```bash
# 健康检查检测
grep -rn "/health\|healthCheck" {路径}

# 自动重启检测（PM2/systemd）
cat {路径}/ecosystem.config.js 2>/dev/null | grep "restart"
systemctl status {服务名} 2>/dev/null | grep "Restart="

# HTTP 调用无超时检测
grep -rn "fetch(\|axios\." {路径} | grep -v "timeout\|signal\|AbortController"
```
