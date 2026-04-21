# AutoLoop Codex Six-Dimension Strict Review Prompt

Send the following content to the review LLM as the prompt (it is recommended to use a different model from development to ensure independence).

---

## Prompt Body

You are a methodology review expert. Please perform the **strictest** possible six-dimension review of the AutoLoop autonomous iteration engine.

### Review Target

AutoLoop is a Claude Code skill that implements an OODA+ 8-stage loop (OBSERVE→ORIENT→DECIDE→ACT→VERIFY→SYNTHESIZE→EVOLVE→REFLECT), supports 7 task templates (T1 Research ~ T7 Optimize), and uses quality gates to drive automatic convergence.

### Review Criteria

**You must read all of the following files** (ordered by priority):

Core scripts (review line by line; **line counts must follow the current repository files**, not old estimates):
1. `scripts/autoloop-controller.py` - main loop controller (about 1100+ lines, including `run_loop`, `phase_evolve`, `check_gates_passed`, `run_tool`, the eight stages, and checkpoint handling)
2. `scripts/autoloop-experience.py` - experience registry read/write tool (use the file as the source of truth)
3. `scripts/autoloop-score.py` - scoring engine (use the file as the source of truth, including `_eval_gate`, `plan_gates_for_ssot_init`, and `score_from_ssot`)

**Must-review functions / areas (controller)**: `run_loop`, `run_init`, `phase_verify`, `phase_evolve`, `phase_orient`, `check_gates_passed`, `_lookup_manifest_comparator`, `_plan_gate_matches_score_result`, `detect_stagnation`, `detect_oscillation`.
**Must-review functions / areas (score)**: `_manifest_to_scorer_gates`, `plan_gates_for_ssot_init`, `_eval_gate`, `score_from_ssot`.

Protocols and configuration (review section by section):
4. `references/gate-manifest.json` - gate SSOT
5. `references/experience-registry.md` - experience registry spec + lifecycle rules
6. `references/loop-protocol.md` - loop protocol
7. `references/quality-gates.md` - gate scoring rules
8. `references/parameters.md` - parameter definitions
9. `references/evolution-rules.md` - evolution rules

Entry points and templates:
10. `SKILL.md` - main protocol definition (~300 lines)
11. `assets/findings-template.md` - findings template
12. `mcp-server/server.py` - MCP tool layer

### Six-Dimension Scoring Framework

Score each dimension from 1-10. **You must provide specific file paths + line numbers as evidence**.

#### Dimension 1: Measurement Validity and Consistency (weight 20%)

Evaluation criteria:
- Are all thresholds loaded from gate-manifest.json (the SSOT)? Are there any hard-coded thresholds?
- Do score.py and controller.py use the same comparator logic? Trace the full `comparator` chain from manifest → scorer → controller
- Are the four scoring concepts (quality_score / confidence / severity / gate_status) kept strictly separate? Is there any mixing?
- Are the oscillation / stagnation detection thresholds consistent with the manifest?
- Do the textual descriptions in quality-gates.md exactly match the numeric values in gate-manifest.json? Verify them one by one

**Deduction trap**: check whether score.py and controller.py produce different pass/fail results for the same gate (split verdict). Use concrete input values to simulate the test.

#### Dimension 2: Data-to-Strategy Closed Loop (weight 20%)

Evaluation criteria:
- Does OBSERVE automatically read the experience registry? Trace the `phase_observe` → `run_tool("autoloop-experience.py", ...)` call chain
- Does REFLECT write strategy effects back to the experience registry? Trace the output content of `phase_reflect`
- Can data written by `cmd_write` be read back correctly by `cmd_query`? Simulate a full write → query loop
- Is the auto-promotion chain (observed → recommended → candidate default) correct? Use `prev_same` to simulate 3 writes and verify the state transition
- Does automatic deprecation work (two consecutive negative results → deprecated)? Simulate a negative write sequence
- Is time decay persisted? Check the downgrade write-back logic in `cmd_query`

**Deduction trap**: Which steps in DECIDE / ACT / REFLECT are deterministic, and which depend on the LLM following the prompt? Any LLM-dependent step is a closed-loop weakness.

#### Dimension 3: Convergence Performance (weight 20%)

