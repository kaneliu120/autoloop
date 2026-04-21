#!/usr/bin/env python3
"""AutoLoop SSOT single source of truth manager

Usage:
  autoloop-state.py init <Work Directory> <Template> <Target>
  autoloop-state.py update <Work Directory> <field path> <Value>
  autoloop-state.py query <Work Directory> <query expression>
  autoloop-state.py add-iteration <Work Directory>
  autoloop-state.py add-finding <Work Directory> <JSON>
  autoloop-state.py add-tsv-row <Work Directory> <JSON>
  autoloop-state.py migrate <Work Directory> [--dry-run]

Data source file: <Work Directory>/autoloop-state.json
"""

import datetime
import importlib.util
import json
import os
import re
import sys


STATE_FILE = "autoloop-state.json"
PROTOCOL_VERSION = "1.0.0"

TSV_COLUMNS = [
    "iteration", "phase", "status", "dimension", "metric_value", "delta",
    "strategy_id", "action_summary", "side_effect", "evidence_ref",
    "unit_id", "protocol_version", "score_variance", "confidence", "details"
]

PHASES = ["OBSERVE", "ORIENT", "DECIDE", "ACT", "VERIFY", "SYNTHESIZE", "EVOLVE", "REFLECT"]


def now_iso():
    return datetime.datetime.now().isoformat(timespec="seconds")


def task_id_now():
    return "autoloop-{}".format(datetime.datetime.now().strftime("%Y%m%d-%H%M%S"))


def validate_phase_transition(current, target):
    """Validate whether a phase transition is legal(see loop-protocol.md §phase transition constraints)"""
    if current not in PHASES or target not in PHASES:
        return False, "unknown phase: {} → {}".format(current, target)
    ci, ti = PHASES.index(current), PHASES.index(target)
    if ti == ci + 1:
        return True, ""
    if target == "OBSERVE" and current == "REFLECT":
        return True, "enter the next round"
    return False, "illegal transition: {} → {}(must advance in order)".format(current, target)


def initial_state(template, goal, work_dir):
    """Create the initial SSOT JSON structure covering all plan/progress/findings/results.tsv data"""
    now = now_iso()
    tid = task_id_now()

    return {
        "plan": {
            "task_id": tid,
            "template": template,
            "goal": goal,
            "detailed_background": "",
            "success_criteria": [],
            "status": "Ready to Start",
            "work_dir": work_dir,
            "plan_version": "1.0",
            "dimensions": [],
            "gates": [],
            "budget": {
                "max_rounds": 0,
                "current_round": 0,
                "time_limit": "Unlimited",
                "exhaustion_strategy": "Output Best Current Result"
            },
            "scope": {
                "includes": [],
                "excludes": [],
                "extensions": []
            },
            "template_params": {},
            "template_mode": "ooda_rounds",
            "linear_delivery_complete": False,
            "output_files": {
                "plan": {"path": "autoloop-plan.md", "status": "Created"},
                "progress": {"path": "autoloop-progress.md", "status": "Pending"},
                "findings": {"path": "autoloop-findings.md", "status": "Pending"},
                "results_tsv": {"path": "autoloop-results.tsv", "status": "Pending"}
            },
            "strategy_history": [],
            "decide_act_handoff": None,
            "change_log": [
                {"time": now, "field": "Initial Creation", "before": "", "after": "", "reason": ""}
            ]
        },
        "iterations": [],
        "findings": {
            "executive_summary": {
                "topic": "TBD",
                "total_rounds": 0,
                "final_scores": {},
                "top_conclusions": []
            },
            "rounds": [],
            "engineering_issues": {
                "security": [],
                "reliability": [],
                "maintainability": [],
                "architecture": [],
                "performance": [],
                "stability": []
            },
            "fix_records": [],
            "disputes": [],
            "info_gaps": [],
            "expansion_directions": [],
            "sources": {"high": [], "medium": [], "low": []},
            "problem_tracker": [],
            "strategy_evaluations": [],
            "pattern_recognition": {
                "recurring_problems": [],
                "diminishing_returns": [],
                "cross_dimension": [],
                "bottlenecks": []
            },
            "lessons_learned": {
                "verified_hypotheses": [],
                "generalizable_methods": [],
                "process_improvements": []
            }
        },
        "experience": [],
        "results_tsv": [],
        "metadata": {
            "protocol_version": PROTOCOL_VERSION,
            "created_at": now,
            "updated_at": now,
            "ssot_version": "1.0.0"
        }
    }


