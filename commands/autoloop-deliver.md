---
name: autoloop-deliver
description: >
  AutoLoop T4: End-to-end delivery template. A complete 5-phase delivery flow from requirements to production (Phase 1-5),
  strictly mapped to the mandatory development process in CLAUDE.md.
  Every phase has explicit quality gates; if a phase fails, do not proceed to the next one.
  See references/quality-gates-engineering.md row T4 for the quality gate threshold.
  Trigger: /autoloop:deliver or any task that requires end-to-end feature delivery.
---

# AutoLoop T4: Deliver — End-to-End Delivery

## Prerequisites for Execution

Read `autoloop-plan.md` to get all execution parameters. See the unified parameter glossary in `references/loop-protocol.md` for T4 parameters.

**Strictly follow the mandatory development process in CLAUDE.md. Do not skip steps.**

**Round 2+ OBSERVE starting point**: if this delivery continues an unfinished task from the previous run, first read the reflection chapter in `autoloop-findings.md` (Layer 2: strategy review) to obtain remaining issues, effective/ineffective strategies, and identified patterns before entering Phase 1 development. See the OBSERVE Step 0 section in `references/loop-protocol.md` for details.

- **Experience registry read**: read entries in `references/experience-registry.md` that match the current task type and target dimensions, identify strategies with status "recommended" or "candidate default", and pass them into the DECIDE stage as reference

---

## Phase Overview

```text
Phase 1   → Development (backend-dev + frontend-dev + db-migrator)
Phase 2   → Review (code-reviewer)
Phase 3   → Test Verification (verifier)
Phase 4   → Deployment (git push + {deploy_command})
Phase 5   → Production Acceptance (verifier + manual confirmation)
```

**Manual confirmation gate (Blocking Gate)**: Phase 5 requires manual confirmation (the state machine enters a paused waiting state); the system must not skip it automatically. See the state-machine section in `references/loop-protocol.md`.

---

## Phase 1: Development

### Goal

Take the confirmed solution document (from the product design phase or `autoloop-plan.md`) and begin implementation.

### API Contract Alignment (Required When Frontend and Backend Run in Parallel)

When Phase 1 dispatches both frontend-dev and backend-dev agents at the same time, complete this step before dispatch:

1. Extract all added/modified API endpoints from the solution document
2. Generate a contract document (OpenAPI spec or endpoint list) containing: path, method, request body, response body, and authentication requirements
3. Save the contract document to `{work_dir}/api-contract.md`
4. Include the contract document path in the dispatch context for both frontend-dev and backend-dev

Risk of skipping this step: frontend and backend agents may infer the API design independently, which can produce inconsistent endpoint naming or parameter formats.

### Execution Order

**1a. Database migration (if any)** — execute first, because other development depends on the database structure

db-migrator subagent (see the db-migrator section in `references/agent-dispatch.md` for dispatch rules):

```text
You are the db-migrator subagent.

Task: create the database migration script.

Change details:
{database change description extracted from the solution document}

Codebase path: {absolute path}
migration_check_cmd: {read from autoloop-plan.md; variable name see references/loop-protocol.md}
syntax_check_cmd: {read from autoloop-plan.md}

Requirements:
- Must include rollback implementation (`downgrade` / `down` / `revert`)
- Use idempotent operations (`IF NOT EXISTS` / `IF EXISTS`) to prevent duplicate-run failures
- Use the migration tool and config-file paths defined in the plan

Adapt to the tech stack:
See the tech-stack-specific checks section in `references/enterprise-standard.md` and the appendix in `references/agent-dispatch.md` for specific migration-tool usage.

Output:
- Migration file path
- Migration summary (added/modified tables/columns/indexes)
- Rollback plan
- Verification result (`{syntax_check_cmd}`)
```

**1b. Backend development** — execute after database migration

backend-dev subagent (see the backend-dev section in `references/agent-dispatch.md` for dispatch rules):

