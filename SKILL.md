---
name: autoloop
description: >
  Autonomous iteration engine combining OODA loop with subagent parallel execution
  and quality-gated convergence. 7 task templates: research (T1), compare (T2),
  iterate (T5), generate (T6), deliver (T4), quality (T7), optimize (T8).
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
- **Score Confidence**: TSV records `score_variance` and `confidence`. Low confidence (variance >= 2.0 or 0 evidence items) triggers fail-closed. Detail: `references/quality-gates.md` confidence calculation. In SSOT mode, `autoloop-score.py` **`overall_pass`** also treats the latest TSV row fail-closed as failure (aligned with `phase_evolve`, not gates-only).
- **Cross-Dimension Impact Analysis**: DECIDE must analyze strategy impact on other dimensions; VERIFY must check all affected dimensions. Detail: `references/loop-protocol.md` impact analysis.
- **Global Experience Registry**: Cross-task strategy effect data accumulates in `references/experience-registry.md`. OBSERVE reads recommended strategies; REFLECT writes back results.
- **Deterministic Tool Scripts**: Python stdlib scripts in `scripts/` eliminate LLM calculation and formatting errors. All MANDATORY calls listed in Step 3.
- **Strict runs**: `autoloop-controller.py <work_dir> --strict` (or `AUTOLOOP_STRICT=1`) stops the loop after VERIFY if score JSON, `autoloop-validate.py`, or `autoloop-variance.py check` fails. Same flag: EVOLVE 前还须本轮结构化 finding **且** `results_tsv` 末行 `iteration` 对齐当前轮次。Use `AUTOLOOP_VALIDATE_STRICT=1` or `autoloop-validate.py <dir> --strict` for schema-as-error (含 REFLECT strict 下 `delta`/Likert 等，见 `loop-protocol.md`)。
- **Protocol Versioning**: Current version 1.0.0. Minor/major changes trigger rebaseline per `references/evolution-rules.md`.
- **Result Verification**: Protocol changes must declare expected outcomes (incremental, <= 20% magnitude). Unmet targets within the verification window trigger rollback evaluation per `references/evolution-rules.md`.

---

## Step 0: Initialize

1. Determine task type (T1-T8) using the routing table in Step 1.
2. If no `autoloop-state.json` exists in the work directory:
   ```bash
   python3 ${SKILL_DIR}/scripts/autoloop-init.py <work_dir> <template> "<goal>"
   ```
3. If `checkpoint.json` exists (session recovery):
   Read checkpoint, resume from the last completed stage.
4. **DEPRECATED — Legacy（不推荐）**：仅有 `autoloop-plan.md` 等工作区 Markdown、**无** `autoloop-state.json` 时，部分脚本可走 markdown-only 回退；**推荐路径**始终为 `autoloop-state.py init` + SSOT JSON + `autoloop-controller.py`。新任务请勿依赖 legacy；旧任务请 `migrate` 或手工补全 state（D-06）。

---

## Step 1: Route & Template Selection

Match the user request to a template using trigger words and intent:

| Template | Trigger Words | Intent |
|----------|--------------|--------|
| T1 Research | research, survey, landscape, 全景调研, 深度调研 | Systematic multi-source knowledge gathering |
| T2 Compare | compare, evaluate options, 对比, 选型, which is better | Evidence-based decision among N candidates |
| T3 Product Design | product design, 产品设计, 方案文档, PRD, spec, 需求分析 | Requirements analysis → solution design → feasibility review |
| T4 Deliver | deliver feature, end-to-end, ship, 全流程交付 | Requirements through production deployment |
| T5 Iterate | iterate until, improve, optimize KPI, 迭代优化, 达标 | KPI-driven repeated refinement toward a target |
| T6 Generate | generate batch, produce N items, 批量生成 | High-volume same-type content production |
| T7 Quality | quality review, enterprise grade, 企业级, 代码审查 | Multi-dimension code/system quality elevation |
| T8 Optimize | optimize, architecture, performance, stability, 系统诊断 | Architecture / performance / stability improvement（与 T5 区分：T5 以**用户 KPI 数值**收敛为主；T8 以**系统多维度工程质量/架构**为主，见 `quality-gates.md` T7/T8） |

