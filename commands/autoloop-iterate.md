---
name: autoloop-iterate
description: >
AutoLoop T5: Goal-driven iteration template. Define KPIs and baselines and remeasure after each round of improvements,
Until the KPI is met or the maximum round is reached. Support manual feedback intervention.
Quality gate thresholds are found in references/quality-gates.md, line T5.
Trigger: /autoloop:iterate or any task that requires iterative improvement until it reaches the target.
---

# AutoLoop T5: Iterate — goal-driven iteration

## Prerequisites for execution

Read `autoloop-plan.md` to get:
- KPI definition (must be measurable and have specific values)
- Current baseline (measured before the start of the first round)
- Change scope constraints (only what should be changed, what should not be changed)
-Measurement method (how to re-measure the KPI after each round)
- Maximum rounds

If the KPI is not clearly defined ("better quality" rather than "error rate < 0.5%"), help users quantify it first.

**Round 2+ OBSERVE starting point**: First read the `autoloop-findings.md` reflection chapter to obtain remaining issues, effective/ineffective strategies, identified patterns, lessons learned, and then scan the current status. See the `references/loop-protocol.md` OBSERVE Step 0 chapter for details.

- **Experience database reading**: Read entries in `references/experience-registry.md` that match the current task type and target dimensions, identify strategies with status "recommended" or "candidate default", and pass them to the DECIDE stage for reference

---

## KPI Quantitative Rules

Example of conversion from fuzzy KPI to specific KPI:

| Fuzzy description | Quantitative KPI (sample format, specific values ​​are defined by the user in the plan) |
|---------|---------|
| "faster" | API P95 latency < {N}ms (range: 100-2000) |
| "Better quality" | test coverage ≥ {N}% (range: 60-100) + py_compile zero errors |
| "Reduce Errors" | Number of exception logs decreased > {N}% (range: 50-99) |
| "Code cleaner" | Average number of lines of functions < {N} (range: 20-50) + no TODO comments |
| "Better user experience" | Time above first screen < {N}s (range: 1-5) + Lighthouse score ≥ {N} (range: 60-100) |

---

## Step 0: Baseline measurement (only performed once)

Before any changes, measure the current state and write it in the "baseline" part of `autoloop-progress.md` (see the `references/loop-protocol.md` round 1 Bootstrap rule for the format):

```
Baseline Measurement Report:

KPI indicator: __ TOK0 __
Measurement method: __ TOK0 __
Current value: __ TOK0 __
Target value: __ TOK0 __
Gap: __ TOK0 __
Estimation of difficulty of reaching the standard: __ TOK0 __ (based on gaps and known room for improvement)
```

---

## Execution process for each round

### OBSERVE: Gap Analysis

```
Read the reflection chapter of autoloop-findings.md (required for Round 2+)
Capture legacy issues, effective/ineffective strategies, identified patterns, lessons learned
(For the specification of Step 0, please see the OBSERVE Step 0 chapter in references/loop-protocol.md)

Current KPI: __ TOK0 __/Target: __ TOK1 __/Gap: __ TOK2 __
Consumed rounds: __ TOK0 __/__ TOK1 __
Available budget for this round: sufficient / limited / urgent

Key observations:
- __ TOK0 __
- __ TOK0 __
- __ TOK0 __
```

### ORIENT: Improving Strategy Development

Choose a strategy based on gap type:

**Gap > 50% (still far away)**:
- Strategy: Look for "big moves" (architectural changes, algorithm replacement, fundamental refactoring)
- Don’t waste time on small optimizations

**Gap 20-50% (progress but not enough)**:
- Strategy: Combine multiple medium improvements (optimize hotspot paths one by one)
- Use profiling/analysis tools to find bottlenecks

**Gap < 20% (close to target)**:
- Strategy: Fine tuning (parameter adjustment, caching strategy, concurrency adjustment)
- Be aware of diminishing returns

**2 consecutive rounds of improvement below the stagnation threshold (see references/parameters.md improvement_threshold for stagnation threshold)**:
- The current method has reached its limit and must be changed.
- Consider: scaling, changing architecture, redefining KPIs (whether the right things are being measured)

### DECIDE: Action plan for this round

