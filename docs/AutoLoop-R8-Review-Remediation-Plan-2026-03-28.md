# AutoLoop R8 Review Repair Plan

**Date**: 2026-03-28  
**Document status (2026-03-29)**: Several F* items were implemented in later iterations (scorers, state machine, SSOT thresholds, and so on). **L4 (`commands/autoloop-quality.md` hard-coded thresholds)**: that command document now points to **`references/quality-gates.md` and `gate-manifest.json`**. Use the repository state as the source of truth and do not rely on the legacy table below. The content here is kept as an archival repair plan.

**Basis**: Codex R8 six-dimension methodology review (3.7/10) + Claude verification pass (4.4/10)  
**Goal**: eliminate the "statement-execution gap" and raise the corrected score from 4.4 to 6.5+

---

## Repair Priority Overview

| # | Category | Issue | Priority | Impacted dimension |
|---|----------|-------|----------|--------------------|
| F1 | Real bug | Scorer and renderer formats are incompatible | P0 | Measurement validity |
| F2 | Real bug | add-finding silently drops data when there is no iteration | P0 | Closed-loop behavior |
| F3 | Typo | autoloop.md TSV "13 columns" → "15 columns" | P0 | Measurement consistency |
| F4 | Protocol fill-in | Gate classification overview (hard / soft matrix) | P1 | Gate discriminative power |
| F5 | Protocol fill-in | Experience registry consumption embedded into command-layer OBSERVE | P1 | Closed-loop behavior + self-evolution |
| F6 | Protocol fill-in | Clarify stage-transition constraints | P1 | Convergence performance |
| F7 | Protocol fill-in | Wire template-specific stagnation thresholds into EVOLVE | P1 | Convergence performance |
| F8 | Definition alignment | Unify version semantics | P2 | Self-evolution |
| F9 | Definition alignment | Precisely define "single-strategy isolation" | P2 | Task-model fit |
| F10 | Framework alignment | Unify governance across evolution-rules + loop-protocol | P2 | Self-evolution |
| F11 | Protocol fill-in | Add T5 migration_check_cmd contract | P2 | Task-model fit |
| F12 | Protocol fill-in | Deduplicate T6 report artifacts | P2 | Task-model fit |

---

## P0: Real Bug Fixes (3 items)

### F1: Scorer and renderer format mismatch

**Issue**: `autoloop-score.py` expects `## Dimension` plus inline `source` bullets, while `autoloop-render.py` emits `## Round N Findings` + `### Dimension [confidence]` + separate `Source:` lines. The scorer systematically under-scores the renderer output.

**Fix**: Align the scorer to the renderer format (the renderer is the SSOT output side, so the scorer should adapt to it).

**Files**: `scripts/autoloop-score.py`
- Section splitting: change from `re.split(r'\n##\s+', content)` to a parser that recognizes both `##` and `###`
- Dimension extraction: parse from `### Dimension name [confidence]`
- Source detection: recognize separate `Source:` lines in addition to inline `source`
- Bullet counting: count paragraphs under `###` sections, not only `- ` bullets

**Validation**: generate a sample findings file with `autoloop-render.py` → feed it to the updated scorer → confirm the score is non-zero

---

### F2: add-finding silently drops data when there is no iteration

**Issue**: In `autoloop-state.py`, `add-finding` skips the iteration update when `state["iterations"]` is empty. It writes to `findings.rounds` but not to `iterations[].findings`, while still printing "OK".

**Fix**: raise an error when there is no iteration instead of silently skipping.

**Files**: `scripts/autoloop-state.py`
- Add an early guard near the start of `cmd_add_finding`:
  ```python
  if not state["iterations"]:
      print("ERROR: no iteration exists yet; run add-iteration first")
      sys.exit(1)
  ```

**Validation**: call `add-finding` without iterations and confirm that it fails

---

### F3: autoloop.md TSV column typo

**Issue**: `commands/autoloop.md:120` says "write a 13-column header row", but the schema (`loop-protocol.md` + `SKILL.md`) defines 15 columns.

**Fix**: update the number directly.

**Files**: `commands/autoloop.md`
- Change "13 columns" to "15 columns"

**Validation**: grep the whole repo and confirm no other "13 columns" references remain

---

## P1: Protocol Fill-In (4 items)

### F4: Gate classification overview (hard / soft matrix)

**Issue**: hard / soft gates are intentionally designed, but there is no unified overview, so Codex can misread them as contradictions.

**Fix**: add a unified gate-classification matrix at the top of `quality-gates.md`.

**Files**: `protocols/quality-gates.md`
- Add a `## Gate Classification Overview` section after the common scoring rules
- Include a full matrix:

```markdown
## Gate Classification Overview

### Definitions
- **Hard Gate**: failure means the round fails and must be fixed before continuing
- **Soft Gate**: failure is recorded in progress.md + findings.md but does not block termination decisions

### Full template × full dimension matrix

| Template | Dimension | Threshold | Gate type | Failure behavior |
|------|------|------|---------|---------|
| T1 Research | Coverage | ≥85% | Hard | Round fails |
| T1 Research | Confidence | ≥80% | Hard | Round fails |
| T1 Research | Consistency | ≥90% | Soft | Record + continue |
| T1 Research | Completeness | ≥85% | Soft | Record + continue |
| T2 Compare | Coverage | 100% | Hard | Round fails |
| T2 Compare | Confidence | ≥80% | Hard | Round fails |
| T2 Compare | Bias check | ... | Hard | Round fails |
| T2 Compare | Sensitivity analysis | ... | Soft | Record + continue |
| T6 Quality | Security score | ≥9 | Hard | Round fails |
| T6 Quality | P1 defect count | =0 | Hard | Round fails |
| T6 Quality | Security P2 | =0 | Hard | Round fails |
| T6 Quality | Reliability P2 | ≤3 | Soft | Record + continue |
| T6 Quality | Maintainability P2 | ≤5 | Soft | Record + continue |
| ... | ... | ... | ... | ... |
```

- In the T6 "single source of truth" section, mark each condition as hard or soft immediately so readers do not need to jump 50 lines to find the classification

**Validation**: every row in the matrix must match the later detailed thresholds, with no omissions

---

### F5: Embed experience registry reads into command-layer OBSERVE

**Issue**: `SKILL.md:35` says "OBSERVE reads recommended strategies, REFLECT writes experience", but only the pipeline writes to the experience registry; the other seven templates only read `findings.md`.

**Fix**: make the experience registry read/write responsibilities explicit in OBSERVE and REFLECT for every template command.

**Files** (7 command files):

In each command's **OBSERVE Step 0** (from round 2 onward), add:
```markdown
**Step 0.1**: Read relevant entries from `protocols/experience-registry.md`
- Retrieve strategies that match the current task type (T{N}) and target dimensions
- Identify strategies marked as `recommended` or `candidate default`
- Pass the recommended strategy list into DECIDE as reference material
```

In each command's **REFLECT** step, add:
```markdown
**Experience write-back**: write this round's strategy effect to `protocols/experience-registry.md`
- strategy ID, applicable scenario, effect score, execution context
- follow the format of the effect-recording table in experience-registry.md
```

**Files involved**:
- `commands/autoloop-research.md` - T1
- `commands/autoloop-compare.md` - T2
- `commands/autoloop-iterate.md` - T3
- `commands/autoloop-generate.md` - T4
- `commands/autoloop-deliver.md` - T5
- `commands/autoloop-quality.md` - T6
- `commands/autoloop-optimize.md` - T7

**Validation**: grep the repo for `experience-registry` and confirm all 7 commands reference it for both read and write

---

### F6: Make stage-transition constraints explicit

**Issue**: the 8-stage sequence is defined in `loop-protocol.md:210-226`, but the `update` command in state.py does not validate semantics and does not reference the transition rules.

**Fix**: two-layer repair - protocol-level definition plus script-level enforcement

**A) Protocol layer** (`protocols/loop-protocol.md`):
- Add a `### Stage Transition Constraints` subsection after the stage definitions:

```markdown
### Stage Transition Constraints

Legal transitions (strict order, no skipping, no reversing):

| Current stage | Legal next stage | Constraint |
|---------|------------|------|
| OBSERVE | ORIENT | — |
| ORIENT | DECIDE | — |
| DECIDE | ACT | decision is locked and cannot be rolled back |
| ACT | VERIFY | — |
| VERIFY | SYNTHESIZE | — |
| SYNTHESIZE | EVOLVE | — |
| EVOLVE | REFLECT | — |
| REFLECT | OBSERVE (next round) / Completed | termination must satisfy conditions |

**Irreversibility rule**: once ACT starts, the DECIDE choice cannot be modified. If a strategy change is needed, finish the current round and adjust in the next round's DECIDE.
```

**B) Script layer** (`scripts/autoloop-state.py`):
- Add a `PHASES` constant and transition validation:

```python
PHASES = ["OBSERVE", "ORIENT", "DECIDE", "ACT", "VERIFY", "SYNTHESIZE", "EVOLVE", "REFLECT"]

def validate_phase_transition(current, target):
    """Validate a legal phase transition (see loop-protocol.md stage-transition constraints)."""
    if current not in PHASES or target not in PHASES:
        return False, f"unknown phase: {current} → {target}"
    ci, ti = PHASES.index(current), PHASES.index(target)
    if ti == ci + 1:
        return True, ""
    if target == "OBSERVE" and current == "REFLECT":
        return True, "entering next round"
    return False, f"illegal transition: {current} → {target} (must advance in order)"
```