```text
You are the backend-dev subagent, responsible for backend implementation.

Solution document: {path}
Codebase path: {absolute path}
syntax_check_cmd: {read from autoloop-plan.md}
syntax_check_file_arg: {read from autoloop-plan.md (true/false)}
main_entry_file: {read from autoloop-plan.md}
new_router_name: {read from autoloop-plan.md}

General requirements:
- All external calls must have exception handling; silent failure (empty catch/except) is not allowed
- New files must be declared in the module export file
- New routes must be registered in the main entry file (`{main_entry_file}`)
- Run the syntax verification command immediately after each file modification

Tech stack adaptation:
Use the corresponding `{syntax_check_cmd}` and `{migration_check_cmd}` based on the tech stack confirmed in the plan. See the tech-stack-specific checks section in `references/enterprise-standard.md` for details.

For each file modification:
1. Read the existing file (do not edit blindly)
2. Apply the change
3. Run `{syntax_check_cmd}` (append the file path when `syntax_check_file_arg=true`, otherwise do not)
4. Report the changes made

Output:
- List of modified/new files (absolute paths)
- Key change summary for each file
- Syntax verification results (all passing)
- Main entry-file registration confirmation: `grep -n '{new_router_name}' {main_entry_file}`
```

**1c. Frontend development (if any)** — may run in parallel with backend work

frontend-dev subagent (see the frontend-dev section in `references/agent-dispatch.md` for dispatch rules):

```text
You are the frontend-dev subagent, responsible for frontend implementation.

Solution document: {path}
Frontend directory: {read frontend_dir from autoloop-plan.md}
syntax_check_cmd: {read from autoloop-plan.md}

General requirements:
- Types must be correct, with no abuse of `any` (for TypeScript projects)
- API calls must go through the project's prescribed proxy/wrapper layer
- Run `{syntax_check_cmd}` immediately after each file modification
- Export new components in barrel export files if the project uses that convention

Tech stack adaptation:
Use the corresponding `{syntax_check_cmd}` based on the tech stack confirmed in the plan. See the tech-stack-specific checks section in `references/enterprise-standard.md` for details.

Output:
- List of modified/new files (absolute paths)
- `{syntax_check_cmd}` verification result (passing)
```

### Quality Gates (Phase 1)

See the engineering-task gate section in `references/quality-gates.md` for Phase 1 gates:

- [ ] Syntax verification passes (run `{syntax_check_cmd}` for each modified file, with file arguments controlled by `syntax_check_file_arg`)
- [ ] New route registered: `grep -n '{new_router_name}' {main_entry_file}` (N/A if there is no new route)
- [ ] New files declared in module export files
- [ ] Database migration script includes a `downgrade` implementation
- [ ] No silent failure (empty catch/except) / no abuse of type escape hatches (`any` / `type:ignore`)

---

## Phase 2: Review

The code-reviewer subagent (see the code-reviewer section in `references/agent-dispatch.md` for dispatch rules) reviews all modified files. See the security / reliability / maintainability gate sections in `references/quality-gates.md` and `references/enterprise-standard.md` for the review checklist and scoring rules:

```text
You are the code-reviewer subagent, reviewing the following files for security + quality.

Files under review:
{absolute paths of all modified/new files produced in Phase 1}

Review checklist (see `references/enterprise-standard.md` for the full deduction rules):

Security:
  - SQL injection (raw strings concatenated into queries)
  - Command injection (unchecked parameters passed into shell commands)
  - Path traversal (user input influencing file paths)
  - Sensitive data exposure (keys/passwords in logs or responses)
  - Input validation (all external input validated with types/schema)

Reliability:
  - All external calls (network/file/database/cache) have exception handling
  - No silent failure (empty catch/except)
  - Critical write operations are protected by transactions
  - External dependencies have degradation fallback (cache failure should not crash the main flow)

Interface consistency:
  - Function signatures follow project conventions (tech stack determined by the plan)
  - Return types are annotated
  - Naming is semantically clear

Code quality:
  - No duplicate code (DRY principle)
  - No hardcoded configuration values
  - Complex logic is commented

Output format:
## Review Report

### Passed Items
- {file}: {areas that passed}

### Issue List

| ID | File | Line | Type | Severity | Description | Fix Suggestion |
|----|------|------|------|---------|------|---------|
| 001 | {path} | {line} | Security | P1 | {description} | {suggestion} |

### Conclusion
- P1 issues (must fix): {N}
- P2 issues (should fix): {N}
- P3 issues (recommended): {N}
- Conclusion: {pass / fix and re-review required}
```

