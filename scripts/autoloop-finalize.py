#!/usr/bin/env python3
"""AutoLoop 最终报告生成工具

用法:
  autoloop-finalize.py <work_dir>          生成最终报告
  autoloop-finalize.py <work_dir> --json   JSON 输出
"""

import json
import os
import sys
import datetime


def load_state(work_dir):
    """加载 autoloop-state.json。"""
    path = os.path.join(work_dir, "autoloop-state.json")
    if not os.path.isfile(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def extract_plan_summary(state):
    """提取计划摘要。"""
    plan = state.get("plan", {})
    budget = plan.get("budget", {})
    meta = state.get("metadata", {})
    max_r = budget.get("max_rounds")
    if not max_r:
        max_r = plan.get("max_iterations", "未知")
    created = meta.get("created_at") or plan.get("created_at", "未知")
    return {
        "task_id": plan.get("task_id", "未知"),
        "template": plan.get("template", "未知"),
        "goal": plan.get("goal", "未知"),
        "created_at": created,
        "max_iterations": max_r,
        "dimensions": plan.get("dimensions", []),
    }


def extract_iteration_trajectory(state):
    """提取迭代轨迹（每轮的分数变化）。"""
    iterations = state.get("iterations", [])
    trajectory = []
    for i, it in enumerate(iterations):
        entry = {
            "round": i + 1,
            "phase": it.get("phase", "—"),
            "scores": it.get("scores", {}),
            "strategies": it.get("strategies_used", []),
            "delta": it.get("delta", {}),
        }
        trajectory.append(entry)
    return trajectory


def extract_final_scores(state):
    """提取最终分数。"""
    iterations = state.get("iterations", [])
    if not iterations:
        return {}
    return iterations[-1].get("scores", {})


def extract_key_findings(state):
    """提取关键发现。"""
    findings = state.get("findings", {})
    rounds = findings.get("rounds", [])
    key = []
    for rnd in rounds:
        for f in rnd.get("findings", []):
            key.append({
                "dimension": f.get("dimension", "—"),
                "summary": f.get(
                    "summary",
                    f.get("description", f.get("content", "—")),
                ),
                "source": f.get("source", "—"),
            })
    return key


def extract_strategy_effectiveness(state):
    """提取策略有效性。"""
    iterations = state.get("iterations", [])
    strategies = {}
    for it in iterations:
        for s in it.get("strategies_used", []):
            sid = s if isinstance(s, str) else s.get("strategy_id", "unknown")
            if sid not in strategies:
                strategies[sid] = {"uses": 0, "positive": 0, "negative": 0}
            strategies[sid]["uses"] += 1
            delta = it.get("delta", {})
            total_delta = sum(
                v for v in delta.values() if isinstance(v, (int, float))
            )
            if total_delta > 0:
                strategies[sid]["positive"] += 1
            elif total_delta < 0:
                strategies[sid]["negative"] += 1
    return strategies


def extract_termination_reason(state):
    """提取终止原因。"""
    return state.get("termination", {}).get("reason", "未记录")


def extract_side_effects(state):
    """提取副作用记录。"""
    effects = []
    for it in state.get("iterations", []):
        se = it.get("side_effects", [])
        if se:
            effects.extend(se)
    return effects


def build_report_data(state):
    """整合所有报告数据。"""
    return {
        "generated_at": datetime.datetime.now().isoformat(),
        "plan_summary": extract_plan_summary(state),
        "iteration_count": len(state.get("iterations", [])),
        "iteration_trajectory": extract_iteration_trajectory(state),
        "final_scores": extract_final_scores(state),
        "key_findings": extract_key_findings(state),
        "strategy_effectiveness": extract_strategy_effectiveness(state),
        "side_effects": extract_side_effects(state),
        "termination_reason": extract_termination_reason(state),
    }


def format_markdown_report(data):
    """将报告数据格式化为 Markdown。"""
    lines = []
    plan = data["plan_summary"]

    lines.append("# AutoLoop 最终报告")
    lines.append("")
    lines.append("## 元信息")
    lines.append("")
    lines.append("| 字段 | 值 |")
    lines.append("|------|-----|")
    lines.append(f"| 任务 ID | {plan['task_id']} |")
    lines.append(f"| 模板 | {plan['template']} |")
    lines.append(f"| 目标 | {plan['goal']} |")
    lines.append(f"| 创建时间 | {plan['created_at']} |")
    lines.append(f"| 报告生成时间 | {data['generated_at']} |")
    lines.append(f"| 总迭代轮次 | {data['iteration_count']} |")
    lines.append(f"| 终止原因 | {data['termination_reason']} |")
    lines.append("")

    # KPI 轨迹表
    lines.append("---")
    lines.append("")
    lines.append("## KPI 轨迹")
    lines.append("")

    trajectory = data["iteration_trajectory"]
    if trajectory:
        # 收集所有维度
        all_dims = set()
        for t in trajectory:
            all_dims.update(t["scores"].keys())
        all_dims = sorted(all_dims)

        if all_dims:
            header = "| 轮次 | " + " | ".join(all_dims) + " | 策略 |"
            sep = "|------|" + "|".join(["------"] * len(all_dims)) + "|------|"
            lines.append(header)
            lines.append(sep)

            for t in trajectory:
                scores_str = " | ".join(
                    str(t["scores"].get(d, "—")) for d in all_dims
                )
                strats = ", ".join(
                    s if isinstance(s, str) else s.get("strategy_id", "?")
                    for s in t["strategies"]
                ) or "—"
                lines.append(f"| {t['round']} | {scores_str} | {strats} |")
        else:
            lines.append("（无评分数据）")
    else:
        lines.append("（无迭代记录）")

    lines.append("")

    # 最终得分
    lines.append("---")
    lines.append("")
    lines.append("## 最终得分")
    lines.append("")
    final = data["final_scores"]
    if final:
        lines.append("| 维度 | 得分 |")
        lines.append("|------|------|")
        for dim, score in sorted(final.items()):
            lines.append(f"| {dim} | {score} |")
    else:
        lines.append("（无最终得分）")
    lines.append("")

    # 策略有效性
    lines.append("---")
    lines.append("")
    lines.append("## 策略有效性")
    lines.append("")
    strats = data["strategy_effectiveness"]
    if strats:
        # Top improvements
        sorted_strats = sorted(
            strats.items(), key=lambda x: x[1]["positive"], reverse=True
        )
        lines.append("### 有效策略（Top Improvements）")
        lines.append("")
        lines.append("| strategy_id | 使用次数 | 正向次数 | 负向次数 |")
        lines.append("|-------------|---------|---------|---------|")
        for sid, info in sorted_strats:
            if info["positive"] > 0:
                lines.append(
                    f"| {sid} | {info['uses']} | {info['positive']} | {info['negative']} |"
                )

        # Failed attempts
        failed = [(sid, info) for sid, info in sorted_strats if info["positive"] == 0]
        if failed:
            lines.append("")
            lines.append("### 失败策略（Failed Attempts）")
            lines.append("")
            lines.append("| strategy_id | 使用次数 | 负向次数 |")
            lines.append("|-------------|---------|---------|")
            for sid, info in failed:
                lines.append(f"| {sid} | {info['uses']} | {info['negative']} |")
    else:
        lines.append("（无策略使用记录）")
    lines.append("")

    # 副作用
    lines.append("---")
    lines.append("")
    lines.append("## 副作用记录")
    lines.append("")
    effects = data["side_effects"]
    if effects:
        for e in effects:
            if isinstance(e, dict):
                lines.append(f"- **{e.get('type', '未知')}**: {e.get('description', '—')}")
            else:
                lines.append(f"- {e}")
    else:
        lines.append("（无副作用记录）")
    lines.append("")

    # 关键发现摘要
    lines.append("---")
    lines.append("")
    lines.append("## 关键发现")
    lines.append("")
    findings = data["key_findings"]
    if findings:
        for f in findings[:20]:  # 最多展示 20 条
            lines.append(f"- **{f['dimension']}**: {f['summary']}")
    else:
        lines.append("（无关键发现）")
    lines.append("")

    return "\n".join(lines)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    work_dir = sys.argv[1]
    json_output = "--json" in sys.argv

    if not os.path.isdir(work_dir):
        print(f"ERROR: 工作目录不存在: {work_dir}", file=sys.stderr)
        sys.exit(1)

    state = load_state(work_dir)
    if state is None:
        print(
            f"ERROR: 未找到 autoloop-state.json: {work_dir}",
            file=sys.stderr,
        )
        sys.exit(1)

    data = build_report_data(state)

    if json_output:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        report_md = format_markdown_report(data)
        # 写入文件
        report_path = os.path.join(work_dir, "autoloop-report.md")
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report_md)
        print(f"OK: 报告已生成 → {report_path}")
        print()
        print(report_md)

    sys.exit(0)


if __name__ == "__main__":
    main()
