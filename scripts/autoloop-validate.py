#!/usr/bin/env python3
"""AutoLoop 跨文件验证器 — SSOT JSON 优先，markdown 回退

用法:
  autoloop-validate.py <工作目录>          验证数据一致性
  autoloop-validate.py <工作目录> --json   JSON 输出
"""

import csv
import json
import os
import re
import sys

_val_dir = os.path.dirname(os.path.abspath(__file__))
if _val_dir not in sys.path:
    sys.path.insert(0, _val_dir)
from autoloop_kpi import plan_gate_is_exempt  # noqa: E402
from autoloop_strategy_multi import (  # noqa: E402
    is_multi_strategy_id,
    parse_multi_strategy_components,
    validate_multi_strategy_id,
)

# --- 常量 ---

STATE_FILE = "autoloop-state.json"

TSV_COLUMNS = [
    "iteration", "phase", "status", "dimension", "metric_value", "delta",
    "strategy_id", "action_summary", "side_effect", "evidence_ref",
    "unit_id", "protocol_version", "score_variance", "confidence", "details",
]

PHASES = [
    "OBSERVE", "ORIENT", "DECIDE", "ACT",
    "VERIFY", "SYNTHESIZE", "EVOLVE", "REFLECT",
]

STRATEGY_RE = re.compile(r"^S\d{2}-.+$")
PROBLEM_RE = re.compile(r"^[A-Z]\d{3}$")

MD_FILES = {
    "results": "autoloop-results.tsv",
    "findings": "autoloop-findings.md",
    "progress": "autoloop-progress.md",
    "plan": "autoloop-plan.md",
}


def _validation_strict_default():
    """AUTOLOOP_VALIDATE_STRICT=1 时 validate 将部分警告升级为错误。"""
    return os.environ.get("AUTOLOOP_VALIDATE_STRICT", "").strip().lower() in (
        "1", "true", "yes",
    )


# ============================================================
# SSOT JSON 模式验证
# ============================================================

def validate_json(work_dir, strict=False):
    """从 autoloop-state.json 执行全部验证，返回 (errors, warnings) 列表

    strict: 门禁契约缺失、阶段产物缺失等按错误计（亦可用环境变量开启）。
    """
    path = os.path.join(work_dir, STATE_FILE)
    with open(path, "r", encoding="utf-8") as f:
        state = json.load(f)

    errors = []
    warnings = []

    _check_top_level_structure(state, errors)
    _check_primary_key_consistency(state, errors)
    _check_dimension_consistency(state, errors, warnings)
    _check_plan_gates_contract(state, warnings, errors, strict)
    _check_phase_artifacts(work_dir, state, errors, warnings, strict)
    _check_findings_canonical_fields(state, warnings)
    _check_tsv_completeness(state, errors)
    _check_iteration_sequence(state, errors)
    _check_phase_sequence(state, errors, warnings)
    _check_gate_status(state, errors, warnings)
    _check_budget(state, errors, warnings)
    _check_version_consistency(state, errors)
    _check_side_effect_vs_handoff(state, errors, warnings, strict)

    return errors, warnings


def _check_top_level_structure(state, errors):
    """验证顶层结构存在"""
    required_keys = ["plan", "iterations", "findings", "results_tsv", "metadata"]
    for key in required_keys:
        if key not in state:
            errors.append("JSON 缺少顶层字段: '{}'".format(key))


