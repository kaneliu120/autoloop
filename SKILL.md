---
name: autoloop
description: >
  Autonomous iteration engine combining OODA loop with subagent parallel execution
  and quality-gated convergence. 7 task templates: research (T1), compare (T2),
  iterate (T3), generate (T4), deliver (T5), quality (T6), optimize (T7).
  Drives multi-round improvement cycles until measurable quality targets are met.
  Use when tasks require systematic multi-step iteration, quality-gated delivery,
  or multi-dimensional optimization with evidence-based scoring.
  Do not use for single-shot tasks, simple questions, or tasks without measurable
  quality criteria.
---

# AutoLoop — Autonomous Iteration Engine

## Core Mechanisms (R4-R7)

- **Independent Evaluator**: Executor and evaluator must be different subagents. The evaluator scores output blind, without knowledge of execution strategy. Detail: `references/agent-dispatch.md` independent evaluator section.
- **Fail-Closed Scoring**: A score missing any of score + rationale + evidence is invalid and treated as failing. Detail: `references/quality-gates.md` scoring specification.
- **Single-Strategy Isolation**: Each DECIDE round selects exactly one strategy (unique `strategy_id`). Multi-strategy parallel results do not enter the experience registry. Detail: `references/loop-protocol.md` single-strategy isolation.
- **Score Confidence**: TSV records `score_variance` and `confidence`. Low confidence (variance >= 2.0 or 0 evidence items) triggers fail-closed. Detail: `references/quality-gates.md` confidence calculation.
- **Cross-Dimension Impact Analysis**: DECIDE must analyze strategy impact on other dimensions; VERIFY must check all affected dimensions. Detail: `references/loop-protocol.md` impact analysis.
- **Global Experience Registry**: Cross-task strategy effect data accumulates in `references/experience-registry.md`. OBSERVE reads recommended strategies; REFLECT writes back results.
- **Deterministic Tool Scripts**: Python stdlib scripts in `scripts/` eliminate LLM calculation and formatting errors. All MANDATORY calls listed in Step 3.
- **Protocol Versioning**: Current version 1.0.0. Minor/major changes trigger rebaseline per `references/evolution-rules.md`.
- **Result Verification**: Protocol changes must declare expected outcomes (incremental, <= 20% magnitude). Unmet targets within the verification window trigger rollback evaluation per `references/evolution-rules.md`.

---

## Step 0: Initialize

1. Determine task type (T1-T7) using the routing table in Step 1.
2. If no `autoloop-state.json` exists in the work directory:
   ```bash
   python3 ${SKILL_DIR}/scripts/autoloop-init.py <work_dir> <template> "<goal>"
   ```
3. If `checkpoint.json` exists (session recovery):
   Read checkpoint, resume from the last completed stage.
4. If `autoloop-plan.md` already exists but no state JSON (legacy mode):
   Continue without SSOT; scripts operate in markdown-only mode.

---

## Step 1: Route & Template Selection

Match the user request to a template using trigger words and intent:

| Template | Trigger Words | Intent |
|----------|--------------|--------|
| T1 Research | research, survey, landscape, 全景调研, 深度调研 | Systematic multi-source knowledge gathering |
| T2 Compare | compare, evaluate options, 对比, 选型, which is better | Evidence-based decision among N candidates |
| T3 Iterate | iterate until, improve, optimize KPI, 迭代优化, 达标 | KPI-driven repeated refinement toward a target |
| T4 Generate | generate batch, produce N items, 批量生成 | High-volume same-type content production |
| T5 Deliver | deliver feature, end-to-end, ship, 全流程交付 | Requirements through production deployment |
| T6 Quality | quality review, enterprise grade, 企业级, 代码审查 | Multi-dimension code/system quality elevation |
| T7 Optimize | optimize, architecture, performance, stability, 系统诊断 | Architecture / performance / stability improvement |

**Confidence routing**: When trigger words are ambiguous, apply the confidence matching rules in `references/parameters.md` routing section. If confidence is below threshold, ask the user to clarify.