**Confidence routing**: When trigger words are ambiguous, apply the confidence matching rules in `references/parameters.md` routing section. If confidence is below threshold, ask the user to clarify.

**Multi-template chains**: Use `/autoloop:pipeline` for sequential template execution (e.g., T1 -> T2 -> T4). Detail: `commands/autoloop-pipeline.md`.

---

## Step 2: Plan Configuration

1. Collect plan parameters interactively or from the user prompt. Use `assets/plan-template.md` as the field reference.
2. Required fields: goal, template, scope, quality gate dimensions, max rounds, budget.
3. **Gate thresholds (SSOT)** come exclusively from `references/gate-manifest.json` — the mandatory numeric threshold source of truth for all gate pass/fail decisions. Use `references/quality-gates.md` for scoring semantics, confidence/fail-closed rules, and methodology — not as the numeric threshold source.
4. Write the plan to `autoloop-plan.md` in the work directory.
5. For T4 Deliver: phase gates follow `references/delivery-phases.md`; phase 5 (acceptance) requires user confirmation. Optional SSOT: `plan.template_mode: linear_phases` ties EVOLVE budget to `plan.linear_delivery_complete` (see `references/loop-data-schema.md`).

Detail: `commands/autoloop-plan.md`.

---

## Step 3: Execute Loop

Run the OODA+ loop. Each iteration passes through 8 stages in order.

**Layering**: AutoLoop owns round progression, gates, TSV variance fail-closed (via EVOLVE), and termination. Implementation work inside ACT can follow Superpowers-style flows (brainstorm → plan → subagents → TDD → review) or your stack’s equivalent — see controller ACT prompts for T5/T6/T4 hints.

### Per-Stage Responsibilities

| Stage | Agent Role | Action | JiT Reference |
|-------|-----------|--------|---------------|
| OBSERVE | orchestrator | Read state + experience registry + prior REFLECT output | `references/loop-protocol.md` |
| ORIENT | orchestrator | Gap analysis: current scores vs target gates | -- |
| DECIDE | orchestrator | Select one strategy; filter `已废弃` strategies, prefer `推荐` strategies; use per-round effect (`保持`/`避免`/`待验证`) from prior REFLECT; run cross-dimension impact analysis | `references/experience-registry.md` |
| ACT | subagents | Execute via dispatched work orders (parallel when independent, serial when dependent) | `references/agent-dispatch.md` |
| VERIFY | kpi-evaluator | Score with `autoloop-score.py`（SSOT 下 `overall_pass` 含末行 TSV fail-closed）；TSV 格式用 `autoloop-tsv.py validate`；方差/置信度合规用 `autoloop-variance.py check <tsv>`（`compute` 仅辅助填列） | `references/quality-gates.md` |
| SYNTHESIZE | orchestrator | Merge subagent outputs; detect and resolve contradictions | -- |
| EVOLVE | orchestrator | Termination check: all gates pass / budget exhausted / oscillation / stagnation | `references/evolution-rules.md` |
| REFLECT | orchestrator | Write findings + strategy effects to experience registry + checkpoint | `references/experience-registry.md` |

**REFLECT → 经验库**：将 `iterations[-1].reflect` 写成 JSON：`strategy_id`、`effect` 必填；**推荐** `delta`（单轮变化量，写入经验库的 `--score`）与可选 `rating_1_to_5`（Likert）。键 `score` 仅 **legacy**（若为正整数 1–5 视为 Likert，不当作 delta）。`AUTOLOOP_VALIDATE_STRICT=1` 下还要求 `delta` / `rating_1_to_5` / legacy Likert `score` 至少其一。控制器才能确定性调用 `autoloop-experience.py write`；字段表见 `references/loop-protocol.md` §REFLECT。

