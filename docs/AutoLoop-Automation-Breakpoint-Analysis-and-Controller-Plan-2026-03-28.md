# AutoLoop Automated Breakpoint Analysis and Controller Plan

**Date**: 2026-03-28  
**Document status (2026-03-29)**: Some of the breakpoints below have already been implemented or partially implemented by `autoloop-controller.py`; do not treat this document as a complete list of current gaps. **Examples already converged in code**: the main loop and 8-stage orchestration exist; **B26 oscillation** and **B32 max_rounds** already have logic in EVOLVE / ORIENT (see `scripts/autoloop-controller.py`). **Typical items still open**: B11 (DECIDE strategy rules still lean LLM-heavy), B28 (side_effect strict validation is still incremental in validate), B37 (some pause semantics are now covered by T3 OBSERVE / EVOLVE pause, not equivalent to the full document). This document is kept as an archival diagnosis; use the repository scripts and `docs/backlog-experience-v2.md` for current planning.

**Basis**: T3 iteration R11 (5.8/10) + end-to-end execution trace  
**Core diagnosis**: AutoLoop is currently a "playbook" (protocol), not an "automation engine"

---

## Core Problem

AutoLoop claims to be an autonomous iteration engine, but in actual execution **every stage transition depends on the LLM remembering to read markdown and decide the next step**. There is no loop controller that drives the OODA 8-stage progression automatically.

The 40 breakpoints are grouped into three layers:

---

## Layer 1: The Loop Engine Does Not Exist (5 key breakpoints)

This is the most fundamental issue - **there is no automatic progression mechanism**. Every transition between stages is effectively "the LLM should know what to do next."

### B1: No mode selection at the entry point

**Location**: `/autoloop` → `autoloop.md` → `autoloop-plan.md`

**Issue**: after the user calls `/autoloop`, the system does not automatically decide whether to use JSON SSOT mode or markdown flat-file mode.
- `autoloop-init.py` creates 4 markdown files
- `autoloop-state.py init` creates `autoloop-state.json`
- **Neither is invoked automatically**; it depends on which protocol fragment the LLM reads

**Impact**: the flow splits into two uncertain paths from the first step.

**Fix direction**: the controller should choose the mode automatically at startup, with JSON SSOT as the default.

---

### B4: VERIFY has no automatic scoring

**Location**: after ACT completes → VERIFY stage

**Issue**: `autoloop-score.py` exists and supports multi-template scoring for T1-T7, but:
- there is no hook that calls it automatically
- no command flow requires it
- the LLM must remember to call the scorer or delegate scoring to a subagent

**Impact**: VERIFY scoring may be skipped or estimated manually, making gate decisions unreliable.

**Fix direction**: the controller should automatically call `autoloop-score.py <work_dir>` after ACT and feed the result into VERIFY.

---

### B8: EVOLVE→REFLECT→OBSERVE does not advance automatically

**Location**: end of one round → start of next round

**Issue**: after REFLECT writes to findings.md, the system enters a "waiting state" - there is no mechanism that automatically:
1. decides whether to continue (consumes the EVOLVE termination decision)
2. advances to the next round (calls `add-iteration`)
3. starts the next round's OBSERVE (reads the previous REFLECT output)

**Impact**: multi-round iteration depends on the LLM remembering "what to do now", which is fragile after context compression.

**Fix direction**: the controller should own the round counter and automatically evaluate the termination criteria after REFLECT; if the task is not complete, advance to the next round.

---

### B13: No breakpoint recovery

**Location**: session interruption (context exhaustion, user closes the window, network disconnect)

**Issue**: if the session ends in the middle of the loop:
- markdown mode: the 4 files exist, but there is no checkpoint marker, so the LLM does not know where it stopped
- SSOT mode: JSON has a phase field, but there is no resume protocol
- neither mode has an automatic "resume from round N / stage X" mechanism

**Impact**: each interruption requires the user to tell the LLM the current state, which wastes time and invites errors.

