# Quality Gates — Quality Gate Specification

## Overview

Quality gates are the **primary termination criterion (success path)** for AutoLoop iterations. This document defines the quality gates for all task types, including calculation methods, scoring rules, and pass criteria.

**Termination hierarchy**:
1. **All quality gates met** → terminate successfully (preferred path)
2. **User interruption** → pause, save progress, resumable
3. **Budget exhausted (maximum rounds reached)** → output the current best result and clearly mark unmet items
4. **Unable to continue** → report to the user, explain the reason, and specify what information is needed

Quality gates determine successful termination; budget exhaustion, interruption, and inability to continue are alternative termination paths, all of which are fully handled in `references/loop-protocol.md`.

**Core principle**: Quality gates must be **quantified and measurable**. Descriptions like "almost done" are not acceptable.

## Scoring Semantics Glossary (authoritative for all files)

AutoLoop uses 4 distinct scoring concepts with different semantics. They must not be mixed:

| Concept | English identifier | Type | Range | Meaning | Usage scenario |
|------|---------|------|---------|------|---------|
| Quality score | quality_score | Continuous value | 0-10 (1 decimal place) | The current quality level of a dimension | `metric_value` column in TSV; threshold comparisons in the gate evaluation matrix |
| Confidence | confidence | Percentage | 0-100% (integer) | The reliability of the score itself | `confidence` column in TSV; fail-closed decisions |
| Severity | severity | Enum | P1 / P2 / P3 | The impact level of a discovered issue | Deduction rules in `enterprise-standard.md`; gate counting conditions |
| Gate status | gate_status | Enum | **Met / Not Met / Exempt** (aligned with `gate_status_enum` in `gate-manifest.json`; `plan.gates[].status` in SSOT JSON uses these three terms) | Final gate decision | Gate evaluation matrix; termination decision |

**No-mixing rules**:
- `quality_score` must not be used to express confidence ("this score is high quality" should use `confidence`)
- `severity` must not replace `quality_score` (`P1/P2/P3` are issue classifications, not scores)
- Low `confidence` ≠ low `quality_score` (quality may be high but evidence may be insufficient)
- `gate_status` is determined jointly by `quality_score` + threshold comparison + counting conditions, and must not be assigned independently

**Cross-file consistency**: Whenever AutoLoop files use these 4 concepts, they must use the English identifiers or the exact concept names in the table above. Do not use synonyms that blur the distinction between concepts.

---

## General Scoring Rules (applies to all templates)

**Evidence requirement**: Every score must output score, rationale, and evidence together. A score missing any of the three is invalid.

```text
Scoring output format:
- Score: {number}
- Rationale: matched {specific item} in the {range}
- Evidence: {file path + line number} or {source URL + quoted paragraph}
A score without evidence is treated as failed (fail-closed). That dimension must be re-scored in the next round after adding evidence. Missing evidence is not "skip"; it forces the system to reflect, discover clues, and identify issues before proceeding.
```

**Universal score anchors**:

| Range | Meaning | Rationale requirement |
|------|------|---------|
| 1-3 | Clear defects | List what is missing and what is wrong |
| 4-6 | Partially satisfied | List what exists and what is still missing |
| 7-8 | Basically satisfied | List which standards are satisfied |
| 9-10 | Excellent | List the concrete aspects that exceed expectations |

**Scoring disagreement arbitration protocol** (the only arbitration rule, applies to all templates):

```text
Arbitration trigger: the difference in quality_score between multiple evaluators on the same dimension is >= 2.0
Arbitration process:
  1. Use the lower score as the quality_score for the current round
  2. Record the variance in the TSV `score_variance` column
  3. Mark the TSV `details` column with "Disagreement arbitration: {evaluator_1}={score_1}, {evaluator_2}={score_2}"
  4. OBSERVE in the next round must list this disagreement as a priority item
  5. If there is a third independent evaluator, use the 2/3 majority opinion

Cases that do not trigger arbitration:
  - Difference < 2.0 → use the average, no arbitration required
  - Single evaluator → variance = 0, no arbitration required
```

**Scoring confidence calculation**:

