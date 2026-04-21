#!/usr/bin/env python3
"""AutoLoop final report generator

Usage:
  autoloop-finalize.py <work_dir>          Generate the final report
  autoloop-finalize.py <work_dir> --json   JSON output
"""

import json
import os
import sys
import datetime


def load_state(work_dir):
    """Load autoloop-state.json."""
    path = os.path.join(work_dir, "autoloop-state.json")
    if not os.path.isfile(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def extract_plan_summary(state):
    """Extract the plan summary."""
    plan = state.get("plan", {})
    budget = plan.get("budget", {})
    meta = state.get("metadata", {})
    max_r = budget.get("max_rounds")
    if not max_r:
        max_r = plan.get("max_iterations", "unknown")
    created = meta.get("created_at") or plan.get("created_at", "unknown")
    return {
        "task_id": plan.get("task_id", "unknown"),
        "template": plan.get("template", "unknown"),
        "goal": plan.get("goal", "unknown"),
        "created_at": created,
        "max_iterations": max_r,
        "dimensions": plan.get("dimensions", []),
    }


def extract_iteration_trajectory(state):
    """Extract the iteration trajectory (per-round score changes)."""
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
    """Extract the final scores."""
    iterations = state.get("iterations", [])
    if not iterations:
        return {}
    return iterations[-1].get("scores", {})


def extract_key_findings(state):
    """Extract the key findings."""
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
    """Extract strategy effectiveness."""
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
    """Extract the termination reason."""
    return state.get("termination", {}).get("reason", "not recorded")


def extract_side_effects(state):
    """Extract side-effect records."""
    effects = []
    for it in state.get("iterations", []):
        se = it.get("side_effects", [])
        if se:
            effects.extend(se)
    return effects


def build_report_data(state):
    """Assemble all report data."""
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
    """Format the report data as Markdown."""
    lines = []
    plan = data["plan_summary"]

    lines.append("# AutoLoop Final Report")
    lines.append("")
    lines.append("## Metadata")
    lines.append("")
    lines.append("| Field | Value |")
    lines.append("|------|-----|")
    lines.append(f"| Task ID | {plan['task_id']} |")
    lines.append(f"| Template | {plan['template']} |")
    lines.append(f"| Goal | {plan['goal']} |")
    lines.append(f"| Created at | {plan['created_at']} |")
    lines.append(f"| Report generated at | {data['generated_at']} |")
    lines.append(f"| Total iterations | {data['iteration_count']} |")
    lines.append(f"| Termination reason | {data['termination_reason']} |")
    lines.append("")

    # KPI trajectory table
    lines.append("---")
    lines.append("")
    lines.append("## KPI Trajectory")
    lines.append("")

    trajectory = data["iteration_trajectory"]
    if trajectory:
            # Collect all dimensions
        all_dims = set()
        for t in trajectory:
            all_dims.update(t["scores"].keys())
        all_dims = sorted(all_dims)

        if all_dims:
            header = "| Round | " + " | ".join(all_dims) + " | Strategy |"
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
            lines.append("(No scoring data)")
    else:
        lines.append("(No iteration records)")

    lines.append("")

    # Final scores
    lines.append("---")
    lines.append("")
    lines.append("## Final Scores")
    lines.append("")
    final = data["final_scores"]
    if final:
        lines.append("| Dimension | Score |")
        lines.append("|------|------|")
        for dim, score in sorted(final.items()):
            lines.append(f"| {dim} | {score} |")
    else:
        lines.append("(No final scores)")
    lines.append("")

    # Strategy effectiveness
    lines.append("---")
    lines.append("")
    lines.append("## Strategy Effectiveness")
    lines.append("")
    strats = data["strategy_effectiveness"]
    if strats:
        # Top improvements
        sorted_strats = sorted(
            strats.items(), key=lambda x: x[1]["positive"], reverse=True
        )
        lines.append("### Effective Strategies (Top Improvements)")
        lines.append("")
        lines.append("| strategy_id | Uses | Positive | Negative |")
        lines.append("|-------------|------|----------|----------|")
        for sid, info in sorted_strats:
            if info["positive"] > 0:
                lines.append(
                    f"| {sid} | {info['uses']} | {info['positive']} | {info['negative']} |"
                )

        # Failed attempts
        failed = [(sid, info) for sid, info in sorted_strats if info["positive"] == 0]
        if failed:
            lines.append("")
            lines.append("### Failed Strategies")
            lines.append("")
            lines.append("| strategy_id | Uses | Negative |")
            lines.append("|-------------|------|----------|")
            for sid, info in failed:
                lines.append(f"| {sid} | {info['uses']} | {info['negative']} |")
    else:
        lines.append("(No strategy usage records)")
    lines.append("")

    # Side effects
    lines.append("---")
    lines.append("")
    lines.append("## Side Effects")
    lines.append("")
    effects = data["side_effects"]
    if effects:
        for e in effects:
            if isinstance(e, dict):
                lines.append(f"- **{e.get('type', 'unknown')}**: {e.get('description', '—')}")
            else:
                lines.append(f"- {e}")
    else:
        lines.append("(No side-effect records)")
    lines.append("")

    # Key findings summary
    lines.append("---")
    lines.append("")
    lines.append("## Key Findings")
    lines.append("")
    findings = data["key_findings"]
    if findings:
        for f in findings[:20]:  # Show at most 20 items
            lines.append(f"- **{f['dimension']}**: {f['summary']}")
    else:
        lines.append("(No key findings)")
    lines.append("")

    return "\n".join(lines)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    work_dir = sys.argv[1]
    json_output = "--json" in sys.argv

    if not os.path.isdir(work_dir):
        print(f"ERROR: Work directory does not exist: {work_dir}", file=sys.stderr)
        sys.exit(1)

    state = load_state(work_dir)
    if state is None:
        print(
            f"ERROR: autoloop-state.json not found: {work_dir}",
            file=sys.stderr,
        )
        sys.exit(1)

    data = build_report_data(state)

    if json_output:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        report_md = format_markdown_report(data)
        # Write the report to disk
        report_path = os.path.join(work_dir, "autoloop-report.md")
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report_md)
        print(f"OK: Report generated → {report_path}")
        print()
        print(report_md)

    sys.exit(0)


if __name__ == "__main__":
    main()
