# AutoLoop L1 Runner（无人值守）

精简版实施说明；完整需求见 Obsidian：《AutoLoop-无人值守与多模型-开发实施手册-2026-03-30》。

## 策略（已选定）

采用手册 **§5.1 策略 α 变体**：薄 Runner + `autoloop-controller.py --stop-after <PHASE>` 切片；在 **ORIENT 之后** 由 Runner 调用模型写入 `plan.decide_act_handoff`，再启动 controller 跑 **DECIDE**；**ACT** 前由 Runner 执行 `planned_commands`（allowlist + `shell=False`）。

## 安装

```bash
pip install -e ".[runner]"
```

`[runner]` 包含 `openai`。仅跑无需模型的切片（如首个 `tick`）时可只装本体。

## 命令

```bash
# 单步推进（读 checkpoint.last_completed_phase）
PYTHONPATH=services autoloop-runner tick /path/to/work_dir
# 或已 editable 安装且包在 PYTHONPATH 时：
autoloop-runner tick /path/to/work_dir

# 连续 tick（可用 RUNNER_MAX_WALL_SECONDS / RUNNER_MAX_TICKS 限制）
autoloop-runner loop /path/to/work_dir --max-ticks 50

# Prometheus 文本（P2-2）
autoloop-runner metrics /path/to/work_dir
```

## 环境变量

| 变量 | 说明 |
|------|------|
| `OPENAI_API_KEY` | DECIDE / REFLECT 调用模型时必需 |
| `OPENAI_BASE_URL` | 兼容代理/Azure |
| `OPENAI_MODEL` | 默认 `gpt-4o-mini` |
| `RUNNER_MOCK_LLM` | `1` 时不调 API，用手册验收用 mock handoff |
| `AUTOLOOP_STRICT` | Runner 默认对子进程注入 `1`（可用 `tick --no-strict` 关闭） |
| `AUTOLOOP_EXIT_CODES` / `autoloop-controller --exit-codes` | controller：`0` 正常，`1` 中止，`10` 暂停 |
| `RUNNER_MAX_WALL_SECONDS` | `loop` 墙钟上限（P1-5） |
| `RUNNER_MAX_ESTIMATED_USD` | 累计 API 粗算费用上限，超出则 tick 退出 `12`（P1-5） |
| `RUNNER_PRICE_INPUT_PER_1K` / `RUNNER_PRICE_OUTPUT_PER_1K` | 美元/1K tokens，用于粗算（默认贴近 gpt-4o-mini 量级） |
| `RUNNER_VERIFY_RETRY` | VERIFY 切片失败时的额外重试次数，默认 `0`（P1-1） |
| `RUNNER_VERIFY_RETRY_DELAY_SEC` | 重试间隔秒，默认 `2` |
| `RUNNER_SYNTHESIZE_MODE` | `minimal`（默认）\|`llm`\|`skip` — SYNTHESIZE 前写回 findings（P1-3） |
| `RUNNER_JSON_LOG` / `RUNNER_JSON_LOG_FILE` | `1` 时结构化 JSON 日志（stderr 或文件）（P2-1） |
| `RUNNER_SKIP_AUTO_TSV` | `1` 时关闭 VERIFY 后自动 TSV（P2-3） |
| `RUNNER_ACT_TIMEOUT` | 单条 shell 命令超时（秒） |
| `AUTOLOOP_EXPERIENCE_REQUIRE_MECHANISM` | `1`/`true`/`yes`：经验库 `write` 在合并后 **use_count≥2** 时必须带 `--mechanism`（默认不启用；收紧 D-03） |

## P1 — 跑稳与可恢复

### VERIFY 与 `AUTOLOOP_STRICT`（P1-1）

- `last_completed_phase == ACT` 时，Runner **只**通过 `autoloop-controller.py --stop-after VERIFY` 执行完整 VERIFY（`autoloop-score` / `autoloop-validate` / `autoloop-variance`），与 IDE 人工跑圈一致。
- `strict`（默认）下 VERIFY 失败 → controller 退出码 `1`，Runner 写入 `metadata.runner_status=ERROR`、`pause_reason=controller_exit_1`。
- 可选重试：`RUNNER_VERIFY_RETRY=N`（第 1 次失败后最多再试 N 次）。

### REFLECT（P1-2）

- 模型输出经校验：`strategy_id`、`effect`（`保持`/`避免`/`待验证`）、`score`、`dimension`、`context`；再 `update iterations[-1].reflect`，以便 REFLECT 阶段触发经验库 write。

### SYNTHESIZE 最小写回（P1-3）