Evaluation criteria:
- Does oscillation detection require both narrow-range fluctuation AND direction alternation? Verify the `direction_changes >= 1` logic
- Does stagnation detection use template-specific thresholds? Trace `_get_stagnation_threshold(template_key)` back to the manifest
- Does stagnation detection skip dimensions that have already met the target? Inspect the `gate_thresholds` dictionary construction and comparison logic
- Is regression (continued decline) distinguished from stagnation (plateau)? Check the `'regressing'` vs `'stagnating'` signals
- Are T4/T5 correctly excluded from stagnation detection?
- Is EVOLVE's termination decision correct? Simulate combinations such as: all passed, regression, multi-dimension stagnation, single-dimension stagnation

**Deduction trap**: Use boundary values to test `detect_stagnation` - for example `[8.0, 8.0, 8.0]` (no improvement), `[8.0, 7.9, 7.8]` (pure regression), `[8.0, 8.1, 8.0]` (oscillation).

#### Dimension 4: Gate Discriminative Power (weight 10%)

Evaluation criteria:
- Is the hard/soft classification consistent across manifest, score.py, and controller.py?
- Is the comparator (`>=`, `<=`, `==`) executed consistently in score.py `_eval_gate` and controller.py `check_gates_passed`?
- Does T5's `syntax_errors == 0` truly use `==` rather than `<=`?
- Is the tiered T6 gating (security P2 hard vs reliability P2 soft <= 3) correctly separated?
- Does T3's user-defined `kpi_target` gate handle `threshold: null` correctly?

**Deduction trap**: Check whether the gap calculation direction in `phase_orient` matches the comparator. Does the percentage gap calculation make sense for `<=` gates?

#### Dimension 5: Task Model Fit (weight 10%)

Evaluation criteria:
- Do all 7 templates have differentiated gate definitions? Compare the gates list for each template in the manifest
- Can `_infer_template` extract the template correctly from `strategy_id`? Test `S15-T3-xxx`, `C01-composed`, `T6-scan`
- Are the trigger words in the template routing table (SKILL.md) ambiguous?
- Is `DEFAULT_ROUNDS` loaded from the manifest? Do T3/T6/T7 have a safe upper bound for infinite rounds?
- Does the linear phase model for T5 receive special handling in the controller, or is it treated like a normal round loop?

**Deduction trap**: Check the interaction between T5 `default_rounds=1` and the controller main loop - does T5 terminate after round 1 because the budget is exhausted?

#### Dimension 6: Self-Evolution and Compounding Ability (weight 20%)

Evaluation criteria:
- Is the lifecycle state machine complete (observed → recommended → candidate default → deprecated → restored)? Draw the actual state transition graph from code
- Does `existing_status` read the latest status from existing records correctly, or does it use the new-row default value?
- Is `success_rate` automatically computed on every write?
- Are the `[Keep]` / `[Avoid]` labels written into `description` and readable on query?
- Is time decay (30/60/90-day coefficients) implemented in `cmd_query`? Does the >90d downgrade persist back to the file?
- Features marked as "v2 reserved" **must not be penalized** - these are explicit scope boundaries

**Deduction trap**: Simulate a strategy's full lifecycle - 3 positive writes (should promote to recommended) → 2 negative writes (should downgrade to deprecated) → 1 positive write (should restore to observed). Verify the actual state at each step.

### Output Format

```text
## Dimension N: [Name] (weight X%)

**Score: N/10**

### Evidence (supports the score)
- [file:line] specific description → score contribution

### Defects (deduction items)
- [severity: CRITICAL/WARNING/INFO] [file:line] specific description → deduction reason

### Simulation Test
- Input: [specific values]
- Expected: [expected result]
- Actual code path: [tracked code lines]
- Result: PASS/FAIL

---

## Weighted Total

| Dimension | Weight | Score | Contribution |
|-----------|--------|-------|--------------|
| ... | ... | ... | ... |
| **Total** | 100% | | **X.XX/10** |

## Highest-Priority Fix Suggestions (ordered by impact, max 5)
```

### Review Discipline

1. **Do not accept self-claims** - inspect only code and files, not comments that say "implemented"
2. **Prefer simulation tests** - walk through key logic with concrete input values
3. **Zero tolerance for split verdicts** - score.py and controller.py must give the same pass/fail result for the same input
4. **v2 reserved exemption** - explicitly marked "v2 reserved" features are outside the review scope
5. **Strict but fair** - implemented and correct functionality must receive full credit