### Quality Gates (Phase 2)

See row T4 in `references/quality-gates.md` for Phase 2 gates:

- [ ] P1 issues = 0 (security vulnerabilities, data-loss risk)
- [ ] P2 issues = 0 (functional defects, missing error handling)
- [ ] P3 issues recorded (not mandatory to fix; include them in the final report)

P1/P2 issues must be fixed and then re-reviewed (return to Phase 1 for targeted fixes). See the unified retry rules in `references/loop-protocol.md` for the retry limit (maximum 3 review-fix loops for T4 Phase 2).

---

## Phase 3: Test Verification

verifier subagent (see the verifier section in `references/agent-dispatch.md` for dispatch rules):

```text
You are the verifier subagent, responsible for running all tests and verification.

Codebase path: {absolute path}
syntax_check_cmd: {read from autoloop-plan.md}
syntax_check_file_arg: {read from autoloop-plan.md (true/false)}
main_entry_file: {read from autoloop-plan.md}
new_router_name: {read from autoloop-plan.md}
migration_check_cmd: {read from autoloop-plan.md}

Verification steps:

1. Syntax check (all modified files)
   Choose execution mode based on `syntax_check_file_arg`:
   - `syntax_check_file_arg=true`: `{syntax_check_cmd} {each modified file}`
   - `syntax_check_file_arg=false`: `{syntax_check_cmd}` (project-level, no file parameter)

2. Route registration check (execute only when `new_router_name ≠ N/A`)
   grep -n '{new_router_name}' {main_entry_file}
   Expectation: find the exact registration statement for that router

3. Database migration verification (if any, using `{migration_check_cmd}`)
   `migration_check_cmd` comes from `autoloop-plan.md`; skip if not applicable

4. API smoke test (if the service is running)
   Send test requests according to the project tech-stack conventions and verify HTTP 2xx with correct response format

Output:
Verification result for each step (pass/fail + error message)
Overall conclusion: pass / fail ({failed step})
```

### Database Migration Check

After the verifier completes automated tests, check whether any database models were added/modified:

- **TypeORM/Prisma projects**: confirm a migration file was generated (`typeorm migration:generate` / `prisma migrate dev`) and does not rely on `synchronize: true`
- **Alembic projects**: confirm `alembic revision --autogenerate` was run and the generated migration file exists
- **Verification**: the migration file is executable and has a corresponding downgrade/revert implementation; do not rely on manual `ALTER TABLE`

### i18n Sync Check

If the project is multilingual (contains `en.json` or a similar primary-language file):

- Check whether the primary-language file includes the keys added in this change
- Confirm that other language files have synced these new keys (at minimum including an English fallback)
- Recommendation: use AI translation to write the new keys into other language files so no gaps remain

If the project is not multilingual, mark as N/A.

### Quality Gates (Phase 3)

See row T4 in `references/quality-gates.md` for Phase 3 gates:

- [ ] Syntax verification passes (append file arguments according to `syntax_check_file_arg`)
- [ ] Route registration: `grep -n '{new_router_name}' {main_entry_file}` finds the registration statement (N/A if no new route)
- [ ] Database migration status is correct: `{migration_check_cmd}` (N/A if no migration)
- [ ] Database migration file exists and includes a `downgrade` implementation (if there is a new Entity/column, a migration file is required; do not rely only on `synchronize:true`)
- [ ] i18n sync: other language files include the newly added keys from the primary language (N/A if no multilingual support)

---

## Phase 4: Deployment

```text
Deployment execution:

1. Commit code
   git add {all modified files (explicitly listed; do not use git add -A)}
   git status (confirm only the expected files are included)
   git commit -m "{feature description}

   Co-Authored-By: AutoLoop <noreply@autoloop>"
   git push origin main

2. Production deployment
   {deploy_command} (from autoloop-plan.md; variable name see references/loop-protocol.md)

3. Service health check
   Check that every service in {service_list} is active (from autoloop-plan.md)
   If `service_list = N/A`, skip this step

4. Health check
   curl {health_check_url}
   Expectation: HTTP 200
   If `health_check_url` is empty, mark as N/A
```

