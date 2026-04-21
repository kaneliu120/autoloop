#!/usr/bin/env python3
"""AutoLoop main loop controller — automatically drives the 8-phase OODA loop

Usage:
  autoloop-controller.py <work_dir>                         start/resume the loop
  autoloop-controller.py <work_dir> --init --template T{N}  initialize a new task
  autoloop-controller.py <work_dir> --resume                resume from checkpoint
  autoloop-controller.py <work_dir> --status                show current status
  autoloop-controller.py <work_dir> --strict                VERIFY abort later phases on failure (or set AUTOLOOP_STRICT=1)
  autoloop-controller.py <work_dir> --enforce-strategy-history   DECIDE strictly validate strategy_history and handoff before DECIDE (or set AUTOLOOP_ENFORCE_STRATEGY_HISTORY=1)
  autoloop-controller.py <work_dir> --stop-after <PHASE>   run until that phase finishes, write the checkpoint, then exit (for sliced Runner calls; PHASE is OBSERVE…REFLECT)
  autoloop-controller.py <work_dir> --exit-codes           process exit codes: 0 normal/terminated/slice complete, 1 abort, 10 pause (also via AUTOLOOP_EXIT_CODES=1)

Core design:
  - Orchestration script, not a standalone daemon. Deterministic phases run automatically, and LLM phases emit structured prompts.
  - checkpoint.json is updated after each phase and supports resume from interruption.
  - Oscillation/stagnation detection uses thresholds defined in parameters.md.
"""

import datetime
import json
import os
import re
import subprocess
import sys
import textwrap

# ---------------------------------------------------------------------------
# 
# ---------------------------------------------------------------------------

PHASES = ["OBSERVE", "ORIENT", "DECIDE", "ACT", "VERIFY", "SYNTHESIZE", "EVOLVE", "REFLECT"]

STATE_FILE = "autoloop-state.json"
CHECKPOINT_FILE = "checkpoint.json"
EXPERIENCE_REGISTRY = "references/experience-registry.md"

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)
from autoloop_kpi import (  # noqa: E402
    kpi_row_satisfied,
    plan_gate_is_exempt,
    results_tsv_last_row_fail_closed,
)

# Round gate-manifest.json (SSOT), Value
_FALLBACK_ROUNDS = {"T1": 3, "T2": 2, "T4": 5, "T5": 99, "T6": 99, "T7": 99, "T8": 99}

# ---------------------------------------------------------------------------
# Gate —  gate-manifest.json(SSOT)read/Stagnationthreshold
# ---------------------------------------------------------------------------

def _load_gate_manifest():
    """Load gate definitions from canonical manifest (SSOT)."""
    manifest_path = os.path.join(os.path.dirname(__file__), "..", "references", "gate-manifest.json")
    with open(manifest_path, "r", encoding="utf-8") as f:
        return json.load(f)

_MANIFEST = _load_gate_manifest()

# manifest dimension → scorer  dim(and autoloop-score._MANIFEST_DIM_MAP ,  comparator )
_MANIFEST_DIM_TO_INTERNAL = {
    "syntax_errors": "syntax",
    "p1_count": "p1_all",
    "security": "security_score",
    "reliability": "reliability_score",
    "maintainability": "maintainability_score",
}

# Round( manifest , )
DEFAULT_ROUNDS = _MANIFEST.get("default_rounds", _FALLBACK_ROUNDS)

# ();  score/validate .validate , (D-04).
SUBPROCESS_TIMEOUT_DEFAULT = int(os.environ.get("AUTOLOOP_SUBPROCESS_TIMEOUT", "120"))
SUBPROCESS_TIMEOUT_VALIDATE = int(os.environ.get("AUTOLOOP_TIMEOUT_VALIDATE", "300"))


def subprocess_timeout_for(script_name):
    if script_name == "autoloop-validate.py":
        return SUBPROCESS_TIMEOUT_VALIDATE
    return SUBPROCESS_TIMEOUT_DEFAULT

# STRICT: VERIFY (None JSON, validate , check)MediumPhase
def _strict_enabled(cli_strict=False):
    env_on = os.environ.get("AUTOLOOP_STRICT", "").strip().lower() in ("1", "true", "yes")
    return bool(cli_strict or env_on)


def _enforce_strategy_history_enabled(cli_flag=False):
    env_on = os.environ.get("AUTOLOOP_ENFORCE_STRATEGY_HISTORY", "").strip().lower() in (
        "1", "true", "yes",
    )
    return bool(cli_flag or env_on)

# threshold( manifest.oscillation)
OSCILLATION_WINDOW = _MANIFEST["oscillation"]["window"]        # round
OSCILLATION_BAND = _MANIFEST["oscillation"]["band"]            # ±score

# Stagnationthreshold( manifest.stagnation_thresholds Value)
STAGNATION_CONSECUTIVE = _MANIFEST.get("stagnation_consecutive", 2)  #  manifest 
# use T1  3% threshold; Template
STAGNATION_THRESHOLD_PCT = 0.03

def _lookup_manifest_comparator(template_key, dim, manifest_dimension=None):
    """ gate-manifest.json  comparator.

    dim: plan.gates and scorer use; manifest_dimension: manifest  dimension .
    """
    tdef = _MANIFEST.get("templates", {}).get(template_key, {})
    if manifest_dimension:
        for g in tdef.get("gates", []):
            if g["dimension"] == manifest_dimension:
                return g.get("comparator")
    for g in tdef.get("gates", []):
        dr = g["dimension"]
        if dr == dim:
            return g.get("comparator")
        if _MANIFEST_DIM_TO_INTERNAL.get(dr, dr) == dim:
            return g.get("comparator")
    return None


def _get_stagnation_threshold(template_key):
    """TemplategetStagnationthreshold, Returns (value, type).type: 'relative'|'absolute'"""
    stag = _MANIFEST.get("stagnation_thresholds", {}).get(template_key)
    if stag:
        return stag["value"] / 100 if stag["type"] == "relative" else stag["value"], stag["type"]
    return STAGNATION_THRESHOLD_PCT, "relative"

# ANSI 
C_RESET = "\033[0m"
C_BOLD = "\033[1m"
C_GREEN = "\033[32m"
C_YELLOW = "\033[33m"
C_RED = "\033[31m"
C_CYAN = "\033[36m"
C_DIM = "\033[2m"

# ---------------------------------------------------------------------------
# 
# ---------------------------------------------------------------------------

def _append_evolve_progress_md(work_dir, round_num, decision, reasons, gate_details):
    """P-01:  EVOLVE  autoloop-progress.md(and state init Medium output_files.progress )."""
    if os.environ.get("AUTOLOOP_SKIP_PROGRESS_LOG", "").strip().lower() in ("1", "true", "yes"):
        return
    path = os.path.join(work_dir, "autoloop-progress.md")
    lines = [
        "",
        "## EVOLVE — Round {} — {}".format(round_num, now_iso()),
        "",
        "- **Decision**: `{}`".format(decision),
    ]
    if reasons:
        lines.append("- **Reason**:")
        for r in reasons:
            lines.append("  - {}".format(r))
    else:
        lines.append("- **Reason**: (None)")
    lines.append("")
    if gate_details:
        lines.append("| Gate | passed | Current | Target |")
        lines.append("|------|------|------|------|")
        for d in gate_details[:24]:
            lines.append(
                "| {} | {} | {} | {} |".format(
                    d.get("label", d.get("dim", "")),
                    "" if d.get("passed") else "",
                    d.get("current"),
                    d.get("threshold"),
                )
            )
        lines.append("")
    block = "\n".join(lines) + "\n"
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(block)
    except OSError as exc:
        warn("Error writing autoloop-progress.md: {}".format(exc))


def _decide_strategy_preflight(state, hard_checks):
    """P-02: warn on strategy_history entries marked Avoid and block reused handoffs in strict mode."""
    history = state.get("plan", {}).get("strategy_history") or []
    if not isinstance(history, list):
        return
    avoided = set()
    for entry in history:
        if not isinstance(entry, dict):
            continue
        res = str(entry.get("result", ""))
        sid = (entry.get("strategy_id") or "").strip()
        if sid and ("Avoid" in res):
            avoided.add(sid)
    if avoided:
        warn(
            "Strategy history contains Avoid records for strategy_id: "
            + ", ".join(sorted(avoided))
        )
    recent = [h for h in history[-3:] if isinstance(h, dict)]
    sids = [(h.get("strategy_id") or "").strip() for h in recent if h.get("strategy_id")]
    if len(sids) >= 2 and sids[-1] and sids[-1] == sids[-2]:
        warn(
            "The last two rounds reused strategy_id '{}'; loop-protocol recommends varying strategies.".format(
                sids[-1]
            )
        )
    if not hard_checks:
        return
    handoff = state.get("plan", {}).get("decide_act_handoff") or {}
    if isinstance(handoff, dict):
        hsid = (handoff.get("strategy_id") or "").strip()
        if hsid and hsid in avoided:
            error(
                "DECIDE: plan.decide_act_handoff.strategy_id={} is marked Avoid in strategy_history; "
                "update the handoff JSON before continuing.".format(hsid)
            )


def now_iso():
    return datetime.datetime.now().isoformat(timespec="seconds")


def _plan_context_tags_csv(plan):
    """SSOT plan.context_tags: list[str] or;  query --tags."""
    if not isinstance(plan, dict):
        return None
    raw = plan.get("context_tags")
    if raw is None:
        return None
    if isinstance(raw, str):
        s = raw.strip()
        return s if s else None
    if isinstance(raw, list):
        parts = [str(x).strip() for x in raw if str(x).strip()]
        return ",".join(parts) if parts else None
    return None


def banner(round_num, phase, msg=""):
    """Phase"""
    idx = PHASES.index(phase) + 1
    label = f"[Round {round_num}] ({idx}/8) {phase}"
    if msg:
        label += f" — {msg}"
    width = max(len(label) + 4, 60)
    print(f"\n{C_BOLD}{C_CYAN}{'=' * width}")
    print(f"  {label}")
    print(f"{'=' * width}{C_RESET}\n")


def info(msg):
    print(f"{C_GREEN}[INFO]{C_RESET} {msg}")


def warn(msg):
    print(f"{C_YELLOW}[WARN]{C_RESET} {msg}")


def error(msg):
    print(f"{C_RED}[ERROR]{C_RESET} {msg}")


def prompt_block(title, content):
    """ LLM needHint"""
    print(f"\n{C_BOLD}>>> LLM ACTION REQUIRED: {title}{C_RESET}")
    print(f"{C_DIM}{'─' * 60}{C_RESET}")
    print(textwrap.dedent(content).strip())
    print(f"{C_DIM}{'─' * 60}{C_RESET}\n")


# ---------------------------------------------------------------------------
# file I/O
# ---------------------------------------------------------------------------

def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    info(f"Wrote: {path}")


def load_state(work_dir):
    path = os.path.join(work_dir, STATE_FILE)
    if not os.path.exists(path):
        error(f"Statusfiledoes not exist: {path}")
        sys.exit(1)
    return load_json(path)


def load_checkpoint(work_dir):
    path = os.path.join(work_dir, CHECKPOINT_FILE)
    if not os.path.exists(path):
        return None
    return load_json(path)


def save_checkpoint(work_dir, checkpoint):
    checkpoint["timestamp"] = now_iso()
    save_json(os.path.join(work_dir, CHECKPOINT_FILE), checkpoint)


def make_checkpoint(task_id, round_num, phase, last_completed):
    return {
        "task_id": task_id,
        "current_round": round_num,
        "current_phase": phase,
        "last_completed_phase": last_completed,
        "timestamp": now_iso(),
        "evolve_history": [],
        "pause_state": None,
    }


# ---------------------------------------------------------------------------
# Call
# ---------------------------------------------------------------------------

def run_tool(script_name, args, capture=False, env=None, work_dir=None):
    """Call autoloop-*.py .work_dir /write metadata.last_error,  tool_* ."""
    script_path = os.path.join(SCRIPTS_DIR, script_name)
    cmd = [sys.executable, script_path] + [str(a) for a in args]
    argv_audit = [str(a) for a in args]
    info(f"Call: {' '.join(cmd)}")
    run_env = os.environ.copy()
    if env:
        run_env.update(env)
    if work_dir:
        _metadata_append_audit_structured(work_dir, {
            "event": "tool_start",
            "script": script_name,
            "argv": argv_audit,
            "work_dir": work_dir,
        })
    timeout_sec = subprocess_timeout_for(script_name)
    try:
        if capture:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout_sec, env=run_env
            )
            if work_dir:
                _metadata_append_audit_structured(work_dir, {
                    "event": "tool_finish",
                    "script": script_name,
                    "argv": argv_audit,
                    "work_dir": work_dir,
                    "returncode": result.returncode,
                    "timeout": False,
                    "stderr": ((result.stderr or "")[:500]),
                })
            if result.stderr:
                for line in result.stderr.splitlines():
                    stripped = line.strip()
                    if not stripped:
                        continue
                    if stripped.startswith("INFO:"):
                        info(f"  {stripped}")
                    else:
                        warn(f"  stderr: {stripped}")
            if result.returncode != 0:
                warn(f"Tool returned a non-zero exit code: {result.returncode}")
                if work_dir:
                    _metadata_set_last_error(
                        work_dir, script_name, result.returncode, (result.stderr or "")[:2000]
                    )
            return result.stdout, result.returncode
        result = subprocess.run(cmd, timeout=timeout_sec, env=run_env)
        if work_dir:
            _metadata_append_audit_structured(work_dir, {
                "event": "tool_finish",
                "script": script_name,
                "argv": argv_audit,
                "work_dir": work_dir,
                "returncode": result.returncode,
                "timeout": False,
                "stderr": "",
            })
        if work_dir and result.returncode != 0:
            _metadata_set_last_error(work_dir, script_name, result.returncode, "")
        return "", result.returncode
    except subprocess.TimeoutExpired:
        warn(f"Tool timed out ({timeout_sec}s): {script_name}")
        if work_dir:
            _metadata_append_audit_structured(work_dir, {
                "event": "tool_timeout",
                "script": script_name,
                "argv": argv_audit,
                "work_dir": work_dir,
                "returncode": 124,
                "timeout": True,
                "stderr": "",
            })
            _metadata_set_last_error(work_dir, script_name, 124, "subprocess timeout")
        return "", 124


