# T1 High-Standard Research Report (Design Notes)

> **SSOT body template**: `assets/report-template.md` -> section **"T1: High-Standard Market / Industry Research Report"**.
> **Applicability rule**: T1 remains the general research entry point, but when the topic is a **market / industry research** topic, it defaults to **high-standard mode**. If the prompt includes an additional direction (for example, "industry + AI job substitution"), add a special analysis module on top of the main industry report.

---

## 0. What T1 Fundamentally Is

**Definition of T1**:

1. **Research first, writing second**: the final report must be built on multi-source web / public-source research completed within this task, not on writing first and retrofitting citations later.
2. **Industry/market topics default to the highest standard**: market or industry research must use the fixed core chapter structure and deliver the quality of a high-standard industry study.
3. **Main agent orchestrates, subagents gather evidence**: the default T1 implementation is that the main agent identifies the topic, splits it into chapters, delegates researcher / verifier subagents, and integrates chapter evidence packs into the final report.
4. **Multiple rounds are a convergence tool, not part of the definition**: if the first round already satisfies depth, sourcing, and cross-validation requirements, T1 may end in one round; if depth is insufficient, continue with additional evidence rounds.

**Common failure modes that do not qualify as a valid T1**:

- rewriting old notes or internal drafts into report form without doing independent research in the current run
- piling up material without producing structured analysis and chapter conclusions
- mixing internal execution noise, quality gates, or system traces into the final report
- the main agent does not split chapters or delegate subagents, and instead writes the report alone, causing unstable evidence density and depth
- subagents return only summaries rather than chapter evidence packs that the main agent can review, deduplicate, and extend in later rounds

### 0.1 Role Division in the Multi-Agent Protocol

Under the goal of making T1 practical for LLM use, it should primarily be understood as a **multi-agent research protocol**:

- **main agent / orchestrator**
  - decides whether the task is T1
  - identifies the primary subject and additional direction
  - generates core chapters and special modules
  - dispatches researcher / verifier subagents for each chapter
  - merges chapter evidence packs, resolves conflicts, and decides whether another round is needed
  - produces the final report in a single unified voice
- **researcher-type subagents**
  - only perform external research and evidence gathering for a specific chapter or special subtopic
  - return structured chapter evidence packs instead of final prose
- **verifier / cross-check subagents**
  - specifically check definition conflicts, source independence, whether conclusions are strong enough to state directly, and whether a claim should be downgraded into a risk or controversy

**Responsibility boundaries**:

- writing / synthesis remains centralized in the main agent by default, to avoid multiple subagents drafting final prose directly and causing tone drift, structural distortion, or duplication
- therefore the key question for T1 is not just "what the template looks like", but "how the main agent decomposes the task, how subagents return evidence, and how the main agent decides on follow-up rounds and assembles the final report"

---

## 1. Reader Boundary of the Final Report

The T1 deliverable is a **formal report written for humans**. It must preserve only information useful to readers and must not leak internal execution details.

### 1.1 The report must not include

- internal execution information such as "evidence strategy", round numbers, subagents, parallel search, SSOT, JSON, render, progress, state, and similar terms
- quality/process information such as quality scores, coverage / credibility, gates, iteration history, and termination conditions
- explicit methodology section titles such as "problem framing", "issue tree / MECE", "hypothesis-driven", or "research method"
- internal validation explanations such as confidence rules, evidence priority, cross-validation mechanisms, or gap-registration mechanisms
- file / system traces such as script names, repository paths, working directories, or the word `AutoLoop`
- template hints, editorial notes, or markers such as "remove after final draft"

### 1.2 What may appear at the beginning of the report

- title
- topic
- objective
- analysis date
- information boundary

These belong to reader-facing business metadata. Beyond that, the opening should not contain any process explanation.

---

## 2. How Methodology Should Be Embedded Invisibly

The following mapping guides writing. It does **not** mean these phrases should appear as headings in the final report.

| Methodology Idea | How it appears in a high-standard report |
|------------|----------------------|
| fact-based | every chapter includes data tables, verifiable facts, and sources |
| structured / MECE | use fixed core chapters to cover market, demand, value chain, competition, regulation, technology, economics, risk, and conclusions |
| hypothesis-driven | in the synthesis section, state which initial hypotheses were supported, revised, or left under-evidenced |
| pyramid writing | the synthesis section must lead with core conclusions; regular chapters still use data, analysis, and conclusion, but the judgment must be traceable to the evidence above it |
| cross-validation | key judgments should ideally be supported by multiple sources; when cross-validation is not possible, they may still appear, but only as risks or controversy points |

This may be used alongside personal "McKinsey-style rapid industry understanding" notes; the original notes are not vendored in this repository.

---

## 3. Mandatory Core Chapters for Market / Industry Topics

When the T1 topic is market / industry research, the report must include at least:

1. title + topic + objective
2. market size and growth
3. demand side / customer structure
4. value chain and profit pools
5. competitive landscape and major players
6. regulatory and policy environment
7. technology and key drivers of change
8. business model / revenue-cost structure / operating leverage
9. key risks, controversy points, and uncertainties
10. synthesis and implications
11. data sources

