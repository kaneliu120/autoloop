---
name: autoloop-quality
description: >
  AutoLoop T7: Enterprise-grade quality iteration template. Run three-dimensional parallel scans (security/reliability/maintainability),
  fix issues by P1→P2→P3 priority, verify no regression after each fix, and continue until everything reaches enterprise-grade standards.
  Goal: meet the requirements of the references/quality-gates.md T7 gate matrix.
  Trigger: /autoloop:quality or any task that needs to raise code to enterprise-grade quality.
---

# AutoLoop T7: Quality — Enterprise-Grade Quality Iteration

## Prerequisites for Execution

Read `autoloop-plan.md` to get:
- Codebase path (absolute path)
- Priority review modules (leave blank to scan everything)
- Special constraints (interfaces/files that cannot be modified)
- Tech stack (detected during the plan phase or specified by the user)
- Verification command (`syntax_check_cmd`, from the plan phase; see the tech stack detection section below)

### Tech Stack Detection and Verification Commands

Before Phase 1 begins, confirm the tech stack and choose the corresponding verification command:

All tech stacks use the `{syntax_check_cmd}` defined in the plan (see the unified parameter glossary in `references/loop-protocol.md`) for syntax verification, with `syntax_check_file_arg` determining whether to append a file argument. Module export and route registration checks are determined by the plan's `main_entry_file`.

If the plan phase did not specify a verification command, confirm with the user before scanning begins:
"Detected tech stack: {detection result}. Will use {verification command} for syntax verification. Is this correct?"

**Round 2+ OBSERVE starting point**: first read the reflection chapter in `autoloop-findings.md` to obtain remaining issues, effective/ineffective strategies, identified patterns, and lessons learned, then formulate the repair plan for this round. See the OBSERVE Step 0 section in `references/loop-protocol.md` for details.

- **Experience registry read**: read entries in `references/experience-registry.md` that match the current task type and target dimensions, identify strategies with status "recommended" or "candidate default", and pass them to the DECIDE stage as reference

---

## OBSERVE Execution Rules for Each Round (Mandatory for Round 2+)

Before each repair round begins, and before any scanning or repair action is executed, OBSERVE Step 0 must be completed first:

```
**Domain Pack Loading**: perform domain pack auto-detection (see domain-pack-spec.md §Loading Mechanism). Scan tech stack characteristics in the working directory to automatically load the matching pack; if `domain_pack` is manually specified in the plan, use that value; `domain_pack: none` explicitly disables it. After loading, use the pack's detection commands to replace the generic commands in enterprise-standard.md, and let the adjusted weights override the generic weights.

OBSERVE Step 0 (required for Round 2+, skip it in Round 1 and perform baseline collection instead):
  Read the reflection chapter in autoloop-findings.md (the 4-layer structure table)
  Obtain:
  - Issue list: unresolved issues left from the previous round, and which "fixed" items had poor results
  - Strategy evaluation: previous-round "keep" strategies (use first this round), "avoid" strategies (exclude this round), and "to be verified" strategies (use cautiously this round and observe results)
  - Pattern recognition: recurring issue types (indicating architecture-level root causes; prioritize them)
  - Lessons learned: which types of fixes work best, and which validation steps discover the most issues

  Only after that, scan the current code state and formulate the repair plan for this round
  (See the OBSERVE Step 0 section in references/loop-protocol.md for the full specification)
```

---

## Enterprise-Grade Quality Standard Definition

> **See `references/enterprise-standard.md` for the complete scoring definition.**
> T7 review must cover every check item in enterprise-standard.md, including but not limited to:
> timeout configuration, retry logic, health checks, test coverage, connection pool configuration, and so on.
> Do not rely only on the simplified list in this file; enterprise-standard.md is the source of truth.

**Target scores**: see row T7 in `references/quality-gates.md` for the quality gate thresholds (score targets for security, reliability, and maintainability).

**Passing condition (composite judgment; see the T7 composite judgment rules in references/quality-gates-engineering.md)**:
- Both conditions must be met at the same time: score threshold met AND count threshold met (`P1=0`, `security P2=0`)

---

## Round 1: Three-Dimensional Parallel Scan

**Run 3 code-reviewer subagents simultaneously** (independent, parallel):

### Security Reviewer Subagent

