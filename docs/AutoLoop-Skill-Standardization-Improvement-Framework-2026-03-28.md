# AutoLoop Skill Standardization Improvement Framework

**Date**: 2026-03-28  
**Basis**: agentskills.io best practices + AutoLoop structure audit  
**Goal**: refactor AutoLoop from a "large document set" into a standardized structure that follows skill best practices

---

## 1. Core Best-Practice Principles vs. Current AutoLoop State

| Principle | Best-practice requirement | Current AutoLoop state | Gap |
|-----------|---------------------------|------------------------|-----|
| SKILL.md < 500 lines | The main file should stay compact and only contain navigation + high-level flow | 405 lines (barely compliant), but it carries too many definitions | Medium |
| Flat first-level directories | scripts/ references/ assets/ should all be first-level | protocols/ contains second-level directories, and commands/ has 10 files | High |
| Just-in-time loading (JiT) | Load helper files only when needed | All protocols are referenced by SKILL.md but there is no explicit "when to read" instruction | High |
| Scripts = deterministic CLI | Small single-purpose CLI tools with stdout/stderr feedback | 7 scripts fit this pattern, but there is no unified CLI standard | Medium |
| Third-person imperative | "Extract the text..." instead of "You should..." | Mixed Chinese prose + second-person language | Low |
| No human documentation | Do not create README / CHANGELOG | README.md + TODO.md exist | Medium |
| Trigger-word optimization | Description should include positive and negative triggers | Positive triggers exist, negative triggers are missing | Low |
| Metadata validation script | Automated name / description validation | None | High |
| Error-handling section | SKILL.md should include an Error Handling section at the bottom | No dedicated error-handling section | High |

---

## 2. Current Structural Problems

```text
autoloop/                          # 49 files, structure is messy
├── SKILL.md                       # 405 lines, barely compliant
├── README.md                      # ❌ human doc, should not exist
├── TODO.md                        # ❌ human doc, should not exist
├── autoloop-plan.md               # ❌ runtime artifact, should not live in the repo
├── autoloop-progress.md           # ❌ runtime artifact
├── autoloop-findings.md           # ❌ runtime artifact
│
├── commands/                      # 10 command files - responsibilities are blurred
│   ├── autoloop.md               # entry routing (should live in SKILL.md)
│   ├── autoloop-plan.md          # planning guide (500+ lines, too large)
│   └── autoloop-{template}.md    # 7 template commands (each 200-500 lines)
│
├── protocols/                     # 12 protocol files - should this be references/ instead?
│   ├── domain-packs/             # ❌ second-level directory, violates the flat principle
│   │   ├── README.md
│   │   ├── python-fastapi.md
│   │   └── nextjs-typescript.md
│   ├── loop-protocol.md          # core loop (680+ lines, too large)
│   ├── quality-gates.md          # gate definitions (650+ lines, too large)
│   └── ...
│
├── templates/                     # 6 template files - should be assets/
│
├── scripts/                       # 7 scripts - mostly OK, but no unified interface
│
├── mcp-server/                    # ❌ non-standard directory
│
├── {compare,deliver,...}/SKILL.md # 8 subcommand SKILL files - nearly empty wrappers
│   └── SKILL.md                  # each is about 15 lines and only passes through
│
└── plan/SKILL.md                  # same issue
```

### Core Problems

1. **Responsibilities are blurred**: `commands/` and `protocols/` do not have a clear boundary - command files contain protocol material, and protocol files contain execution instructions
2. **Context bloat**: the protocols/ directory is roughly 4,500 lines total; loading all of it at once will blow up the context window
3. **Runtime artifacts pollute the repository**: autoloop-plan/progress/findings.md are runtime files and should not be committed
4. **Subcommand SKILL.md files are low-value**: the 8 subcommand directories each contain a tiny pass-through SKILL.md
5. **Second-level directory**: `domain-packs/` violates the flat first-level principle
6. **Human docs**: README.md and TODO.md do not belong in a skill repository

---

## 3. Recommended Standard Directory Layout

