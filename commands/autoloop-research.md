---
name: autoloop-research
description: >
  AutoLoop T1: Research task. T1 remains the general research entry point; when the topic is a market/industry study, it defaults to the high-standard mode:
  fixed core chapters, every chapter must include data + analysis + conclusion, and supports adding special analysis modules by "industry + direction/topic".
  See references/quality-gates.md row T1 for the quality gate threshold.
  Trigger: /autoloop:research or any task that requires systematic research.
---

# AutoLoop T1: Research — High-Standard Research

## T1 Task Definition (Required Reading)

- **T1 remains the broad research entry point**: suitable for systematic research, landscape studies, solution research, industry research, and similar work.
- **Market/industry topics default to the highest standard**: if the research object is an industry, track, market, jurisdiction, value chain, or business ecosystem, use **"T1: High-Standard Market/Industry Research Report"** from `assets/report-template.md` by default.
- **Direction/topic can add special modules**: if the topic is "subject object + direction/topic", such as "gambling industry + AI job replaceability", add special analysis modules on top of the core industry report.
- **Success state**: the final report must be a formal report that readers can use directly, and its core arguments must be supported primarily by web/public-source research completed within this task, not by rewriting old internal drafts.
- **Default implementation is multi-agent orchestration**: the lead agent breaks down chapters, dispatches researcher / verifier subagents, collects chapter evidence packs, resolves conflicts, decides whether another round is needed, and unifies the final draft.
- **Multiple rounds are optional**: multi-round OODA is a mechanism for evidence strengthening and convergence, not the definition of T1; if a single round already meets the depth and sourcing requirements, the task can conclude.

## Prerequisites for Execution

Read `autoloop-plan.md` to get the task parameters. If the file does not exist, configure it first through `/autoloop:plan`.

Round 2+ OBSERVE starting point:

- First read the reflection section in `autoloop-findings.md` to obtain remaining issues, effective / ineffective strategies, identified patterns, and lessons learned.
- Read recommended strategies in `references/experience-registry.md` that match the current topic, and pass them into the DECIDE stage as reference.

---

## Report Output Boundaries (Final Report)

The final reader-facing T1 report must **never** include:

- Internal runtime information: such as "evidence strategy", round number, subagent, parallel search, SSOT, JSON, render, progress, state, and similar wording.
- Quality and process information: such as quality scores, coverage / credibility, gates, iteration trail, and stop conditions.
- Explicit methodology headings: such as "problem definition", "issue tree / MECE", "hypothesis-driven", or "research method".
- Internal validation notes: such as confidence rules, evidence priority, cross-verification mechanism, or gap-registration mechanism.
- File / system traces: such as script names, repository paths, working directories, or the word `AutoLoop`.
- Template prompts and editor notes.

The beginning of the report may retain:

- Title
- Topic
- Objective
- Analysis date
- Information boundary

---

## Topic Identification: Subject Object + Additional Direction

Before starting research, break the topic into two layers:

1. **Subject object**: such as industry, market, track, company cluster, jurisdiction, or problem domain.
2. **Additional direction**: such as AI, regulation, investment logic, overseas expansion, job replaceability, supply chain, organization, or technology trends.

### Decision Rules

- If the subject object is an industry / market / track / value-chain analysis, enter **high-standard industry mode**.
- If "industry + direction/topic" appears together, include:
  - **Core industry chapters**
  - **Special direction modules**
- If it is not a market/industry topic, T1 still applies, but chapter names may be adapted to the topic; however, the reader-facing boundary must still be maintained, and it should still satisfy "data + analysis + conclusion" as much as possible.

---

## Lead Agent / Subagent Protocol

The default T1 collaboration model is:

- **Lead agent**
  - Determine whether the task enters T1 and whether it enters high-standard industry mode
  - Break the topic into core chapters and special modules
  - Dispatch researcher / verifier subtasks for each chapter or special subtopic
  - Collect chapter evidence packs, deduplicate them, resolve conflicts, and judge which chapters are still thin
  - Own the final reader-facing writing and integration
- **Researcher subagent**
  - Only handles external search and evidence gathering for a specific chapter or special subtopic
  - Returns a chapter evidence pack in the required format
- **Verifier / cross-check subagent**
  - Checks key judgments for framing, sourcing, strength of claim, and conflicts