def _check_primary_key_consistency(state, errors):
    """主键一致性: iterations[].strategy_id 必须出现在 findings 中"""
    # 收集 findings 中所有 strategy_id
    findings_strategy_ids = set()
    for rnd in state.get("findings", {}).get("rounds", []):
        for finding in rnd.get("findings", []):
            sid = finding.get("strategy_id", "")
            if sid and STRATEGY_RE.match(sid):
                findings_strategy_ids.add(sid)

    # 也从 strategy_evaluations 收集
    for ev in state.get("findings", {}).get("strategy_evaluations", []):
        sid = ev.get("strategy_id", "")
        if sid and STRATEGY_RE.match(sid):
            findings_strategy_ids.add(sid)

    # 也从 plan.strategy_history 收集（作为已知策略的补充来源）
    known_strategy_ids = set(findings_strategy_ids)
    for sh in state.get("plan", {}).get("strategy_history", []):
        sid = sh.get("strategy_id", "") if isinstance(sh, dict) else str(sh)
        if sid and STRATEGY_RE.match(sid):
            known_strategy_ids.add(sid)

    def _check_sid_defined(label, idx, sid):
        if STRATEGY_RE.match(sid):
            if sid not in known_strategy_ids:
                errors.append(
                    "{} {}: strategy_id '{}' 未在 findings/strategy_history 中定义".format(
                        label, idx, sid
                    )
                )
            return
        if is_multi_strategy_id(sid):
            ok_m, msg = validate_multi_strategy_id(sid)
            if not ok_m:
                errors.append("{} {}: {}".format(label, idx, msg))
                return
            for comp in parse_multi_strategy_components(sid):
                if comp not in known_strategy_ids:
                    errors.append(
                        "{} {}: multi 子策略 '{}' 未在 findings/strategy_history 中定义".format(
                            label, idx, comp
                        )
                    )
            return
        errors.append(
            "{} {}: strategy_id 格式错误: '{}' (期望 SNN-描述 或合法 multi:{{...}})".format(
                label, idx, sid
            )
        )

    # 检查每个 iteration 的 strategy_id
    for i, it in enumerate(state.get("iterations", []), start=1):
        sid = it.get("strategy", {}).get("strategy_id", "")
        if not sid or sid in ("—", "baseline", ""):
            continue
        _check_sid_defined("轮次", i, sid)

    # 检查 results_tsv 中的 strategy_id
    for row_idx, row in enumerate(state.get("results_tsv", []), start=1):
        sid = row.get("strategy_id", "").strip()
        if not sid or sid in ("—", "baseline", ""):
            continue
        _check_sid_defined("TSV 行", row_idx, sid)


def _check_dimension_consistency(state, errors, warnings):
    """维度一致性: plan.dimensions 必须匹配 iterations[].scores 中使用的维度"""
    plan_dims = set()
    for d in state.get("plan", {}).get("dimensions", []):
        if isinstance(d, dict):
            plan_dims.add(d.get("name", d.get("dimension", "")))
        elif isinstance(d, str):
            plan_dims.add(d)

    # 也从 gates 收集（dim 与 dimension 与 scorer 对齐）
    for g in state.get("plan", {}).get("gates", []):
        dim = g.get("dim") or g.get("dimension", "")
        if dim:
            plan_dims.add(dim)

    if not plan_dims:
        return

    non_exempt_gate_dims = set()
    for g in state.get("plan", {}).get("gates", []) or []:
        if plan_gate_is_exempt(g):
            continue
        d = g.get("dim") or g.get("dimension", "")
        if d:
            non_exempt_gate_dims.add(d)

    used_dims = set()
    for it in state.get("iterations", []):
        for dim in it.get("scores", {}):
            used_dims.add(dim)

    undefined = used_dims - plan_dims
    for dim in sorted(undefined):
        errors.append(
            "维度 '{}' 在 iterations.scores 中使用但未在 plan.dimensions/gates 中定义".format(dim)
        )

    unused = plan_dims - used_dims
    if unused and state.get("iterations"):
        for dim in sorted(unused):
            if non_exempt_gate_dims and dim not in non_exempt_gate_dims:
                continue
            warnings.append(
                "维度 '{}' 已定义但未在任何 iteration.scores 中使用".format(dim)
            )


# gate-manifest 原始 dimension，映射后与 scorer 内部键不同；若 plan.gates 仍用原名易导致 split verdict
_MANIFEST_RAW_SCORER_DIMS = frozenset({
    "syntax_errors", "p1_count", "security", "reliability", "maintainability",
})


