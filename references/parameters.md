# AutoLoop Process Control Parameters

> **Complementarity statement**: This document complements `quality-gates.md`; together they define the AutoLoop iteration control system.
> - `quality-gates.md` defines "is the result good enough?" - quality judgment, focused on scoring criteria and gate thresholds for outputs
> - `parameters.md` (this document) defines "how is the process controlled?" - process parameters, focused on execution constraints such as iteration counts, trigger conditions, and rollback limits
>
> Changes to this document are protocol evolution and may only be applied after a REFLECT-stage proposal plus user confirmation (see the protocol evolution section in `evolution-rules.md`).

---

## 1. Iteration Control Parameters

### 1.1 Default Round Table

> Source: the default parameter reference table in the original `commands/autoloop-plan.md` template

| Parameter | Template | Value | Scope | Description |
|--------|------|----|---------|------|
| `default_rounds.T1` | T1 Research | 3 rounds | T1 research tasks | Research tasks default to 3 rounds to ensure sufficient information coverage |
| `default_rounds.T2` | T2 Compare | 2 rounds | T2 comparison tasks | Comparison tasks usually converge after two rounds |
| `default_rounds.T5` | T5 Iterate | **99** (SSOT: `gate-manifest.json`) | T5 iteration tasks | The manifest value is authoritative; treat it as a safety ceiling. It can be overridden with `plan.budget.max_rounds`; termination is still primarily gate/KPI-driven |
| `default_rounds.T6` | T6 Generate | 99 rounds (gate-terminated, **upper bound**) | T6 batch generation tasks | `pass_rate` + `avg_score` gates determine termination. If `plan.budget.max_rounds` is not set, the controller may use **`min(items×2, 99)`** based on `plan.generation_items` or `template_params.items` as the default round count (P-04) |
| `default_rounds.T4` | T4 Deliver | **5** (OODA round budget) | T4 delivery tasks | Upper bound for **full OODA rounds**, aligned with the five delivery phases (Phase 1-5) in `delivery-phases.md`. `plan.budget.max_rounds` can override it. |
| `default_rounds.T7` | T7 Quality | **99** (SSOT: `gate-manifest.json`) | T7 quality review tasks | Same as T5: the manifest is authoritative; `max_rounds` can be overridden; gate-based termination takes precedence |
| `default_rounds.T8` | T8 Optimize | **99** (SSOT: `gate-manifest.json`) | T8 optimization tasks | Same as above |

**Usage conventions**:
- The wizard shows the default value for the selected template in Step 4/5, and the user may adjust it during planning
- In `items × 2`, `items` means the total number of generation units defined in `plan.md`
- For T5/T7/T8, the round ceiling is determined by `default_rounds` in `references/gate-manifest.json` (currently **99**); the old "unlimited" wording in earlier docs is deprecated to avoid conflicts with the implementation

---

## 2. Evolution Trigger Parameters

> Source: the original `references/evolution-rules.md`

### 2.1 Conditions That Permit Scope Expansion

| Parameter | Value | Scope | Description |
|--------|----|---------|------|
| `evolution.expand.budget_threshold` | ≥ 30% | T1, T3, T6, T7 | Scope expansion is allowed only if the remaining budget ratio reaches this threshold |
| `evolution.expand.dimension_ceiling` | ≤ initial dimensions × 1.5 | All templates | The total number of dimensions after expansion must not exceed 1.5 times the initial dimension count |

**Trigger logic**: Expansion is allowed only when **all** of the following are true:
1. The new dimension is highly important (it affects the core conclusion)
2. Remaining budget ≥ `evolution.expand.budget_threshold` (30%)
3. Total dimensions after expansion ≤ `evolution.expand.dimension_ceiling` (initial × 1.5)

### 2.2 Conditions That Trigger Scope Narrowing

| Parameter | Value | Scope | Description |
|--------|----|---------|------|
| `evolution.narrow.budget_consumed` | ≥ 70% | T1, T3, T6, T7 | Narrowing evaluation is triggered when the consumed budget ratio reaches this value |
| `evolution.narrow.coverage_threshold` | < 60% | T1, T3, T6, T7 | Narrowing evaluation is triggered when coverage falls below this value |
| `evolution.narrow.lag_dimensions` | ≥ 3 dimensions lagging for 2 consecutive rounds | T1, T3 | Criterion for multi-dimension simultaneous lag |

