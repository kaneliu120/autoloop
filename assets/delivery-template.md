> **Note**: This template was originally the output format for T4 Phase 0.5 (documentation). T4 has since been slimmed down to Phase 1-5 (development → acceptance), and the analysis/documentation phase now lives in the separate product design template (T3). This template is now used for the **product design phase**. T4 consumes the confirmed design document as input for Phase 1.

# {Feature Name} Implementation Plan

**Date**: {YYYY-MM-DD}
**Status**: Paused awaiting confirmation
**Task ID**: autoloop-{YYYYMMDD-HHMMSS}
**Author**: AutoLoop T4 Deliver
**Reviewer**: {Reviewer}

---

## Problem Statement

{Restate the user request in your own words and confirm the understanding is correct. Include background, current state, and expected outcome.}

**Primary goal**: {one sentence}

**Out of scope for this round**:
- {exclusion 1}
- {exclusion 2}

---

## Impact Scope

### Files to Modify

| Absolute file path | Change type | Summary of changes |
|--------------------|-------------|--------------------|
| {path} | Modify | {what to change} |
| {path} | Add | {what to implement} |

### Database Changes

{Database change SQL - write it according to the actual tech stack. If you add tables, columns, or indexes, write the full DDL here, including idempotent guards such as IF NOT EXISTS. If there are no database changes, write "None".}

Use `{migration_check_cmd}` to verify migration status.

### API Changes

| Method | Path | Description |
|--------|------|-------------|
| {method} | {path} | {description} |

### Frontend Changes (if any)

| Page / component | Path | Change summary |
|------------------|------|----------------|
| {component name} | {frontend path} | {change} |

---

## Detailed Plan

### Backend Implementation

{Describe the backend implementation plan, including data model design, routing logic, and key function signatures. Use general language and avoid framework-specific syntax.}

#### Data Model

{Describe the model fields and relationships. See the appendix for technology-stack-specific examples.}

#### API Routes

{Describe the path, method, request parameters, and response format for any new routes.}

Register `{new_router_name}` in `{main_entry_file}`.

### Frontend Implementation (if any)

{Describe the frontend implementation plan, including component structure, state management, and API calls. See the appendix for technology-stack-specific examples.}

### Database Migration

{Describe the migration plan: which new tables / columns / indexes need to be created, how the migration files should be organized, and how rollback (downgrade) will be supported. See the appendix for tool-specific examples.}

---

## Implementation Steps

**Step 0**: Read the existing related code and confirm understanding of the current architecture

**Step 1**: Create the database migration script first; all later development depends on it
- The migration file must include both upgrade and downgrade implementations
- Use idempotent operations to avoid duplicate-execution failures

**Step 2**: Implement the data model ({model file path})

**Step 3**: Implement the request / response schema ({schema file path})

**Step 4**: Implement the route function ({route file path})
- Handle exceptions for all external calls; no silent failures
- Declare the new file in the module export file

**Step 5**: Register `{new_router_name}` in `{main_entry_file}`
- Follow the project's route registration conventions

**Step 6**: Implement frontend components (if any; this can run in parallel with Steps 2-5)

**Step 7**: Run syntax checks on all modified files (`{syntax_check_cmd}`, append a single-file argument only if `{syntax_check_file_arg}` is true)

**Step 8**: Code review (security / reliability / interface consistency); proceed only if P1/P2 = 0

**Step 9**: Commit and deploy (`{deploy_command}`)

**Step 10**: Online acceptance check (visit `{acceptance_url}` and confirm manually)

---

## Risks and Mitigations

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| {risk 1} | P1/P2/P3 | P1/P2/P3 | {mitigation} |
| Database migration failure | High | Low | Support rollback in downgrade |
| Frontend/backend API mismatch | Medium | Medium | Confirm the API contract before development |

---

## Acceptance Criteria

**Functional acceptance**:
- [ ] {acceptance criterion 1}
- [ ] {acceptance criterion 2}
- [ ] {acceptance criterion 3}

**Technical acceptance**:
- [ ] All modified files pass syntax checks (`{syntax_check_cmd}`)
- [ ] New route is registered: `grep -n "{new_router_name}" {main_entry_file}`
- [ ] Database migration status is correct: `{migration_check_cmd}` (skip if N/A)
- [ ] Code review P1/P2 = 0
- [ ] Health check (`{health_check_url}`) returns 200 (skip if N/A)
- [ ] All services in `{service_list}` are active (skip if N/A)

**Online acceptance**:
- [ ] Desktop browser flow works correctly
- [ ] Mobile browser layout works correctly
- [ ] No red console errors
- [ ] No regressions in existing functionality

---

## Rollback Plan

**Trigger condition**: a severe bug is found after deployment and affects production

**Rollback steps**:

1. Git rollback: `git revert {commit_hash} && git push origin main`
2. Redeploy in production: **see delivery-phases.md §Phase 4 deployment commands**
3. Roll back the database, if migrations were applied: **see delivery-phases.md §Phase 4 migration rollback**

**Estimated rollback time**: {N} minutes

---

## Review Log

| Time | Reviewer | Comments | Status |
|------|----------|----------|--------|
| {time} | {reviewer} | {comments} | Pending / Approved / Rejected |

---

## Appendix: Technology-Stack Examples (reference only)

> The following examples are for specific tech stacks and are for reference only. The actual implementation must follow the project's stack and must not copy this appendix into the main plan.

### Python / FastAPI Example

**Data model (SQLAlchemy)**:
```python
# Example, adjust to the actual tech stack
class ExampleModel(Base):
    __tablename__ = "examples"
    id = mapped_column(BigInteger, primary_key=True)
    name = mapped_column(String(255), nullable=False)
    created_at = mapped_column(DateTime(timezone=True), server_default=func.now())
```

**API route registration (main.py)**:
```python
# Example: register a new route in main.py
from backend.api.example import example_router
app.include_router(example_router, prefix="/api/v1")
```

**Database migration (Alembic)**:
```python
# Example: alembic/versions/xxxx_add_examples.py
def upgrade():
    op.create_table("examples", ...)

def downgrade():
    op.drop_table("examples")
```

**Migration verification command**: `python -m alembic current && python -m alembic check`

**Syntax check command**: `python3 -m py_compile {file path}`

---

### Node.js / TypeScript Example

**Data model (Prisma)**:
```typescript
// Example: schema.prisma
model Example {
  id        Int      @id @default(autoincrement())
  name      String
  createdAt DateTime @default(now())
}
```

**Route registration (app.ts)**:
```typescript
// Example: register a new route in app.ts/index.ts
import { exampleRouter } from './routes/example'
app.use('/api/v1/examples', exampleRouter)
```

**Database migration (Prisma)**: `npx prisma migrate dev --name add_examples`

**Migration verification command**: `npx prisma migrate status`

**Syntax check command**: `npx tsc --noEmit`
