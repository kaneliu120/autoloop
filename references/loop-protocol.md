# Loop Protocol — OODA Iteration Loop Specification

**Protocol Version**: 1.0.0

> Data format rules (parameter glossary, TSV schema, file naming, Bootstrap, SSOT) have been moved to `references/loop-data-schema.md`.
> Version semantics are defined at the beginning of `references/loop-data-schema.md`.

---

## Overview

Every AutoLoop execution follows the standard 8-phase OODA loop. This document defines the concrete behavior, input/output rules, and state-machine transition rules for each phase.

---

## Responsibility Definition for the Three-layer Architecture

| Layer | Identity | Includes | Excludes | Dependency direction |
| -- | ---- | ---- | ------ | -------- |
| Protocol | Single source of truth for rules / standards / enums | Gate thresholds, flow parameters, enums, scoring methodology | Execution steps, ticket format | No upward dependency (top layer) |
| Command | Orchestration / execution plan | Workflow steps, ticket generation, role dispatching, result collection | Threshold values, evaluation standards | Reads Protocol, outputs to Template |
| Template | Report format / deliverable | Section titles, table headers, placeholders | Conditional logic, bash commands | Filled by Command (bottom layer) |

**Boundary rule**: if the institution changes (thresholds / enums) → protocol; if the method changes (step order / tickets) → command; if the format changes (titles / headers) → template.

---

## State Machine

```text
Bootstrap → OBSERVE → ORIENT → DECIDE → ACT → VERIFY → SYNTHESIZE → EVOLVE → REFLECT → OBSERVE (next round) / Completed
                                                                                          ↕
                                                                                   [Paused for confirmation]
```

**Core rules**:
- **Irreversible**: once ACT starts, DECIDE is locked. To adjust strategy, finish the current round first and change it in the next round's DECIDE
- **Pause points**: EVOLVE / Phase 5 may enter a paused-for-confirmation state and resume after user input
- **Error handling**: any phase error → write to `progress.md` → attempt recovery → terminate with explanation if recovery fails
- **Phase enum**: `OBSERVE`, `ORIENT`, `DECIDE`, `ACT`, `VERIFY`, `SYNTHESIZE`, `EVOLVE`, `REFLECT`
- **Execution determinism**: when `autoloop-controller.py --strict` (or `AUTOLOOP_STRICT=1`) is enabled, if any of scoring JSON / validate / variance check fails in VERIFY, the loop **must not enter** SYNTHESIZE; `autoloop-validate.py --strict` counts gate-contract issues as errors.
- **Sliced execution (L1 Runner)**: `autoloop-controller.py <work_dir> --stop-after <PHASE>` runs through the end of that phase, updates `checkpoint.json`, and exits, allowing an unattended host to insert model calls between slices; conventions and operations are documented in `docs/RUNNER.md`.

### The "Gap" column in OBSERVE / ORIENT tables

This column is a **heuristic sorting hint** (helpful for manually scanning CRITICAL / MODERATE items). It is **not** the formal quality measure equivalent to `gate-manifest`; formal judgment is determined by `autoloop-score` and `check_gates_passed`.

### Priority of EVOLVE detection signals (within the same dimension)

When the same dimension matches multiple detection types simultaneously, the controller uses the priority: **regressing > stagnating > oscillation**. A dimension already classified as stagnant / regressing does not also report oscillation.

### T4: Delivery phases and OODA rounds

| delivery-phases.md | OODA rounds (conceptual) | Notes |
|--------------------|--------------------------|------|
| Phase 1–5 | Commonly mapped across multiple `OBSERVE…REFLECT` rounds | See the end of `references/delivery-phases.md` for the concrete mapping |
| Each round still runs all 8 phases | The default T4 OODA round count in `gate-manifest.json` is 5 (aligned with five delivery phases) | `plan.budget.max_rounds` may override |

## OBSERVE — Observation

### Inputs
- `autoloop-plan.md` (task plan)
- `autoloop-progress.md` (historical progress)
- `autoloop-findings.md` (existing findings, including REFLECT records from the last round)
- Current repository state (for engineering tasks)

