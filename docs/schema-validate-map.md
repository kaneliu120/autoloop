# loop-data-schema ↔ autoloop-validate 对照表

维护本表有助于判断「改 schema 是否要改校验逻辑」。实现函数均在 `scripts/autoloop-validate.py`。

| Schema / 文档章节 | 校验函数 | 说明 |
|-------------------|----------|------|
| 顶层 `plan` / `iterations` / `findings` / `results_tsv` / `metadata` | `_check_top_level_structure` | 缺键即 error |
| `iterations[].strategy_id` ↔ findings / strategy_history | `_check_primary_key_consistency` | 未注册策略 error |
| `plan.dimensions` ↔ `iterations[].scores` 键 | `_check_dimension_consistency` | 未定义维度 error；未使用维度 warn（仅针对出现在**非豁免** `plan.gates` 行的维度） |
| `plan.gates` 契约（dim / manifest_dimension / 非 manifest 原名） | `_check_plan_gates_contract` | strict 时升格为 error；**`status=豁免/Exempt` 行整段跳过**（与 `autoloop_kpi.plan_gate_is_exempt` 一致） |
| 末轮 `phase` 与 DECIDE/VERIFY/REFLECT 最小产物 | `_check_phase_artifacts` | strict→error，否则 warn（含 checkpoint 与 SSOT phase 一致性） |
| `findings.rounds[].findings[]` summary/content | `_check_findings_canonical_fields` | 空正文 warn；summary+content 并存 warn |
| `results_tsv` 列与 iteration 连续 | `_check_tsv_completeness` | error |
| `iterations[].round` 序号 | `_check_iteration_sequence` | error |
| `phase` 枚举与完成态 | `_check_phase_sequence` | 未知 phase error；完成非 REFLECT warn |
| `plan.gates[].current` ↔ 最新 scores | `_check_gate_status` | warn；豁免行跳过 |
| `plan.budget` 与轮次数 | `_check_budget` | 超支 error；current_round 不一致 warn |
| `metadata.protocol_version` ↔ TSV 行 | `_check_version_consistency` | error |
| `plan.decide_act_handoff.impacted_dimensions` ↔ 末行 `results_tsv.side_effect` | `_check_side_effect_vs_handoff` | strict→error，否则 warn（P-03） |
| 末轮 `phase=REFLECT` 时 `iterations[-1].reflect` | `_check_phase_artifacts` | strict：`strategy_id`+`effect`（E-01）；且须含 `delta` / `rating_1_to_5` / legacy Likert `score` 之一 |

**Markdown 回退模式**（无 `autoloop-state.json`）使用 `validate_markdown` 与上表独立。

官方最小 SSOT 样例见仓库根目录 `examples/minimal-state.json`（由 `autoloop-state.py init` 生成，仅替换 `work_dir` / `task_id` 即可复用）。
