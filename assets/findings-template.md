# AutoLoop Findings — Findings Log

**Task ID**: autoloop-{YYYYMMDD-HHMMSS}
**Template**: T{N}: {Name}
**Created at**: {ISO 8601}
**Last updated**: {ISO 8601}

---

## Executive Summary

**Research / analysis topic**: {topic}
**Total rounds**: {N}
**Final quality score**: {dimension 1}: {score}/10, {dimension 2}: {score}/10

**Key conclusions (top 5)**:
1. {conclusion 1} (confidence: {N}%; N is an integer from 0 to 100)
2. {conclusion 2}
3. {conclusion 3}
4. {conclusion 4}
5. {conclusion 5}

---

## Round 1 Findings ({time})

### Dimension: {dimension 1 name}

**Key findings**:
- {finding 1} (source: [{source name}]({URL}), confidence: high)
- {finding 2} (source: [{source name}]({URL}), confidence: medium)

**Data points**:
- {metric}: {value} (source: {URL})
- {metric}: {value} (source: {URL})

**Information gaps**:
- {gap 1} (impact level: P1/P2/P3)

**Conflict log** (optional - fill this in when contradictory information is found within the same dimension):
- **Conflicting sources**: {source A} vs {source B}, difference: {specific difference description}
- **Explanation / downgrade**: {different definitions / time lag / statistical methodology difference / real dispute}
- **Confidence impact**: {keep original confidence / downgrade to medium / downgrade to low, with reason}

**Related findings** (out of scope):
- {unexpected finding, for evolution decisions}

---

### Dimension: {dimension 2 name}

**Key findings**:
- {finding 1} (source: [{source name}]({URL}), confidence: high)
- {finding 2} (source: [{source name}]({URL}), confidence: medium)

**Data points**:
- {metric}: {value} (source: {URL})

**Information gaps**:
- {gap 1} (impact level: P1/P2/P3)

**Related findings** (out of scope):
- {unexpected finding, for evolution decisions}

---

### Conflict Log (Round 1)

| Dimension | Claim A (source) | Claim B (source) | Analysis | Handling |
|-----------|------------------|------------------|----------|----------|
| {dimension} | {claim A} ({URL}) | {claim B} ({URL}) | {analysis} | {use A / keep both / investigate later} |

---

## Additional Findings in Round 2 ({time})

### New dimension: {new dimension name} (added in round 2)

{same format}

### Update: {existing dimension name} (additional information)

**New finding**:
- {new finding} (source: {URL})

**Conflict resolved**:
- {previous conflict ID}: resolved (reason: {explanation})

---

## Engineering Issue List (for T4/T7/T8)

### Security issues

| ID | File (absolute path) | Line | Type | Priority | Status | Description |
|----|----------------------|------|------|----------|--------|-------------|
| S001 | {path} | {line} | SQL injection | P1 | New / Fixed / Open / Carryover | {description} |

### Reliability issues

| ID | File | Line | Type | Priority | Status | Description |
|----|------|------|------|----------|--------|-------------|
| R001 | {path} | {line} | silent failure | P1 | New / Fixed / Open / Carryover | {description} |

### Maintainability issues

| ID | File | Line | Type | Priority | Status | Description |
|----|------|------|------|----------|--------|-------------|
| M001 | {path} | {line} | any type usage | P2 | New / Fixed / Open / Carryover | {description} |

### Architecture issues

| ID | Impact scope | Type | Priority | Status | Description |
|----|--------------|------|----------|--------|-------------|
| A001 | {file/module} | circular dependency | P1 | New / Fixed / Open / Carryover | {description} |

### Performance issues

| ID | File | Line | Type | Expected gain | Status | Description |
|----|------|------|------|---------------|--------|-------------|
| P001 | {path} | {line} | N+1 query | reduce N queries/requests | New / Fixed / Open / Carryover | {description} |

### Stability issues

| ID | File | Type | Priority | Status | Description |
|----|------|------|----------|--------|-------------|
| ST001 | {path} | no fallback | P1 | New / Fixed / Open / Carryover | {description} |

---

## Fix Log (for T5/T6/T7)

| ID | Fix time | Fix content | Modified file | Verification result | Introduced new issue? |
|----|----------|-------------|---------------|---------------------|----------------------|
| S001 | {time} | {fix description} | {file path} | {syntax_check_cmd} passed | No |

---

## Disputes and Uncertainty

| Topic | Claim A | Claim B | Source of each | Our position | Position confidence (0-100%) | Severity |
|-------|---------|---------|---------------|--------------|------------------------------|----------|
| {topic} | {A} | {B} | {source A}/{source B} | {position} | {e.g. 70%} | P1/P2/P3 |

---

## Information Gaps Summary

The following important information could not be found or sufficiently verified (must be explained in the final report):

| Gap | Dimension | Impact level | Methods tried | Suggested next action |
|-----|-----------|--------------|---------------|-----------------------|
| {gap 1} | {dimension} | P1/P2/P3 | {attempted} | {suggestion} |

---

## Expansion Ideas (out-of-scope findings for later use)

The following findings are outside the scope of this research but are recorded for future use:

- {finding 1}: {brief description} (found in round {N}, dimension: {dimension})
- {finding 2}: ...

---

## Source List

### High-confidence sources
- [{name}]({URL}) - official documentation / primary source
- [{name}]({URL})

### Medium-confidence sources
- [{name}]({URL}) - technical media / expert blog
- [{name}]({URL})

### Low-confidence sources (reference only)
- [{name}]({URL}) - cross-validated against other sources

---

## Issue List (REFLECT Layer 1 - cumulative tracking)

Status enum: **New** | **Fixed** | **Open** | **Carryover**

| Round | Issue description | Source | Severity | Status | Root cause analysis |
|-------|-------------------|--------|----------|--------|---------------------|
| R1 | {issue} | {subagent / verification step} | P1/P2/P3 | New / Fixed / Open / Carryover | {why} |

## Strategy Evaluation (REFLECT Layer 2 - strategy effect knowledge base)

| Round | strategy_id | Strategy | Effect score (1-5) | Score change | Keep | Avoid | To verify | Reason |
|-------|-------------|----------|--------------------|-------------|------|-------|-----------|--------|
| R1 | S01-{short name} | {strategy description} | {1-5} | {+/− score} | **Keep** / **Avoid** / **To verify** | {why effective / ineffective} |

> See references/loop-data-schema.md for the canonical status enum.

## Pattern Recognition (REFLECT Layer 3 - cross-round trends)

### Recurring issues
- {issue type} - appears in R{x}, R{y}, R{z}; systemic root cause: {analysis}

### Diminishing returns signals
- R1→R2 improvement {x}%, R2→R3 improvement {y}% - trend: {rising / falling / flat}

### Cross-dimension links
- {change A} caused {dimension B} to change: {description}

### Bottlenecks
- {dimension / area} has been stuck for {n} rounds at {score}; strategies tried: {strategy list}

## Lessons Learned (REFLECT Layer 4 - reusable knowledge)

### Validated hypotheses
- ✅ {hypothesis} - confirmed, evidence: {evidence}
- ❌ {hypothesis} - disproved, reason: {reason}

### Generalizable methods
- {method} - applicable in: {scenario}, effect: {effect}

### Improvement ideas for AutoLoop itself
- {suggestion} - trigger: {workflow issue discovered during this task}