### Mandatory Script Calls

Execute these scripts at the designated stages. Failure to run them degrades output quality.

```bash
# VERIFY stage — score quality gates
python3 ${SKILL_DIR}/scripts/autoloop-score.py <findings_path>

# VERIFY stage — validate TSV before write
python3 ${SKILL_DIR}/scripts/autoloop-tsv.py validate <tsv_path>

# VERIFY stage — TSV 方差/置信度合规（与 controller phase_verify 一致，须带 check 子命令）
python3 ${SKILL_DIR}/scripts/autoloop-variance.py check <tsv_path>

# REFLECT stage — render markdown views from SSOT (when ssot_mode: true)
python3 ${SKILL_DIR}/scripts/autoloop-render.py <work_dir>

# REFLECT stage — cross-file primary key consistency check（契约加严用 --strict 或 AUTOLOOP_VALIDATE_STRICT=1）
python3 ${SKILL_DIR}/scripts/autoloop-validate.py <work_dir>
```

### Template-Specific Behavior

| Template | Key Difference | Gate Dimensions | Detail |
|----------|---------------|-----------------|--------|
| T1 Research | **General research entry**. For market/industry topics, upgrade automatically to a **top-tier market research report** with fixed core chapters, per-chapter data+analysis+conclusion, optional direction modules (e.g. industry + AI job substitution), and a **master-agent / subagent protocol**: the master agent splits chapters, dispatches evidence collection, integrates chapter evidence packets, resolves conflicts, and writes the only final report; OODA rounds optional for gate convergence | coverage, credibility, consistency, completeness | `commands/autoloop-research.md`, `references/t1-formal-report.md` §0 |
| T2 Compare | Independent option-analyzer per candidate | coverage, credibility, bias, sensitivity | `commands/autoloop-compare.md` |
| T3 Design | 3-phase: requirements → design → review; output is confirmed spec for T4 | design_completeness, feasibility_score, requirement_coverage, scope_precision, validation_evidence | `commands/autoloop-design.md` |
| T4 Deliver | 5-phase (Phase 1-5) with user gate at phase 5 | **Machine dims** (manifest): `syntax_errors`, `p1_p2_issues`, `service_health`, `user_acceptance` — 文档口语可称 syntax / P1-P2 / 服务健康 / 验收 | `commands/autoloop-deliver.md` |
| T5 Iterate | KPI-driven with baseline measurement | user-defined KPI target | `commands/autoloop-iterate.md` |
| T6 Generate | Batch with per-unit QC, auto-retry on low score | pass_rate, avg_score | `commands/autoloop-generate.md` |
| T7 Quality | 3-dimension unified review framework | security, reliability, maintainability | `commands/autoloop-quality.md` |
| T8 Optimize | 3-dimension with checkpoint every 5 fixes | architecture, performance, stability | `commands/autoloop-optimize.md` |

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

1. Execute `python3 ${SKILL_DIR}/scripts/autoloop-render.py <work_dir>` to refresh internal markdown views and SSOT-derived artifacts when applicable.
2. The report follows the structure in `assets/report-template.md`. **T1 Research** uses the **「T1：高标准市场/行业调研报告」** section for market/industry topics: title, topic, goal, date, boundary, fixed core chapters, optional direction modules, and sources only. **Do not include** in that file: task ID, exec summary table, quality scores, internal process notes, issue-tree/methodology headings, or system traces. **T1 content must be grounded in agent-run web/public-source research** in `autoloop-findings.md` per `commands/autoloop-research.md`.
3. For T1, the master agent should synthesize chapter evidence packets into a single reader-facing report. Subagents collect evidence; they do not each write their own final chapter prose.
4. Gate scores, iteration count, plan metadata, and internal validation artifacts live in `autoloop-state.json` / `autoloop-progress.md`, not in the T1 reader report. **Iteration count is not what defines T1**; depth, structure, sourced evidence, and clear evidence boundaries define the deliverable.
5. At the current stage, the T1 reader-facing final report should be treated as **protocol-first composition by the master agent**. Full structured `state/render` generation of that reader report is a **phase-two enhancement**, not a prerequisite for high-quality output.

