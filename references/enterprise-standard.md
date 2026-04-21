# Enterprise Standard — Enterprise-Grade Standard Definition

## Overview

This document is the scoring-detail component referenced by `quality-gates.md`. It defines the scoring methods for the T7/T8 dimensions. For pass thresholds, see `quality-gates.md` under "Gate Classification Overview".

It defines the enterprise-grade scoring system used by AutoLoop T7 (Quality) and T8 (Optimize). All scoring rules are concrete and measurable, eliminating subjective judgment.

> **Objectivity principle**: every deduction item in this document uses a measurable threshold or a rule that can be verified by grep or equivalent tooling. Subjective wording such as "clear", "important", "critical", or "frequent" must not be used. Thresholds may be tuned in `parameters.md`.

The scoring dimensions (Security / Reliability / Maintainability / Architecture / Performance / Stability) and their pass standards are **tech-stack-agnostic**. Each dimension includes a "tech-stack-specific checks" subsection with example detection commands.

> **Domain Pack extension**: when `autoloop-plan.md` specifies `domain_pack` (for example, `python-fastapi`), the T7/T8 OBSERVE phase should load `references/domain-pack-{pack_name}.md`. Commands from that pack replace the generic commands in this document, pack-specific weight adjustments override the generic weights, and any extra checks are appended to the deduction rules. See `references/domain-pack-spec.md`.

---

## Security Scoring System

### Pass Standard
See the gate matrix in `quality-gates.md`.

### Full-Score Condition (10/10)

All of the following must hold:

- zero known injection vulnerabilities (SQL injection / command injection / XSS / path traversal)
- all external input has structured validation (type checks / schema validation)
- no sensitive data (passwords / keys / tokens) appears in logs or API responses
- production CORS is configured with explicit domains, not wildcards
- file uploads include type checks and size limits
- security-relevant operations produce audit logs

### Deduction Rules (Generic)

| Issue | Deduction | Severity |
|------|------|---------|
| SQL injection (raw string concatenation used to build SQL) | -4 | P1 |
| Command injection (user input executed in the shell) | -4 | P1 |
| Keys/passwords in API responses | -3 | P1 |
| Keys/passwords in logs | -3 | P1 |
| XSS (frontend directly injects unescaped user input) | -3 | P1 |
| Path traversal (file paths not validated) | -3 | P1 |
| External input lacks structured validation | -2 | P2 |
| Production CORS allows wildcard origins | -1 | P3 |
| File upload lacks type/size limits | -1 | P2 |
| Missing audit log for sensitive operations | -0.5 | P3 |

### Tech-Stack-Specific Checks

> For Node.js/TypeScript and other stacks, see the relevant `references/domain-pack-*.md`.

#### Python/FastAPI

```bash
# SQL injection checks
grep -rn "execute(f\|execute(\".*{" {path}
grep -rn "text(f\|text(\".*{" {path}

# Command injection checks
grep -rn "subprocess\|os.system\|os.popen" {path}
grep -rn "shell=True" {path}

# Sensitive-data checks
grep -rn "password\|secret\|api_key\|token" {path} | grep -i "log\|print\|response"

# CORS checks
grep -rn "allow_origins" {path}

# External input validation checks (Pydantic)
grep -rn "def .*request\|Body(\|Query(\|Path(" {path}
```

---

## Reliability Scoring System

### Pass Standard
See the gate matrix in `quality-gates.md`.

### Full-Score Condition (10/10)

All of the following must hold:

- all external calls (HTTP / cache / DB / files / third-party APIs) have error handling
- no silent failures (no empty `except`/`catch`, and no critical paths that only log at debug level)
- all external dependencies have fallback / degradation behavior (cache service failure must not crash the primary flow)
- critical write operations are protected by transactions
- all HTTP client calls have timeout configuration
- external call retries: every third-party API call and DB write has retry logic (>= 1 retry, with exponential backoff or fixed interval)
- the service exposes a health check endpoint that validates critical dependencies

### Deduction Rules (Generic)

