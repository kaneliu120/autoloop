---
name: autoloop-optimize
description: >
AutoLoop T8: Architecture/performance/stability optimization template. Three-dimensional parallel comprehensive diagnosis,
Cross-dimensional collaborative repair (one repair improves multiple dimensions), rescoring every 5 repair checkpoints.
Goal: Meet references/quality-gates.md T8 gate matrix requirements.
Trigger: /autoloop:optimize or any task that requires system-level optimization.
---

# AutoLoop T8: Optimize — Architecture/Performance/Stability Optimization

## Prerequisites for execution

Read `autoloop-plan.md` to get:
- System/codebase path (absolute path)
- Current performance metrics (if any)
- Prioritize optimization directions (all/specified directions)
- Unmodifiable parts (API interface, database schema, etc.)
- Verification commands (`syntax_check_cmd`, `syntax_check_file_arg`, for variable names see `references/loop-protocol.md` Unified Parameter Glossary)

**Round 2+ OBSERVE starting point**: First read the `autoloop-findings.md` reflection chapter to obtain the remaining issues, effective/ineffective strategies, identified patterns, and lessons learned, and then formulate an optimization plan for this round. See the `references/loop-protocol.md` OBSERVE Step 0 chapter for details.

- **Experience database reading**: Read entries in `references/experience-registry.md` that match the current task type and target dimensions, identify strategies with status "recommended" or "candidate default", and pass them to the DECIDE stage for reference

---

## OBSERVE execution specifications for each round (Round 2+ mandatory)

Before each round of optimization begins, and before any diagnostic or repair actions can be performed, OBSERVE Step 0 must be completed:

```
**Domain Pack Loading**: Perform domain pack automatic detection (see domain-pack-spec.md §Loading mechanism). Scan the working directory technology stack features to automatically load the matching pack; if `domain_pack` is manually specified in the plan, the specified value is used; `domain_pack: none` is explicitly disabled. After loading, use the pack detection command to replace the common command of enterprise-standard.md.

OBSERVE Step 0 (Required for Round 2+, skip baseline collection in Round 1):
Read the reflection chapter of autoloop-findings.md (4-layer structure table)
Get:
- Issue list: Issues left unfixed in the previous round, which ones have been fixed but with poor effect
- Strategy evaluation: "Keep" strategy in the previous round (used first in this round), "Avoid" strategy (excluded in this round), "To be verified" strategy (used with caution in this round and observe the effect)
- Pattern recognition: recurring problem types (architectural-level root causes, prioritized)
- Lessons learned: Which types of optimizations are most effective and which validation steps find the most problems

After completion, scan the current system status and formulate an optimization strategy for this round.
(For the complete specification, see references/loop-protocol.md OBSERVE Step 0 chapter)
```

---

## Three-dimensional scoring criteria

> **See `references/enterprise-standard.md` for complete definitions of scoring criteria and deduction rules. **
> T8 diagnosis and scoring must cover all inspection items and deduction mapping in enterprise-standard.md, and the shortened version cannot be customized.

**Target score**: The quality gate threshold is shown in the `references/quality-gates.md` T8 line (score targets for each dimension of architecture, performance, and stability).

---

## Round 1: Three-dimensional parallel comprehensive diagnosis

**Run 3 diagnostic subagents simultaneously** (parallel):

### Architecture Diagnostic Subagent

```
You are the architecture-diagnostic subagent, responsible for comprehensive architectural diagnostics.

Code library path: {absolute path}

Diagnostic steps:

1. Stratified analysis
Goal: Identify whether there is a clear hierarchy (routing layer → service layer → data layer)

examine:
- Whether the routing file directly operates the database (should pass the service layer)
- Is there a service layer? Or is the business logic directly in the routing?
- Is the data model mixed with business logic?

### Technology stack adaptation (layered check command)
- Python/FastAPI: grep -rn "from.*db\|session.execute" {routing directory, such as backend/api/}
- Node.js: grep -rn "prisma\.\|sequelize\.\|mongoose\." {routing directory, such as src/routes/}
- Others: Search the routing directory for direct database calls based on the project structure

2. Coupling analysis
examine:
- Whether module A directly imports the internal implementation of module B (non-public API)
- Is there a two-way dependency (A import B, B import A)

Tool: Read the import list of each module and draw the dependency graph

3. API design consistency
examine:
- Is the route naming consistent (RESTful vs RPC mixed)
- Is the response format uniform (some return {data:...}, some directly return list)
- Is the error response format uniform?
- Is the paging implementation unified?

4. Configuration management
examine:
- Whether all configurations are obtained through settings
- Are there hardcoded URLs/numbers/paths?

5. Code reuse
examine:
- Whether the same function is implemented in multiple places
- Is there duplicate CRUD code that can be abstracted

Output:
## Architecture Diagnostic Report

### Stratified analysis results
{describe the current layering state}

### Architectural issues discovered

| ID | Type | Impact Files | Severity | Description | Remediation Suggestions | Impact Dimensions |
|----|------|---------|--------|------|---------|---------|
| A001 | Cross-layer access | {path} | High | {description} | {suggestion} | Architecture |

### Architecture Rating

Initial score: 10
Deduction items:...
Architecture score: {N}/10

### Cross-dimensional impact
(Which architectural issues affect both performance and stability)
```

