# AutoLoop Task Plan

## Metadata

| Field | Value |
|------|-----|
| Task ID | autoloop-{YYYYMMDD-HHMMSS} |
| Template | T{N}: {Name} |
| Status | Ready / In progress / Paused awaiting confirmation / Completed |
| Created at | {ISO 8601} |
| Last updated | {ISO 8601} |
| Workdir | {absolute path} |
| Plan version | 1.0 |

---

## Goal Description

**One-line goal**: {concise description, no more than one sentence}

**Detailed background**:
{complete description of the user's goal, including background, current state, and desired outcome}

**Success criteria** (measurable):
- {criterion 1}: {specific verification method}
- {criterion 2}: {specific verification method}
- {criterion 3}: {specific verification method}

---

## Task Parameters

### Template-Specific Parameters

**T1 Research**:
- Core topic: {topic}
- Research dimensions:
  1. {dimension 1}
  2. {dimension 2}
  3. {dimension 3}
- Exclusions: {what not to research}
- Time range: the last {N} years

**T2 Compare**:
- Option A: {description}
- Option B: {description}
- Evaluation dimensions: {dimension 1} (weight {X}%), {dimension 2} (weight {Y}%), ...
- Decision criterion: {most important factor}
- key_assumptions (assumptions table for sensitivity analysis):

| Assumption name | Current value | Unit | Sensitivity range (±20%) |
|-----------------|---------------|------|--------------------------|
| {assumption 1, e.g. market growth rate} | {current value, e.g. 15} | {unit, e.g. %/year} | {low} ~ {high} |
| {assumption 2, e.g. implementation cycle} | {current value, e.g. 6} | {unit, e.g. months} | {low} ~ {high} |
| {assumption 3, e.g. team size} | {current value, e.g. 5} | {unit, e.g. people} | {low} ~ {high} |

**T3 Product Design**:
- Functional requirements: {detailed description}
- Target codebase path: {absolute path}
- Output document path: {absolute path}

**T4 Deliver**:
- Functional description: {detailed requirements}
- Codebase path: {absolute path}
- New route: {yes/no}, route prefix: {prefix}
- new_router_name: {router variable name to add, e.g. comments_router}
- main_entry_file: {absolute path to the main entry file, e.g. /project/backend/main.py or /project/src/app.ts}
- Database changes: {yes/no}, change details: {description}
- syntax_check_cmd: {syntax check command, e.g. python3 -m py_compile {file}}
- syntax_check_file_arg: {true/false, whether the syntax check command accepts a single-file argument; python3 -m py_compile -> true, npx tsc --noEmit -> false}
- deploy_target: {deployment host/environment, e.g. prod-server}
- deploy_command: {full deployment command, e.g. gcloud compute ssh ... --command="cd /opt/sip && git pull && sudo bash deploy.sh"}
- service_list: {service names, e.g. [backend-api, worker, scheduler, frontend]; use N/A if not applicable}
- service_count: {auto-calculated, = len(service_list); use 0 when service_list=N/A}
- health_check_url: {health check URL, e.g. https://example.com/api/health; leave blank if not applicable}
- acceptance_url: {online acceptance URL, e.g. https://example.com}
- migration_check_cmd: {database migration check command, e.g. `alembic check` / `prisma migrate status` / N/A}
- doc_output_path: {absolute output directory for the design document}

**T5 Iterate**:
- KPI: {metric name} = {target value}
- Current baseline: {baseline value} ({measurement time})
- Measurement method: {command or steps}
- Change constraints: {allowed / disallowed change scope}

**T6 Generate**:
- Content type: {type}
- Quantity: {N}
- Variables: {variable 1}, {variable 2}
- Quality threshold: {N}/10
- output_path: {absolute output directory, default {workdir}/autoloop-output/}
- naming_pattern: {filename convention, e.g. {template_name}-{index}.md}

**T7 Quality**:
- Codebase path: {absolute path}
- main_entry_file: {absolute path to the main entry file, e.g. /project/backend/main.py or /project/src/app.ts}
- Review scope: {module list / all}
- syntax_check_cmd: {syntax check command, e.g. python3 -m py_compile {file}}
- syntax_check_file_arg: {true/false, whether the syntax check command accepts a single-file argument}
- Known issues: {description / none}
- Special constraints: {constraint / none}

**T8 Optimize**:
- System path: {absolute path}
- main_entry_file: {absolute path to the main entry file, e.g. /project/backend/main.py or /project/src/app.ts}
- syntax_check_cmd: {syntax check command, e.g. python3 -m py_compile {file}}
- syntax_check_file_arg: {true/false, whether the syntax check command accepts a single-file argument}
- Current performance: {metric: value}
- Priority focus: {all / architecture / performance / stability}
- Do not modify: {content}

---

## Scope Definition

**Included**:
- {scope 1}
- {scope 2}

**Excluded**:
- {exclusion 1} (reason: {reason})
- {exclusion 2}

**Extended dimensions** (added during iteration):
- {new dimension} (added in round {N}, reason: {reason})

---

## Quality Gates

| Dimension | Target score | Current score | Target threshold | Status |
|-----------|--------------|---------------|------------------|--------|
| {dimension 1} | — | — | ≥ {threshold} | Ready |
| {dimension 2} | — | — | ≥ {threshold} | Ready |
| {dimension 3} | — | — | ≥ {threshold} | Ready |

**All-pass condition**: all dimensions reach their target thresholds at the same time

---

## Iteration Budget

| Field | Value |
|------|-----|
| Max rounds | {N} |
| Current round | 0 |
| Time limit | {unlimited / N minutes} |
| Budget exhaustion policy | {return best current result / ask the user} |

---

## Output Files

| File | Path | Purpose | Status |
|------|------|---------|--------|
| autoloop-plan.md | {workdir}/autoloop-plan.md | Task plan (this file) | Created |
| autoloop-progress.md | {workdir}/autoloop-progress.md | Iteration progress | To create |
| autoloop-findings.md | {workdir}/autoloop-findings.md | Findings log | To create |
| Final report | {workdir}/ | Final report (file naming follows the unified output naming section in references/loop-data-schema.md) | To create |
| autoloop-results.tsv | {workdir}/autoloop-results.tsv | Structured iteration log (shared by all templates) | To create |

---

## Strategy History (Attempted Methods)

| Round | strategy_id | Dimension | Strategy | Result | Why discarded |
|-------|-------------|-----------|----------|--------|---------------|
| — | — | — | — | — | — |

---

## Change Log

| Time | Field | Before | After | Reason |
|------|------|--------|-------|--------|
| {time} | Initial creation | — | — | — |