**Fix direction**: maintain `checkpoint.json` (`current_round`, `current_phase`, `last_completed_phase`, `timestamp`) and have new sessions read it automatically to resume.

---

### B16: No automatic connection from plan to execution

**Location**: after `autoloop-plan.md` is created → first execution round

**Issue**: after plan creation, `autoloop.md` says "enter the first execution round", but:
- there is no code that automatically calls the corresponding template command (for example `/autoloop:research`)
- the plan guide says "start automatically in 5 seconds", but that is only a prompt to the LLM, not a timer
- there is no deterministic connection between bootstrap file creation and execution start

**Impact**: plan creation may stall until the user manually triggers execution.

**Fix direction**: the controller should automatically enter Round 1 OBSERVE after bootstrap finishes.

---

## Layer 2: Toolchain Breaks (7 breakpoints)

The scripts exist, but they are "passive tools" - they need someone to call them. There is no active orchestrator that invokes them in order.

### B2: Bootstrap does not read templates

**Location**: `autoloop-init.py` creates 4 files

**Issue**: init.py creates only a bare skeleton and does not reference:
- `findings-template.md` (full issue tracking table, strategy evaluation table, 4-layer reflection structure)
- `progress-template.md` (8-stage loop record template)
- `quality-gates.md` (template-specific gate thresholds)

**Impact**: the generated files lack structure, so the LLM must read the templates separately and fill them manually.

**Fix direction**: have the controller call an enhanced init that automatically reads the templates and gate definitions to generate a structured bootstrap set.

---

### B3: SSOT mode has no automatic render

**Location**: when `autoloop-state.json` exists

**Issue**: in SSOT mode, `autoloop-render.py` must generate the 4 markdown views for the LLM to read. However:
- there is no mechanism that automatically calls render after `state.json` changes
- if JSON is updated but not rendered, markdown and JSON drift apart
- there is no automatic decision about which representation is authoritative

**Impact**: JSON and markdown drift, causing cross-file validation failures.

**Fix direction**: after every state.json write, the controller should automatically call `render.py` so the markdown views remain derived from JSON.

---

### B9: The experience registry has no write-back

**Location**: REFLECT stage → `experience-registry.md`

**Issue**: all 7 command files say "Experience write-back: write this round's strategy effect to experience-registry.md", but:
- that line is only a markdown instruction
- there is no script that performs the write
- there is no hook that appends the data after REFLECT
- the strategy effect table in experience-registry.md is still empty ("initially empty, filled as tasks run")

**Impact**: cross-task learning effectively does not exist. The self-evolution dimension has a low ceiling.

**Fix direction**: the controller should automatically extract strategy-effect data during REFLECT and call a dedicated tool to write to the experience registry.

---

### B10: The experience registry has no read path

**Location**: OBSERVE Step 0 → `experience-registry.md`

**Issue**: loop-protocol.md says "you must also read experience-registry.md", and the 7 command files all have an "experience registry read" step, but:
- there is no script that parses experience-registry.md and outputs recommended strategies
- there is no structured "recommended strategy list" passed to DECIDE
- the LLM must manually open the file, find relevant entries, and decide whether they apply

**Impact**: even if the registry has data (after fixing B9), it still cannot be consumed automatically.

**Fix direction**: during OBSERVE, the controller should automatically query the registry, filter by template + context_tags, and output `recommended_strategies.json`.

---

### B19: Gate thresholds are not auto-filled into the plan

**Location**: `autoloop-init.py` creates `autoloop-plan.md`

**Issue**: the quality-gate table in plan.md starts as empty (`—` placeholders), even though quality-gates.md already defines all gate thresholds for every template. init.py does not read quality-gates.md to populate it.

**Impact**: the LLM must manually read quality-gates.md and fill in the plan, which is easy to get wrong or omit.

