# Delivery Phases — Delivery Phase Specification

## Overview

This document defines the five delivery phases of AutoLoop T4 (Deliver), strictly aligned with the mandatory development flow in `CLAUDE.md`. Each phase has explicit inputs, outputs, quality gates, and pause conditions.

---

## Phase Mapping

| AutoLoop Phase | CLAUDE.md Phase | Notes |
|-------------|--------------|------|
| Phase 1: Development | Phase 1: Development | `backend-dev` + `frontend-dev` + `db-migrator` in parallel |
| Phase 2: Review | Phase 2: Review | Serial review by `code-reviewer` |
| Phase 3: Testing | Phase 3: Test and Verification | Executed by `verifier` |
| Phase 4: Deployment | Phase 4: Deploy to Production | `git push` + `{deploy_command}` |
| Phase 5: Acceptance | Phase 5: Production Acceptance | `verifier` + human confirmation |

---

## Phase 1: Development

### Inputs

- an approved solution document (from product design or `autoloop-plan.md`)
- repository path

### Execution Order (dependency-driven)

**1a. Database migration (first; required by all downstream development)**:
- `db-migrator` subagent
- create the migration script (both upgrade and downgrade implemented)
- validate the script syntax (`{syntax_check_cmd}`)

**1b. Backend development (after the database migration completes)**:
- `backend-dev` subagent
- implement backend features one by one according to the solution
- run `{syntax_check_cmd}` immediately after each file change (append the file argument only when `syntax_check_file_arg` is true)
- register new routes in `{main_entry_file}` according to project conventions
- export new files from the module export file according to project conventions

**1c. Frontend development (can run in parallel with 1b if it does not depend on backend API changes)**:
- `frontend-dev` subagent
- correct type annotations, no abuse of `any`
- all API calls go through the project proxy/wrapper layer and do not expose backend addresses directly
- run frontend syntax validation (`{syntax_check_cmd}`) after each file change

### Outputs
- all modified/new files (absolute path list)
- syntax validation result for each file (`{syntax_check_cmd}`)
- route registration status in `{main_entry_file}`

### Quality Gates
- [ ] Syntax validation passes for all modified files (`{syntax_check_cmd}`, zero errors)
- [ ] New routes are registered in the main entry file (`grep -n "{new_router_name}" {main_entry_file}`)
- [ ] New files are declared in the module export file
- [ ] The migration script includes a downgrade implementation
- [ ] No silent failures (empty `catch`/`except`) and no abuse of type escapes (`any` / `# type: ignore`)

### Pause Condition
Any file fails syntax validation -> fix it and re-validate before entering Phase 2

---

## Phase 2: Review

### Inputs
- the full file list produced by Phase 1

### Execution
The `code-reviewer` subagent performs a full review of all modified files.

**Review dimensions**:
1. Security (SQL injection / command injection / XSS / path traversal / sensitive data)
2. Reliability (`try`/`except` coverage / silent failure / fallback behavior)
3. Interface consistency (`async def` / return types / naming conventions)
4. Completeness (route registration / module exports / migration completeness)

**Review output format**:

```markdown
## Phase 2 Review Report

### Files Reviewed
- {file 1} (new/modified)
- {file 2}

### Issue List
| ID | File | Line | Type | P-level | Description | Suggested Fix |

### Review Conclusion
P1: {N}, P2: {N}, P3: {N}
Conclusion: {Pass / Requires fixes (all P1 and P2 issues must be fixed)}
```

### Quality Gates
- [ ] P1 issues = 0 (security vulnerabilities / data-loss risk)
- [ ] P2 issues = 0 (functional defects / missing error handling)
- [ ] P3 issues are recorded (do not block delivery, but must appear in the final report)

### Pause Condition
Any P1 or P2 issue found -> return to Phase 1 for targeted fixes (up to 3 fix-review loops for this phase; T4 is allowed this exception because it includes a human acceptance gate. See the unified retry-limit rule in `loop-protocol.md`)

---

## Phase 3: Testing and Verification

### Inputs
- the full file list produced by Phase 1
- `{main_entry_file}` path (from `autoloop-plan.md`)

### Execution (`verifier` subagent)

**Required validations**:

```bash
# 1. Syntax check (all modified files)
{syntax_check_cmd} {each_file}        # append file arguments when syntax_check_file_arg=true
# or: {syntax_check_cmd}              # run at project root when syntax_check_file_arg=false

# 2. Route registration validation ({new_router_name} = the route/module name added in this change, collected in the plan)
grep -n "{new_router_name}" {main_entry_file}

# 3. Migration status check (if database migration exists)
{migration_check_cmd}
# Example: python -m alembic check (Python); npx drizzle-kit check (Node.js)
```