**Rules**:

- Subagents do not directly write final report prose by default.
- The lead agent must unify the tone, structure, and narrative of the final draft to avoid repetition or style drift caused by directly stitching together multi-agent outputs.

---

## Lead Agent Task Breakdown Guide

When the lead agent breaks down a research task, it should use the following strategy choices and quality baselines.

### Breakdown Method Selection

Choose the most suitable breakdown method based on the topic characteristics:

| Breakdown Method | Applicable Scenario | Example |
|---------|---------|------|
| **By topic** | Industry landscape, multi-dimensional analysis | Market size / value chain / regulation / labor / AI stack / job trends |
| **By data source** | Data-driven research, cross-verification required | Public reports / job platforms / social media / patent data / financial statements |
| **By subquestion** | Question-driven research, decision support | Who is using AI? / What is being replaced? / Where is the resistance? / What does the cost structure look like? |
| **Hybrid** | Complex topics | Break core chapters by topic + break special modules by subquestion |

### Parallel vs. Serial Decision Rules

| Condition | Dispatch Mode |
|------|---------|
| **No data dependency** between chapters (such as "market size" and "regulatory environment") | Dispatch subagents **in parallel** |
| Chapter B needs the conclusion of Chapter A as input (such as "AI stack" depending on the output of "value chain") | Run **serially**; dispatch B after A completes |
| The same chapter requires validation from multiple independent sources | Dispatch multiple researchers **in parallel** to search different sources |

### Chapter Depth Baseline

Each chapter (or research block) is only considered "deliverable enough" if it meets the following baseline:

- **≥3 independent data sources**: avoid dependence on a single source
- **≥2 quantitative data points**: numbers / percentages / monetary figures, not purely qualitative description
- **≥1 company or regional example**: make the chapter concrete and avoid empty generalization
- **Explicit distinction**: direct evidence vs. organizational signals vs. cautious inference

**Below baseline** → the lead agent should either gather more evidence in the current round or mark it as a next-round priority, rather than submitting it directly.

### Recommended Breakdown Count

- Industry landscape research: **8-10** core chapters + **3-6** special modules
- Solution comparison research: break down by number of candidate solutions × number of evaluation dimensions
- Problem-driven research: break down by number of core questions, with each question as an independent research block

---

## High-Standard Industry Mode: Mandatory Core Chapters

Market/industry research uses the following core chapters by default:

1. Title + Topic + Objective
2. Market Size and Growth
3. Demand Side / Customer Structure
4. Value Chain and Profit Pool
5. Competitive Landscape and Major Players
6. Regulatory and Policy Environment
7. Technology and Key Change Factors
8. Business Model / Revenue-Cost Structure / Operating Leverage
9. Major Risks, Disputes, and Uncertainties
10. Overall Judgment and Implications
11. Data Sources

Write the **information boundary** in the title section, not as a standalone body chapter.

### Minimum Standard for Each Chapter

Each core chapter must contain all of the following:

- **Data**: at least 1 set of key data, table, or verifiable fact
- **Analysis**: explain relationships, structure, drivers, or comparisons
- **Conclusion**: a clear chapter-level judgment

If any chapter is missing one of these elements, it is considered **insufficient in depth** and must be supplemented in the next round.

### Default Goal for Each Chapter

In high-standard industry mode, each chapter should first produce a "chapter evidence pack" rather than a summary. The chapter evidence pack must at least support the lead agent in producing:

- Fact layer: verifiable data, structural breakdowns, changes over time, company examples, regional differences
- Explanation layer: drivers, mechanisms, comparisons, segmentation, boundaries
- Judgment layer: chapter conclusions and how strongly they can be asserted
- Traceability layer: source URLs and evidence limits

---

## Rules for Special Direction Modules

If the topic includes an additional direction, add special modules on top of the core industry chapters.

### Common Special Directions

- AI / Automation
- Regulation deep-dive
- Investment logic
- Overseas expansion
- Supply chain
- Organization and talent
- Job replaceability

### Example: Industry + AI Job Replaceability

The special module should contain at least:

1. AI technology penetration and current application status
2. Role / function mapping
3. Replaceable and non-replaceable mechanisms
4. Leading-company case studies
5. Organization and talent trends
6. Special-module conclusion

The special module must also satisfy: **data + analysis + conclusion**.