**Fix direction**: during bootstrap, the controller should extract thresholds from the scorer's gate definitions based on template type and inject them into the plan.

---

### B34: Final report is not generated automatically

**Location**: after loop termination

**Issue**: `report-template.md` and `audit-template.md` define the final report format, but:
- there is no `autoloop-finalize.py` tool to fill the template
- nothing automatically generates the report when EVOLVE decides to stop
- the LLM has to manually read templates, findings/progress/results, and assemble the report

**Impact**: the post-termination artifact depends on manual LLM assembly and is therefore inconsistent.

**Fix direction**: on termination, the controller should call a finalize tool that builds the full report from state.json.

---

### B35: TSV rows are not appended automatically

**Location**: ACT / VERIFY stage → `autoloop-results.tsv`

**Issue**: `autoloop-state.py add-tsv-row` exists, but:
- no command file calls it
- VERIFY results are not automatically written to TSV
- the TSV file only has a header row after bootstrap and is never appended

**Impact**: results.tsv stays empty or incomplete, so the structured iteration log is unusable.

**Fix direction**: after VERIFY scoring completes, the controller should automatically construct and append the TSV row.

---

## Layer 3: Missing Validation and Guard Rails (5 key breakpoints)

The protocol declares rules, but the code does not enforce them.

### B11: DECIDE does not enforce strategy-selection rules

**Location**: DECIDE strategy selection

**Issue**: loop-protocol.md says:
- strategies marked "avoid" should not be reused
- strategies marked "keep" should be preferred
- but DECIDE has no validation that checks strategy history

**Impact**: the same failed strategy can be tried repeatedly, wasting rounds.

**Fix direction**: before DECIDE, the controller should read historical strategy evaluations and automatically filter "avoid" strategies and promote "keep" strategies.

---

### B26: Oscillation detection is not implemented

**Location**: EVOLVE termination decision

**Issue**: loop-protocol.md defines oscillation detection (a dimension fluctuates by ±0.5 for 3 consecutive rounds), but:
- there is no code that implements the detection
- the EVOLVE decision tree has no oscillation branch
- `autoloop-variance.py` exists but only handles single-round variance, not cross-round oscillation

**Impact**: the system can bounce between two strategies without converging.

**Fix direction**: during EVOLVE, the controller should automatically compute recent score trends and detect oscillation patterns.

---

### B28: side_effect is not validated

**Location**: VERIFY stage → `results.tsv` `side_effect` column

**Issue**: loop-protocol.md says "do not fill 'none' without verification", but:
- the `side_effect` column in results.tsv accepts any string
- no validator checks whether the affected dimensions were actually evaluated
- the LLM can write "none" to skip side-effect checks

**Impact**: strategy side effects can be ignored, so one dimension may improve while another worsens.

**Fix direction**: during VERIFY, the controller should run gate checks for all affected dimensions and auto-fill `side_effect` from the evaluation result.

---

### B32: Maximum rounds are not enforced

**Location**: EVOLVE termination decision

**Issue**: plan.md defines `max_rounds`, but:
- no code checks whether the current round has reached the limit during EVOLVE
- the LLM can ignore the budget and continue
- `autoloop-state.py` has `budget.max_rounds`, but there is no enforcement

**Impact**: the system may loop forever and consume resources indefinitely.

**Fix direction**: in EVOLVE, the controller should check `current_round >= max_rounds` and terminate when the limit is reached.

---

### B37: Pause confirmation is not implemented

**Location**: hard gate failure → should pause and wait for user confirmation

**Issue**: quality-gates.md says hard-gate failures should pause (for example T5 Phase 0.5 and Phase 5), but:
- no code creates a pause checkpoint when a hard gate fails
- there is no "wait for user input" mechanism
- the LLM may skip the pause and continue

**Impact**: critical decision points that require human judgment can be skipped automatically.

**Fix direction**: when a hard gate fails, the controller should write `pause_checkpoint.json` and wait for a user confirmation signal before continuing.
