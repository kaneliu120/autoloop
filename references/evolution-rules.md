# Evolution Rules — Inter-Round Evolution Rules

## Overview

AutoLoop's core capability is adjusting goals, scope, and strategy dynamically during iteration. This document defines when to adjust them, how to adjust them, and how those adjustments must be recorded.

**Core principle**: evolution is controlled, not open-ended. Every adjustment must have explicit trigger conditions and boundaries.

**Unified status enum**: the canonical status enum is defined in `references/loop-protocol.md`. All evolution records must use the values defined there and may not introduce alternative terms such as "done", "not done", or "pending".

---

## Evolution Type 1: Scope Expansion

### Trigger Conditions
- a subagent discovers an unplanned dimension that materially affects the goal
- the test is whether ignoring that dimension would meaningfully distort the conclusion

### Expansion Rules

**Expansion allowed**:
```text
New dimension importance = high (affects the core conclusion)
+ remaining budget >= 30%
+ total dimensions after expansion <= initial dimensions x 1.5
-> expansion allowed; cover the new dimension in the next round
```

**Expansion not allowed**:
```text
Remaining budget < 30%
OR expansion would double the total dimension count
OR the relation between the new dimension and the core goal is unclear
-> record the new dimension in the "Expansion Directions" section of findings.md, but keep it out of the current scope
```

### Expansion Steps
1. Append the new dimension under "Scope Definition > Expanded Dimensions" in `autoloop-plan.md`.
2. Add a change-log record with the time, added dimension, and trigger reason.
3. Update the coverage denominator (the total dimension count increases).
4. Record the decision in the current round's EVOLVE section of `autoloop-progress.md`.

---

## Evolution Type 2: Narrowing the Focus

### Trigger Conditions
- >= 70% of the budget has been consumed, but coverage is still < 60%
- >= 3 dimensions have lagged simultaneously for 2 consecutive rounds
- some dimensions are extremely information-scarce and further investment has very low expected return

### Narrowing Rules

**Narrowing priority**: preserve the dimensions with the greatest impact on the core conclusion; demote or remove secondary dimensions first.

**Dimensions whose requirements may be lowered**:
```text
Dimension importance = low (impact on the recommendation/conclusion < 10%)
-> lower the quality standard from "3 sources" to "1 source is enough"
-> note in the report that research depth on this dimension is limited
```

**Dimensions that may be skipped entirely**:
```text
Dimension importance = low AND information is extremely hard to obtain AND budget is tight
-> remove the dimension from the coverage denominator
-> explicitly state in the report that this dimension was not researched and why
```

### Narrowing Steps
1. Record the reduction and its reason under "Scope Changes" in `autoloop-plan.md`.
2. Update the quality gates and clearly mark any lowered requirements.
3. Record the decision and impact assessment in `autoloop-progress.md`.

---

## Evolution Type 3: Strategy Switching

### Trigger Conditions
- the same dimension improves by less than 3% of its current score for 2 consecutive rounds
  - example: if the current score is 80%, the improvement threshold is 2.4%; if the current score is 7/10, the threshold is 0.21 points
- the current method has reached its limit for that dimension

### Strategy Switching Rules

Record the methods already tried, then switch to an untried direction.

**Knowledge-task strategy matrix**:

| Already Tried | Switch To |
|--------|--------|
| keyword search | direct access to official documentation |
| English search | Chinese search (for China-market data) |
| general search | academic / professional databases |
| recent content | historical content (to understand how the space evolved) |
| text sources | video / podcast sources (conference talks, etc.) |

**Engineering-task strategy matrix**:

| Already Tried | Switch To |
|--------|--------|
| algorithm optimization | architectural refactor |
| query optimization | caching strategy |
| code review to find problems | profiler-driven bottleneck analysis |
| line-by-line fixes | batch replacement (regex / scripts) |

### Strategy Switching Steps
1. In Layer 2 ("Strategy Review") of `autoloop-findings.md`, mark the failed strategy as `Avoid` and the new strategy as `Pending Verification`.
2. Append the change to the "Strategy History" section of `autoloop-plan.md` (format defined under "Evolution Decision Log Format" below).
3. In ORIENT, explicitly describe the new strategy and reference the `Avoid` strategy from `findings.md` to prevent repeating it.

---

## Evolution Type 4: Priority Reordering

### Trigger Conditions
- an urgent P1 issue is discovered (data-loss risk, production security vulnerability)
- a critical risk is found that is more severe than expected

### Criteria for Urgent P1 Issues

Engineering tasks:
```text
Urgent P1 (stop everything and address immediately):
- evidence that SQL injection is already being exploited
- keys/passwords exposed in the code repository
- a real risk of deleting production data by mistake
- a memory leak pattern that crashes the service
```

Knowledge tasks:
```text
Urgent P1 (notify the user immediately):
- the research target carries major legal/compliance risk
- a core assumption is found to be fundamentally wrong (for example, the market direction itself is wrong)
```

### Urgent P1 Handling Flow
1. Immediately pause all other work in the current round.
2. Notify the user and wait at a human confirmation gate.
3. After confirmation, fixing the urgent P1 takes precedence over every other task.
4. Resume normal iteration only after the urgent P1 fix is complete.