### Task Breakdown for Special Modules

If the special direction is AI / automation / organization / job replaceability, prioritize breaking it down by **work package** rather than only by job title:

- Which tasks are automated first
- Which tasks remain human-handled
- Which tasks carry regulatory responsibility, exception handling discretion, or high-value relationship attributes
- Which judgments have strong direct evidence and which are only cautious inference

---

## Dimension / Chapter Generation Rules

### A. Market / Industry Research (Default Highest Standard)

If the user does not explicitly provide dimensions, generate them in the following order:

#### Core Chapter Dimensions

1. Market size and growth
2. Demand side / customer structure
3. Value chain and profit pool
4. Competitive landscape and major players
5. Regulatory and policy environment
6. Technology and key change factors
7. Business model / revenue-cost structure / operating leverage
8. Risks, disputes, and uncertainties

#### Special Direction Dimensions (If Any)

Generate 3-6 subdimensions based on the additional direction in the topic.

Example: AI job replaceability

1. AI technology maturity and penetration
2. Role / function segmentation
3. Replacement mechanisms and retention mechanisms
4. Leading-company case studies
5. Talent trends and organizational impact
6. Special conclusion and boundaries

### B. Other T1 Topics

Other research topics may continue to define custom dimensions based on the problem domain, but should still try to ensure:

- Complete structure
- Key judgments supported by evidence
- The final draft is readable for end readers

---

## Round 1: Chapter Planning + Initial Search

### OBSERVE (Round 1 Baseline Collection)

Round 1 has no historical data, so perform baseline collection: current finding count = 0, covered chapters / dimensions = 0, all quality gate scores = 0. Write this into `autoloop-progress.md` as the iteration 0 baseline.

### 1.1 Chapter / Dimension Planning

- Write the following into `autoloop-plan.md`:
  - Research topic
  - Subject object
  - Additional direction (if any)
  - Core chapters
  - Special direction modules (if any)
  - Exclusion scope and information boundary
- For market/industry research mode, the recommended total number of dimensions is **8-12**; a smaller number of precise dimensions is better than meaningless over-generalization.

### 1.2 Parallel Search

Assign one researcher subagent to each core chapter dimension / special dimension and run them in parallel (see `references/agent-dispatch.md` for dispatch rules).

### 1.2.1 Standard Researcher Subagent Output: Chapter Evidence Pack

Each researcher subagent must return a **chapter evidence pack** in a unified format, containing at least:

- `chapter_id`
- `chapter_name`
- `key_datapoints`
- `company_examples`
- `regional_differences`
- `mechanism_explanations`
- `source_urls`
- `evidence_limits`
- `draft_conclusions`

If the work is a special module such as AI / job replaceability, it should also include:

- `work_package_breakdown`
  - `role`
  - `task_bundle`
  - `automatable_part`
  - `retained_human_part`
  - `evidence_strength`

Task template for each subagent:

```text
You are the researcher subagent responsible for the following research block:

Topic: {research topic}
Research block: {chapter name or special subtopic}
Objective: produce a "chapter evidence pack" for the final report so the lead agent can later integrate it into:
- Data
- Analysis
- Conclusion

Requirements:
1. Find at least 3 independent sources
2. Extract key data points (numbers, facts, directly quotable lines)
3. Label each information point with its source URL and credibility
4. If conflicting information is found, record both sides in parallel
5. Prioritize verifiable facts, structural breakdowns, company examples, regional differences, changes over time, and methodology notes
6. Do not write full report paragraphs directly; focus on returning an evidence pack that the lead agent can review, deduplicate, and strengthen in later rounds

Output format:
## Chapter Evidence Pack: {research block name}

chapter_id: {fixed chapter name or special subtopic ID}
chapter_name: {name}

### key_datapoints
- {data point / fact / metric} (Source: {URL}, Credibility: high/medium/low)

### company_examples
- {company example} (Source: {URL})

### regional_differences
- {regional or jurisdictional difference}

### mechanism_explanations
- {why this happens / where the difference comes from / what the mechanism is}

### source_urls
- {URL 1}
- {URL 2}

### evidence_limits
- {differences in methodology / places where strong claims are not justified / boundaries that only apply to certain market types}

### draft_conclusions
- {cautious judgment supported by this research block}

### information_gaps
- {key information still not found}

### work_package_breakdown (required only for special modules)
- role: {role/function}
  task_bundle: {task bundle}
  automatable_part: {part automated first}
  retained_human_part: {part still handled by humans}
  evidence_strength: {strong direct evidence / organizational signal / cautious inference}
```