### OBSERVE Step 0: Read last-round reflection (mandatory from Round 2 onward)

Before scanning the current state, first read the reflection section in `autoloop-findings.md` (the **4-layer structure table**):

1. **Unresolved issues** → prioritize in this round (issues with status "Pending" or "Cross-round carryover")
2. **Effective strategies** → prioritize for DECIDE in this round (strategies evaluated as "Maintain")
3. **Ineffective strategies** → exclude in this round's DECIDE; do not retry (strategies evaluated as "Avoid")
4. **Recognized patterns** → if there is a systemic root cause, this round must change methodology instead of continuing to patch
5. **Bottleneck information** → if a dimension has been blocked across consecutive rounds, try a breakthrough strategy this round
6. **Lessons learned** → adjust this round's method and expectations

This ensures each round starts with the previous round's knowledge instead of starting from zero.

**Global experience read**: besides reading the current task's `findings.md`, also read the recommended strategies in the global strategy-effect library `references/experience-registry.md` for the same template + overlapping `context_tags` (sorted by `success_rate` descending). `context_tags` overlap means the current task tags and the strategy's `context_tags` share at least 2 tags. Strategies without overlapping tags are not recommended, avoiding incorrect cross-context migration. On first-round cold start, global experience is the only source of strategy reference.

**Protocol version check**: at OBSERVE start, check whether the current `protocol_version` matches the version from the previous task. If not (minor / major change), trigger the re-baselining flow (see the re-baselining section in `references/evolution-rules.md`) and use the new baseline as the starting point for this round.

**OBSERVE Step 0 also applies to T7/T8**: when T7 and T8 execute OBSERVE in Round 2+, they must first read the reflection section in `findings.md` to obtain the carryover issue list, ineffective repair patterns, and recognized systemic root causes before defining this round's repair strategy.

**Immediate learning hook**: if Step 0 finds cross-round repeated patterns while reading findings (the same issue appears for 2+ consecutive rounds), write them immediately into the "Pattern Recognition" section of `findings.md` instead of waiting for REFLECT. This ensures recognized repeated patterns are not lost even if the session crashes between ACT and REFLECT.

### Round 1 Bootstrap rule

**Round 1 OBSERVE has no previous VERIFY result and must perform baseline collection instead:**

- **Knowledge tasks (T1/T2/T5/T6)**: current findings = 0, covered dimensions = 0, all quality-gate scores = 0. Write this as the iteration 0 baseline to `progress.md`.
- **Engineering tasks (T4/T7/T8)**: run the initial detection commands to get baseline scores (scan all files with `syntax_check_cmd`, run a full scan with `code-reviewer`) and write the detection results as the iteration 0 baseline to `progress.md`.

Baseline write format:
```markdown
### Baseline (Iteration 0)
- Execution time: {ISO 8601}
- Baseline source: initial collection for Round 1 (no historical data)
- Scores by dimension: {each dimension: 0 or initial detection value}
- Notes: Round 1 has no prior data; this baseline is treated as the "previous-round result" for Round 1 OBSERVE
```

### Questions that must be answered

1. **What is the target state?** — read the target quality-gate values from `plan.md`
2. **What is the current state?** — the latest actual quality-gate values (VERIFY result from the previous round; use the iteration 0 baseline in Round 1)
3. **What is the gap?** — target value - current value, per dimension
4. **How much time / budget remains?** — rounds used / maximum rounds, calculate remaining percentage
5. **What unexpected findings came from the last round?** — read the content appended in the last round from `findings.md` (Round 1: none, write "No historical findings")

### Output
Write to `progress.md`: dimension gap (current / target / gap) + remaining budget % + this round's focus (1-2 dimensions) + carryover from the previous round.

---

## ORIENT — Orientation Analysis

### Goal
Turn the observed gaps into actionable analysis: **why does the gap remain, and how do we fix it?**

### Analysis framework