def load_state(work_dir):
    """Load state.json and exit with an error if it does not exist"""
    path = os.path.join(work_dir, STATE_FILE)
    if not os.path.exists(path):
        print("ERROR: data source file does not exist: {}".format(path))
        print("Hint: run autoloop-state.py init <Work Directory> <Template> <Target> first")
        sys.exit(1)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_state(work_dir, state):
    """Save state.json and automatically update updated_at"""
    state["metadata"]["updated_at"] = now_iso()
    path = os.path.join(work_dir, STATE_FILE)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    return path


# --- Field Path Parsing ---

def _parse_path_segment(segment):
    """Parse a path segment, supporting key[N] array indexing"""
    m = re.match(r"^(\w+)\[(-?\d+)\]$", segment)
    if m:
        return m.group(1), int(m.group(2))
    return segment, None


def resolve_path(obj, path_str):
    """
    Traverse nested dict/list values by dot path and return (parent, key, value).

    Supported syntax:
      plan.goal                     -> state["plan"]["goal"]
      iterations[-1].scores         -> state["iterations"][-1]["scores"]
      findings.rounds[0].findings   -> state["findings"]["rounds"][0]["findings"]
    """
    segments = path_str.split(".")
    current = obj
    parent = None
    last_key = None

    for seg in segments:
        parent = current
        key, idx = _parse_path_segment(seg)

        if isinstance(current, dict):
            if key not in current:
                return None, None, None
            current = current[key]
        elif isinstance(current, list):
            try:
                current = current[int(key)]
            except (ValueError, IndexError):
                return None, None, None
        else:
            return None, None, None

        last_key = key

        if idx is not None:
            parent = current
            last_key = idx
            try:
                current = current[idx]
            except (IndexError, TypeError):
                return None, None, None

    return parent, last_key, current


def set_by_path(obj, path_str, value):
    """Set a value by dot path and auto-create missing intermediate dict keys"""
    segments = path_str.split(".")
    current = obj

    for seg in segments[:-1]:
        key, idx = _parse_path_segment(seg)
        if isinstance(current, dict):
            if key not in current:
                current[key] = {}
            current = current[key]
        elif isinstance(current, list):
            current = current[int(key)]
        if idx is not None:
            current = current[idx]

    last_seg = segments[-1]
    key, idx = _parse_path_segment(last_seg)

    if idx is not None:
        if isinstance(current, dict) and key not in current:
            current[key] = {}
        current[key][idx] = value
    elif isinstance(current, dict):
        current[key] = value
    elif isinstance(current, list):
        current[int(key)] = value


def _auto_convert(value_str):
    """Try converting a string to an appropriate Python type"""
    if value_str.lower() in ("true", "false"):
        return value_str.lower() == "true"
    try:
        return int(value_str)
    except ValueError:
        pass
    try:
        return float(value_str)
    except ValueError:
        pass
    if value_str.startswith(("{", "[")):
        try:
            return json.loads(value_str)
        except json.JSONDecodeError:
            pass
    return value_str


# --- Subcommand implementation ---

