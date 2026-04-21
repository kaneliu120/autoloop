# AutoLoop Codex Review R8 - Six-Dimension Methodology Review

**Review date**: 2026-03-28  
**Review tool**: OpenAI Codex CLI (xhigh reasoning effort + web_search_cached)  
**Review scope**: the full `~/Projects/autoloop` repository (49 files: 12 protocols + 11 commands + 6 templates + 7 scripts + 3 MCP files + 9 SKILL files + 1 document)  
**Token usage**: 290,275  
**Review mode**: static source review (read-only, no end-to-end execution)

---

## Review Framework

| Dimension | Weight | Focus |
|-----------|--------|-------|
| Measurement validity and consistency | 20% | Are the metrics defined correctly? Do the scoring rules actually measure what they claim? Are thresholds grounded in experience? Are files consistent? |
| Data-to-strategy closed loop | 20% | Do observations truly drive strategy selection? Is there a real feedback loop from results back into decisions? |
| Convergence performance | 20% | Does the system actually converge toward the quality target? Are oscillation, stagnation, and divergence prevented? |
| Gate discriminative power | 10% | Can the quality gates actually separate good from bad? Do the pass/fail thresholds have meaning? |
| Task model fit | 10% | Do the 7 templates genuinely fit real tasks? Are there gaps, overlaps, or forced-fit problems? |
| Self-evolution and compounding ability | 20% | Does the system genuinely learn from prior runs? Does the experience registry compound over time? |

---

## Total Score

| Dimension | Weight | Score | Weighted |
|-----------|--------|-------|----------|
| Measurement validity and consistency | 20% | 4/10 | 0.80 |
| Data-to-strategy closed loop | 20% | 3/10 | 0.60 |
| Convergence performance | 20% | 4/10 | 0.80 |
| Gate discriminative power | 10% | 4/10 | 0.40 |
| Task model fit | 10% | 5/10 | 0.50 |
| Self-evolution and compounding ability | 20% | 3/10 | 0.60 |
| **Weighted total** | **100%** | | **3.7/10** |

---

## Detailed Findings

### 1. Measurement Validity and Consistency (4/10, weight 20%)

**Strengths**:
- Fail-closed scoring is defined in `quality-gates.md:40-62`, and each score must include score + criteria + evidence
- Measurable success criteria and gate thresholds exist in `plan-template.md`
- Baseline and per-round score updates exist in `progress-template.md`

**Key defects**:

1. **Scorer / renderer format mismatch**
   - `autoloop-score.py` expects `##` sections plus inline source markers
   - `autoloop-render.py` outputs `###` subheads plus separate `Source:` lines
   - **Result**: SSOT-rendered findings are systematically under-scored or scored zero

2. **Threshold authority drift**
   - Some docs say thresholds should live in `quality-gates.md`
   - `audit-template.md` hard-codes the T6 thresholds
   - `TODO.md` recorded the problem, but it was not fixed

3. **Scoring vocabulary fragmentation**
   - Mixed use of `/10` scores, `%` confidence, `high / medium` source credibility, `P1 / P2 / P3` severity, and `1-5` strategy-effect scores
   - This creates ambiguity in aggregation and cross-dimension comparisons

4. **Weak calibration basis**
   - Only a few end-to-end runs existed at the time of review
   - Thresholds were still being moved from guesswork toward calibration

**Recommendations**:
- Define a normalized metric schema and generate templates, TSV headers, validators, and reports from it
- Have the scorer consume the SSOT directly instead of parsing markdown
- Calibrate thresholds on labeled examples and publish false-positive / false-negative behavior per gate

---

### 2. Data-to-Strategy Closed Loop (3/10, weight 20%)

**Strengths**:
- The protocol requires later rounds to read the previous round's REFLECT output before starting OBSERVE
- The root skill says tasks should read and write a global experience registry

**Key defects**:

1. **The command layer does not execute the claimed loop**
   - Commands mostly reread `autoloop-findings.md` instead of shared memory
   - Only the pipeline explicitly writes to the registry at completion

2. **Two competing execution modes were not unified**
   - Flat-file path: `autoloop-init.py` creates markdown files
   - SSOT JSON path: `autoloop-state.py` creates `autoloop-state.json`
   - MCP exposed the flat-file toolchain but not the state/render path

3. **Learning containers had schema but no reducer**
   - SSOT contained `strategy_history`, `pattern_recognition`, `lessons_learned`, and `experience`
   - There was no automatic reducer to promote round-level REFLECT data into those containers
   - The renderer also omitted much of this information

4. **add-finding silently dropped data**
   - Without an iteration, the round defaulted to 0 and the storage path was skipped

**Recommendations**:
- Give one controller ownership of all per-round state
- Expose state, render, score, and experience update through one API
- Require each round to emit structured observations, choose one strategy, score it, and persist the updated priors before starting the next round

---

### 3. Convergence Performance (4/10, weight 20%)

**Strengths**:
- Strategy switching, oscillation detection, and termination logic existed in the protocol
- Template-specific stagnation thresholds existed in `parameters.md`
- The design had multi-layer convergence control: generic strategy switching + template-specific stagnation + max exploration + "cannot continue"

