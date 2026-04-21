---
name: autoloop-compare
description: >
  AutoLoop T2: multi-option comparison template. Multi-dimensional scoring + evidence support + confidence statements + explicit recommendation.
  Each option is analyzed independently with unified scoring dimensions, sensitivity checks, and a decision matrix.
  Quality gate thresholds are in references/quality-gates.md T2.
  Triggered by /autoloop:compare or any task that requires deciding among multiple options.
---

# AutoLoop T2: Compare — Multi-Option Comparison

## Execution Prerequisites

Read `autoloop-plan.md` to obtain:
- The list of options to compare (must be at least 2)
- The list of evaluation dimensions (can be generated automatically)
- Weight configuration, if the user specified priorities
- `key_assumptions` (structured list: assumption name + current value + unit)

**Round 2+ OBSERVE starting point**: first read the reflection section in `autoloop-findings.md` to get open issues, effective/ineffective strategies, identified patterns, and lessons learned, then scan the current state. See `references/loop-protocol.md` OBSERVE Step 0.

- **Experience registry read**: read entries in `references/experience-registry.md` that match the current task type and target dimensions, identify strategies marked as "recommended" or "candidate default", and carry them into DECIDE as references

---

## Default Evaluation Dimensions

The default evaluation dimensions and weights are in the default evaluation dimensions section of `references/quality-gates.md` T2. User-defined dimensions and weights in the plan take precedence.

---

## Round 1: Parallel Option Analysis

### OBSERVE (Round 1 baseline collection)

There is no historical data in Round 1. Collect the baseline: current issue count = 0, all quality-gate scores = 0.
Write this as iteration 0 baseline into `autoloop-progress.md`. See the Round 1 Bootstrap rules in `references/loop-protocol.md`.

### 1.1 Assign an Independent Subagent to Each Option

- **Work order generation**: use the corresponding role template in `references/agent-dispatch.md` to generate dispatch work orders, filling in task goal, input data, output format, quality standards, scope limits, current round, and context summary

Assign **2 independent option-analyzer subagents per candidate option** for parallel analysis (using different analysis-angle prompts).

This ensures the bias-check gate is reachable: at least 2 independent subagents evaluate each option. See the bias-check calculation in the T2 bias-check section of `references/quality-gates.md`. Subagent dispatch rules are in the option-analyzer section of `references/agent-dispatch.md`.

Instructions for each analyzer subagent:

```
You are an option-analyzer subagent, responsible for deep analysis of the following option:

Option name: {Option A}
Comparison topic: {topic}
Evaluation dimensions: {dimension list}
Analysis angle: {positive analysis / critical analysis} (the two subagents for the same option must use different angles)

Task: Perform deep analysis of this option for each evaluation dimension.

Requirements:
1. Every dimension must be backed by specific evidence (data, citations, examples)
2. Identify the core strengths (maximum 3)
3. Identify the core weaknesses / risks (maximum 3)
4. Identify the most suitable use cases
5. Identify the least suitable use cases

Output format:
## Option Analysis: {option name}

### Dimension Scores

| Dimension | Score (1-10) | Evidence Summary | Source |
|------|------------|---------|------|
| {dimension 1} | {N} | {short evidence} | {URL} |

### Core Strengths
1. {Strength 1}: {specific explanation with data support}
2. {Strength 2}: ...
3. {Strength 3}: ...

### Core Weaknesses / Risks
1. {Weakness 1}: {specific explanation, impact assessment}
2. {Weakness 2}: ...

### Use Cases
✓ Suitable: {scenario description}
✗ Not suitable: {scenario description}

### Real User Feedback
(from Reddit / Stack Overflow / Hacker News, etc.)
- "{quote}" (source: {URL})

### Overall Score (before weighting)
Total: {X}/10, confidence: {N}% (based on {N} sources)
```

### 1.2 Bias Check (run immediately after all analyzers return)

See the bias-check section in `references/quality-gates.md` T2 for the calculation method.

Quality gate thresholds are in the T2 bias-check section of `references/quality-gates.md` (trigger conditions and pass criteria). In short: compare the two analyzer scores for each option; if the difference exceeds the threshold, launch a third independent analyzer to re-evaluate that option and use the majority conclusion.

### 1.3 Independent Neutral Review

After all option analyses are complete, run a neutral-reviewer subagent (dispatch rules in `references/agent-dispatch.md` neutral-reviewer section):

```
You are a neutral-reviewer responsible for checking whether the analysis contains bias.

Read the analysis results for all options and check:
1. Whether any score is clearly abnormal (one option is ≥9 or ≤3 across all dimensions)
2. Whether evidence quality is balanced (whether one option cites more authoritative sources)
3. Whether selective citation is happening (only citing information favorable to one option)
4. Whether scoring standards are consistent (whether equal-level findings are scored the same across options)

Output:
- Bias risk assessment (low / medium / high)
- Dimensions that need re-evaluation, if any
- Suggested opposing evidence to add, if any
```

---

## Round 2: Weighted Scoring + Sensitivity Analysis

### 2.1 Weighted Calculation

