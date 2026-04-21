# Agent Dispatch — Subagent Dispatch Specification

## Overview

This document defines the rules for AutoLoop to dispatch subagents: which scenarios should run in parallel, which should run serially, and what context must be included in every dispatch.

**Core Principle**: Each subagent must be able to work independently and must not rely on being told "where the context is" later. You must put the context directly into the instruction.

---

## Task-type Labels (Task-Aware Dispatch)

Each template + phase combination has a corresponding `task_type` and `prefer_tools` tag used to guide the subagent toward appropriate tools and behavior patterns.

| template + phase | task_type | prefer_tools | behavior orientation |
| ---------- | ----------- | ------------- | --------- |
| T1 ACT | research | web_search, read_file | Prioritize search tools to collect broad information |
| T2 ACT | analysis | read_file, grep | Prioritize comparative analysis tools |
| T3 ACT | design | read_file, write_file | Prefer document-writing tools |
| T4 ACT | coding | edit_file, bash, grep | Prioritize code editing and execution tools |
| T5 ACT | iteration | read_file, web_search | Mixed use, data-driven |
| T6 ACT | generation | write_file | Prioritize batch generation tools |
| T7 ACT | review | grep, read_file | Prioritize code search and reading tools |
| T8 ACT | optimization | edit_file, bash | Prioritize refactoring and testing tools |

The controller automatically injects `[Task type: {task_type}] {behavior_hint}` according to the current template during ACT. See `TASK_TYPE_MAP` in `scripts/autoloop-controller.py`.

---

## Parallel vs. Serial Decision Rules

### Must run in parallel (dispatch simultaneously)

Parallelism is allowed when any of the following conditions are true:

1. **Output independence**: the output of subagent A is not the input of subagent B
2. **File independence**: two subagents operate on completely different file sets
3. **Dimension independence**: they investigate different dimensions / check different modules
4. **Layer independence**: `backend-dev` works on backend files, `frontend-dev` works on frontend files

**Forced parallel scenarios**:

```text
T1 Research: multiple researchers search different dimensions → must be parallel
T2 Compare: multiple analyzers analyze different options → must be parallel
T7 Quality: security review + reliability review + maintainability review → must run in parallel (all three use the code-reviewer role; see explanation below)
T8 Optimize: architecture diagnosis + performance diagnosis + stability diagnosis → must run in parallel (same pattern as above)
```

**T7/T8 specialized review role notes**:

`security-reviewer`, `reliability-reviewer`, `maintainability-reviewer`, and similar roles are not independent agent-definition files. They are implemented by passing role-specific instructions to the generic `code-reviewer` through the Agent tool `prompt` parameter. Example dispatch:

```python
# Security review
Agent(
  subagent_type='code-reviewer',
  prompt='You are a security review expert and focus only on security dimensions (SQL injection / command injection / XSS / path traversal / sensitive data exposure).
Use the security gate scoring rules (P1/P2/P3) from quality-gates.md.
Ignore reliability and maintainability dimensions.'
)

# Reliability review
Agent(
  subagent_type='code-reviewer',
  prompt='You are a reliability review expert and focus only on reliability dimensions (silent failure / missing exception handling / no timeout configuration / missing degradation fallback).
Use the reliability gate scoring rules from quality-gates.md.
Ignore security and maintainability dimensions.'
)

# Maintainability review
Agent(
  subagent_type='code-reviewer',
  prompt='You are a maintainability review expert and focus only on maintainability dimensions (route registration / module exports / type specifications / code duplication).
Use the maintainability gate scoring rules from quality-gates.md.
Ignore security and reliability dimensions.'
)
```

The same applies to `verifier` (T4 Phase 5 online acceptance): the `prompt` parameter is used to assume the online-acceptance role, and no independent definition file is required. When dispatching, always use the role name `verifier`; do not use the old name "browse subagent".

### Must run serially (dispatch in order)

Serial execution is required when any of the following conditions are true:

1. **Output dependency**: B needs A's output before it can start
2. **File conflict**: A and B modify the same file
3. **State dependency**: B depends on the system state modified by A
4. **Priority dependency**: do not start P2 repairs before P1 repairs are complete

**Forced serial scenarios**:

```text
T3 Product Design:
Phase 1 (Requirements Analysis) → Phase 2 (Solution Design) → Phase 3 (Feasibility Review)
(Solution design depends on the output of requirements analysis; review depends on the complete solution document)

T4 Deliver:
Development (Phase 1) → Review (2) → Test (3) → Deploy (4) → Acceptance (5)
(Each stage depends on the output of the previous stage)

T7 Quality (single file):
problem-1 repair → verification passes → problem-2 repair
(The same file cannot be repaired in parallel; avoid conflicts)

Database migration (T4):
db-migrator completes first → implementation-layer subagent starts development
(code depends on the new database structure)
```

---

## Subagent Role Definitions

### Role profile reference

Each agent role has a corresponding evolvable profile file (`assets/agent-profiles/{role}.md`).
During ACT, the "evolution area" content of the current profile should be injected into the subagent work order (if the file exists).

Profile update rules:

- Fixed area: manual modification only (git-audited)
- Evolution area: REFLECT may propose updates and write them into the `pending_evolution` queue
- The `pending_evolution` queue is managed by the `autoloop-experience.py evolve-profile` subcommand

---

### `researcher`

**Responsibilities**: information gathering, online research, competitive analysis

**Trigger scenarios**: T1 full workflow, T2 option analysis, T3 Phase 1 (when information gaps, background knowledge, or technical constraints need to be filled)

**Template**: instructions include research topic / dimensions / goals / source requirements (>= 3 independent sources) / output format (key findings + data points + information gaps + related findings). Confidence calculation follows `quality-gates.md`.

---

### `planner`

**Responsibilities**: task decomposition, architecture design, plan formulation

**Trigger scenarios**: before complex tasks begin (technical solution design), T3 Phase 1 (requirements extraction and JTBD definition), T3 Phase 2 (technical solution design, also serving as technical architect)

**Template**: instructions include functional requirements / repository path / technology stack, and read `main_entry_file` + related modules. Output: impact scope (modified / new files + DB changes + new endpoints) + interface definitions + implementation order and dependencies + risk identification.

---

### `backend-dev`

**Responsibilities**: backend / server code implementation

**Trigger scenarios**: T4 Phase 1, during T7/T8 repair

**Template**: instructions include files to modify / create (absolute paths) + modification guidance, `tech_constraints`, constraints (what must not change), and `syntax_check_cmd`. Output: file content + syntax-validation results + route registration confirmation.

---

### `frontend-dev`

**Responsibilities**: frontend implementation

**Trigger scenarios**: T4 Phase 1, and frontend-side repair in T7/T8

**Template**: same structure as `backend-dev`, plus the frontend directory path. Output: file content + syntax-validation results.

---

### `db-migrator`

**Responsibilities**: database migration script creation and verification

**Trigger scenarios**: T4 Phase 1 (when database changes exist), T8 (when database structure is being optimized)

**Template**: instructions include `codebase_path`, `migration_check_cmd`, and DDL change description. `upgrade` (`IF NOT EXISTS`) + `downgrade` (rollback) must both be implemented. Output: migration file path + implementation + verification results.

---

### `code-reviewer`

**Responsibilities**: security + quality review

**Trigger scenarios**: T4 Phase 2, each T7 scan round, T8 checkpoints

**Template**: instructions include review type (`security` / `reliability` / `maintainability` / `full`), repository path, and key file list. The review checklist follows `quality-gates.md`, and scoring follows `enterprise-standard.md`. Output: issue list (`id` / file / line / type / P-level / description / repair suggestion) + dimension score + P1/P2/P3 statistics.

---

### `generator`

**Responsibilities**: batch content generation

**Trigger scenarios**: full T6 workflow

**Template**: instructions include the complete template (variables marked with `{{name}}`), the variable values for the current unit, quality standard (`N/10`), and common errors. Output format: `---UNIT-START-{unit_id}---` content `---UNIT-END---` + `---QUALITY---` score `---QUALITY-END---`.