**Multi-template chains**: Use `/autoloop:pipeline` for sequential template execution (e.g., T1 -> T2 -> T5). Detail: `commands/autoloop-pipeline.md`.

---

## Step 2: Plan Configuration

1. Collect plan parameters interactively or from the user prompt. Use `assets/plan-template.md` as the field reference.
2. Required fields: goal, template, scope, quality gate dimensions, max rounds, budget.
3. Gate thresholds auto-populate from `references/quality-gates.md` based on the selected template. Override only when the user specifies custom thresholds.
4. Write the plan to `autoloop-plan.md` in the work directory.
5. For T5 Deliver: phase gates follow `references/delivery-phases.md`; phase 0.5 (documentation) requires user confirmation before proceeding.

Detail: `commands/autoloop-plan.md`.

---

## Step 3: Execute Loop

Run the OODA+ loop. Each iteration passes through 8 stages in order.

### Per-Stage Responsibilities

| Stage | Agent Role | Action | JiT Reference |
|-------|-----------|--------|---------------|
| OBSERVE | orchestrator | Read state + experience registry + prior REFLECT output | `references/loop-protocol.md` |
| ORIENT | orchestrator | Gap analysis: current scores vs target gates | -- |
| DECIDE | orchestrator | Select one strategy; filter `已废弃` strategies, prefer `推荐` strategies; use per-round effect (`保持`/`避免`/`待验证`) from prior REFLECT; run cross-dimension impact analysis | `references/experience-registry.md` |
| ACT | subagents | Execute via dispatched work orders (parallel when independent, serial when dependent) | `references/agent-dispatch.md` |
| VERIFY | kpi-evaluator | Score output using `autoloop-score.py`; validate TSV with `autoloop-tsv.py`; compute variance with `autoloop-variance.py` | `references/quality-gates.md` |
| SYNTHESIZE | orchestrator | Merge subagent outputs; detect and resolve contradictions | -- |
| EVOLVE | orchestrator | Termination check: all gates pass / budget exhausted / oscillation / stagnation | `references/evolution-rules.md` |
| REFLECT | orchestrator | Write findings + strategy effects to experience registry + checkpoint | `references/experience-registry.md` |

### Mandatory Script Calls

Execute these scripts at the designated stages. Failure to run them degrades output quality.

```bash
# VERIFY stage — score quality gates
python3 ${SKILL_DIR}/scripts/autoloop-score.py <findings_path>

# VERIFY stage — validate TSV before write
python3 ${SKILL_DIR}/scripts/autoloop-tsv.py validate <tsv_path>

# VERIFY stage — compute score variance (optional but recommended)
python3 ${SKILL_DIR}/scripts/autoloop-variance.py <tsv_path>

# REFLECT stage — render markdown views from SSOT (when ssot_mode: true)
python3 ${SKILL_DIR}/scripts/autoloop-render.py <work_dir>

# REFLECT stage — cross-file primary key consistency check
python3 ${SKILL_DIR}/scripts/autoloop-validate.py <work_dir>
```

### Template-Specific Behavior

| Template | Key Difference | Gate Dimensions | Detail |
|----------|---------------|-----------------|--------|
| T1 Research | Multi-source parallel search | coverage, credibility, consistency, completeness | `commands/autoloop-research.md` |
| T2 Compare | Independent option-analyzer per candidate | coverage, credibility, bias, sensitivity | `commands/autoloop-compare.md` |
| T3 Iterate | KPI-driven with baseline measurement | user-defined KPI target | `commands/autoloop-iterate.md` |
| T4 Generate | Batch with per-unit QC, auto-retry on low score | pass_rate, avg_score | `commands/autoloop-generate.md` |
| T5 Deliver | 7-phase with user gates at phase 0.5 and phase 5 | syntax, security, service_health, acceptance | `commands/autoloop-deliver.md` |
| T6 Quality | 3-dimension unified review framework | security, reliability, maintainability | `commands/autoloop-quality.md` |
| T7 Optimize | 3-dimension with checkpoint every 5 fixes | architecture, performance, stability | `commands/autoloop-optimize.md` |