```text
autoloop/
├── SKILL.md                       # entry point - navigation + routing + loop overview (<500 lines)
│
├── scripts/                       # deterministic tools - small CLI with stdout/stderr feedback
│   ├── autoloop-controller.py    # 🆕 main loop controller (core engine)
│   ├── autoloop-state.py         # SSOT state management
│   ├── autoloop-score.py         # multi-template scorer
│   ├── autoloop-validate.py      # cross-file validator
│   ├── autoloop-render.py        # SSOT → markdown render
│   ├── autoloop-init.py          # bootstrap (enhanced)
│   ├── autoloop-tsv.py           # TSV operations
│   ├── autoloop-variance.py      # variance / confidence
│   ├── autoloop-experience.py    # 🆕 experience registry I/O
│   ├── autoloop-finalize.py      # 🆕 final report generation
│   └── validate-metadata.py      # 🆕 metadata validation (from best practices)
│
├── references/                    # JiT-loaded protocols / specs (read only when needed)
│   ├── loop-protocol.md          # core loop definition (condensed, <300 lines)
│   ├── quality-gates.md          # gate definitions + thresholds + hard/soft matrix
│   ├── agent-dispatch.md         # subagent dispatch rules
│   ├── enterprise-standard.md    # T6/T7 scoring criteria
│   ├── evolution-rules.md        # protocol evolution rules
│   ├── experience-registry.md    # strategy experience registry
│   ├── parameters.md             # centralized parameters
│   ├── delivery-phases.md        # T5 delivery phases
│   ├── orchestration.md          # pipeline orchestration
│   ├── domain-pack-fastapi.md    # Python/FastAPI detection rules (flattened)
│   ├── domain-pack-nextjs.md     # Next.js / TypeScript detection rules (flattened)
│   ├── domain-pack-spec.md       # Domain pack framework definition (old README.md)
│   └── checklist.md              # 🆕 skill quality checklist
│
├── assets/                        # output templates + static files
│   ├── plan-template.md          # plan output template
│   ├── progress-template.md      # progress output template
│   ├── findings-template.md      # findings output template
│   ├── report-template.md        # final report template
│   ├── audit-template.md         # T6 audit template
│   ├── delivery-template.md      # T5 delivery template
│   └── checkpoint-schema.json    # 🆕 checkpoint JSON schema
│
└── mcp-server/                    # MCP integration (optional enhancement layer)
    ├── server.py
    ├── install.sh
    └── mcp-config.json
```

### Change Mapping

| Current | Recommended | Change type |
|---------|-------------|-------------|
| `commands/autoloop.md` | Merge into `SKILL.md` | delete and move upward |
| `commands/autoloop-plan.md` | Condense and merge into `SKILL.md` Step 1 | delete and move upward |
| `commands/autoloop-{template}.md` × 7 | Merge into `SKILL.md` template sections + JiT references | delete and move upward |
| `protocols/` × 12 | → `references/` | rename and flatten |
| `protocols/domain-packs/` (second-level) | → `references/domain-pack-*.md` | flatten |
| `templates/` × 6 | → `assets/` | rename |
| `{compare,deliver,...}/SKILL.md` × 8 | delete | route subcommands in the main SKILL.md |
| `README.md` | delete | human doc |
| `TODO.md` | delete (move content into a project-management tool) | human doc |
| `autoloop-plan/progress/findings.md` | `.gitignore` | runtime artifact |

---

## 4. Standardized SKILL.md Framework