def _record_state_metadata(work_dir, mutator):
    """update autoloop-state.json  metadata()."""
    path = os.path.join(work_dir, STATE_FILE)
    if not os.path.isfile(path):
        return
    try:
        data = load_json(path)
        mutator(data)
        save_json(path, data)
    except (OSError, ValueError, TypeError, KeyError):
        pass


def _metadata_set_last_error(work_dir, script_name, returncode, stderr_snip=""):
    def _m(state):
        meta = state.setdefault("metadata", {})
        meta["last_error"] = {
            "time": now_iso(),
            "script": script_name,
            "returncode": returncode,
            "stderr": (stderr_snip or "")[:500],
        }
    _record_state_metadata(work_dir, _m)


def _metadata_append_audit(work_dir, event, detail=""):
    def _m(state):
        meta = state.setdefault("metadata", {})
        meta.setdefault("audit", []).append({
            "time": now_iso(),
            "event": event,
            "detail": detail,
        })
    _record_state_metadata(work_dir, _m)


def _metadata_append_audit_structured(work_dir, record):
    """ metadata.audit[] itemsrecord; record  \"event\" ."""
    def _m(state):
        meta = state.setdefault("metadata", {})
        row = {"time": now_iso()}
        row.update(record)
        meta.setdefault("audit", []).append(row)
    _record_state_metadata(work_dir, _m)


# ---------------------------------------------------------------------------
# Scores/Gateread
# ---------------------------------------------------------------------------

def get_current_scores(state):
    """ iterations[-1].scores get.

    T5: round add-iteration  scores , ORIENT/Stagnation plan.gates[].current Value kpi (VERIFY  gap and).
    """
    iters = state.get("iterations", [])
    if not iters:
        return {}
    sc = iters[-1].get("scores") or {}
    if sc:
        return sc
    if get_template(state) != "T5":
        return {}
    merged = {}
    for g in get_gates(state):
        dim = g.get("dim") or g.get("dimension", "")
        cur = g.get("current")
        if dim and isinstance(cur, (int, float)):
            merged[dim] = float(cur)
    return merged


def get_gates(state):
    """ plan.gates getGate Definitions"""
    return state.get("plan", {}).get("gates", [])


def get_template(state):
    return state.get("plan", {}).get("template", "T1")


def get_max_rounds(state):
    budget = state.get("plan", {}).get("budget", {})
    max_r = budget.get("max_rounds", 0)
    if max_r > 0:
        return max_r
    tmpl = get_template(state)
    # T6: parameters.md  items×2 Budget,  manifest default_rounds(P-04)
    if tmpl == "T6":
        plan = state.get("plan", {}) or {}
        tp = plan.get("template_params") or {}
        raw_items = plan.get("generation_items", tp.get("items", tp.get("generation_item_count")))
        try:
            n = int(raw_items)
            if n > 0:
                cap = int(DEFAULT_ROUNDS.get("T6", 99))
                return min(max(n * 2, 1), cap)
        except (TypeError, ValueError):
            pass
    # T4 and delivery-phases.md Phase; manifest default_rounds  7
    return DEFAULT_ROUNDS.get(tmpl, 5)


def get_current_round(state):
    budget = state.get("plan", {}).get("budget", {})
    return budget.get("current_round", 0)


def get_score_history(state):
    """Returns [{dim: score, ...}, ...] Round"""
    history = []
    for it in state.get("iterations", []):
        scores = it.get("scores", {})
        if scores:
            history.append(scores)
    return history


# ---------------------------------------------------------------------------
#  & Stagnation
# ---------------------------------------------------------------------------

def detect_oscillation(score_history):
    """ OSCILLATION_WINDOW roundMediumDimension

    (parameters.md §):  3 round ±0.5 
    Returns: [(dim, scores, is_oscillating), ...]
    """
    if len(score_history) < OSCILLATION_WINDOW:
        return []

    recent = score_history[-OSCILLATION_WINDOW:]
    all_dims = set()
    for s in recent:
        all_dims.update(s.keys())

    results = []
    for dim in sorted(all_dims):
        vals = [s.get(dim) for s in recent]
        # Value
        vals = [v for v in vals if v is not None]
        if len(vals) < OSCILLATION_WINDOW:
            continue
        vmin, vmax = min(vals), max(vals)
        in_narrow_band = (vmax - vmin) <= (OSCILLATION_BAND * 2)

        # checkdirection: at leastdirection(→or→)
        # ( 7.0→7.3→7.6)
        direction_changes = 0
        for j in range(2, len(vals)):
            d_prev = vals[j - 1] - vals[j - 2]
            d_curr = vals[j] - vals[j - 1]
            if (d_prev > 0 and d_curr < 0) or (d_prev < 0 and d_curr > 0):
                direction_changes += 1

        is_osc = in_narrow_band and direction_changes >= 1
        if is_osc:
            results.append((dim, vals, True))
    return results


def _confidence_for_dim(dim):
    """DimensionSource, Returns (confidence, margin).

    and autoloop-score.py MediumKeep.
    fileNone import, ——.

    - empirical (margin ≤ 0.3): based on actual tool output
    - heuristic (margin ≤ 1.5): ContentanalysisPattern
    - binary (margin = None): can only determine pass/fail
    """
    # P1-6: Dimension(manifest → )
    dim = _MANIFEST_DIM_TO_INTERNAL.get(dim, dim)
    _EMPIRICAL = {
        "syntax", "p1_p2_issues", "service_health",
        "p1_all", "security_p2", "reliability_p2", "maintainability_p2",
    }
    _BINARY = {"bias_check", "user_acceptance"}
    if dim in _EMPIRICAL:
        return "empirical", 0.3
    if dim in _BINARY:
        return "binary", None
    return "heuristic", 1.5


def detect_stagnation(score_history, gates, template_key=None):
    """StagnationRegression

    Stagnation: Dimension N roundLowTemplatethreshold().
    Regression: Dimension N roundscore.
    T6/T4 .

    Confidence(P1-05): Stagnationthreshold max(threshold, margin).
    - empirical (margin=0.3): threshold
    - heuristic (margin=1.5): threshold margin, Avoid
    - binary (margin=None): direction(improving/declining), Value

    Returns: (results, eligible_dims)
        results: [(dim, recent_scores, signal_type), ...], signal_type  'stagnating' | 'regressing'
        eligible_dims: andStagnation/RegressionDimension(Pass / KPI )
    """
    if template_key in ("T6", "T4"):
        return [], set()

    # " N round < threshold"need N+1 check N 
    # STAGNATION_CONSECUTIVE=2 → need 3 , check 2  R(n-1)→R(n) 
    if len(score_history) < STAGNATION_CONSECUTIVE + 1:
        return [], set()

    threshold, threshold_type = _get_stagnation_threshold(template_key) if template_key else (STAGNATION_THRESHOLD_PCT, "relative")

    window = score_history[-(STAGNATION_CONSECUTIVE + 1):]
    all_dims = set()
    for s in window:
        all_dims.update(s.keys())

    results = []
    eligible_dims = set()
    # Dimension→Gatethreshold, PassDimension
    gate_thresholds = {}
    for g in (gates or []):
        g_dim = g.get("dim") or g.get("dimension", "")
        if not g_dim:
            continue
        g_thr = g.get("threshold")
        g_comp = g.get("comparator", ">=")
        if g_thr is not None:
            gate_thresholds[g_dim] = (g_thr, g_comp)

    for dim in sorted(all_dims):
        vals = [s.get(dim) for s in window]
        vals = [v for v in vals if v is not None]
        if len(vals) < STAGNATION_CONSECUTIVE + 1:
            continue

        # PassDimension: CurrentValueGate, NoneStagnation
        if dim in gate_thresholds:
            thr, comp = gate_thresholds[dim]
            current_val = vals[-1]
            if comp == ">=" and current_val >= thr:
                continue
            elif comp == "<=" and current_val <= thr:
                continue
            elif comp == "==" and current_val == thr:
                continue

        # T5 KPI (threshold null): and score/controller , Stagnation
        kpi_gate = None
        for g in (gates or []):
            gd = g.get("dim") or g.get("dimension", "")
            if gd == dim and g.get("threshold") is None:
                kpi_gate = g
                break
        if kpi_gate is not None and kpi_row_satisfied(kpi_gate, vals[-1]):
            continue

        eligible_dims.add(dim)

        # P1-05: getDimensionConfidenceMargin
        confidence, margin = _confidence_for_dim(dim)

        # binary Dimension: direction( vs ), Value
        if confidence == "binary":
            all_regressing = all(
                vals[i] < vals[i - 1] for i in range(1, len(vals))
            )
            if all_regressing:
                results.append((dim, vals, 'regressing'))
            # binary DimensionandValueStagnation
            continue

        # checkRegression(score)
        all_regressing = all(
            vals[i] < vals[i - 1] for i in range(1, len(vals))
        )
        if all_regressing:
            results.append((dim, vals, 'regressing'))
            continue

        # P1-05: Stagnationthreshold margin —  max(threshold, margin)
        # empirical (margin=0.3) impactthreshold(threshold ≥ 0.3)
        # heuristic (margin=1.5) threshold, AvoidMarginStagnation
        effective_threshold = threshold
        effective_type = threshold_type
        if margin is not None and threshold_type == "absolute":
            effective_threshold = max(threshold, margin)
        elif margin is not None and threshold_type == "relative":
            #  margin Value: Value
            min_nonzero = min((v for v in vals if v > 0), default=1.0)
            relative_as_absolute = threshold * min_nonzero
            if margin > relative_as_absolute:
                effective_threshold = margin
                effective_type = "absolute"

        # checkStagnation: None
        has_sufficient_improvement = False
        for i in range(1, len(vals)):
            delta = vals[i] - vals[i - 1]
            if delta <= 0:
                continue
            if effective_type == "absolute":
                if delta >= effective_threshold:
                    has_sufficient_improvement = True
                    break
            else:
                if vals[i - 1] == 0:
                    has_sufficient_improvement = True
                    break
                improvement = delta / vals[i - 1]
                if improvement >= effective_threshold:
                    has_sufficient_improvement = True
                    break

        if not has_sufficient_improvement:
            results.append((dim, vals, 'stagnating'))

    return results, eligible_dims


def _bool_gate_eval(cur, g, state):
    """bool GateCurrentValue: bias_check  float  <0.15 ,  comparator/threshold ."""
    dim = g.get("dim") or g.get("dimension", "")
    if dim == "bias_check" and isinstance(cur, (int, float)) and not isinstance(cur, bool):
        cur = cur < 0.15
    comp = g.get("comparator")
    if not comp:
        comp = _lookup_manifest_comparator(
            get_template(state), dim, g.get("manifest_dimension")
        ) or ">="
    thr = g.get("threshold")
    if comp == "==" and thr is not None:
        return cur == thr
    return bool(cur)


def _plan_numeric_gate_pass_at(cur, g, state):
    """threshold  None , Value cur Gate(and check_gates_passed Value)."""
    thr = g.get("threshold")
    dim = g.get("dim") or g.get("dimension", "")
    if cur is None:
        return False
    if g.get("unit") == "bool":
        return _bool_gate_eval(cur, g, state)
    comp = g.get("comparator")
    if not comp:
        comp = _lookup_manifest_comparator(
            get_template(state), dim, g.get("manifest_dimension")
        ) or ">="
    if comp == ">=":
        return cur >= thr
    if comp == "<=":
        return cur <= thr
    if comp == "==":
        return cur == thr
    if comp == "<":
        return cur < thr
    if comp == ">":
        return cur > thr
    return cur >= thr


def detect_cross_dimension_regression(state):
    """hard ValueGate: previous round, this round(pass→fail).

     plan.decide_act_handoff.impacted_dimensions , andRegression pass→fail ; 
     handoff ,  VERIFY score ****  hard Exempt pass→fail(and loop-protocol ).
    """
    hist = get_score_history(state)
    if len(hist) < 2:
        return False, []
    prev, cur = hist[-2], hist[-1]
    gates = get_gates(state)
    violated = []
    seen = set()
    for g in gates:
        if (g.get("gate") or "").lower() != "hard":
            continue
        if plan_gate_is_exempt(g):
            continue
        thr = g.get("threshold")
        if thr is None:
            continue
        dim = g.get("dim") or g.get("dimension", "")
        if not dim:
            continue
        pv, cv = prev.get(dim), cur.get(dim)
        if pv is None or cv is None:
            continue
        if _plan_numeric_gate_pass_at(pv, g, state) and not _plan_numeric_gate_pass_at(
            cv, g, state
        ):
            if dim not in seen:
                seen.add(dim)
                violated.append(dim)
    if not violated:
        return False, []
    return True, violated