| Issue | Deduction | Severity |
|------|------|---------|
| Silent failure (empty `catch`/`except` swallows the exception) | -2 | P1 |
| Unhandled external HTTP call | -2 | P1 |
| Unhandled cache operation | -2 | P1 |
| Cache failure crashes the primary flow (no fallback) | -2 | P1 |
| External API call without timeout | -1 | P2 |
| Critical write without transaction | -1 | P2 |
| External call without retry: third-party API call or DB write lacks retry logic | -1 each | P2 |
| Missing health check endpoint | -1 | P2 |
| Error logs lack context | -0.5 | P3 |
| Resource leak (connection/file not closed correctly) | -1 | P2 |

### Tech-Stack-Specific Checks

#### Python/FastAPI

```bash
# Silent failure checks
grep -rn "except.*pass" {path}
grep -rn "except:" {path}

# HTTP call checks (then verify try/except coverage)
grep -rn "httpx\|aiohttp\|requests\." {path}

# Redis/cache operation checks
grep -rn "redis\." {path}

# Timeout checks (HTTP calls)
grep -rn "httpx.get\|httpx.post\|client.get" {path} | grep -v "timeout"

# Health-check checks
grep -rn "/health\|health_check\|healthcheck" {path}
```

---

## Maintainability Scoring System

### Pass Standard
See the gate matrix in `quality-gates.md`.

### Full-Score Condition (10/10)

All of the following must hold:

- complete type annotations, no abuse of `any`/`Any`
- no duplicated code blocks (> 10 lines of identical code)
- all configuration is loaded through configuration management (no hard-coded URLs / secrets / numeric constants)
- new modules/files are registered in the entry file / export file
- functions have a single responsibility (main logic functions under 50 lines)
- naming follows conventions: variable/function names >= 3 characters, no unregistered abbreviations, no sequential numeric suffixes such as `temp1`/`temp2`
- tests cover critical paths

### Deduction Rules (Generic)

| Issue | Deduction | Severity |
|------|------|---------|
| New module/route not registered in the entry file | -2 | P1 |
| New file not registered in the export file | -1 | P1 |
| `any` type (TypeScript) | -1 each, up to -3 | P2 |
| `Any` type (Python) | -1 each, up to -3 | P2 |
| `# type: ignore` / `@ts-ignore` | -0.5 each, up to -2 | P2 |
| Duplicated code block (> 10 lines) | -1 each, up to -3 | P2 |
| Hard-coded URL/port | -0.5 each | P2 |
| Hard-coded timeout/limit constants | -0.5 each | P3 |
| Overlong function (> 80 lines) | -0.5 each, up to -2 | P3 |
| Naming violation: variable/function name < 3 chars, contains unregistered abbreviations, or uses sequential numeric suffixes | -0.5 each | P3 |
| Missing return type annotation on a critical function | -0.5 each, up to -1.5 | P3 |
| Test coverage < 60% on critical paths | -1 | P2 |
| Test coverage < 40% on critical paths | -2 | P2 |

### Tech-Stack-Specific Checks

#### Python/FastAPI

```bash
# Any type checks
grep -rn "from typing import.*Any\|: Any\b" {path}

# type: ignore checks
grep -rn "# type: ignore" {path}

# Entry registration checks (main.py)
grep -n "include_router" {main_py_path}

# __init__.py export checks
find {path} -name "__init__.py" -exec grep -l "." {} \;

# Hard-coded URL checks
grep -rn "http://\|https://" {path} | grep -v ".md\|test\|#\|source"

# Long-function detection (rough)
awk '/^    def |^def /{if(lines>50)print FILENAME":"fn": "lines" lines"; fn=$0; lines=0} {lines++}' {file}
```

---

## Architecture Scoring System

### Pass Standard
See the gate matrix in `quality-gates.md`.

### Full-Score Condition (10/10)

- clear layering: entry layer -> business logic layer -> data layer, with boundaries respected
- zero circular dependencies
- consistent API naming and response format
- all configuration managed centrally (no scattered hard-coding)
- functionality grouped by business domain rather than by technical type
- new features added through a registry-driven architecture

### Deduction Rules (Generic)