### Quality Gates (Phase 4)

See row T4 in `references/quality-gates.md` for Phase 4 gates:

- [ ] `git push` succeeds
- [ ] `{deploy_command}` runs without errors
- [ ] All services in `{service_list}` are active (`service_list = N/A` means skip)
- [ ] Health check (`{health_check_url}`) returns 200 (`health_check_url` empty means mark N/A)
- [ ] At least one of `service_list` and `health_check_url` passes (if both are N/A, the plan is invalid)

---

## Phase 5: Production Acceptance — Manual Confirmation Gate

verifier subagent (see the verifier section in `references/agent-dispatch.md` for invocation rules):

```text
You are the verifier subagent, responsible for production feature verification.

Production environment: {acceptance_url} (from autoloop-plan.md; variable name see references/loop-protocol.md)

Verification checklist (execute item by item):
1. New feature works correctly: {specific steps}
2. Existing features show no regression: {check key features}
3. Browser Console has zero errors
4. API response time is normal (`< 500ms`)

Optional tool: Chrome DevTools MCP (if configured)

Output:
Result for each verification item (pass/fail + screenshot or log)
```

### Pause: Wait for Manual Confirmation (Phase 5)

```text
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Phase 5 manual confirmation point — production confirmation required
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Automated verification result: {pass/issues found}

Please access the production environment in a browser (desktop + mobile) and confirm:
1. {acceptance criterion 1}
2. {acceptance criterion 2}
3. {acceptance criterion 3}

After confirming everything is correct, enter "User confirmed (production acceptance)" to complete the task.
If there are issues, describe them and then either roll back or continue fixing.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

T4 completion condition: Phase 4 gates pass AND the user enters "User confirmed (production acceptance)". See row T4 in `references/quality-gates.md` for the full gate definition.

---

## REFLECT Execution Rules for Each Round

Execute this after each phase completes. REFLECT must be written to a file and cannot be completed only in thought (see the REFLECT section in `references/loop-protocol.md`).

Write the 4-layer reflection structure table into `autoloop-findings.md` (see `assets/findings-template.md` for the format):

- **Issue registration (Layer 1)**: record code issues found in this round, whether fixes introduced new issues, and review omissions
- **Strategy review (Layer 2)**: evaluate the effectiveness of repair strategies / review methods / verification commands (keep | avoid | to be verified) (for strategy evaluation enums, see the unified status enums in `references/loop-protocol.md`)
- **Pattern recognition (Layer 3)**: recurring types of code issues (indicating architecture-level root causes), and causal chains where a fix led to a new issue
- **Lessons learned (Layer 4)**: which types of fixes are most effective and which validation steps uncover the most issues
- **Experience write-back**: write the strategy effects from this round into `references/experience-registry.md` (strategy ID, applicable scenario, effect score, execution context, following the effect-record table format)

**See `references/agent-dispatch.md` for dispatch rules.**

---

## Delivery Completion Report

Follow the unified output filename rules in `references/loop-protocol.md` (T4: `autoloop-delivery-{feature}-{date}.md`).

After manual confirmation, output the final delivery report:

```markdown
# Delivery Completion Report

## Feature
{feature name}

## Delivery Content

| Phase | Status | Duration |
|------|------|------|
| 1 Development | Complete | {time} |
| 2 Review | Passed (`P1/P2 = 0`) | {time} |
| 3 Testing | Passed | {time} |
| 4 Deployment | Success | {time} |
| 5 Acceptance | Confirmed | {time} |

## Change List

### New Files
{file list}

### Modified Files
{file list}

### Database Migration
{migration script name (or "none" if not applicable)}

### Added Routes/Interfaces
{list (or "none" if not applicable)}

## Issues Found

Issues found during this delivery but not fixed (P3 level):
{list (or "none" if not applicable)}

## Follow-Up Recommendations

{any remaining items or optimization suggestions}
```
