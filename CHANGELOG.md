# Changelog

## [0.1.0] — 2026-03-29

### 新增

- **L1 Runner（无人值守）**：`services/autoloop_runner/` — `autoloop-runner tick|loop`、work_dir fcntl 锁、OpenAI DECIDE/REFLECT、`ACT` allowlist 子进程；`docs/RUNNER.md`；`autoloop-controller.py --stop-after <PHASE>` 与可选 `--exit-codes` / `AUTOLOOP_EXIT_CODES`；`init` 预置 `plan.decide_act_handoff: null`。可选依赖 `[runner]`（`openai`）。单测 `tests/test_runner_unattended.py`。
- **Runner P1**：VERIFY 不跳过 + `RUNNER_VERIFY_RETRY`；`metadata.runner_status` / `pause_reason` 与暂停对齐；REFLECT JSON 校验（`reflect.py`）；SYNTHESIZE 前 `add-finding`（`RUNNER_SYNTHESIZE_MODE` minimal/llm/skip）；`chat_json` 返回 usage 并累计 `runner_estimated_cost_usd`，`RUNNER_MAX_ESTIMATED_USD` 超阈 tick 退出 `12`；`runner_tick_count`。
- **Runner P2**：`RUNNER_JSON_LOG` / `RUNNER_JSON_LOG_FILE` 结构化日志；`metadata.runner_metrics` + `autoloop-runner metrics` Prometheus 文本；VERIFY 后 `impacted_dimensions` 自动 `add-tsv-row`（`tsv_auto.py`，`RUNNER_SKIP_AUTO_TSV` 可关）。
- **EVOLVE → autoloop-progress.md**：每轮 EVOLVE 结束自动追加决策与门禁摘要；可用 `AUTOLOOP_SKIP_PROGRESS_LOG=1` 关闭（P-01）。
- **DECIDE 策略预检**：`--enforce-strategy-history` / `AUTOLOOP_ENFORCE_STRATEGY_HISTORY=1` 或与 `--strict` 组合时，校验 `plan.decide_act_handoff.strategy_id` 不得与 `strategy_history` 中「避免」冲突；始终 warn 重复/避免列表（P-02）。
- **T6 默认轮次**：未设 `plan.budget.max_rounds` 时，可按 `plan.generation_items` 或 `template_params.items` 推导 `min(items×2, manifest cap)`（P-04）。
- **validate**：`impacted_dimensions` / `target_dimensions` 与末行 TSV `side_effect` 一致性（strict 为 error）；strict 下 REFLECT 要求 `reflect.strategy_id` + `effect`（P-03 / E-01）。
- **子进程超时**：`autoloop-validate.py` 默认 **300s**（`AUTOLOOP_TIMEOUT_VALIDATE`），其它脚本仍用 `AUTOLOOP_SUBPROCESS_TIMEOUT`（默认 120s）（D-04）。
- **工程**：`.gitignore` 忽略 `*.egg-info/`；`pyproject.toml` 增加可选依赖 `[dev]`（含 `mcp`）；删除误生成的 `UNKNOWN.egg-info`（D-01/D-02）。
- **文档**：断点分析 / R8 方案文首增加「与代码对齐」说明；`loop-protocol` 进化输出与 `autoloop-progress.md` 对齐；`SKILL.md` 标明 legacy 非推荐路径；`docs/backlog-experience-v2.md` 汇总经验库 v2 预留（P-05 / D-05 / D-06）。

### 变更

- **经验库 write**：registry 补充 WARN 仅在 **use_count==2** 时打印一次（D-03）。
- **EVOLVE `stagnation_max_explore`**：`gate-manifest.json` 对 T5/T7/T8 配置后，停滞中按 `iterations` 末两轮 `strategy_id` 切换累加 `metadata.stagnation_explore_switches`，达上限且决策仍为 `continue` 时改为 **`pause`**；无停滞信号时计数清零。单测 `tests/test_stagnation_max_explore.py`。
- **经验库收紧（可选）**：`AUTOLOOP_EXPERIENCE_REQUIRE_MECHANISM=1` 时，合并后 **use_count≥2** 的 `write` 必须带非空 `--mechanism`。单测 `tests/test_experience_write_fsm.py`。

## 历史归档（未单独发版前的合并说明）

> 下列条目描述的是更早批次的合并内容，与 **[0.1.0]** 及当前代码可能有重叠；以 Git 与脚本行为为准。

### 新增（待完成报告 §一 — 部分完成项收口）