### T1 Protocol Priorities

When implementing or extending T1, use this order of priority:

1. Stabilize the master-agent / subagent protocol.
2. Stabilize chapter evidence packet fields and return format.
3. Stabilize depth gates that block thin drafts.
4. Only after the above are stable, consider adding full reader-report rendering to structured `state/render`.

Current recommendation: treat structured state/render support for the final T1 reader report as **phase two**, not the first implementation step.

---

## Step 5: Experience Accumulation

After termination, the REFLECT stage writes strategy effects to `references/experience-registry.md`:

- **strategy_id**: Which strategy was used
- **template**: Which template type
- **dimension**: Which quality dimension was targeted
- **delta**: Score change attributed to this strategy (passed to `autoloop-experience.py --score`)
- **effect**（经验库与 `iterations[-1].reflect` 字段名）: `保持` / `避免` / `待验证` — 口语「verdict」与此等价，文档以 `effect` 为准
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
| researcher | Web research, competitive analysis, data collection | T1/T2 throughout |
| backend-dev | Backend implementation (stack per plan) | T4 phase 1, T7/T8 fixes |
| frontend-dev | Frontend implementation (stack per plan) | T4 phase 1, T7/T8 fixes |
| db-migrator | Database migrations, SQL operations | T4 phase 1 (when DB changes needed) |
| code-reviewer | Security + quality review | T4 phase 2, T7 every round, T8 every 5 fixes |
| generator | Batch content production | T6 throughout |
| verifier | Test execution, production acceptance | T4 phases 3+5, T7/T8 post-fix |

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
| `autoloop-state.json` | SSOT primary authority | Every stage |
| `autoloop-plan.md` | Task plan: goal, template, scope, gates, budget | Task start; scope changes |
| `autoloop-progress.md` | Per-round start/end records, score progression | Round start and end |
| `autoloop-findings.md` | Research results, issue lists, fix records | After each subagent return |
| `autoloop-results.tsv` | Structured iteration log (15 columns per `references/loop-data-schema.md` TSV schema) | VERIFY stage |
| `checkpoint.json` | Session recovery state | Every stage |
| `references/experience-registry.md` | Cross-task strategy memory | REFLECT stage |
| `references/domain-pack-*.md` | Technology-specific gate weights and detection commands (FastAPI, Next.js) | Task start (T7/T8) |

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
- T4 Deliver maps directly to the CLAUDE.md mandatory development flow (phases 0-5)
- All engineering decisions follow the project CLAUDE.md code conventions
- Technology stack parameters are collected in `autoloop-plan.md` and respected by T4/T7/T8 subagents

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
Provides 10 tools: `autoloop_init`, `autoloop_score`, `autoloop_tsv`, `autoloop_validate`, `autoloop_variance`, `autoloop_state`, `autoloop_render`, `autoloop_experience`, `autoloop_finalize`, `autoloop_controller`.

MCP is an enhancement layer; file-based mode remains the default.

---

## Quick Reference

```
/autoloop          -> Interactive entry (guided template selection)
/autoloop:plan     -> Guided plan configuration
/autoloop:research -> T1 Research
/autoloop:compare  -> T2 Compare
/autoloop:design   -> T3 Product Design
/autoloop:iterate  -> T5 Iterate
/autoloop:generate -> T6 Generate
/autoloop:deliver  -> T4 Deliver
/autoloop:quality  -> T7 Quality
/autoloop:optimize -> T8 Optimize
/autoloop:pipeline -> Multi-template chain (e.g., T1 -> T2 -> T4)
```