def check_gates_passed(state):
    """check hard gate , Returns (all_passed, details)"""
    scores = get_current_scores(state)
    gates = get_gates(state)
    if not gates:
        return True, []

    details = []
    all_hard_passed = True
    for g in gates:
        dim = g.get("dim") or g.get("dimension", "")
        threshold = g.get("threshold")
        gate_type = g.get("gate", "soft")
        current = scores.get(dim)
        label = g.get("label", dim)

        if not dim:
            continue

        if plan_gate_is_exempt(g):
            passed = True
        # KPI : ExemptStatus scores ; and autoloop_kpi.kpi_row_satisfied 
        elif threshold is None:
            passed = kpi_row_satisfied(g, current)
        elif current is None:
            passed = False
        elif g.get("unit") == "bool":
            passed = _bool_gate_eval(current, g, state)
        else:
            # use manifest comparator(and score.py _eval_gate )
            #  gate ,  manifest , last >=
            comp = g.get("comparator")
            if not comp:
                comp = _lookup_manifest_comparator(
                    get_template(state), dim, g.get("manifest_dimension")
                ) or ">="
            if comp == ">=":
                passed = current >= threshold
            elif comp == "<=":
                passed = current <= threshold
            elif comp == "==":
                passed = current == threshold
            elif comp == "<":
                passed = current < threshold
            elif comp == ">":
                passed = current > threshold
            else:
                passed = current >= threshold

        details.append({
            "dim": dim, "label": label, "threshold": threshold,
            "current": current, "gate": gate_type, "passed": passed,
        })
        if gate_type == "hard" and not passed:
            all_hard_passed = False

    return all_hard_passed, details


# ---------------------------------------------------------------------------
# Phase
# ---------------------------------------------------------------------------

def _plan_gate_matches_score_result(gate_def, gate_result):
    """plan.gates and JSON items( dim or manifest_dimension)."""
    pg = gate_def.get("dim") or gate_def.get("dimension", "")
    if gate_result.get("dimension") == pg:
        return True
    sr_man = gate_result.get("manifest_dimension")
    gd_man = gate_def.get("manifest_dimension")
    if sr_man and gd_man and sr_man == gd_man:
        return True
    return False


def _observe_target_gap_cells(g, cur_display, template_key):
    """OBSERVE : Targetand(and ORIENT , )."""
    dim = g.get("dim") or g.get("dimension", "")
    thr = g.get("threshold")
    tgt = g.get("target")
    comp = g.get("comparator")
    if not comp:
        comp = _lookup_manifest_comparator(
            template_key, dim, g.get("manifest_dimension")
        ) or ">="
    if thr is None and tgt is not None:
        disp_tgt = tgt
    else:
        disp_tgt = thr if thr is not None else "—"
    gap = ""
    if cur_display in ("—", "", None):
        return str(disp_tgt), gap
    try:
        cur = float(cur_display)
    except (ValueError, TypeError):
        return str(disp_tgt), gap
    if thr is None and tgt is not None:
        try:
            tnum = float(tgt)
            if cur >= tnum:
                gap = "PASS"
            elif abs(tnum) > 1e-9:
                gap = "{:.0f}%".format((tnum - cur) / abs(tnum) * 100)
        except (ValueError, TypeError):
            pass
        return str(disp_tgt), gap
    if not isinstance(thr, (int, float)):
        return str(disp_tgt), gap
    if comp == "==":
        gap = "PASS" if cur == thr else ("FAIL" if thr != 0 else "FAIL Δ={}".format(cur))
    elif comp == "<=":
        gap = "PASS" if cur <= thr else "FAIL"
    elif comp in (">", ">="):
        if cur >= thr:
            gap = "PASS"
        elif thr != 0:
            gap = "{:.1f}%".format(max(0.0, (thr - cur) / thr * 100))
        else:
            gap = "FAIL"
    else:
        if thr != 0 and cur < thr:
            gap = "{:.1f}%".format((thr - cur) / thr * 100)
        else:
            gap = "PASS" if cur >= thr else "FAIL"
    return str(disp_tgt), gap


def _latest_tsv_fail_closed(state):
    """and autoloop-variance check : ≥2 orConfidence<50%(≠0) fail-closed."""
    fc, _ = results_tsv_last_row_fail_closed(state)
    return fc


def _record_lesson_quality_issue(work_dir, strategy_id, lesson, missing):
    """ lesson_learned record autoloop-findings.md Issue ListMedium."""
    fpath = os.path.join(work_dir, "autoloop-findings.md")
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    entry = (
        "\n### lesson_learned  — {} ({})\n"
        "- strategy_id: {}\n"
        "- Issues: {}\n"
        "- CurrentContent: \"{}\"\n"
    ).format(now, strategy_id, strategy_id, "; ".join(missing), lesson[:200])
    try:
        with open(fpath, "a", encoding="utf-8") as f:
            f.write(entry)
    except OSError:
        pass  # findings.md does not exist()


def _append_immediate_discovery(work_dir, round_num, text):
    """Append an Immediate Findings note to autoloop-findings.md."""
    fpath = os.path.join(work_dir, "autoloop-findings.md")
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    entry = f"\n[Immediate Findings R{round_num}] ({now}) {text}\n"
    try:
        with open(fpath, "a", encoding="utf-8") as f:
            f.write(entry)
    except OSError:
        pass  # findings.md does not exist


def _detect_cross_round_repeat_patterns(state, round_num):
    """roundPattern: Issues 2+ round.ReturnsDescription."""
    if round_num < 2:
        return []
    rnds = (state.get("findings") or {}).get("rounds") or []
    if len(rnds) < 2:
        return []
    # extractroundIssue Description
    def _extract_problems(rnd):
        items = rnd.get("findings", [])
        return [
            (f.get("summary") or f.get("description") or f.get("content", "")).strip().lower()
            for f in items
            if isinstance(f, dict)
        ]

    prev = set(_extract_problems(rnds[-2])) if len(rnds) >= 2 else set()
    curr = set(_extract_problems(rnds[-1]))
    prev.discard("")
    curr.discard("")
    repeated = prev & curr
    return [p for p in repeated if p]


def _maybe_reflect_experience_write(work_dir, state, tmpl):
    """ iterations[-1].reflect  dict, Call autoloop-experience write.

    ``--score`` round **delta**(and experience-registry avg_delta ).
    Likert  ``rating_1_to_5``,  delta write;  ``score``  1–5  Likert.
    """
    iters = state.get("iterations", [])
    if not iters:
        return
    ref = iters[-1].get("reflect")
    if not isinstance(ref, dict):
        return
    sid = str(ref.get("strategy_id", "")).strip()
    effect = str(ref.get("effect", "")).strip()
    if not sid or effect not in ("Keep", "Avoid", "To Validate"):
        return

    delta = ref.get("delta")
    rating = ref.get("rating_1_to_5")
    legacy = ref.get("score")

    score_for_write = None
    if delta is not None:
        score_for_write = delta
    elif legacy is not None:
        try:
            fv = float(legacy)
            iv = int(fv)
        except (TypeError, ValueError):
            score_for_write = legacy
        else:
            if fv == iv and 1 <= iv <= 5:
                info(
                    "iterations[-1].reflect.score is a 1-5 Likert value; "
                    "please use delta, score_delta, or rating_1_to_5, then write the delta to the experience registry"
                )
                return
            score_for_write = legacy

    if score_for_write is None:
        if rating is not None:
            info(
                "Use iterations[-1].reflect.rating_1_to_5 (Likert) together with a delta, "
                "then call autoloop-experience.py write"
            )
        return

    dimension = str(ref.get("dimension", "—"))
    context = str(ref.get("context", ""))
    args = [
        work_dir, "write",
        "--strategy-id", sid,
        "--effect", effect,
        "--score", str(score_for_write),
        "--template", tmpl,
        "--dimension", dimension,
    ]
    if context:
        args.extend(["--context", context])
    st = ref.get("status")
    if st:
        args.extend(["--status", str(st)])
    # --- lesson_learned check(effect="Avoid"  delta < 0 )---
    lesson = str(ref.get("lesson_learned", "")).strip()
    if effect == "Avoid" and score_for_write is not None:
        try:
            delta_val = float(score_for_write)
        except (ValueError, TypeError):
            delta_val = 0.0
        if delta_val < 0:
            lesson_ok = True
            missing = []
            if not lesson or len(lesson) <= 20:
                lesson_ok = False
                missing.append("lesson_learned or(≤20)")
            else:
                # check:  /  / AlternativeRecommendation
                has_what = any(kw in lesson for kw in ("", "tried", "did", "", "", "adopted", "used", "applied"))
                has_why = any(kw in lesson for kw in ("because", "because", "", "caused", "", "failed", "Issues", "issue", "Reason"))
                has_instead = any(kw in lesson for kw in ("", "instead", "Alternative", "should", "should", "Recommendation", "recommend", "better"))
                if not has_what:
                    missing.append("''Description")
                if not has_why:
                    missing.append("''Reason")
                if not has_instead:
                    missing.append("'AlternativeRecommendation'")
            if not lesson_ok or missing:
                warn(
                    "Strategy marked as 'Avoid' with negative delta but lesson_learned is insufficient.\n"
                    "  Required: describe (1) what was tried, (2) why it failed, (3) what to do instead.\n"
                    "  Current lesson_learned: \"{}\"\n"
                    "  Issues: {}".format(lesson[:120], "; ".join(missing))
                )
                # record findings Issue List
                _record_lesson_quality_issue(work_dir, sid, lesson, missing)

    info("Writing to the experience registry from iterations[-1].reflect...")
    _, rc = run_tool("autoloop-experience.py", args, capture=True, work_dir=work_dir)
    if rc != 0:
        warn("experience write returned non-zero; still verify reflect fields and the experience-registry path")


def _t3_kpi_actionable(gates):
    """T5 at leastitems KPI (threshold null) target(quality-gates.md)."""
    rows = [g for g in (gates or []) if g.get("threshold") is None]
    if not rows:
        return False
    return any(g.get("target") is not None for g in rows)


def _findings_md_protocol_version(text):
    """ findings.md Protocol Version( 1.0.0), and SSOT ."""
    head = "\n".join(text.splitlines()[:120])
    for line in head.splitlines():
        s = line.strip()
        if "protocol" in s.lower() or "Protocol Version" in s:
            m = re.search(r"(\d+\.\d+\.\d+)", s)
            if m:
                return m.group(1)
    return None


def _findings_md_h2_section_lines(lines, keywords):
    """ ``## ``  keyword , Returns ``## `` ()."""
    for i, line in enumerate(lines):
        if line.startswith("## ") and any(k in line for k in keywords):
            out = []
            for j in range(i + 1, len(lines)):
                ln = lines[j]
                if ln.startswith("## "):
                    break
                out.append(ln)
            return out
    return []


def _count_md_table_body_lines(section_lines):
    """H2 :  markdown ****(+|---| ; None)."""
    lines = section_lines
    sep_i = -1
    for i, line in enumerate(lines):
        if line.count("|") >= 2 and "---" in line:
            sep_i = i
            break
    start = sep_i + 1 if sep_i >= 0 else 0

    def _row(line):
        if line.count("|") < 2:
            return False
        s = line.strip()
        if "---" in s and line.count("|") >= 2:
            return False
        if re.match(r"^[\|\s\-:]+$", s):
            return False
        inner = "|".join(p.strip() for p in s.split("|"))
        return bool(inner) and not (set(inner) <= set("-: \t"))

    if sep_i >= 0:
        return sum(1 for line in lines[start:] if _row(line))
    return sum(1 for line in lines if _row(line))


def _findings_md_four_layer_table_stats(text):
    """Reflection:  H2 (0=Not FoundorNone)."""
    lines = text.splitlines()
    specs = (
        ("L1Issue List", ("Issue List", "1", "REFLECT  1")),
        ("L2Strategy", ("Strategy", "2", "REFLECT  2")),
        ("L3Pattern Recognition", ("Pattern Recognition", "3", "REFLECT  3")),
        ("L4Lessons Learned", ("Lessons Learned", "4", "REFLECT  4")),
    )
    return {
        label: _count_md_table_body_lines(_findings_md_h2_section_lines(lines, kws))
        for label, kws in specs
    }


def _strict_evolve_requires_tsv_current_round(state, round_num):
    """STRICT:  results_tsv.iteration andCurrent OODA Round( VERIFY )."""
    rows = state.get("results_tsv") or []
    if not rows:
        return False
    last = rows[-1]
    lit = last.get("iteration")
    try:
        return int(lit) == int(round_num)
    except (TypeError, ValueError):
        return str(lit).strip() == str(round_num).strip()


def _strict_evolve_requires_findings(state):
    """STRICT: EVOLVE this round finding(Recommendation #4 )."""
    it = state.get("iterations") or []
    if it and it[-1].get("findings"):
        return True
    rnds = (state.get("findings") or {}).get("rounds") or []
    return bool(rnds and rnds[-1].get("findings"))