def _load_plan_gates_for_template(template):
    """ autoloop-score and scorer  plan.gates(AvoidDimension)."""
    score_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "autoloop-score.py")
    spec = importlib.util.spec_from_file_location("al_score_ssot", score_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.plan_gates_for_ssot_init(template)


def cmd_init(work_dir, template, goal):
    """Initialize autoloop-state.json"""
    if not os.path.isdir(work_dir):
        print("ERROR: directory does not exist: {}".format(work_dir))
        return False

    path = os.path.join(work_dir, STATE_FILE)
    if os.path.exists(path):
        print("WARNING: data source already exists: {}".format(path))
        print("Delete this file first if you need to reinitialize.")
        return False

    state = initial_state(template, goal, work_dir)
    gates = _load_plan_gates_for_template(template)
    state["plan"]["gates"] = gates
    # T1/T2/T3: plan.dimensions = research scope, filled by user/controller later.
    # T4-T8: derive from gate dims (scoring reads from iterations[-1].scores).
    _RESEARCH_SCOPE_TEMPLATES = {"T1", "T2", "T3"}
    template_key = template.upper().split()[0] if template else ""
    if template_key in _RESEARCH_SCOPE_TEMPLATES:
        state["plan"]["dimensions"] = []
    else:
        state["plan"]["dimensions"] = [
            g.get("manifest_dimension") or g.get("dimension") or g.get("dim", "")
            for g in gates
            if g.get("manifest_dimension") or g.get("dimension") or g.get("dim")
        ]
    # Read default template rounds from gate-manifest.json
    if state["plan"]["budget"]["max_rounds"] <= 0:
        manifest_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..", "references", "gate-manifest.json"
        )
        try:
            with open(manifest_path, "r", encoding="utf-8") as mf:
                manifest = json.load(mf)
            default_rounds = manifest.get("default_rounds", {}).get(template, 3)
            state["plan"]["budget"]["max_rounds"] = default_rounds
        except (OSError, json.JSONDecodeError):
            state["plan"]["budget"]["max_rounds"] = 3  # fallback
    saved = save_state(work_dir, state)
    print("OK: SSOT data source created: {}".format(saved))
    print("  Task ID: {}".format(state["plan"]["task_id"]))
    print("  Template: {}".format(template))
    print("  Target: {}".format(goal))
    return True


PROTECTED_PATH_PATTERNS = [
    re.compile(r"^plan\.gates\[\d+\]\.threshold$"),
    re.compile(r"^plan\.budget\.max_rounds$"),
]


def cmd_update(work_dir, field_path, value_str):
    """Update a specific field in the data source"""
    for pat in PROTECTED_PATH_PATTERNS:
        if pat.match(field_path):
            print("WARNING: Cannot update protected path '{}' via update command.".format(field_path))
            print("Gate thresholds can only be modified by editing gate-manifest.json directly (leaves git audit trail).")
            sys.exit(1)

    state = load_state(work_dir)

    parent, key, old_value = resolve_path(state, field_path)
    if parent is None:
        # The leaf key may not exist yet — check that the parent path resolves
        # to an existing dict before allowing auto-creation of the new key.
        parent_path = ".".join(field_path.split(".")[:-1])
        if parent_path:
            pp, pk, parent_val = resolve_path(state, parent_path)
            if pp is None or not isinstance(parent_val, dict):
                print("ERROR: field path does not exist: {}".format(field_path))
                print("Hint: use the query command to inspect the current structure")
                sys.exit(1)
        else:
            # Single-segment path with no parent — root must be a dict
            if not isinstance(state, dict):
                print("ERROR: field path does not exist: {}".format(field_path))
                sys.exit(1)
        # Parent exists as a dict; new key will be auto-created by set_by_path
        old_value = None

    new_value = _auto_convert(value_str)

    if field_path.endswith("phase"):
        if isinstance(old_value, str) and isinstance(new_value, str):
            ok, msg = validate_phase_transition(old_value, new_value)
            if not ok:
                print("ERROR: phase transition validation failed: {}".format(msg))
                sys.exit(1)
            if msg:
                print("INFO: {}".format(msg))

    set_by_path(state, field_path, new_value)

    state["plan"]["change_log"].append({
        "time": now_iso(),
        "field": field_path,
        "before": str(old_value) if old_value is not None else "",
        "after": str(new_value),
        "reason": "autoloop-state update"
    })

    save_state(work_dir, state)
    print("OK: {}".format(field_path))
    print("  Old Value: {}".format(old_value))
    print("  New Value: {}".format(new_value))

    return True


