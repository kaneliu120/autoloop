#!/usr/bin/env python3
"""AutoLoop bootstrap initializer — creates 4 working files (plan/findings/progress/results.tsv)

Usage:
  autoloop-init.py <Work Directory> [Template] [Target]
  autoloop-init.py <Work Directory> 'T1: Research' 'research AI autonomous iteration tools'
  autoloop-init.py <Work Directory> 'T6: Quality' 'code quality review' --ssot
"""

import subprocess
import sys
import os
import datetime

TSV_HEADER = "iteration\tphase\tstatus\tdimension\tmetric_value\tdelta\tstrategy_id\taction_summary\tside_effect\tevidence_ref\tunit_id\tprotocol_version\tscore_variance\tconfidence\tdetails"

# ---------------------------------------------------------------------------
# T1-T7 quality gate dimension definitions — loaded from gate-manifest.json (SSOT)
# ---------------------------------------------------------------------------

import json


def _load_gate_manifest():
    """Load gate definitions from canonical manifest (SSOT)."""
    manifest_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "references", "gate-manifest.json")
    with open(manifest_path, "r", encoding="utf-8") as f:
        return json.load(f)


# manifest dimension → English label
_MANIFEST_LABEL_MAP = {
    "coverage": "Coverage",
    "credibility": "Credibility",
    "consistency": "Consistency",
    "completeness": "Completeness",
    "bias_check": "Bias Check",
    "sensitivity": "Sensitivity Analysis",
    "kpi_target": "KPI Target Met",
    "pass_rate": "Pass Rate",
    "avg_score": "Average Score",
    "syntax_errors": "Syntax Validation",
    "p1_p2_issues": "P1/P2 Issues",
    "service_health": "Service Health",
    "user_acceptance": "Manual Acceptance",
    "security": "Security",
    "reliability": "Reliability",
    "maintainability": "Maintainability",
    "p1_count": "P1 Issues",
    "security_p2": "Security P2 Issues",
    "reliability_p2": "Reliability P2 Issues",
    "maintainability_p2": "Maintainability P2 Issues",
    "architecture": "Architecture",
    "performance": "Performance",
    "stability": "Stability",
}


def _format_threshold(gate):
    """Convert manifest gate to human-readable threshold string."""
    threshold = gate["threshold"]
    unit = gate["unit"]
    comparator = gate.get("comparator", ">=")

    if threshold is None:
        return "Set by the user in plan"
    if unit == "bool":
        return "True" if threshold else "False"
    if unit == "%":
        if comparator == ">=":
            return f"≥ {threshold}%"
        elif comparator == "==":
            return f"{threshold}%"
        elif comparator == "<=":
            return f"≤ {threshold}%"
        return f"{threshold}%"
    if unit == "/10":
        if comparator == ">=":
            return f"≥ {threshold}/10"
        return f"{threshold}/10"
    if unit == "count":
        if comparator == "==" and threshold == 0:
            return "= 0"
        elif comparator == "<=":
            return f"≤ {threshold}"
        return f"{threshold}"
    return str(threshold)


def _manifest_to_init_gates(manifest):
    """Convert manifest templates to init's internal TEMPLATE_GATES format.

    Returns dict: {"T1": [("Coverage", "≥ 85%", "Hard"), ...], ...}
    """
    result = {}
    for tkey, tdef in manifest["templates"].items():
        gates = []
        for g in tdef["gates"]:
            dim_raw = g["dimension"]
            label = _MANIFEST_LABEL_MAP.get(dim_raw, dim_raw)
            threshold_str = _format_threshold(g)
            gate_type = g["type"].capitalize()  # hard → Hard
            gates.append((label, threshold_str, gate_type))
        result[tkey] = gates
    return result


_MANIFEST = _load_gate_manifest()
TEMPLATE_GATES = _manifest_to_init_gates(_MANIFEST)

# ---------------------------------------------------------------------------
# Asset template paths
# ---------------------------------------------------------------------------

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.normpath(os.path.join(SCRIPT_DIR, "..", "assets"))