```text
Confidence = f(amount_of_evidence, evaluator_consistency)
- Evidence >= 3 items + variance < 1.0 → high confidence (>= 80%)
- Evidence 1-2 items + variance < 2.0 → medium confidence (50-79%)
- Evidence 0 items or variance >= 2.0 → low confidence (< 50%) → fail-closed (treated as failed)
```

Low-confidence scores are handled the same as scores with missing evidence: treated as failed, and must be re-scored in the next round after adding evidence or increasing evaluator count.

**Script alignment**: The fail-closed rules for the last TSV row `score_variance` / `confidence` are shared by `autoloop-variance.py check`, EVOLVE in `autoloop-controller.py`, and `autoloop_kpi.results_tsv_last_row_fail_closed`. In SSOT mode, `overall_pass` from `autoloop-score.py --json` also includes fail-closed on the last row (`gates_pass` and `overall_pass` remain separate), avoiding the dual-interpretation confusion of "the score script passed but EVOLVE still rejects convergence."

### Cross-model scoring consistency mechanism

When multiple LLM evaluators are used:
- **Structured rubric**: the prompt must include the full anchor table from this document
- **Blind review**: each evaluator scores independently and cannot see the others; T7/T8 recommend >= 2 models
- **Late aggregation**: aggregate only after all evaluations are complete (at the end of VERIFY), with no information exchange during execution
- **Debiasing**: in T2, different evaluators assess options in different orders; apply the same principle when dimensions >= 5

---

## Gate Classification Overview

### Definitions
- **Hard Gate**: failure = the entire round fails and must be fixed in the next round before proceeding
- **Soft Gate**: failure = record it in `progress.md` + `findings.md`, but it does not block termination

### Full template × full dimension matrix

| Template | Dimension | Threshold | Gate type | Failure behavior |
|------|------|------|---------|---------|
| T1 Research | Coverage | >= 85% | Hard | Entire round fails; missing dimension content must be added next round |
| T1 Research | Credibility | >= 80% | Hard | Entire round fails; independent sources must be added next round |
| T1 Research | Consistency | >= 90% | Soft | Record in `progress.md` + `findings.md`; does not block termination |
| T1 Research | Completeness | >= 85% | Soft | Record in `progress.md` + `findings.md`; does not block termination |
| T2 Compare | Coverage | 100% | Hard | Entire round fails; every option must have content for every dimension |
| T2 Compare | Credibility | >= 80% | Hard | Entire round fails; independent sources must be added next round |
| T2 Compare | Bias Check | all options pass (bool) | Hard | Entire round fails; trigger a third independent `option-analyzer` |
| T2 Compare | Sensitivity Analysis | top recommendation remains unchanged after `key_assumptions` +/-20% | Soft | Record in `progress.md` + `findings.md`; does not block termination |
| T5 Iterate | KPI reaches target | target threshold defined by the user in plan | Hard | Entire round fails; continue iterative optimization |
| T6 Generate | Pass Rate | >= 90% | Hard | Entire round fails; fix the failed content items next round |
| T6 Generate | Average Score | >= 7/10 | Hard | Entire round fails; improve content quality next round |
| T4 Deliver | Syntax Validation | zero errors | Hard | Entire round fails; syntax errors must be fixed next round |
| T4 Deliver | P1/P2 issues | = 0 | Hard | Entire round fails; security/reliability issues must be fixed next round |
| T4 Deliver | Human Acceptance | user input `"User confirmation (online acceptance)"` | Hard | Entire round fails; wait for user online acceptance confirmation |
| T4 Deliver | Service Health Check | every item in `service_list` is `active` + health 200 | Soft | Record in `progress.md`; N/A may be skipped; does not block termination |
| T7 Quality | Security Score | >= 9/10 | Hard | Entire round fails; the security score must improve next round |
| T7 Quality | Reliability Score | >= 8/10 | Hard | Entire round fails; the reliability score must improve next round |
| T7 Quality | Maintainability Score | >= 8/10 | Hard | Entire round fails; the maintainability score must improve next round |
| T7 Quality | P1 Issues (all dimensions) | = 0 | Hard | Entire round fails; all P1 issues must be fixed next round |
| T7 Quality | Security P2 Issues | = 0 | Hard | Entire round fails; all security P2 issues must be fixed next round |
| T7 Quality | Reliability P2 Issues | <= 3 | Soft | Record in `progress.md` + `findings.md`; does not block termination |
| T7 Quality | Maintainability P2 Issues | <= 5 | Soft | Record in `progress.md` + `findings.md`; does not block termination |
| T8 Optimize | Architecture | >= 8/10 | Hard | Entire round fails; architecture issues must be fixed next round |
| T8 Optimize | Performance | >= 8/10 | Hard | Entire round fails; performance issues must be fixed next round |
| T8 Optimize | Stability | >= 8/10 | Hard | Entire round fails; stability issues must be fixed next round |