---

### `verifier`

**Responsibilities**: syntax verification, route-registration verification, online acceptance (`T4 Phase 5` uses this role name uniformly; do not use the old name "browse subagent")

**Trigger scenarios**: T4 Phase 3 + Phase 5, and after every T7/T8 repair

**Invocation**: `Agent(subagent_type="code-reviewer", prompt="You are the verifier subagent...")`

Note: `verifier` is not an independent role. It is a role-based invocation of `code-reviewer`. The Chrome DevTools MCP tool may be used for T4 Phase 5 online acceptance (if configured).

**Template**: instructions include verification type (`build` / `routing` / `online acceptance`), repository path, verification steps, and expected results. Output: Pass / Fail for each step + overall conclusion.

**T4 Phase 5 online acceptance**: provide `acceptance_url` + acceptance-criteria list, and output pass / fail per criterion + screenshot evidence. Final confirmation must wait for user input `User confirmation (online acceptance)`.

---

### `cross-verifier`

**Responsibilities**: perform conflict checks and multi-source verification on findings from multiple `researcher` subagents

**Trigger scenarios**: after each T1 round; after T2 option analysis completes

**Invocation**: `Agent(subagent_type="researcher", prompt="You are the cross-verifier subagent...")`

**Applicable templates**: T1, T2

**Template**: input the findings list from `findings.md`. Task: identify contradictions → analyze causes (time / scenario / methodology / genuine dispute) → provide handling suggestions. Output: contradiction report table (number / dimension / statement A+B / analysis / suggestion) + verification-status summary (confirmed / contradictory / unverified counts).

---

### `option-analyzer`

**Responsibilities**: conduct in-depth analysis of individual candidate options in comparison tasks

**Trigger scenarios**: T2 first round, one option per parallel allocation

**Invocation**: `Agent(subagent_type="researcher", prompt="You are the option-analyzer subagent...")`

**Applicable template**: T2

**Template**: instructions include option name / comparison subject / evaluation dimensions / analysis angle (positive or critical; the same option is assigned both angles to ensure bias checking). Every dimension must be supported by evidence and identify core strengths / weaknesses (<= 3 each) + applicable scenarios. Output: dimension score table + overall score + confidence (quoted from `quality-gates.md`).

---

### `neutral-reviewer`

**Responsibilities**: check option-analysis results for scoring bias

**Trigger scenarios**: after all T2 option analyses are complete

**Invocation**: `Agent(subagent_type="researcher", prompt="You are the neutral-reviewer subagent...")`

**Applicable template**: T2

**Template**: input all `option-analyzer` outputs. Check: abnormal scores (all >= 9 or <= 3) / balance of evidence quality / selective citation / consistency of scoring standards. Output: bias risk (`low` / `medium` / `high`) + dimensions that need re-evaluation + additional suggestions + conclusion (`passed` / `needs supplementation`).

---

### `template-extractor`

**Responsibilities**: extract reusable generation templates from user-provided examples

**Trigger scenarios**: T6 Step 1, template normalization before batch generation

**Invocation**: `Agent(subagent_type="planner", prompt="You are the template-extractor subagent...")`

**Applicable template**: T6

**Template**: input the user example. Tasks: identify fixed / variable parts (mark variables with `{{name}}`) + extract quality criteria (1-10 points) + identify common errors. Output: template structure + variable-definition table + quality standards + common errors.

---

### `quality-checker`

**Responsibilities**: independently score the quality of batch-generated content units

**Trigger scenarios**: after completion of each generated unit in T6

**Invocation**: `Agent(subagent_type="code-reviewer", prompt="You are the quality-checker subagent...")`

**Applicable template**: T6

**Template**: input generated content + quality standards. Scoring rules: `8-10 pass` / `7 borderline pass, improve` / `5-6 needs improvement` / `1-4 regenerate`. The check is independent from the generator's self-evaluation; any difference > 2 points is decided by the checker. Output: score + main issues + improvement suggestions.

