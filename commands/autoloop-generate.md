---
name: autoloop-generate
description: >
  AutoLoop T6: Batch content generation template. Template-driven + parallel generation + per-item quality checks + automatic retries.
  Each generation unit is scored independently, and low-scoring units are regenerated automatically. For the retry cap, see the unified retry rules in references/loop-protocol.md (default: 2 retries).
  Quality gate thresholds are in references/quality-gates.md T6.
  Triggered by /autoloop:generate or any task that requires batch generation of similar content.
---

# AutoLoop T6: Generate — Batch Content Generation

## Execution Prerequisites

Read `autoloop-plan.md` to obtain:
- Content type (report / email / code / data / copy, etc.)
- Variable list (the per-unit changing fields)
- Quantity
- Quality standards (pass criteria are in `references/quality-gates.md` T6)
- Examples (at least 1 user-approved sample)
- Output location (`output_path`; variable name is defined in the unified parameter glossary in `references/loop-protocol.md`)
- File naming rules (`naming_pattern`; variable name is defined in the unified parameter glossary in `references/loop-protocol.md`)

**Round 2+ OBSERVE starting point**: First read the reflection section in `autoloop-findings.md` to get open issues, effective/ineffective strategies, identified patterns, and lessons learned, then scan the current state. See `references/loop-protocol.md` OBSERVE Step 0 for details.

- **Experience registry read**: Read entries in `references/experience-registry.md` that match the current task type and target dimensions, identify strategies marked as "recommended" or "candidate default", and carry them into DECIDE as references

---

## Step 1: Template Standardization

Extract the template structure from the user-provided examples.

Run the `template-extractor` subagent (dispatch rules are in the `template-extractor` section of `references/agent-dispatch.md`):

```
You are the template-extractor subagent.

Task: Analyze the user-provided examples and extract a reusable template structure.

Example content:
{user-provided examples}

Requirements:
1. Identify the fixed parts (shared by all units) and the variable parts (different per unit)
2. Mark variable positions with {{variable_name}}
3. Extract the quality standards (what makes this example "good")
4. Identify common mistakes (what causes the output quality to drop)

Output:
## Template Structure

{extracted template, with variables marked as {{name}}}

## Variable Definitions

| Variable Name | Description | Value Rules | Example |
|---------------|-------------|-------------|---------|
| {{variable_1}} | {description} | {rule} | {example} |

## Quality Standards (Quantifiable)

1. {standard 1}: {how to judge 1-10}
2. {standard 2}: {how to judge 1-10}
3. {standard 3}: {how to judge 1-10}

## Common Mistakes

- {mistake 1}: {how to avoid it}
- {mistake 2}: {how to avoid it}
```

Before batch generation begins, show the template to the user and then automatically proceed to Step 2:

```
I extracted the following template. If you want any adjustments, say so now; otherwise I will automatically proceed to the variable data preparation stage:

{template preview}

Variables: {variable list}
Quality standards: {standards list}
```

---

## Step 2: Variable Data Preparation

Prepare the variable values for each generation unit according to the variable definitions.

If variables come from files or spreadsheets, read and parse them.
If variables need to be inferred, generate them from rules.
If variables need to be provided by the user, list the required inputs and ask for confirmation.

Generate status-tracking rows (write them to `autoloop-results.tsv`, one row per generation unit, recording status and score; for the TSV schema, see the unified TSV Schema section in `references/loop-protocol.md`):

```text
(For TSV format, see the unified TSV Schema in references/loop-data-schema.md, 15 columns)
001  generate  pending_check  score  —  —  baseline  pending_generation  none  —  001  {version}  pending_generation
002  generate  pending_check  score  —  —  baseline  pending_generation  none  —  002  {version}  pending_generation
```

Write variable data into `autoloop-findings.md`, not into TSV. The `details` column in TSV should record only status summaries (for example, "passed after 1 retry"), not variable key-value pairs.

---

## Step 3: Parallel Batch Generation

- **Work order generation**: Use the corresponding role template in `references/agent-dispatch.md` to generate dispatch work orders, filling in task goal, input data, output format, quality standards, scope limits, current round, and context summary

Assign all generation units to `generator` subagents and execute them in parallel (dispatch rules are in `references/agent-dispatch.md`).

Maximum parallelism per batch: 5 units (to avoid quality drops from excessive parallel generation).

Instructions for each `generator` subagent:

```
You are the generator subagent, responsible for generating the following content unit.

Template:
{template content}

Variables for this unit:
- {{variable_1}}: {value}
- {{variable_2}}: {value}

Quality standards:
1. {standard 1} (10 points max)
2. {standard 2} (10 points max)
3. {standard 3} (10 points max)

Common mistakes to avoid:
- {mistake 1}
- {mistake 2}

Requirements:
1. Follow the template structure strictly
2. Integrate the variable values naturally into the content (do not mechanically "fill in blanks")
3. Keep tone and style consistent
4. Self-check after generation to confirm that all quality standards are met

Output format:
---UNIT-START-{unit_id}---
{generated content}
---UNIT-END-{unit_id}---

---QUALITY-{unit_id}---
Standard 1 score: {N}/10 — {reason}
Standard 2 score: {N}/10 — {reason}
Standard 3 score: {N}/10 — {reason}
Overall score: {N}/10
Issues found: {if any}
---QUALITY-END-{unit_id}---
```

---

## Step 4: Per-Item Quality Scoring