```
You are the security-reviewer subagent, focused on code security review.

Codebase path: {absolute path}
Modules under review: {module list, leave blank for full scan}

Review checklist:
1. SQL injection
   - Find: SQL built directly with f-strings or `%` formatting
   - Find: raw strings passed into `execute()`
   - Find: unparameterized user input used with the ORM `text()` function

2. Command injection
   - Find: user input included in `subprocess.run/call/Popen`
   - Find: `os.system()` / `os.popen()`
   - Find: user input included in `eval()` / `exec()`

3. XSS (if there is a frontend)
   - Find: `dangerouslySetInnerHTML`
   - Find: user input assigned to `innerHTML`

4. Path traversal
   - Find: unvalidated user input used in `os.path.join()` / `open()`
   - Find: path construction like `../../../`

5. Sensitive data exposure
   - Find: passwords/keys in `logger.info/debug/print`
   - Find: passwords/keys in API response dicts
   - Find: values from `.env` files returned in responses

6. Input validation
### Tech stack adaptation (input validation checks)
Check the corresponding input-validation mechanism based on the actual tech stack:
- Python/FastAPI: whether route parameters use Pydantic models; whether file-upload routes validate type and size
- Node.js/Express: whether `express-validator` / `zod` / `joi` middleware is present
- Other frameworks: check equivalent request-validation mechanisms and whether arbitrary user input flows directly into databases/commands

Reference search commands (run `grep` in the codebase):
grep -rn "execute(f" {path}
grep -rn "subprocess" {path}
grep -rn "os.system" {path}
grep -rn "dangerouslySetInnerHTML" {path}
grep -rn "# type: ignore" {path}

Output format:
## Security Review Report

### Issues Found

| ID | File (absolute path) | Line | Type | Severity | Description | Impact Analysis | Fix Suggestion |
|----|---------------|------|------|---------|------|---------|---------|
| S001 | {path} | {line} | SQL injection | P1 | {description} | {impact} | {suggestion} |

### Security Score

Initial score: 10
Deductions:
- {issue S001}: -{points} (reason: {category})
Final security score: {N}/10

### Priority Summary
P1 (must be fixed immediately): {N}
P2 (should be fixed in this pass): {N}
P3 (recommended fix): {N}
```

### Reliability Reviewer Subagent

```
You are the reliability-reviewer subagent, focused on code reliability review.

Codebase path: {absolute path}
Modules under review: {module list}

Review checklist:
1. Exception-handling coverage
   - Find: HTTP client calls (`httpx/aiohttp/requests`) without `try/except`
   - Find: Redis operations without `try/except`
   - Find: database operations without `try/except`
   - Find: file operations without `try/except`

2. Silent failures
   - Find: `except: pass`
   - Find: `except Exception: logger.debug` in key paths (insufficient handling)
   - Find: empty `finally` blocks

3. Degradation fallback
   - Find: whether Redis cache read failures fall back to the database
   - Find: whether external API timeouts have retries or fallback
   - Find: whether database connection failures return proper error responses

4. Transaction integrity
   - Find: whether multiple database writes are performed in the same transaction
   - Find: whether write operations are followed by `await session.commit()`

5. Resource leaks
   - Find: whether opened connections/files are closed in `finally` or `async with`
   - Find: whether async generators have `return` statements

Reference search commands:
grep -rn "except.*pass" {path}
grep -rn "except:" {path}
grep -rn "redis" {path}  # then check whether try/except exists

Output format:
## Reliability Review Report

### Issues Found

| ID | File | Line | Type | Severity | Description | Fix Suggestion |
|----|------|------|------|---------|------|---------|
| R001 | {path} | {line} | Silent failure | P1 | {description} | {suggestion} |

### Reliability Score

Initial score: 10
Deductions: ...
Final reliability score: {N}/10

P1/P2/P3 count summary
```

### Maintainability Reviewer Subagent

```
You are the maintainability-reviewer subagent, focused on code maintainability review.

Codebase path: {absolute path}
Modules under review: {module list}

Review checklist:
1. Type system
   - Find: `any` types (Python: `Any` / TypeScript: `any`)
   - Find: `# type: ignore`
   - Find: functions missing return type annotations

2. Code duplication
   - Identify: duplicated code blocks longer than 10 lines
   - Identify: the same functionality implemented in multiple places

3. Hardcoding
   - Find: hardcoded URLs / ports / timeout values (outside config files)
   - Find: magic numbers (for example `3600` instead of `CACHE_TTL`)