def _check_plan_gates_contract(state, warnings, errors, strict):
    """plan.gates 与 scorer 契约：建议含 manifest_dimension，避免使用 manifest 原始名作为 dim。"""
    gates = state.get("plan", {}).get("gates", [])
    if not gates:
        return
    for i, g in enumerate(gates):
        if plan_gate_is_exempt(g):
            continue
        dim = g.get("dim") or g.get("dimension", "")
        if "manifest_dimension" not in g:
            msg = (
                "plan.gates[{}] 缺少 manifest_dimension（旧版 state，建议重新 init 或迁移，见 references/loop-data-schema.md §迁移）".format(i)
            )
            (errors if strict else warnings).append(msg)
        if g.get("dimension") and not g.get("dim"):
            msg = (
                "plan.gates[{}] 仅含 dimension，缺少 canonical 键 dim（见 loop-data-schema.md §plan.gates）".format(i)
            )
            (errors if strict else warnings).append(msg)
        if dim in _MANIFEST_RAW_SCORER_DIMS:
            msg = (
                "plan.gates[{}].dim='{}' 为 gate-manifest 原始名，与 autoloop-score 内部键不一致，可能导致分裂判定".format(i, dim)
            )
            (errors if strict else warnings).append(msg)


def _side_effect_text_covers_dimension(side_effect_lower, dim):
    """末行 side_effect 是否体现维度 dim（strict 交叉校验用）。"""
    d = str(dim).strip().lower()
    if not d:
        return True
    if d in side_effect_lower:
        return True
    for token in d.split("_"):
        if len(token) >= 3 and token in side_effect_lower:
            return True
    return False


def _check_side_effect_vs_handoff(state, errors, warnings, strict):
    """P-03: handoff 声明跨维影响时，末行 TSV side_effect 不应为空/无。"""
    handoff = state.get("plan", {}).get("decide_act_handoff") or {}
    if not isinstance(handoff, dict):
        return
    impacted = handoff.get("impacted_dimensions")
    if impacted is None:
        impacted = handoff.get("target_dimensions")
    if not impacted:
        return
    if isinstance(impacted, str) and not impacted.strip():
        return
    if isinstance(impacted, list) and not impacted:
        return
    rows = state.get("results_tsv") or []
    if not rows:
        return
    last = rows[-1]
    se = (last.get("side_effect") or "").strip().lower()
    if se in ("无", "—", "-", "", "none", "n/a"):
        msg = (
            "末行 results_tsv.side_effect 为「{}」但 plan.decide_act_handoff 声明了 impacted_dimensions/"
            "target_dimensions；请填写实际跨维影响或移除 handoff 中的声明".format(
                last.get("side_effect") or "空"
            )
        )
        (errors if strict else warnings).append(msg)
        return

    dims = impacted if isinstance(impacted, list) else [impacted]
    missing = [d for d in dims if not _side_effect_text_covers_dimension(se, d)]
    if missing:
        msg = (
            "末行 side_effect 未覆盖 handoff 声明的维度（须含各维标识或下划线分段 token≥3）: {}".format(
                ", ".join(str(x) for x in missing)
            )
        )
        (errors if strict else warnings).append(msg)