def cmd_query(work_dir, query_expr):
    """Query data source fields"""
    state = load_state(work_dir)

    if query_expr == "summary":
        plan = state["plan"]
        meta = state["metadata"]
        n_iter = len(state["iterations"])
        n_findings = sum(
            len(r.get("findings", []))
            for r in state["findings"]["rounds"]
        )
        n_tsv = len(state["results_tsv"])
        print("Task ID: {}".format(plan["task_id"]))
        print("Template: {}".format(plan["template"]))
        print("Status: {}".format(plan["status"]))
        print("Target: {}".format(plan["goal"]))
        print("Iteration Count: {}".format(n_iter))
        print("Total Findings: {}".format(n_findings))
        print("TSV Row Count: {}".format(n_tsv))
        print("Protocol Version: {}".format(meta["protocol_version"]))
        print("Created At: {}".format(meta["created_at"]))
        print("Updated At: {}".format(meta["updated_at"]))
        return True

    if query_expr == "dimensions":
        gates = state["plan"].get("gates", [])
        if not gates:
            print("No quality gate dimensions configured")
            return True
        for g in gates:
            dim_label = g.get("dimension", g.get("dim", "?"))
            print("  {}: Current={} Target={} Status={}".format(
                dim_label,
                g.get("current", "—"),
                g.get("target", "—"),
                g.get("status", "—")
            ))
        return True

    _, _, value = resolve_path(state, query_expr)
    if value is None:
        print("Not Found: {}".format(query_expr))
        return False

    if isinstance(value, (dict, list)):
        print(json.dumps(value, ensure_ascii=False, indent=2))
    else:
        print(value)
    return True


def cmd_add_iteration(work_dir):
    """Add a new round iteration record"""
    state = load_state(work_dir)

    round_num = len(state["iterations"]) + 1
    now = now_iso()

    prev_scores = {}
    if state["iterations"]:
        prev_scores = dict(state["iterations"][-1].get("scores", {}))

    iteration = {
        "round": round_num,
        "start_time": now,
        "end_time": "",
        "status": "In Progress",
        "phase": "OBSERVE",
        "scores": prev_scores,
        "strategy": {
            "strategy_id": "",
            "name": "",
            "description": "",
            "target_dimension": ""
        },
        "observe": {
            "gaps": [],
            "budget_remaining_pct": 0,
            "focus": "",
            "carryover": ""
        },
        "orient": {
            "gap_cause": "",
            "strategy": "",
            "scope_adjustment": "None",
            "expected_improvement": ""
        },
        "decide": {
            "actions": []
        },
        "act": {
            "records": [],
            "failures": []
        },
        "verify": {
            "score_updates": [],
            "verification_method": "",
            "new_issues": []
        },
        "synthesize": {
            "contradictions_found": [],
            "contradictions_resolved": [],
            "merged_data": [],
            "new_insights": []
        },
        "evolve": {
            "termination": "Continue",
            "next_focus": "",
            "strategy_adjustment": "None",
            "scope_change": "None"
        },
        "reflect": {
            "problem_registry": {"new": 0, "fixed": 0, "remaining": 0},
            "strategy_review": {"rating": 0, "verdict": "To Validate", "reason": ""},
            "pattern_recognition": "",
            "lesson_learned": "",
            "next_round_guidance": ""
        },
        "findings": [],
        "evolution_decisions": [],
        "tsv_rows": []
    }

    state["iterations"].append(iteration)
    state["plan"]["budget"]["current_round"] = round_num
    state["plan"]["status"] = "In Progress"

    save_state(work_dir, state)
    print("OK: Added round {} iteration".format(round_num))
    print("  Status: In Progress")
    print("  Phase: OBSERVE")
    return True