def _observe_report_findings_md(work_dir, state):
    """OBSERVE Step 0:  work_dir/autoloop-findings.md(loop-protocol Reflection 4 )."""
    path = os.path.join(work_dir, "autoloop-findings.md")
    if not os.path.isfile(path):
        info("OBSERVE Step 0: autoloop-findings.md does not exist( SSOT findings +  render)")
        return
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()
    except OSError as e:
        warn("OBSERVE Step 0: Noneread autoloop-findings.md — {}".format(e))
        return
    n = len(text)
    anchors = (
        ("Issue List/1", ("Issue List" in text) or ("REFLECT  1" in text)),
        ("Strategy/2", ("Strategy" in text) or ("REFLECT  2" in text)),
        ("Pattern Recognition/3", ("Pattern Recognition" in text) or ("REFLECT  3" in text)),
        ("Lessons Learned/4", ("Lessons Learned" in text) or ("REFLECT  4" in text)),
    )
    hits = [label for label, ok in anchors if ok]
    info(
        "OBSERVE Step 0: autoloop-findings.md ({} ); Reflection: {}".format(
            n, ", ".join(hits) if hits else "Medium( 4 )"
        )
    )
    meta = state.get("metadata") or {}
    pv = meta.get("protocol_version")
    if pv:
        info("  SSOT metadata.protocol_version={}".format(pv))
    f_pv = _findings_md_protocol_version(text)
    if f_pv:
        info("  findings.md  protocol : {}".format(f_pv))
    if f_pv and pv and str(f_pv) != str(pv):
        warn(
            "  findings.md and SSOT metadata.protocol_version  —  loop-protocol Baseline"
        )
    stats = _findings_md_four_layer_table_stats(text)
    stat_s = "; ".join("{}={}".format(k, v) for k, v in stats.items())
    info("  (H2 ): {}".format(stat_s))
    if sum(stats.values()) == 0:
        info(
            "  rebaseline Hint:  ## ;  loop-protocol  "
            "'Issue List / Strategy Evaluation / Pattern Recognition / Lessons Learned'"
        )

    def _persist_observe_snapshot(st):
        m = st.setdefault("metadata", {})
        m["observe_findings_snapshot"] = {
            "path": "autoloop-findings.md",
            "char_count": n,
            "anchors_hit": list(hits),
            "four_layer_table_stats": dict(stats),
            "findings_md_protocol_version": f_pv,
            "ssot_protocol_version": pv,
        }
        if f_pv and pv and str(f_pv) != str(pv):
            m["rebaseline_required"] = True
        elif f_pv and pv:
            m["rebaseline_required"] = False

    _record_state_metadata(work_dir, _persist_observe_snapshot)


def phase_observe(work_dir, state, round_num):
    """OBSERVE: CurrentScores vs Target, readexperience registryRecommended.

    Returns (decision, reasons): decision  \"continue\" or \"pause\"(T5  KPI ).
    """
    banner(round_num, "OBSERVE", "CurrentStatus")

    le = state.get("metadata", {}).get("last_error")
    if isinstance(le, dict) and le.get("script"):
        warn(
            ": {} rc={} @ {}".format(
                le.get("script"), le.get("returncode"), le.get("time", "")
            )
        )
        sn = (le.get("stderr") or "").strip()
        if sn:
            warn("  stderr: {}".format(sn[:400]))

    scores = get_current_scores(state)
    gates = get_gates(state)
    template = get_template(state)

    if template == "T5" and not _t3_kpi_actionable(gates):
        warn(
            "T5  KPI: please plan.gates Medium KPI  target and dim(Dimensionand iterations[].scores )."
        )
        error(
            "OBSERVE: KPI targets are missing for this T5 task (see quality-gates.md T5 KPI requirements)"
        )
        return "pause", [
            "T5  KPI or target; please plan.gates  autoloop-controller.py <work_dir> --resume"
        ]

    # 0. roundrecord gate-manifest.json mtime( VERIFY Phasecheck)
    if round_num == 1:
        manifest_path = os.path.join(os.path.dirname(__file__), "..", "references", "gate-manifest.json")
        try:
            mtime = os.path.getmtime(manifest_path)
            state.setdefault("metadata", {})["manifest_mtime"] = mtime
            save_json(os.path.join(work_dir, STATE_FILE), state)
            info(f"record gate-manifest.json mtime: {mtime}")
        except OSError:
            warn("Noneread gate-manifest.json mtime")

    # 1. Current Score vs GateTarget
    info(f"Template: {template} | Round: {round_num}/{get_max_rounds(state)}")
    if scores:
        print(f"\n{'Dimension':<20} {'Current':>8} {'Target':>8} {'':>8} {'Gate':>6}")
        print("─" * 56)
        for g in gates:
            dim = g.get("dim") or g.get("dimension", "")
            if not dim:
                continue
            cur = scores.get(dim, "—")
            tgt_s, gap = _observe_target_gap_cells(g, cur, template)
            print(f"{g.get('label', dim):<20} {str(cur):>8} {tgt_s:>8} {gap:>8} {g['gate']:>6}")
    else:
        warn("Nonescore(round)")

    # 1b. round findings Summary(Options)
    rnds = state.get("findings", {}).get("rounds", [])
    if rnds:
        last_r = rnds[-1]
        items = last_r.get("findings", [])
        if items:
            info("round findings Summary( 3 items):")
            for f in items[-3:]:
                line = f.get("summary") or f.get("content") or f.get("description", "")
                d = f.get("dimension", "—")
                if line:
                    print(f"  [{d}] {str(line)[:120]}")

    # 1c. Structured Reflection(SSOT): lessons_learned + previous round iterations.reflect
    ll = state.get("findings", {}).get("lessons_learned") or {}
    if isinstance(ll, dict):
        blocks = []
        for key, label in (
            ("verified_hypotheses", "validationhypothesis"),
            ("generalizable_methods", "method"),
            ("process_improvements", ""),
        ):
            arr = ll.get(key)
            if isinstance(arr, list) and arr:
                preview = arr[:3]
                blocks.append("{}: {}".format(label, "; ".join(str(x)[:80] for x in preview)))
        if blocks:
            info("roundReflection(findings.lessons_learned):")
            for b in blocks:
                print(f"  {b}")
    iters = state.get("iterations", [])
    if len(iters) >= 2:
        prev_ref = iters[-2].get("reflect")
        if isinstance(prev_ref, dict) and prev_ref:
            info("previous round iterations[-2].reflect Summary:")
            for k in (
                "strategy_id",
                "effect",
                "lesson_learned",
                "delta",
                "rating_1_to_5",
                "score",
                "dimension",
            ):
                if prev_ref.get(k) not in (None, ""):
                    print(f"  {k}: {str(prev_ref.get(k))[:200]}")

    _observe_report_findings_md(work_dir, state)

    # 1d. : roundMode Detection(Round 2+)
    if round_num >= 2:
        repeats = _detect_cross_round_repeat_patterns(state, round_num)
        if repeats:
            info(f"[] Detected {len(repeats)} roundPattern, write findings.md Pattern Recognition")
            for r in repeats:
                pattern_msg = f"Cross-round pattern: '{r[:120]}' repeated in 2+ rounds, "
                _append_immediate_discovery(work_dir, round_num, pattern_msg)
                info(f"  → {pattern_msg[:150]}")

    # 2. experience registryRecommended — (Template OR applicable_templates) + context_tags ≥2(see loop-protocol); None plan.context_tags 
    ctx_csv = _plan_context_tags_csv(state.get("plan") or {})
    qargs = [work_dir, "query", "--template", template, "--include-global"]
    if ctx_csv:
        qargs.extend(["--tags", ctx_csv])
        info("experience registry (Template={}, context_tags={}, include_global)...".format(template, ctx_csv))
    else:
        info("experience registry (Template={}, include_global)...".format(template))
    output, rc = run_tool(
        "autoloop-experience.py",
        qargs,
        capture=True,
        work_dir=work_dir,
    )
    if rc == 0 and output.strip():
        print(f"\n{C_DIM}{output.strip()}{C_RESET}\n")
    elif rc != 0:
        warn(
            "Experience registry not found (look in work_dir/references/ or references/)"
        )
    else:
        info("No matching strategies found in the experience registry for this round")

    # 3. OBSERVE mustField(P2-17)
    info("--- OBSERVE mustField ---")
    info("1. current_scores: DimensionCurrent Score (dict[str, float])")
    info("2. target_scores: DimensionTargetscore (dict[str, float])")
    info("3. remaining_budget_pct: remaining budget% (float)")
    info("4. focus_dimensions: this roundDimension (list[str])")
    info("5. carry_over_issues: roundIssues (list[str], Options)")
    info("------------------------------")

    return "continue", []


def phase_orient(work_dir, state, round_num):
    """ORIENT: , priority"""
    banner(round_num, "ORIENT", "analysisandpriority")

    scores = get_current_scores(state)
    gates = get_gates(state)

    if not scores or not gates:
        warn("NoneorGate, ")
        return

    critical = []   # >50% 
    moderate = []   # 20-50% 
    minor = []      # <20% 
    passed = []     # Pass

    for g in gates:
        dim = g.get("dim") or g.get("dimension", "")
        if not dim:
            continue
        cur = scores.get(dim)
        thr = g.get("threshold")
        label = g.get("label", dim)

        # T5 /  KPI: threshold  None  target andCurrent( check_gates_passed)
        if thr is None:
            tgt = g.get("target")
            if tgt is not None and cur is not None:
                try:
                    tnum = float(tgt)
                    cnum = float(cur)
                except (ValueError, TypeError):
                    moderate.append((label, dim, cur, "KPI is non-numeric, "))
                    continue
                if cnum >= tnum:
                    passed.append((label, dim, cur, "PASS"))
                else:
                    gap_pct = ((tnum - cnum) / abs(tnum) * 100) if abs(tnum) > 1e-9 else 100.0
                    bucket = critical if gap_pct > 50 else moderate if gap_pct > 20 else minor
                    bucket.append((label, dim, cur, f"{gap_pct:.0f}%"))
                continue
            if cur is None and tgt is None:
                moderate.append((label, dim, "—", "KPI not defined yet TargetandCurrent"))
            elif cur is None:
                moderate.append((label, dim, "—", f"Target={tgt}, Current"))
            else:
                moderate.append((label, dim, cur, "target not configured"))
            continue

        if cur is None:
            critical.append((label, dim, "None", "—"))
            continue

        if g.get("unit") == "bool":
            ok = _bool_gate_eval(cur, g, state)
            if ok:
                passed.append((label, dim, cur, "PASS"))
            else:
                critical.append((label, dim, cur, "Fail"))
            continue

        # use comparator  pass/fail direction
        comp = g.get("comparator")
        if not comp:
            comp = _lookup_manifest_comparator(
                get_template(state), dim, g.get("manifest_dimension")
            ) or ">="

        if comp in ("<=", "=="):
            # or
            check_pass = (cur <= thr) if comp == "<=" else (cur == thr)
            if check_pass:
                passed.append((label, dim, cur, "PASS"))
            else:
                gap_pct = ((cur - thr) / max(cur, 1)) * 100
                bucket = critical if gap_pct > 50 else moderate if gap_pct > 20 else minor
                bucket.append((label, dim, cur, f"{gap_pct:.0f}%"))
            continue

        # High(>=, >)
        if thr == 0:
            passed.append((label, dim, cur, "PASS"))
            continue

        if cur >= thr:
            passed.append((label, dim, cur, "PASS"))
        else:
            gap_pct = ((thr - cur) / thr) * 100
            bucket = critical if gap_pct > 50 else moderate if gap_pct > 20 else minor
            bucket.append((label, dim, cur, f"{gap_pct:.0f}%"))

    def _print_bucket(name, color, items):
        if not items:
            return
        print(f"\n{color}{C_BOLD}{name}{C_RESET}")
        for label, dim, cur, gap in items:
            print(f"  {label:<20} Current={cur:<8} ={gap}")

    _print_bucket("CRITICAL (>50%)", C_RED, critical)
    _print_bucket("MODERATE (20-50%)", C_YELLOW, moderate)
    _print_bucket("MINOR (<20%)", C_GREEN, minor)
    _print_bucket("PASSED", C_DIM, passed)

    info(
        "Note: comparator <= / == gates may look unresolved in ORIENT; "
        "final evaluation happens in VERIFY through autoloop-score and plan.gates (E-02)."
    )

    #  & Stagnation
    history = get_score_history(state)
    tmpl = get_template(state)
    osc = detect_oscillation(history)
    stag, _eligible = detect_stagnation(history, gates, template_key=tmpl)
    stag_dims = {d for d, _, _ in stag} if stag else set()
    osc_for_display = [x for x in osc if x[0] not in stag_dims]

    if osc_for_display:
        warn("(andStagnation/Regression, and EVOLVE ):")
        for dim, vals, _ in osc_for_display:
            warn(f"  {dim}:  {OSCILLATION_WINDOW} round {vals} —  ≤ ±{OSCILLATION_BAND}")
    if stag:
        threshold, threshold_type = _get_stagnation_threshold(tmpl)
        if threshold_type == "absolute":
            threshold_str = f"{threshold} (Value)"
        else:
            threshold_str = f"{threshold*100:.0f}%(Value)"
        warn(f"Stagnation/Regression(Template={tmpl}, threshold={threshold_str}):")
        for dim, vals, signal in stag:
            if signal == 'regressing':
                warn(f"  {C_RED}[Regression]{C_RESET} {dim}:  {vals} — score, ")
            else:
                warn(f"  [Stagnation] {dim}:  {vals} — Lowthreshold, RecommendationStrategy")