4. Modularity
### Tech stack adaptation (modularity checks)
Check the corresponding module export and route registration rules based on the actual tech stack:
- Python: whether new files are exported in `__init__.py`; whether new routes are registered in `{main_entry_file}`
- Node.js/TypeScript: whether new files are declared in `index.ts` barrel exports; whether new routes are registered in the entry file (`app.ts`)
- Other frameworks: check equivalent module export and route registration mechanisms according to project conventions
- General: single responsibility of functions (whether functions longer than 50 lines should be split)

5. Naming conventions
   - Find: abbreviated variable names (such as `d`, `tmp`, `x`)
   - Find: naming styles that violate project conventions (such as camelCase in Python)

Reference search commands:
grep -rn "Any" {path}
grep -rn ": any" {path}
grep -rn "# type: ignore" {path}
grep -rn "http://\|https://" {path}  # hardcoded URLs

Output format:
## Maintainability Review Report

### Issues Found

| ID | File | Line | Type | Severity | Description | Fix Suggestion |
|----|------|------|------|---------|------|---------|

### Maintainability Score

Initial score: 10
Deductions: ...
Final maintainability score: {N}/10
```

### End of Round 1: Summarize Scan Results

Merge the three reports and build a unified issue list:

```markdown
## Round 1 Scan Complete

| Dimension | Initial Score | Target | Status |
|------|---------|------|------|
| Security | {N}/10 | {threshold, see quality-gates.md §T7 gate} | below target / meets target |
| Reliability | {N}/10 | {threshold, see quality-gates.md §T7 gate} | below target / meets target |
| Maintainability | {N}/10 | {threshold, see quality-gates.md §T7 gate} | below target / meets target |

Total issues: {N}
  P1 (must fix): {N}
  P2 (should fix): {N}
  P3 (recommended): {N}

Next step: fix in P1 → P2 → P3 order
```

---

## Round 2-N: Priority-Based Repair Loop

### Repair Order Rules

1. **P1 security issues** (all must be fixed before moving to the next type)
2. **P1 reliability issues**
3. **P1 maintainability issues**
4. **P2 security issues**
5. **P2 reliability issues**
6. **P2 maintainability issues**
7. **P3 issues** (depending on budget)

### Execution Flow for Each Fix

**For each issue (in priority order)**:

1. **Work order generation**: generate the delegation work order using the corresponding role template in `references/agent-dispatch.md`, filling in the task objective, input data, output format, quality standard, scope limits, current round, and context summary

2. **Assign repair subagent**:

```
You are the `fix-{type}` subagent, fixing the following code quality issue.

Issue ID: {ID}
File: {absolute path}
Line: {line}
Issue description: {description}
Fix suggestion: {suggestion}

Constraints:
- Only modify the flagged issue; make no unrelated changes
- Do not change function signatures or API interfaces
- Run the syntax verification command immediately after the change (`{syntax_check_cmd}`, from `autoloop-plan.md`)

Repair steps:
1. Read the file
2. Apply the minimal fix
3. Run `{syntax_check_cmd}` (must pass before reporting completion)
4. Confirm that the fix resolves the issue
5. Confirm that no new issue was introduced

Output:
- Modified content (diff format)
- `{syntax_check_cmd}` verification result (must pass)
- Whether a new issue was introduced (yes/no; describe if yes)
```

3. **Verify no regression** (after every fix):

```bash
# Syntax verification (using syntax_check_cmd from autoloop-plan.md)
# The plan phase should explicitly define syntax_check_file_arg: true/false.
# - syntax_check_file_arg=true:  {syntax_check_cmd} {modified file}
# - syntax_check_file_arg=false: {syntax_check_cmd} (do not append a file argument)

# If a route file was modified, check registration in the main entry file (according to the tech stack convention for {main_entry_file})
grep -n "{new_router_name}" {main_entry_file}

# If key imports were modified, check circular dependencies (using the appropriate tool for the tech stack)
{syntax_check_cmd}
```

4. **Update issue-list status**: update repaired issues to `"resolved"` (using the unified status enums from `loop-protocol.md`).

### Parallel Rules for Batch Repair

- Multiple issues in the same file: fix **serially** (to avoid conflicts)
- Issues in different files: fix **in parallel** (to improve efficiency)
- Finish all P1 items before handling P2 (do not parallelize across priorities)

---

## Checkpoint After Every 5 Fixes

```
Checkpoint ({N} issues fixed)