### 1.3 Result Integration

After all researcher subagents complete:

1. Append findings to `autoloop-findings.md`
2. Build the mapping between chapters / special modules
3. Check whether each chapter evidence pack includes:
   - key_datapoints
   - mechanism_explanations
   - draft_conclusions
   - source_urls
4. Identify information gaps, framing conflicts, and evidence strength
5. Mark which chapters are still "thin":
   - Missing the data layer
   - Missing structural breakdown
   - Missing company / regional examples
   - Missing source-to-chapter mapping
   - Conclusions appearing before evidence
   - Incomplete subagent return format

---

## Quality Gate Scoring

See row T1 in `references/quality-gates.md` for the quality gate threshold:

- Coverage
- Credibility
- Consistency
- Completeness

The CHECK stage is still scored by an independent evaluator according to `references/quality-gates.md`.

### T1 Supplemental Checks (Chapter Depth)

In addition to the above gates, market/industry research mode must also run chapter-depth checks:

1. Whether all mandatory chapters contain content
2. Whether every chapter includes "data + analysis + conclusion"
3. Whether the special direction module is complete
4. Whether key judgments are cross-verified
5. Whether all internal noise has been removed from the final report
6. Whether every chapter has enough verifiable data blocks instead of only summary statements
7. Whether direct evidence, organizational signals, and analytical inference are clearly distinguished
8. Whether data sources are organized by chapter rather than as a pure bibliography

These supplemental checks can be recorded in `autoloop-progress.md` and `autoloop-findings.md` to determine the focus of the next round.

---

## Inter-Round Decision Rules

After each round, decide the next step based on the gates and chapter depth:

### Scenario A: Everything Meets Standard

- Coverage, credibility, consistency, and completeness meet the T1 threshold
- All mandatory chapters are present
- Every chapter includes data + analysis + conclusion
- Special modules (if any) are complete

→ Stop iterating and move to result integration

### Scenario B: Coverage Is Insufficient

- Assign new researchers to missing chapters or missing dimensions
- Check whether new research blocks need to be added

### Scenario C: Credibility Is Insufficient

- Add primary materials or independent sources for key judgments
- Prioritize official documents, annual reports, regulation, academic sources, and raw data

### Scenario D: Consistency Is Insufficient

- Investigate conflicting information in depth
- Attribute conflicts to time differences / methodology differences / scenario differences / real disputes

### Scenario E: Completeness Is Insufficient

- Add sources one by one to unsupported statements
- Downgrade unsourced judgments to "to be verified" or remove them

### Scenario F: Chapter Depth Is Insufficient

Trigger conditions include:

- A chapter has data but no analysis
- A chapter has analysis but lacks hard data
- A chapter has no explicit conclusion
- The special module lacks depth
- Key judgments are not cross-verified
- Cross-evidence is missing across company / region / product / time dimensions
- There are many sources, but they do not map stably to chapters
- The chapter evidence pack returned by a subagent is missing key fields
- The chapter only contains summary statements and lacks enough verifiable fact blocks

→ The next round should focus on supplementing "chapter depth", not just increasing quantity

---

## Round 2-N Execution

```text
OBSERVE:
  Read the reflection section in findings.md
  Read the current chapter-depth check results
  Identify the lowest-scoring gate and the weakest chapters

ORIENT:
  Determine the chapters / special modules to strengthen this round (up to 3)
  Define specific tactics: add data, add structural breakdown, add company/regional examples, add cross-verification, add conclusions, improve source organization

DECIDE:
  Assign subagents
  Run independent chapters in parallel; run strongly dependent chapters serially
  Specify the required chapter evidence pack format for each subagent

ACT:
  Run searches and integrate the results back into findings.md
  Update chapter-depth status
  Identify missing return fields and conflict items

VERIFY:
  Recalculate T1 gate scores
  Recheck whether chapters contain data + analysis + conclusion
  Recheck whether chapter evidence packs are sufficient to support reader-facing writing

EVOLVE:
  Decide whether to terminate
  If the same chapter improves only minimally for 2 consecutive rounds, switch search strategy

REFLECT:
  Write the 4-layer reflection structure table into findings.md
```

