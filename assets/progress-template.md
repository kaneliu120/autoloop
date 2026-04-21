# AutoLoop Progress — Iteration Progress Tracker

**Task ID**: autoloop-{YYYYMMDD-HHMMSS}
**Template**: T{N}: {Name}
**Start time**: {ISO 8601}
**Current status**: In progress

---

## Quality Gate Overview

| Dimension | Baseline | Round 1 | Round 2 | Round 3 | Target |
|-----------|----------|---------|---------|---------|--------|
| {dimension 1} | — | — | — | — | ≥ {threshold} |
| {dimension 2} | — | — | — | — | ≥ {threshold} |
| {dimension 3} | — | — | — | — | ≥ {threshold} |

---

## Baseline Record (Round 0, before any changes)

**Measurement time**: {time}
**Measurement results**:

| Dimension | Baseline value | Measurement method |
|-----------|----------------|--------------------|
| {dimension 1} | {value} | {command / method} |
| {dimension 2} | {value} | {command / method} |

**Initial state summary**: {describe the current situation and identify the main issues}

---

## Iteration Round #1

**Start time**: {ISO 8601}
**Status**: In progress / Completed

### OBSERVE

Current gaps:
| Dimension | Current value | Target value | Gap |
|-----------|---------------|--------------|-----|
| {dimension 1} | {current} | {target} | {gap} |

Remaining budget: {X}% (0 rounds used / max {N} rounds)
Observation focus for this round: {most important dimension to address}

### ORIENT

Main reason for the gap: {analysis}
Strategy for this round: {strategy name + explanation}
Scope adjustment: {none / expand / narrow + reason}
Expected improvement: {how much improvement is expected}

### DECIDE

Actions for this round:

| # | Action | Owner | Input | Expected output | Parallel? |
|---|--------|-------|-------|-----------------|-----------|
| 1 | {action 1} | {agent} | {file / information} | {output} | — |
| 2 | {action 2} | {agent} | {file / information} | {output} | Parallel with 3 |
| 3 | {action 3} | {agent} | {file / information} | {output} | Parallel with 2 |

Execution order: {explain parallel / serial relationships}

### ACT

| # | Owner | Task | Start time | End time | Status | Result summary |
|---|-------|------|------------|----------|--------|----------------|
| 1 | researcher | {task} | {time} | {time} | passed / failed | {summary} |
| 2 | code-reviewer | {task} | {time} | {time} | passed / failed | found {N} issues |

