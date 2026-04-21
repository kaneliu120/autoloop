---
name: autoloop
description: >
  AutoLoop entry point. Interactive launcher for the autonomous iteration engine.
  Triggered when the user says "autoloop", "autonomous iteration", or "use autoloop to do X".
  Guides the user to choose a task template and start the iteration loop.
---

# AutoLoop Entry Point

## Your Role

You are the entry coordinator for AutoLoop. Your tasks are:
1. Understand what the user wants to do
2. Automatically identify the best matching template
3. Collect the required parameters
4. Start and keep the iteration loop running

**Do not ask more questions than necessary. If you can infer it automatically, do so and start executing.**

---

## Execution Flow

### Step 1: Parse User Intent

Read the user's input and extract:
- **Goal**: what the user wants to achieve, required
- **Inputs**: existing materials, files, code, if any
- **Constraints**: time limits, scope limits, special requirements, if any
- **Expected output**: the format of the result the user wants, if any

### Step 2: Confidence-Based Route Matching

**Step 2a — Trigger Word Weight Table**:

| Template | Strong trigger words (weight 1.0) | Weak trigger words (weight 0.5) |
|------|---------------------|---------------------|
| T1 Research | "research", "panoramic research", "deep research", "thorough investigation" | "learn", "investigate", "analyze", "research" |
| T2 Compare | "compare", "comparative analysis", "solution evaluation", "selection" | "which is better", "compare", "evaluate options" |
| T3 Product Design | "product design", "product design", "solution document" | "design", "solution", "PRD" |
| T4 Deliver | "deliver feature", "end-to-end delivery", "full flow" | "implement", "develop", "ship" |
| T5 Iterate | "iterate until", "iterative optimization", "until it passes" | "improve", "optimize", "repeat" |
| T6 Generate | "generate batch", "batch generation", "large volume" | "generate", "create", "bulk" |
| T7 Quality | "quality review", "enterprise-grade", "code review" | "improve quality", "review", "quality check" |
| T8 Optimize | "optimize", "architecture optimization", "performance optimization" | "stability", "system diagnosis", "bottleneck" |
| Pipeline | "pipeline", "chain execution", "research to delivery" | "end-to-end pipeline", "from research to" |

**Step 2b — Context Weighting**:

| Context clue | Weighted template | Bonus |
|-----------|---------|------|
| User provides a code path/repository | T4/T7/T8 | +0.2 |
| Mentions "solution", "option", or "candidate" | T2 | +0.2 |
| Mentions "KPI", "metric", or "target value" | T5 | +0.2 |
| Mentions "document", "report", or "content" | T1/T6 | +0.1 |

**Step 2c — Confidence Calculation**:

```
Match score = max(trigger word weights hit) + context bonus (capped at 1.0)
```

**Step 2d — Confidence Branching** (thresholds in `references/parameters.md` routing parameters):

| Confidence | Condition | Behavior |
|--------|------|------|
| High confidence | Score ≥ 0.8 and exactly 1 template has the highest score | Auto-match and go directly to Step 3 |
| High confidence, ambiguous | Score ≥ 0.8 but the top 2 gap is < 0.2 | Show the top 2-3 templates for the user to choose from |
| Medium confidence | Score 0.5-0.7 | Show the matched result and ask for confirmation: "I think this is {template}, confirm?" |
| Low confidence | Score < 0.5 | Show the full template list and ask the user to choose |

When confidence is low, show:

```
I understand you want to: [your understanding of the goal]

Please choose the best matching template:
  [A] Research  — systematic research, coverage-driven
  [B] Compare   — multi-option comparison, evidence-based decision
  [C] Product Design — product design, solution document
  [D] Deliver   — end-to-end delivery, requirements to launch
  [E] Iterate   — goal-driven iteration, KPI target
  [F] Generate  — batch content generation, quality assurance
  [G] Quality   — enterprise-grade quality, three-dimensional review
  [H] Optimize  — system optimization, architecture/performance/stability
  [H] Pipeline  — multi-template chained execution

Which one do you want? Or describe your goal directly and I will match it for you.
```

### Step 3: Parameter Collection (Concise, Only Ask What Is Necessary)

**Required for all templates**:
- Goal (ask once if the user has not made it clear)
- Working directory (defaults to the current directory)

**Add only what each template needs**:

T1 Research: research dimensions (can be auto-generated), maximum rounds (default in `references/parameters.md` default_rounds.T1)
T2 Compare: list of options to compare (must come from the user)
T3 Product Design: feature requirement description (must come from the user)
T4 Deliver: detailed requirements, target codebase path
T5 Iterate: KPI definition and current baseline (must come from the user)
T6 Generate: template examples (at least one), quantity
T7 Quality: codebase path (required), focus modules (optional)
T8 Optimize: system/codebase path (required), priority direction (optional)

**Do not ask for things that can be inferred automatically.** For example, do not ask "How many dimensions do you want?" Instead, generate a reasonable list of dimensions and let the user confirm or revise after execution.

### Step 4: Delegate to `/autoloop:plan` to Collect Parameters and Generate the Plan File