| Issue | Deduction |
|------|------|
| Circular dependency | -2 each |
| Entry layer accesses the database directly | -2 |
| Business logic placed in the entry layer instead of the logic layer | -1 |
| Inconsistent API naming (REST mixed with RPC) | -1 |
| Inconsistent response format | -1 |
| Functionality mixed by technical type rather than business domain | -0.5 |
| Hard-coded config outside centralized management | -0.5 each |
| Giant file (> 500 lines) | -1 each |

### Tech-Stack-Specific Checks

#### Python/FastAPI

```bash
# Route-layer direct DB access
grep -rn "session.execute\|session.query" {api_path}

# Circular dependency detection
python3 -c "import {module_name}" 2>&1 | grep "circular\|ImportError"

# API naming consistency checks
grep -rn "@router\.\(get\|post\|put\|delete\)" {path} | grep -E "/[a-z]+[A-Z]"
```

---

## Performance Scoring System

### Pass Standard
See the gate matrix in `quality-gates.md`.

### Full-Score Condition (10/10)

- zero N+1 queries, including hidden ORM lazy-loading cases
- database connection pool configured reasonably (`pool_size >= 10` in production)
- cache connection pooling enabled instead of creating a fresh connection on every use
- hot-read queries cached: any query invoked >= 10 times per request and updated <= once per minute has a cache layer
- pagination on list endpoints instead of returning everything at once
- no synchronous calls inside async functions
- high-frequency query fields are covered by indexes

### Deduction Rules (Generic)

| Issue | Deduction |
|------|------|
| N+1 query (clear loop-query pattern) | -2 each, up to -6 |
| No connection pool (new connection for every request) | -3 |
| Synchronous call inside an async function | -2 each |
| Hot query not cached: query meets the >= 10 calls/request and <= 1 update/minute rule but has no cache layer | -1 each |
| Missing pagination (large datasets returned without limits) | -1 each |
| Cache layer has no connection pool | -1 |
| High-frequency query field lacks an index (verified by `EXPLAIN`) | -1 |

### Tech-Stack-Specific Checks

#### Python/FastAPI (SQLAlchemy)

```bash
# Sync/async mixing checks
grep -rn "time.sleep\|requests.get\|requests.post" {path}

# Missing connection pool checks
grep -rn "create_engine\|create_async_engine" {path} | grep -v "pool_size\|NullPool"

# Missing pagination checks (rough)
grep -rn "\.all()\|fetchall()" {path}
```

---

## Stability Scoring System

### Pass Standard
See the gate matrix in `quality-gates.md`.

### Full-Score Condition (10/10)

- all external dependencies have timeout + fallback + retry
- health checks verify all critical dependencies
- structured logging includes request tracing IDs
- critical operations have alerting
- service processes auto-restart after crashes
- database connection pool uses pre-ping or an equivalent health-check setting

### Deduction Rules (Generic)

| Issue | Deduction |
|------|------|
| External dependency has no fallback (failure => 500) | -2 each |
| Missing health check endpoint | -2 |
| Health check does not validate dependencies | -1 |
| HTTP call without timeout | -1 each |
| Cache service lacks timeout configuration | -1 |
| Missing auto-restart configuration | -1 |
| Logs lack request context | -0.5 |
| Same issue as "external call without retry" in the reliability dimension | — |
| Missing alerting: endpoint with error rate > 1% or operation with P95 latency > 5s has no alert configuration | -1 each |
| DB connection pool lacks pre-ping | -0.5 |

### Tech-Stack-Specific Checks

#### Python/FastAPI

```bash
# Health-check detection
grep -rn "/health\|healthcheck" {path}

# Auto-restart detection (systemd)
systemctl status {service_name} | grep "Restart="

# Connection-pool pre-ping detection
grep -rn "create_async_engine" {path} | grep -v "pool_pre_ping"

# HTTP call without timeout
grep -rn "httpx.get\|httpx.post\|client.get\|client.post" {path} | grep -v "timeout"
```

#### Node.js/TypeScript

```bash
# Health-check detection
grep -rn "/health\|healthCheck" {path}

# Auto-restart detection (PM2/systemd)
cat {path}/ecosystem.config.js 2>/dev/null | grep "restart"
systemctl status {service_name} 2>/dev/null | grep "Restart="

# HTTP call without timeout
grep -rn "fetch(\|axios\." {path} | grep -v "timeout\|signal\|AbortController"
```