def phase_decide(work_dir, state, round_num, strict_cli=False, enforce_strategy_history=False):
    """DECIDE: StrategyHint(LLM )"""
    banner(round_num, "DECIDE", "Strategy")

    st = _strict_enabled(strict_cli)
    hard = st or _enforce_strategy_history_enabled(enforce_strategy_history)
    _decide_strategy_preflight(state, hard)

    scores = get_current_scores(state)
    template = get_template(state)
    strategy_history = state.get("plan", {}).get("strategy_history", [])

    history_summary = "None" if not strategy_history else "\n".join(
        f"  Round {s.get('round', '?')}: {s.get('strategy_id', '?')} — {s.get('result', '?')}"
        for s in strategy_history[-5:]
    )

    prompt_block("Strategy This Round", f"""\
         ORIENT Phaseanalysis, this roundStrategy:

        Template: {template}
        current round: {round_num}/{get_max_rounds(state)}
        Current Scores: {json.dumps(scores, ensure_ascii=False)}
        Strategy(5round):
        {history_summary}

        :
        1.  CRITICAL Dimension
        2. StrategyID: S{round_num:02d}-<Description>
        3. ( coverage +15%)
        4. /Stagnation, mustStrategy(roundStrategy)
        5. :
           StrategyID: S{round_num:02d}-xxx
           TargetDimension: [dim1, dim2]
           : dim1 +X%, dim2 +Y%
           method: ...
           Risk: ...

        6. [handoff] Write this round's decision into plan.decide_act_handoff (JSON):
           autoloop-state.py update {work_dir} plan.decide_act_handoff '<JSON >'

        7. [Template]:
           {{"strategy_id":"S{round_num:02d}-short-name","hypothesis":"this roundhypothesis","planned_commands":["1","Options2"],"impacted_dimensions":["dimA","dimB"]}}

           Use strategy_id in SNN-Description form. If the experience registry recommends a strategy, still assign a fresh strategy_id for this round.
           If the strategy has cross-dimension impact, declare impacted_dimensions(); in VERIFY, the TSV side_effect must not be 'None' (strict validate checks this).
    """)

    # DECIDE mustField(P2-17)
    info("--- DECIDE mustField ---")
    info("1. strategy_id: S{NN}-{Description}  (str)")
    info("2. action_plan:  (list[str])")
    info("3. fallback: Strategy (str)")
    info("4. impacted_dimensions: impactDimension (list[str])")
    info("------------------------------")


##############################################################################
# ACT TypeandResume
##############################################################################

FAILURE_TYPES = ("timeout", "capability_gap", "resource_missing", "external_error", "code_error", "partial_success")

RECOVERY_STRATEGIES = {
    "timeout": "task(task), ",
    "capability_gap": "or",
    "resource_missing": "pleaseResources",
    "external_error": "(delay = min(base * 2^attempt, 300))",
    "code_error": "record bug, ",
    "partial_success": "Continue(Completed)",
}


def classify_failure(error_msg, exit_code=None):
    """Type( subagent Returns failure_type use)."""
    if exit_code and exit_code == 124:  # timeout exit code
        return "timeout"
    error_lower = (error_msg or "").lower()
    if any(k in error_lower for k in ("timeout", "timed out", "context limit")):
        return "timeout"
    if any(k in error_lower for k in ("rate limit", "429", "503", "network")):
        return "external_error"
    if any(k in error_lower for k in ("traceback", "syntax error", "import error")):
        return "code_error"
    if any(k in error_lower for k in ("not found", "permission denied", "no such file")):
        return "resource_missing"
    return "capability_gap"  # 


def parse_completion_ratio(state):
    """ state.json  iterations[-1].act Mediumextract completion_ratio.

    Returns int (0-100) or None(Not Found/).
    """
    iterations = state.get("iterations") or []
    if not iterations:
        return None
    act_data = iterations[-1].get("act")
    if not act_data:
        return None
    # act_data  dict or JSON 
    if isinstance(act_data, str):
        try:
            act_data = json.loads(act_data)
        except (json.JSONDecodeError, TypeError):
            return None
    if not isinstance(act_data, dict):
        return None
    raw = act_data.get("completion_ratio")
    if raw is None:
        return None
    try:
        ratio = int(raw)
        return max(0, min(100, ratio))
    except (ValueError, TypeError):
        return None


def process_act_completion(work_dir, state):
    """ACT→VERIFY :  completion_ratio  partial / needs_replanning.

    Returns True Continue VERIFY, False Recommendation().
    """
    ratio = parse_completion_ratio(state)
    if ratio is None:
        return True  #  completion_ratio, 

    if ratio >= 80:
        info(f"Subagent Progress: {ratio}% —  VERIFY")
        return True
    elif ratio >= 50:
        warn(f"Subagent Progress: {ratio}% — Completed,  VERIFY  partial")
        run_tool(
            "autoloop-state.py",
            ["update", work_dir, "iterations[-1].act.partial", "true"],
            work_dir=work_dir,
        )
        return True
    else:
        warn(f"Subagent Progress: {ratio}% — Progress, Recommendation DECIDE ")
        run_tool(
            "autoloop-state.py",
            ["update", work_dir, "iterations[-1].act.needs_replanning", "true"],
            work_dir=work_dir,
        )
        return False


def log_act_failure(work_dir, state, failure_type, failure_detail="", completion_ratio=0):
    """TypeResumeStrategywrite state.json  iterations[-1].act."""
    recovery = RECOVERY_STRATEGIES.get(failure_type, RECOVERY_STRATEGIES["capability_gap"])
    warn(f"ACT Type: {failure_type} — {failure_detail}")
    info(f"ResumeStrategy: {recovery}")

    # write state.json
    act_failure = json.dumps({
        "failure_type": failure_type,
        "failure_detail": failure_detail,
        "completion_ratio": completion_ratio,
        "recovery_action": recovery,
    }, ensure_ascii=False)
    run_tool("autoloop-state.py", ["update", work_dir, "iterations[-1].act", act_failure], work_dir=work_dir)


TASK_TYPE_MAP = {
    "T1": ("research", "use web_search "),
    "T2": ("analysis", "useanalysis, "),
    "T3": ("design", "use, "),
    "T4": ("coding", "use edit_file  bash "),
    "T5": ("iteration", ", searchanalysis"),
    "T6": ("generation", ", Consistency"),
    "T7": ("review", "search, findingIssues"),
    "T8": ("optimization", "PerformanceTest, validation"),
}


def get_recommended_model(template, phase="ACT"):
    """read, ReturnsRecommended Model(, )."""
    routing_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..", "references", "model-routing.json",
    )
    if not os.path.exists(routing_path):
        return None
    try:
        with open(routing_path) as f:
            routing = json.load(f)
    except (json.JSONDecodeError, OSError):
        return None

    tmpl_config = routing.get("template_models", {}).get(template, {})
    if phase == "ACT" and tmpl_config.get("act_override"):
        return tmpl_config["act_override"]
    return tmpl_config.get("preferred", routing.get("default_model"))


def phase_act(work_dir, state, round_num, strict=False):
    """ACT:  subagent (LLM ).strict and run_loop / CLI --strict ."""
    banner(round_num, "ACT", "")

    template = get_template(state)
    handoff = state.get("plan", {}).get("decide_act_handoff")
    if handoff:
        info(" plan.decide_act_handoff(DECIDE→ACT handoff):")
        print(json.dumps(handoff, ensure_ascii=False, indent=2))
    elif strict:
        error(
            "STRICT: plan.decide_act_handoff  — Medium(please DECIDE write JSON handoff)"
        )
        return False

    tp = state.get("plan", {}).get("template_params") or {}
    globs = tp.get("allowed_script_globs") or tp.get("allowed_commands")
    if isinstance(globs, list) and globs:
        info("plan.template_params (/ glob or, ):")
        for g in globs[:20]:
            print(f"  - {g}")
    elif isinstance(globs, str) and globs.strip():
        info("plan.template_params : {}".format(globs.strip()[:500]))

    sup = ""
    if template in ("T5", "T6", "T4"):
        sup = """
        TemplateRecommendation(and Superpowers ):
        brainstorming → writing-plans → subagent-driven-development → TDD → requesting-code-review
        """

    task_type_hint = ""
    if template in TASK_TYPE_MAP:
        tt, hint = TASK_TYPE_MAP[template]
        task_type_hint = f"[taskType: {tt}] {hint}"
        info(f"Task-Aware Dispatch: {task_type_hint}")

    cmd_chk = f"""\
        [Recommended Command List — copy as needed]
          python3 scripts/autoloop-score.py {work_dir} --json
          python3 scripts/autoloop-validate.py {work_dir}
          python3 scripts/autoloop-validate.py {work_dir} --strict
          python3 scripts/autoloop-render.py {work_dir}
          python3 scripts/autoloop-variance.py check {work_dir}/autoloop-results.tsv
          python3 -m py_compile <.py>    # or syntax_check_cmd
        (; VERIFY PhaseCall score/validate.)
    """

    model_hint = ""
    recommended = get_recommended_model(template, "ACT")
    if recommended:
        model_hint = f"Recommended Model: {recommended}(, )"
        info(f"Model Routing: {model_hint}")

    prompt_block("Strategy", f"""\
         DECIDE PhaseStrategy, :

        Work Directory: {work_dir}
        Template: {template}
        {task_type_hint}
        {model_hint}
        {sup}
        {cmd_chk}
        Execution Requirements:
        1. StrategyMediummethod( autoloop-*.py / Test)
        2. validation(py_compile / tsc --noEmit)
        3. record state.json Current
        4. Completedupdate findings

        On failure, return structured information(write iterations[-1].act):
          failure_type: timeout | capability_gap | resource_missing | external_error | code_error | partial_success
          failure_detail: Description
          completion_ratio: 0-100

        Immediate Findings(Options):
          if subagent ReturnsMedium discoveries (), write findings.md,  REFLECT.
          See agent-dispatch.md, section "Immediate Findings".

        Completed:
          autoloop-state.py update {work_dir} plan.budget.current_round {round_num}
    """)
    # P2-03: ACT Completedfile(T4/T7/T8)
    check_file_changes(work_dir, state)

    # check ACT  — None act.records Description subagent
    state_path = os.path.join(work_dir, STATE_FILE)
    try:
        state_fresh = load_json(state_path)
    except (OSError, json.JSONDecodeError):
        state_fresh = state  #  state(Test stub )
    iters_fresh = state_fresh.get("iterations", [])
    act_records = iters_fresh[-1].get("act", {}).get("records", []) if iters_fresh else []
    if not act_records:
        warn("ACT phase has no act.records; actual execution is still missing.")
        warn("Complete execution, write the result via add-finding, then continue with --resume.")
        return "pause"

    return True


def check_file_changes(work_dir, state):
    """check ACT Phasefile( T4/T7/T8 Template).

    if git diff ,  state Medium no_file_changes .
    """
    template = get_template(state)
    if template not in ("T4", "T7", "T8"):
        return  # Templatecheck

    import subprocess
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD"],
            cwd=work_dir, capture_output=True, text=True, timeout=10
        )
        changed_files = [f for f in result.stdout.strip().split("\n") if f]
    except (subprocess.TimeoutExpired, OSError) as e:
        warn(f"filecheck: {e}")
        return

    if not changed_files:
        warn("ACT CompletedDetectedfile(git diff ).")
        warn("Reason: subagent file, or.")
        # write state: iterations[-1].act.no_file_changes = True
        iterations = state.get("plan", {}).get("iterations", [])
        if iterations:
            act = iterations[-1].setdefault("act", {})
            act["no_file_changes"] = True
            save_json(os.path.join(work_dir, STATE_FILE), state)
    else:
        info(f"ACT file: {len(changed_files)}  files")
        for f in changed_files[:10]:
            info(f"  {f}")
        if len(changed_files) > 10:
            info(f"  ...  {len(changed_files)}  files")


def process_act_discoveries(work_dir, state, round_num, subagent_result):
    """ACT :  subagent ReturnsMedium discoveries Field.

     subagent_result(dict or JSON str)Mediumextract discoveries , 
    write findings.md  state.json metadata.immediate_discoveries.
    """
    if isinstance(subagent_result, str):
        try:
            subagent_result = json.loads(subagent_result)
        except (json.JSONDecodeError, TypeError):
            return []
    if not isinstance(subagent_result, dict):
        return []
    discoveries = subagent_result.get("discoveries", [])
    if not isinstance(discoveries, list) or not discoveries:
        return []
    info(f"[] finding {len(discoveries)} items")
    for d in discoveries:
        d_str = str(d).strip()
        if d_str:
            _append_immediate_discovery(work_dir, round_num, d_str)
            info(f"  → {d_str[:150]}")
    # write state.json metadata
    state.setdefault("metadata", {}).setdefault("immediate_discoveries", []).extend(
        str(d).strip() for d in discoveries if str(d).strip()
    )
    save_json(os.path.join(work_dir, STATE_FILE), state)
    return discoveries