**Gap cause analysis** (choose what applies):
- Insufficient information (uncovered dimensions / sources)
- Insufficient quality (information found, but evidence is not strong enough)
- Ineffective strategy (the method is correct, but there is no information in this domain)
- Cognitive bias (search keywords restricted the results)
- Resource constraints (insufficient time / budget)

**Strategy adjustment rules**:

| Scenario | Analysis conclusion |
|------|---------|
| No progress for the same dimension across 2 consecutive rounds (improvement < template stagnation threshold; see `parameters.md`) | The current method has reached its limit and needs a new direction |
| Multiple dimensions lag simultaneously | Solve the highest-priority one first; do not spread effort |
| An important unplanned dimension is discovered | Evaluate whether to expand scope (consider the budget) |
| A critical P1 issue is discovered (data loss / security vulnerability) | Escalate immediately and pause other work |
| **Oscillation detection**: the same dimension fluctuates within a ±0.5 band for 3 consecutive rounds **and is non-monotonic (direction alternates)** | Report oscillation and switch to a completely different strategy direction (implemented in `autoloop-controller.py` `detect_oscillation`, distinct from simple monotonic drift) |
| **Cross-dimension regression**: dimension A improves this round but dimension B drops below the gate threshold | Treat as regression; prioritize fixing B next round and mark the strategy as "has side effects" |

### Output
Write to `progress.md`: main gap causes + this round's strategy (name + explanation) + scope adjustments + expected score improvement.

---

## DECIDE — Decision

### Goal
Define a **concrete and executable** action plan: who does what, with which tools, expecting what result.

### Decision principles

**Parallel first**: if tasks can run in parallel, they must run in parallel. Criteria:
- The output of task A is not the input of task B → parallel
- Task A and task B operate on different files → parallel

**Minimize scope**: in each round, do only the most important work for that round; do not try to do everything at once.

**Always have a fallback**: every action must have a backup strategy (if the subagent cannot find the information, what happens next).

**Prefer "Maintain" strategies**: DECIDE in this round should prioritize strategies marked "Maintain" in the reflection section of `findings.md`; exclude strategies marked "Avoid".

### Action plan format
Write a table to `progress.md`: action ID | action | executor | input | expected output | parallel? + execution order (parallel / serial) + fallback strategy.

**Single-strategy isolation principle**: in each DECIDE phase, select only one primary strategy for execution so A/B verification remains attributable. Running multiple strategies in parallel makes score changes non-attributable and causes spurious correlations in the strategy-effect library.

**Precise definition of "strategy"**:
- "Strategy" = the methodological direction selected in DECIDE (for example, "multi-source cross-validation", "parallel option-analyzer evaluation"), uniquely identified by `strategy_id`
- "Strategy" ≠ the number of concurrent subagents. Multiple subagents may run subtasks in parallel inside one strategy
- **Compliance rule**: all TSV rows from all subagents share the same `strategy_id` → compliant with the single-strategy rule

Exception: when multiple independent dimensions need fixing simultaneously and do not affect each other (for example, security and maintainability belong to different code areas), parallel execution is allowed, but each dimension's strategy must be recorded and attributed independently. In `results.tsv`, the `strategy_id` for such a parallel round should be `multi:{S01-xxx+S02-yyy}` (must use the full `SNN-description` form; see experience-registry P3-06), and `side_effect` should say "mixed attribution, do not enter strategy-effect library."

**`strategy_id` naming rule**: each strategy is named in DECIDE with the format `S{NN}-{short-description}` (for example, `S01-sql-param`, `S02-error-handler`). This ID propagates through the round's `results.tsv`, `findings.md`, `progress.md`, and `plan.md` to ensure cross-file traceability.

**Impact-surface analysis (mandatory in DECIDE)**:

Before executing the strategy, analyze cross-dimension dependencies:
1. What dimension is targeted by this round's strategy?
2. Which other dimensions depend on it? Common dependencies:
   - Security ↔ reliability (security hardening may increase exception-handling complexity)
   - Performance ↔ maintainability (performance optimization may reduce readability)
   - Architecture ↔ all dimensions (architecture changes have the broadest impact)
