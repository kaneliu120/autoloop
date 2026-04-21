# Quality Gates (Engineering) — T4/T7/T8 Engineering Quality Gates

> Split out from `quality-gates.md`. For the shared scoring conventions, semantic vocabulary, and knowledge-task gates (T1/T2/T5/T6), see `references/quality-gates.md`.
> For scoring anchors and deduction rules, see `references/enterprise-standard.md`.

## Engineering Task Gates (T4/T7/T8)

### Syntax Validation Gate (Mandatory, before Phase 1 ends)

```bash
# Use the syntax_check_cmd defined in the plan to validate all modified files
# syntax_check_file_arg=true:  {syntax_check_cmd} {file_path} (validate file by file)
# syntax_check_file_arg=false: {syntax_check_cmd} (project-level validation, no file argument)

# Pass condition: zero errors (warnings are acceptable, but must be recorded)
```

### Route Registration Gate (Mandatory when new routes are added)

```bash
# Verify that the new route has been registered ({new_router_name} = the router variable name defined in the plan)
# Choose the command based on the tech stack:
# Python/FastAPI: grep -n "include_router.*{new_router_name}" {main_entry_file}
# Node.js: grep -n "use\|route" {main_entry_file}
# Other: check route registration in the main entrypoint according to project conventions

# Pass condition: grep finds the exact registration statement for that router
```

### Security Gate (T4/T7)

> Note: security severity classification follows `references/enterprise-standard.md`.

| Severity | Issue Type | Pass Condition |
|---------|------------|----------------|
| P1 (must fix) | SQL injection, command injection, sensitive data exposure, XSS, path traversal | = 0 |
| P2 (must fix) | Missing input validation | = 0 |
| P3 (record only) | CORS configuration, overly broad error messages | Record only; does not block delivery |

T7 enterprise standard: security score >= 9/10

### Reliability Gate (T4/T7)

| Severity | Issue Type | Pass Condition |
|---------|------------|----------------|
| P1 (must fix) | Silent failure (`except: pass`), missing exception handling on critical paths | = 0 |
| P2 (must fix) | No timeout configuration, missing fallback/degradation | = 0 for T4; for T7 see the compound rule below (<= 3) |
| P3 (record only) | Incomplete logging, missing retry logic | Record only; does not block delivery |

T7 enterprise standard: reliability score >= 8/10

### Maintainability Gate (T4/T7)

| Severity | Issue Type | Pass Condition |
|---------|------------|----------------|
| P1 (must fix) | New routes not registered, new files not exported | = 0 |
| P2 (recommended) | Abuse of `any`, duplicated code | <= 3 for T4 |
| P3 (record only) | Naming violations, missing comments | Record only; does not block delivery |

T7 enterprise standard: maintainability score >= 8/10

### Architecture Gate (T8)

| Issue Type | Pass Condition |
|------------|----------------|
| Circular dependencies | = 0 |
| Direct cross-layer access | = 0 (for example, route layer accessing the DB directly) |
| API inconsistency (same class of routes formatted differently) | <= 2 cases (recorded, scheduled for refactor) |

T8 enterprise standard: architecture score >= 8/10

### Performance Gate (T8)

| Issue Type | Pass Condition |
|------------|----------------|
| N+1 queries | = 0 on production paths |
| Missing connection pool configuration | = 0 |
| No cache on hot paths (high read frequency, low update rate) | <= 2 cases (recorded, scheduled for addition) |

T8 enterprise standard: performance score >= 8/10

### Stability Gate (T8)

| Issue Type | Pass Condition |
|------------|----------------|
| External dependencies without fallback | = 0 (Redis / third-party APIs) |
| Missing health check endpoint | = 0 |
| Critical operations without timeout | = 0 |

T8 enterprise standard: stability score >= 8/10

---

> T4 delivery-task scoring anchors: see the corresponding dimension in `references/enterprise-standard.md`.
> T7 enterprise-quality scoring anchors: see the corresponding dimension in `references/enterprise-standard.md`.
> T8 optimization-task scoring anchors: see the corresponding dimension in `references/enterprise-standard.md`.

---

## Gate Evaluation Matrix (Quick Reference)

| Template | Hard Gates | Soft Gates |
| ---- | ------ | ------ |
| T1 | coverage >= 85%, credibility >= 80% | consistency >= 90%, completeness >= 85% |
| T2 | coverage = 100%, credibility >= 80%, bias < 0.15 | sensitivity (top-ranked option unchanged under +/-20%) |
| T5 | KPI meets the target value in the plan | -- |
| T6 | pass_rate >= 95%, avg_score >= 7/10 | -- |
| T4 | zero syntax errors, P1/P2 = 0, manual acceptance | service health check |
| T7 | security >= 9, reliability >= 8, maintainability >= 8, P1 = 0, security P2 = 0 | reliability P2 <= 3, maintainability P2 <= 5 |
| T8 | architecture >= 8, performance >= 8, stability >= 8 | -- |

---

## T4 N/A Handling Rules

```text
If service_list is empty or N/A: mark the Phase 4 service check as N/A (skip it)
If health_check_url is empty: mark the Phase 4 health check as N/A (skip it)
Validity constraint: at least one of service_list or health_check_url must be provided, otherwise the plan is invalid
Phase 5: always requires the user to input 'User confirmed (production acceptance)' and is not affected by N/A
```

---

## T7 Compound Pass Rule (Single Source of Truth)

T7 passes only when the following two conditions are both satisfied:

**Condition 1: score thresholds met**

```text
Security >= 9/10
Reliability >= 8/10
Maintainability >= 8/10
```

**Condition 2: issue counts within tolerance**

```text
P1 issues = 0 (all dimensions)           <- (Hard Gate)
Security P2 issues = 0                   <- (Hard Gate)
Reliability P2 issues <= 3               <- (Soft Gate)
Maintainability P2 issues <= 5           <- (Soft Gate)
```

**Count-first principle**: even if the scores meet the threshold, any P1 issue > 0 means the task still fails. P1 issues must be fixed before termination is allowed.

> This rule is the only valid definition of T7 pass/fail. The `P2=0` rule in `delivery-phases.md` Phase 2 is the T4 delivery standard and does not apply to T7. There is no conflict: T4 requires zero P2 issues for delivered code, while T7 allows a small number of residual low-risk P2 issues.

---

> For the full hard-gate/soft-gate classification, see the "Gate Classification Overview" section at the top of this file.

---

## Gate Exemption Rules

The following cases may be exempted if they are explicitly recorded and justified:

1. **Legacy-code exemption**: issues outside the scope of the current change may be recorded without being mandatory to fix.
2. **Technical-debt exemption**: P3-level issues may be recorded under "open issues" when the budget is exhausted, without blocking delivery.
3. **Environment-limitation exemption**: if a production acceptance step cannot run because of the environment, the alternative validation method must be stated.

**Every exemption must**:
- explicitly state the reason for the exemption
- assess the impact (including whether core functionality is affected)
- be recorded in `progress.md` and in the "open issues" section of the final report
- remain visible; this is not "forgotten", it is "known, intentionally not fixed, because ..."