- 默认 `RUNNER_SYNTHESIZE_MODE=minimal`：在跑 controller 的 SYNTHESIZE 切片**之前**，调用 `autoloop-state.py add-finding` 写入一条 `dimension=runner_synthesize` 的摘要（末轮 scores + gates）。
- `llm`：用 OpenAI 生成 `dimension`+`content` 再 add-finding（`RUNNER_MOCK_LLM=1` 时退回 minimal）。
- `skip`：不写 findings。

### 暂停与恢复（P1-4）

1. Runner 退出码 **`10`**，或 `metadata.runner_status=PAUSED`（含 `EVOLVE: pause`、T3 KPI 未就绪、费用上限 `12` 等）。
2. 查看 `checkpoint.json` 的 `pause_state`、`metadata.pause_reason`。
3. 人工修正 SSOT（如补 `plan.gates` KPI、改 `plan.budget`）后执行：  
   `autoloop-controller.py <work_dir> --resume`（清除 checkpoint 暂停语义、继续循环）。  
4. 再执行 `autoloop-runner tick` 或 `loop`。

### 全局预算（P1-5）

- **墙钟**：`RUNNER_MAX_WALL_SECONDS` 或 `autoloop-runner loop --max-wall-seconds`。
- **费用（粗算）**：每次 Chat Completions 的 `usage` 累计到 `metadata.runner_api_prompt_tokens` / `runner_api_completion_tokens` / `runner_estimated_cost_usd`；超过 `RUNNER_MAX_ESTIMATED_USD` 时 **tick 退出 `12`**（不发起新切片）。
- 可选：`metadata.runner_api_request_log` 保留近期 `request_id`（上限 500 条）。

## 退出码摘要

| 码 | 含义 |
|----|------|
| 0 | 本步成功 |
| 1 | 错误（含 strict VERIFY 失败） |
| 10 | 暂停（与 controller `--exit-codes` 对齐） |
| 11 | work_dir 锁未获取 |
| 12 | 费用/预算上限（P1-5） |

## P2 — 可运营

### 结构化日志（P2-1）

- `RUNNER_JSON_LOG=1`：每行一条 JSON 到 **stderr**（或 `RUNNER_JSON_LOG_FILE` 指向文件）。
- 字段包含：`event`、`task_id`、`round`、`checkpoint_phase`、`phase`（若传入）、`request_id`（OpenAI 成功时）、`latency_ms`、`ts`。
- 事件示例：`tick_slice`、`openai_chat_complete`、`openai_chat_error`、`verify_auto_tsv`。

### 指标 / Prometheus（P2-2）

- SSOT：`metadata.runner_metrics`（`api_calls_total`、`api_latency_ms_sum`、`pauses_total`、`failures_total`、`lock_denied_total`）；成功切片数仍用 `runner_tick_count`。
- 导出：`autoloop-runner metrics <work_dir>` 打印 **Prometheus 文本**，可由 sidecar 写入文件供 `file_sd` 或 `textfile collector` 抓取。
- **OpenTelemetry**：未内置；可在外层用 OTel SDK 包装子进程或解析 JSON 日志（见手册 §4.3）。

### TSV / `side_effect`（P2-3）

- 若 `plan.decide_act_handoff` 含非空 `impacted_dimensions`（或 `target_dimensions`），在 **VERIFY 切片成功** 后 Runner 自动追加一行 `results_tsv`：`side_effect` 为 `跨维影响: dim1,dim2,...`，以满足 `autoloop-validate.py --strict` 与 handoff 一致性。
- 若末行 TSV 已有合法 `side_effect`，则跳过。
- `RUNNER_SKIP_AUTO_TSV=1` 关闭；strict 下 `add-tsv-row` 失败 → tick 返回 **`1`**。

## Controller 新增 CLI

- `--stop-after OBSERVE|…|REFLECT`：执行到该阶段结束并更新 `checkpoint.json` 后退出。
- `--exit-codes` 或 `AUTOLOOP_EXIT_CODES=1`：按上表退出码退出进程。

## 互斥

同一 `work_dir` 使用 `.autoloop-runner.lock`（fcntl）；第二个 `tick --no-wait-lock` 得退出码 `11`。

## SSOT

Runner **不**维护第二套任务状态；以 `autoloop-state.json` 与 `checkpoint.json` 为准。`plan.decide_act_handoff` 在 `init` 时预置为 `null`，便于 `autoloop-state.py update` 写入。

## 测试

```bash
PYTHONPATH=services python -m unittest tests.test_runner_unattended -v
RUN_FULL_RUNNER_TICK=1 PYTHONPATH=services python -m unittest tests.test_runner_unattended.TestRunnerTickMockIntegration -v
```