def _read_asset(filename):
    """read assets/ template file and return None if it does not exist."""
    path = os.path.join(ASSETS_DIR, filename)
    if os.path.isfile(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return None


def _parse_template_key(template):
    """Extract the T{N} key from the template string, e.g. 'T6: Quality' -> 'T6'."""
    t = template.strip().upper().split(":")[0].split(" ")[0]
    if t.startswith("T") and len(t) >= 2 and t[1:].isdigit():
        return t
    return None


def _build_gate_table(template):
    """Generate quality gate table content from the template."""
    key = _parse_template_key(template)
    gates = TEMPLATE_GATES.get(key, []) if key else []

    if not gates:
        return "| — | — | 0 | — | Ready to Start |"

    rows = []
    for dim, threshold, gate_type in gates:
        rows.append(f"| {dim} | {threshold} | 0 | {gate_type} | Ready to Start |")
    return "\n".join(rows)


def create_plan(work_dir, task_id, template, goal):
    path = os.path.join(work_dir, "autoloop-plan.md")
    now = datetime.datetime.now().isoformat()
    gate_rows = _build_gate_table(template)

    content = f"""# AutoLoop Task Plan

## Metadata

| Field | Value |
|------|-----|
| Task ID | {task_id} |
| Template | {template} |
| Status | Ready to Start |
| Created At | {now} |
| Last Updated | {now} |
| Work Directory | {work_dir} |
| Plan Version | 1.0 |

---

## Goal Description

**One-line Goal**: {goal}

---

## Quality Gates

| Dimension | Target Threshold | Current Score | Gate Type | Status |
|------|---------|---------|---------|------|
{gate_rows}

---

## Iteration Budget

| Field | Value |
|------|-----|
| Max Rounds | See references/parameters.md |
| current round | 0 |
| Budget Exhaustion Strategy | Output Best Current Result |

---

## Strategy History

| Round | strategy_id | Dimension | Strategy | Result | Deprecation Reason |
|------|-------------|------|------|------|---------|
| — | — | — | — | — | — |
"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path


def create_findings(work_dir, task_id, template):
    """Create the findings file using the 4-layer skeleton from assets/findings-template.md."""
    path = os.path.join(work_dir, "autoloop-findings.md")
    now = datetime.datetime.now().isoformat()

    asset = _read_asset("findings-template.md")
    if asset:
        # Replace template placeholders with actual values
        content = asset
        content = content.replace("autoloop-{YYYYMMDD-HHMMSS}", task_id)
        content = content.replace("T{N}: {Name}", template)
        content = content.replace("{ISO 8601}", now)
        # TBD
        content = content.replace("{Topic}", "TBD")
        content = content.replace("{N}", "In Progress")
    else:
        # Fallback: inline minimal skeleton
        content = f"""# AutoLoop Findings — Findings Log

**Task ID**: {task_id}
**Template**: {template}
**Created At**: {now}
**Last Updated**: {now}

---

## Executive Summary

**Research/Analysis Topic**: TBD
**Total Rounds**: In Progress
**Final Quality Score**: TBD

**Key Conclusions (Top 5)**: 
1. TBD
2. TBD
3. TBD
4. TBD
5. TBD

---

## Issue List (REFLECT Layer 1 - Cumulative Tracking)

| Round | Issue Description | Source | Severity | Status | Root Cause Analysis |
|------|---------|------|--------|------|---------|
| — | — | — | — | — | — |

## Strategy Evaluation (REFLECT Layer 2 - Strategy Effect Knowledge Base)

| Round | strategy_id | Strategy | Effect Rating (1-5) | Score Delta | Keep/Avoid/To Validate | Reason |
|------|-------------|------|--------------|---------|-----------------|------|
| — | — | — | — | — | — | — |

## Pattern Recognition (REFLECT Layer 3 - Cross-round Trends)

### Recurring Issues
- To Record

### Diminishing-return Signals
- To Record

### Cross-dimension Links
- To Record

### Bottlenecks
- To Record

## Lessons Learned (REFLECT Layer 4 - Reusable Insights)

### Validated Hypotheses
- To Record

### Generalizable Methodology
- To Record

### Improvements for the AutoLoop process itself
- To Record
"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path


def create_progress(work_dir, task_id, template):
    """Create the progress file using the 8-phase loop skeleton from assets/progress-template.md."""
    path = os.path.join(work_dir, "autoloop-progress.md")

    asset = _read_asset("progress-template.md")
    if asset:
        now = datetime.datetime.now().isoformat()
        content = asset
        content = content.replace("autoloop-{YYYYMMDD-HHMMSS}", task_id)
        content = content.replace("T{N}: {Name}", template)
        content = content.replace("{ISO 8601}", now)

        # Fill quality gate overview rows
        key = _parse_template_key(template)
        gates = TEMPLATE_GATES.get(key, []) if key else []
        if gates:
            # Replace placeholder dimension rows in the template
            gate_rows = []
            for dim, threshold, _ in gates:
                gate_rows.append(f"| {dim} | — | — | — | — | ≥{threshold.lstrip('≥').strip()} |")
            gate_block = "\n".join(gate_rows)
            # Replace {Dimension N} placeholder rows in the template
            import re
            content = re.sub(
                r'\| \{Dimension \d+\} \| — \| — \| — \| — \| ≥\{threshold\} \|\n?',
                '',
                content,
            )
            # Insert actual dimensions after the quality gate overview header separator
            sep_marker = "|------|------|-------|-------|-------|------|\n"
            if sep_marker in content:
                content = content.replace(sep_marker, sep_marker + gate_block + "\n")
    else:
        # Fallback: inline minimal skeleton
        key = _parse_template_key(template)
        gates = TEMPLATE_GATES.get(key, []) if key else []
        if gates:
            gate_rows = []
            for dim, threshold, _ in gates:
                gate_rows.append(f"| {dim} | 0 | — | — | — | ≥{threshold.lstrip('≥').strip()} |")
            gate_block = "\n".join(gate_rows)
        else:
            gate_block = "| — | 0 | — | — | — | — |"

        content = f"""# AutoLoop Progress — Progress Tracking

**Task ID**: {task_id}
**Template**: {template}

## Quality Gate Overview

| Dimension | Baseline | Round 1 | Round 2 | Round 3 | Target |
|------|------|-------|-------|-------|------|
{gate_block}
"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path


def create_tsv(work_dir):
    path = os.path.join(work_dir, "autoloop-results.tsv")
    with open(path, "w", encoding="utf-8") as f:
        f.write(TSV_HEADER + "\n")
    return path


def bootstrap(work_dir, task_id=None, template="T1: Research", goal="TBD",
              ssot=False):
    if not os.path.isdir(work_dir):
        print(f"ERROR: directory does not exist: {work_dir}")
        return False

    if task_id is None:
        task_id = f"autoloop-{datetime.datetime.now().strftime('%Y%m%d-%H%M%S')}"

    files = []
    files.append(create_plan(work_dir, task_id, template, goal))
    files.append(create_findings(work_dir, task_id, template))
    files.append(create_progress(work_dir, task_id, template))
    files.append(create_tsv(work_dir))

    # --ssot: initialize autoloop-state.json as well
    if ssot:
        state_script = os.path.join(SCRIPT_DIR, "autoloop-state.py")
        if os.path.isfile(state_script):
            result = subprocess.run(
                [sys.executable, state_script, "init", work_dir, template, goal],
                capture_output=True, text=True,
            )
            if result.returncode == 0:
                files.append(os.path.join(work_dir, "autoloop-state.json"))
                print(f"SSOT: {result.stdout.strip()}")
            else:
                error = result.stderr.strip() or result.stdout.strip()
                print(f"WARNING: SSOT initialization failed: {error}")
        else:
            print(f"WARNING: autoloop-state.py does not exist: {state_script}")

    print(f"OK: Bootstrap completed, created {len(files)} files:")
    for f in files:
        print(f"  - {os.path.basename(f)}")
    print(f"\nTask ID: {task_id}")
    print(f"Template: {template}")
    print(f"Work Directory: {work_dir}")
    return True


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    work_dir = sys.argv[1]
    # Filter out flags
    positional = [a for a in sys.argv[2:] if not a.startswith("--")]
    template = positional[0] if len(positional) > 0 else "T1: Research"
    goal = positional[1] if len(positional) > 1 else "TBD"
    ssot = "--ssot" in sys.argv

    ok = bootstrap(work_dir, template=template, goal=goal, ssot=ssot)
    sys.exit(0 if ok else 1)
