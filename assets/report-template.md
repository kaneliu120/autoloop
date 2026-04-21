# AutoLoop Final Report

> **Usage notes**: This template contains sections for all template types (T1-T8). Keep only the sections that match the actual template type and delete the others.
>
> - **T1 Research**: For market / industry research topics, use the section below by default: **"T1: High-Standard Market / Industry Research Report"**. The final report should keep only reader-facing information. It must **not** include internal execution details, gate labels, methodology headings, system traces, or template prompts.  
> - **Non-market T1**: You may adapt the section titles using the same reader-facing principle, but every section must still include **data, analysis, and conclusions**, with no internal noise.  
> - **Default T1 implementation**: The main agent coordinates the work, and subagents gather evidence by section. The template is the final shell, not the research protocol itself.  
> - **T2 Compare**: Keep sections such as "Knowledge-type (T2): Key Findings" and "Comparison-type (T2)", and remove the T1 and T3-T8 special sections.  
> - **T4 Deliver**: Likewise, keep only the section that matches the actual template.
>
> Quality-gate thresholds for each template are defined in `references/quality-gates.md`; T1 gate and iteration details should not be copied into the final reader-facing report.

> **The following "Task ID / Executive Summary / Quality Score" block is skipped for T1; keep it only for final T2-T8 deliverables.**

**Task ID**: autoloop-{YYYYMMDD-HHMMSS}
**Template**: T{N}: {Name}
**Generated at**: {ISO 8601}
**Status**: {Completed (met target) / Completed (budget exhausted) / Completed (user stopped) / Completed (cannot continue)}

---

## Executive Summary

| Field | Value |
|------|-----|
| Task objective | {one sentence} |
| Iteration rounds | {N} |
| Total time | {N} minutes |
| Final conclusion | {one-sentence conclusion} |
| Quality met | {all met / {N} dimensions not met} |

---

## Quality Scores

| Dimension | Baseline | Final | Target | Improvement | Status |
|-----------|----------|-------|--------|------------|--------|
| {dimension 1} | {base} | {final} | {target} | +{N} | Met |
| {dimension 2} | {base} | {final} | {target} | +{N} | Met |
| {dimension 3} | {base} | {final} | {target} | -{N} | Not met (gap {N}) |

---

## Main Deliverables

### T1: High-Standard Market / Industry Research Report (reader-facing final body only)

# {report title}

> **Topic**: {research topic}  
> **Research objective**: {core question the report answers}  
> **Analysis date**: {YYYY-MM-DD}  
> **Information boundaries**: {region / time / methodology / exclusions}

{Open with 1-3 paragraphs that directly explain what question the report answers, why it matters, and how the reader should interpret the sections below. Do not include process notes.}

---

## 1. Market Size and Growth

### Data

| Metric | Value or range | Source |
|--------|----------------|--------|
| … | … | … |

{Prefer ranges, time trends, regional comparisons, methodological differences, and structural breakdowns. Do not rely on a single total-market number.}

### Analysis

- {Explain market size, growth rate, cycle, drivers, and methodological differences. Answer: why sources differ, where growth comes from, and which structural changes matter more than a single TAM number.}

### Conclusion

- {clear judgment for this chapter}

---

## 2. Demand Side / Customer Structure

### Data

| Dimension | Observation | Source |
|-----------|-------------|--------|
| Customer segment | … | … |
| Use case / JTBD | … | … |

{Prefer product mix, active/ARPU differences, mobile behavior, multi-account / multi-platform behavior, cross-sell, and value differences between mature and emerging markets.}

### Analysis

- {Explain customer segmentation, demand differences, and acquisition / retention mechanisms. Answer: which users are only traffic, which users create durable monetization, and why different products map to different demand logic.}

### Conclusion

- {clear judgment for this chapter}

---

## 3. Value Chain and Profit Pool

### Data

| Segment | Main participants | Value / profit characteristics | Source |
|---------|-------------------|-------------------------------|--------|
| … | … | … | … |

### Analysis

- {Explain who captures value, where the barriers are, and how profits flow. Answer: whether revenue and profit are concentrated in the same segment, which segments act as entry points, and which are long-term profit pools.}

### Conclusion

- {clear judgment for this chapter}

---

## 4. Competitive Landscape and Key Players

### Data