### Decision rules (rollup and `plan.gates[].status`)

The terms below must remain consistent with the `gate_status` glossary above: **Met / Not Met / Exempt**. The `status` column in `autoloop-results.tsv` belongs to the **check result** enum layer (`Pass / Fail / Pending Check / Pending Review`) and is **not** the same layer as `plan.gates[].status` in SSOT. Do not mix them.

- If all hard gates have **status = Met** (or Exempt), and soft-gate failures have been recorded in `progress` / `findings` → **the hard-gate path for this round is considered eligible to enter successful termination evaluation** (soft-gate leftovers are tracked separately)
- If any hard gate has **status = Not Met** → **rollup for this round = Not Met** (regardless of whether soft-gate failures were recorded)
- If any soft gate has **status = Not Met** but all hard gates are Met or Exempt → **the hard-gate path is still considered Met**; soft-gate issues become cross-round carryover items

### Exemption rules
- **Exempt**: the dimension is not applicable to the current task (for example, database migration checks in a purely frontend project)
- Roll-up: exempt dimensions do not participate in gate decisions, equivalent to removing that row from the matrix
- Exemptions must be declared in `autoloop-plan.md` with a reason

---

## Knowledge-task Gates (T1/T2/T5/T6)

### Coverage

**Definition**: number of dimensions with substantive content / total number of planned research dimensions

**Calculation**:

```text
Covered dimensions = dimensions in findings.md that contain at least 2 concrete information points (not just "not found")
Coverage = covered dimensions / total dimensions × 100%
```

Note: the threshold is set to 2 information points (not 3) because the number of information points reflects breadth of coverage, while information trustworthiness is handled by the separate "Credibility" gate (>= 2 independent sources). The two are intentionally non-overlapping.

**Pass criteria**:
- T1 Research: >= 85%
- T2 Compare: 100% (every dimension of every option must contain content)
- T6 Generate: every generated unit is completed = 100%

**Coverage scoring anchors**:

| Range | Criteria |
|------|------|
| 1-3 | <50% of dimensions have substantive content |
| 4-6 | 50-84% have substantive content |
| 7-8 | 85-95% have substantive content |
| 9-10 | >95% and every dimension has >= 3 information points |

---

### Credibility

**Definition**: key findings supported by >= 2 independent sources / total number of key findings

**Independent source criteria**: the same author / same company / same forum does not count as independent (unless different authors provide original content). Official docs + third-party review, or different media + official data, do count as independent.

**Source credibility levels**:

```text
Level 1 (high credibility): official documentation / official GitHub / primary research reports
Level 2 (medium-high): Gartner / Forrester / IDC / Stack Overflow / high-vote Hacker News
Level 3 (medium): reputable tech media, expert blogs (with verified identity)
Level 4 (low-medium): general blogs, ordinary Reddit answers
Level 5 (low): anonymous content, content without a stated time
```

**Calculation**:

```text
Key finding = a statement explicitly labeled as a "key conclusion" in findings.md
Multi-source support = the statement has >= 2 independent sources, and at least one is Level 1-2
Credibility = key findings with multi-source support / total key findings × 100%
```

**Pass criteria**: >= 80%

**Credibility scoring anchors**:

| Range | Criteria |
|------|------|
| 1-3 | <50% of key findings have independent sources |
| 4-6 | 50-79% have independent sources |
| 7-8 | >= 80% have independent sources |
| 9-10 | >90% and each key finding has >= 3 independent sources |

---

### Consistency

**Definition**: number of contradiction-free dimensions / total dimensions × 100%

Note: the unit of measurement is the **dimension**, not an individual statement. If any contradictory statement exists inside a dimension, that entire dimension counts as contradictory.