**Trigger logic**: Narrowing is triggered when **any** of the following is true:
1. Consumed budget ≥ `evolution.narrow.budget_consumed` (70%) and coverage < `evolution.narrow.coverage_threshold` (60%)
2. At least 3 dimensions lag simultaneously for 2 consecutive rounds
3. Some dimensions are found to have extremely sparse information, making further investment low-yield

### 2.3 Conditions That Trigger Strategy Switching

| Parameter | Value | Scope | Description |
|--------|----|---------|------|
| `evolution.switch.consecutive_rounds` | 2 rounds | All templates | Number of consecutive low-improvement rounds required to trigger a strategy switch |
| `evolution.switch.improvement_threshold` | < 3% (relative) | All templates | Improvement below this relative percentage in a single round is treated as "stagnation"; example: if current is 80%, the improvement threshold is 2.4%; if current is 7/10, the threshold is 0.21 points |

**Trigger logic**: A strategy switch is triggered when improvement for the same dimension remains below `evolution.switch.improvement_threshold` (3%, relative) for `evolution.switch.consecutive_rounds` (2) consecutive rounds.

---

## 3. Scope Expansion Limits

> Source: the evolution constraints section of the original `references/evolution-rules.md`

| Parameter | Value | Scope | Description |
|--------|----|---------|------|
| `evolution.expand.max_count` | 2 times | All templates | Maximum number of scope expansions allowed over the entire task lifecycle |
| `evolution.expand.dimension_ceiling` | ≤ initial dimensions × 1.5 | All templates | Upper bound on the total number of dimensions after each expansion (same as 2.1, listed here as a hard constraint) |
| `evolution.expand.cumulative_limit` | ≤ 50% of the initial dimension count | All templates | Upper bound on the cumulative number of added dimensions (prevents unbounded sprawl) |

**Constraint note**: Once `evolution.expand.max_count` (2) is exceeded, further expansion is disallowed even if the conditions are met; the system must report to the user and wait for manual decision-making.

---

## 4. Flow Rollback Limits

> Source: the rollback mechanism section of the original `references/delivery-phases.md`

| Parameter | Value | Scope | Description |
|--------|----|---------|------|
| `flow.rollback.max_per_phase` | 2 times | T5 phases (Phase 1-5) | Maximum number of rollbacks allowed per phase; once exceeded, the system must report to the user and wait for manual decision-making |
| `flow.rollback.phase2_exception` | 3 rounds | T5 Phase 2 (fix-review loop) | Exception upper bound for the Phase 2 fix-review loop; up to 3 rounds are allowed |

**Rollback path reference**:

| Phase where the issue is found | Roll back to | Rollback scope |
|-------------|--------|---------|
| P1/P2 issue found in Phase 2 | Phase 1 | Fix only the corresponding files |
| Validation fails in Phase 3 | Phase 1 or Phase 2 | Fix + re-review |
| Deployment fails in Phase 4 | Phase 3 (re-test after fixing) | Fix + re-test + re-deploy |
| Production issue found in Phase 5 | Phase 4 (rollback) or Phase 1 (fix) | The user decides between rollback and hotfix |

---

## 5. Validation and Conflict Resolution Parameters

> Source: the conflict resolution rules in the original `references/loop-protocol.md`

| Parameter | Value | Scope | Description |
|--------|----|---------|------|
| `verification.conflict.score_diff` | > 2 | All templates | If two subagents differ by more than this score on the same code, trigger a third validation or manual judgment |
| `oscillation.window` | 3 rounds | All templates | Number of consecutive rounds fluctuating within ±band that counts as oscillation |
| `oscillation.band` | ±0.5 points | All templates | Score fluctuation bandwidth used to judge oscillation |
| `regression.threshold` | falls below the gate threshold | All templates | Any affected dimension falling below its gate threshold counts as cross-dimension regression |

**Conflict resolution rules**:

| Conflict type | Resolution rule |
|---------|---------|
| A says "there is a problem", B says "there is no problem" | Use the more conservative conclusion ("there is a problem") and record B's rationale |
| Two subagents differ by more than `verification.conflict.score_diff` (2) on the same code | Run a third validation (or use manual judgment) |
| Proposed fixes conflict with each other | Choose the change with the smallest footprint and record why the other option was rejected |

---

## 6. Template-Level Stagnation Detection Parameters

> Source: R7 review recommendation #3 - T3/T6/T7 need independent stagnation thresholds
>
> **SSOT**: Runtime thresholds are provided by the `stagnation_thresholds` field in `references/gate-manifest.json`. This section is a human-readable reference; if any conflict exists, `gate-manifest.json` is authoritative.