Failure log, if any:
- {action #N}: failure reason {reason}, fallback strategy: {strategy}, result: {passed / failed}

### VERIFY

Score updates:
| Dimension | Previous round | This round | Change | Status |
|-----------|----------------|------------|--------|--------|
| {dimension 1} | {previous} | {this round} | {+/−} | Met / Not met |

Verification method: {specific command or check method}

New issues introduced this round:
- {issue} (to be handled next round)

### SYNTHESIZE

Conflicts identified:
- {conflict 1}: {subagent A said X, subagent B said Y, explanation of the conflict}
- No conflicts (fill this in if none)

Conflicts resolved:
- {conflict 1}: {resolution, e.g. use the more conservative conclusion / run a third verification / choose the smaller change}

Merged data:
- `autoloop-findings.md`: appended {N} findings (round {N})
- `autoloop-results.tsv`: updated {N} records (if any)
- {other updated file}: {explanation}

New insights (visible only after synthesis):
- {insight 1}: {pattern or rule discovered by combining subagent outputs}
- None (fill this in if none)

### EVOLVE

Termination decision: continue / quality met / budget exhausted / user interrupted / cannot continue

If continuing:
- Next round focus: {dimension}
- Strategy adjustment: {none / switch strategy (attempted: {old strategy}, new strategy: {new strategy})}
- Scope change: {none / expand {new dimension} / narrow {reduce {dimension} requirement}}

### REFLECT

- **Issue log**: {newly discovered N, fixed M, remaining K}
- **Strategy review**: {this round's strategy} - effect score {1-5}/5, {keep | avoid | to verify} (see the canonical status enum in references/loop-data-schema.md)
- **Pattern recognition**: {new pattern / no new pattern}
- **Lesson learned**: {the most important lesson from this round}
- **Guidance for next round**: {what to focus on and what to avoid based on reflection}

**End time**: {ISO 8601}
**Round duration**: {N} minutes

---

## Iteration Round #2

**Start time**: {ISO 8601}
**Status**: In progress / Completed

> Note: every later iteration round must include the full 8-stage structure, exactly matching round #1, with no omissions or merges. The block below is a placeholder for round 2; copy it and fill in all fields.

### OBSERVE

> Note: starting from round 2, you must first read the previous round's REFLECT record in `autoloop-findings.md`, and use the remaining issues, effective strategies, and recognized patterns as inputs to this round's observation.

Current gaps:
| Dimension | Current value | Target value | Gap |
|-----------|---------------|--------------|-----|
| {dimension 1} | {current} | {target} | {gap} |

Remaining budget: {X}% (1 round used / max {N} rounds)
Observation focus for this round: {most important dimension to address}
Carryover from last round: {remaining issues, or "none"}

### ORIENT

Main reason for the gap: {analysis}
Strategy for this round: {strategy name + explanation}
Scope adjustment: {none / expand / narrow + reason}
Expected improvement: {how much improvement is expected}

### DECIDE

Actions for this round:

| # | Action | Owner | Input | Expected output | Parallel? |
|---|--------|-------|-------|-----------------|-----------|
| 1 | {action 1} | {agent} | {file / information} | {output} | — |
| 2 | {action 2} | {agent} | {file / information} | {output} | Parallel with 3 |
| 3 | {action 3} | {agent} | {file / information} | {output} | Parallel with 2 |

Execution order: {explain parallel / serial relationships}

### ACT

| # | Owner | Task | Start time | End time | Status | Result summary |
|---|-------|------|------------|----------|--------|----------------|
| 1 | {agent} | {task} | {time} | {time} | passed / failed | {summary} |

Failure log, if any:
- {action #N}: failure reason {reason}, fallback strategy: {strategy}, result: {passed / failed}

### VERIFY

Score updates:
| Dimension | Previous round | This round | Change | Status |
|-----------|----------------|------------|--------|--------|
| {dimension 1} | {previous} | {this round} | {+/−} | Met / Not met |

Verification method: {specific command or check method}

New issues introduced this round:
- {issue} (to be handled next round)

### SYNTHESIZE

Conflicts identified:
- {conflict 1}: {explanation}
- No conflicts (fill this in if none)

Conflicts resolved:
- {conflict 1}: {resolution}

Merged data:
- `autoloop-findings.md`: appended {N} findings (round 2)
- `autoloop-results.tsv`: updated {N} records (if any)
- {other updated file}: {explanation}

New insights (visible only after synthesis):
- {insight 1}: {explanation}
- None (fill this in if none)

### EVOLVE

Termination decision: continue / quality met / budget exhausted / user interrupted / cannot continue

If continuing:
- Next round focus: {dimension}
- Strategy adjustment: {none / switch strategy (attempted: {old strategy}, new strategy: {new strategy})}
- Scope change: {none / expand {new dimension} / narrow {reduce {dimension} requirement}}

### REFLECT

- **Issue log**: {newly discovered N, fixed M, remaining K}
- **Strategy review**: {this round's strategy} - effect score {1-5}/5, {keep | avoid | to verify} (see the canonical status enum in references/loop-data-schema.md)
- **Pattern recognition**: {new pattern / no new pattern}
- **Lesson learned**: {the most important lesson from this round}
- **Guidance for next round**: {what to focus on and what to avoid based on reflection}

**End time**: {ISO 8601}
**Round duration**: {N} minutes

> Tip: continue appending later rounds in this full format (#3, #4, ...), incrementing the round number each time. All 8 stages must be filled in completely, with nothing omitted.

---

## Task Completion Record

**End time**: {ISO 8601}
**Termination reason**: {quality met / budget exhausted / user interrupted / cannot continue}
**Total duration**: {N} minutes
**Total rounds**: {N}

### Final Scores

| Dimension | Baseline | Final | Target | Improvement | Status |
|-----------|----------|-------|--------|------------|--------|
| {dimension 1} | {baseline} | {final} | {target} | {+/−} | Met / Not met |

### Task Summary

{a paragraph describing what this task did, what it achieved, and what it left behind}

### Output Files

| File | Path | Description |
|------|------|-------------|
| Final report | {path} | {description} |
| Findings log | {path} | {N} findings |

---

## Strategy History

| Round | strategy_id | Dimension | Strategy | Result | Effective? |
|-------|-------------|-----------|----------|--------|------------|
| 1 | S01-{short name} | {dimension} | {strategy} | {result} | Keep / Avoid / To verify (reason: {reason}) |

---

## Issues Encountered and Handling

| Issue | Round | Handling | Result |
|-------|-------|----------|--------|
| {issue description} | {N} | {handling} | {result} |