3. List all potentially impacted dimensions
4. VERIFY must validate: the target dimension + all impacted dimensions
5. If any impacted dimension drops below its gate threshold → treat as regression and prioritize it next round

**`plan.decide_act_handoff.impacted_dimensions`**: DECIDE should still explicitly list possibly impacted dimensions so VERIFY and TSV `side_effect` can cross-check. If left empty, `autoloop-controller.py` in EVOLVE will still infer **pass→fail** from **score history** for dimensions that passed hard gates in the previous round but not in the current round, and trigger a cross-dimension regression pause. This is less likely to miss a brake than the old behavior that only detected regression when the handoff was non-empty.

**Strengthened use of the `side_effect` field**: it is not allowed to write "none" without verification. "None" can only be confirmed after VERIFY actually measures the impacted dimensions.

---

## ACT — Action

### Goal
Dispatch subagents according to the decision plan and collect all outputs.

### Subagent dispatch rules

Each dispatch must provide full context (see `references/agent-dispatch.md` for details):
1. Role definition (you are X subagent)
2. Concrete task (actionable, not directional)
3. Inputs (absolute file paths, information content)
4. Constraints (what must not be done)
5. Acceptance criteria (how completion is judged)
6. Output format (explicit structure)

### Execution log
After each subagent completes, record a table in `progress.md`: # | executor | task | status | result summary.

### Immediate learning hook

`discoveries` returned by the subagent (environment facts, resource changes, tool discoveries) are written immediately to the "Immediate Discoveries" area of `findings.md` instead of waiting for REFLECT. Strategy evaluation (`Maintain` / `Avoid`) still belongs in REFLECT. See the "Immediate Discoveries" rule in `references/agent-dispatch.md`.

The controller processes this with `process_act_discoveries()`: write to `findings.md` + `state.json` `metadata.immediate_discoveries`.

### Unified retry-cap rule

**Default retry cap = 2 attempts** (applies to all templates and all subagents).

Exception: the delivery template (T4), because it includes human confirmation, allows the Phase 2 review-fix cycle to run up to **3 rounds**. All other templates must respect the cap of 2.

Any retry / fallback counts described in protocol files must follow this rule:
- Subagent retry in `agent-dispatch.md` → at most 2 attempts
- Phase 2 fix-review cycle in `delivery-phases.md` → at most 3 rounds (T4 only, because it includes human confirmation)
- Other phase rollbacks in `delivery-phases.md` → at most 2 attempts (aligned with this rule)

### Failure handling

When a subagent fails, the controller automatically classifies `failure_type` and selects a differentiated recovery strategy:

| failure_type | Recovery strategy | Retry mode |
|-------------|---------|---------|
| `timeout` | Retry after splitting the task (narrow scope / fewer files) | Retry with smaller scope (max 2 attempts) |
| `capability_gap` | Change role or adjust tool configuration | Retry with a different subagent role (max 2 attempts) |
| `resource_missing` | Pause and request the missing resource from the user | Pause and wait for user input |
| `external_error` | Retry with exponential backoff (`delay = min(base * 2^attempt, 300s)`) | Automatic backoff retry (max 2 attempts) |
| `code_error` | Record the bug, fix it, and retry | Retry after repair (max 2 attempts) |
| `partial_success` | Continue from the breakpoint (keep completed parts) | Continue the unfinished part (max 2 attempts) |

**Handling flow**:
1. Record `failure_type` + `failure_detail` + `completion_ratio` into `iterations[-1].act`
2. Select and execute the recovery strategy based on the table above (all types respect the unified retry cap = 2, except `resource_missing`, which requires user involvement)
3. If the recovery strategy also fails → mark the task as "Partially Completed" and continue other tasks
4. Explain the impact in VERIFY

**Automatic `failure_type` classification rules** (controller-side, when the subagent does not explicitly return `failure_type`):
- `exit_code=124` → `timeout`
- Error message contains `timeout` / `timed out` / `context limit` → `timeout`
- Error message contains `rate limit` / `429` / `503` / `network` → `external_error`
- Error message contains `traceback` / `syntax error` / `import error` → `code_error`
- Error message contains `not found` / `permission denied` / `no such file` → `resource_missing`
- None of the above match → `capability_gap` (default)