def _create_t3_scoring_findings(work_dir, state, round_num):
    """T3:  ACT extractkeyContent, create summary findings  score.py keyword analysis."""
    #  iterations[-1].act.records extractSummary
    iters = state.get("iterations", [])
    if not iters:
        return
    act_records = iters[-1].get("act", {}).get("records", [])

    #  act Description/Summary
    summaries = []
    for rec in act_records:
        desc = rec.get("description", "") or rec.get("summary", "") or ""
        result = rec.get("result", "") or rec.get("output", "") or ""
        if desc:
            summaries.append(desc)
        if result and len(str(result)) < 2000:
            summaries.append(str(result))

    # if act records,  output_files read
    if not summaries:
        output_files = state.get("plan", {}).get("output_files", {})
        for key, info_dict in output_files.items():
            if isinstance(info_dict, dict):
                fpath = info_dict.get("path", "")
                resolved = os.path.realpath(os.path.join(work_dir, fpath)) if fpath else ""
                if resolved and resolved.startswith(os.path.realpath(work_dir)) and os.path.exists(resolved):
                    try:
                        with open(resolved, "r", encoding="utf-8") as f:
                            content = f.read(3000)  #  3000 
                        summaries.append(content)
                    except OSError:
                        pass

    if not summaries:
        return

    combined = "\n".join(summaries)

    # create 5 Dimension findings,  keyword Content
    t3_dims = [
        ("design_completeness", "Design Completeness: " + combined[:500]),
        ("feasibility_score", "Technical Feasibilityanalysis: Architecture, analysis, Risk." + combined[:300]),
        ("requirement_coverage", ": , , ." + combined[:300]),
        ("scope_precision", ": IN scope / OUT scope ." + combined[:200]),
        ("validation_evidence", "Validation Evidence: check, RiskCompleted." + combined[:200]),
    ]

    for dim, content in t3_dims:
        finding_json = json.dumps({
            "dimension": dim,
            "content": content,
            "source": "auto-extracted from T3 ACT output",
            "confidence": "Medium",
            "type": "finding"
        }, ensure_ascii=False)
        run_tool("autoloop-state.py", ["add-finding", work_dir, finding_json],
                 capture=True, work_dir=work_dir)


def phase_verify(work_dir, state, round_num, strict=False):
    """VERIFY: Call.Returns verify_ok(strict  False)."""
    banner(round_num, "VERIFY", "Score Verification")

    # T3:  ACT create findings(score.py need findings  keyword analysis)
    template = get_template(state)
    template_key = template.upper().split()[0] if template else ""
    if template_key == "T3" and round_num > 0:
        rounds = state.get("findings", {}).get("rounds", [])
        has_findings = any(
            rnd.get("findings") for rnd in rounds
        )
        if not has_findings:
            info("T3: findings.rounds ,  ACT create findings...")
            _create_t3_scoring_findings(work_dir, state, round_num)
            state = load_state(work_dir)  # reload after findings creation

    verify_ok = True

    # gate-manifest.json  mtime check
    recorded_mtime = state.get("metadata", {}).get("manifest_mtime")
    if recorded_mtime is not None:
        manifest_path = os.path.join(os.path.dirname(__file__), "..", "references", "gate-manifest.json")
        try:
            current_mtime = os.path.getmtime(manifest_path)
            if current_mtime != recorded_mtime:
                warn(f"gate-manifest.json (mtime {recorded_mtime} → {current_mtime}).")
                warn("Gate SSOT task, please.")
                warn(", please update metadata.manifest_mtime or init..")
                return False
        except OSError:
            warn("Noneread gate-manifest.json mtime, check")

    info("Run scorer...")
    stdout, rc = run_tool(
        "autoloop-score.py", [work_dir, "--json"], capture=True, work_dir=work_dir
    )
    score_results = []
    score_parse_ok = False
    if rc in (0, 1) and stdout.strip():
        try:
            score_result = json.loads(stdout.strip())
            info(f"Score result: {json.dumps(score_result, ensure_ascii=False, indent=2)}")
            score_results = score_result.get("gates", [])
            score_parse_ok = bool(score_results)
        except json.JSONDecodeError:
            info(f"Score output:\n{stdout}")
    else:
        warn(f"scorer did not return JSON output (rc={rc})")
        if stdout.strip():
            print(stdout)
    if strict and not score_parse_ok:
        verify_ok = False
        error("STRICT: scorer did not return parseable gates JSON")

    if score_results:
        info("Write scores back to state.json...")
        for gate_result in score_results:
            if "error" in gate_result:
                continue
            dim = gate_result.get("dimension", "")
            value = gate_result.get("value")
            # T5: kpi_target  score Medium,  iterations[].scores MediumValue KPI
            if dim == "kpi_target" and isinstance(value, bool):
                continue
            if dim and value is not None:
                _, wrc = run_tool(
                    "autoloop-state.py",
                    ["update", work_dir, f"iterations[-1].scores.{dim}", str(value)],
                    capture=True,
                    work_dir=work_dir,
                )
                if wrc != 0:
                    warn(f"failed to write scores back: {dim}={value}")
                    if strict:
                        verify_ok = False

    if score_results:
        info("updateGateStatus...")
        state_fresh = load_state(work_dir)
        plan_gates = get_gates(state_fresh)
        for idx, gate_def in enumerate(plan_gates):
            for gate_result in score_results:
                if _plan_gate_matches_score_result(gate_def, gate_result):
                    current_val = gate_result.get("value")
                    passed = gate_result.get("pass", False)
                    gd0 = gate_def.get("dim") or gate_def.get("dimension", "")
                    if gd0 == "kpi_target" and isinstance(current_val, bool):
                        numeric = get_current_scores(state_fresh).get("kpi_target")
                        current_val = numeric
                    if current_val is not None:
                        run_tool(
                            "autoloop-state.py",
                            [
                                "update",
                                work_dir,
                                f"plan.gates[{idx}].current",
                                str(current_val),
                            ],
                            capture=True,
                            work_dir=work_dir,
                        )
                        status_label = "Pass" if passed else "Fail"
                        run_tool(
                            "autoloop-state.py",
                            [
                                "update",
                                work_dir,
                                f"plan.gates[{idx}].status",
                                status_label,
                            ],
                            capture=True,
                            work_dir=work_dir,
                        )
                    break

    # T5: score  kpi_target Returns bool,  iterations[].scores;  plan.gates Value
    # For T5, iterations[-1].scores must be the source of truth; use get_current_scores so gate fallback does not hide KPI mismatches.
    state_post = load_state(work_dir)
    if get_template(state_post) == "T5":
        iters = state_post.get("iterations") or []
        raw_sc = (iters[-1].get("scores") or {}) if iters else {}
        kt = raw_sc.get("kpi_target")
        if not isinstance(kt, (int, float)):
            for g in get_gates(state_post):
                gd = g.get("dim") or g.get("dimension", "")
                if gd != "kpi_target":
                    continue
                cur = g.get("current")
                if isinstance(cur, (int, float)):
                    merged = dict(raw_sc)
                    merged["kpi_target"] = float(cur)
                    run_tool(
                        "autoloop-state.py",
                        [
                            "update",
                            work_dir,
                            "iterations[-1].scores",
                            json.dumps(merged, ensure_ascii=False),
                        ],
                        capture=True,
                        work_dir=work_dir,
                    )
                break

    val_args = [work_dir]
    if strict:
        val_args.append("--strict")
    info("Run validator...")
    _, val_rc = run_tool(
        "autoloop-validate.py", val_args, capture=True, work_dir=work_dir
    )
    if strict and val_rc != 0:
        verify_ok = False
        error("STRICT: autoloop-validate ")
        _metadata_set_last_error(work_dir, "autoloop-validate.py", val_rc)

    tsv_path = os.path.join(work_dir, "autoloop-results.tsv")
    if os.path.exists(tsv_path):
        info("Run variance check...")
        _, var_rc = run_tool(
            "autoloop-variance.py", ["check", tsv_path], capture=True, work_dir=work_dir
        )
        if strict and var_rc != 0:
            verify_ok = False
            error("STRICT: autoloop-variance check ")
            _metadata_set_last_error(work_dir, "autoloop-variance.py", var_rc)
    else:
        info("TSV filedoes not exist, check")

    info("Render output files...")
    run_tool("autoloop-render.py", [work_dir], work_dir=work_dir)

    prompt_block("Append TSV record", f"""\
        pleasethis roundScore result, Call:
          autoloop-state.py add-tsv-row {work_dir} '<JSON>'

        JSON Field: iteration, phase, status, dimension, metric_value, delta,
                   strategy_id, action_summary, side_effect, evidence_ref,
                   unit_id, protocol_version, score_variance, confidence, details

        add-tsv-row  TSV rulesvariance/confidence validation; please.
    """)

    return verify_ok


def _manifest_stagnation_max_explore(template_key):
    raw = _MANIFEST.get("stagnation_max_explore") or {}
    n = raw.get(template_key)
    try:
        return int(n) if n is not None and int(n) > 0 else None
    except (TypeError, ValueError):
        return None


def _stagnation_max_explore_apply(work_dir, state, stag, decision, reasons):
    """manifest.stagnation_max_explore: stagnation trackingrecordStrategy,  pause(T5/T7/T8)."""
    tpl = get_template(state)
    limit = _manifest_stagnation_max_explore(tpl)
    if not limit:
        return decision, reasons
    stagnating = [x for x in (stag or []) if len(x) > 2 and x[2] == "stagnating"]
    meta_key = "stagnation_explore_switches"

    def _read_count(st):
        return int((st.get("metadata") or {}).get(meta_key) or 0)

    if not stagnating:
        if _read_count(state) != 0:
            def _zero(st):
                st.setdefault("metadata", {})[meta_key] = 0

            _record_state_metadata(work_dir, _zero)
        return decision, reasons

    count = _read_count(state)
    iters = state.get("iterations") or []
    if len(iters) >= 2:
        p = ((iters[-2].get("strategy") or {}).get("strategy_id") or "").strip()
        c = ((iters[-1].get("strategy") or {}).get("strategy_id") or "").strip()
        if c and c != p:
            count += 1

            def _set(st):
                st.setdefault("metadata", {})[meta_key] = count

            _record_state_metadata(work_dir, _set)
    if count >= limit and decision == "continue":
        return "pause", reasons + [
            " manifest stagnation_max_explore={}(stagnation tracking strategy_id ={}), "
            "Please adjust the target/budget or confirm manually before continuing".format(limit, count)
        ]
    return decision, reasons


def phase_synthesize(work_dir, state, round_num):
    """SYNTHESIZE: Output synthesis prompt(LLM )"""
    banner(round_num, "SYNTHESIZE", "Synthesis")

    scores = get_current_scores(state)
    _, gate_details = check_gates_passed(state)
    passed_count = sum(1 for d in gate_details if d["passed"])
    total_count = len(gate_details)

    prompt_block("Synthesize this round's findings", f"""\
        Synthesize this round's improvement results and update findings:

        Current Scores: {json.dumps(scores, ensure_ascii=False)}
        Gates Passed: {passed_count}/{total_count}

        :
        1. this roundEffective(which strategies worked and which did not)
        2. update executive_summary.final_scores
        3. recordfindingIssues engineering_issues
        4. update pattern_recognition(Recurring Issues, Bottlenecks)
        5. Evaluate strategy ROI: effort vs payoff

        Call:
          autoloop-state.py add-finding {work_dir} '<JSON>'
    """)