def _check_phase_artifacts(work_dir, state, errors, warnings, strict):
    """按当前末轮 phase 核对最小产物；strict 下缺失为 error，非 strict 下为 warn（见 loop-data-schema §阶段产物）。"""
    iterations = state.get("iterations", [])
    if not iterations:
        return
    last = iterations[-1]
    phase = (last.get("phase") or "").strip()
    if phase not in PHASES:
        return
    phase_idx = PHASES.index(phase)

    def _emit(msg):
        (errors if strict else warnings).append(msg)

    # ACT 及之后：须有 DECIDE 交接或本轮 strategy_id（canonical）
    act_idx = PHASES.index("ACT")
    if phase_idx >= act_idx:
        handoff = state.get("plan", {}).get("decide_act_handoff") or {}
        sid_h = ""
        if isinstance(handoff, dict):
            sid_h = (handoff.get("strategy_id") or "").strip()
        strat = last.get("strategy") or {}
        sid_it = (strat.get("strategy_id") or "").strip() if isinstance(strat, dict) else ""
        def _phase_sid_ok(s):
            if not s:
                return False
            if STRATEGY_RE.match(s):
                return True
            return bool(
                is_multi_strategy_id(s) and validate_multi_strategy_id(s)[0]
            )

        ok = _phase_sid_ok(sid_h) or _phase_sid_ok(sid_it)
        if not ok:
            _emit(
                "末轮 phase={} 但缺少有效 strategy_id（应设置 plan.decide_act_handoff.strategy_id "
                "或 iterations[-1].strategy.strategy_id；格式 SNN-描述 或 multi:{{SNN+SNN}}）".format(
                    phase
                )
            )

    # VERIFY 之后：须有 scores（防后期阶段空转）
    verify_idx = PHASES.index("VERIFY")
    late_post_verify = {"SYNTHESIZE", "EVOLVE", "REFLECT"}
    if phase in late_post_verify and phase_idx > verify_idx and not last.get("scores"):
        _emit(
            "末轮 phase={} 但 iterations[-1].scores 为空（应先完成 VERIFY 写回评分）".format(phase)
        )

    # REFLECT：建议有结构化 reflect（供 experience write）；strict 下要求 strategy_id + effect（E-01）
    if phase == "REFLECT":
        ref = last.get("reflect")
        if strict:
            if not isinstance(ref, dict):
                errors.append(
                    "末轮 phase=REFLECT 但 iterations[-1].reflect 非 JSON 对象（strict 要求 dict）"
                )
            else:
                sid = (ref.get("strategy_id") or "").strip()
                eff = (ref.get("effect") or "").strip()
                if not sid or not eff:
                    errors.append(
                        "末轮 phase=REFLECT 时 strict 要求 iterations[-1].reflect 含非空 "
                        "strategy_id 与 effect（供经验库 write）"
                    )
                else:
                    dval = ref.get("delta", None)
                    has_delta = dval is not None and dval != ""
                    has_likert = ref.get("rating_1_to_5") not in (None, "")
                    sc = ref.get("score")
                    leg_likert = isinstance(sc, int) and 1 <= sc <= 5
                    if not (has_delta or has_likert or leg_likert):
                        errors.append(
                            "末轮 REFLECT strict 要求 reflect 含 delta、rating_1_to_5 "
                            "或 legacy Likert（score 为 1–5 整数）之一"
                        )
        elif not isinstance(ref, dict) or not any(
            (ref.get(k) not in (None, "", [], {}))
            for k in ("strategy_id", "effect", "lesson_learned", "score", "dimension", "context")
        ):
            _emit(
                "末轮 phase=REFLECT 但 iterations[-1].reflect 为空或非结构化（建议 JSON：strategy_id/effect/...）"
            )

    # checkpoint.json 与 SSOT 末轮 phase 不一致时提示（常见于手工改 state 未同步断点）
    ck_path = os.path.join(work_dir, "checkpoint.json")
    if os.path.isfile(ck_path):
        try:
            with open(ck_path, "r", encoding="utf-8") as f:
                ck = json.load(f)
            ck_phase = (ck.get("current_phase") or "").strip()
            if ck_phase and ck_phase in PHASES and ck_phase != phase:
                msg = (
                    "checkpoint.current_phase={} 与 iterations[-1].phase={} 不一致（请同步 checkpoint 或 state）".format(
                        ck_phase, phase
                    )
                )
                (errors if strict else warnings).append(msg)
        except (OSError, ValueError, TypeError):
            pass


def _check_findings_canonical_fields(state, warnings):
    """findings.rounds[].findings[]：推荐 summary 为短摘要；空条目与 summary+content 并存仅 warn。"""
    rounds = state.get("findings", {}).get("rounds", [])
    for ri, rnd in enumerate(rounds):
        for fi, fnd in enumerate(rnd.get("findings", [])):
            if not isinstance(fnd, dict):
                continue
            summ = fnd.get("summary")
            cont = fnd.get("content")
            desc = fnd.get("description")
            has_s = summ not in (None, "")
            has_c = cont not in (None, "")
            has_d = desc not in (None, "")
            if not (has_s or has_c or has_d):
                warnings.append(
                    "findings.rounds[{}].findings[{}] 无 summary/content/description，"
                    "渲染与评分可能跳过该条".format(ri, fi)
                )
            elif has_s and has_c:
                warnings.append(
                    "findings.rounds[{}].findings[{}] 同时含 summary 与 content，"
                    "建议以 summary 为 canonical 短摘要、content 为详述".format(ri, fi)
                )


