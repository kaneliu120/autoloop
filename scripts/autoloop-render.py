#!/usr/bin/env python3
"""AutoLoop SSOT 渲染工具 — 从 autoloop-state.json 生成 4 个可读文件

用法:
  autoloop-render.py <工作目录>              渲染全部 4 个文件
  autoloop-render.py <工作目录> --file plan  只渲染 plan.md
  autoloop-render.py <工作目录> --file progress
  autoloop-render.py <工作目录> --file findings
  autoloop-render.py <工作目录> --file tsv
"""

import csv
import json
import os
import sys
from io import StringIO

STATE_FILE = "autoloop-state.json"


def load_state(work_dir):
    path = os.path.join(work_dir, STATE_FILE)
    if not os.path.exists(path):
        print("ERROR: 数据源不存在: {}".format(path))
        sys.exit(1)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def render_plan(state, work_dir):
    p = state["plan"]
    meta = state["metadata"]
    lines = [
        "# AutoLoop Plan",
        "",
        "## 基本信息",
        "",
        "| 字段 | 值 |",
        "|------|-----|",
        "| 任务 ID | {} |".format(p["task_id"]),
        "| 模板 | {} |".format(p["template"]),
        "| 目标 | {} |".format(p["goal"]),
        "| 状态 | {} |".format(p["status"]),
        "| 协议版本 | {} |".format(meta["protocol_version"]),
        "| 创建时间 | {} |".format(meta["created_at"]),
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
        for g in p["gates"]:
            lines.append("| {} | {} | {} | {} |".format(
                g.get("dimension", ""), g.get("target", ""),
                g.get("current", "—"), g.get("status", "—")))
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

        lines.append("---")
        lines.append("")

    path = os.path.join(work_dir, "autoloop-progress.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return path


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
            lines.append(f.get("content", ""))
            if f.get("source"):
                lines.append("")
                lines.append("来源: {}".format(f["source"]))
            lines.append("")

    if findings.get("problem_tracker"):
        lines += ["## 问题追踪", "",
                   "| ID | 描述 | 状态 |", "|-----|------|------|"]
        for p in findings["problem_tracker"]:
            lines.append("| {} | {} | {} |".format(
                p.get("id", ""), p.get("description", "")[:50],
                p.get("status", "")))
        lines.append("")

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


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    work_dir = sys.argv[1]
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