### 6.1 Stagnation Thresholds (Independent by Template)

| Parameter | Template | Value | Description |
|--------|------|----|------|
| `stagnation.T5.threshold` | T5 Iterate | < 2% (relative) | KPI improvement below 2% of the current value counts as stagnation |
| `stagnation.T5.max_explore` | T5 Iterate | 3 rounds | After stagnation, at most 3 new strategies may be tried |
| `stagnation.T7.threshold` | T7 Quality | < 0.3 points (absolute) | Improvement below 0.3 points in any of security/reliability/maintainability counts as stagnation |
| `stagnation.T7.max_explore` | T7 Quality | 2 rounds | After stagnation, at most 2 new strategies may be tried |
| `stagnation.T8.threshold` | T8 Optimize | < 0.5 points (absolute) | Improvement below 0.5 points in any of architecture/performance/stability counts as stagnation |
| `stagnation.T8.max_explore` | T8 Optimize | 2 rounds | After stagnation, at most 2 new strategies may be tried |

**Implementation status (`max_explore`)**: `stagnation_max_explore` in `references/gate-manifest.json` (T5/T7/T8) is consumed by `phase_evolve` in `autoloop-controller.py`: while a **stagnating** signal remains, if the current round's `iterations[].strategy.strategy_id` differs from the previous round, `metadata.stagnation_explore_switches` is incremented; once the limit is reached and the decision is still `continue`, the controller switches to **`pause`**. The counter resets when no stagnation is present. This aligns semantically with `stagnation.T5.max_explore` and related table entries; templates not configured in the manifest are not covered.

**Note**: T1/T2 use the generic stagnation threshold `evolution.switch.improvement_threshold` (< 3%) because research tasks show different stagnation characteristics from iterative optimization tasks.

### 6.1.1 T5: `get_current_scores` and Stagnation History (Implementation Convention)

> Aligned with the behavior of `scripts/autoloop-controller.py` to avoid false positives in ORIENT and EVOLVE.

- **`get_current_scores(state)`** (T5): if `iterations[-1].scores` is empty, the values in **`plan.gates[].current`** may be used to backfill the displayed current score (such as `kpi_target`) for the ORIENT gap table and some heuristic logic.
- **`get_score_history(state)`** (stagnation/oscillation window): only chains rounds where **`iterations[].scores` is non-empty**; it does **not** include the virtual points from the "empty round + gate backfill" behavior above. Therefore, before VERIFY writes the new T3 round back, the stagnation sequence still uses the SSOT scores from the previous round and earlier rounds.

### 6.2 Unified Stagnation State Machine

```text
Normal iteration
  ↓ improvement below the template threshold for 2 consecutive rounds
[Stagnation detection] → mark the dimension as "stagnating"
  ↓
[Strategy switch] → choose a new strategy from experience-registry or the strategy matrix
  ↓ execute the new strategy
[Exploration validation] → is the new strategy effective?
  ├── Effective (improvement ≥ threshold) → return to normal iteration
  ├── Ineffective but max_explore not reached → continue exploring (switch to another strategy)
  └── Ineffective and max_explore reached → [Termination evaluation]
        ├── Distance to gate ≤ 10% → output the current best result and mark unmet items
        └── Distance to gate > 10% → report to the user and recommend adjusting the goal or adding budget
```

---

## 7. Parameter Index (Quick Reference)

