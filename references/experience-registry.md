# Experience Registry — Global Experience Library

## Overview

The experience library is the core component of AutoLoop's second feedback loop (iteration of the methodology itself). It enables experience to flow across tasks, making the Nth execution faster, more accurate, and more efficient than the first.

**Relationship to other files**:
- `loop-protocol.md`: OBSERVE reads global experience; REFLECT produces experience entries
- `evolution-rules.md`: defines the approval workflow for protocol changes after experience distribution
- `findings-template.md`: the `strategy_id` in the strategy evaluation table maps to the strategy-effect table in this library

> Version semantics are defined in `loop-protocol.md` §Version Semantics (single authority).

---

## Experience Capture Flow

```text
Experience output (REFLECT phase)
  ↓
Evaluation (type + impact level + confidence)
  ↓
Distribution (write to the corresponding file by type and level)
  ↓
Validation (verify whether the experience is effective in the next similar task)
  ↓
Retirement (2 consecutive failed validations → mark as retired)
```

**Write-back rule**: when a strategy's `use_count` reaches 2, the three required fields `mechanism` / `preconditions` / `contraindications` must be added (see "Detailed Strategy Description Format" below).

---

## Experience Types and Distribution Targets

| Experience type | Distribution target | Approval level | Example |
|---------|---------|---------|------|
| Scoring-standard defect | `quality-gates.md` | Low risk: AI automatic | "T7 SQL injection checks easily miss stored procedures" |
| Parameter calibration | `parameters.md` | Medium risk: AI promotes + validate next round | "T1 is more efficient with 3 rounds than 5" |
| Strategy effect | Strategy-effect library in this file | Low risk: AI automatic | "Module-by-module scanning improves by 30% over full scan" |
| Template improvement | Corresponding template file | Low risk: AI automatic | "Adding a root-cause column to the findings table is more useful" |
| Process defect | `loop-protocol.md` or the corresponding command | High risk: user confirmation | "T4 is missing a database rollback verification step" |
| Gate threshold adjustment | `quality-gates.md` | High risk: user confirmation | "T7 security should be lowered from 9 to 8" |

---

## Global Strategy-effect Library

The table below records strategy-effect data accumulated across tasks for OBSERVE to reference.

| strategy_id | template | dimension | description | avg_delta | side_effects | use_count | success_rate | status |
|------------|----------|-----------|-------------|-----------|-------------|-----------|-------------|--------|
| (initially empty; accumulates as tasks run) | | | | | | | | |

**P3-01 Main table and audit (implementation convention)**:
- **Main table**: each `strategy_id` keeps **only one row** (`autoloop-experience.py write` is an upsert that updates aggregate fields such as `use_count` / `success_rate` / `avg_delta` / `description` / `status`).
- **Audit**: append `experience-audit.md` in the **same directory** as `experience-registry.md` (one entry per `write`; one entry when `consolidate` merges duplicate rows). (This file is created automatically the first time `autoloop-experience.py write` is called; do not create it manually.)
- **Historical duplicate rows**: run `autoloop-experience.py <work_dir> consolidate [--dry-run]` (it must be able to resolve this file; this file must exist either under `references/` in the work directory or under a skill bundle `references/`). During merge, **prefer recomputing from the audit** for `use_count` / `avg_delta` / `success_rate`; without audit, use the arithmetic mean of existing `avg_delta` values in the duplicate rows (approximation).
- **`multi:`**: when `strategy_id` starts with `multi:`, **write audit only** and do not modify the main table (mixed attribution; see the attribution rules below).

**P3-06 `multi:` strategy constraints (implementation convention)**:
- **Format**: `multi:{SNN-description,SNN-description}` or `multi:{SNN-description+SNN-description}` (`+` / `,` are both allowed and may be mixed); there must be **exactly one layer** of braces; the `multi:` prefix is case-insensitive.
- **Sub-strategies**: at least **2**; each must match the same `SNN-description` form as a single strategy; **duplicates are forbidden**.
- **write**: `autoloop-experience.py write` **rejects** invalid `multi:` values before validation passes; `--status` is **forbidden** on `multi:` values (they do not enter the main-table lifecycle).
- **validate**: rows with `multi:` in `results.tsv` / SSOT `results_tsv` must pass the format validation above, and each sub-strategy must be traceable in findings (or `strategy_history`); `side_effect` is recommended to explicitly say "mixed attribution" (consistent with `loop-protocol`).