### Per-Iteration Output Requirements

Each loop iteration must produce:

1. What was completed this round (concrete, quantifiable)
2. Current quality gate scores (numeric, not qualitative)
3. Next round plan (specific actions, not directions)
4. Termination judgment (continue / complete / needs user decision)
5. Reflection record (problem registration + strategy review + pattern identification + experience accumulation)

---

## Step 4: Termination & Report

### Termination Conditions

| Condition | Trigger | Action |
|-----------|---------|--------|
| Normal completion | All Hard Gates pass | Generate final report |
| Budget exhaustion | Max rounds reached | Report "current best" with unmet gates and recommended next steps |
| User interrupt | User says stop/enough | Save progress to checkpoint, deliver intermediate results with completion percentage |
| Blocked | Unresolvable contradiction or irreversible operation needed | Explain blocker clearly, request user decision |
| Oscillation | Score alternates without net improvement for 3+ rounds | Halt, report oscillation pattern, suggest strategy change |
| Stagnation | No gate improvement for consecutive rounds (threshold in `references/parameters.md`) | Halt, report plateau |

### Final Report

1. Execute `python3 ${SKILL_DIR}/scripts/autoloop-render.py <work_dir>` to generate final views.
2. The report follows the structure in `assets/report-template.md`.
3. The report must include: goal recap, final gate scores, iteration count, key findings, and recommendations.

---

## Step 5: Experience Accumulation

After termination, the REFLECT stage writes strategy effects to `references/experience-registry.md`:

- **strategy_id**: Which strategy was used
- **template**: Which template type
- **dimension**: Which quality dimension was targeted
- **delta**: Score change attributed to this strategy
- **verdict**: `保持` (positive effect), `避免` (negative/neutral), or `待验证` (insufficient data)
- **context**: Brief description of when this strategy works

Future OBSERVE stages read this registry to inform DECIDE. Detail: `references/experience-registry.md` effect recording section.

---

## Agent Dispatch Rules

### Parallel Dispatch (Independent Tasks)

Dispatch in parallel when task A output is not task B input:

- Multiple researchers searching different dimensions
- Multiple reviewers checking different code modules
- Multiple generators producing different content units
- frontend-dev and backend-dev working on different layers

### Serial Dispatch (Dependent Tasks)

Dispatch serially when task B requires task A output:

- Analysis before development
- Development before review
- Review approval before deployment
- Deployment before acceptance testing

### Subagent Role Matrix

| Agent | Responsibility | Invocation Context |
|-------|---------------|-------------------|
| planner | Task decomposition, architecture design | Task start, complex feature planning |
| researcher | Web research, competitive analysis, data collection | T1/T2 throughout, T5 phase 0 |
| backend-dev | Backend implementation (stack per plan) | T5 phase 1, T6/T7 fixes |
| frontend-dev | Frontend implementation (stack per plan) | T5 phase 1, T6/T7 fixes |
| db-migrator | Database migrations, SQL operations | T5 phase 1 (when DB changes needed) |
| code-reviewer | Security + quality review | T5 phase 2, T6 every round, T7 every 5 fixes |
| generator | Batch content production | T4 throughout |
| verifier | Test execution, production acceptance | T5 phases 3+5, T6/T7 post-fix |

### Subagent Context Requirements

Every dispatch must provide:

1. **Task objective** -- concrete deliverable, not a direction
2. **Input data** -- absolute file paths, prior findings, previous round results
3. **Output format** -- expected return structure for integration
4. **Quality criteria** -- applicable gate conditions and pass thresholds
5. **Scope constraints** -- allowed files/directories/domains, forbidden modifications
6. **Round context** -- current round N of M budget
7. **History summary** -- key findings from prior rounds to avoid duplicate work

Detail: `references/agent-dispatch.md`.

---

## File System Conventions