---

### Independent grader roles (applicable to all templates)

**Principle**: the executor and evaluator must be different subagent instances. The evaluator receives only the output, not the execution process information (blind evaluation), and scores according to the anchor points and evidence requirements in `quality-gates.md`.

| template | executor | evaluator | scoring dimensions |
|------|----------|-----------|---------|
| T1 Research | researcher | research-evaluator | coverage / credibility / consistency |
| T2 Compare | option-analyzer | compare-evaluator | bias / coverage / consistency |
| T3 Design | planner | feasibility-reviewer | design completeness / feasibility / requirements coverage / scope accuracy / validation evidence |
| T5 Iterate | optimizer | kpi-evaluator | KPI attainment / strategy effectiveness / side effects |
| T6 Generate | generator | quality-checker | content quality / format compliance / variable coverage |
| T4 Deliver | implementer | code-reviewer | security / reliability / maintainability |
| T7 Quality | code-reviewer (fix) | security / reliability / maintainability-reviewer | same as T4 |
| T8 Optimize | optimizer | architecture / performance / stability-reviewer | architecture / performance / stability |

**Evaluator blind-review constraints**:
- The evaluator prompt contains only: output content + scoring criteria (`quality-gates.md`)
- It must not include: this round's strategy name, execution process, expected improvement goals
- Purpose: avoid confirmation bias and ensure scoring is based on output quality itself

---

### `feasibility-reviewer`

**Responsibilities**: perform an independent feasibility review of the T3 product-design plan, covering 5 quality-gate dimensions

**Trigger scenarios**: T3 Phase 3 (independent feasibility review, after the solution document is complete)

**Invocation**: `Agent(subagent_type="planner", prompt="You are the feasibility-reviewer subagent...")`

**Applicable template**: T3

**Template**: input the complete solution document (`PRD` / `spec`) + quality-gate standard (T3 section of `gate-manifest.json`). Scoring dimensions:

- `design_completeness` (7/10): coverage ratio between requirement items and design solutions
- `feasibility_score` (7/10): whether the technical architecture, dependencies, and risks are feasible
- `requirement_coverage` (7/10): whether each requirement traces back to a document section
- `scope_precision` (7/10): whether IN / OUT scope is clear and dependencies are identified
- `validation_evidence` (7/10): whether feasibility checks + risk assessment are complete

Output: 5 dimension scores (0-10) + major issue list + overall pass / fail verdict.

---

### T7 review roles (three parallel reviewers, all implemented through `code-reviewer`)

| Role | Responsibilities | Invocation |
| ---- | ---- | -------- |
| `security-reviewer` | injection / XSS / path traversal / sensitive data exposure | `Agent(subagent_type="code-reviewer", prompt="You are security-reviewer...")` |
| `reliability-reviewer` | silent failure / exception handling / timeout / degradation fallback | `Agent(subagent_type="code-reviewer", prompt="You are reliability-reviewer...")` |
| `maintainability-reviewer` | entry registration / module export / type specifications / code duplication | `Agent(subagent_type="code-reviewer", prompt="You are maintainability-reviewer...")` |

**Trigger scenarios**: T7 first round parallel scan. See `commands/autoloop-quality.md` for the full command template.

### T7 unified review framework

All three reviewers receive the same file list and output this unified format: `| problem_id | file | line | type | priority (P1/P2/P3) | description | repair suggestion |`

**Aggregation**: merge + deduplicate (`same file + line + type`) → keep the highest priority among duplicates → decide by T7 composite rules in `quality-gates.md`.  
**Conflict arbitration**: where priorities differ, take the highest; where repair suggestions conflict, prefer the safer repair (record the trade-off); score difference > 2 points triggers third-party arbitration.

---

### `fix-{type}` (quality issue fixer)

**Responsibilities**: perform minimal fixes for specific issues found by T7 scans

**Trigger scenarios**: T7 Round 2-N, assign issues in order P1 → P2 → P3

**Invocation**: `Agent(subagent_type="backend-dev" or "frontend-dev", prompt="You are the fix-{type} subagent...")`

