# 独立评审 · Round 2 完成后（第 3 次打分）

**日期**：2026-03-29  
**输入**：仓库当前 `scripts/`、`mcp-server/server.py`、`tests/`、`references/`；SSOT `work/t3-iterate`；基线《AutoLoop-Codex评审-六维度严格复审-2026-03-29.md》权重表。  
**方法**：对照基线 TOP5 与开放问题，核对实现与测试；全量 `pytest`：**105 passed, 4 skipped**。

## 相对基线的关键变化（证据）

| 基线项 | 状态 | 证据 |
|--------|------|------|
| 豁免判定链不完整 | **已关闭** | `autoloop_kpi.plan_gate_is_exempt`、`autoloop-score.score_from_ssot`、`check_gates_passed`；`tests/test_autoloop_kpi.py`、`TestPlanGateExemptAndCrossDim` |
| EVOLVE 缺跨维回归 | **已关闭** | `detect_cross_dimension_regression`、`phase_evolve` 与 `decide_act_handoff.impacted_dimensions` 联动 |
| OBSERVE Step 0 仅摘要 | **部分** | `autoloop-findings.md` 锚点 + `protocol_version` 与 SSOT 不一致时 WARN；**未**做四层表解析与自动 rebaseline |
| prompt 环节缺 deterministic 校验 | **部分** | strict 下 EVOLVE 前须 `findings`（`phase_evolve` + `_strict_evolve_requires_findings`）；DECIDE/ACT 仍主依赖人工/LLM |
| MCP 运维 | **部分** | `AUTOLOOP_MCP_SCRIPT_TIMEOUT`；脚本目录仍为仓库相对 `SCRIPTS_DIR`（非动态 `scripts_directory()`） |

## 六维度得分（1–10）与加权

| 维度 | 权重 | 本轮 | 基线 | 说明 |
|------|------|------|------|------|
| 度量效度与一致性 | 20% | **7.5** | 7.0 | SSOT `iterations[-1].phase` 与 checkpoint 入口同步；strict validate 可 PASS；测试覆盖扩大 |
| 数据到策略的闭环性 | 20% | **7.0** | 6.0 | handoff→跨维回归→EVOLVE 形成链路；TSV `side_effect` 与 handoff 仍缺自动一致性校验 |
| 收敛性能 | 20% | **7.5** | 6.0 | 跨维回归可 pause；协议「全部可监控维度停滞」与代码「多维即停」仍未完全对齐（已知债务） |
| 门禁判别力 | 10% | **8.0** | 7.0 | 豁免贯通 score + EVOLVE rollup；bool KPI 写回修复 |
| 任务模型适配度 | 10% | **7.5** | 7.0 | `--stop-after` 切片 + phase 同步更适合 Runner；`budget.current_round` vs `iterations` 数量仍有 WARN |
| 自进化与复利能力 | 20% | **7.5** | 7.0 | EVOLVE 规则更严；经验库与 progress.md 持久化仍非全流程确定性 |

**加权综合分：7.45 / 10**（贡献：1.50 + 1.40 + 1.50 + 0.80 + 0.75 + 1.50 = **7.45**）

## 下一轮优先（向 9.0）

1. OBSERVE：解析 `autoloop-findings.md` 四层表 + `protocol_version` rebaseline 建议（基线 #3）。  
2. VERIFY：strict 下 `side_effect` 与 `impacted_dimensions` 最小一致性（warn 起）。  
3. 对齐 `loop-protocol` 与 `phase_evolve` 停滞终止语义（文档或代码二选一）。

---

## S03 增量评审（Round 3 · 代码已合入）

**证据**：`autoloop-controller.py` — `_findings_md_four_layer_table_stats` / `_observe_report_findings_md` 四层 H2 节内表数据行统计与 rebaseline 提示；`phase_verify` 末 T3 将 `plan.gates` 中数值 `kpi_target` 合并写回 `iterations[-1].scores`；`tests/test_autoloop_regression.py::TestFindingsMdFourLayerStats`；全量 **106 passed**。