| File | Purpose | Updated |
|------|---------|---------|
| `autoloop-state.json` | SSOT primary authority (when ssot_mode enabled) | Every stage |
| `autoloop-plan.md` | Task plan: goal, template, scope, gates, budget | Task start; scope changes |
| `autoloop-progress.md` | Per-round start/end records, score progression | Round start and end |
| `autoloop-findings.md` | Research results, issue lists, fix records | After each subagent return |
| `autoloop-results.tsv` | Structured iteration log (15 columns per `references/loop-data-schema.md` TSV schema) | VERIFY stage |
| `checkpoint.json` | Session recovery state | Every stage |
| `references/experience-registry.md` | Cross-task strategy memory | REFLECT stage |

**Cross-File Primary Keys**: Four files share unified keys (`iteration` + `strategy_id` + `dimension` + `problem_id`) for traceability. Detail: `references/loop-data-schema.md` primary key specification.

---

## Error Handling

| Symptom | Cause | Recovery |
|---------|-------|----------|
| `autoloop-controller.py` fails during ACT | Subagent timeout or error | Read `checkpoint.json`, restart from the failed stage's OBSERVE |
| `autoloop-score.py` returns all-zero scores | Gate definitions do not match template | Verify `references/quality-gates.md` gate definitions match the template in `autoloop-plan.md` |
| `autoloop-state.json` and markdown views are out of sync | Render was skipped or interrupted | Execute `python3 ${SKILL_DIR}/scripts/autoloop-render.py <work_dir>` to regenerate |
| `experience-registry.md` is empty (first run) | No prior task history | Skip experience read in OBSERVE; use default strategies in DECIDE |
| `checkpoint.json` is corrupted or unreadable | Crash during write | Execute `python3 ${SKILL_DIR}/scripts/autoloop-init.py <work_dir> <template> "<goal>"` to reinitialize |
| TSV validation fails | Column count or format mismatch | Check `references/loop-data-schema.md` TSV schema; fix the row; re-run `autoloop-tsv.py validate` |
| Score oscillation detected (3+ rounds) | Strategy is counterproductive or scope is too narrow | Log oscillation in findings; switch strategy in DECIDE; if persists, halt and report to user |
| Subagent returns empty output | Scope too narrow or tool access failure | Widen scope or verify tool availability; retry once; if still empty, escalate to user |

---

## Integration with CLAUDE.md

When operating within a project that has a `CLAUDE.md`:

- AutoLoop serves as the Orchestrator-First execution engine defined in CLAUDE.md
- T5 Deliver maps directly to the CLAUDE.md mandatory development flow (phases 0-5)
- All engineering decisions follow the project CLAUDE.md code conventions
- Technology stack parameters are collected in `autoloop-plan.md` and respected by T5/T6/T7 subagents

---

## Optional Enhancements

### Claude Code Hooks (auto-enforcement)

When configured in `~/.claude/settings.json`:

- `PostToolUse:Write|Edit` on `autoloop-findings.md` triggers `autoloop-score.py`
- `PostToolUse:Write|Edit` on `autoloop-results.tsv` triggers `autoloop-tsv.py validate`
- `Stop` trigger runs `autoloop-validate.py` for cross-file consistency

### MCP Server Mode

Install: `bash ${SKILL_DIR}/mcp-server/install.sh`
Register: `claude mcp add autoloop python3 ${SKILL_DIR}/mcp-server/server.py`
Provides 5 tools: `autoloop_init`, `autoloop_score`, `autoloop_tsv`, `autoloop_validate`, `autoloop_variance`.

MCP is an enhancement layer; file-based mode remains the default.

---

## Quick Reference

```
/autoloop          -> Interactive entry (guided template selection)
/autoloop:plan     -> Guided plan configuration
/autoloop:research -> T1 Research
/autoloop:compare  -> T2 Compare
/autoloop:iterate  -> T3 Iterate
/autoloop:generate -> T4 Generate
/autoloop:deliver  -> T5 Deliver
/autoloop:quality  -> T6 Quality
/autoloop:optimize -> T7 Optimize
/autoloop:pipeline -> Multi-template chain (e.g., T1 -> T2 -> T5)
```