Use `backend-dev` for backend / server issues; use `frontend-dev` for frontend / client issues.

**Applicable template**: T7

**Template**: instructions include issue ID / file / line / description / suggestion / round / context summary. Constraints: only change the annotated issue, do not change function signatures / APIs, run `syntax_check_cmd` immediately after the modification. Output: diff + verification result + whether new issues were introduced.

---

### T8 diagnostic roles (three parallel reviewers, all implemented through `code-reviewer`)

| Role | Responsibilities | Invocation |
| ---- | ---- | -------- |
| `architecture-diagnostic` | layering / coupling / API consistency / configuration management / code reuse | `Agent(subagent_type="code-reviewer", prompt="You are architecture-diagnostic...")` |
| `performance-diagnostic` | N+1 queries / connection pool / cache / sync mixing / query efficiency | `Agent(subagent_type="code-reviewer", prompt="You are performance-diagnostic...")` |
| `stability-diagnostic` | external dependency fallback / error handling / health checks / timeout | `Agent(subagent_type="code-reviewer", prompt="You are stability-diagnostic...")` |

**Trigger scenarios**: T8 first round parallel diagnosis. See `commands/autoloop-optimize.md` for the full command template.

---

### `optimization-fix` (optimization fix executor)

**Responsibilities**: fix architecture / performance / stability issues found by T8 diagnostics

**Trigger scenarios**: T8 Round 2-N, executed in overall priority order

**Invocation**: `Agent(subagent_type="backend-dev" or "frontend-dev", prompt="You are the optimization-fix subagent...")`

Use `backend-dev` for backend / server repairs; use `frontend-dev` for frontend / client repairs.

**Applicable template**: T8

**Template**: instructions include issue ID / type (`architecture` / `performance` / `stability`) / description / impacted file / recommendation / round / context summary. Constraints: do not change public API signatures; do not change DB schema (unless explicitly planned); run `syntax_check_cmd` after modifications. Execution steps: read file → analyze impact → minimal repair → verify. Output: change list + description + verification results + three-dimension impact estimate.

---

## Output Rules for Document-oriented Subagents

When a subagent is asked to generate document content (`PRD`, report, analysis, etc.), the output must be written to a file:

- **File path**: `{work_dir}/output-{agent_name}.md` (for example `output-prd-part1.md`)
- **Forbidden**: returning only task-output text without writing the file
- **Merge convention**: the SYNTHESIZE phase sorts and stitches by file name (`output-01-*.md`, `output-02-*.md`)
- **Applicable templates**: T1 Research, T2 Compare, T3 Product Design

Non-document subagents (`code-reviewer`, `backend-dev`, etc.) are not bound by this rule and may return structured results directly in task output.

---

## Subagent Immediate Discoveries (optional return field)

If the subagent discovers information during execution that is not directly related to the current task but is valuable for future rounds or other tasks, include a `discoveries` list in the return value.

**Applicable types** (not the same as REFLECT; record immediately):

- Environmental facts: API rate limits, data-source status, tool compatibility
- Resource changes: file-path changes, dependency version updates, service migrations
- Tool discoveries: a tool is unavailable or behaves specially in certain scenarios

**Not applicable** (these still belong in REFLECT):

- Strategy evaluation (`Maintain` / `Avoid`) — requires VERIFY results before judgment
- Quality score — requires independent verification

**Return example**:

```json
{
  "result": "...",
  "discoveries": [
    "xAI Grok API rate limit is 60 requests per minute; recommended interval for batch tasks is 2 seconds",
    "The target website is protected by Cloudflare and requires a headless browser"
  ]
}
```

After the controller receives `discoveries` during ACT, it immediately writes them into the "Immediate Discoveries" area of `autoloop-findings.md` and into `metadata.immediate_discoveries` in `state.json`, without waiting for REFLECT.

---

## MCP Tool Availability (cross-platform)