Current scores:
  Security: {old} → {new} ({+/- change})
  Reliability: {old} → {new} ({+/- change})
  Maintainability: {old} → {new} ({+/- change})

Remaining unresolved: {N} (P1:{N} P2:{N} P3:{N})

Any new issue introduced by fixes: {yes/no}
  If yes: {describe the new issue and add it to the issue list}

Continue fixing → next batch ({specific plan})
```

---

## Final Acceptance Scan

After all P1 and P2 issues are fixed, rerun the full three-dimensional scan:

```
Goal of final scan: confirm all issues are fixed and no regression exists

Security rescan → {N}/10 (improvement: {+X})
Reliability rescan → {N}/10 (improvement: {+X})
Maintainability rescan → {N}/10 (improvement: {+X})

New issues discovered (introduced during improvement): {N}
```

### Termination Judgment

The termination condition uses composite judgment (both conditions must be satisfied); see the T7 composite judgment rules in `references/quality-gates.md` for the full definition.

```
Condition 1: score thresholds met (see the T7 gate row in quality-gates.md)
  Security {N}/10 ≥ {threshold} ✓
  Reliability {N}/10 ≥ {threshold} ✓
  Maintainability {N}/10 ≥ {threshold} ✓

Condition 2: count thresholds met (for tolerance, see the T7 composite judgment rules in quality-gates-engineering.md)
  P1 issues = 0 (all dimensions) ✓
  Security P2 issues = 0 ✓
  Reliability P2 issues ≤ {tolerance} ✓
  Maintainability P2 issues ≤ {tolerance} ✓

Both conditions must be satisfied at the same time → terminate iteration and generate the final audit report

Note: if score thresholds are met but P1 issues still exist → do not terminate; continue fixing P1
```

If not everything meets the threshold → continue repair rounds (P3 issues may be handled depending on budget).

---

## REFLECT Execution Rules for Each Round

After each repair batch (checkpoint), execute this after EVOLVE judgment. REFLECT must be written to a file and cannot be completed only in thought (see the REFLECT section in `references/loop-protocol.md`):

Write the 4-layer reflection structure table into `autoloop-findings.md` (issue registration / strategy review / pattern recognition / lessons learned); see `assets/findings-template.md` for the format:

- **Issue registration**: record code issues found in this round, whether fixes introduced new issues, review omissions, and remaining items that could not be fixed
- **Strategy review**: evaluate the effectiveness of repair strategies / review methods / verification commands (keep | avoid | to be verified) (for strategy evaluation enums, see the unified status enums in `references/loop-data-schema.md`)
- **Pattern recognition**: recurring types of code issues (indicating architecture-level root causes), fix → new issue causal chains, and which issue types are concentrated in the same module
- **Lessons learned**: which kinds of fixes are most effective, which validation steps uncover the most issues, and systemic lessons across security / reliability / maintainability
- **Experience write-back**: write the strategy effects from this round into `references/experience-registry.md` (strategy ID, applicable scenario, effect score, execution context, following the effect-record table format)

---

## Final Audit Report

Follow the unified output filename rules in `references/loop-protocol.md` (T7: `autoloop-audit-{date}.md`). Use `assets/audit-template.md` when writing:

```markdown
# Enterprise-Grade Quality Audit Report

## Executive Summary

| Dimension | Initial | Final | Target | Status |
|------|------|------|------|------|
| Security | {initial}/10 | {final}/10 | {threshold, see quality-gates.md §T7 gate} | meets target / below target |
| Reliability | {initial}/10 | {final}/10 | {threshold, see quality-gates.md §T7 gate} | meets target / below target |
| Maintainability | {initial}/10 | {final}/10 | {threshold, see quality-gates.md §T7 gate} | meets target / below target |

**Iteration rounds**: {N}
**Issues fixed**: {N} (P1:{N} P2:{N} P3:{N})
**Conclusion**: {enterprise-grade quality achieved / close to target (explain the gap)}

## Repair Details

| ID | Dimension | Priority | File | Issue | Fix Approach | Status |
|----|------|--------|------|------|---------|------|

## Remaining Issues

(Unfixed P3 issues, with reasons)

## Codebase Health Changes

Files covered by the scan: {N}
Key improvements: {top 3 improvements}

## Follow-Up Recommendations

{continuous improvement suggestions}
```