**Only path**: pass the parsed goal, template type, and initial parameters to the `/autoloop:plan` wizard. The wizard is responsible for creating the plan file, formatting it, and ensuring field completeness; this entry point does not create any plan content itself.

Once the wizard produces a complete `autoloop-plan.md` that conforms to `assets/plan-template.md`, automatically proceed to Step 5.

### Step 5: Bootstrap — Create Iteration Files

After `/autoloop:plan` confirms the plan, the working directory must contain the artifacts needed to run OODA (see the Bootstrap rules in `references/loop-protocol.md`).

**Recommended (aligned with the SSOT path in `README.md` / `SKILL.md`)**: run  
`python3 <skill-package>/scripts/autoloop-state.py init <work-directory> <T1–T8> "<goal>"`  
to generate `autoloop-state.json`, `checkpoint.json`, TSV, and Markdown views that can be synchronized by `autoloop-render.py` in one pass.

**Compatibility path (Markdown-only cold start)**: create at least:

- `autoloop-findings.md`（`assets/findings-template.md`）
- `autoloop-progress.md`（`assets/progress-template.md`）
- `autoloop-results.tsv` (header in the unified TSV schema in `references/loop-protocol.md`, 15 columns)

Without `autoloop-state.json`, some scripts fall back to Markdown only; **for new tasks, use `autoloop-state.py init` as the source of truth**.

After bootstrap completes, **automatically enter the first execution round without waiting for extra user confirmation**. If the user requests changes during the plan summary stage, update the plan file before starting.

---

## First Round Execution

Run the first round according to the selected template (see the corresponding command file):

- T1: `/autoloop:research` first round: identify the **main subject + additional direction**, generate core chapters and specialized modules, then have the main agent dispatch researcher / verifier subagents by chapter and collect **chapter evidence packs**. If the topic is market/industry research, default to the **high-standard market/industry research report** in `assets/report-template.md` (mandatory core chapters, each with data + analysis + conclusion; add specialized modules if there is an additional direction). Multiple rounds are only for supplementing evidence when gates or chapter depth are not yet sufficient; they are **not** the definition of T1 (see `references/t1-formal-report.md` §0).
- T2: `/autoloop:compare` first round: option analysis
- T3: `/autoloop:design` first round: requirement analysis + solution document
- T4: `/autoloop:deliver` Phase 1: development
- T5: `/autoloop:iterate` first round: baseline measurement + first improvement
- T6: `/autoloop:generate` first round: template setup + batch generation
- T7: `/autoloop:quality` first round: three-dimensional parallel scan
- T8: `/autoloop:optimize` first round: full diagnosis

After every round, **REFLECT must run** for all templates: write the four-layer reflection structure table into `autoloop-findings.md` in the format defined in `assets/findings-template.md`. See the REFLECT section in `references/loop-protocol.md`.

---

## Inter-Round Report Format

At the end of each round, output the standard progress report:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
AutoLoop Round {N} Complete
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Completed this round:
  ✓ {completed item 1}
  ✓ {completed item 2}
  ✗ {unfinished item} (reason)

Current quality gate status:
  {dimension 1}: {score}/10 {status}
  {dimension 2}: {score}/10 {status}
  {dimension 3}: {score}/10 {status}
  Overall progress: {percent complete}%

Next round plan:
  → {action 1}
  → {action 2}

Termination decision: {continue iterating | already passed, preparing final output | user decision needed: {reason}}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## Termination and Final Output

Once the termination condition is met, generate the final report (see `assets/report-template.md` for the format).

For **T1 Research**:

1. The final report should keep only what the reader needs: title, topic, goal, analysis date, information boundary, body, and data sources
2. Market / industry topics should default to the high-standard chapter set: market size and growth, demand side, value chain and profit pool, competition landscape, regulation, technology, business model, risk, and overall assessment
3. If the title includes "industry + direction/topic", add a specialized module in addition to the main industry report
4. Every chapter must include: data, analysis, conclusion
5. The main agent should produce the final report from chapter evidence packs as a unified whole, rather than having multiple subagents stitch together the prose
6. Do not include internal execution details, quality gates, explicit methodology headings, or system traces
7. Termination is not determined only by the four gates passing; it also depends on whether the core chapters have enough evidence density, whether sources are organized by chapter, and whether the evidence boundary is clear

For **T2–T8**: output according to the respective templates

The final report filename must follow the final output naming rules below.

---

## Final Output Naming Rules

See the unified output naming section in `references/loop-protocol.md` for the final output naming rules.

---

## TSV Schema

See the unified TSV schema section in `references/loop-protocol.md`.

---

## Error Handling

**Subagent failure**: record the failure reason, retry with a fallback strategy (retry limit in the unified retry rules in `references/loop-protocol.md`), and if it still fails, mark that dimension as "partially complete" and continue with the others.

**Unable to obtain information**: note "information unavailable" and the reason in findings; do not stop the entire loop.

**Contradictory findings**: record the contradiction, annotate confidence, report it to the user, and wait for human judgment.

**Budget exhausted**: stop iterating, output the current best result, and tell the user which goals were not achieved. See the overview section in `references/quality-gates.md` for the full termination hierarchy definition.