- **Claude Code**: the subagent automatically inherits all installed MCP tools without additional configuration
- **Gemini CLI / Codex CLI**: use `autoloop-mcp-bridge.py discover` to inspect available tools
- **Environment without MCP**: the subagent should use built-in tools (`read_file`, `grep`, `bash`, etc.) to complete the task

The controller detects the platform during ACT and notes MCP availability in the work order.

---

## Context Integrity Checklist

Before each dispatch, ensure the following content is included in the instruction:

- [ ] Role definition ("You are X subagent")
- [ ] Concrete task (actionable instructions, not vague direction)
- [ ] **Absolute paths** to all related files (not relative paths)
- [ ] Constraints that must be respected (what cannot be changed)
- [ ] Acceptance criteria (how completion is judged)
- [ ] Output format (structured for easy integration)
- [ ] Current iteration round (so the subagent knows which round it is)
- [ ] Context summary (including the previous round's reflection record):
- Carryover issue list (problems in `Pending` status)
- Effective / ineffective strategies (avoid repeating ineffective methods)
- Recognized patterns (make the subagent aware of systemic problems)
- Relevant lessons learned

**If any item is missing → rewrite the instruction and dispatch again.**

---

## Subagent Failure Return Specification

If the subagent cannot complete the task, it **MUST** return the following structured information (written into `iterations[-1].act`):

- `failure_type`: failure-type enum (see table below)
- `failure_detail`: concrete description (one sentence describing what failed)
- `completion_ratio`: completion percentage (0-100; fill it in for partial completion)

| failure_type | Meaning | Typical scenarios |
|-------------|------|---------|
| `timeout` | The task is too large and the context is insufficient | Too many files to analyze; search scope too broad |
| `capability_gap` | The current role / tools cannot complete the task | Specific domain knowledge is required; required tools are unavailable |
| `resource_missing` | Necessary information or permissions are missing | File does not exist, API lacks permissions, dependencies are not installed |
| `external_error` | External service failure | API rate limit, network timeout, third-party service outage |
| `code_error` | Script / tool error | Syntax error, missing dependency, version incompatibility |
| `partial_success` | Partially completed | 3 of 5 subtasks completed |

**Example return**:
```json
{
  "failure_type": "external_error",
  "failure_detail": "OpenAI API 429 rate limit exceeded",
  "completion_ratio": 60
}
```

The controller automatically selects a differentiated recovery strategy based on `failure_type` (see the ACT failure-handling section in `loop-protocol.md` for details).

---

## Subagent Self-check Protocol (Context Self-Check)

### Must be included when returning

- `completion_ratio`: an integer between 0-100, estimating task completion percentage (write it to `iterations[-1].act`)

### Self-check rules

Continuously evaluate during execution:

- If the main goal is < 50% complete and multiple methods have already been tried: stop, report current progress and blocking reasons, rather than continue forcing it
- If it becomes clear that the current approach simply does not work: terminate early and report it instead of pushing until exhaustion
- If a problem exceeds the role's capabilities: explicitly mark it and return it to the controller

### Controller handling logic

The controller automatically interprets `completion_ratio` during the ACT→VERIFY transition:

- **>= 80%**: enter VERIFY normally
- **50-79%**: enter VERIFY but mark `partial = true` (used as a reference during VERIFY scoring)
- **< 50%**: mark `needs_replanning = true`; DECIDE is recommended to replan

---

## Failure-handling Strategy

| Failure type | Handling strategy |
| -------- | -------- |
| Subagent cannot find the information | Change keywords / change sources / mark "Information not available" |
| Subagent output format error | Extract usable parts and fill in missing fields |
| Subagent code verification failed | Return detailed errors to the subagent and request a repair (respect the unified retry cap = 2; see `loop-protocol.md`) |
| Subagent timeout | Mark as "Partially Completed", record progress, and continue other tasks |
| Parallel subagents conflict | Record both solutions and use the more conservative one (smaller change) as the baseline |

---

> **Technology stack variable filling**: for variable values of each technology stack, see `references/domain-pack-*.md` and the unified parameter glossary in `references/loop-protocol.md`. General rule: all variables are read from plan and must not be hard-coded at dispatch time.