| Company / type | Size or share | Role | Key characteristics | Source |
|---------------|---------------|------|---------------------|--------|
| … | … | … | … | … |

### Analysis

- {Explain tiers, concentration, competition structure, M&A dynamics, and differentiation. Answer: what different layers of players are actually competing for, and whether the moat is licensing, brand, data rights, content, or systems integration.}

### Conclusion

- {clear judgment for this chapter}

---

## 5. Regulatory and Policy Environment

### Data

| Jurisdiction / policy point | Current status | Industry impact | Source |
|----------------------------|----------------|----------------|--------|
| … | … | … | … |

{Prefer license structure, taxes / fees, advertising and player-protection rules, enforcement actions, and business implications. Do not merely say "regulation is tightening" or "loosening".}

### Analysis

- {Explain how regulation affects growth, entry barriers, business models, and risk. Answer: is this a high-barrier national market, a fragmented state / provincial market, a gray-to-white transition market, or a restrictive market?}

### Conclusion

- {clear judgment for this chapter}

---

## 6. Technology and Key Change Factors

### Data

| Technology / change factor | Current adoption | Impact | Source |
|---------------------------|------------------|--------|--------|
| … | … | … | … |

{Prefer the tech chain, company examples, quantified uplift, and applicability boundaries. Do not simply write "AI is penetrating".}

### Analysis

- {Explain how technology, channels, macro conditions, or other variables change the industry structure. Answer: which technical chains are close to mature production use, which are still just efficiency gains, and which uplift figures are only case studies rather than industry averages.}

### Conclusion

- {clear judgment for this chapter}

---

## 7. Business Model / Revenue-Cost Structure / Operating Leverage

### Data

| Item | Typical characteristics | Source |
|------|-------------------------|--------|
| Revenue sources | … | … |
| Cost structure | … | … |
| Leverage points | … | … |

### Analysis

- {Explain the revenue model, cost constraints, operating leverage, and profit elasticity. Answer: which products drive acquisition, which drive durable monetization, and which technologies or processes actually move unit economics.}

### Conclusion

- {clear judgment for this chapter}

---

## 8. Special Topic: {direction / topic} (delete if not applicable)

### 8.1 {special subtopic 1}

#### Data

| Metric / fact | Content | Source |
|--------------|---------|--------|
| … | … | … |

{For special topics, prefer working-package-level evidence instead of abstract commentary.}

#### Analysis

- {Explain the mechanisms, impact, and differences in the special topic. Answer: which parts have strong direct evidence, which are cautious inferences, and which work packages are rewritten first.}

#### Conclusion

- {clear judgment for this subsection}

### 8.2 {special subtopic 2}

#### Data

| Metric / fact | Content | Source |
|--------------|---------|--------|
| … | … | … |

#### Analysis

- …

#### Conclusion

- …

{If the direction is "industry + AI job replacement potential", this chapter must cover at least: AI adoption, role / function mapping, work-package decomposition, replaceable and non-replaceable mechanisms, company examples, organizational and talent trends, and the special-topic conclusion.}

---

## 9. Major Risks, Controversies, and Uncertainty

### Data

| Risk / controversy | Trigger condition or manifestation | Source |
|-------------------|------------------------------------|--------|
| … | … | … |

### Analysis

- {Explain which judgments are still uncertain, where the disputes come from, and how they should be interpreted. Clearly distinguish direct evidence, organizational signals, analytical inferences, and which numbers are not directly comparable.}

### Conclusion

- {clear judgment for this chapter}

---

## 10. Overall Judgment and Implications

### Core conclusions

1. {conclusion 1}
2. {conclusion 2}
3. {conclusion 3}

### Analysis

- {Tie all chapters together into a complete narrative}

### Conclusion

- {overall judgment for strategy / investment / organization / next research steps}

---

## Data Sources

### Market size and growth

- {source 1}

### Demand side / customer structure

- {source 2}

### Value chain, competitive landscape, and business model

- {source 3}

### Regulatory and policy environment

- {source 4}

### Technology and AI adoption

- {source 5}

### Job displacement, organization, and uncertainty

- {source 6}

---

**(T1 final report ends here; do not write the following into the same file for T1)**

---

### Knowledge-type (T2): Key Findings

**Summary of key conclusions for {comparison topic}** (see the next section, "Comparison-type (T2)", for the full matrix and recommendation):