def cmd_add_finding(work_dir, finding_json):
    """Add a finding to the current round."""
    state = load_state(work_dir)

    if not state["iterations"]:
        print("ERROR: No iteration exists yet; run add-iteration first")
        sys.exit(1)

    try:
        finding = json.loads(finding_json)
    except json.JSONDecodeError as e:
        print("ERROR: JSON parse failed: {}".format(e))
        print(
            "Example: autoloop-state.py add-finding /path "
            '\'{"dimension": "coverage", "content": "analysis content...", '
            '"source": "https://example.com", "confidence": "High"}\''
        )
        sys.exit(1)

    if "dimension" not in finding:
        print("ERROR: Missing required field: dimension")
        print(
            "Example: autoloop-state.py add-finding /path "
            '\'{"dimension": "coverage", "content": "analysis content...", '
            '"source": "https://example.com", "confidence": "High"}\''
        )
        sys.exit(1)
    body_keys = ("summary", "description", "content")
    if not any(
        finding.get(k) not in (None, "")
        for k in body_keys
    ):
        print("ERROR: Missing body field: provide summary, description, or content")
        print(
            "Example: autoloop-state.py add-finding /path "
            '\'{"dimension": "coverage", "content": "analysis content...", '
            '"source": "https://example.com", "confidence": "High"}\''
        )
        sys.exit(1)
    if not finding.get("content"):
        for k in ("summary", "description"):
            v = finding.get(k)
            if v not in (None, ""):
                finding["content"] = v
                break

    finding.setdefault("source", "")
    finding.setdefault("confidence", "Medium")
    finding.setdefault("type", "finding")
    finding.setdefault("time", now_iso())
    finding.setdefault("round", len(state["iterations"]))

    if state["iterations"]:
        state["iterations"][-1]["findings"].append(finding)

    round_num = finding["round"]
    while len(state["findings"]["rounds"]) < round_num:
        state["findings"]["rounds"].append({
            "round": len(state["findings"]["rounds"]) + 1,
            "time": now_iso(),
            "findings": [],
            "contradictions": []
        })

    if 0 < round_num <= len(state["findings"]["rounds"]):
        state["findings"]["rounds"][round_num - 1]["findings"].append(finding)

    save_state(work_dir, state)
    preview = (
        finding.get("content")
        or finding.get("summary")
        or finding.get("description")
        or ""
    )
    print("OK: Added finding (Round {}, Dimension: {})".format(
        round_num, finding["dimension"]))
    print("  Content: {}...".format(str(preview)[:80]))
    return True


def _tsv_row_variance_fail_closed(row):
    """Fail-closed aligned with autoloop-variance check (variance≥2 or 0<Confidence<50)."""
    sv = str(row.get("score_variance", "0")).strip()
    conf = str(row.get("confidence", "100")).replace("%", "").strip()
    try:
        var = float(sv) if sv and sv != "—" else 0.0
    except ValueError:
        return True, "score_variance non-numeric"
    try:
        c = float(conf) if conf and conf != "—" else 100.0
    except ValueError:
        return True, "confidence non-numeric"
    if var >= 2.0:
        return True, "score_variance≥2.0"
    if c < 50 and c != 0:
        return True, "confidence<50%"
    return False, ""


def cmd_add_tsv_row(work_dir, row_json):
    """Add a TSV row record"""
    state = load_state(work_dir)

    try:
        row = json.loads(row_json)
    except json.JSONDecodeError as e:
        print("ERROR: JSON parse failed: {}".format(e))
        sys.exit(1)

    for col in TSV_COLUMNS:
        row.setdefault(col, "—")

    fc, reason = _tsv_row_variance_fail_closed(row)
    if fc:
        print("ERROR: TSV row failed variance/confidence validation: {}".format(reason))
        print("  Fix score_variance / confidence and retry (see autoloop-variance.py check)")
        sys.exit(1)

    row.setdefault("protocol_version", PROTOCOL_VERSION)
    state["results_tsv"].append(row)

    if state["iterations"]:
        state["iterations"][-1]["tsv_rows"].append(row)

    save_state(work_dir, state)
    print("OK: Added TSV row (iteration={}, dimension={})".format(
        row.get("iteration", "—"), row.get("dimension", "—")))
    return True


# --- Main Entry ---