```
Action plan for this round:
1. __ TOK0 __ (expected improvement: __ TOK1 __)
Executor: __ TOK0 __
File: __ TOK0 __

2. __ TOK0 __ (expected improvement: __ TOK1 __)
Executor: __ TOK0 __
File: __ TOK0 __

Independence analysis:
- Action 1 and Action 2 independent? __ TOK0 __
- If not, execution order: __ TOK0 __
```

See `references/agent-dispatch.md` for parallel/serial judgment rules.

### ACT: Implementation improvements

- **Work order generation**: Generate a delegation work order according to the corresponding role template of `references/agent-dispatch.md`, fill in the task goal, input data, output format, quality standard, scope limit, current round, and context summary

Assign subagent execution improvements (see `references/agent-dispatch.md` for scheduling specifications). Each subagent must receive:

```
You are the __ TOK0 __ subagent and are responsible for the following improvement tasks:

Target KPI: __ TOK0 __ reduced from __ TOK1 __ to __ TOK2 __

This improvement task:
__ TOK0 __

Change constraints:
- Can be modified: __ TOK0 __
- Unmodifiable: __ TOK0 __
- Remain unchanged: __ TOK0 __

Related files (absolute path):
- __ TOK0 __
- __ TOK0 __

Verification after execution:
- Run: __ TOK0 __
- Expected result: __ TOK0 __

Output:
1. Which files have been modified and what has been changed in each file
2. Screenshot/output of verification results
3. Anticipated impact on KPIs
4. Whether new problems are introduced?
```

### VERIFY: remeasure

For the definition of KPI gate control, see the `references/quality-gates.md` T5 KPI Target chapter.

The VERIFY phase is performed by an independent kpi-evaluator subagent (see the independent scorer chapter in references/agent-dispatch.md for scheduling methods). kpi-evaluator only receives KPI measurement results, not optimization strategy information, and blindly evaluates according to quality-gates.md anchor point.

When scoring, the score, criterion (which anchor range is hit), and evidence (source URL or file line number) must be output at the same time. Ratings that are missing any item are invalid and the dimension is marked as pending inspection.

```
Improved KPI measurements:

Measurement command: __ TOK0 __
Result: __ TOK0 __

contrast:
Before improvement: __ TOK0 __
After this round: __ TOK0 __
Improvements in this round: __ TOK0 __ (__ TOK1 __ %)
Cumulative improvements: __ TOK0 __

Whether the standard is met: __ TOK0 __
If no, remaining gap: __ TOK0 __
```

---

## Manual feedback intervention point

Actively pause and request user feedback under the following circumstances (the state machine enters pause and waits for confirmation, see the `references/loop-protocol.md` state machine chapter):

**Scenario 1: KPI improves but experience deteriorates**

```
Potential issue detected:
KPI __ TOK0 __ improved from __ TOK1 __ to __ TOK2 __ (↑)
But __ TOK0 __ is reduced from __ TOK1 __ to __ TOK2 __ (↓)

Is this an acceptable trade-off? Continue/rollback/adjust target?
```

**Scenario 2: Fundamental problem discovered**

```
Discover fundamental issues that require decision-making:

Question: __ TOK0 __
Impact: __ TOK0 __

Options:
A. Address the underlying issue (estimated to require __ TOK0 __ rounds, impact __ TOK1 __)
B. Continue by bypassing the problem (risky: __ TOK0 __)
C. Redefine KPI targets

You choose?
```

**Case 3: Continuous No Progress**

```
Improvement rate < 5% for consecutive {N} rounds:

Current KPI: __ TOK0 __ (Target: __ TOK1 __)

Possible reasons:
1. __ TOK0 __
2. __ TOK0 __

suggestion:
A. Change strategy (__ TOK0 __)
B. Abandon that direction and try __ TOK0 __
C. Accept the current result ({X}% from the target)

You choose?
```

---

## Rollback mechanism

Record the rollback point in the progress file before each change:

```markdown
### Rollback point {N} (before the start of round {M})

Status snapshot:
- KPI value: __ TOK0 __
- Modified files:
- __ TOK0 __ (git commit: __ TOK1 __)
- __ TOK0 __ (git commit: __ TOK1 __)

Rollback command (including safety check):
# Step 1: Confirm that there are no uncommitted modifications of this round
git status

# Step 2: If there are dirty files, temporarily save them first
git stash # Only executed when git status shows unexpected files

# Step 3: Use git revert to roll back (keep the complete history)
git revert {commit_hash}

# Step 4: Restore the temporary work (if stash is executed in step 2)
git stash pop
```