def _check_tsv_completeness(state, errors):
    """TSV 行完整性: 每行必须有全部 15 列，iteration 编号连续"""
    tsv_rows = state.get("results_tsv", [])
    seen_iterations = set()

    for row_idx, row in enumerate(tsv_rows, start=1):
        # 检查必需列
        missing_cols = [col for col in TSV_COLUMNS if col not in row]
        if missing_cols:
            errors.append(
                "TSV 行 {}: 缺少列 {}".format(row_idx, ", ".join(missing_cols))
            )

        # 收集 iteration 编号
        it_val = row.get("iteration", "")
        if isinstance(it_val, int):
            seen_iterations.add(it_val)
        elif isinstance(it_val, str) and it_val.isdigit():
            seen_iterations.add(int(it_val))

    # 检查 iteration 编号连续性
    if seen_iterations:
        max_it = max(seen_iterations)
        for expected in range(1, max_it + 1):
            if expected not in seen_iterations:
                errors.append(
                    "TSV iteration 编号不连续: 缺少第 {} 轮记录".format(expected)
                )


def _check_iteration_sequence(state, errors):
    """迭代轮次编号连续性"""
    iterations = state.get("iterations", [])
    for i, it in enumerate(iterations, start=1):
        actual_round = it.get("round", None)
        if actual_round is not None and actual_round != i:
            errors.append(
                "iterations[{}].round = {}，期望 {}".format(i - 1, actual_round, i)
            )


def _check_phase_sequence(state, errors, warnings):
    """阶段序列: 每个 iteration 的阶段历史必须遵循 PHASES 顺序"""
    for i, it in enumerate(state.get("iterations", []), start=1):
        current_phase = it.get("phase", "")
        status = it.get("status", "")

        if not current_phase:
            continue

        if current_phase not in PHASES:
            errors.append(
                "轮次 {}: 未知阶段 '{}'（合法值: {}）".format(i, current_phase, ", ".join(PHASES))
            )
            continue

        # 对已完成的轮次，phase 应该是 REFLECT
        if status in ("已完成", "完成") and current_phase != "REFLECT":
            warnings.append(
                "轮次 {}: 状态为 '{}' 但阶段停留在 '{}'（期望 REFLECT）".format(i, status, current_phase)
            )

        # 检查阶段数据填充：已经过的阶段应有数据
        phase_idx = PHASES.index(current_phase)
        for j in range(phase_idx + 1):
            phase_key = PHASES[j].lower()
            phase_data = it.get(phase_key, {})
            if isinstance(phase_data, dict) and not any(
                v for v in phase_data.values()
                if v and v != 0 and v != "无" and v != "待验证"
            ):
                # 空阶段数据只是警告，不是错误
                pass


def _check_gate_status(state, errors, warnings):
    """门禁状态: plan.gates[].current 应与最新 iteration 的 scores 一致"""
    gates = state.get("plan", {}).get("gates", [])
    iterations = state.get("iterations", [])

    if not gates or not iterations:
        return

    latest = iterations[-1]
    latest_scores = latest.get("scores", {})

    for gate in gates:
        if plan_gate_is_exempt(gate):
            continue
        dim = gate.get("dim") or gate.get("dimension", "")
        gate_current = gate.get("current")

        if gate_current is None or not dim:
            continue

        if dim in latest_scores:
            score_val = latest_scores[dim]
            # 比较时容忍类型差异（str vs int/float）
            try:
                if float(gate_current) != float(score_val):
                    warnings.append(
                        "门禁 '{}': plan.gates.current={} 与最新 iteration.scores.{}={} 不一致".format(
                            dim, gate_current, dim, score_val
                        )
                    )
            except (ValueError, TypeError):
                if str(gate_current) != str(score_val):
                    warnings.append(
                        "门禁 '{}': plan.gates.current={} 与最新 iteration.scores.{}={} 不一致".format(
                            dim, gate_current, dim, score_val
                        )
                    )