**P3-02 Context matching (implementation convention)**:
- **`query`**: when `--tags` (task `context_tags`) is non-empty, keep only strategies whose `context_tags` inside `description` (written by `write --tags`, stored inside `[...]` immediately after `@YYYY-MM-DD`) have **intersection >= 2** with the task tags; when `--tags` is absent, no overlap filtering is applied (first-round cold start, consistent with `loop-protocol`).
- **Context-scoped supplemental table**: effective `status` prefers an **exact match** first (task tag set = row tag set); otherwise select the row where **task tags ⊇ row tags** and the row has the **largest number of tags**; if nothing matches, fall back to the global `status` in the main table.
- **Controller**: when `plan.context_tags` is a string or a string list, pass it to `query --tags`; omit the argument by default for cold start.

**write `--mechanism` (optional)**: `autoloop-experience.py write --mechanism "..."` writes a mechanism summary into the `[mechanism: ...]` fragment inside the main-table `description`, making it easier to satisfy the "add mechanism" documentation requirement once `use_count>=2` (consistent with the detailed strategy description format below). **Context-scoped supplemental table**: currently only `query` reads it; there is **no** separate `write` path for writing rows into the scoped section. Full scoped writes and migration to an "archive section" remain v2 / backlog items (see list item F08).

**write state machine and `use_count` (implementation convention)**:
- Without `--status`, the automatic transition **starting state** is the current row's `status` for that `strategy_id` in the main table (you must not overwrite statuses such as "Retired" with a fixed "Observe" default when `--status` is omitted).
- "2 consecutive `delta>0` / `delta<=0`" is evaluated by comparing the **score from the most recent `write` for that strategy in `experience-audit.md`** with the **current round `--score`**; `use_count`, `avg_delta`, and `success_rate` are also recomputed from the full score sequence of all `write` records for that strategy in the audit (chronological order) plus the current round, matching the main-table one-row upsert behavior.
- **Recommendation should remain stable once promoted**: after `query` marks a strategy as **maintain**, unless a later `write` explicitly overrides it with flags such as `--effect`, the main-table `status` / recommendation semantics for that row should remain stable, independent from the "2 consecutive" retirement logic (retirement applies only to the failed-validation path).

**Field descriptions**:
- `strategy_id`: unique strategy identifier, consistent with `results.tsv` and `findings.md`
- `template`: applicable template (`T1-T8`, or `"general"`)
- `dimension`: target dimension
- `description`: one-line strategy summary; see "Detailed Strategy Description Format" below for the detailed form
- `avg_delta`: the **arithmetic mean** of the per-round `--score` values written by `write` (single-round score / gate delta); it shares the same source as `use_count` and `success_rate`, and when `experience-audit.md` exists, **the authoritative source is the full score sequence of all `write` records for that `strategy_id` in the audit** (consistent with `write` aggregation into the main table)
- `side_effects`: list of known side effects
- `use_count`: total usage count (= length of the score sequence above)
- `success_rate`: ratio of rounds with positive effect (share of rounds where `delta > 0`; consistent with the promotion rule `delta > 0`)
- `status`: Recommended / Candidate Default / Observe / Retired (lifecycle state enum)
- `applicable_templates`: list of applicable templates. For example, `[T1,T2]` means only applicable to T1 and T2; `[*]` means applicable to all templates. Default is the current template (that is, the value of the `template` field). Write with `write --templates "T1,T2"` or `--templates "*"` and store it in the `[templates: ...]` fragment inside `description`.

**Extended fields**:

- `avg_cost`: average execution cost (round count), currently defaults to — (reserved for v2, to be enabled after enough data accumulates)
- `confidence`: confidence of the effect data (low / medium / high), **computed at runtime** (auto-derived inside `cmd_write` from `use_count`, not persisted as a table column) — see "Automatic Confidence Calculation and Promotion Thresholds" below
- `context_tags`: applicable context-tag list (for example `[python, backend, security]`), **already active** (written into the `description` field via `--tags`) — see "Standard Vocabulary for context_tags" below
- `side_effect_severity`: side-effect severity (none / low / medium / high), currently defaults to none (reserved for v2, to be enabled after enough data accumulates)