- Call the validation from `cmd_update` when the updated path includes `phase`

**Validation**: try jumping directly from OBSERVE to ACT and confirm that it fails

---

### F7: Wire template-specific stagnation thresholds into EVOLVE

**Issue**: `parameters.md` defines stagnation thresholds for T3 (<2%)/T6 (<0.3)/T7 (<0.5), but loop-protocol EVOLVE still uses the generic 3% rule.

**Fix**: reference the template-specific thresholds from `parameters.md` in the EVOLVE decision tree.

**Files**: `protocols/loop-protocol.md`
- In the EVOLVE termination decision section, replace the generic rule:

From:
```text
all dimensions improve by less than relative 3%
```

To:
```text
all dimensions improve by less than the template stagnation threshold (see parameters.md §Iteration control parameters):
- T1/T2: < relative 3% (generic default)
- T3: < relative 2% (precise KPI convergence)
- T6: < absolute 0.3 points (engineering quality)
- T7: < absolute 0.5 points (system optimization)
- T4/T5: not applicable (T4 retries per unit, T5 advances per stage)
```

**Validation**: the threshold reference in loop-protocol EVOLVE must exactly match `parameters.md`

---

## P2: Semantics Alignment and Framework Fill-In (5 items)

### F8: Unify version semantics

**Issue**: patch-version semantics are inconsistent - loop-protocol defines them as "anchor / sample / experience", but evolution-rules also use patch for formal rule upgrades and rollbacks.

**Fix**: establish a single authoritative version definition in `protocols/loop-protocol.md`.

**Files**: `protocols/loop-protocol.md` (version-definition section)
- Redefine the three version levels:

```markdown
### Version Semantics (single source of truth)

| Level | Trigger | Example | Direction |
|------|---------|------|------|
| major (X.0.0) | structural loop changes | add/remove stages, change stage order | increment only |
| minor (0.X.0) | gate / dimension / parameter changes | add a scoring dimension, change thresholds, adjust weights | increment only |
| patch (0.0.X) | calibration-data changes | anchor samples, strategy experience, scoring calibration | increment only |

**No-decrement rule**: rollback is implemented by increasing the version number (for example, 1.2.3 rollback → 1.3.0), never by decrementing.
```

---

### F9: Define "single-strategy isolation" precisely

**Issue**: "single-strategy isolation" is used loosely, leading people to misread multi-subagent analysis as a violation.

**Fix**: define it as a decision rule rather than an execution rule.

**Files**: `protocols/loop-protocol.md`
- Add a precise statement near the DECIDE section:
  - Each DECIDE round selects one primary strategy for the round's causal hypothesis
  - Multiple subagents may still be used to gather evidence, but they must converge on a single decision anchor
  - If the evidence conflicts, record the conflict and defer to the most conservative conclusion

**Validation**: the definition must match how the command-layer templates and controller actually schedule work

---

### F10: Unify governance across evolution-rules + loop-protocol

**Issue**: loop-protocol and evolution-rules govern protocol changes in different ways, which makes rollback and upgrade semantics drift.

**Fix**: add a single governance layer and make both docs reference it.

**Files**: `protocols/loop-protocol.md`, `protocols/evolution-rules.md`
- Clarify which changes require user confirmation, which can be auto-applied, and which are blocked
- Make patch / minor / major upgrade and rollback behavior match the unified version semantics

**Validation**: the two documents must no longer describe conflicting rollback behavior

---

### F11: Complete the T5 migration_check_cmd contract

**Issue**: T5 delivery requires `migration_check_cmd`, but the plan template's T5 parameter block does not collect it.

**Fix**: add the missing contract field to the T5 section in the plan template.

**Files**: `assets/plan-template.md`, `assets/delivery-template.md`
- Ensure T5 captures `migration_check_cmd`
- Ensure delivery and acceptance steps reference it consistently

**Validation**: the parameter must appear in the plan, in the delivery plan, and in the verification checklist

---

### F12: Deduplicate T6 report artifacts

**Issue**: T6 uses both a generic report template and a separate audit template, which creates duplicate final artifacts with unclear authority.

**Fix**: define a single authoritative output and make the other one a subordinate artifact or an appendix.

**Files**: `assets/report-template.md`, `assets/audit-template.md`
- Decide which file is the primary T6 final deliverable
- Make the other file clearly subordinate or optional

**Validation**: the final artifact ownership must be unambiguous

---

## Expected Outcome

If all F1-F12 are implemented, the plan should eliminate the major measurement mismatches, close the command-layer loop, and bring the protocol documentation into a more coherent SSOT-aligned state.