def _check_budget(state, errors, warnings):
    """预算检查: iterations 数量不超过 plan.budget.max_rounds"""
    budget = state.get("plan", {}).get("budget", {})
    max_rounds = budget.get("max_rounds", 0)
    current_round = budget.get("current_round", 0)
    iters = state.get("iterations") or []
    n_iterations = len(iters)

    if max_rounds and max_rounds > 0:
        if n_iterations > max_rounds:
            errors.append(
                "预算超支: 已执行 {} 轮，预算上限 {} 轮".format(n_iterations, max_rounds)
            )

    # OODA 轮次号：与末条 iteration.round 粗对齐（允许 ±1：add-iteration 先增 round、controller 稍后写 budget）
    if n_iterations > 0:
        last_r = iters[-1].get("round")
        if last_r is not None and abs(last_r - current_round) >= 2:
            warnings.append(
                "budget.current_round={} 与 iterations[-1].round={} 偏差过大（≥2）".format(
                    current_round, last_r
                )
            )


def _check_version_consistency(state, errors):
    """版本一致性: metadata.protocol_version 与所有 TSV 行一致"""
    meta_version = state.get("metadata", {}).get("protocol_version", "")
    if not meta_version:
        errors.append("metadata.protocol_version 未设置")
        return

    for row_idx, row in enumerate(state.get("results_tsv", []), start=1):
        row_version = row.get("protocol_version", "")
        if row_version and row_version not in ("—", "") and row_version != meta_version:
            errors.append(
                "TSV 行 {}: protocol_version='{}' 与 metadata.protocol_version='{}' 不一致".format(
                    row_idx, row_version, meta_version
                )
            )


# ============================================================
# Markdown 回退模式（保留原有逻辑，清理优化）
# ============================================================

def validate_markdown(work_dir):
    """从 markdown 文件执行跨文件主键校验，返回 (errors, warnings) 列表"""
    errors = []
    warnings = []

    # 检查必需文件
    missing = []
    for key, fname in MD_FILES.items():
        if not os.path.exists(os.path.join(work_dir, fname)):
            missing.append(fname)
    if missing:
        return ["缺少文件: {}".format(", ".join(missing))], []

    tsv_rows = _parse_tsv(os.path.join(work_dir, MD_FILES["results"]))
    f_problems, f_strategies = _extract_ids_from_findings(
        os.path.join(work_dir, MD_FILES["findings"])
    )
    p_iterations = _extract_iterations_from_progress(
        os.path.join(work_dir, MD_FILES["progress"])
    )
    known_dims = _extract_dimensions_from_gates(work_dir)

    for row in tsv_rows:
        ln = row["_line"]
        sid = row.get("strategy_id", "").strip()
        evi = row.get("evidence_ref", "").strip()
        it = row.get("iteration", "").strip()
        dim = row.get("dimension", "").strip()

        # strategy_id 格式校验（P3-06 multi: 须含 ≥2 个 SNN-子策略）
        if sid and sid not in ("—", "baseline"):
            if STRATEGY_RE.match(sid):
                if sid not in f_strategies:
                    errors.append(
                        "行{}: strategy_id '{}' 在 findings.md 中未定义".format(ln, sid)
                    )
            elif is_multi_strategy_id(sid):
                ok_m, msg = validate_multi_strategy_id(sid)
                if not ok_m:
                    errors.append("行{}: {}".format(ln, msg))
                else:
                    for comp in parse_multi_strategy_components(sid):
                        if comp not in f_strategies:
                            errors.append(
                                "行{}: multi 子策略 '{}' 在 findings.md 中未定义".format(
                                    ln, comp
                                )
                            )
                    sef = row.get("side_effect", "").strip()
                    if "混合" not in sef and "归因" not in sef:
                        warnings.append(
                            "行{}: multi: 建议 side_effect 注明混合归因（loop-protocol）".format(ln)
                        )
            else:
                errors.append(
                    "行{}: strategy_id 格式错误: '{}' (期望 SNN-描述 或 multi:{{...}})".format(
                        ln, sid
                    )
                )

        # evidence_ref -> problem_id 存在性
        if evi and evi != "—":
            for pid in re.findall(r"[A-Z]\d{3}", evi):
                if pid not in f_problems:
                    errors.append(
                        "行{}: evidence_ref 引用的 '{}' 在 findings.md 中未定义".format(ln, pid)
                    )

        # iteration 存在性
        if it and it.isdigit() and p_iterations and it not in p_iterations:
            errors.append(
                "行{}: iteration {} 在 progress.md 标题中无对应轮次记录".format(ln, it)
            )

        # dimension 一致性
        if dim and dim not in ("—", "score") and known_dims and dim not in known_dims:
            errors.append(
                "行{}: dimension '{}' 不在已知维度集合中 ({})".format(
                    ln, dim, ", ".join(sorted(known_dims))
                )
            )

    return errors, warnings