After each unit is generated, run an independent `quality-checker` subagent (dispatch rules are in the `quality-checker` section of `references/agent-dispatch.md`).

When scoring, the score, criterion (which anchor range is hit), and evidence (source URL or file line number) must be output at the same time. Ratings missing any one of these are invalid, and that dimension is marked as pending inspection.

```
You are the quality-checker subagent, responsible for independently scoring the following generated content.

Content:
{generated content}

Quality standards:
1. {standard 1}: {scoring guidance}
2. {standard 2}: {scoring guidance}
3. {standard 3}: {scoring guidance}

Scoring rules:
- 8-10: excellent, pass directly
- 7: acceptable, note improvement points
- 5-6: needs improvement, identify the main problems
- 1-4: must be regenerated, explain why

Note: Your score is independent of the generator's self-score. If the difference is > 2 points, your score takes precedence.

Output:
Score: {N}/10 ({pass / needs improvement / regenerate})
Main issues (if any):
- {issue 1}
- {issue 2}
Improvement suggestion: {specific suggestion}
```

---

## Retry Mechanism

For the retry cap, see the unified retry rules in `references/loop-protocol.md` (default: 2 retries). Any unit scoring below the T6 per-unit pass threshold in `references/quality-gates.md` triggers a retry:

**Retry 1**:
- Send the `quality-checker` feedback back to the generator
- Keep the original template and revise only the specific problems

```
The previous generation had the following issues:
{quality-checker feedback}

Keep the overall structure, but focus on improving:
{specific improvement points}
```

**Retry 2 (final retry)**:
- Switch to a different generation strategy
- Regenerate from scratch without referring to the previous version
- If the score is still below the T6 per-unit pass threshold in `references/quality-gates.md`, mark it as "needs manual review" and continue with the other units

---

## Batch Progress Tracking

Continuously update `autoloop-results.tsv` (for the TSV schema, see the unified TSV Schema section in `references/loop-protocol.md`):

```text
(For TSV format, see the unified TSV Schema in references/loop-data-schema.md, 15 columns)
1  generate  pass            score  8.5  —  S01-template-gen  generated from template  none  —  001  {version}  0 retries
1  generate  pass            score  7.2  —  S01-template-gen  generated from template  none  —  002  {version}  1 retry: tone adjusted
1  generate  pending_review  score  6.0  —  S02-rewrite       full rewrite              none  —  003  {version}  still below target after 2 retries
1  generate  pending_check   score  —    —  baseline          pending_generation        none  —  004  {version}  generating
```

Output progress every 10% completion:

```
Progress: {completed}/{total} ({percentage}%)
  Passed: {N} units ({average score}/10)
  Pending retry: {N} units
  Needs manual review: {N} units

Estimated completion time: {estimate}
```

---

## Final Summary

After all units are complete, generate a summary report (file naming is defined in the unified output filename section of `references/loop-protocol.md`):

```markdown
## Batch Generation Completion Report

### Overall Results

| Status | Count | Share |
|--------|-------|-------|
| Passed on first attempt (≥7) | {N} | {%} |
| Passed after retries | {N} | {%} |
| Needs manual review | {N} | {%} |
| **Total** | {total N} | 100% |

Pass rate: {X}% (target threshold is in the pass-rate section of references/quality-gates.md T6)
Average score: {X}/10 (target threshold is in the average-score section of references/quality-gates.md T6)

### Quality Distribution

| Score Range | Count |
|-------------|-------|
| 9-10 | {N} |
| 8-9  | {N} |
| 7-8  | {N} |
| <7   | {N} |

### Common Issues (Top 3)

1. {most common issue}: affected {N} units
2. {second}: affected {N} units
3. {third}: affected {N} units

### Units Requiring Manual Review

| Unit ID | Issue | Suggestion |
|---------|-------|------------|
| {ID}    | {issue} | {suggestion} |

### Output Files

All passed content has been written to: {output_path} (from autoloop-plan.md; variable name is defined in `references/loop-protocol.md`)
```

---

## REFLECT Execution Rules for Each Round

Run after each generated batch finishes (or every 25% of progress). REFLECT must be written to a file and cannot just be done in thinking (see the `references/loop-protocol.md` REFLECT chapter for specifications):

Write the four-layer reflection table into `autoloop-findings.md` (issue registration / strategy review / pattern recognition / lessons learned). The format is shown in `assets/findings-template.md`:

- **Issue Registration**: Record template defects, variable data problems, and anomalous quality scores discovered in this batch
- **Strategy Review**: Effect evaluation of generation strategy / template parameters / quality standards (keep | avoid | to be verified) (for the strategy evaluation enum, see the unified status enum in `references/loop-data-schema.md`)
- **Pattern Recognition**: Which kinds of variable values tend to produce low scores, and which quality standards are the main bottlenecks
- **Lessons Learned**: Summary of what worked for template optimization, generation prompts, and quality evaluation methods
- **Experience write-back**: Write the current round's strategy effects into `references/experience-registry.md` (strategy ID, applicable scenario, effect score, execution context; follow the effect-record table format)

---

## Output File Formats

Choose the output format based on content type:

- **Copy / reports**: Markdown files, with each unit separated by `---`
- **Code**: Separate files, one file per unit
- **Structured data**: TSV or JSON
- **Email**: One Markdown file per email, including Subject / Body / Variables

Write all output files to `{output_path}` (the `output_path` field from `autoloop-plan.md`; variable name is defined in the unified parameter glossary in `references/loop-protocol.md`). Do not use relative paths like `./output/`.