### Performance Diagnostic Subagent

```
You are the performance-diagnostic subagent, responsible for comprehensive performance diagnostics.

Code library path: {absolute path}

Diagnostic steps:

1. N+1 query detection
Find: Execute a database query in a loop
tool:
grep -rn "for.*in.*:" backend/ # Find loops
Then check whether there is session.execute / session.get etc. in the loop body

2. Connection pool check
Find: Database/Redis connection configuration
examine:
- Whether SQLAlchemy pool_size is configured (default 5, production should be larger)
- Whether Redis connections are reused (ConnectionPool)
- Whether to create a new connection for each request

3. Cache coverage analysis
Identification: Which data are hot reads (frequent queries, few changes)
Check: Is this data cached by Redis
Tool: grep -rn "redis\|cache" backend/

4. Synchronous mixed detection
Find: Calling synchronous I/O in an async function
tool:
grep -rn "def " backend/ # Find sync def (non-async)
Check if called directly in async route (apply asyncio.run_in_executor)
Find: time.sleep() in async function

5. Query efficiency
Find: SELECT * Query without LIMIT
Find: Return all data in list API (should be paginated)
Find: Missing indexed frequently queried fields

6. Front-end performance (if any)
examine:
- whether next.config.js has image optimization configuration
- Whether there is code splitting (dynamic import)
- Is the Bundle size reasonable?

Output:
## Performance diagnostic report

### Performance issues found

| ID | Type | Impact Files | Severity | Description | Expected Benefit | Remediation Recommendations |
|----|------|---------|--------|------|---------|---------|
| P001 | N+1 query | {path} | High | {description} | {reduce X queries/requests} | {suggestion} |

### Performance Rating

Initial score: 10
Deduction items:...
Performance Score: {N}/10

### Highest profit repair (TOP 3)
(3 issues expected to improve the most)
```

### Stability Diagnostic Subagent

```
You are the stability-diagnostic subagent, responsible for comprehensive stability diagnostics.

Code library path: {absolute path}

Diagnostic steps:

1. External dependency downgrade check
Identify all external dependencies: Redis / third-party API / mail service / file storage
Check each dependency:
- Whether timeout is configured
- Failure with or without degradation (returning degraded data vs crash)
- Is there retry logic?

2. Error handling integrity
Find: only except Exception as e: but not logger.error(e, exc_info=True)
Find: Exception caught but inaccurate status code returned (200 but actually failed)
Tools: grep -rn "except" backend/ | grep -v "logger"

3. Health Checkup
Check: Is there a /health endpoint
Check: Whether the health check verifies key dependencies (DB connectivity, Redis connectivity)
Check: whether /ready (readiness check) is different from /health (liveness check)

4. Timeout configuration
Find if: httpx/requests/aiohttp calls have timeout
Find: Whether the Redis operation has socket_timeout
Find: Whether the database query has statement_timeout (PostgreSQL parameter)

5. Log integrity
Check: Is there an info log for key operations (request start/completion)
Check: Does the error have enough context (request ID, related data)
Check: Whether there are structured logs (JSON format for easy search)

6. Automatic recovery
Check: whether the worker process crashes and will automatically restart (systemd/supervisor)
Check: Whether the database connection will be automatically reconnected if it is disconnected (SQLAlchemy pool_pre_ping)

Output:
## Stability diagnostic report

### External dependency list

| Dependencies | Timeouts | Downgrades | Retries | Risk Assessment |
|------|--------|--------|--------|---------|
| Redis | Yes/No | Yes/No | Yes/No | P1/P2/P3 |

### Stability issues discovered

| ID | Type | Impact Files | Severity | Description | Impact Scenarios | Remediation Recommendations |
|----|------|---------|--------|------|---------|---------|

### Stability score

Initial score: 10
Deduction items:...
Stability score: {N}/10
```

---

## Cross-dimensional collaborative repair rules

After the first round of diagnosis is completed, a cross-dimensional impact matrix is ​​established:

```markdown
## Cross-dimensional influence matrix

| Issue ID | Description | Architectural Impact | Performance Impact | Stability Impact | Synthesis Priority |
|---------|------|---------|---------|-----------|----------|
| A001 | The routing layer directly accesses the DB | High | Medium (no ORM optimization) | Medium (no unified error handling) | P1 |
| P001 | N+1 Query | Low | High | Low | P1 |
| S001 | Redis no timeout | Low | Low | High | P1 |
```

**Comprehensive Priority Rules**:
- Affects 3 dimensions → highest priority (fix first)
- Affects 2 dimensions → high priority
- Affects 1 dimension → processed according to priority of each dimension

---

## Round 2-N: Collaborative Repair Cycle

### Fix subagent directive (by priority)

- **Work order generation**: Generate a delegation work order according to the corresponding role template of `references/agent-dispatch.md`, fill in the task goal, input data, output format, quality standard, scope limit, current round, and context summary

```
You are the optimization-fix subagent, responsible for fixing the following performance/architecture/stability issues.

Question ID: {ID}
Type: {architecture/performance/stability}
Description: {issue description}
Affected files: {list of absolute paths}
Repair suggestion: {specific suggestion}

Constraints (cannot be violated):
- No changes to public API signature (routing path, request/response format)
- Do not change the database schema (unless explicitly stated in the schema)
- The modification must pass syntax verification (use {syntax_check_cmd} in autoloop-plan.md)

### Syntax verification command (from autoloop-plan.md)
Use `syntax_check_cmd` and `syntax_check_file_arg` collected in the plan phase (see the `references/loop-protocol.md` unified parameter vocabulary for variable names):
- `syntax_check_file_arg=true`: `{syntax_check_cmd} {modified file}`
- `syntax_check_file_arg=false`: `{syntax_check_cmd}` (no file parameters appended)
- The default values ​​corresponding to different technology stacks are collected in the plan stage and are not hard-coded here.

Execution steps:
1. Read related files (read all, don’t guess)
2. Analyze the impact scope (which callers are affected by this change)
3. Implement minimal fixes
4. Run {syntax_check_cmd} (press syntax_check_file_arg to determine whether to append file parameters)
5. Report modifications

Output:
- Modify file list
- Key modification instructions for each file
- Verification results
- Expected impact on three-dimensional scoring
- Whether it is necessary to test the associated function
```

### Common optimization solution templates (examples, subject to actual technology stack)

**N+1 query fix** (example uses Python/SQLAlchemy, other ORMs are fixed equivalently):

```python
# Before repair (N+1)
companies = await session.execute(select(Company))
for company in companies:
contacts = await session.execute( # N additional queries
        select(Contact).where(Contact.company_id == company.id)
    )

# After repair (JOIN or selectinload)
from sqlalchemy.orm import selectinload

companies = await session.execute(
    select(Company).options(selectinload(Company.contacts))
)
# Node.js/Prisma equivalent: include: { contacts: true }
# Other ORM: use the corresponding eager loading / JOIN mechanism
```

**Cache downgrade fallback fix** (example uses Python/Redis, other cache layers are fixed in equivalent ways):

```python
# Before repair (cache failure and direct crash)
async def get_cached_data(key: str) -> dict:
return await redis.get(key) #Exception will result in 500

# After repair (with downgrade)
async def get_cached_data(key: str) -> dict | None:
    try:
        result = await redis.get(key)
        return result
    except Exception as e:
        logger.warning(f"Cache miss for {key}: {e}")
return None #Downgrade to database query
# Node.js equivalent: same try/catch pattern
```

**Service layer extraction fix** (the example uses Python/FastAPI, other frameworks are fixed in an equivalent layered manner):

```python
# Before repair (routing layer directly operates DB)
@router.get("/companies")
async def list_companies(session: AsyncSession = Depends(get_session)):
result = await session.execute(select(Company)) # The routing layer directly checks the database
    return result.scalars().all()

# After repair (through service layer)
# backend/services/company_service.py
async def list_companies(session: AsyncSession) -> list[Company]:
    result = await session.execute(select(Company))
    return result.scalars().all()

# backend/api/companies.py
@router.get("/companies")
async def list_companies_route(session: AsyncSession = Depends(get_session)):
    return await company_service.list_companies(session)
# Node.js/Express equivalent: controller calls service, service operates repository
```

---

## Checkpoint after every 5 repairs

Each Checkpoint must re-run the verification command of the corresponding dimension, and score updates based solely on code review are not allowed.

### Architecture dimension verification (must be performed after architecture-related repairs)