def phase_evolve(work_dir, state, round_num, strict=False):
    """EVOLVE: Automatically check termination conditions"""
    banner(round_num, "EVOLVE", "Termination Condition Evaluation")

    state = load_state(work_dir)
    if _strict_enabled(strict) and not _strict_evolve_requires_findings(state):
        error(
            "STRICT: EVOLVE  findings — SYNTHESIZE  add-finding orwrite findings.rounds"
        )
        return "pause", [
            "STRICT: At least one structured finding is required(iterations[-1].findings or findings.rounds[-1])"
        ]
    if _strict_enabled(strict) and not _strict_evolve_requires_tsv_current_round(
        state, round_num
    ):
        error(
            "STRICT: EVOLVE  TSV  iteration current round {}(please VERIFY this round)".format(
                round_num
            )
        )
        return "pause", [
            "STRICT: results_tsv[-1].iteration andCurrent round or TSV "
        ]

    max_rounds = get_max_rounds(state)
    # if budget.max_rounds=0, get_max_rounds  fallback  manifest default_rounds; record
    raw_max = state.get("plan", {}).get("budget", {}).get("max_rounds", 0)
    if raw_max == 0:
        warn(
            "budget.max_rounds=0,  fallback  manifest default_rounds[{}]={}(recommended to run "
            "autoloop-state.py update <dir> plan.budget.max_rounds {} writeValue)".format(
                get_template(state), max_rounds, max_rounds
            )
        )
    all_passed, gate_details = check_gates_passed(state)
    history = get_score_history(state)
    osc = detect_oscillation(history)
    stag, eligible_stag_dims = detect_stagnation(
        history, get_gates(state), template_key=get_template(state))
    stag_dims = {d for d, _, _ in stag} if stag else set()
    osc_filtered = [x for x in osc if x[0] not in stag_dims]

    decision = "continue"
    reasons = []

    tsv_fc = _latest_tsv_fail_closed(state)
    if tsv_fc and state.get("results_tsv"):
        reasons.append("TSV ≥2 orConfidence fail-closed, Gatesuccessful termination")

    cross_reg, cross_dims = detect_cross_dimension_regression(state)
    if cross_reg:
        reasons.append(
            "Cross-dimension regression: Dimension {} round hard (handoff.impacted_dimensions recommended to declare explicitly; "
            "score)".format(", ".join(cross_dims))
        )
        if decision == "continue":
            decision = "pause"

    # 1. Gate TSV fail-closed →  completion_authority Decision
    if all_passed and gate_details and not tsv_fc:
        tmpl = get_template(state)
        authority = _MANIFEST.get("completion_authority", {}).get(tmpl, "internal")
        if authority == "internal":
            decision = "stop"
            reasons.append("PassTermination(internal authority)")
        elif authority == "human_review":
            decision = "pause"
            reasons.append("GatePass, manual.please Kane keyfindingCompleted.")
        elif authority == "external_validation":
            decision = "pause"
            reasons.append("GatePass, validation(Test/)Completed.")
        else:
            decision = "stop"
            reasons.append("PassTermination(Unknown authority '{}', fallback  internal)".format(authority))
    elif all_passed and gate_details and tsv_fc:
        reasons.append("GateValue,  TSV fail-closed successful termination")

    # 2. budget exhausted(T4 + linear_phases Completed, Avoid OODA Round)
    if round_num >= max_rounds:
        tmpl = get_template(state)
        plan = state.get("plan", {})
        linear_pause = (
            tmpl == "T4"
            and plan.get("template_mode") == "linear_phases"
            and not plan.get("linear_delivery_complete", False)
            and not all_passed
        )
        if linear_pause:
            reasons.append(
                "Max rounds {} reached while T4 template_mode=linear_phases and "
                "plan.linear_delivery_complete=false (update plan.linear_delivery_complete to true "
                "with autoloop-state.py, or increase plan.budget.max_rounds)".format(max_rounds)
            )
            if decision == "continue":
                decision = "pause"
        elif decision != "stop":
            decision = "stop"
            reasons.append(f"Max Rounds {max_rounds}")

    # 3. Oscillation and stagnation signals.
    if len(osc_filtered) >= 2:
        reasons.append(f"Detected {len(osc_filtered)}  dimension oscillations")
        if decision == "continue":
            decision = "pause"

    # 4. Stagnation/Regression(per-dimension)
    if stag:
        regressing = [(d, v, s) for d, v, s in stag if s == 'regressing']
        stagnating = [(d, v, s) for d, v, s in stag if s == 'stagnating']
        if regressing:
            reasons.append(f"Regression: {', '.join(d for d, _, _ in regressing)} — ")
            if decision == "continue":
                decision = "pause"  # Regression is more severe than stagnation; pause immediately
        if stagnating:
            reasons.append(f"Stagnation: {', '.join(d for d, _, _ in stagnating)}")
            stagnating_dims = {d for d, _, _ in stagnating}
            # loop-protocol: the round cannot continue when every eligible dimension is stagnating.
            # If only one eligible dimension exists (for example T5 kpi_target), eligible==stagnating should still trigger stagnation termination.
            if (
                decision == "continue"
                and eligible_stag_dims
                and stagnating_dims == eligible_stag_dims
                and len(eligible_stag_dims) > 1
            ):
                decision = "stop"
                reasons.append(
                    "Cannot continue: all eligible dimensions are blocked by stagnation"
                )
            elif decision == "continue" and len(stagnating_dims) == 1:
                reasons.append("Recommendation: use the DECIDE phase to adjust strategy for the stagnating dimension")

    decision, reasons = _stagnation_max_explore_apply(
        work_dir, state, stag, decision, reasons
    )

    # Output decision
    decision_color = {
        "continue": C_GREEN, "stop": C_RED, "pause": C_YELLOW,
    }.get(decision, C_RESET)
    print(f"\n{C_BOLD}Termination Condition Evaluation Result:{C_RESET}")
    print(f"  Decision: {decision_color}{C_BOLD}{decision.upper()}{C_RESET}")
    for r in reasons:
        print(f"  Reason: {r}")

    # Gate
    if gate_details:
        print(f"\n{'Gate':<20} {'Status':>6} {'Current':>8} {'Target':>8} {'Type':>6}")
        print("─" * 52)
        for d in gate_details:
            status = f"{C_GREEN}PASS{C_RESET}" if d["passed"] else f"{C_RED}FAIL{C_RESET}"
            print(f"  {d['label']:<18} {status:>15} {str(d['current']):>8} {str(d['threshold']):>8} {d['gate']:>6}")

    # P2-13: EVOLVE structured recommendation output
    if decision == "continue":
        failed_dims = [d["label"] for d in gate_details if not d["passed"]] if gate_details else []
        focus_dims = ", ".join(failed_dims[:3]) if failed_dims else "N/A"
        remaining_pct = round((1 - round_num / max_rounds) * 100) if max_rounds > 0 else 0
        info("--- EVOLVE Recommendation ---")
        info("Recommendation: ContinueRound {},  {}".format(round_num + 1, focus_dims))
        info("Rationale: {}".format(", ".join(reasons) if reasons else "continue with the standard strategy"))
        info("Risk: remaining budget {}%".format(remaining_pct))
        info("Alternative: Current, ")
        info("-------------------")

    # P1-05: output a quality assessment summary when the task terminates(ConfidenceMargin)
    if decision in ("stop", "pause") and gate_details:
        print(f"\n{C_BOLD}Scoring Quality Summary (by confidence tier):{C_RESET}")
        print(f"  {'Dimension':<20} {'Current':>8} {'Target':>8} {'Confidence':>10} {'Margin':>6}  {'Confidence Description'}")
        print("  " + "─" * 80)
        needs_review = []
        heuristic_dims = []
        scored_dims = []
        for d in gate_details:
            dim = d.get("dim", d.get("dimension", ""))
            label = d.get("label", dim)
            current = str(d.get("current", "?"))
            target = str(d.get("threshold", "?"))
            confidence, margin = _confidence_for_dim(dim)
            margin_display = "±{:.1f}".format(margin) if margin is not None else "N/A"
            scored_dims.append(label)
            if confidence == "empirical":
                note = ", Highconfidence"
            elif confidence == "heuristic":
                note = "Heuristic, manual review recommended"
                needs_review.append(label)
                heuristic_dims.append(label)
            else:
                note = "Binary verdict, direction only"
                needs_review.append(label)
            print(f"  {label:<20} {current:>8} {target:>8} {confidence:>10} {margin_display:>6}  {note}")
        if needs_review:
            all_heuristic = len(heuristic_dims) == len(scored_dims)
            if all_heuristic:
                print(f"\n  {C_YELLOW}ℹ All dimensions are heuristic scores; this is expected for this template{C_RESET}")
            else:
                print(f"\n  {C_YELLOW}⚠ Manual review recommended for: {', '.join(needs_review)}{C_RESET}")

    _append_evolve_progress_md(work_dir, round_num, decision, reasons, gate_details)

    # P2-04: CostSummary
    print_cost_summary(state)

    return decision, reasons


def print_cost_summary(state):
    """CostSummary(round consumption + subagent call count)."""
    iterations = state.get("plan", {}).get("iterations", [])
    round_count = len(iterations)
    max_rounds = state.get("plan", {}).get("budget", {}).get("max_rounds", "?")

    #  subagent Call
    subagent_count = 0
    for it in iterations:
        act = it.get("act")
        if isinstance(act, dict):
            results = act.get("subagent_results", [])
            if isinstance(results, list):
                subagent_count += len(results)

    info("--- Resource Usage ---")
    info(f"Rounds Used: {round_count}/{max_rounds}")
    info(f"Total Subagent Calls: {subagent_count}")
    info("----------------")


def phase_reflect(work_dir, state, round_num):
    """REFLECT: Output a reflection prompt and update the experience registry"""
    banner(round_num, "REFLECT", "Reflection and Experience Capture")

    state = load_state(work_dir)
    tmpl = get_template(state)
    _maybe_reflect_experience_write(work_dir, state, tmpl)

    history = get_score_history(state)
    prev_scores = history[-2] if len(history) >= 2 else {}
    curr_scores = history[-1] if history else {}

    # changes this round
    deltas = {}
    for dim in set(list(prev_scores.keys()) + list(curr_scores.keys())):
        p = prev_scores.get(dim)
        c = curr_scores.get(dim)
        if isinstance(p, (int, float)) and isinstance(c, (int, float)):
            deltas[dim] = round(c - p, 2)

    # T1 exploration phase(Round 1, no score history yet): reflection summary, Strategy
    t1_early = tmpl == "T1" and round_num <= 1
    if t1_early:
        prompt_block("Reflection and Experience Capture", f"""\
        changes this round: {json.dumps(deltas, ensure_ascii=False)}
        CurrentTemplate: {tmpl}(exploration phase — strategy attribution is optional)

        Reflection Requirements:
        1. this roundkeyfinding？which dimensions？
        2. information sources are high quality？needvalidation？
        3. neednext roundsupplement？
        4. next roundsearchdirectionpriority？

        Experience Capture(Options — fill this if the round produced a clearly reusable strategy):
        - write iterations[-1].reflect(JSON):
          autoloop-state.py update {work_dir} iterations[-1].reflect '{{"strategy_id":"S{round_num:02d}-xxx","effect":"Keep|Avoid|To Validate","delta":0.5,"dimension":"coverage","context":"..."}}'
        - T1 exploration phase strategy_id/effect/delta, reflection summary

        Call:
          autoloop-state.py update {work_dir} findings.lessons_learned.verified_hypotheses '[...]'
    """)
    else:
        prompt_block("Reflection and Experience Capture", f"""\
        changes this round: {json.dumps(deltas, ensure_ascii=False)}
        CurrentTemplate: {tmpl}

        Reflection Requirements:
        1. Strategy This Round？Reason？
        2. findingmethod？
        3. hypothesisvalidationor？
        4. next roundshould？

        Experience Capture(Strategy):
        - [Recommended] write iterations[-1].reflect (JSON). In REFLECT, always call experience write with --score as the delta and optionally rating_1_to_5:
          autoloop-state.py update {work_dir} iterations[-1].reflect '{{"strategy_id":"S{round_num:02d}-xxx","effect":"Keep|Avoid|To Validate","delta":0.5,"rating_1_to_5":4,"dimension":"coverage","context":"..."}}'
        - or manually: autoloop-experience.py {work_dir} write --strategy-id ... --effect ... --score ...
        - scoring semantics → references/quality-gates.md; threshold SSOT → references/gate-manifest.json
        - parameter calibration → references/parameters.md

        Call:
          autoloop-state.py update {work_dir} findings.lessons_learned.verified_hypotheses '[...]'
    """)


# ---------------------------------------------------------------------------
# Main Loop
# ---------------------------------------------------------------------------

def run_init(work_dir, template, goal=""):
    """initialize a new task"""
    os.makedirs(work_dir, exist_ok=True)

    # 1. Call autoloop-state.py init
    args = ["init", work_dir, template]
    if goal:
        args.append(goal)
    _, rc = run_tool("autoloop-state.py", args, work_dir=work_dir)
    if rc != 0:
        error("initialization failed")
        sys.exit(1)

    # 2.  state get task_id
    state = load_state(work_dir)
    task_id = state.get("plan", {}).get("task_id", "unknown")

    # 3. create checkpoint
    checkpoint = make_checkpoint(task_id, 0, "OBSERVE", "INIT")
    save_checkpoint(work_dir, checkpoint)

    info(f"Task initialized: {task_id}")
    info(f"Template: {template}")
    info(f"Work Directory: {work_dir}")
    info(f"Next step: autoloop-controller.py {work_dir}")


def run_status(work_dir):
    """show current status"""
    state = load_state(work_dir)
    checkpoint = load_checkpoint(work_dir)

    plan = state.get("plan", {})
    task_id = plan.get("task_id", "unknown")
    template = plan.get("template", "?")
    status = plan.get("status", "?")
    round_num = plan.get("budget", {}).get("current_round", 0)
    max_rounds = get_max_rounds(state)

    print(f"\n{C_BOLD}AutoLoop Task Status{C_RESET}")
    print(f"{'─' * 40}")
    print(f"  Task ID:   {task_id}")
    print(f"  Template:     {template}")
    print(f"  Status:     {status}")
    print(f"  Round:     {round_num}/{max_rounds}")

    if checkpoint:
        print(f"  Checkpoint:   Round {checkpoint.get('current_round', '?')} / {checkpoint.get('current_phase', '?')}")
        print(f"  Last Completed: {checkpoint.get('last_completed_phase', '?')}")
        print(f"  Timestamp:   {checkpoint.get('timestamp', '?')}")

        #  evolve 
        evolve_hist = checkpoint.get("evolve_history", [])
        if evolve_hist:
            print(f"\n  EVOLVE History:")
            for eh in evolve_hist[-5:]:
                print(f"    Round {eh.get('round', '?')}: {eh.get('decision', '?')} — {eh.get('reason', '')}")
    else:
        print(f"  Checkpoint:   None")

    # Current Scores
    scores = get_current_scores(state)
    if scores:
        print(f"\n  Current Scores:")
        for dim, val in sorted(scores.items()):
            print(f"    {dim}: {val}")

    # GateStatus
    all_passed, details = check_gates_passed(state)
    if details:
        passed = sum(1 for d in details if d["passed"])
        print(f"\n  Gate: {passed}/{len(details)} passed {'(all)' if all_passed else ''}")

    le = state.get("metadata", {}).get("last_error")
    if isinstance(le, dict) and le.get("script"):
        print(f"\n  Most Recent Tool Error: {le.get('script')} rc={le.get('returncode')} @ {le.get('time', '')}")

    print()