```markdown
---
name: autoloop
description: >
  Autonomous iteration engine combining OODA loop with subagent parallel execution.
  7 task templates: research, compare, iterate, generate, deliver, quality, optimize.
  Executes multi-round improvement cycles with quality gates until targets are met.
  Use when tasks require systematic iteration, quality-gated delivery, or multi-dimensional optimization.
  Do not use for single-shot tasks, simple questions, or tasks without measurable quality criteria.
---

# AutoLoop - autonomous iteration engine

## Step 0: Initialization

1. Determine the task type (T1-T7) using the routing table below
2. If the workdir has no `autoloop-state.json`:
   run `python3 scripts/autoloop-controller.py <work_dir> --init --template T{N}`
3. If `checkpoint.json` exists (resume after interruption):
   run `python3 scripts/autoloop-controller.py <work_dir> --resume`

## Step 1: Routing and template selection

[condensed routing table - trigger words → template mapping]
[confidence matching rules - reference references/parameters.md §routing match parameters]

## Step 2: Plan configuration

[condensed plan collection flow - reference assets/plan-template.md]
[gate-threshold auto-injection - controller reads references/quality-gates.md]

## Step 3: Execution loop

Run `python3 scripts/autoloop-controller.py <work_dir>` to start the main loop.
The controller automatically drives the 8-stage OODA loop.

### Stage responsibilities by agent

[condensed table: OBSERVE / ORIENT / DECIDE / ACT / VERIFY / SYNTHESIZE / EVOLVE / REFLECT]
[write only 2-3 core responsibilities for each stage; detailed specs are JiT-loaded from references/]

### Template-specific behavior

[T1-T7 differences table - only key differences, detailed behavior lives in references/]

## Step 4: Termination and reporting

1. The controller determines the termination condition (all hard gates passed / budget exhausted / user interrupted)
2. Run `python3 scripts/autoloop-finalize.py <work_dir>`
3. Output the final report (format defined in assets/report-template.md)

## Step 5: Experience accumulation

The controller automatically writes strategy effects into `references/experience-registry.md`
(see references/experience-registry.md §effect recording for details)

## Error Handling

* If `autoloop-controller.py` fails in ACT (subagent timeout / error):
  read checkpoint.json and restart from OBSERVE in the failed stage
* If `autoloop-score.py` returns zero for all dimensions:
  read references/quality-gates.md to confirm the gate definitions match the template
* If `autoloop-state.json` and the markdown views are out of sync:
  run `python3 scripts/autoloop-render.py <work_dir>` to regenerate
* If experience-registry.md is empty (first run):
  skip experience reads and let DECIDE use the default strategy

## Quick Reference

/autoloop          → interactive entry point
/autoloop:plan     → guided setup
/autoloop:research → T1 full-scope research
/autoloop:compare  → T2 multi-option comparison
/autoloop:iterate  → T3 goal-driven iteration
/autoloop:generate → T4 batch generation
/autoloop:deliver  → T5 end-to-end delivery
/autoloop:quality  → T6 enterprise quality
/autoloop:optimize → T7 architecture optimization
/autoloop:pipeline → multi-template chained execution
```

---

## 5. JiT Loading Rules

Each `references/` file should state "when to load it":

| File | When to load | Trigger condition |
|------|--------------|-------------------|
| loop-protocol.md | Step 3 execution loop | when the controller needs stage-transition rules |
| quality-gates.md | Step 2 plan configuration + VERIFY | when gate thresholds are needed |
| agent-dispatch.md | ACT stage | when delegating to subagents |
| enterprise-standard.md | T6/T7 OBSERVE | when scoring criteria are needed |
| evolution-rules.md | EVOLVE stage | when evolution / termination rules are needed |
| experience-registry.md | OBSERVE + REFLECT | read recommended strategies / write strategy effects |
| parameters.md | Step 1 routing + EVOLVE | when thresholds / parameters are needed |
| delivery-phases.md | T5 ACT stage | T5-specific phase rules |
| orchestration.md | pipeline mode | when chaining multiple templates |
| domain-pack-*.md | T6/T7 OBSERVE | when auto-detecting the tech stack |
| checklist.md | pre-release validation | self-check after skill changes |

---

## 6. Script CLI Standard

All scripts/ should follow a unified interface:

```text
Usage: autoloop-{tool}.py <work_dir> [command] [args] [--json]

Exit codes:
  0 = success
  1 = validation failure (gates not passed, data inconsistent)
  2 = invalid arguments

Output:
  stdout = structured result (human-readable by default, JSON with --json)
  stderr = error messages (for agent self-correction)
```