**Rollback Security Rules**:
- You must first confirm with `git status` that there are only uncommitted modifications of this round.
- When there are dirty files, save them in `git stash` first, and restore them in `git stash pop` after rolling back.
- Use `git revert {commit}` instead of `git checkout -- {file}` to keep full history
- Do not use `git reset --hard` (uncommitted work will be destroyed)

---

## Progress Tracking

Each round adds a complete 8-stage record (OBSERVE/ORIENT/DECIDE/ACT/VERIFY/SYNTHESIZE/EVOLVE/REFLECT) in `autoloop-progress.md`. For the format, see the `references/loop-protocol.md` circular log format chapter. Here is a simplified summary example for T5 Iterate (actual records must contain all 8 stages):

```markdown
# # Round __ TOK0 __ — __ TOK1 __

**KPI Trends**:
Baseline → Round 1 → ... → Current Round
__ TOK0 __ → __ TOK1 __→... → __ TOK2 __

**Operation this round**:
- __ TOK0 __: __ TOK1 __
- __ TOK0 __: __ TOK1 __

* * Improvement * *: __ TOK0 __ → __ TOK1 __ (__ TOK2 __, __ TOK3 __ % improvement)
* * Cumulative improvement * *: __ TOK0 __ → __ TOK1 __ (__ TOK2 __ % improvement)

* * Next Round Strategy * *: __ TOK0 __
```

---

## Each round of REFLECT execution specifications

After each round of EVOLVE judgment, it is executed before entering the next round of OBSERVE. REFLECT must be written to a file and cannot just be done in thinking (see the `references/loop-protocol.md` REFLECT chapter for specifications):

Write a 4-layer reflection structure table (problem registration/strategy review/pattern recognition/lessons learned) written into `autoloop-findings.md`. The format is shown in `assets/findings-template.md`:

- **Problem Registration**: Record the KPI deviations, improvement side effects, and measurement errors found in this round
- **Strategy review**: Evaluation of the effect of this round of improvement strategies - actual improvement vs. expected, maintain | avoid | to be verified (for strategy evaluation enumeration, see references/loop-data-schema.md unified status enumeration)
- **Pattern Recognition**: KPI improvement trajectory trend (linear/exponential/diminishing returns), which type of improvement is most effective
- **Lessons Learned**: New understanding of the target system in this round, which assumptions were verified or overturned
- **Experience write back**: Write the current round of strategy effects into `references/experience-registry.md` (strategy ID, applicable scenarios, effect score, execution context, follow the effect record table format)

---

## Final report

After reaching the KPI or the maximum round, output (for the file name, see the `references/loop-protocol.md` Unified Output File Naming Chapter):

```markdown
# AutoLoop Iterate — Iterate results

## Summary
- KPI: __ TOK0 __
- Baseline: __ TOK0 __
- Final value: __ TOK0 __
- Total improvements: __ TOK0 __ (__ TOK1 __ %)
- Iteration round: {N}
- Goal achieved: {yes/no (__ TOK0 __ vs target __ TOK1 __)}

## Improve trajectories

| Round | KPI Value | Amount of Improvement | Key Actions |
|------|--------|--------|---------|
| baseline | __ TOK0 __ | — | — |
| Round 1 | __ TOK0 __ | __ TOK1 __ | __ TOK2 __ |
| Round N | __ TOK0 __ | __ TOK1 __ | __ TOK2 __ |

## Key improvements

1. __ TOK0 __: Contributed __ TOK1 __ % of the total improvement
2. __ TOK0 __: Contribution __ TOK1 __ %
3. __ TOK0 __:...

## Invalid attempt

Tried the following directions but had no significant results:
- __ TOK0 __: Reason __ TOK1 __

## side effect

Other changes introduced or discovered during the improvement process:
- __ TOK0 __: __ TOK1 __

## Target not reached (if the target is not met)

Distance to target: __ TOK0 __
Suggested continuation path: __ TOK0 __
It is estimated that {N} rounds will be needed
```