### Cross-platform security pipeline (P3-04/05)

Before ACT executes in non-Claude Code environments, `autoloop-security.py` checks:

1. **Tool allowlist**: tools requested by the subagent must be in `TOOL_ALLOWLIST`
2. **Sensitive-path detection**: reads / writes to paths such as `.env` / `credentials` / `secrets` are blocked
3. **Pre-approval for writes**: modifying `.py` / `.sh` / config files requires confirmation

In Claude Code environments, these checks are handled by the host permission system and `security.py` is not activated.

---

## VERIFY — Verification

### Goal
Objectively evaluate the quality of this round's execution result and update scores for all dimensions.

### Verification rules

**Must quantify**: do not accept "much better"; accept only "improved from 6.2 to 7.8".

**Do not trust subagent self-evaluation**: every subagent's evaluation of its own work must be independently verified:
- Code tasks: run `{syntax_check_cmd}` (whether to append file arguments depends on `syntax_check_file_arg`)
- Research tasks: check source count and source quality
- Repair tasks: rerun the affected reviewer(s)

**Regression check**: did this round's fix introduce new problems?
- Engineering tasks: run compile validation on all affected files
- Content tasks: check whether conclusions from previous rounds still hold

### Verification output format
Write to `progress.md`: score update table (dimension / previous round / current round / change / target / status) + improvement details + newly discovered issues + verification conclusion.

---

## SYNTHESIZE — Synthesis

### Goal
Merge all subagent outputs, resolve contradictions, and update core files.

### Synthesis steps

1. **Merge findings**: append all subagent outputs from this round to `autoloop-findings.md`
2. **Resolve contradictions**:
   - Same fact, different wording → list both and explain the basis
   - Different issues in the same file → merge them and avoid duplication
   - Conflicting repair suggestions → choose the safer one (smaller change, smaller impact)
3. **Update structured data**: if `autoloop-results.tsv` exists, update it in sync
4. **Archive the round**: label this round's outputs with the round number for later traceability

### Contradiction resolution rules

| Contradiction type | Resolution rule |
|---------|---------|
| A says "problem exists", B says "no problem" | Use the more conservative answer ("problem exists") and record B's reasoning |
| Two subagents differ by > 2 in scoring the same code | Run a third verification (or use manual judgment) |
| Repair plans conflict with each other | Choose the plan with the smallest change and record why the other was discarded |

---

## EVOLVE — Evolution

### Goal
Based on the result of this round, decide the next-round strategy (or termination).

### Termination hierarchy

AutoLoop has four termination paths, ordered by priority:

1. **All quality gates met** → determine termination behavior according to `completion_authority` (see below)
2. **User interruption** → paused termination → Completed (user terminated), save progress, explain how to resume
3. **Budget exhausted (maximum rounds reached)** → budget termination → Completed (budget exhausted), output the current best result
4. **Unable to continue (no progress in any dimension for 2 consecutive rounds)** → unable to continue → Completed (unable to continue), report the reason and list required user input

**`completion_authority`** — defined in `gate-manifest.json`, differentiated by template:

| Authority type | Applicable templates | Behavior |
|---------|---------|------|
| `internal` | T6/T7/T8 | If all score.py gates pass, terminate automatically (`decision=stop`) |
| `human_review` | T1/T2/T3 | Pause after gates pass (`decision=pause`) and wait for Kane to review key findings before confirming completion |
| `external_validation` | T4/T5 | Pause after gates pass (`decision=pause`) and require actual testing / deployment validation before confirming completion |

### Decision tree