**Key defects**:

1. **Template-specific control was not wired into the main EVOLVE path**
   - `loop-protocol.md` still used the generic 3% rule
   - The template-specific rules were not actually taking effect

2. **The state layer allowed bypassing ordering**
   - The generic `update` command could write arbitrary paths / values
   - The only transition logic was "new rounds start from OBSERVE"
   - The phase sequence could therefore be bypassed completely

3. **T3 could ignore collateral-damage termination**
   - Termination depended only on KPI achievement
   - Side-effect control was not part of the final stop condition

4. **Pipeline allowed gate relaxation**
   - `gate_override` could relax gates
   - `skip_and_continue` was possible
   - Auto rollback across nodes was forbidden

**Recommendations**:
- Move convergence logic from documentation into the state controller
- Compute marginal gains, oscillation, and side-effect regression from the SSOT
- Block termination unless target improvement and collateral constraints both pass

---

### 4. Gate Discriminative Power (4/10, weight 10%)

**Strengths**:
- Coverage and confidence were intentionally separated
- T2 quantified bias and sensitivity
- T6 used a compound score + defect-count rule
- T5 had a hard user-confirmation block

**Key defects**:

1. **Gate policy contradictions**
   - T1 / T2 said to pause when gates fail
   - Later sections marked some T1/T2 gates as non-blocking

2. **T6 contradictions**
   - One section required scores and counts to pass together
   - Later sections still allowed pass-through when counts failed

3. **T5 deployment rule conflicts**
   - One section allowed either service checks or health checks to be N/A
   - Another still required both

4. **No empirical basis**
   - No confusion-matrix analysis
   - No benchmark of known-good / known-bad runs

**Recommendations**:
- Benchmark gates against known-good / known-bad runs
- Compute false-positive / false-negative rates
- Merge hard / soft semantics into one table
- Ensure the scorer evaluates the actual artifact that the engine produces

---

### 5. Task Model Fit (5/10, weight 10%)

**Strengths**:
- The template taxonomy was intentional
- Routing thresholds existed in `parameters.md`
- T5 had its own phase model
- T6/T7 could be specialized through domain packs

**Key defects**:

1. **Easy to bypass**
   - Direct template commands were exposed
   - Each template SKILL.md was just a thin wrapper

2. **T2 violated "single-strategy isolation"**
   - The core rule says each DECIDE should choose one primary strategy
   - T2 used two analyzers and a third when they disagreed

3. **T5 parameter contract hole**
   - delivery-template required `migration_check_cmd`
   - the T5 parameter block in plan-template did not collect it

4. **T6 report authority split**
   - `report-template.md` contained a T6 section
   - `audit-template.md` was a separate T6 report

**Recommendations**:
- Centralize routing and prevent templates from being called without verified classification
- Close the parameter gaps for each template
- Merge overlapping final artifacts

---

### 6. Self-Evolution and Compounding Ability (3/10, weight 20%)

**Strengths**:
- The registry supported promotion, decay, and candidate-default logic
- Evolution rules defined protocol upgrade mechanics
- In theory, this was the strongest part of the design

**Key defects**:

1. **Little operationalization in the execution path**
   - Command use of the registry was inconsistent; most commands still read local findings
   - SSOT had learning containers, but no automatic fill path

2. **Governance inconsistency**
   - Some protocol changes required user confirmation
   - Some evolution rules still allowed low / medium risk changes to auto-apply

3. **Version semantics drift**
   - Patch was defined one way in the loop protocol
   - In practice, other docs also used patch for formal upgrades and default-value changes
   - Rollback semantics were also inconsistent

**Recommendations**:
- Require automatic strategy-effect updates each round
- Make registry read/write a mandatory controller step
- Promote strategies only after repeated validation wins
- Unify governance and version semantics

---

## Top 3 Systemic Problems

| # | Problem | Root cause |
|---|---------|------------|
| 1 | The "autonomous loop" is not mechanically closed | Two competing execution modes (flat files vs SSOT), weak MCP paths, and stage transitions rely on agent discipline rather than enforced state |
| 2 | The metric contract is internally inconsistent | Thresholds, TSV schema, report artifacts, and scorer inputs drift across docs, templates, and scripts |
| 3 | Self-evolution is a document-level fiction | The experience registry and evolution rules are well-written, but they are not embedded in the main execution path |

## Top 3 Highest-Leverage Improvements

| # | Improvement | Expected impact |
|---|-------------|-----------------|
| 1 | Replace markdown-first paths with one machine-readable SSOT | Generate findings / progress / reports / TSV / scores from the same data model and eliminate cross-file drift |
| 2 | Implement a real round controller | Enforce OBSERVE→ORIENT→DECIDE→ACT→VERIFY→SYNTHESIZE→EVOLVE→REFLECT, update strategy memory automatically, and block illegal transitions |
| 3 | Build an experience-gate calibration framework | Label historical runs, fit thresholds, analyze variance, and publish false-positive / false-negative rates per gate |
