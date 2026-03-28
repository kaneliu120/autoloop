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
MULTI_STRATEGY_RE = re.compile(r"^multi:\{.+\}$")

MD_FILES = {
    "results": "autoloop-results.tsv",
    "findings": "autoloop-findings.md",
    "progress": "autoloop-progress.md",
    "plan": "autoloop-plan.md",
}


# ============================================================
# SSOT JSON 模式验证
# ============================================================

def validate_json(work_dir):
    """从 autoloop-state.json 执行全部验证，返回 (errors, warnings) 列表"""
    path = os.path.join(work_dir, STATE_FILE)
    with open(path, "r", encoding="utf-8") as f:
        state = json.load(f)

    errors = []
    warnings = []

    _check_top_level_structure(state, errors)
    _check_primary_key_consistency(state, errors)
    _check_dimension_consistency(state, errors, warnings)
    _check_tsv_completeness(state, errors)
    _check_iteration_sequence(state, errors)
    _check_phase_sequence(state, errors, warnings)
    _check_gate_status(state, errors, warnings)
    _check_budget(state, errors, warnings)
    _check_version_consistency(state, errors)

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

    # 检查每个 iteration 的 strategy_id
    for i, it in enumerate(state.get("iterations", []), start=1):
        sid = it.get("strategy", {}).get("strategy_id", "")
        if not sid or sid in ("—", "baseline", ""):
            continue
        if STRATEGY_RE.match(sid) and sid not in known_strategy_ids:
            errors.append(
                "轮次 {}: strategy_id '{}' 未在 findings/strategy_history 中定义".format(i, sid)
            )

    # 检查 results_tsv 中的 strategy_id
    for row_idx, row in enumerate(state.get("results_tsv", []), start=1):
        sid = row.get("strategy_id", "").strip()
        if not sid or sid in ("—", "baseline", ""):
            continue
        if STRATEGY_RE.match(sid) and sid not in known_strategy_ids:
            errors.append(
                "TSV 行 {}: strategy_id '{}' 未在 findings/strategy_history 中定义".format(row_idx, sid)
            )


def _check_dimension_consistency(state, errors, warnings):
    """维度一致性: plan.dimensions 必须匹配 iterations[].scores 中使用的维度"""
    plan_dims = set()
    for d in state.get("plan", {}).get("dimensions", []):
        if isinstance(d, dict):
            plan_dims.add(d.get("name", d.get("dimension", "")))
        elif isinstance(d, str):
            plan_dims.add(d)

    # 也从 gates 收集
    for g in state.get("plan", {}).get("gates", []):
        dim = g.get("dimension", "")
        if dim:
            plan_dims.add(dim)

    if not plan_dims:
        # 没有定义维度则跳过此检查
        return

    # 收集 iterations 中使用的所有维度
    used_dims = set()
    for it in state.get("iterations", []):
        for dim in it.get("scores", {}):
            used_dims.add(dim)

    # 检查 iterations 中是否使用了未定义的维度
    undefined = used_dims - plan_dims
    for dim in sorted(undefined):
        errors.append(
            "维度 '{}' 在 iterations.scores 中使用但未在 plan.dimensions/gates 中定义".format(dim)
        )

    # 检查定义了但未使用的维度（仅警告）
    unused = plan_dims - used_dims
    if unused and state.get("iterations"):
        for dim in sorted(unused):
            warnings.append(
                "维度 '{}' 已定义但未在任何 iteration.scores 中使用".format(dim)
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
        dim = gate.get("dimension", "")
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
    n_iterations = len(state.get("iterations", []))

    if max_rounds and max_rounds > 0:
        if n_iterations > max_rounds:
            errors.append(
                "预算超支: 已执行 {} 轮，预算上限 {} 轮".format(n_iterations, max_rounds)
            )

    # current_round 应与 iterations 数量一致
    if n_iterations > 0 and current_round != n_iterations:
        warnings.append(
            "budget.current_round={} 与实际 iterations 数量 {} 不一致".format(
                current_round, n_iterations
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

        # strategy_id 格式校验
        if sid and sid not in ("—", "baseline"):
            if not STRATEGY_RE.match(sid) and not MULTI_STRATEGY_RE.match(sid):
                errors.append(
                    "行{}: strategy_id 格式错误: '{}' (期望 S{{NN}}-{{描述}})".format(ln, sid)
                )
            elif STRATEGY_RE.match(sid) and sid not in f_strategies:
                errors.append(
                    "行{}: strategy_id '{}' 在 findings.md 中未定义".format(ln, sid)
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
# 统一入口
# ============================================================

def validate(work_dir):
    """自动选择验证模式: SSOT JSON 优先，markdown 回退。返回 (errors, warnings, mode)"""
    json_path = os.path.join(work_dir, STATE_FILE)

    if os.path.exists(json_path):
        errors, warnings = validate_json(work_dir)
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
        print("用法: autoloop-validate.py <工作目录> [--json]")
        print("  验证 autoloop 数据一致性（SSOT JSON 优先，markdown 回退）")
        sys.exit(1)

    work_dir = sys.argv[1]
    use_json_output = "--json" in sys.argv

    if not os.path.isdir(work_dir):
        print("ERROR: 目录不存在: {}".format(work_dir))
        sys.exit(1)

    errs, warns, mode = validate(work_dir)

    if use_json_output:
        print(format_json_output(errs, warns, mode))
    else:
        print(format_text(errs, warns, mode))

    sys.exit(1 if errs else 0)