```
Overall score = Σ (dimension score × dimension weight)
```

User-defined weights take precedence; default weights come second.

Compute the weighted score for each option and generate the ranking.

### 2.2 Sensitivity Analysis

Sensitivity analysis reads the key assumptions list from the `key_assumptions` field in `autoloop-plan.md` (structured format: assumption name + current value + unit). If the plan does not provide assumptions, automatically infer cost / time / scale dimensions from the evaluation dimensions as assumption sources.

See `references/quality-gates.md` T2 sensitivity analysis section for the calculation method. Pass criteria: after any single assumption changes by ±20%, the top recommended option must remain the same. The full calculation rules are defined in quality-gates.md and are not redefined here.

```
Sensitivity test (assumptions come from plan.key_assumptions):

For each key assumption H (read the structured list from plan.key_assumptions):
  Scenario H+: H × 1.2 → recompute ranking → compare with original ranking
  Scenario H-: H × 0.8 → recompute ranking → compare with original ranking

Example output:
Scenario 1 ({assumption name} ×1.2):
  Ranking: {option} first, margin {X}

Scenario 2 ({assumption name} ×0.8):
  Ranking: {option} first, margin {X}

(Repeat the ±20% test above for every assumption in key_assumptions)

Conclusion:
- Recommendation robustness: {high / medium / low} (high means the same option wins in all ±20% scenarios)
- Critical assumption: {the assumption with the biggest impact on the result}
```

---

## Comparison Matrix Generation

Generate the full comparison matrix:

```markdown
## Comprehensive Comparison Matrix

| Dimension (weight) | {Option A} | {Option B} | {Option C} |
|------------|---------|---------|---------|
| Feature fit (25%) | 8/10 ✓ | 7/10 | 6/10 |
| Technical maturity (20%) | 9/10 ✓ | 8/10 | 7/10 |
| Learning curve (15%) | 5/10 | 8/10 ✓ | 7/10 |
| Community ecosystem (15%) | 9/10 ✓ | 7/10 | 5/10 |
| Cost (15%) | 4/10 | 7/10 ✓ | 9/10 |
| Long-term risk (10%) | 8/10 ✓ | 7/10 | 6/10 |
| **Weighted total** | **7.5** | **7.3** | **6.7** |
| **Rank** | **#1** | **#2** | **#3** |

Note: ✓ marks the best option for that dimension
```

---

## Recommended Output Format

```markdown
## Recommendation

### Main Recommendation: {Option A}
Confidence: {N}% ({based on N sources})

**Why this is recommended**:
{Option A} ranks first across the core dimensions (feature fit, technical maturity, community ecosystem),
with a weighted score of 7.5/10, leading the second-place option by 0.2 points.

Main strengths:
1. {Strength 1} (data support: {source})
2. {Strength 2}
3. {Strength 3}

Main risks:
1. {Risk 1} (mitigation: {measure})
2. {Risk 2}

### When to Use

✓ **Choose {Option A} when**:
- {condition 1}
- {condition 2}

✓ **Choose {Option B} when**:
- {condition 1} (especially {scenario})

### Gap Analysis

The gap between Option A and B is only 0.2 points, so the result is not robust (the recommendation flips if the cost weight increases by 10%).
**Suggestion**: if cost constraints are strict, re-evaluate A vs B.

### Why the Others Are Not Recommended

{Option C}: {specific reason, not a vague "worse than the others"}

---

## Evidence Limitations

The following information could not be fully verified and may affect the conclusion:
- {information gap 1} (affected dimension: {dimension}, impact: medium)
- {information gap 2}

Recommended verification before final decision: {specific verification suggestion}
```

---

## Result File

Generate `autoloop-results.tsv` (TSV format in the unified TSV schema section of `references/loop-protocol.md`):

```tsv
 (15-column TSV format in references/loop-data-schema.md unified TSV schema)
iteration	phase	status	dimension	metric_value	delta	strategy_id	action_summary	side_effect	evidence_ref	unit_id	protocol_version	details
1	compare	pass	feature fit	8	—	S01-option-analysis	parallel dual-analyzer evaluation	none	F001	Option A	1.0.0	weight 0.25, 3 evidence items
1	compare	pass	technical maturity	9	—	S01-option-analysis	parallel dual-analyzer evaluation	none	F002	Option A	1.0.0	weight 0.20, 5 evidence items
1	compare	pass	feature fit	7	—	S01-option-analysis	parallel dual-analyzer evaluation	none	F003	Option B	1.0.0	weight 0.25, 2 evidence items
```

Evidence source URLs and detailed analysis belong in `autoloop-findings.md`, not in `results.tsv`.

---

## Quality Gate Checks

See the full gate definitions and pass criteria in `references/quality-gates.md` T2. Before outputting the final recommendation, verify:

The CHECK stage is scored by an independent compare-evaluator subagent (dispatch rules in the `references/agent-dispatch.md` independent scorer section). The compare-evaluator receives only the comparison artifacts, not the execution process, and performs blind scoring against the anchors in quality-gates.md.