```text
Are all quality gates met?
  └─ Yes → successful termination → Completed (terminated by meeting criteria)
  └─ No →
      Has the maximum round count been reached?
        └─ Yes → budget termination → Completed (budget exhausted)
        └─ No →
            No progress in all dimensions for 2 consecutive rounds (all dimension improvements < template stagnation threshold; see parameters.md §Iteration Control Parameters)?
              Template stagnation thresholds:
              - T1/T2: < relative 3% (general default)
              - T5: < relative 2% (precise KPI convergence)
              - T7: < absolute 0.3 points (fine-grained engineering quality improvement)
              - T8: < absolute 0.5 points (system optimization)
              - T6/T4: not applicable (T6 retries by unit; T4 advances by phase)
              └─ Yes → unable to continue → Completed (unable to continue), output the current best result and notify the user
                        (list the reasons it cannot continue and the user input required; enter paused-for-confirmation)
              └─ No →
                  No progress in the same dimension for 2 consecutive rounds (improvement < template stagnation threshold; see parameters.md)?
                    (Example: T1 current = 80%, threshold = 2.4%; T7 current = 7/10, threshold = 0.3 points)
                    └─ Yes → change strategy (record attempted methods in strategy history)
                    └─ No →
                        Remaining budget < 20%?
                          └─ Yes → focus on the highest-priority dimension
                          └─ No → continue the standard strategy
              → enter next-round OBSERVE
```

**Implementation note (single-KPI T5)**: in `phase_evolve`, the condition "2 consecutive rounds with **all** monitorable dimensions showing no progress → unable to continue" requires **more than one** monitorable dimension (`len(eligible_stag_dims) > 1`) to avoid incorrectly stopping single-KPI tasks. In single-KPI scenarios, termination is mainly driven by **KPI / gate met**, **budget exhausted**, and **user pause**. This intentionally does not fully match the literal reading of "all dimensions" in the decision tree above; the code is authoritative.

**OBSERVE / `findings.md`**: the controller detects the 4-layer structure in `autoloop-findings.md` and writes a summary to `metadata.observe_findings_snapshot`; when `findings.md` differs from `metadata.protocol_version`, it sets `metadata.rebaseline_required=true` and emits a warning (automatic pause for re-baselining is optional and not enabled by default).

### Evolution output
Write to **`autoloop-progress.md`** (consistent with `plan.output_files.progress` in `autoloop-state.json`): at the end of every EVOLVE phase, `autoloop-controller.py` **automatically appends** a Markdown subsection containing the termination decision (continue / criteria met / budget / unable to continue), reason list, and gate summary table. Optional disable: `AUTOLOOP_SKIP_PROGRESS_LOG=1`. Human writers may still add narrative about next-round focus, strategy adjustment, scope changes, expected round count, and so on.

---

## REFLECT — Reflection

### Phase 8: REFLECT (Reflection)

> The knowledge consolidation at the end of each round. This is not optional; it is mandatory. The value of reflection is that it is read and used by OBSERVE Step 0 in the next round.

**Input**: execution results from all phases in this round, VERIFY quality scores, and EVOLVE decisions

### `iterations[-1].reflect` (experience library `autoloop-experience.py write`)

When REFLECT writes data and the controller automatically sends it back to the experience library, it is recommended that the last item in `iterations` use a **JSON object** (not plain text only), and include as much of the following as possible:

| Key | Type | Description |
|----|------|------|
| `strategy_id` | string | Must match this round's DECIDE |
| `effect` | string | `Maintain` / `Avoid` / `Pending Validation` (aligned with the registry enum) |
| `delta` | number | **The only meaning passed to `autoloop-experience.py --score` when writing to the experience library**: single-round score / gate delta (not an absolute score, not Likert) |
| `rating_1_to_5` | integer | Subjective strategy effect (1–5); used **only** for findings / manual tables; the controller **does not** write it to the experience library as delta |
| `score` | number | **Legacy key**: if it is an integer in `[1,5]`, the controller treats it as Likert and **skips** experience-library delta writing; otherwise it is passed to `--score` as a delta-compatible value |
| `dimension` | string | Primary impacted dimension (optional; better if aligned with `plan.gates` `dim`) |
| `lesson_learned` | string | One-sentence actionable lesson (optional) |