1. **{Conclusion 1}**
   {detailed explanation, 2-3 sentences}
   Supporting evidence: ({Source 1}) ({Source 2})

2. **{Conclusion 2}**
   {detailed explanation}
   Supporting evidence: ({Source})

3. **{Conclusion 3}**
   {detailed explanation}

### Comparison-type (T2): Recommendation

**Recommendation**: {option name} (confidence: {N}%)

Reasoning:
{2-3 paragraphs with concrete explanation}

Comparison matrix (summary):

| Dimension | {Option A} | {Option B} | {Option C} |
|----------|-----------|-----------|-----------|
| Weighted total | {N} | {N} | {N} |
| Rank | 1st | 2nd | 3rd |

### Iteration-type (T5): KPI Achievement

**KPI**: {metric name}
**Baseline**: {value} → **Final**: {value} (improvement {X}%)
**Target**: {value} - **Status**: {met / not met}

Key improvements (by contribution):
1. {improvement 1}: contributed {X}% of the improvement
2. {improvement 2}: contributed {X}%

### Generation-type (T6): Batch Results

**Generated**: {N}
**Pass rate**: {X}% (see references/quality-gates.md for the T6 threshold)
**Average score**: {N}/10 (see references/quality-gates.md for the T6 threshold)

Output files: {path}

Quality distribution:
- 9-10 points: {N}
- 7-8 points: {N}
- Requires manual review: {N}

### Delivery-type (T4): Feature Delivery

**Feature**: {name}
**Delivery status**: {completed / in progress}

Change list:
| Type | Content |
|------|---------|
| Added files | {path list} |
| Modified files | {path list} |
| Database migrations | {migration name} |
| Added routes | {route list} |

### T7 Quality Audit Results

> See `autoloop-audit.md` for the detailed audit report generated from the audit template. Summary below:

| Dimension | Final score | Gate status |
|----------|-------------|-------------|
| Security | {audit reference} | {audit reference} |
| Reliability | {audit reference} | {audit reference} |
| Maintainability | {audit reference} | {audit reference} |

### Optimization-type (T8): System Optimization

| Dimension | Before | After | Met |
|----------|--------|-------|-----|
| Architecture | {N}/10 | {N}/10 | Met / Not met |
| Performance | {N}/10 | {N}/10 | Met / Not met |
| Stability | {N}/10 | {N}/10 | Met / Not met |

Key optimizations:
1. {highest-impact optimization}: {quantified effect}
2. {second optimization}: {effect}

---

## Iteration Trace

> **T1**: Do not write this section into `autoloop-report-*.md`; see `autoloop-progress.md`.

| Round | Main action | Score change | Strategy adjustment |
|------|-------------|--------------|---------------------|
| Round 1 | {action} | {change} | {none / adjustment} |
| Round 2 | {action} | {change} | {none / adjustment} |
| Round N | {action} | {change} | — |

---

## Remaining Issues

The following issues were not resolved in this task:

| Issue | Reason | Impact | Recommendation |
|------|--------|--------|----------------|
| {issue 1} | {reason (P3 priority / insufficient budget / technical limitation)} | P1/P2/P3 | {suggested next action} |

---

## Controversies and Uncertainty

The following conclusions are uncertain and should be used carefully:

| Conclusion | Why uncertain | Confidence | Suggested validation method |
|-----------|---------------|------------|-----------------------------|
| {conclusion} | {reason} | Medium | {validation method} |

---

## Next Steps

Based on the findings from this task, recommend:

1. **Immediate action** (high priority):
   - {suggestion 1}: {specific action}

2. **Short-term plan** (within 1-2 weeks):
   - {suggestion 2}: {specific action}

3. **Long-term plan** (1 month or more):
   - {suggestion 3}: {direction}

---

## Deliverable List

| File | Path | Description |
|------|------|-------------|
| Task plan | {path}/autoloop-plan.md | Task configuration and change log |
| Findings log | {path}/autoloop-findings.md | Complete findings and issue list |
| Progress tracker | {path}/autoloop-progress.md | Detailed record of each iteration round |
| This report | {path}/ | Final report (file naming follows the unified output naming section in references/loop-data-schema.md) |
| Structured data | {path}/autoloop-results.tsv | Structured iteration log (shared by all templates) |
