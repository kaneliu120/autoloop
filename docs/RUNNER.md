# AutoLoop L1 Runner (Unattended)

Condensed implementation notes; the full requirements are in Obsidian: `AutoLoop-Unattended-and-Multi-Model-Implementation-Handbook-2026-03-30`.

## Selected Strategy

Use handbook **§5.1 Strategy Alpha variant**: a thin Runner plus `autoloop-controller.py --stop-after <PHASE>` slicing; **after ORIENT**, the Runner calls the model to write `plan.decide_act_handoff`, then starts the controller to run **DECIDE**; before **ACT**, the Runner executes `planned_commands` (allowlist + `shell=False`).

## Installation

```bash
pip install -e ".[runner]"
```

`[runner]` includes `openai`. If you only run slices that do not need a model (such as the first `tick`), installing the core package alone is enough.

## Commands

```bash
# Single-step advance (reads checkpoint.last_completed_phase)
PYTHONPATH=services autoloop-runner tick /path/to/work_dir
# Or, if installed editable and on PYTHONPATH:
autoloop-runner tick /path/to/work_dir

# Continuous tick loop (can be limited with RUNNER_MAX_WALL_SECONDS / RUNNER_MAX_TICKS)
autoloop-runner loop /path/to/work_dir --max-ticks 50

# Prometheus text (P2-2)
autoloop-runner metrics /path/to/work_dir
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `OPENAI_API_KEY` | Required when DECIDE / REFLECT call the model |
| `OPENAI_BASE_URL` | Proxy / Azure compatibility |
| `OPENAI_MODEL` | Default `gpt-4o-mini` |
| `RUNNER_MOCK_LLM` | When `1`, skip API calls and use the mock handoff for handbook validation |
| `AUTOLOOP_STRICT` | Runner injects `1` into subprocesses by default (disable with `tick --no-strict`) |
| `AUTOLOOP_EXIT_CODES` / `autoloop-controller --exit-codes` | controller: `0` success, `1` abort, `10` pause |
| `RUNNER_MAX_WALL_SECONDS` | Wall-clock limit for `loop` (P1-5) |
| `RUNNER_MAX_ESTIMATED_USD` | Estimated cumulative API cost limit; when exceeded, tick exits with `12` (P1-5) |
| `RUNNER_PRICE_INPUT_PER_1K` / `RUNNER_PRICE_OUTPUT_PER_1K` | USD per 1K tokens for rough cost estimation (defaults approximate gpt-4o-mini) |
| `RUNNER_VERIFY_RETRY` | Extra retry count when a VERIFY slice fails; default `0` (P1-1) |
| `RUNNER_VERIFY_RETRY_DELAY_SEC` | Delay between retries in seconds; default `2` |
| `RUNNER_SYNTHESIZE_MODE` | `minimal` (default) \| `llm` \| `skip` - write back findings before SYNTHESIZE (P1-3) |
| `RUNNER_JSON_LOG` / `RUNNER_JSON_LOG_FILE` | Structured JSON logs when `1` (stderr or file) (P2-1) |
| `RUNNER_SKIP_AUTO_TSV` | Disable automatic TSV writing after VERIFY when `1` (P2-3) |
| `RUNNER_ACT_TIMEOUT` | Timeout for a single shell command, in seconds |
| `AUTOLOOP_EXPERIENCE_REQUIRE_MECHANISM` | `1` / `true` / `yes`: after merge, experience `write` must include `--mechanism` when **use_count≥2** (disabled by default; tightens D-03) |

## P1 - Stability and Recovery

### VERIFY and `AUTOLOOP_STRICT` (P1-1)

- When `last_completed_phase == ACT`, the Runner **only** executes the full VERIFY slice through `autoloop-controller.py --stop-after VERIFY` (`autoloop-score` / `autoloop-validate` / `autoloop-variance`), matching manual IDE runs.
- In `strict` mode (default), a VERIFY failure causes controller exit code `1`, and the Runner writes `metadata.runner_status=ERROR` and `pause_reason=controller_exit_1`.
- Optional retries: `RUNNER_VERIFY_RETRY=N` (retry up to N more times after the first failure).

### REFLECT (P1-2)

- Validate model output fields: `strategy_id`, `effect` (`keep` / `avoid` / `to verify`), `score`, `dimension`, `context`; then `update iterations[-1].reflect` so the REFLECT stage can trigger experience writes.

### Minimal SYNTHESIZE write-back (P1-3)

- Default `RUNNER_SYNTHESIZE_MODE=minimal`: before running the controller's SYNTHESIZE slice, call `autoloop-state.py add-finding` to write a summary with `dimension=runner_synthesize` (final round scores + gates).
- `llm`: use OpenAI to generate `dimension` + `content`, then add the finding back (`RUNNER_MOCK_LLM=1` falls back to minimal).
- `skip`: do not write findings.

### Pause and Resume (P1-4)

1. Runner exit code **`10`**, or `metadata.runner_status=PAUSED` (including `EVOLVE: pause`, unfinished T3 KPI, budget cap `12`, etc.).
2. Inspect `checkpoint.json` for `pause_state` and `metadata.pause_reason`.
3. After manually fixing the SSOT (for example, adding `plan.gates` KPIs or changing `plan.budget`), run:  
   `autoloop-controller.py <work_dir> --resume` (clears checkpoint pause semantics and continues the loop).  
4. Then run `autoloop-runner tick` or `loop` again.

### Global Budget (P1-5)

- **Wall clock**: `RUNNER_MAX_WALL_SECONDS` or `autoloop-runner loop --max-wall-seconds`.
- **Cost (rough estimate)**: each Chat Completions `usage` is accumulated into `metadata.runner_api_prompt_tokens` / `runner_api_completion_tokens` / `runner_estimated_cost_usd`; once `RUNNER_MAX_ESTIMATED_USD` is exceeded, tick exits with **`12`** (no new slice is started).
- Optional: `metadata.runner_api_request_log` can retain recent `request_id` values (up to 500 entries).

## Exit Code Summary

| Code | Meaning |
|------|---------|
| 0 | Step succeeded |
| 1 | Error (including strict VERIFY failure) |
| 10 | Paused (aligned with controller `--exit-codes`) |
| 11 | work_dir lock not acquired |
| 12 | Cost / budget cap (P1-5) |

## P2 - Operability

### Structured Logging (P2-1)

- `RUNNER_JSON_LOG=1`: emit one JSON object per line to **stderr** (or to the file pointed to by `RUNNER_JSON_LOG_FILE`).
- Fields include: `event`, `task_id`, `round`, `checkpoint_phase`, `phase` (if provided), `request_id` (when OpenAI succeeds), `latency_ms`, `ts`.
- Example events: `tick_slice`, `openai_chat_complete`, `openai_chat_error`, `verify_auto_tsv`.

### Metrics / Prometheus (P2-2)

- SSOT: `metadata.runner_metrics` (`api_calls_total`, `api_latency_ms_sum`, `pauses_total`, `failures_total`, `lock_denied_total`); successful slice count still uses `runner_tick_count`.
- Export: `autoloop-runner metrics <work_dir>` prints **Prometheus text**, which a sidecar can write to a file for `file_sd` or the `textfile collector`.
- **OpenTelemetry**: not built in; wrap subprocesses externally with the OTel SDK or parse JSON logs (see handbook §4.3).

### TSV / `side_effect` (P2-3)

- If `plan.decide_act_handoff` includes non-empty `impacted_dimensions` (or `target_dimensions`), after a **successful VERIFY slice** the Runner automatically appends a `results_tsv` row whose `side_effect` is `cross-dimension impact: dim1,dim2,...`, keeping `autoloop-validate.py --strict` consistent with the handoff.
- If the last TSV row already has a valid `side_effect`, skip the append.
- `RUNNER_SKIP_AUTO_TSV=1` disables this; in strict mode, a failed `add-tsv-row` makes tick return **`1`**.

## Controller New CLI

- `--stop-after OBSERVE|...|REFLECT`: stop after that stage finishes and `checkpoint.json` is updated.
- `--exit-codes` or `AUTOLOOP_EXIT_CODES=1`: exit the process using the codes listed above.

## Mutual Exclusion

The same `work_dir` uses `.autoloop-runner.lock` (`fcntl`); a second `tick --no-wait-lock` exits with code `11`.

## SSOT

The Runner does **not** maintain a second task state; `autoloop-state.json` and `checkpoint.json` are the source of truth. `plan.decide_act_handoff` is initialized to `null` during `init`, which makes it easy for `autoloop-state.py update` to write into it.

## Testing

```bash
PYTHONPATH=services python -m unittest tests.test_runner_unattended -v
RUN_FULL_RUNNER_TICK=1 PYTHONPATH=services python -m unittest tests.test_runner_unattended.TestRunnerTickMockIntegration -v
```
