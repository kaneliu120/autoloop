#!/usr/bin/env python3
"""AutoLoop SSOT 渲染工具 — 从 autoloop-state.json 生成 4 个可读文件

用法:
  autoloop-render.py <工作目录>              渲染全部 4 个文件
  autoloop-render.py <工作目录> --file plan  只渲染 plan.md
  autoloop-render.py <工作目录> --file progress
  autoloop-render.py <工作目录> --file findings
  autoloop-render.py <工作目录> --file tsv
  autoloop-render.py <工作目录> panorama     全景视图（stdout）
"""

import csv
import json
import os
import sys
from io import StringIO

_rdir = os.path.dirname(os.path.abspath(__file__))
if _rdir not in sys.path:
    sys.path.insert(0, _rdir)
from autoloop_kpi import plan_gate_is_exempt  # noqa: E402

STATE_FILE = "autoloop-state.json"


def load_state(work_dir):
    path = os.path.join(work_dir, STATE_FILE)
    if not os.path.exists(path):
        print("ERROR: 数据源不存在: {}".format(path))
        sys.exit(1)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def render_plan(state, work_dir):
    p = state.get("plan") or {}
    meta = state.get("metadata") or {}
    lines = [
        "# AutoLoop Plan",
        "",
        "## 基本信息",
        "",
        "| 字段 | 值 |",
        "|------|-----|",
        "| 任务 ID | {} |".format(p.get("task_id", "")),
        "| 模板 | {} |".format(p.get("template", "")),
        "| 目标 | {} |".format(p.get("goal", "")),
        "| 状态 | {} |".format(p.get("status", "")),
        "| 协议版本 | {} |".format(meta.get("protocol_version", "")),
        "| 创建时间 | {} |".format(meta.get("created_at", "")),
        "",
    ]

    if p.get("detailed_background"):
        lines += ["## 详细背景", "", p["detailed_background"], ""]

    if p.get("dimensions"):
        lines += ["## 调研维度", ""]
        for i, d in enumerate(p["dimensions"], 1):
            lines.append("{}. {}".format(i, d))
        lines.append("")

    if p.get("gates"):
        lines += ["## 质量门禁", "",
                   "| 维度 | 目标 | 当前 | 状态 |",
                   "|------|------|------|------|"]
        hard_non_exempt_fail = 0
        hard_non_exempt = 0
        for g in p["gates"]:
            dim_col = g.get("dim") or g.get("dimension", "")
            st_show = g.get("status", "—")
            if plan_gate_is_exempt(g):
                st_show = "豁免"
            lines.append("| {} | {} | {} | {} |".format(
                dim_col, g.get("target", ""),
                g.get("current", "—"), st_show))
            if (g.get("gate") or "").lower() == "hard" and not plan_gate_is_exempt(g):
                hard_non_exempt += 1
                s = (g.get("status") or "").strip()
                if s == "未达标":
                    hard_non_exempt_fail += 1
        lines.append(
            "*硬门禁未达标（不含豁免行）: {} / {}*".format(
                hard_non_exempt_fail, hard_non_exempt
            )
        )
        lines.append("")

    budget = p.get("budget", {})
    lines += [
        "## 预算",
        "",
        "- 最大轮次: {}".format(budget.get("max_rounds", "未设定")),
        "- 当前轮次: {}".format(budget.get("current_round", 0)),
        "- 时间限制: {}".format(budget.get("time_limit", "无限制")),
        "",
    ]

    if p.get("change_log"):
        lines += ["## 变更记录", "",
                   "| 时间 | 字段 | 变更前 | 变更后 | 原因 |",
                   "|------|------|--------|--------|------|"]
        for c in p["change_log"][-10:]:
            lines.append("| {} | {} | {} | {} | {} |".format(
                c.get("time", ""), c.get("field", ""),
                c.get("before", "")[:30], c.get("after", "")[:30],
                c.get("reason", "")))
        lines.append("")

    path = os.path.join(work_dir, "autoloop-plan.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return path


def render_progress(state, work_dir):
    lines = ["# AutoLoop Progress", ""]

    for it in state.get("iterations", []):
        lines += [
            "## 第 {} 轮".format(it["round"]),
            "",
            "- 状态: {}".format(it.get("status", "")),
            "- 阶段: {}".format(it.get("phase", "")),
            "- 开始: {}".format(it.get("start_time", "")),
            "",
        ]

        if it.get("scores"):
            lines += ["### 得分", "",
                       "| 维度 | 分数 |", "|------|------|"]
            for dim, score in it["scores"].items():
                lines.append("| {} | {} |".format(dim, score))
            lines.append("")

        strategy = it.get("strategy", {})
        if strategy.get("strategy_id"):
            lines += ["### 策略: {} — {}".format(
                strategy.get("strategy_id", ""), strategy.get("name", "")), ""]

        evolve = it.get("evolve", {})
        if evolve.get("termination") != "继续":
            lines.append("### 终止: {}".format(evolve.get("termination", "")))
            lines.append("")

        reflect = it.get("reflect", {})
        if reflect.get("lesson_learned"):
            lines += ["### 反思", "", reflect["lesson_learned"], ""]
        sid = (reflect.get("strategy_id") or "").strip()
        eff = (reflect.get("effect") or "").strip()
        if sid or eff:
            lines += [
                "### 结构化反思",
                "",
                "- **strategy_id**: `{}`".format(sid or "—"),
                "- **effect**: {}".format(eff or "—"),
            ]
            for k in ("dimension", "delta", "rating_1_to_5"):
                v = reflect.get(k)
                if v is not None and v != "" and v != 0:
                    lines.append("- **{}**: {}".format(k, v))
            ctx = reflect.get("context")
            if ctx:
                lines.append(
                    "- **context**: {}".format(str(ctx).replace("\n", " ")[:480])
                )
            lines.append("")

        lines.append("---")
        lines.append("")

    path = os.path.join(work_dir, "autoloop-progress.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return path


def reflect_four_layer_footer_lines(state):
    """loop-protocol 四层 H2+表：随 findings.md 每次渲染追加，避免仅 SSOT 轮次块时被整文件重写冲掉，OBSERVE Step0 可计数。"""
    meta = state.get("metadata") or {} if isinstance(state, dict) else {}
    pv = meta.get("protocol_version")
    pv_s = str(pv).strip() if pv is not None and str(pv).strip() else "1.0.0"
    return [
        "",
        "## 问题清单（REFLECT 第 1 层）",
        "",
        "| ID | 描述 | 状态 |",
        "| --- | --- | --- |",
        "| RFL-1 | 由 render 追加；请与 SSOT findings 同步更新叙事 | open |",
        "",
        "## 策略评估（REFLECT 第 2 层）",
        "",
        "| 策略 | 结果 | 备注 |",
        "| --- | --- | --- |",
        "| — | 待填 | 每轮 DECIDE 后更新 |",
        "",
        "## 模式识别（REFLECT 第 3 层）",
        "",
        "| 模式 | 说明 |",
        "| --- | --- |",
        "| — | 待从多轮 findings 归纳 |",
        "",
        "## 经验教训（REFLECT 第 4 层）",
        "",
        "| 教训 | 后续动作 |",
        "| --- | --- |",
        "| — | 待记录 |",
        "",
        "协议版本（findings 侧）: {}（与 SSOT metadata.protocol_version 对齐）".format(pv_s),
    ]


def render_findings(state, work_dir):
    findings = state.get("findings", {})
    lines = ["# AutoLoop Findings", ""]

    summary = findings.get("executive_summary", {})
    if summary.get("topic") != "待填写":
        lines += [
            "## 执行摘要",
            "",
            "- 主题: {}".format(summary.get("topic", "")),
            "- 总轮次: {}".format(summary.get("total_rounds", 0)),
            "",
        ]

    for rd in findings.get("rounds", []):
        lines += ["## 第 {} 轮发现".format(rd["round"]), ""]
        for f in rd.get("findings", []):
            lines.append("### {} [{}]".format(
                f.get("dimension", ""), f.get("confidence", "")))
            lines.append("")
            body = f.get("content", "")
            summ = f.get("summary", "")
            if summ:
                lines.append("**摘要**: {}".format(summ))
                lines.append("")
            lines.append(body)
            if f.get("source"):
                lines.append("")
                lines.append("来源: {}".format(f["source"]))
            if f.get("strategy_id"):
                lines.append("策略: {}".format(f["strategy_id"]))
            if f.get("id"):
                lines.append("ID: {}".format(f["id"]))
            lines.append("")

    if findings.get("problem_tracker"):
        lines += ["## 问题追踪", "",
                   "| ID | 描述 | 状态 |", "|-----|------|------|"]
        for p in findings["problem_tracker"]:
            lines.append("| {} | {} | {} |".format(
                p.get("id", ""), p.get("description", "")[:50],
                p.get("status", "")))
        lines.append("")

    lines.extend(reflect_four_layer_footer_lines(state))

    path = os.path.join(work_dir, "autoloop-findings.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return path


def render_tsv(state, work_dir):
    rows = state.get("results_tsv", [])
    columns = [
        "iteration", "phase", "status", "dimension", "metric_value", "delta",
        "strategy_id", "action_summary", "side_effect", "evidence_ref",
        "unit_id", "protocol_version", "score_variance", "confidence", "details"
    ]

    path = os.path.join(work_dir, "autoloop-results.tsv")
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns, delimiter="\t",
                                extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return path


RENDERERS = {
    "plan": render_plan,
    "progress": render_progress,
    "findings": render_findings,
    "tsv": render_tsv,
}


# ---------------------------------------------------------------------------
# panorama — 全景视图（stdout only, 不写文件）
# ---------------------------------------------------------------------------

def render_panorama(state):
    """从 state.json 提取关键信息，输出全景视图到 stdout。"""
    plan = state.get("plan") or {}
    meta = state.get("metadata") or {}
    iterations = state.get("iterations") or []
    findings = state.get("findings") or {}
    budget = plan.get("budget") or {}

    task_name = plan.get("task_id", "unknown")
    template = plan.get("template", "?")
    max_rounds = budget.get("max_rounds", 0)
    current_round = budget.get("current_round", 0)
    status_label = plan.get("status", "未知")

    # 当前阶段: 取最后一个 iteration 的 phase
    last_phase = "N/A"
    if iterations:
        last_phase = iterations[-1].get("phase", "N/A")

    # 完成度: current_round / max_rounds (if max_rounds > 0)
    if max_rounds > 0:
        pct = min(100, round(current_round / max_rounds * 100))
        budget_line = "轮次: {}/{} ({}%)".format(current_round, max_rounds, pct)
    else:
        budget_line = "轮次: {} (无上限)".format(current_round)

    lines = [
        "## 任务全景 — {} ({})".format(task_name, template),
        "状态: Round {}/{} | {} | {}".format(
            current_round, max_rounds if max_rounds else "∞",
            last_phase, status_label),
        "",
    ]

    # --- 门禁一览 ---
    gates = plan.get("gates") or []
    if gates:
        lines += [
            "### 门禁一览",
            "| 维度 | 当前 | 目标 | 通过? | 置信度 | 趋势(近3轮) |",
            "|------|------|------|-------|--------|------------|",
        ]
        for g in gates:
            dim = g.get("dim") or g.get("dimension", "")
            current_val = g.get("current", "—")
            target_val = g.get("target", "—")
            passed = "✓" if g.get("status") == "达标" else "✗"
            if plan_gate_is_exempt(g):
                passed = "豁免"

            # 趋势: 从最近 3 轮 iterations 的 scores 中提取该维度
            recent_scores = []
            for it in iterations[-3:]:
                scores = it.get("scores") or {}
                if dim in scores:
                    recent_scores.append(scores[dim])
            if recent_scores:
                trend_parts = "→".join(str(s) for s in recent_scores)
                if len(recent_scores) >= 2:
                    if recent_scores[-1] > recent_scores[-2]:
                        trend_parts += " ↑"
                    elif recent_scores[-1] < recent_scores[-2]:
                        trend_parts += " ↓"
                    else:
                        trend_parts += " →"
            else:
                trend_parts = "—"

            # 置信度: heuristic (来自 gate 本身没有置信度字段, 用 unit 或默认)
            confidence = g.get("confidence", g.get("unit", "heuristic"))

            lines.append("| {} | {} | {} | {} | {} | {} |".format(
                dim, current_val, target_val, passed, confidence, trend_parts))
        lines.append("")

    # --- 本轮策略 ---
    if iterations:
        last_it = iterations[-1]
        strategy = last_it.get("strategy") or {}
        sid = strategy.get("strategy_id", "—")
        desc = strategy.get("description") or strategy.get("name", "")
        lines += [
            "### 本轮策略",
            "- strategy_id: {} — {}".format(sid, desc),
        ]
        # reflect 中的 effect
        reflect = last_it.get("reflect") or {}
        effect = reflect.get("effect") or reflect.get("strategy_review", {}).get("verdict", "")
        if effect:
            lines.append("- effect: {}".format(effect))
        lines.append("")

    # --- 未解决问题 (Top 5) ---
    problems = findings.get("problem_tracker") or []
    open_problems = [p for p in problems if (p.get("status") or "").lower() in ("open", "进行中", "")]
    if open_problems:
        lines.append("### 未解决问题 (Top 5)")
        for i, p in enumerate(open_problems[:5], 1):
            lines.append("{}. [{}] {}".format(
                i, p.get("id", "?"), p.get("description", "")))
        lines.append("")
    else:
        lines += ["### 未解决问题", "无", ""]

    # --- 经验教训 (从最近几轮 reflect 中提取) ---
    effective = []
    avoid = []
    for it in iterations[-5:]:
        reflect = it.get("reflect") or {}
        lesson = (reflect.get("lesson_learned") or "").strip()
        if lesson:
            sr = reflect.get("strategy_review") or {}
            rating = sr.get("rating", 0)
            if isinstance(rating, (int, float)) and rating >= 3:
                effective.append(lesson[:120])
            elif isinstance(rating, (int, float)) and rating > 0 and rating < 3:
                avoid.append(lesson[:120])
            else:
                effective.append(lesson[:120])
    if effective or avoid:
        lines.append("### 经验教训")
        if effective:
            lines.append("- 有效: {}".format("; ".join(effective[:3])))
        if avoid:
            lines.append("- 避免: {}".format("; ".join(avoid[:3])))
        lines.append("")

    # --- 资源 ---
    completion_authority = meta.get("completion_authority", "internal")
    lines += [
        "### 资源",
        "- {}".format(budget_line),
        "- 完成权威: {}".format(completion_authority),
    ]

    output = "\n".join(lines)
    print(output)
    return output


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    work_dir = sys.argv[1]

    # 检查 panorama 子命令
    if len(sys.argv) >= 3 and sys.argv[2] == "panorama":
        state = load_state(work_dir)
        render_panorama(state)
        return

    state = load_state(work_dir)

    target = None
    if "--file" in sys.argv:
        idx = sys.argv.index("--file")
        if idx + 1 < len(sys.argv):
            target = sys.argv[idx + 1]
            if target not in RENDERERS:
                print("ERROR: 未知文件类型: {}".format(target))
                print("可选: {}".format(", ".join(RENDERERS.keys())))
                sys.exit(1)

    if target:
        path = RENDERERS[target](state, work_dir)
        print("OK: 已渲染 {}".format(path))
    else:
        for name, renderer in RENDERERS.items():
            path = renderer(state, work_dir)
            print("OK: 已渲染 {}".format(path))

    print("完成: 从 autoloop-state.json 生成可读文件")


if __name__ == "__main__":
    main()