**Conditional validation**:

```bash
# If the backend service is already running, execute API smoke tests
curl -X GET {API_endpoint} \
  -H "{auth_header}: {test_key}" \
  -H "Content-Type: application/json"

# Expected: HTTP 200, response format matches the design
```

### Outputs
Validation result for each step (command + output + status)

### Quality Gates
- [ ] Syntax validation passes for all files, zero errors (`{syntax_check_cmd}`)
- [ ] Route registration: grep finds the `{new_router_name}` registration statement (N/A if there is no new route)
- [ ] Migration status check shows no conflict (N/A if there is no migration)
- [ ] API smoke test, when runnable, returns HTTP 2xx

### Pause Condition
Any validation failure -> fix it and re-validate before entering Phase 4

---

## Phase 4: Deployment

### Inputs
- the Phase 3 verification results that passed

### Execution

```bash
# 1. Commit code (list files explicitly, do not use git add -A)
git add {files} && git status && git commit -m "feat({module}): {description}"
# 2. Push
git push origin main
# 3. Deploy to production (deploy_command is defined in the plan)
{deploy_command}
# 4. Service health check (all services in service_list must be active)
```

### Outputs
- git commit hash
- deployment command result
- service status (all services in `{service_list}` active)
- health check response (`{health_check_url}`)

### Quality Gates
- [ ] `git push` succeeds
- [ ] `{deploy_command}` runs without error
- [ ] all services in `{service_list}` are active (`systemctl status`)
- [ ] health check returns HTTP 200 (`{health_check_url}`)

> For N/A exemptions on service checks and health checks, see `quality-gates.md` exemption rules. Exemption is only allowed when one side is unavailable and the other remains valid.

### Pause Condition
If services are not all active -> inspect logs, fix the issue, and redeploy

---

## Phase 5: Production Acceptance (Human Confirmation Gate)

### Inputs
- acceptance criteria (from `autoloop-plan.md`)
- production environment URL

### Execution

**Automated validation (`verifier` subagent)**:

Invocation:
`Agent(subagent_type="code-reviewer", prompt="You are the production acceptance tester. Use browser tools to validate the following functionality...")`

Optional tool: Chrome DevTools MCP (if configured)

- open the relevant pages and verify the new feature is visible
- execute the feature flow and verify the outcome is correct
- confirm the browser console has no errors
- verify the related API response time is normal (`< 500ms`)

**Human confirmation (required)**:

```text
Phase 5 paused: please open {URL} in a browser (desktop + mobile) and verify each acceptance item.
After confirming there are no red console errors and no regressions in existing functionality, enter "User confirmed (production acceptance)".
If you find any issue, describe it.
```

### Quality Gates
- [ ] Automated validation passes (or an exception is explicitly explained)
- [ ] Human confirms the new feature works correctly in a desktop browser
- [ ] Human confirms the layout works correctly in a mobile browser
- [ ] Zero red errors in the console
- [ ] No regression in existing functionality (manual test on core paths)

### Pause Condition
Without human confirmation, the task is not complete

---

## Inter-Phase Rollback Rules

| Phase where issue is found | Roll back to | Rollback scope |
|-------------|--------|---------|
| Phase 2 finds P1/P2 | Phase 1 | Fix only the relevant files |
| Phase 3 verification fails | Phase 1 or Phase 2 | Fix + re-review |
| Phase 4 deployment fails | Phase 3 (retest after fix) | Fix + retest + redeploy |
| Phase 5 finds issues in production | Phase 4 (rollback) or Phase 1 (fix) | User decides rollback vs hotfix |

**Maximum rollback count**: at most 2 rollbacks per phase (follows the unified retry-limit rule in `loop-protocol.md`); the Phase 2 fix-review loop is the only exception and may run up to 3 rounds. Beyond that, report to the user and wait for a manual decision.

---

## T4 Delivery Phases ↔ OODA Eight Stages (Controller Mapping)

| delivery-phases | Typical OODA stage(s) | Notes |
|-----------------|------------------------|------|
| Phase 1 Development | mainly `ACT` | coding and local validation |
| Phase 2 Review | `ACT` / `VERIFY` | review-fix loop |
| Phase 3 Testing | `VERIFY` | testing and score write-back |
| Phase 4 Deployment | `ACT` | release scripts |
| Phase 5 Acceptance | `VERIFY` + user gate | production acceptance |

**Round budget**: T4 defaults to **5** full OODA rounds in `gate-manifest.json` to align with the five delivery phases above. `plan.budget.max_rounds` can override it.