### Detailed Strategy Description Format

When a strategy's `use_count` is >= 2, the following structured description must be added (written below the strategy-effect table and indexed by `strategy_id`):

| Field | Required | Description |
|------|------|------|
| `mechanism` | Yes | Mechanism by which the strategy works (why it is effective) |
| `preconditions` | Yes | Preconditions for the strategy to work (when it should be used) |
| `contraindications` | Yes | Contraindications for the strategy (when it should not be used) |
| `optimal_context` | No | Best-use scenario (distilled from successful cases) |
| `failure_mode` | No | Typical failure behavior (distilled from failed cases) |
| `pitfall_description` | No (recommended when `status=Retired`) | What happens if this strategy is used anyway (concrete negative impact description) |
| `failure_lesson` | No (recommended when `effect=avoid`) | Structured failure lesson: `what` (what was done) / `why` (why it failed) / `instead` (recommended alternative). CLI write form: `--failure-lesson "what:...\|why:...\|instead:..."` |

**Example**:

**S01-parallel-scan**:
- `mechanism`: assign independent dimensions to different subagents and scan them in parallel, using the task's dependency-free nature to reduce total elapsed time
- `preconditions`: there is no data dependency between dimensions; the number of available subagents is >= the number of dimensions
- `contraindications`: strong dependencies exist between dimensions (for example, a security scan requires architecture analysis first); total dimension count <= 2 (parallel overhead exceeds the benefit)

---

### Standard Vocabulary for `context_tags`

The following tags are used to mark the applicable context of a strategy. OBSERVE filters recommended strategies by tag overlap:

**Language**: `python` | `typescript` | `javascript` | `go` | `rust` | `java`  
**Layer**: `backend` | `frontend` | `database` | `infrastructure` | `fullstack`  
**Domain**: `security` | `performance` | `reliability` | `maintainability` | `architecture`  
**Task**: `api-design` | `data-model` | `testing` | `deployment` | `migration` | `refactoring`  
**Scale**: `small(<1K lines)` | `medium(1K-10K lines)` | `large(>10K lines)`

Tagging rule: each strategy must include at least 1 language tag + 1 layer tag + 1 domain tag. Infer them automatically based on the affected file paths.

### Automatic Confidence Calculation and Promotion Thresholds

**Automatic calculation**:
- `use_count = 1` → `confidence = low`
- `use_count = 2-3` → `confidence = medium`
- `use_count >= 4` → `confidence = high`

**Promotion threshold**: for a strategy to move from "Observe" to "Recommended", it must satisfy:
- `confidence >= medium` (that is, `use_count >= 2`)
- 2 consecutive `delta > 0`

When `use_count = 1`, `success_rate` is not statistically meaningful and must not be used as a promotion basis.

**Ordering rules**:

- Current version: sort by `success_rate` descending (simple version)
- Future version (after enough data accumulates): `success_rate × confidence × (1 - side_effect_penalty) / avg_cost`

**Attribution rules**:
- Only results from single-strategy rounds (where `strategy_id` is a single strategy) may update `avg_delta` and `success_rate`
- Results from multi-strategy parallel rounds (where `strategy_id` is `multi:...`) are marked as "mixed attribution" and do not update aggregate metrics; they are recorded only as reference data
- This rule ensures that the data in the strategy-effect library remains attributable and reproducible

**State transition rules** (lifecycle enum: Recommended / Candidate Default / Observe / Retired):
- New strategies default to "Observe"
- Promotion to "Recommended" requires `confidence >= medium` (`use_count >= 2`) and 2 consecutive `delta > 0`
- 2 consecutive `delta <= 0` → "Retired"
- A "Retired" strategy with `delta > 0` in a new context → move back to "Observe"

### Context-scoped Status

A strategy's `status` may be refined by `context_tags` combinations. When the same strategy performs differently in different contexts, use the extension below:

**Global `status`**: still kept in the main strategy-effect table as the default when no context match exists.

**Context-specific `status`**: maintain a supplemental table outside the main strategy-effect table:

| strategy_id | context_tags | status | evidence | last_validated |
|-------------|-------------|--------|----------|----------------|
| S01-parallel-scan | [python, backend, security] | Recommended | 3 positive runs | 2026-03-28 |
| S01-parallel-scan | [typescript, frontend, performance] | Retired | 2 negative runs | 2026-03-28 |

**Query priority**:
1. Exact match: the task's `context_tags` exactly match the row's `context_tags` → use that row's `status`
2. Subset match: the task's `context_tags` are a superset of a row's `context_tags` → use that row's `status`
3. No match: use the global `status` (the `status` field in the main strategy-effect table)

**Extended state transition rules**:
- Context-specific `status` follows the same transition rules as the global rules (2 consecutive `delta > 0` → Recommended; 2 consecutive `delta <= 0` → Retired)
- It is based only on usage data from that specific context and is not affected by other contexts
- First use in a new context → inherit the global `status`; after the second use, an independent context-specific `status` is created

### Automatic Experience Promotion Chain

```text
Stored (automatic, Observe, low confidence) → Recommended (2 consecutive delta>0 + use>=2) → Candidate Default (success>=80% + use>=4 + high confidence) → [v2] Canary validation (1 similar task) → [v2] Upgrade (write into command, user confirmation, patch+1)
```

**Implemented in v1**: stored → Observe → Recommended → Candidate Default (automatic promotion); 2 consecutive negative runs → Retired (automatic retirement); Retired + positive run → Observe (automatic recovery).  
**Reserved for v2**: canary validation, upgrade by writing into command files, rollback after upgrade.  
**Rollback** (v2): 2 consecutive `delta <= 0` after upgrade → remove from command, demote back to Recommended, `patch+1`.

---

## Memory Layering (MUSE Three-layer Classification)

Each strategy in the experience library is classified into three layers by impact level. Different layers are read with different priorities and decay rates in OBSERVE.

| Layer | Tag | Meaning | Example | Decay rate |
|------|------|------|------|---------|
| L1 | `strategic` | Methodology-level knowledge that changes the overall direction | "Fail-closed scoring drives quality better than permissive scoring" | Slow (180d) |
| L2 | `procedural` | Process-level experience that changes execution steps | "Parallel scanning speeds up T7 by 40% compared to serial scanning" | Medium (90d) |
| L3 | `tool` | Tool / technique-level experience that changes concrete operations | "`grep -rn` locates issues faster than `find + xargs`" | Fast (30d) |

**Tagging rules** (reserved for v2): when a strategy enters the library, add one layer tag. Criteria:
- Changes "whether to do it" → `strategic`
- Changes "how to do it" → `procedural`
- Changes "what to use to do it" → `tool`

**Read priority** (reserved for v2): in OBSERVE, `strategic > procedural > tool`. When the budget is tight, prefer higher-layer experience.

> **v1 status**: MUSE layering exists only in the design docs; the `memory_layer` field is not persisted as a table column. v1 uses flat sorting (`success_rate × time decay`).

### Time-decay Mechanism

Strategy effect decays over time to avoid outdated experience influencing decisions.

**Decay rules** (based on `last_validated_date`):

| Days ago | Decay coefficient | Effect |
|---------|---------|------|
| 0-30d | ×1.0 | Fully valid |
| 31-60d | ×0.8 | Slight decay |
| 61-90d | ×0.5 | Significant decay |
| >90d | Downgrade | `status` automatically drops from "Recommended" to "Observe" |

**Decay application**:
- During ranking: effective ranking score = `success_rate × decay coefficient`
- Downgrade trigger: a "Recommended" strategy not validated for >90d automatically downgrades to "Observe" and must be revalidated on next use
- Revalidation: if `delta > 0` after use, update `last_validated_date` to today and reset decay
- Strategic-layer exemption: L1 experience decays at 2× the periods in the table above (60d / 120d / 180d)

