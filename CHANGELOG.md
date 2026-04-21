# Changelog

## [0.1.0] — 2026-03-29

### Added

- **L1 Runner (unattended)**: `services/autoloop_runner/` with `autoloop-runner tick|loop`, work_dir fcntl locking, OpenAI DECIDE/REFLECT, and an `ACT` subprocess allowlist; `docs/RUNNER.md`; `autoloop-controller.py --stop-after <PHASE>` plus optional `--exit-codes` / `AUTOLOOP_EXIT_CODES`; `init` now seeds `plan.decide_act_handoff: null`. Optional dependency group `[runner]` (`openai`). Unit test: `tests/test_runner_unattended.py`.
- **Runner P1**: VERIFY is no longer skipped and now supports `RUNNER_VERIFY_RETRY`; `metadata.runner_status` / `pause_reason` align with pause semantics; REFLECT JSON validation (`reflect.py`); pre-SYNTHESIZE `add-finding` with `RUNNER_SYNTHESIZE_MODE` (`minimal`/`llm`/`skip`); `chat_json` returns usage and accumulates `runner_estimated_cost_usd`, and ticks exit with code `12` once `RUNNER_MAX_ESTIMATED_USD` is exceeded; adds `runner_tick_count`.
- **Runner P2**: structured logging via `RUNNER_JSON_LOG` / `RUNNER_JSON_LOG_FILE`; `metadata.runner_metrics` plus `autoloop-runner metrics` Prometheus text output; automatic `add-tsv-row` for `impacted_dimensions` after VERIFY (`tsv_auto.py`, disable with `RUNNER_SKIP_AUTO_TSV`).
- **EVOLVE → autoloop-progress.md**: each EVOLVE round now appends the round decision and gate summary automatically; disable with `AUTOLOOP_SKIP_PROGRESS_LOG=1` (P-01).
- **DECIDE strategy precheck**: `--enforce-strategy-history` / `AUTOLOOP_ENFORCE_STRATEGY_HISTORY=1`, or using it together with `--strict`, now prevents `plan.decide_act_handoff.strategy_id` from conflicting with strategies marked `avoid` in `strategy_history`; repeated/avoided strategy lists always emit warnings (P-02).
- **T6 default round budget**: when `plan.budget.max_rounds` is missing, rounds can now be derived from `plan.generation_items` or `template_params.items` using `min(items×2, manifest cap)` (P-04).
- **validate**: enforces consistency between `impacted_dimensions` / `target_dimensions` and the last TSV row’s `side_effect` (strict mode upgrades this to an error); strict mode also requires `reflect.strategy_id` + `effect` in REFLECT (P-03 / E-01).
- **Subprocess timeout**: `autoloop-validate.py` now defaults to **300s** (`AUTOLOOP_TIMEOUT_VALIDATE`); other scripts still use `AUTOLOOP_SUBPROCESS_TIMEOUT` (default 120s) (D-04).
- **Engineering hygiene**: `.gitignore` now ignores `*.egg-info/`; `pyproject.toml` adds optional `[dev]` dependencies (including `mcp`); removes the accidentally generated `UNKNOWN.egg-info` (D-01/D-02).
- **Documentation**: breakpoint-analysis and R8 proposal docs now open with a “code-aligned” note; `loop-protocol` evolution outputs align with `autoloop-progress.md`; `SKILL.md` labels the legacy path as non-recommended; `docs/backlog-experience-v2.md` consolidates the experience-registry v2 backlog (P-05 / D-05 / D-06).

### Changed

- **Experience-registry writes**: registry WARN output now appears only once when **`use_count == 2`** (D-03).
- **EVOLVE `stagnation_max_explore`**: after configuring T5/T7/T8 in `gate-manifest.json`, stagnation tracking now accumulates `metadata.stagnation_explore_switches` based on strategy changes across the last two rounds in `iterations`; once the cap is reached and the decision is still `continue`, it is downgraded to **`pause`**. The counter resets when stagnation signals disappear. Unit test: `tests/test_stagnation_max_explore.py`.
- **Optional experience-registry tightening**: with `AUTOLOOP_EXPERIENCE_REQUIRE_MECHANISM=1`, merged `write` entries with **`use_count >= 2`** must include a non-empty `--mechanism`. Unit test: `tests/test_experience_write_fsm.py`.

## Historical Archive (merged work from before individual releases)

> The entries below summarize earlier merged work. They may overlap with **[0.1.0]** and the current codebase; Git history and actual script behavior remain the source of truth.

### Added (carryover items from the unfinished report, section 1)