def _parse_tsv(path):
    """解析 results.tsv，返回行列表（dict）"""
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for i, row in enumerate(reader, start=2):
            row["_line"] = i
            rows.append(row)
    return rows


def _extract_ids_from_findings(path):
    """从 findings.md 提取 problem_id 集合和 strategy_id 集合"""
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    problem_ids = set(re.findall(r"\b([A-Z]\d{3})\b", text))
    strategy_ids = set(re.findall(r"\b(S\d{2}-[\w-]+)", text))
    return problem_ids, strategy_ids


def _extract_iterations_from_progress(path):
    """从 progress.md 标题中提取 iteration 编号集合"""
    iterations = set()
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("#"):
                nums = re.findall(r"(?:iteration|轮次|第)\s*(\d+)", line, re.IGNORECASE)
                iterations.update(nums)
    return iterations


def _extract_dimensions_from_gates(work_dir):
    """尝试从 plan.md 或 quality-gates.md 提取维度名"""
    dims = set()
    for name in ("autoloop-plan.md", "quality-gates.md"):
        p = os.path.join(work_dir, name)
        if not os.path.exists(p):
            continue
        with open(p, "r", encoding="utf-8") as f:
            for line in f:
                m = re.match(r"^\|\s*(.+?)\s*\|.*\d+%", line)
                if m:
                    dim = m.group(1).strip()
                    if dim and dim != "维度":
                        dims.add(dim)
    return dims


# ============================================================
# P2-17: OODA 阶段输出 Schema 验证
# ============================================================

PHASE_SCHEMAS = {
    "observe": {"required": ["current_scores", "target_scores", "remaining_budget_pct", "focus_dimensions"]},
    "decide": {"required": ["strategy_id", "action_plan", "fallback", "impacted_dimensions"]},
    "act": {"required": ["subagent_results", "completion_ratio"]},
    "verify": {"required": ["scores", "regression_detected"]},
}


def validate_phase_output(work_dir, phase, strict=False):
    """验证指定 OODA 阶段的输出是否包含必需字段。返回 (errors, warnings)。"""
    phase = phase.lower()
    if phase not in PHASE_SCHEMAS:
        return ["未知阶段: '{}' (合法值: {})".format(phase, ", ".join(sorted(PHASE_SCHEMAS)))], []

    path = os.path.join(work_dir, STATE_FILE)
    if not os.path.isfile(path):
        return ["未找到 {}".format(STATE_FILE)], []

    with open(path, "r", encoding="utf-8") as f:
        state = json.load(f)

    iterations = state.get("iterations", [])
    if not iterations:
        return ["无迭代数据，无法验证阶段输出"], []

    last = iterations[-1]
    schema = PHASE_SCHEMAS[phase]
    required = schema["required"]
    missing = []

    if phase == "observe":
        obs = last.get("observe", {})
        if not isinstance(obs, dict):
            obs = {}
        for field in required:
            if field not in obs or obs[field] is None:
                missing.append(field)
    elif phase == "decide":
        # DECIDE 数据来自 plan.decide_act_handoff 或 iterations[-1].strategy
        handoff = state.get("plan", {}).get("decide_act_handoff", {})
        strat = last.get("strategy", {})
        if not isinstance(handoff, dict):
            handoff = {}
        if not isinstance(strat, dict):
            strat = {}
        merged = {**strat, **handoff}
        for field in required:
            if field not in merged or merged[field] is None:
                missing.append(field)
    elif phase == "act":
        act = last.get("act", {})
        if not isinstance(act, dict):
            act = {}
        for field in required:
            if field not in act or act[field] is None:
                missing.append(field)
    elif phase == "verify":
        scores = last.get("scores", {})
        verify_data = last.get("verify", {})
        if not isinstance(verify_data, dict):
            verify_data = {}
        merged = {**verify_data, "scores": scores if scores else None}
        for field in required:
            if field not in merged or merged[field] is None:
                missing.append(field)

    errors = []
    warnings = []
    if missing:
        msg = "阶段 {} 输出缺少必需字段: {}".format(phase.upper(), ", ".join(missing))
        if strict:
            errors.append(msg)
        else:
            warnings.append(msg)

    return errors, warnings


