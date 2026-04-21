# Loop Data Schema — data format and vocabulary specifications

> Data layer specification separated from loop-protocol.md. See `loop-protocol.md` for state machine and OODA phase definitions.

### Version semantic definition (only authoritative)

| Level | Trigger Condition | Example | Direction |
|------|---------|------|------|
| major (X.0.0) | Changes to the cycle process structure | Addition or deletion of stages, adjustment of stage order | Incremental only |
| minor (0.X.0) | Access control/dimension/parameter changes | Add scoring dimensions, modify thresholds, adjust weights | Incremental only |
| patch (0.0.X) | Calibration data changes | Anchor samples, strategy experience, score calibration | Incremental only |

**Non-decreasing rule**: The version number can only be incremented, not decremented. Rollback is implemented by incrementing the version number (for example, 1.2.3 rollback → 1.3.0).
Rollback record format: `{new_version} (rollback from {old_version}, reason: {reason})`

> See evolution-rules.md for change history.

## Unified parameter vocabulary

**Rule**: When the following concepts are involved in all AutoLoop files (commands/, references/, assets/), the variable names in the table below must be used, and synonyms are not allowed to be invented.

| Variable name | Type | Purpose | Collection timing | Applicable templates |
|--------|------|------|---------|---------|
| deploy_target | string | Deployment target host/environment (such as sip-server, prod-01) | plan | T4 |
| deploy_command | string | Deployment execution command (complete command, such as gcloud compute ssh...) | plan | T4 |
| service_list | string[] | Service name list (such as [sip-backend, sip-worker]) | plan | T4 |
| service_count | int | Number of services (automatically calculated = len(service_list), do not fill in manually) | Automatic | T4 |
| health_check_url | string | Health check URL (such as https://example.com/api/health) | plan | T4 |
| acceptance_url | string | Online acceptance URL (such as https://example.com) | plan | T4 |
| doc_output_path | string | Plan document output directory (absolute path) | plan | T4 |
| syntax_check_cmd | string | Syntax check command (such as python3 -m py_compile {file} or npx tsc --noEmit) | plan | T4/T7/T8 |
| syntax_check_file_arg | boolean | Whether the syntax check command accepts single file arguments (python3 -m py_compile → true; npx tsc --noEmit → false) | plan | T4/T7/T8 |
| new_router_name | string | The name of the new router variable this time (such as comments_router; fill in N/A if there is no new route) | plan | T4 |
| main_entry_file | string | Absolute path of the main entry file (such as /project/backend/main.py or /project/src/app.ts) | plan | T4/T7 |
| output_path | string | Absolute path to the output directory (default `{work_dir}/autoloop-output/`) | plan | T6 |
| naming_pattern | string | File naming rules (such as {template_name}-{index}.md) | plan | T6 |
| key_assumptions | list[{name, current_value, unit}] | Key assumptions in T2 comparison (structured list, each item contains name + current value + unit, used for sensitivity analysis) | plan | T2 |
| migration_check_cmd | string | Database migration status verification command (such as python -m alembic current && python -m alembic check; fill in N/A if there is no migration) | plan | T4 |
| frontend_dir | string | Absolute path to the front-end code directory (such as /project/frontend) | plan | T4 |

---

## Unified status enumeration

All documents referring to issue status and policy evaluation must use the following enumeration values ​​and no other terms may be used.

**Problem Status**:
```
Newly discovered | Fixed | Pending | Cross-round carryover
```

**Strategy Rating**:
```
Keep | Avoid | Pending Verification
```

---

## Unified output file naming rules (standard source)

All documents must reference this table when citing the final report file name and may not redefine it in other documents.

| Template | Final report file name | Process file |
|------|--------------|---------|
| T1 Research | `autoloop-report-{topic}-{date}.md` | plan + findings + progress + results.tsv |
| T2 Compare | `autoloop-report-{topic}-{date}.md` | Same as above |
| T5 Iterate | `autoloop-report-{topic}-{date}.md` | Same as above |
| T6 Generate | `{output_path}/{naming_pattern}` (generated content) + `autoloop-report-{topic}-{date}.md` (summary report) | Same as above |
| T4 Deliver | `autoloop-delivery-{feature}-{date}.md` | Same as above |
| T7 Quality | `autoloop-audit-{date}.md` | Same as above |
| T8 Optimize | `autoloop-audit-{date}.md` | Same as above |

where `{date}` = `YYYYMMDD`, `{topic}` / `{feature}` are extracted from the one-sentence target of plan (spaces replaced with `-`, lowercase).

---

## Unified TSV Schema (standard source)

All templates written to `autoloop-results.tsv` must use the following uniform column structure and must not be redefined in other files.

```
iteration	phase	status	dimension	metric_value	delta	strategy_id	action_summary	side_effect	evidence_ref	unit_id	protocol_version	score_variance	confidence	details
```

| Column | Description | Example |
|---|---|---|
| iteration | iteration number (starting from 1) | 1 |
| phase | Phase or substep identifier | scan / generate / compare |
| status | Status (inspection result enumeration): passed / failed / pending inspection / pending review | passed |
| dimension | score dimension name | security / coverage / score |
| metric_value | Metric value (number or percentage) | 8.5 / 85% |
| delta | Changes from the previous round (fill in — in the first round) | +1.2 |
| strategy_id | The strategy identifier used in this round (consistent with the findings.md strategy evaluation table) | S01-sql-scan |
| action_summary | Summary of specific execution actions | Scan all SQL splices and replace them with parameterization |
| side_effect | Impact on other dimensions (if there are no side effects, fill in "None") | Maintainability-0.5 |
| evidence_ref | Evidence reference (issue ID in findings.md) | S001, R003 |
| unit_id | T2 option name/T6 unit number (fill in — for other templates) | option A / 001 / — |
| protocol_version | Current protocol version number | 1.0.0 |
| score_variance | Multiple evaluator score variance (fill in 0 for single evaluator) | 0.5 |
| confidence | Rating confidence percentage | 85% |
| details | Supplementary instructions | First round of baseline collection |

**Usage convention (at each template row granularity)**:

- T1/T5/T4/T7/T8: **one row per dimension** per round, ensuring that score changes and strategic attribution of each dimension can be tracked
- T2 Compare: One row per dimension per option in each round, `unit_id` = option name
- T6 Generate: One row per generation unit, `unit_id` = generation unit ID (001/002/...), `dimension` = `score`
- strategy_id must be consistent with the strategy name in the strategy evaluation table in findings.md
- The side_effect field is mandatory (if there is no side effect, fill in "None")
- During the first round of baseline collection, fill in "baseline" for strategy_id and "baseline measurement" for action_summary

Additional raw data (variable values, evidence sources, etc.) is written to `autoloop-findings.md` and not placed in results.tsv.

### Cross-file primary key specification

All AutoLoop output files (results.tsv, findings.md, progress.md, plan.md) share the following primary key system to ensure cross-file traceability and joinability:

| Primary Key | Format | Definition Timing | Through File |
|------|------|---------|---------|
| iteration | integer (incrementing from 1) | auto-increment at the start of each round | all four files |
| strategy_id | `S{NN}-{short-description}` | named in the DECIDE stage | All four files |
| problem_id | `{dimension_abbrev}{NNN}` (such as `S001`) | named when the finding is created | findings + results.tsv |
| dimension | exactly the same as quality-gates.md dimension name | quality-gates.md definition | results.tsv + findings |

**Quotation Rules**:
- the evidence_ref of results.tsv must refer to the problem_id defined in findings.md
- progress.md Each round of records must have the iteration number in the title
- The strategy_id of plan.md strategy history must be consistent with the findings.md strategy evaluation table
- Dimension names appearing in any file must match quality-gates.md exactly, no synonyms are allowed

---

## Bootstrap rules (executed immediately after plan is completed)

**As soon as the plan wizard completes, the following files are created (without waiting for round 1 of OBSERVE):**

```
1. autoloop-plan.md (created by the wizard)
2. autoloop-findings.md (includes: executive summary, discovery record of each round, engineering problem list, information gap summary, expansion direction, strategy evaluation, pattern recognition, lessons learned)
3. autoloop-progress.md (includes: quality access control overview, baseline record, 8-stage iteration loop for each round, task completion record, strategy history)
4. autoloop-results.tsv (write the header line: iteration\tphase\tstatus\tdimension\tmetric_value\tdelta\tstrategy_id\taction_summary\tside_effect\tevidence_ref\tunit_id\tprotocol_version\tscore_variance\tconfidence\tdetails)
```

All 4 files must exist before round 1 of OBSERVE begins. After creation, update the status from "To be created" to "Created" in the "Output files" table of autoloop-plan.md.

### SSOT optional mode

When `autoloop-plan.md` is set to `ssot_mode: true` , structured single source of truth mode is enabled:

- **Data source**: `autoloop-state.json` (JSON format), contains all data of plan/iterations/findings/results
- **Write operation**: All status changes are written to JSON through `scripts/autoloop-state.py`, and the MD file is not edited directly.
- **Rendering**: Run `scripts/autoloop-render.py` at the end of each round to generate 4 readable MD files from JSON
- **Read operation**: MD files can still be read in the OBSERVE stage (synchronized with JSON after rendering)
- **Backward Compatibility**: When `ssot_mode` is not set, the behavior is completely unchanged and 4 MD files are read and written directly.
- **Advantages**: Eliminate duplication and inconsistency of information across files, support `query` command to quickly retrieve any field
- **Initialization**: Use `autoloop-state.py init` instead of `autoloop-init.py`, automatically create JSON + 4 MDs

---

## autoloop-state.json migration (plan.gates aligned with scorer)

**Background**: `autoloop-score.py` uses the same internal dimension key as `gate-manifest.json` (such as `syntax_errors` → `syntax`). `plan.gates[].dim` must be consistent with `dimension` of the scoring JSON; each gate suggestion contains `manifest_dimension` (manifest original name) for comparator to check back.

**If your state is earlier than the above convention** (`plan.gates` is empty, `manifest_dimension` is missing, or `dim` still writes `syntax_errors` / `p1_count` and other manifest original names):

1. **Recommendation**: Delete `autoloop-state.json` in the working directory (and clean the checkpoint as needed) and re-execute it.
`python3 scripts/autoloop-state.py init <work_dir> <template T1-T8> "<goal>"`
Will automatically write to `plan.gates` aligned with scorer.
2. **Keep history**: Manually change the `dim` of each gate to the internal key mapped with `gate-manifest.json` through `_MANIFEST_DIM_MAP`, and add `manifest_dimension`; you can refer to the structure in the newly generated state.
3. **Check**: `python3 scripts/autoloop-validate.py <work_dir>` reports a **warning** (non-fatal) for legacy conventions; this is upgraded to **error** when `--strict` or `AUTOLOOP_VALIDATE_STRICT=1` is used.
4. **Preview migration**: `python3 scripts/autoloop-state.py migrate <work_dir> --dry-run` prints the `plan.gates` JSON recommended by SSOT for the current template (do not modify the file).

---

## plan.gates field convention (canonical)

| Field | Required | Description |
|------|------|------|
| `dim` | Yes | Consistent with `dimension` output by `autoloop-score` (internal key) |
| `manifest_dimension` | Strongly recommended | The original `dimension` string of the entry in `gate-manifest.json` |
| `threshold` / `target` | Depending on the template | T5, etc. can be `threshold: null` + `target` |
| `gate` / `label` / `comparator` / `unit` | View template | Consistent with manifest |

**Deprecated**: Only write `dimension` instead of `dim` — an error will be reported in validate strict mode.

---

## Stage products (for validate/automated verification)

| Current last round `iterations[-1].phase` | Minimum product (SSOT) | validate behavior |
|--------------------------------|------------------|----------------|
| `OBSERVE` … `DECIDE` | No additional compulsory (no scores in the first round) | — |
| `ACT` and later | `plan.decide_act_handoff.strategy_id` **or** `iterations[-1].strategy.strategy_id` (`SNN-description`) | strict → error, otherwise warn |
| `SYNTHESIZE` / `EVOLVE` / `REFLECT` (after entering VERIFY) | `iterations[-1].scores` is not empty | strict→error, otherwise warn |
| `REFLECT` | `iterations[-1].reflect` is structured JSON (including at least one valid value such as `strategy_id` / `effect` / `lesson_learned`) | strict→error, otherwise warn |

| Others | Description |
|------|------|
| DECIDE | `plan.decide_act_handoff` (`strategy_id`, `hypothesis`, `planned_commands`) |
| VERIFY | `iterations[-1].scores`; `plan.gates[].current` / `status` |
| checkpoint | If `checkpoint.json` exists, `current_phase` should be consistent with `iterations[-1].phase` |

**DECIDE→ACT handover SSOT**: The policy handover field is **only** written in `plan.decide_act_handoff` of `autoloop-state.json` (and the `strategy` mirror within the iteration); `checkpoint.json` **does not** carry `hypothesis` / `planned_commands` to avoid double sources. Validation and automation should be based on state.

`autoloop-validate.py --strict` upgrades the strict row in the above table to error.

---

## metadata field (SSOT)

### `metadata.last_error`

Child process failure or timeout is written by `run_tool` of `scripts/autoloop-controller.py` (when `autoloop-state.json` is present and the caller passes in `work_dir`).

| Field | Type | Description |
|------|------|------|
| `time` | string (ISO8601) | recording time |
| `script` | string | Script file name (such as `autoloop-validate.py`) |
| `returncode` | int | Exit code; timeout is `124` |
| `stderr` | string | Truncated standard error (up to about 500 characters) |

### `metadata.audit[]`

Audit rows appended by time, the elements are objects, **at least** contain `time`, `event`.

| `event` | Description | Typical additional fields |
|---------|------|----------------|
| `phase_complete` | Stage advancement | `detail` (string, compatible with old format) |
| `tool_start` | Subtool is about to be executed | `script`, `argv` (string list), `work_dir` |
| `tool_finish` | The subtool has ended (including non-zero exit) | `returncode`, `timeout` (bool), `stderr` (interception) |
| `tool_timeout` | Subtool timeout | `returncode`(124), `timeout`(true) |

---

## plan.template_mode delivered with T4 (P2-04)

| Field | Type | Default | Description |
|------|------|------|------|
| `plan.template_mode` | string | `ooda_rounds` | `ooda_rounds`: The termination condition is consistent with manifest `default_rounds`. `linear_phases`: When the budget under T4 is exhausted, if `linear_delivery_complete` is still false, the controller EVOLVE **pauses** instead of successfully terminating to avoid accidental stopping based on OODA rounds alone. |
| `plan.linear_delivery_complete` | boolean | `false` | Manually set to `true` after all delivery phases 1-5 are complete (see `references/delivery-phases.md`). |

---

## findings entry canonical field (P3-07)

| Field | Role |
|------|------|
| `summary` | **Recommendation**: short summary (list/rendering is displayed first) |
| `content` | Detailed text (optional) |
| `description` | Compatible with `content` alternative old data |

- All three are empty: `autoloop-validate` **warn** (`render`/`score` may skip this item).
- Contains both `summary` and `content`: **warn** (it is recommended that summary be a short canonical sentence and content be long text).
- `autoloop-score` When counting credibility/completeness, URL and source scanning will merge `source` with the above text (`summary`→`content`→`description`).

---

## Scoring Confidence Stratification (P1-05 Scoring Confidence)

`autoloop-score.py` Rating results for each dimension now include `confidence` and `margin` fields, indicating how trustworthy the rating is.

### Access control result extension field

| Field | Type | Description |
|------|------|------|
| `confidence` | string | Confidence level: `empirical` / `heuristic` / `binary` |
| `margin` | float \| null | Error range (absolute value); `null` for `binary` |

### Three-level confidence rules

| Level | Margin | Trigger conditions | Typical dimensions |
|------|--------|----------|----------|
| `empirical` | ≤ 0.3 | Rating based on actual tool output (syntax_check_cmd results, test pass rate, lint error count, health check URL responses, etc.) | `syntax`, `p1_p2_issues`, `service_health`, `p1_all`, `security_p2`, `reliability_p2`, `maintainability_p2` |
| `heuristic` | ≤ 1.5 | Scoring based on content analysis pattern matching (source count, keyword coverage, text pattern matching, review score, etc.) | `coverage`, `credibility`, `consistency`, `completeness`, T7/T8 review score, T3 design category |
| `binary` | null | Can only pass/fail, no quantitative tool support | `bias_check`, `user_acceptance` |

### Stasis detection adaptation

`autoloop-controller.py` of `detect_stagnation` uses margin to adjust the stall threshold:

- **empirical** (margin=0.3): retain existing fixed threshold (usually ≥ 0.3)
- **heuristic** (margin=1.5): The threshold is enlarged to `max(fixed_threshold, margin)` to prevent small fluctuations within the error range from being misjudged as stagnation.
- **binary** (margin=null): only look at the direction (overall improvement/deterioration), without numerical comparison

### Task termination quality summary

When the task terminates (`stop` or `pause`), the EVOLVE stage outputs a summary of the quality assessment for each dimension:

```text
Dimensions | Current | Goal | Confidence | Error | Confidence Statement
```

The `heuristic` and `binary` dimensions will be marked with "Manual review recommended" to help Kane quickly determine which scores are credible and which require additional verification.

---

## OODA stage output Schema (P2-17)

Each OODA stage must output the following fields. The controller prompts for required fields in the stage prompt, `autoloop-validate.py --phase-output <phase>` can be verified.

### OBSERVE output (write to progress.md)

| Field | Type | Required | Description |
|------|------|------|------|
| current_scores | dict[str, float] | Yes | Current scores of each dimension |
| target_scores | dict[str, float] | Yes | Target scores for each dimension |
| remaining_budget_pct | float | yes | remaining budget percentage |
| focus_dimensions | list[str] | Yes | Focus dimensions of this round |
| carry_over_issues | list[str] | No | carryover issues |

### DECIDE output (write to progress.md)

| Field | Type | Required | Description |
|------|------|------|------|
| strategy_id | str | yes | `S{NN}-{description}` format |
| action_plan | list[str] | Yes | Specific action list |
| fallback | str | yes | fallback strategy |
| impacted_dimensions | list[str] | yes | Dimensions that may be affected |

### ACT output (write state.json iterations[-1].act)

| Field | Type | Required | Description |
|------|------|------|------|
| subagent_results | list | yes | subagent execution results |
| completion_ratio | int | yes | completion percentage 0-100 (P2-10) |
| failure_type | str | no | failure type enumeration (P2-12) |
| discoveries | list[str] | No | Instant discovery (P2-15) |

### VERIFY output (write state.json iterations[-1].scores)

| Field | Type | Required | Description |
|------|------|------|------|
| scores | dict[str, ScoreResult] | Yes | Contains confidence (P1-05) |
| regression_detected | bool | yes | whether regression is detected |

---