```bash
# Dependency analysis (if tools are available)
import-linter --config .importlinter # or dep-tree src/
# Alternative: Manually grep circular dependencies
python3 -c "
import sys, importlib
# Try to import key modules and catch circular import errors
try: import {main module}; print('OK')
except ImportError as e: print('Circular dependency:', e)
"
# Cross-layer access detection
grep -rn "from.*db\|session.execute" {routing layer directory} | grep -v "Depends\|get_session"
```

### Performance dimension verification (must be performed after performance-related repairs)

```bash
# Key query EXPLAIN ANALYZE (if there is a database)
# psql -c "EXPLAIN ANALYZE {key query statement}"

# API response time sampling (if the service is running)
for i in 1 2 3 4 5; do
curl -o /dev/null -s -w "%{time_total}s\n" {health_url or key API endpoint}
done

# Front-end bundle analysis (if there is a front-end and the tool is available)
# npx next build --profile 2>&1 | grep "First Load JS"
```

### Stability dimension verification (must be performed after stability-related repairs)

```bash
# error handling coverage statistics
TOTAL=$(grep -rn "def \|async def " {code directory} | wc -l)
WITH_TRY=$(grep -rn -A5 "def \|async def " {code directory} | grep -c "try:")
echo "Total number of functions: $TOTAL, with try/except: $WITH_TRY"

# Silent failure detection
grep -rn "except.*pass\|except:$" {code directory}

# Service status check (if there is container deployment)
# docker ps --format "table {{.Names}}\t{{.Status}}"
```

```
Checkpoint ({N} fixes completed)

Verification results (must be based on the output of the actual command run above):
Architecture verification: {circular dependency detection result / cross-layer access count}
Performance verification: {average API response time / query duration}
Stability verification: {error handling coverage / silent failure count}

Score update (recalculated based on verification results, not estimated):
Architecture: {old} → {new} ({+/-}, based on: {verification command output summary})
Performance: {old} → {new} ({+/-}, based on: {verification command output summary})
Stability: {old} → {new} ({+/-}, based on: {verification command output summary})

Remaining questions: {N} (P1: {N} P2: {N} P3: {N})

New problem (introduced by fix): {N items, description}

Continue to optimize the plan:
Next 5 fixes: {list}
```

---

## Termination condition

See line `references/quality-gates.md` T8 for compliance judgment.

```
All standards are met (the target value is based on quality-gates-engineering.md T8 behavior):
Architecture {N}/10 ≥ Target ✓
Performance {N}/10 ≥ Target ✓
Stability {N}/10 ≥ Target ✓

→ Terminate and generate optimization report
```

---

## Each round of REFLECT execution specifications

After each checkpoint (every 5 fixes), execute this after the EVOLVE decision. REFLECT must be written to a file and cannot be done only in thought (see the `references/loop-protocol.md` REFLECT chapter for details):

Write a 4-layer reflection structure table (problem registration/strategy review/pattern recognition/lessons learned) written into `autoloop-findings.md`. The format is shown in `assets/findings-template.md`:

- **Issue Registration**: Record the architecture/performance/stability issues discovered in this round, whether the repair introduces new issues, diagnosis omissions, and remaining items that cannot be repaired.
- **Strategy review**: Effect evaluation of repair strategy/optimization method/verification command (keep | avoid | to be verified), actual improvement vs. expected improvement (for strategy evaluation enumeration, see references/loop-data-schema.md unified status enumeration)
- **Pattern Recognition**: Recurring problem types (indicating architectural-level root causes), repair → causal chain of new problems, which problems have cross-dimensional linkage effects
- **Lessons learned**: Which type of optimization is most effective, which verification steps can find the most problems, and systematic lessons from the three dimensions of architecture/performance/stability
- **Experience write back**: Write the current round of strategy effects into `references/experience-registry.md` (strategy ID, applicable scenarios, effect score, execution context, follow the effect record table format)

---

## Final optimization report

```markdown
# System optimization report

## Rating overview

| Dimensions | Before optimization | After optimization | Goal | Status |
|------|--------|--------|------|------|
| Architecture | {N}/10 | {N}/10 | ≥8/10 | Compliance |
| Performance | {N}/10 | {N}/10 | ≥8/10 | Compliance |
| Stability | {N}/10 | {N}/10 | ≥8/10 | Compliance |

## Key improvements

### Architecture
{top 3 improvements, one sentence each}

### Performance
{top 3 improvements, with quantitative data if available}

### Stability
{top 3 improvements}

## Complete fix list

| Number | Problem | Type | Fix | Impact Dimension |
|------|------|------|---------|---------|

## Remaining issues (not handled by P3)

{list, with reasons it was not handled}

## Monitoring suggestions

{suggested monitoring metrics to support ongoing verification of optimization results}
```
