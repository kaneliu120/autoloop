---
name: autoloop-design
description: >
  AutoLoop T3: Product design template. Starting from T1/T2 research conclusions, it produces a confirmed solution document that can be handed directly to T4 for delivery through requirement analysis, solution design, and feasibility review.
  Methodology: JTBD problem framing + RICE prioritization + Shape Up scope control + spec-driven output.
  Quality gate thresholds are in references/gate-manifest.json T3.
  Triggered by /autoloop:design or any task that needs product design / solution documentation.
---

# AutoLoop T3: Design — Product Design

## Execution Prerequisites
Read `autoloop-plan.md` to obtain the task parameters.

For Round 2+, the OBSERVE starting point is to first read the reflection section in `autoloop-findings.md` and `references/experience-registry.md`.

## Phase 1: Requirement Analysis and Extraction

### Goal
Extract structured requirements from T1/T2 outputs and user requirements.

### Methodology
- JTBD framing: When [situation], I want [motivation], so I can [outcome]
- RICE prioritization: Reach × Impact / Confidence / Effort

### Execution

**Parallel subagents**:

planner subagent:
- Read T1 findings and T2 decision recommendations
- Extract core requirements and user pain points
- Generate JTBD definitions
- Rank the requirement list by RICE
- Generate user stories (As a / I want / So that + Given-When-Then acceptance criteria, INVEST standard)
- Define scope boundaries (IN/OUT list)

researcher subagent (if there are information gaps):
- Supplement technical or market information not covered by T1/T2

### Output

- **Problem Restatement**: restate the user's request in one paragraph to confirm understanding. Format:
  - "The problem the user wants to solve is: {...}"
  - "In scope (IN): {...}"
  - "Out of scope (OUT): {...}"
  - "Key assumptions: {...}"

  This restatement must be confirmed by the user before Phase 2 begins. If the planner has questions about the requirements, it should raise them here.
- Problem Statement
- JTBD definition
- Requirement list (RICE-ranked)
- User stories + acceptance criteria
- Scope definition (IN/OUT)

### Phase 1 Gate
- [ ] Problem statement is clear (one paragraph: what problem, for whom, why now, success metric)
- [ ] At least 3 user stories, each with Given-When-Then acceptance criteria
- [ ] Scope boundaries are defined (IN + OUT + rationale)
- [ ] Requirements are prioritized

## Phase 2: Solution Design

### Goal
Create a complete design document that combines the technical and product solution.

### Methodology
- Shape Up scope control: fixed time, variable scope
- Spec-driven output: structured specifications drive implementation

### Execution

**Parallel subagents**:

technical-architect subagent:
- Read the Phase 1 requirement list
- Read the target codebase, if one already exists
- Design the data model
- Design the API schema and routing
- Define the migration strategy
- Assess technical risk

frontend-architect subagent (if frontend is involved):
- Design the component structure
- Define the state management approach
- Define the API call pattern

db-specialist subagent (if database changes are involved):
- Design the data model in detail
- Draft the migration script skeleton
- Assess performance impact

### Optional Phase 2: Competitive Multi-Solution Mode

When the user sets `attempt_mode: true` in autoloop-plan.md, Phase 2 enters competitive mode:

1. **Parallel dispatch**: start 2-3 technical-architect subagents, each designing an independent solution
   - Each subagent receives the same requirement input (Phase 1 output)
   - Each subagent works independently and cannot see the others
   - Use `isolation: "worktree"` to keep files isolated

2. **Scoring and selection**: after all solutions finish, the VERIFY stage scores each solution independently
   - Score using the 5 T3 quality gate dimensions
   - Select the highest-scoring solution to enter Phase 3

3. **Record alternatives**: summarize the unselected solutions in findings.md as references

**Notes**:

- This mode consumes 2-3x API budget and should only be used when solution quality is critical
- It does not change the single-strategy isolation of the OODA loop (attribution still works)
- It is off by default and must be explicitly enabled in the plan