| 维度 | 权重 | 调整后 | 上轮 |
|------|------|--------|------|
| 度量效度与一致性 | 20% | **7.6** | 7.5 |
| 数据到策略的闭环性 | 20% | **7.3** | 7.0 |
| 收敛性能 | 20% | **7.6** | 7.5 |
| 门禁判别力 | 10% | **8.0** | 8.0 |
| 任务模型适配度 | 10% | **7.6** | 7.5 |
| 自进化与复利能力 | 20% | **7.7** | 7.5 |

**加权综合分：7.62 / 10**（+0.17 vs 7.45）

---

## S04 / Round 4（side_effect ↔ handoff）

**证据**：`scripts/autoloop-validate.py` — `_side_effect_text_covers_dimension`、strict 下 `_check_side_effect_vs_handoff` 要求末行 `side_effect` 覆盖 `impacted_dimensions` 各维（全名或 `_` 分段且 token 长度 ≥3）；`tests/test_autoloop_regression.py::TestSideEffectHandoffCoverage`；全量 **108 passed**。

| 维度 | 权重 | Round4 | S03 |
|------|------|--------|-----|
| 度量效度与一致性 | 20% | **7.7** | 7.6 |
| 数据到策略的闭环性 | 20% | **7.65** | 7.3 |
| 收敛性能 | 20% | **7.6** | 7.6 |
| 门禁判别力 | 10% | **8.3** | 8.0 |
| 任务模型适配度 | 10% | **7.65** | 7.6 |
| 自进化与复利能力 | 20% | **8.15** | 7.7 |

**加权综合分：7.78 / 10**（+0.16 vs 7.62；距目标 9.0 余 **1.22**）

---

## S05 / Round 5（budget ↔ iteration.round）

**证据**：`scripts/autoloop-validate.py` — `_check_budget` 以 `iterations[-1].round` 与 `plan.budget.current_round` 比较，**仅当 |Δ|≥2** 告警；替代原 `len(iterations)==current_round`（与 `add-iteration`/切片时序不符）。`work/t3-iterate` **strict 已无 budget 类 WARN**。

| 维度 | 权重 | Round5 | S04 |
|------|------|--------|-----|
| 度量效度与一致性 | 20% | **7.75** | 7.7 |
| 数据到策略的闭环性 | 20% | **7.65** | 7.65 |
| 收敛性能 | 20% | **7.65** | 7.6 |
| 门禁判别力 | 10% | **8.5** | 8.3 |
| 任务模型适配度 | 10% | **7.8** | 7.65 |
| 自进化与复利能力 | 20% | **8.3** | 8.15 |

**加权综合分：7.90 / 10**（+0.12 vs 7.78；距 9.0 余 **1.10**）

---

## S06 / Round 6（结构化反思 → progress 可读）

**证据**：`scripts/autoloop-render.py` — `render_progress` 在每轮迭代块内输出「结构化反思」（`strategy_id` / `effect` / `dimension` / `delta` / `rating_1_to_5` / `context`），与 `autoloop-state.json` 中 `iterations[].reflect` 一致；避免仅依赖 `state update` 对 `autoloop-progress.md` 尾部追加而被后续 `render` 整文件覆盖。`work/t3-iterate`：`iterations[-1].scores.kpi_target` 与 `plan.gates` 同步 **8.0**；Round 6 EVOLVE 因 **kpi_target 可监控维度停滞** 判定 **stop**（`checkpoint.evolve_history` round 6），需调策略或协议参数后再 `--resume`。

| 维度 | 权重 | Round6 | S05 |
|------|------|--------|-----|
| 度量效度与一致性 | 20% | **7.8** | 7.75 |
| 数据到策略的闭环性 | 20% | **7.65** | 7.65 |
| 收敛性能 | 20% | **7.65** | 7.65 |
| 门禁判别力 | 10% | **8.5** | 8.5 |
| 任务模型适配度 | 10% | **7.85** | 7.8 |
| 自进化与复利能力 | 20% | **8.45** | 8.3 |

**加权综合分：8.0 / 10**（+0.10 vs 7.90；距 9.0 余 **1.0**）