- **validate (P0-01 / P2-10 / P3-07)**: validates DECIDE handoff, post-VERIFY scores, and structured REFLECT payloads against the final-round `phase`; warns when `checkpoint.json` and the SSOT `phase` disagree; emits canonical-entry warnings for `findings` (`summary`/`content`); docs live in `references/loop-data-schema.md` and `docs/schema-validate-map.md`; example at `examples/minimal-state.json`.
- **controller (P2-04 / P3-03 / P3-08 / P3-09 / P3-17 / P3-18)**: adds `plan.template_mode` + `linear_delivery_complete` (for T4 `linear_phases`, exhaustion now pauses instead of falsely stopping); OBSERVE prints `metadata.last_error`, `findings.lessons_learned`, and the prior round’s `reflect`; `run_tool` writes `last_error` on non-zero exit or timeout; ACT outputs allowlist configuration hints and copy-ready command lists; DECIDE provides a copyable JSON template.
- **score (P3-07)**: `_finding_body_text` now standardizes `summary → content → description`, and uses that normalized order for credibility/completeness scans.
- **state**: `init` now writes `template_mode` and `linear_delivery_complete` by default.
- **Packaging (P3-14)**: adds `autoloop_entrypoints.py` plus `pyproject.toml` console scripts.
- **Engineering (P3-12 / P3-13 / P2-09)**: adds `docs/RELEASING.md` and `docs/mcp-cli-parity.md`; README now documents the zero-dependency path and the CI **3.10 + 3.11** matrix.
- **Tests (P2-08)**: `TestP208T4EvolveHardFailRound1` covers T4 first-round EVOLVE behavior: if the `syntax` hard gate fails, the decision must remain `continue` and must never claim “all hard gates passed”; TSV fail-closed on variance must not terminate successfully with `stop`.
- **Experience registry (P3-01)**: `autoloop-experience.py` now **upserts** the main table by `strategy_id`; appends audit entries to **`experience-audit.md`** in the same directory; `query`/`list` prefer the newest duplicate row; `consolidate` merges historical duplicates; `multi:` prefixes are audit-only and do not update the primary aggregate row. See `references/experience-registry.md`.
- **Experience registry (P3-02)**: `query --tags` now filters on **at least two overlaps** between description `context_tags` and task tags; context-scoped rows resolve valid status using **exact match / longest superset match**; `autoloop-controller` passes `plan.context_tags` during OBSERVE. See `references/experience-registry.md` §P3-02.
- **Experience-registry writes (state machine + use_count)**: when `--status` is omitted, writes now inherit the previous main-row `status` instead of accidentally resetting `deprecated` to `observing`; two-round upgrades/downgrades use the **previous audited score and current score** (`delta > 0 / <= 0`); `use_count`, `avg_delta`, and `success_rate` are recomputed in time order from all audited `write` scores for the same strategy, keeping them aligned with the P3-01 main row. Unit test: `tests/test_experience_write_fsm.py`.
- **Experience-registry `avg_delta`**: now aligns with the registry definition as the **arithmetic mean of all `--score` values**; `consolidate` recomputes from audited score sequences where possible to avoid averaging already-aggregated `avg_delta` values.
- **Experience registry (P3-06)**: `multi:` strategies are validated centrally by `scripts/autoloop_strategy_multi.py` (requires at least two `SNN-description` entries and no duplicates); `write` rejects invalid `multi:` values and forbids `--status`; `autoloop-validate` verifies traceability of multi sub-strategies in TSV/SSOT and suggests mixed attribution through `side_effect`. See `references/experience-registry.md` §P3-06.

### Fixed (merged TODO work from Waves A/B)

- **Execution determinism**: `--strict` / `AUTOLOOP_STRICT` now stops later stages after VERIFY failures (missing gates JSON, non-zero validate, non-zero variance check); `autoloop-validate.py --strict` / `AUTOLOOP_VALIDATE_STRICT` upgrades gate-contract issues to errors; DECIDE→ACT now uses the structured `plan.decide_act_handoff` JSON contract; `metadata.audit[]` records stage completion.
- **OBSERVE**: gap columns now align with the comparator / `target`; optionally prints the previous round’s `findings` summary.
- **REFLECT**: structured `iterations[-1].reflect` now automatically triggers `autoloop-experience.py write`.
- **EVOLVE**: fail-closed on the final TSV row (variance ≥ 2 or confidence fail-closed) now **blocks** successful termination based only on gates; when oscillation and stagnation/regression target the same dimension, stagnation-style signals take priority.
- **T4 budget**: `gate-manifest.json` now sets `default_rounds.T4` to **7** (aligned with `delivery-phases.md`); `parameters.md` is synchronized.
- **TSV**: `add-tsv-row` validates fail-closed variance/confidence before writing.
- **Migration**: `autoloop-state.py migrate <dir> --dry-run` previews SSOT `plan.gates`.
- **Docs/SKILL**: threshold SSOT is explicitly `gate-manifest.json`; `quality-gates.md` aligns `gate_status` naming with the manifest (`pass` / `fail` / `waived` semantics in Chinese were normalized there); `loop-protocol` / `loop-data-schema` add phase artifacts, gap heuristics, signal priority, and T4↔OODA mapping; `delivery-phases.md` adds an OODA mapping table.
- **Misc**: `validate` fixes `dim` matching when comparing `plan.gates` and `scores`; `render_findings` now supports `summary`; the repo-root `pyproject.toml` metadata now explicitly sets `requires-python>=3.10`.

### Fixed (against review items P1–P6 and associated TODOs)

- **P1/P4**: `plan_gates_for_ssot_init()` and `plan.gates` now include `manifest_dimension`, aligning them with the scorer `dimension`; controller-side comparator lookups can resolve backward from that value.  
- **P2**: boolean gates now use `value == threshold` when `comparator ==`.  
- **P3**: MCP `autoloop_controller` `init` now passes `template` / `goal`.  
- **P5**: OBSERVE always calls `autoloop-experience.py query`.  
- **P6**: `run_tool` subprocesses now obey `AUTOLOOP_SUBPROCESS_TIMEOUT` (default 120s).  
- **P7**: `phase_orient` computes gaps for KPI rows with `threshold is None` using `target` vs. the current score.  
- **P8**: fixes garbled quoted text in `loop-protocol.md`; removes duplicate headings in `loop-data-schema.md`.  
- **Scoring JSON**: gate results now include `manifest_dimension`; VERIFY writes back to `plan.gates` by matching either the internal key or the manifest name.  
- **Validation**: `autoloop-validate.py` warns on legacy `plan.gates` contracts; `plan.dimensions` and gate collection both handle `dim` compatibility.  
- **Repository**: adds root `README.md`, updates `.gitignore` to ignore `.DS_Store`, adds `docs/SECURITY.md`, and runs `unittest` in GitHub Actions.