### Output
Solution document in `assets/delivery-template.md` format:
- Problem description (with T1/T2 context)
- Impact scope (files to change, DB changes, API changes, frontend changes)
- Detailed solution (data model, API schema, routes, migration strategy)
- Implementation steps (including dependency order)
- Risks and mitigations
- Acceptance criteria (functional + technical)

### Phase 2 Gate
- [ ] The solution document includes all 5 required sections (problem / impact / solution / steps / acceptance)
- [ ] Data model is defined, if DB changes are involved
- [ ] API interfaces are defined (path, method, schema)
- [ ] Implementation steps are ordered by dependencies
- [ ] Risks are identified and have mitigations

## Phase 3: Feasibility Review

### Goal
Independently review completeness, feasibility, and requirement coverage.

### Methodology
- Definition of Ready check
- Independent reviewer principle (reviewer agent ≠ designer agent)

### Execution

After the ACT stage generates the PRD, the VERIFY stage includes an independent review (reviewer agent ≠ designer agent).

feasibility-reviewer subagent (independent review):
- Check requirement coverage line by line (whether each requirement maps to the design)
- Evaluate technical feasibility (whether the architecture is reasonable and dependencies are identified and manageable)
- Check scope precision (whether IN/OUT is clear and the work is estimable)
- Validate the completeness of risk assessment
- Produce 5-dimension scores and write them to `autoloop-findings.md` and `iterations[-1].scores`

**Review dimensions** (corresponding to the T3 gate-manifest checks):
1. **design_completeness**: whether every requirement has a corresponding design
2. **feasibility_score**: whether the technical architecture is feasible and dependencies are identified
3. **requirement_coverage**: whether the traceability chain from requirement to design is complete
4. **scope_precision**: whether the IN/OUT boundary is clear
5. **validation_evidence**: whether there is an independent feasibility check record

**Writeback rules**:
- Write review results into the `autoloop-findings.md` findings section, using the five dimension names above in the `dimension` field
- Write scores into `iterations[-1].scores` (for example, `design_completeness: 8.5`)
- If Phase 2 and Phase 3 complete in the same OODA round, Phase 3 happens in the VERIFY stage (score.py automatic scoring + feasibility-reviewer agent supplemental manual review)

### Output
- Review report (pass / needs revision), with the concrete issues and scoring basis for each dimension
- 5-dimension scores (written to findings + iterations[-1].scores)
- The final confirmed solution document → direct input for T4 Phase 1

### Phase 3 Gate
Quality gate thresholds are in `references/gate-manifest.json` T3:
- Hard: design_completeness ≥ 7, feasibility_score ≥ 7, requirement_coverage ≥ 7
- Soft: scope_precision ≥ 7, validation_evidence ≥ 7

## Quality Gate Scoring

CHECK stage is scored by an independent evaluator on the following dimensions (0-10):

| Dimension | 1-3 (fail) | 4-6 (partial) | 7-8 (pass) | 9-10 (excellent) |
|------|-------------|-----------|-----------|------------|
| design_completeness | Most requirements have no design mapping | Some requirements have a design | ≥90% of requirements have a complete design | 100% + edge cases |
| feasibility_score | Technical solution is not feasible | Partially feasible, with risks | Architecture is reasonable and risks are manageable | Verified + POC |
| requirement_coverage | Requirement traceability is badly broken | 50-80% traceable | ≥95% traceable | 100% bidirectional traceability |
| scope_precision | No scope definition | Partial IN/OUT | Complete + dependencies identified | + effort estimate |
| validation_evidence | No review | Self-review | Independent review + risk assessment | + POC validation |

## REFLECT Execution Rules for Each Round

T3 Phase 1 (exploration) REFLECT is similar to T1: strategy attribution is optional; the focus is on the reflection summary.
Phase 2-3 REFLECT should preferably write the full structured reflection (strategy_id + effect + delta).

Write the four-layer reflection table into `autoloop-findings.md`.

## Deliverables

Core files produced after T3 completes:
- Solution document (`{doc_output_path}/{feature_name}-{date}.md`, delivery-template.md format)
- `autoloop-findings.md` (requirement analysis process, design decisions, review conclusions)
- `autoloop-progress.md` (per-phase progress log)

The solution document is the direct input for T4 Deliver Phase 1.