---

## Cross-Verification Mechanism

At the end of each round, run the cross-verifier subagent:

```text
Task: check whether key judgments in findings.md contain contradictions or rely on a single source

Output:
## Conflict Report

| ID | Research Block | Claim A (Source) | Claim B (Source) | Analysis | Handling Suggestion |
|------|--------|-----------------|-----------------|------|---------|
```

Its purpose is to:

- Detect factual contradictions
- Detect framing conflicts
- Detect insufficient support for conclusions
- Identify which judgments can only be downgraded to risks or points of dispute

---

## Source Priority

See the credibility section of `references/quality-gates.md` for source credibility tiers. General priority order:

1. Official documents, regulatory announcements, financial statements, raw databases
2. Peer-reviewed research, authoritative industry institutions
3. Mainstream professional media
4. Expert content with named authors and endorsement
5. General blogs and community content (requires cross-verification)

---

## Result Integration

After the stop condition is met, integrate the final report (see `references/loop-data-schema.md` for filename rules and `assets/report-template.md` for the format).

### T1 Final Draft Requirements

- Market / industry topics must be output as **"T1: High-Standard Market/Industry Research Report"**
- Every mandatory chapter must contain: data + analysis + conclusion
- If an additional direction exists, add a special module
- The report must not include any internal runtime details, gate information, explicit methodology headings, or system traces
- Body arguments must come from the findings accumulated through this round of research, not from directly rewriting historical drafts
- The factual layer in the final draft should reflect as much as possible from the chapter evidence pack: structural breakdown, company examples, regional differences, changes over time, and evidence boundaries
- Conclusions in the final draft must be built on top of evidence and cannot replace the factual layer with one or two summary sentences

### Final Structure of findings.md

```markdown
# AutoLoop Research Findings

## Executive Summary
- Topic: {research topic}
- Research rounds: {N}
- Final scores: coverage {X}% / credibility {X}% / consistency {X}% / completeness {X}%
- Key conclusions (3-5 items)

## Research Block Details

### {research block 1}
{integrated content, organized by data / analysis clues / candidate conclusions / sources / gaps}

### {research block 2}
...

## Controversies and Uncertainties

| Topic | Claim A | Claim B | Current Handling |
|------|--------|--------|----------|

## Information Gaps
- {gap 1}

## Recommended Reading
- {key resource}
```

---

## Progress Tracking Format

Append a full 8-stage record to `autoloop-progress.md` for each round. Simplified T1 summary example:

```markdown
## Round {N} — {start time}

**Goal for this round**: strengthen {chapter / special module}

**Execution log**:
- {subagent 1}: {task} → {result}
- {subagent 2}: {task} → {result}

**Scores for this round**:
- Coverage: {previous round} → {current round}
- Credibility: {previous round} → {current round}
- Consistency: {previous round} → {current round}
- Completeness: {previous round} → {current round}

**Chapter depth check**:
- {chapter 1}: data / analysis / conclusion = {status}
- {chapter 2}: data / analysis / conclusion = {status}

**Decision**: {continue / stop}
**Next-round focus**: {specific plan}
```

---

## REFLECT Execution Rules for Each Round

After each round (including Round 1), execute this after EVOLVE / termination judgment. REFLECT must be written to a file and cannot be completed only in thought. Write the 4-layer reflection structure table into `autoloop-findings.md` (issue registration / strategy review / pattern recognition / lessons learned); see `assets/findings-template.md` for the format.

- **Issue registration**: record information gaps, source conflicts, and data-quality issues found in this round
- **Strategy review**: evaluate the effectiveness of search strategies / validation methods / integration approaches (keep | avoid | to be verified) (for strategy evaluation enums, see the unified status enums in `references/loop-data-schema.md`)
- **Pattern recognition**: which sources consistently provide high-quality information, and which dimensions repeatedly show gaps
- **Lessons learned**: summarize the effectiveness of search keywords / data sources / analysis methods
- **Protocol review**: which chapter evidence-pack fields are most effective, which fields are frequently missing, and which chapters are easiest to make too thin
- **Experience write-back**: write the strategy effects from this round into `references/experience-registry.md` (strategy ID, applicable scenario, effect score, execution context, following the effect-record table format)