USAGE = """Usage:
  autoloop-state.py init <Work Directory> <Template> <Target>
  autoloop-state.py update <Work Directory> <field path> <Value>
  autoloop-state.py query <Work Directory> <query expression>
  autoloop-state.py add-iteration <Work Directory>
  autoloop-state.py add-finding <Work Directory> '<JSON>'
  autoloop-state.py add-tsv-row <Work Directory> '<JSON>'
  autoloop-state.py migrate <Work Directory> --dry-run

Query Example:
  autoloop-state.py query /path summary
  autoloop-state.py query /path dimensions
  autoloop-state.py query /path plan.goal
  autoloop-state.py query /path iterations[-1].scores
  autoloop-state.py query /path metadata.protocol_version

Update Example:
  autoloop-state.py update /path plan.status In Progress
  autoloop-state.py update /path plan.budget.max_rounds 7
  autoloop-state.py update /path iterations[-1].phase ORIENT

Migration Example:
  autoloop-state.py migrate /path --dry-run   # print a preview diff between current plan.gates and the SSOT suggestion
"""


def cmd_migrate(work_dir, dry_run):
    """Compare plan.gates with the gate-manifest initialization recommendation (no automatic write-back)."""
    import importlib.util

    state = load_state(work_dir)
    tmpl = state.get("plan", {}).get("template", "T1")
    scripts_dir = os.path.dirname(os.path.abspath(__file__))
    score_path = os.path.join(scripts_dir, "autoloop-score.py")
    spec = importlib.util.spec_from_file_location("al_score_migrate", score_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    proposed = mod.plan_gates_for_ssot_init(tmpl)
    current = state.get("plan", {}).get("gates", [])

    print("Template: {}".format(tmpl))
    print("Current plan.gates count: {}".format(len(current)))
    print("SSOT recommended gate count: {}".format(len(proposed)))
    if dry_run:
        print("\n--- Suggested plan.gates (preview; full JSON below)---")
        print(json.dumps(proposed, ensure_ascii=False, indent=2))
        print(
            "\n(dry-run)No files were modified. Merge manually or re-run init to align them;"
            "See references/loop-data-schema.md §migration"
        )
    return True


def main():
    if len(sys.argv) < 2:
        print(USAGE)
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "init":
        if len(sys.argv) < 5:
            print("Usage: autoloop-state.py init <Work Directory> <Template> <Target>")
            sys.exit(1)
        ok = cmd_init(sys.argv[2], sys.argv[3], sys.argv[4])
        sys.exit(0 if ok else 1)

    elif cmd == "update":
        if len(sys.argv) < 5:
            print("Usage: autoloop-state.py update <Work Directory> <field path> <Value>")
            sys.exit(1)
        ok = cmd_update(sys.argv[2], sys.argv[3], sys.argv[4])
        sys.exit(0 if ok else 1)

    elif cmd == "query":
        if len(sys.argv) < 4:
            print("Usage: autoloop-state.py query <Work Directory> <query expression>")
            sys.exit(1)
        ok = cmd_query(sys.argv[2], sys.argv[3])
        sys.exit(0 if ok else 1)

    elif cmd == "add-iteration":
        if len(sys.argv) < 3:
            print("Usage: autoloop-state.py add-iteration <Work Directory>")
            sys.exit(1)
        ok = cmd_add_iteration(sys.argv[2])
        sys.exit(0 if ok else 1)

    elif cmd == "add-finding":
        if len(sys.argv) < 4:
            print("Usage: autoloop-state.py add-finding <Work Directory> '<JSON>'")
            sys.exit(1)
        ok = cmd_add_finding(sys.argv[2], sys.argv[3])
        sys.exit(0 if ok else 1)

    elif cmd == "add-tsv-row":
        if len(sys.argv) < 4:
            print("Usage: autoloop-state.py add-tsv-row <Work Directory> '<JSON>'")
            sys.exit(1)
        ok = cmd_add_tsv_row(sys.argv[2], sys.argv[3])
        sys.exit(0 if ok else 1)

    elif cmd == "migrate":
        if len(sys.argv) < 3:
            print("Usage: autoloop-state.py migrate <Work Directory> [--dry-run]")
            sys.exit(1)
        dry = "--dry-run" in sys.argv
        ok = cmd_migrate(sys.argv[2], dry)
        sys.exit(0 if ok else 1)

    else:
        print("unknown command: {}".format(cmd))
        print(USAGE)
        sys.exit(1)


if __name__ == "__main__":
    main()