Example (delta + Likert separated; escape quotes when written as a single line into state):
`{"strategy_id":"S01-latency","effect":"Maintain","delta":0.5,"rating_1_to_5":4,"dimension":"latency","lesson_learned":"Cache hit rate improved significantly"}`

**4-layer reflection (must be written into the 4-layer structure table in `findings.md`; bullet points alone are not allowed):**

#### Layer 1: Problem Registry

Write to the "Problem List (REFLECT Layer 1)" table in `findings.md`:

| Round | Problem description | Source | Severity | Status | Root-cause analysis |
|------|---------|------|--------|------|---------|
| R{N} | {problem} | {subagent / verification step} | P1/P2/P3 | **Newly Found** / **Fixed** / **Pending** / **Cross-round Carryover** | {why} |

The `status` field must use the unified enum values exactly (`Newly Found` / `Fixed` / `Pending` / `Cross-round Carryover`).

#### Layer 2: Strategy Review

Write to the "Strategy Evaluation (REFLECT Layer 2)" table in `findings.md`:

| Round | Strategy | Effect rating (1-5) | Score change | Maintain \| Avoid \| Pending Validation | Reason |
|------|------|-------------|---------|---------------------|------|
| R{N} | {strategy description} | {1-5} | {+/-score} | **Maintain** / **Avoid** / **Pending Validation** | {why it worked / did not work} |

The evaluation field must use the unified strategy-evaluation enum exactly (`Maintain` / `Avoid` / `Pending Validation`).

#### Layer 3: Pattern Recognition

Write to the "Pattern Recognition (REFLECT Layer 3)" section in `findings.md`:
- Repeated issue types (systemic root-cause analysis)
- Diminishing-return signals (trend of lower improvement across consecutive rounds)
- Cross-dimension correlation (changing A caused B to change)
- Bottleneck identification (which dimension / area remains stuck)

#### Layer 4: Lessons Learned

Write to the "Lessons Learned (REFLECT Layer 4)" section in `findings.md`:
- What hypothesis was validated this round (confirmed / overturned)
- What methodology generalizes (can be reused directly in similar tasks next time)
- Suggestions for improving the AutoLoop process itself

**Experience extraction and distribution**: after REFLECT completes, extract generalizable experience items from this round's findings, evaluate them using the criteria defined in `references/experience-registry.md` (type, impact level, confidence), and distribute them to the corresponding files. Low-risk experience is written directly; high-risk experience is recorded pending approval.

**Key rules**:
- REFLECT must write to the 4-layer structure table in `autoloop-findings.md`; it cannot exist only in thought
- Each round's reflection record is mandatory input for the next round's OBSERVE Step 0
- The problem list is cumulative (track status changes across rounds)
- Strategy evaluation builds the "strategy-effect knowledge library" for DECIDE
- Status and evaluation fields must use the unified enum values defined in this document

---

## Termination

### Handling by termination type

**Termination by meeting criteria**:
1. Update the `plan.md` status to "Completed"
2. Generate the final report (for the file name, see the "Unified Output File Naming Rules" table in this document)
3. Clean temporary files (optional)

**Budget termination**:
1. Update the `plan.md` status to "Budget Exhausted"
2. Generate the "Current Best Result" report
3. Clearly mark which targets were not met

**User interruption**:
1. Save current progress immediately
2. Generate an interim report (marked "User Interrupted")
3. Explain the resume method (how to continue from the current state next time)

**Unable to continue**:
1. Clearly explain the reason it cannot continue
2. List the information required from the user
3. Explain how work will continue after that information is provided

---

## Loop Log Format

Every complete loop produces a standard log in `autoloop-progress.md`, including: iteration number, start / end time, status, and outputs for each phase (observation / orientation / decision / action log / verification / synthesis / evolution decision / reflection). The reflection section must record problem-registry count, strategy-review rating, pattern recognition, lessons learned, and next-round guidance, and mark which corresponding layer in `findings.md` has been written.

---

## Pipeline Parallel Execution (P3-01)

### Parallel-condition rules

Templates in the pipeline run serially by default (`T1→T2→T3→T4`). They may run in parallel when all of the following are true:

- No data dependency exists between the two templates (the output of template A is not the input of template B)
- The two templates operate on different file sets (no write conflict)

### Parallel isolation method

Use Git Worktree to create an isolated workspace for each parallel template:

1. `git worktree add <path> -b autoloop-<template>-<timestamp>` creates a worktree
2. Each template runs its full OODA loop in its own worktree
3. After completion, merge results with: `git merge --no-ff autoloop-<template>-<timestamp>`
4. Cleanup: `git worktree remove <path>` + `git branch -d autoloop-<template>-<timestamp>`

### Conflict handling

- If a conflict occurs during merge → pause and notify the user for manual resolution
- Merge strategy for parallel templates' `findings.md`: interleave-sort by timestamp

### Configuration

Add optional `parallel_groups` in the pipeline config:

```yaml
pipeline:
  stages:
    - [T1]           # serial
    - [T2]           # serial (depends on T1)
    - [T7, T8]       # parallel group (no dependency)
```

---

## Enterprise Governance

In enterprise environments, AutoLoop provides governance extension points implemented through `scripts/autoloop-governance.py`:

| Capability | Description | Command |
| ------ | ------ | ------ |
| **Secrets detection** | Scan output files for sensitive information such as API keys, passwords, and tokens | `scan-secrets <file>` |
| **Policy-violation detection** | Check whether agent operations violate organizational policy (for example, deployment requires approval) | `check-policy <action>` |
| **Approval-flow audit** | Record all governance events into a JSONL audit log | `approval-log` |
| **Role permissions** | RBAC-based permission checks for user actions (`admin` / `developer` / `reviewer` / `viewer`) | `role-check <user> <action>` |

Config files are located at `~/.autoloop/governance/`, including `policies.json` (policy overrides) and `roles.json` (user-role mapping). In single-user scenarios, the default role is `admin` and no extra config is required.

---

## Middleware Architecture (P3-08)

The controller's core OODA 8-phase pipeline remains unchanged. Cross-cutting concerns are handled by independent Middleware modules:

| Middleware | Responsibility | Activation phase |
| --------- | ---- | ------- |
| `logging` | Unified phase logging | All phases |
| `cost_tracking` | Cost accumulation | After ACT |
| `evaluator_audit` | Scoring-event recording | After VERIFY |
| `failure_classification` | Automatic failure classification | After ACT |
| `security` | Cross-platform security checks | Before ACT |

Each Middleware can be enabled / disabled via the `AUTOLOOP_MIDDLEWARE` environment variable (comma-separated list).

### Middleware interface contract

```python
def middleware_name(phase: str, state: dict, work_dir: str, **kwargs) -> dict:
    # Returns {"proceed": True/False, "modifications": {...}}
```

- When `proceed=False`, interrupt the Middleware chain and return a `blocked_by` identifier
- Keys in `modifications` are applied by the controller to `state` (dot-separated paths indicate nesting)
- Implementations live in the `scripts/middleware/` directory, one module file per cross-cutting concern
- `__init__.py` re-exports all Middleware classes
- Module list: `logging_mw.py`, `cost_tracking.py`, `evaluator_audit.py`, `failure_classification.py`
- This is currently an interface definition + documentation; the actual logic still lives in `autoloop-controller.py` and will gradually migrate during future refactors

---

## Multi-model Routing (P3-09)

Config file: `references/model-routing.json`

In the current Claude Code session, subagents share the same model and cannot switch models at runtime. P3-09 is reserved infrastructure for future pipeline execution across multiple sessions / models:

- **`template_models`**: recommended model per template (`T1-T8`) and ACT-phase overrides (for example, T1 research uses Grok `web_search`)
- **`phase_models`**: default model strategy per phase (ACT chooses by template; VERIFY uses scripts and does not need a model)
- **`multi_session_pipeline`**: reserved interface, `enabled=false`. When enabled in the future, the pipeline can start an independent session for each template

During ACT, the controller outputs recommended model information through `get_recommended_model()` (informational only; it does not switch automatically). The operator may choose the session model manually based on that output.
