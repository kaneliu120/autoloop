#!/usr/bin/env python3
"""AutoLoop SSOT renderer — generates 4 readable files from autoloop-state.json

Usage:
  autoloop-render.py <Work Directory>              render all 4 files
  autoloop-render.py <Work Directory> --file plan  render only plan.md
  autoloop-render.py <Work Directory> --file progress
  autoloop-render.py <Work Directory> --file findings
  autoloop-render.py <Work Directory> --file tsv
  autoloop-render.py <Work Directory> panorama     Panorama View(stdout)
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
        print("ERROR: data source does not exist: {}".format(path))
        sys.exit(1)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def render_plan(state, work_dir):
    p = state.get("plan") or {}
    meta = state.get("metadata") or {}
    lines = [
        "# AutoLoop Plan",
        "",
        "## Basic Information",
        "",
        "| Field | Value |",
        "|------|-----|",
        "| Task ID | {} |".format(p.get("task_id", "")),
        "| Template | {} |".format(p.get("template", "")),
        "| Target | {} |".format(p.get("goal", "")),
        "| Status | {} |".format(p.get("status", "")),
        "| Protocol Version | {} |".format(meta.get("protocol_version", "")),
        "| Created At | {} |".format(meta.get("created_at", "")),
        "",
    ]

    if p.get("detailed_background"):
        lines += ["## Detailed Background", "", p["detailed_background"], ""]

    if p.get("dimensions"):
        lines += ["## ResearchDimension", ""]
        for i, d in enumerate(p["dimensions"], 1):
            lines.append("{}. {}".format(i, d))
        lines.append("")

    if p.get("gates"):
        lines += ["## Quality Gates", "",
                   "| Dimension | Target | Current | Status |",
                   "|------|------|------|------|"]
        hard_non_exempt_fail = 0
        hard_non_exempt = 0
        for g in p["gates"]:
            dim_col = g.get("dim") or g.get("dimension", "")
            st_show = g.get("status", "—")
            if plan_gate_is_exempt(g):
                st_show = "Exempt"
            lines.append("| {} | {} | {} | {} |".format(
                dim_col, g.get("target", ""),
                g.get("current", "—"), st_show))
            if (g.get("gate") or "").lower() == "hard" and not plan_gate_is_exempt(g):
                hard_non_exempt += 1
                s = (g.get("status") or "").strip()
                if s == "Fail":
                    hard_non_exempt_fail += 1
        lines.append(
            "*Hard gates not met (excluding exempt rows): {} / {}*".format(
                hard_non_exempt_fail, hard_non_exempt
            )
        )
        lines.append("")

    budget = p.get("budget", {})
    lines += [
        "## Budget",
        "",
        "- Max Rounds: {}".format(budget.get("max_rounds", "Not Set")),
        "- current round: {}".format(budget.get("current_round", 0)),
        "- Time Limit: {}".format(budget.get("time_limit", "Unlimited")),
        "",
    ]

    if p.get("change_log"):
        lines += ["## Change Log", "",
                   "| Time | Field | Before | After | Reason |",
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
            "## Round {}".format(it["round"]),
            "",
            "- Status: {}".format(it.get("status", "")),
            "- Phase: {}".format(it.get("phase", "")),
            "- Start: {}".format(it.get("start_time", "")),
            "",
        ]

        if it.get("scores"):
            lines += ["### Scores", "",
                       "| Dimension | score |", "|------|------|"]
            for dim, score in it["scores"].items():
                lines.append("| {} | {} |".format(dim, score))
            lines.append("")

        strategy = it.get("strategy", {})
        if strategy.get("strategy_id"):
            lines += ["### Strategy: {} — {}".format(
                strategy.get("strategy_id", ""), strategy.get("name", "")), ""]

        evolve = it.get("evolve", {})
        if evolve.get("termination") != "Continue":
            lines.append("### Termination: {}".format(evolve.get("termination", "")))
            lines.append("")

        reflect = it.get("reflect", {})
        if reflect.get("lesson_learned"):
            lines += ["### Reflection", "", reflect["lesson_learned"], ""]
        sid = (reflect.get("strategy_id") or "").strip()
        eff = (reflect.get("effect") or "").strip()
        if sid or eff:
            lines += [
                "### Structured Reflection",
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
    """loop-protocol  H2+:  findings.md , Avoid SSOT Roundfile, OBSERVE Step0 ."""
    meta = state.get("metadata") or {} if isinstance(state, dict) else {}
    pv = meta.get("protocol_version")
    pv_s = str(pv).strip() if pv is not None and str(pv).strip() else "1.0.0"
    return [
        "",
        "## Issue List (REFLECT Layer 1)",
        "",
        "| ID | Description | Status |",
        "| --- | --- | --- |",
        "| RFL-1 | Appended by render; keep the narrative synchronized with SSOT findings | open |",
        "",
        "## Strategy Evaluation (REFLECT Layer 2)",
        "",
        "| Strategy | Result | Notes |",
        "| --- | --- | --- |",
        "| — | TBD | update after each DECIDE round |",
        "",
        "## Pattern Recognition (REFLECT Layer 3)",
        "",
        "| Pattern | Description |",
        "| --- | --- |",
        "| — | to be summarized from multi-round findings |",
        "",
        "## Lessons Learned (REFLECT Layer 4)",
        "",
        "| Lesson | Follow-up Action |",
        "| --- | --- |",
        "| — | To Record |",
        "",
        "Protocol Version(findings side): {} (aligned with SSOT metadata.protocol_version)".format(pv_s),
    ]


def render_findings(state, work_dir):
    findings = state.get("findings", {})
    lines = ["# AutoLoop Findings", ""]

    summary = findings.get("executive_summary", {})
    if summary.get("topic") != "TBD":
        lines += [
            "## Executive Summary",
            "",
            "- Topic: {}".format(summary.get("topic", "")),
            "- Total Rounds: {}".format(summary.get("total_rounds", 0)),
            "",
        ]

    for rd in findings.get("rounds", []):
        lines += ["## Round {} Findings".format(rd["round"]), ""]
        for f in rd.get("findings", []):
            lines.append("### {} [{}]".format(
                f.get("dimension", ""), f.get("confidence", "")))
            lines.append("")
            body = f.get("content", "")
            summ = f.get("summary", "")
            if summ:
                lines.append("**Summary**: {}".format(summ))
                lines.append("")
            lines.append(body)
            if f.get("source"):
                lines.append("")
                lines.append("Source: {}".format(f["source"]))
            if f.get("strategy_id"):
                lines.append("Strategy: {}".format(f["strategy_id"]))
            if f.get("id"):
                lines.append("ID: {}".format(f["id"]))
            lines.append("")

    if findings.get("problem_tracker"):
        lines += ["## Problem Tracking", "",
                   "| ID | Description | Status |", "|-----|------|------|"]
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
# panorama — Panorama View (stdout only, does not write files)
# ---------------------------------------------------------------------------

def render_panorama(state):
    """Extract key information from state.json and print the panorama view to stdout."""
    plan = state.get("plan") or {}
    meta = state.get("metadata") or {}
    iterations = state.get("iterations") or []
    findings = state.get("findings") or {}
    budget = plan.get("budget") or {}

    task_name = plan.get("task_id", "unknown")
    template = plan.get("template", "?")
    max_rounds = budget.get("max_rounds", 0)
    current_round = budget.get("current_round", 0)
    status_label = plan.get("status", "Unknown")

    # CurrentPhase: last iteration  phase
    last_phase = "N/A"
    if iterations:
        last_phase = iterations[-1].get("phase", "N/A")

    # Progress: current_round / max_rounds (if max_rounds > 0)
    if max_rounds > 0:
        pct = min(100, round(current_round / max_rounds * 100))
        budget_line = "Round: {}/{} ({}%)".format(current_round, max_rounds, pct)
    else:
        budget_line = "Round: {} (Unlimited)".format(current_round)

    lines = [
        "## Task Panorama — {} ({})".format(task_name, template),
        "Status: Round {}/{} | {} | {}".format(
            current_round, max_rounds if max_rounds else "∞",
            last_phase, status_label),
        "",
    ]

    # --- Gate Overview ---
    gates = plan.get("gates") or []
    if gates:
        lines += [
            "### Gate Overview",
            "| Dimension | Current | Target | Pass? | Confidence | Trend (last 3 rounds) |",
            "|------|------|------|-------|--------|------------|",
        ]
        for g in gates:
            dim = g.get("dim") or g.get("dimension", "")
            current_val = g.get("current", "—")
            target_val = g.get("target", "—")
            passed = "✓" if g.get("status") == "Pass" else "✗"
            if plan_gate_is_exempt(g):
                passed = "Exempt"

            # Trend:  3 round iterations  scores MediumextractDimension
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

            # Confidence: heuristic ( gate ConfidenceField,  unit or)
            confidence = g.get("confidence", g.get("unit", "heuristic"))

            lines.append("| {} | {} | {} | {} | {} | {} |".format(
                dim, current_val, target_val, passed, confidence, trend_parts))
        lines.append("")

    # --- Strategy This Round ---
    if iterations:
        last_it = iterations[-1]
        strategy = last_it.get("strategy") or {}
        sid = strategy.get("strategy_id", "—")
        desc = strategy.get("description") or strategy.get("name", "")
        lines += [
            "### Strategy This Round",
            "- strategy_id: {} — {}".format(sid, desc),
        ]
        # reflect Medium effect
        reflect = last_it.get("reflect") or {}
        effect = reflect.get("effect") or reflect.get("strategy_review", {}).get("verdict", "")
        if effect:
            lines.append("- effect: {}".format(effect))
        lines.append("")

    # --- Open Issues (Top 5) ---
    problems = findings.get("problem_tracker") or []
    open_problems = [p for p in problems if (p.get("status") or "").lower() in ("open", "In Progress", "")]
    if open_problems:
        lines.append("### Open Issues (Top 5)")
        for i, p in enumerate(open_problems[:5], 1):
            lines.append("{}. [{}] {}".format(
                i, p.get("id", "?"), p.get("description", "")))
        lines.append("")
    else:
        lines += ["### Open Issues", "None", ""]

    # --- Lessons Learned (round reflect Mediumextract) ---
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
        lines.append("### Lessons Learned")
        if effective:
            lines.append("- Effective: {}".format("; ".join(effective[:3])))
        if avoid:
            lines.append("- Avoid: {}".format("; ".join(avoid[:3])))
        lines.append("")

    # --- Resources ---
    completion_authority = meta.get("completion_authority", "internal")
    lines += [
        "### Resources",
        "- {}".format(budget_line),
        "- Completion Authority: {}".format(completion_authority),
    ]

    output = "\n".join(lines)
    print(output)
    return output


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    work_dir = sys.argv[1]

    # Check the panorama subcommand
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
                print("ERROR: unknown file type: {}".format(target))
                print("Options: {}".format(", ".join(RENDERERS.keys())))
                sys.exit(1)

    if target:
        path = RENDERERS[target](state, work_dir)
        print("OK: Rendered {}".format(path))
    else:
        for name, renderer in RENDERERS.items():
            path = renderer(state, work_dir)
            print("OK: Rendered {}".format(path))

    print("Completed: generated readable files from autoloop-state.json")


if __name__ == "__main__":
    main()