**Contradiction criteria**: different values for the same attribute without explanation, or logical contradiction, count as contradictions; different scenarios, different versions, or subjective differences do not count as contradictions if explained in findings.

**Calculation**:

```text
Contradictory dimensions = dimensions marked as "contradiction exists" in the cross-verification report
Contradiction-free dimensions = total dimensions - contradictory dimensions
Consistency = (contradiction-free dimensions / total dimensions) × 100%
```

**Pass criteria**: >= 90%

**Consistency scoring anchors**:

| Range | Criteria |
|------|------|
| 1-3 | Contradictory information exists and is undocumented |
| 4-6 | Contradictions are recorded but unresolved |
| 7-8 | All contradictions are resolved and explained |
| 9-10 | No contradictions, or all contradictions resolved with cross-verification evidence |

---

### Completeness

**Definition**: number of key statements with cited sources / total number of key statements

**Key statements**: statements that support conclusions or recommendations (must have sources). General statements (background descriptions) are recommended to have sources but are not mandatory.

**Calculation**:

```text
Key statements = conclusion statements, data statements, and recommendation-basis statements in findings.md
Has source = the statement is followed by `(Source: URL)` or a `[^N]` citation
Completeness = key statements with sources / total key statements × 100%
```

**Pass criteria**: >= 85%

---

### T1 Draft-depth supplementary checks (market / industry topics)

> This section is an additional checklist for **T1 Research** in market / industry mode, used to judge whether more supporting evidence or rewriting is required.  
> It **does not replace** the four formal gate thresholds above, nor does it independently alter Hard / Soft Gate decisions; its purpose is to prevent a situation where "the gates passed, but the draft still reads like an outline or a pile of materials."

#### Thin-draft criteria

If any of the following occurs, it should be treated as "structurally correct but insufficiently deep":

- A section contains only high-level judgments and lacks enough verifiable data blocks.
- Averages are present but structural breakdowns are missing, such as region, product, company, or time dimension.
- Conclusions sound complete, but the reader cannot follow the preceding evidence to independently reach a similar judgment.
- There are many sources, but they are not mapped to sections, making traceability difficult.
- Special-topic modules only list roles or directions, without breaking down work packages, automation boundaries, and retained human tasks.

#### Checklist

1. **Mandatory section completeness**
   - Whether it includes: title / topic / objective, market size and growth, demand side, value chain and profit pools, competitive landscape, regulation, technology, business models, risks, synthesized judgment, and data sources.
2. **Three elements present in every section**
   - Whether every section contains all three: `data`, `analysis`, and `conclusion`.
3. **Complete special-topic module**
   - If the prompt includes "industry + direction/topic", whether a special-topic module is added, and whether it also contains `data`, `analysis`, and `conclusion`.
4. **Sufficient cross-verification traces**
   - Whether key judgments have multi-source support; whether judgments that cannot be cross-verified are downgraded to risks or disputed points.
5. **Reader-facing boundary compliance**
   - Whether the final report removes explicit internal execution labels, gate labels, methodology headings, system traces, and template hints.
6. **Sufficient evidence density per section**
   - Whether each section contains several verifiable data blocks rather than only abstract summaries.
7. **Adequate structural breakdown**
   - Whether several key sections include cross-dimensions such as region, product, company, or time, instead of only industry averages.
8. **Traceable source organization**
   - Whether `Data Sources` is organized by section, or at least clearly maps to sections, instead of being only a bibliography.
9. **Clear evidence boundaries**
   - Whether it distinguishes "direct evidence", "organizational signals", and "analytical inference"; whether unsupported claims are explicitly bounded.
10. **Work-package breakdown in special-topic modules**
   - For AI / automation / job substitutability themes, whether the content is broken down to the work-package level rather than stopping at job titles.

#### Usage

- If any checklist item fails, T1 should prioritize improving **section depth** in the next round instead of mechanically expanding the number of dimensions.
- It is recommended to record in `autoloop-progress.md` which sections are missing:
  - data
  - analysis
  - conclusion
  - structural breakdown
  - company / regional examples
  - source mapping
  - evidence boundaries