# ============================================================
# 统一入口
# ============================================================

def validate(work_dir, strict=False):
    """自动选择验证模式: SSOT JSON 优先，markdown 回退。返回 (errors, warnings, mode)"""
    json_path = os.path.join(work_dir, STATE_FILE)

    if os.path.exists(json_path):
        errors, warnings = validate_json(work_dir, strict=strict)
        return errors, warnings, "json"
    else:
        errors, warnings = validate_markdown(work_dir)
        return errors, warnings, "markdown"


def format_text(errors, warnings, mode):
    """格式化为人类可读文本"""
    lines = []
    lines.append("模式: {} ({})".format(
        "SSOT JSON" if mode == "json" else "Markdown 回退",
        STATE_FILE if mode == "json" else "4 markdown 文件",
    ))

    if errors:
        lines.append("FAIL: {} 个错误".format(len(errors)))
        for e in errors:
            lines.append("  [ERROR] {}".format(e))
    else:
        lines.append("PASS: 无错误")

    if warnings:
        lines.append("WARN: {} 个警告".format(len(warnings)))
        for w in warnings:
            lines.append("  [WARN] {}".format(w))

    return "\n".join(lines)


def format_json_output(errors, warnings, mode):
    """格式化为 JSON 输出"""
    return json.dumps({
        "mode": mode,
        "pass": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "error_count": len(errors),
        "warning_count": len(warnings),
    }, ensure_ascii=False, indent=2)


# ============================================================
# CLI 入口
# ============================================================

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: autoloop-validate.py <工作目录> [--json] [--strict] [--phase-output <phase>]")
        print("  验证 autoloop 数据一致性（SSOT JSON 优先，markdown 回退）")
        print("  --strict  契约/阶段产物问题计为错误；亦可设 AUTOLOOP_VALIDATE_STRICT=1")
        print("  --phase-output <phase>  验证 OODA 阶段输出 Schema（observe/decide/act/verify）")
        sys.exit(1)

    work_dir = sys.argv[1]
    use_json_output = "--json" in sys.argv
    strict_cli = "--strict" in sys.argv
    strict = strict_cli or _validation_strict_default()

    if not os.path.isdir(work_dir):
        print("ERROR: 目录不存在: {}".format(work_dir))
        sys.exit(1)

    # P2-17: --phase-output 模式
    phase_output = None
    if "--phase-output" in sys.argv:
        po_idx = sys.argv.index("--phase-output")
        if po_idx + 1 < len(sys.argv):
            phase_output = sys.argv[po_idx + 1]
        else:
            print("ERROR: --phase-output 需要指定阶段名 (observe/decide/act/verify)")
            sys.exit(1)

    if phase_output:
        errs, warns = validate_phase_output(work_dir, phase_output, strict=strict)
        mode = "phase-output"
    else:
        errs, warns, mode = validate(work_dir, strict=strict)

    if use_json_output:
        print(format_json_output(errs, warns, mode))
    else:
        print(format_text(errs, warns, mode))

    sys.exit(1 if errs else 0)