def run_loop(
    work_dir,
    start_phase=None,
    start_round=None,
    strict=False,
    enforce_strategy_history=False,
    stop_after_phase=None,
):
    """Execute the main loop.strict=True  VERIFY Mediumtask.
    enforce_strategy_history: in DECIDE, enforce strategy_history Avoid constraints against the handoff when AUTOLOOP_ENFORCE_STRATEGY_HISTORY=1.
    stop_after_phase: CompletedPhase( checkpoint.last_completed_phase);  L1 Runner call it in slices.
    ReturnsValue: None budget exhausted | "pause" | "stop" | "abort" | "stop_after"
    """
    state = load_state(work_dir)
    checkpoint = load_checkpoint(work_dir)

    # Determine the starting position
    if start_round is not None:
        round_num = start_round
    elif checkpoint:
        round_num = checkpoint.get("current_round", 1)
    else:
        round_num = 1

    if start_phase is not None:
        phase_start_idx = PHASES.index(start_phase)
    elif checkpoint:
        last = checkpoint.get("last_completed_phase", "INIT")
        if last == "INIT":
            phase_start_idx = 0
        elif last == "REFLECT":
            # previous roundCompleted, enter the next round
            round_num += 1
            phase_start_idx = 0
        elif last in PHASES:
            phase_start_idx = PHASES.index(last) + 1
            if phase_start_idx >= len(PHASES):
                round_num += 1
                phase_start_idx = 0
        else:
            phase_start_idx = 0
    else:
        phase_start_idx = 0

    max_rounds = get_max_rounds(state)
    task_id = state.get("plan", {}).get("task_id", "unknown")

    if not checkpoint:
        checkpoint = make_checkpoint(task_id, round_num, PHASES[phase_start_idx], "INIT")

    info(f"Starting AutoLoop loop: {task_id}")
    info(f"Start: Round {round_num}, Phase {PHASES[phase_start_idx]}")
    info(f"Budget: {max_rounds} rounds")
    print()

    # Main Loop
    while round_num <= max_rounds:
        # roundcreate the iteration when starting from OBSERVE; --stop-after round, 
        # Avoid add-iteration  scores,  ORIENT/VERIFY  kpi_target.
        if phase_start_idx == 0:
            info(f"Automatically creating Round {round_num} iteration record...")
            _, rc = run_tool(
                "autoloop-state.py", ["add-iteration", work_dir], capture=True, work_dir=work_dir
            )
            if rc != 0:
                warn(f"add-iteration returned a non-zero exit code (rc={rc}), it may already exist")
        else:
            info(
                "Resume Round {}:  add-iteration( {} continue)".format(
                    round_num, PHASES[phase_start_idx]
                )
            )

        # update current_round
        run_tool(
            "autoloop-state.py",
            ["update", work_dir, "plan.budget.current_round", str(round_num)],
            capture=True,
            work_dir=work_dir,
        )

        abort_task = False
        for phase_idx in range(phase_start_idx, len(PHASES)):
            phase = PHASES[phase_idx]

            # update checkpoint: CurrentPhase
            checkpoint["current_round"] = round_num
            checkpoint["current_phase"] = phase
            save_checkpoint(work_dir, checkpoint)

            #  state()
            state = load_state(work_dir)

            # strict validate: checkpoint.current_phase and iterations[-1].phase ()
            it_list = state.get("iterations") or []
            if it_list:
                cur_ph = (it_list[-1].get("phase") or "OBSERVE").strip()
                if cur_ph != phase:
                    run_tool(
                        "autoloop-state.py",
                        ["update", work_dir, "iterations[-1].phase", phase],
                        capture=True,
                        work_dir=work_dir,
                    )
                    state = load_state(work_dir)

            # Phase
            evolve_decision = None
            evolve_reasons = []

            if phase == "OBSERVE":
                obs_decision, obs_reasons = phase_observe(work_dir, state, round_num)
                if obs_decision == "pause":
                    print(f"\n{C_BOLD}{C_YELLOW}{'=' * 60}")
                    print(f"  AutoLoop  — Round {round_num}(OBSERVE)")
                    print(f"  Reason: {'; '.join(obs_reasons)}")
                    print(f"  Resume: autoloop-controller.py {work_dir} --resume")
                    print(f"{'=' * 60}{C_RESET}\n")
                    checkpoint["pause_state"] = {
                        "reason": "; ".join(obs_reasons),
                        "required_confirmation": "Continue after completing the T5 KPI",
                        "paused_at": now_iso(),
                    }
                    save_checkpoint(work_dir, checkpoint)
                    return "pause"
            elif phase == "ORIENT":
                phase_orient(work_dir, state, round_num)
            elif phase == "DECIDE":
                phase_decide(
                    work_dir,
                    state,
                    round_num,
                    strict_cli=strict,
                    enforce_strategy_history=enforce_strategy_history,
                )
            elif phase == "ACT":
                act_result = phase_act(work_dir, state, round_num, strict=strict)
                if act_result == "pause":
                    print(f"\n{C_BOLD}{C_YELLOW}{'=' * 60}")
                    print(f"  AutoLoop ACT  — Round {round_num}")
                    print(f"  Reason: ACT phase has no act.records; execution is incomplete")
                    print(f"  Resume: autoloop-controller.py {work_dir} --resume")
                    print(f"{'=' * 60}{C_RESET}\n")
                    checkpoint["pause_state"] = {
                        "reason": "ACT phase missing act.records; resume after execution is completed",
                        "required_confirmation": "Continue after completing the actual execution and writing act.records",
                        "paused_at": now_iso(),
                    }
                    save_checkpoint(work_dir, checkpoint)
                    return "pause"
                elif not act_result:
                    abort_task = True
                else:
                    # ACT→VERIFY :  subagent completion_ratio
                    state = load_state(work_dir)
                    process_act_completion(work_dir, state)
            elif phase == "VERIFY":
                vok = phase_verify(work_dir, state, round_num, strict=strict)
                if strict and not vok:
                    error("AUTOLOOP_STRICT: VERIFY failed; aborting task( SYNTHESIZE)")
                    abort_task = True
            elif phase == "SYNTHESIZE":
                phase_synthesize(work_dir, state, round_num)
            elif phase == "EVOLVE":
                evolve_decision, evolve_reasons = phase_evolve(
                    work_dir, state, round_num, strict=strict
                )
            elif phase == "REFLECT":
                phase_reflect(work_dir, state, round_num)
                # FIX 4: REFLECT Completedauto-render after thisfile
                info("REFLECT auto-render after this...")
                run_tool("autoloop-render.py", [work_dir], work_dir=work_dir)

            _metadata_append_audit(work_dir, "phase_complete", "{} round={}".format(phase, round_num))

            # update checkpoint: PhaseCompleted
            checkpoint["last_completed_phase"] = phase
            save_checkpoint(work_dir, checkpoint)

            if abort_task:
                break

            # EVOLVE decision handling
            if phase == "EVOLVE" and evolve_decision:
                checkpoint.setdefault("evolve_history", []).append({
                    "round": round_num,
                    "decision": evolve_decision,
                    "reason": "; ".join(evolve_reasons),
                })
                save_checkpoint(work_dir, checkpoint)

                if evolve_decision == "stop":
                    print(f"\n{C_BOLD}{C_GREEN}{'=' * 60}")
                    print(f"  AutoLoop loop terminated — Round {round_num}")
                    print(f"  Reason: {'; '.join(evolve_reasons)}")
                    print(f"{'=' * 60}{C_RESET}\n")
                    return "stop"

                if evolve_decision == "pause":
                    print(f"\n{C_BOLD}{C_YELLOW}{'=' * 60}")
                    print(f"  AutoLoop  — Round {round_num}")
                    print(f"  Reason: {'; '.join(evolve_reasons)}")
                    print(f"  Resume: autoloop-controller.py {work_dir} --resume")
                    print(f"{'=' * 60}{C_RESET}\n")
                    checkpoint["pause_state"] = {
                        "reason": "; ".join(evolve_reasons),
                        "required_confirmation": "User confirms continuation or adjusts the strategy",
                        "paused_at": now_iso(),
                    }
                    save_checkpoint(work_dir, checkpoint)
                    return "pause"

            if (
                stop_after_phase
                and phase.upper() == stop_after_phase.strip().upper()
            ):
                info(
                    "--stop-after {}: Phase {} completed and wrote the checkpoint, then exit".format(
                        stop_after_phase, phase
                    )
                )
                return "stop_after"

        if abort_task:
            return "abort"

        # the current round is complete,  phase_start_idx  0(next round OBSERVE Start)
        phase_start_idx = 0
        round_num += 1

    # budget exhausted
    print(f"\n{C_BOLD}{C_RED}{'=' * 60}")
    print(f"  AutoLoop budget exhausted — {round_num - 1} roundCompleted")
    print(f"  Output Best Current ResultResult")
    print(f"{'=' * 60}{C_RESET}\n")
    return None


# ---------------------------------------------------------------------------
# Pipeline Worktree (P3-01 parallel isolation)
# ---------------------------------------------------------------------------


def create_pipeline_worktree(work_dir, template, timestamp=None):
    """Create a Git worktree for a parallel pipeline.

    Returns (worktree_path, branch_name).
    """
    import subprocess
    import time

    ts = timestamp or int(time.time())
    branch = f"autoloop-{template}-{ts}"
    wt_path = os.path.join(work_dir, ".worktrees", branch)
    os.makedirs(os.path.dirname(wt_path), exist_ok=True)
    subprocess.run(
        ["git", "worktree", "add", wt_path, "-b", branch],
        cwd=work_dir,
        check=True,
        capture_output=True,
    )
    info(f"Worktree Created: {wt_path} (branch: {branch})")
    return wt_path, branch


def remove_pipeline_worktree(work_dir, wt_path, branch):
    """Clean up the Git worktree and its temporary branch."""
    import subprocess

    result = subprocess.run(
        ["git", "worktree", "remove", wt_path],
        cwd=work_dir,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        warn(f"Worktree cleanup failed ({wt_path}): {result.stderr.strip()}")
    subprocess.run(
        ["git", "branch", "-d", branch],
        cwd=work_dir,
        capture_output=True,
    )
    info(f"Worktree cleaned up: {branch}")


def merge_pipeline_worktree(work_dir, branch):
    """Merge a parallel pipeline worktree branch.

    Returns True if merge succeeded, False if conflicts require manual resolution.
    """
    import subprocess

    result = subprocess.run(
        ["git", "merge", "--no-ff", branch, "-m",
         f"AutoLoop pipeline merge: {branch}"],
        cwd=work_dir,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        warn(f"Worktree merge conflict: {branch}. Manual resolution required.")
        warn(f"  stderr: {result.stderr.strip()}")
        return False
    info(f"Worktree branch merged: {branch}")
    return True


# ---------------------------------------------------------------------------
# CLI Entry
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    work_dir = os.path.abspath(sys.argv[1])

    # Parse command-line arguments
    args = sys.argv[2:]
    mode = "run"
    template = None
    goal = ""

    cli_strict = False
    cli_enforce_strategy_history = False
    stop_after_phase = None
    cli_exit_codes = False
    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "--init":
            mode = "init"
        elif arg == "--resume":
            mode = "resume"
        elif arg == "--status":
            mode = "status"
        elif arg == "--strict":
            cli_strict = True
        elif arg == "--enforce-strategy-history":
            cli_enforce_strategy_history = True
        elif arg == "--exit-codes":
            cli_exit_codes = True
        elif arg == "--stop-after" and i + 1 < len(args):
            stop_after_phase = args[i + 1]
            i += 1
        elif arg == "--template" and i + 1 < len(args):
            template = args[i + 1]
            i += 1
        elif arg == "--goal" and i + 1 < len(args):
            goal = args[i + 1]
            i += 1
        else:
            # Treat unknown arguments as part of the goal
            if mode == "init" and not goal:
                goal = arg
        i += 1

    def _apply_exit(outcome):
        use_codes = cli_exit_codes or os.environ.get(
            "AUTOLOOP_EXIT_CODES", ""
        ).strip().lower() in ("1", "true", "yes")
        if not use_codes:
            return
        if outcome == "pause":
            sys.exit(10)
        if outcome == "abort":
            sys.exit(1)
        sys.exit(0)

    if stop_after_phase:
        s = stop_after_phase.strip().upper()
        if s not in PHASES:
            error("--stop-after must be one of: {}".format(", ".join(PHASES)))
            sys.exit(1)
        stop_after_phase = s

    if mode == "init":
        if not template:
            error("--init mode requires the --template argument")
            sys.exit(1)
        run_init(work_dir, template, goal)

    elif mode == "status":
        run_status(work_dir)

    elif mode == "resume":
        checkpoint = load_checkpoint(work_dir)
        if not checkpoint:
            error(f"checkpoint not found: {os.path.join(work_dir, CHECKPOINT_FILE)}")
            sys.exit(1)
        # clear paused status
        if checkpoint.get("pause_state"):
            info("clear paused status, continue the loop")
            checkpoint["pause_state"] = None
            save_checkpoint(work_dir, checkpoint)
        outcome = run_loop(
            work_dir,
            strict=_strict_enabled(cli_strict),
            enforce_strategy_history=cli_enforce_strategy_history,
            stop_after_phase=stop_after_phase,
        )
        _apply_exit(outcome)

    elif mode == "run":
        if not os.path.exists(os.path.join(work_dir, STATE_FILE)):
            error(f"Statusfiledoes not exist: {os.path.join(work_dir, STATE_FILE)}")
            error("Run --init first to initialize the task")
            sys.exit(1)
        outcome = run_loop(
            work_dir,
            strict=_strict_enabled(cli_strict),
            enforce_strategy_history=cli_enforce_strategy_history,
            stop_after_phase=stop_after_phase,
        )
        _apply_exit(outcome)

    else:
        error(f"unknown mode: {mode}")
        sys.exit(1)


if __name__ == "__main__":
    main()