**Information boundary** should not appear as a standalone body chapter. It belongs in the front matter near the title.

### 3.1 Minimum content standard for each chapter

Each core chapter must contain all three of the following:

- **data**: at least one table, key metric set, or group of verifiable facts
- **analysis**: explanation of structure, causes of change, comparative relationships, or driving mechanisms
- **conclusion**: an explicit chapter-level judgment rather than a list of materials

### 3.2 Shared characteristics of strong reference reports

If we reverse-engineer the target form from high-quality samples, qualified final reports usually share these traits:

- **evidence first**: give readers verifiable data, structural breakdowns, company examples, regional differences, time-series changes, and scope notes before giving explanations and conclusions
- **analysis extends evidence instead of replacing it**: analysis explains why patterns exist, where differences come from, and which mechanisms matter most. It should not replace evidence with a few high-level sentences
- **conclusions sharpen rather than carry the chapter**: conclusions compress and finalize the chapter's argument; they are not the chapter body
- **sources are traceable**: sources should ideally be grouped by chapter at the end, or at minimum organized so that readers can trace them back easily rather than facing a single long bibliography dump
- **length follows information density**: brevity is not the goal by itself. As long as information density remains high, a long report is acceptable and should not be compressed just to reduce line count

### 3.3 What counts as a "thin draft"

For T1, the following should be treated as **insufficient chapter depth**:

- only top-level judgments, without enough verifiable data blocks
- one average value with no structural breakdown such as regional, product, company, or time differences
- heavily stated conclusions that readers cannot independently reconstruct from the evidence above
- many sources listed, but no stable mapping between sources and chapters
- special modules that only list job titles or topic names, without breaking them down into work packages, mechanisms, retained boundaries, or evidence strength

---

## 4. Additional Direction / Theme Overlay Mechanism

If the prompt combines a primary subject with an additional direction/theme, the structure is:

**main industry report + special module**

### 4.1 Combination Rule

- the **primary subject** determines the core frame, such as "gambling industry", "cross-border SaaS", or "Southeast Asian live-commerce"
- the **additional direction** determines the special module, such as AI, regulation, investment logic, international expansion, supply chain, job substitution, and so on

### 4.2 Example: Industry + AI Job Substitution

If the topic is "gambling industry + AI job substitution", the report must:

1. fully cover the main industry report chapters first
2. then add a special AI job substitution module containing at least:
   - AI technology penetration and current applications
   - role / function mapping
   - replacement mechanisms and retention mechanisms
   - leading company case studies
   - organizational and talent trends
   - special-module conclusions

The special module must also satisfy the same rule: **data + analysis + conclusion**.

### 4.3 Work-Package Requirement for Special Modules

If the additional direction involves AI, automation, organization, or job substitution, the special module should be decomposed into **work packages** rather than stopping at job-title or theme names:

- which tasks get automated first
- which tasks remain human
- which tasks carry regulatory responsibility, exception handling, or high-value relationship attributes
- which judgments have strong direct evidence and which are only cautious inference

---

## 5. Division of Responsibility Across AutoLoop Artifacts

| Artifact | Responsibility |
|------|------|
| `autoloop-plan.md` | topic, boundary, primary subject, additional direction, core chapters, special modules, exclusions |
| `autoloop-findings.md` | raw research integration: facts, sources, controversies, and gaps organized by chapter / special module |
| `autoloop-report-{topic}-{date}.md` | the formal report for human readers; contains only reader-facing chapter content |
| `autoloop-results.tsv` / state JSON | scoring, iteration, and control data; not copied into the final report |
| `autoloop-progress.md` | round logs, strategy changes, and rewrite history; not copied into the final report |

### 5.1 Position of the Chapter Evidence Pack

To make T1 suitable for main-agent delegation, each chapter's intermediate output should be treated as a **chapter evidence pack**. Its role sits between findings and the final report:

- produced by researcher / verifier subagents
- used by the main agent for integration, deduplication, conflict handling, and decisions about further rounds
- not exposed directly to readers, but structured enough that the main agent does not need to reconstruct raw search results from scratch

The chapter evidence pack is the standard intermediate layer in T1; the final report is only the presentation layer.

---

## 6. Maintenance Rules

When adjusting the T1 industry research standard, update the following in order:

1. `assets/report-template.md`
2. `commands/autoloop-research.md`
3. `references/t1-formal-report.md`
4. `commands/autoloop.md`
5. `SKILL.md`
6. `references/quality-gates.md` if needed

### 6.1 Phase-Two Implementation Boundary

The current priority is **protocol, template, execution flow, and gates**, not immediately bringing the reader-facing final report into automatic `state/render` generation.

- phase-one goal: let the main agent reliably produce a high-quality T1 final report through standardized delegation, chapter evidence packs, and follow-up-round rules
- phase-two goal: only after the protocol is stable, consider structuring chapter evidence packs into state and adding reader-report rendering
