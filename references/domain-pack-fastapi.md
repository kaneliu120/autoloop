# Python/FastAPI Domain Pack

## Scope

- Stack: Python 3.10+ / FastAPI / SQLAlchemy 2.0 / Pydantic v2
- Applicable templates: T7 Quality / T8 Optimize

---

## Detection Coverage

### Security Checks

```bash
# SQL injection (SQLAlchemy text() + f-string)
grep -rn "text(f\|text(\".*{" {path} --include="*.py"
grep -rn "execute(f\|execute(\".*{" {path} --include="*.py"

# Command injection
grep -rn "subprocess\.\|os\.system\|os\.popen" {path} --include="*.py"
grep -rn "shell=True" {path} --include="*.py"

# Sensitive data exposure
grep -rn "password\|secret\|api_key\|token" {path} --include="*.py" | grep -i "log\|print\|response\|json"

# Pydantic model validation (confirm the API entry has a schema)
grep -rn "def .*request\b\|Body(\|Query(\|Path(\|Depends(" {path} --include="*.py"

# CORS configuration
grep -rn "allow_origins\|CORSMiddleware" {path} --include="*.py"

# Path traversal
grep -rn "open(\|Path(\|os\.path\.join" {path} --include="*.py" | grep -v "test\|spec"
```

### Reliability Checks

```bash
# Silent failures
grep -rn "except.*pass\|except:$" {path} --include="*.py"

# External HTTP calls without try/except
grep -rn "httpx\.\|aiohttp\.\|requests\." {path} --include="*.py"

# Redis/cache operations without exception handling
grep -rn "redis\.\|aioredis\." {path} --include="*.py"

# HTTP timeout checks
grep -rn "httpx\.get\|httpx\.post\|client\.get\|client\.post\|AsyncClient(" {path} --include="*.py" | grep -v "timeout"

# Health checks
grep -rn "/health\|healthcheck\|health_check" {path} --include="*.py"

# SQLAlchemy session leakage (confirm async with / context manager usage)
grep -rn "AsyncSession\|get_db\|session" {path} --include="*.py" | grep -v "async with\|Depends\|yield"
```

### Maintainability Checks

```bash
# Any type abuse
grep -rn "from typing import.*Any\|: Any\b\|-> Any" {path} --include="*.py"

# type: ignore
grep -rn "# type: ignore" {path} --include="*.py"

# Route registration checks
grep -n "include_router\|app\.add_route" {main_entry_file}

# __init__.py exports
find {path} -name "__init__.py" -exec grep -l "." {} \;

# Hard-coded URLs / secrets
grep -rn "http://\|https://\|sk-\|pk_" {path} --include="*.py" | grep -v ".md\|test\|#\|source\|comment"

# Long function detection
awk '/^    def |^def /{if(lines>80)print FILENAME":"fn": "lines" lines"; fn=$0; lines=0} {lines++}' {path}/**/*.py
```

### Architecture Checks (T8)

```bash
# Route layer directly accessing the DB
grep -rn "session\.\|\.execute\|\.query" {api_path} --include="*.py" | grep -v "Depends\|get_db"

# Circular dependencies
python3 -c "import importlib; importlib.import_module('{module_name}')" 2>&1 | grep -i "circular\|ImportError"

# API naming consistency (RESTful)
grep -rn "@router\.\(get\|post\|put\|delete\|patch\)" {path} --include="*.py"
```

### Performance Checks (T8)

```bash
# Mixing sync calls in async functions
grep -rn "time\.sleep\|requests\.get\|requests\.post\|open(" {path} --include="*.py" | grep -v "aiofiles\|async"

# SQLAlchemy connection pool configuration
grep -rn "create_engine\|create_async_engine" {path} --include="*.py" | grep -v "pool_size"

# N+1 queries (queries inside loops)
grep -rn "for.*await.*session\|for.*\.query" {path} --include="*.py"

# No pagination
grep -rn "\.all()\|fetchall()" {path} --include="*.py" | grep -v "limit\|offset\|paginate"
```

### Stability Checks (T8)

```bash
# Health-check dependency validation
grep -rn "/health" {path} --include="*.py" -A 10 | grep -i "redis\|db\|session"

# Auto-restart configuration
systemctl status {service_name} 2>/dev/null | grep "Restart="

# Connection pool precheck
grep -rn "create_async_engine" {path} --include="*.py" | grep -v "pool_pre_ping"

# Structured logging
grep -rn "logging\.\|logger\." {path} --include="*.py" | head -5
```

---

## Weight Adjustments

| Check | Generic penalty | Pack penalty | Reason |
|--------|---------|-------------|---------|
| sync calls in async code | -2 / occurrence | -3 / occurrence | A fully async FastAPI architecture is blocked when sync calls prevent the event loop from serving other requests |
| SQLAlchemy session leakage | — | -2 / occurrence (P1) | Not closing sessions correctly exhausts the connection pool |
| Missing Pydantic model | — | -1 / occurrence (P2) | Type safety is core to FastAPI; no model means no validation |

## Additional Checks

| Check | Penalty | Severity | Description |
|--------|------|---------|------|
| Missing Alembic migration (new column without migration) | -2 | P1 | Production DB and code are out of sync |
| Pydantic model not used at the API entry | -1 / occurrence | P2 | Bypasses type validation |
| SQLAlchemy session not using a context manager | -2 / occurrence | P1 | Connection leak risk |
| BackgroundTask without exception handling | -1 / occurrence | P2 | Background task silently fails |