- **validate（P0-01 / P2-10 / P3-07）**：按末轮 `phase` 校验 DECIDE 交接 / VERIFY 后 scores / REFLECT 结构化 `reflect`；`checkpoint.json` 与 SSOT `phase` 不一致时提示；`findings` 条目 canonical（summary/content）warn；文档见 `references/loop-data-schema.md`、`docs/schema-validate-map.md`；样例 `examples/minimal-state.json`。
- **controller（P2-04 / P3-03 / P3-08 / P3-09 / P3-17 / P3-18）**：`plan.template_mode` + `linear_delivery_complete`（T4 `linear_phases` 下预算耗尽时暂停而非误停）；OBSERVE 打印 `metadata.last_error`、`findings.lessons_learned` 与上一轮 `reflect`；`run_tool` 非零/超时写入 `last_error`；ACT 白名单配置提示与可复制命令清单；DECIDE 可复制 JSON 模板。
- **score（P3-07）**：`_finding_body_text` 统一 summary→content→description，并用于可信度/完整性扫描。
- **state**：`init` 默认写入 `template_mode`、`linear_delivery_complete`。
- **打包（P3-14）**：`autoloop_entrypoints.py` + `pyproject.toml` console_scripts。
- **工程化（P3-12 / P3-13 / P2-09）**：`docs/RELEASING.md`、`docs/mcp-cli-parity.md`；README 零依赖与 CI **3.10 + 3.11** 矩阵。
- **测试（P2-08）**：`TestP208T4EvolveHardFailRound1` — T4 首轮 EVOLVE，`syntax` hard 未达标时决策为 `continue` 且不得出现「所有 hard gate 已通过」；TSV 方差 fail-closed 时不得 `stop` 成功终止。
- **经验库（P3-01）**：`autoloop-experience.py` 主表按 `strategy_id` **upsert**；同目录 **`experience-audit.md`** 追加审计；`query`/`list` 对重复行取最新；`consolidate` 合并历史重复行；`multi:` 前缀仅审计、不更新主表聚合。详见 `references/experience-registry.md`。
- **经验库（P3-02）**：`query --tags` 按 description 内 context_tags 与任务标签 **≥2 重叠** 过滤；context-scoped 表按 **精确匹配 / 超集取最长行** 解析有效 status；`autoloop-controller` OBSERVE 传入 `plan.context_tags`。见 `references/experience-registry.md` §P3-02。
- **经验库 write（状态机 + use_count）**：无 `--status` 时以主表上一行 `status` 为起点（避免误将「已废弃」重置为「观察」）；连续两轮升降级依据 **审计中上一轮 score 与本轮 score**（delta >0 / ≤0）；`use_count`、`avg_delta`、`success_rate` 由同策略全部 `write` 审计 score 按时间顺序重算，与 P3-01 单行主表一致。单测见 `tests/test_experience_write_fsm.py`。
- **经验库 avg_delta**：与 registry 对齐为**各轮 `--score` 的算术平均**；`consolidate` 合并重复行时优先用审计 score 序列重算，避免对已是聚合值的 `avg_delta` 再取平均导致偏差。
- **经验库（P3-06）**：`multi:` 策略 `scripts/autoloop_strategy_multi.py` 统一校验（≥2 个 `SNN-描述`、不重复）；`write` 拒绝非法 `multi:` 且禁止 `--status`；`autoloop-validate` 校验 TSV/SSOT 中 multi 子策略可追溯，并建议 `side_effect` 混合归因。见 `references/experience-registry.md` §P3-06。

### 已修复（合并 TODO 清单 Wave A/B 大量项）

- **执行确定性**：`--strict` / `AUTOLOOP_STRICT` — VERIFY 失败（无 gates JSON、validate 非零、variance check 非零）则中止后续阶段；`autoloop-validate.py --strict` / `AUTOLOOP_VALIDATE_STRICT` 将门禁契约问题升为 error；DECIDE→ACT 约定 `plan.decide_act_handoff` JSON；`metadata.audit[]` 记录阶段完成。
- **OBSERVE**：差距列与 comparator / `target` 对齐；可选打印上轮 `findings` 摘要。
- **REFLECT**：`iterations[-1].reflect` 结构化时自动调用 `autoloop-experience.py write`。
- **EVOLVE**：TSV 末行方差≥2 或置信度 fail-closed 时**禁止**仅凭门禁判定成功终止；振荡与停滞/回归同维时优先停滞类信号。
- **T4 预算**：`gate-manifest.json` `default_rounds.T4` 改为 **7**（与 `delivery-phases.md` 对齐）；`parameters.md` 表同步。
- **TSV**：`add-tsv-row` 写入前校验方差/置信度 fail-closed。
- **迁移**：`autoloop-state.py migrate <dir> --dry-run` 预览 SSOT `plan.gates`。
- **文档/SKILL**：阈值 SSOT 指向 `gate-manifest.json`；`quality-gates.md` gate_status 与 manifest 统一为达标/未达标/豁免；`loop-protocol` / `loop-data-schema` 补充阶段产物、gap 启发式、信号优先级、T4↔OODA；`delivery-phases.md` 增加 OODA 映射表。
- **其它**：`validate` 修复 `plan.gates` 与 `scores` 比对时的 `dim`；`render_findings` 支持 `summary`；根目录 `pyproject.toml`（元数据，`requires-python>=3.10`）。

### 已修复（对照代码审查 P1–P6 及修复 TODO）

- **P1/P4**：`plan_gates_for_ssot_init()`、`plan.gates` 含 `manifest_dimension`，与 scorer `dimension` 对齐；controller 侧 comparator 反查。  
- **P2**：bool 门禁在 `comparator ==` 时使用 `value == threshold`。  
- **P3**：MCP `autoloop_controller` 的 `init` 传入 `template` / `goal`。  
- **P5**：OBSERVE 始终调用 `autoloop-experience.py query`。  
- **P6**：`run_tool` 子进程超时（`AUTOLOOP_SUBPROCESS_TIMEOUT`，默认 120s）。  
- **P7**：`phase_orient` 对 `threshold is None` 的 KPI 行使用 `target` 与当前分计算差距。  
- **P8**：`loop-protocol.md` 引用句乱码修复；`loop-data-schema.md` 去除重复标题。  
- **评分 JSON**：各 gate 结果增加 `manifest_dimension`；VERIFY 写回 `plan.gates` 时按内部键或 manifest 名匹配。  
- **校验**：`autoloop-validate.py` 对旧 `plan.gates` 契约发出 warning；`plan.dimensions` 与 gates 收集兼容 `dim`。  
- **仓库**：根目录 `README.md`、`.gitignore` 忽略 `.DS_Store`、`docs/SECURITY.md`、GitHub Actions 运行 `unittest`。