### Priority-Reordering Log Format
```markdown
### Priority Change Log
- Time: {time}
- Trigger: {urgent P1 description}
- Paused tasks: {list}
- New priority order: {urgent P1 fix -> other P1 -> ...}
- Estimated resume time: {estimate}
```

---

## Evolution Constraints (Preventing Unbounded Scope Creep)

### Scope Expansion Limits
- at most 2 expansions over the entire task lifecycle
- after each expansion, total dimensions must remain <= initial dimensions x 1.5
- cumulative added dimensions must remain <= 50% of the initial dimension count

### Budget-Extension Rules
- AutoLoop does not extend budget automatically
- once the max round count is reached, only explicit user approval may add more budget
- when asking for more budget, explain the current state, the remaining gap to target, and how many more rounds are expected

### Goal-Drift Protection
- the core goal may not change during iteration; only additions to scope are allowed in the "Scope Definition" section of `plan.md`
- if the initial goal definition is found to be flawed, pause and ask the user to reconfirm the goal
- once the goal changes, previously generated iteration results may need to be re-evaluated

---

## Protocol Evolution Flow

This section defines the standard flow for changing AutoLoop protocol files themselves. Protocol evolution differs from inter-round evolution: the former changes the rules in `references/`, while the latter only changes how the current task is executed.

**Core principle**: the protocol is the single source of rules. Changes must be controlled, traceable, and backward compatible.

```text
Trigger -> Proposal -> Approval -> Update -> Notify -> Verify -> Conflict Handling -> Archive
```

### Protocol Evolution Steps

| Step | Owner | Input | Output | Recorded In |
| ---- | ------ | ---- | ---- | -------- |
| 1 Trigger | REFLECT subagent | rule issue discovered during iteration | change request (file + issue + impact) | REFLECT section of `progress.md` |
| 2 Proposal | orchestrating agent | change request | full proposal (what changes + why + impact + alternatives) | REFLECT section of `progress.md` |
| 3 Approval | user (Kane) | proposal | approval / rejection / revision comments | REFLECT section of `progress.md` |
| 4 Update | orchestrating agent | approved proposal | updated protocol file + linked changes | current round in `progress.md` |
| 5 Notify | orchestrating agent | update result | change notice (file / section / content / effective round / linked changes) | current round in `progress.md` |
| 6 Verify | next-round ORIENT subagent | change notice | verification report (rule effective + linked docs consistent + no conflict) | next-round ORIENT in `progress.md` |

**Verification stage 2 (outcome validation)**:
- Every change must declare an expected result in the format: expected `{metric}` improves from `{current}` to `{target}` within `{N}` tasks; amplitude must be <= 20%.
- Meets expectation -> harden it, patch+1.
- Positive trend but not enough -> extend by 1 more task.
- No trend -> trigger rollback review.
- Record the result in the protocol-change effectiveness tracking table in `experience-registry.md`.

**Tracking table update timing**: when the proposal is approved (create row) -> after each task (append data) -> when the validation window ends (final judgment) -> after rollback (record outcome).

**Rollback review criteria** (not automatic rollback):
1. Zero positive improvements within the window -> analyze why (bad change / different environment / insufficient sample).
2. Any dimension regresses by >= 1.0 points -> roll back the change and bump patch+1.
3. Insufficient sample -> extend once, but only once.

### Conflict Handling

When a new protocol rule conflicts with an existing rule:

1. **Newest approved rule wins**: once user-approved, the new rule takes precedence and overrides the old one.
2. **Conflict identification**: detect the conflict during Step 6 verification and record it in the current round's "Conflict List" in `autoloop-progress.md`.
3. **Resolution scheduling**: the conflict automatically becomes a REFLECT topic in the next round and generates a new change request (back to Step 1).
4. **Temporary handling**: until resolved, execution follows the latest approved change notice; the conflicting part of the old rule is temporarily suspended.

---

### Archiving

- All protocol change records (change request -> proposal -> approval -> notice -> verification) are permanently retained in the relevant round of `autoloop-progress.md` and must not be deleted.
- The archive serves as historical input for future REFLECT phases, preventing rejected changes from being proposed repeatedly.
- If protocol-change history needs to be summarized after the task ends, extract it from the "Protocol Change Notice" sections across `autoloop-progress.md`.

---

## Evolution Decision Log Format

Append every evolution decision to the end of the current round in `progress.md`. Each entry must include:
- trigger condition
- decision type (expand / narrow / strategy switch / priority reorder)
- before/after comparison
- impact assessment (coverage / budget / quality)
- strategy status update table (`Keep` / `Avoid` / `Pending Verification`)
- open-issue status table (`Cross-round carryover` / `Pending`)
- next-round strategy

Status enum:
`Keep` (effective in the previous round, continue using it) |
`Avoid` (tried for >=2 rounds without improvement) |
`Pending Verification` (newly introduced) |
`Newly discovered` |
`Fixed` |
`Pending` |
`Cross-round carryover`