- For market / industry topics, only when the four formal gates are met and this supplementary check also passes should the workflow move to the final draft.

---

## T2-specific Gates

### Bias Check

**Definition**: each candidate option is evaluated by >= 2 independent subagents, and the scoring difference between subagents for the same option is < 1.5 points on a 0-10 scale.

**Single authoritative formula (applies to all files)**:

```text
For each option:
  Bias score = (max_score - min_score) / 10
  Pass condition: bias score < 0.15 (i.e. maximum difference < 1.5 points on a 10-point scale)
  Fail: trigger a third independent option-analyzer to re-evaluate that option

Bias Check passes = all options satisfy the condition above
```

**Pass criteria**: all options have bias scores < 0.15 (if the difference is >= 1.5, a third independent evaluation must run and the majority conclusion prevails). In `gate-manifest.json`, `bias_check` is a bool (`unit: "bool"`), meaning the review subagent precomputes it and writes `true/false` into `state.json`.

---

### Sensitivity Analysis

**Definition**: adjust each key assumption in the `key_assumptions` list in plan by +/-20%, then check whether the final top-ranked recommendation stays unchanged.

`key_assumptions` format: comes from `autoloop-plan.md`; each item contains `name` + `current_value` + `unit`.

**Single authoritative formula (applies to all files)**:

```text
For each assumption H in plan.key_assumptions:
  original_rank = recommendation ranking computed with H.current_value
  high_rank = ranking computed with H.current_value × 1.2
  low_rank  = ranking computed with H.current_value × 0.8
  Pass condition: original_rank == high_rank == low_rank (top rank unchanged)

Sensitivity Analysis passes = all key_assumptions satisfy the condition above
```

**Pass criteria**: the #1 recommendation remains unchanged after a +/-20% change to any single key assumption

---

### Default T2 evaluation dimensions

When the user does not specify evaluation dimensions, use default weights by option type. There are three default tables:

- **Tech stack / tool selection**: feature fit (25%) > technical maturity (20%) > learning curve / community / cost (15% each) > long-term risk (10%)
- **Architecture comparison**: decoupling / scalability / performance (20% each) > implementation complexity / operations (15% each) > migration risk (10%)
- **Business option comparison**: ROI (25%) > implementation timeline / resources / market risk (20% each) > strategic fit (15%)

Dimensions and weights defined by the user in plan take precedence over these defaults.

## T5-specific Gates

### KPI Target

**Definition**: the KPI value defined by the user in `autoloop-plan.md` reaches the target threshold set in plan.

**Calculation**:

```text
Measured value = the actual KPI measurement result in VERIFY
Pass = measured value reaches or exceeds the target threshold defined in plan.md
```

**Requirement**: plan must explicitly state the KPI name, measurement method, and target threshold (for example, `"API response time < 200ms"` or `"Coverage >= 90%"`). When the KPI definition is missing (no row in `plan.gates` with `threshold=null` and a valid `target`), `autoloop-controller.py` **pauses the loop** during **OBSERVE** and writes a checkpoint, requiring the user to complete the KPI before continuing with `--resume`.

---

## T6-specific Gates

### Pass Rate

**Definition**: number of content items that pass QA / total generated items × 100%

**Calculation**:

```text
Pass QA = the number of content items that meet the content standards defined in plan (non-empty, correct format, no obvious errors)
Pass rate = number of items that pass QA / total content items × 100%
```

**Pass criteria**: >= 90% (SSOT: `gate-manifest.json`, T6 Generate)

### Average Score

**Definition**: arithmetic mean of the quality scores of all content items (the scoring standard must be defined in `autoloop-plan.md`, range 0-10)

**Calculation**:

```text
Each content item is scored by subagents according to the scoring standard defined in plan (0-10)
Average score = sum(all content item scores) / total number of content items
```

**Pass criteria**: >= 7/10

---

> Scoring anchors for T5 iterative tasks: see the corresponding dimensions in `references/enterprise-standard.md`.
> Scoring anchors for T6 generation tasks: see the corresponding dimensions in `references/enterprise-standard.md`.
---


---

> Engineering-task gates (T4/T7/T8), the gate evaluation matrix, T7 composite decision rules, and exemption rules are in `references/quality-gates-engineering.md`.