**Extended fields** (reserved for v2): the strategy-effect library plans to add `memory_layer` (`L1/L2/L3`) and `last_validated_date` (ISO 8601 date). In v1, `last_validated_date` is represented equivalently by the `@YYYY-MM-DD` tag inside `description` (parsed by `cmd_query` for time-decay sorting).

---

## Strategy Composition and Ablation (reserved for v2)

### Strategy composition (`composed_from`)

When a combination of multiple base strategies performs better, a composed strategy may be created:

**Extended field**: add a `composed_from` field to the strategy-effect library (a list of `strategy_id` values, such as `[S01-parallel-scan, S03-cache-first]`).

**Composition rules**:
- Composed strategy `strategy_id` uses the format `C{NN}-{description}` (`C` = Composed)
- Every base strategy in `composed_from` must independently exist in the strategy-effect library
- The composed strategy's `avg_delta` is calculated independently and does not affect the base strategies' `avg_delta`
- The composed strategy's `success_rate` is tracked independently

**Example**:
```text
strategy_id: C01-parallel-cached-scan
composed_from: [S01-parallel-scan, S03-cache-first]
description: composed strategy of parallel scan + cache-first
```

### Ablation protocol

Triggered when a composed strategy records 2 consecutive `delta > 0` runs (requires budget >= 50% and the user has not skipped it). Remove one base strategy from the composition at a time and run one round, then compare delta changes: no significant change (<20% threshold) = low contribution (remove to simplify); significant drop = key component (keep). If only one component contributes, dissolve the composition and promote that strategy directly.

---

## Experience Evaluation Criteria

| Evaluation dimension | Criteria |
|---------|------|
| Type | See the "Experience Types and Distribution Targets" table above |
| Impact level | Low: add anchors / samples; Medium: adjust parameters (within +/-20%); High: change rules / gates / workflow |
| Confidence | Based on validation count: 1 = low, 2-3 = medium, >=4 = high |
| Distribution priority | High-risk high-confidence > low-risk high-confidence > medium-risk medium-confidence > others |

---

## Cross-task Experience Read Rules

OBSERVE read order (also written into `loop-protocol.md`):

```text
0. "Retired" entries with pitfall_description or failure_lesson (avoiding pitfalls takes priority over reusing successes)
1. findings.md of the current task (task-local experience)
2. Global strategy-effect library in references/experience-registry.md (cross-task experience)
3. "Recommended" strategies where (same template OR applicable_templates contains current template OR applicable_templates is `[*]`) + context_tags overlap (ordered by success_rate descending)
   - applicable_templates match: the `[templates: ...]` fragment in strategy description includes the current template identifier or `*`
   - context_tags overlap = the current task tags and the strategy's context_tags share at least 2 tags
   - Strategies with no tag overlap are not recommended, avoiding incorrect migration across contexts
   - If a strategy has a context-scoped status, prefer the status matching the current context instead of the global status

At first-round cold start:
- No task-local experience
- Read recommended strategies from the global experience library where (same template OR applicable_templates matches) + context_tags overlap
- Use global experience as the basis for first-round strategy selection
- Retired entries with pitfall_description / failure_lesson are always shown (avoiding pitfalls is more important than reusing success)
```

---

## Experience Retirement Mechanism

- 2 consecutive failed validations (`delta <= 0`) across different tasks → change `status` to "Retired"
- If "Retired" remains unvalidated for 5 tasks → move it to the archive section
- Retired experience is not deleted; it remains in the archive section for auditability

---

## Protocol-change Effect Tracking Table (reserved for v2)

Record the intended goal and actual effect of each protocol change to support outcome validation. In v1, protocol changes are tracked via git commit history.

| change_id          | protocol_version | change | intended_goal | validation_window | actual_effect | status |
|--------------------|------------------|--------|---------------|-------------------|---------------|--------|
| (accumulates as protocol changes occur) |                  |        |               |                   |               |        |

**Status enum**: In Validation / Met (solidified) / Not Met (rollback under evaluation) / Rolled Back

**`change_id` format**: `CH{NNN}-{short-description}` (for example `CH001-anchor-t4`). Prefix `CH = Change`, distinct from the composed-strategy prefix `C{NN}` (`C = Composed`) to avoid naming collisions.