| Parameter | Value | Group |
|--------|----|---------|
| `default_rounds.T1` | 3 rounds | Iteration control |
| `default_rounds.T2` | 2 rounds | Iteration control |
| `default_rounds.T5` | 99 (see `gate-manifest.json`) | Iteration control |
| `default_rounds.T6` | 99 rounds (gate-terminated) | Iteration control |
| `default_rounds.T4` | **5 rounds** (`gate-manifest.json` SSOT, aligned with delivery phase docs) | Iteration control; when `plan.template_mode=linear_phases`, additional pause semantics apply (see `autoloop-controller`) |
| `default_rounds.T7` | 99 (see `gate-manifest.json`) | Iteration control |
| `default_rounds.T8` | 99 (see `gate-manifest.json`) | Iteration control |
| `evolution.expand.budget_threshold` | ≥ 30% | Evolution trigger |
| `evolution.expand.dimension_ceiling` | ≤ initial × 1.5 | Evolution trigger / expansion limit |
| `evolution.narrow.budget_consumed` | ≥ 70% | Evolution trigger |
| `evolution.narrow.coverage_threshold` | < 60% | Evolution trigger |
| `evolution.narrow.lag_dimensions` | ≥ 3 dimensions lagging for 2 consecutive rounds | Evolution trigger |
| `evolution.switch.consecutive_rounds` | 2 rounds | Evolution trigger |
| `evolution.switch.improvement_threshold` | < 3% (relative) | Evolution trigger |
| `evolution.expand.max_count` | 2 times | Expansion limit |
| `evolution.expand.cumulative_limit` | ≤ 50% of initial dimensions | Expansion limit |
| `flow.rollback.max_per_phase` | 2 times | Flow rollback |
| `flow.rollback.phase2_exception` | 3 rounds | Flow rollback |
| `verification.conflict.score_diff` | > 2 | Conflict resolution |
| `stagnation.T5.threshold` | < 2% (relative) | Stagnation detection |
| `stagnation.T5.max_explore` | 3 rounds | Stagnation detection |
| `stagnation.T7.threshold` | < 0.3 points (absolute) | Stagnation detection |
| `stagnation.T7.max_explore` | 2 rounds | Stagnation detection |
| `stagnation.T8.threshold` | < 0.5 points (absolute) | Stagnation detection |
| `stagnation.T8.max_explore` | 2 rounds | Stagnation detection |
| `oscillation.window` | 3 rounds | Oscillation detection |
| `oscillation.band` | ±0.5 points | Oscillation detection |
| `regression.threshold` | falls below the gate threshold | Regression detection |
| `routing.high_confidence_threshold` | 0.8 | Routing match |
| `routing.confirm_threshold` | 0.5 | Routing match |
| `routing.ambiguity_gap` | 0.2 | Routing match |

---

## 8. Routing Match Parameters

> Source: the confidence-based routing mechanism in the entry command `commands/autoloop.md`

| Parameter | Value | Description |
|--------|----|------|
| `routing.high_confidence_threshold` | 0.8 | When the match score is ≥ this value, the template is selected automatically without user confirmation |
| `routing.confirm_threshold` | 0.5 | When the match score is between this value and `high_confidence_threshold`, show the match result and ask the user to confirm |
| `routing.ambiguity_gap` | 0.2 | If the score gap between the top 2 templates is < this value, treat it as ambiguity and show multiple options |

**Routing logic**:
- Score ≥ `high_confidence_threshold` (0.8) and no ambiguity → automatic match
- Score ≥ `high_confidence_threshold` (0.8) but the top-2 gap < `ambiguity_gap` (0.2) → show the top 2-3 options for the user to choose
- Score between `confirm_threshold` (0.5) and `high_confidence_threshold` (0.8) → ask the user to confirm
- Score < `confirm_threshold` (0.5) → show all templates

---

## 9. Reproducibility (Sampling)

If a subtask uses randomness or sampling, it must record a **seed** (integer) in `findings` or `iterations` to support reruns and comparison. This is a task-layer convention and remains decoupled from the deterministic `scripts/` toolchain.

---

## 10. Pipeline Parallel Execution Parameters (P3-01)

> Source: the Pipeline parallel execution specification in `loop-protocol.md`

| Parameter | Value | Scope | Description |
| ------ | -- | ------- | ---- |
| `pipeline.parallel_groups` | `[]` (empty by default, fully serial) | Pipeline mode | Defines which templates can execute in parallel; each element is a group of dependency-free templates |
| `pipeline.worktree_base` | `.worktrees/` | Pipeline mode | Directory where Git worktrees are created (relative to `work_dir`) |
| `pipeline.merge_strategy` | `no-ff` | Pipeline mode | Merge strategy; defaults to `--no-ff` to preserve branch history |
| `pipeline.conflict_action` | `pause` | Pipeline mode | Behavior when a merge conflict occurs: `pause` (pause and wait for the user) or `abort` (abandon the branch) |

**`parallel_groups` configuration example**:

```yaml
pipeline:
  stages:
    - [T1]           # serial
    - [T2]           # serial (depends on T1)
    - [T7, T8]       # parallel group (no dependencies)
```

**Constraints**:

- Templates within the same parallel group must not have data dependencies (template A's output must not be template B's input)
- Templates within the same parallel group must not operate on the same file set (to avoid write conflicts)
- If a parallel merge fails, behavior is determined by `pipeline.conflict_action`
