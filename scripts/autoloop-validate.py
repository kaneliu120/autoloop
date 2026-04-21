#!/usr/bin/env python3
"""AutoLoop Cross-file validator — SSOT JSON preferred, markdown fallback

Usage:
  autoloop-validate.py <work_dir>          Verify data consistency
  autoloop-validate.py <work_dir> --json   JSON output
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

# --- constants ---

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
    """Return True when AUTOLOOP_VALIDATE_STRICT=1 upgrades selected warnings to errors."""
    return os.environ.get("AUTOLOOP_VALIDATE_STRICT", "").strip().lower() in (
        "1", "true", "yes",
    )


# ============================================================
# SSOT JSON mode validation
# ============================================================

def validate_json(work_dir, strict=False):
    """Run full validation from autoloop-state.json and return (errors, warnings).

    strict: treat contract and phase-artifact gaps as errors instead of warnings.
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
    """Verify that all required top-level fields exist."""
    required_keys = ["plan", "iterations", "findings", "results_tsv", "metadata"]
    for key in required_keys:
        if key not in state:
            errors.append("JSON Top level field missing: '{}'".format(key))


def _check_primary_key_consistency(state, errors):
    """Ensure strategy IDs used by iterations and TSV rows are defined in findings or strategy history."""
    findings_strategy_ids = set()
    for rnd in state.get("findings", {}).get("rounds", []):
        for finding in rnd.get("findings", []):
            sid = finding.get("strategy_id", "")
            if sid and STRATEGY_RE.match(sid):
                findings_strategy_ids.add(sid)

    # from strategy_evaluations
    for ev in state.get("findings", {}).get("strategy_evaluations", []):
        sid = ev.get("strategy_id", "")
        if sid and STRATEGY_RE.match(sid):
            findings_strategy_ids.add(sid)

    # from plan.strategy_history (supplementary source of known strategies)
    known_strategy_ids = set(findings_strategy_ids)
    for sh in state.get("plan", {}).get("strategy_history", []):
        sid = sh.get("strategy_id", "") if isinstance(sh, dict) else str(sh)
        if sid and STRATEGY_RE.match(sid):
            known_strategy_ids.add(sid)

    def _check_sid_defined(label, idx, sid):
        if STRATEGY_RE.match(sid):
            if sid not in known_strategy_ids:
                errors.append(
                    "{} {}: strategy_id '{}' is missing from findings/strategy_history".format(
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
                        "{} {}: multi child '{}' is missing from findings/strategy_history".format(
                            label, idx, comp
                        )
                    )
            return
        errors.append(
            "{} {}: invalid strategy_id '{}' (expected SNN-description or multi:{{...}})".format(
                label, idx, sid
            )
        )

    #  iteration  strategy_id
    for i, it in enumerate(state.get("iterations", []), start=1):
        sid = it.get("strategy", {}).get("strategy_id", "")
        if not sid or sid in ("—", "baseline", ""):
            continue
        _check_sid_defined("Round", i, sid)

    #  results_tsv in strategy_id
    for row_idx, row in enumerate(state.get("results_tsv", []), start=1):
        sid = row.get("strategy_id", "").strip()
        if not sid or sid in ("—", "baseline", ""):
            continue
        _check_sid_defined("TSV Row", row_idx, sid)


def _check_dimension_consistency(state, errors, warnings):
    """Check consistency between plan dimensions/gates and iteration score dimensions."""
    plan_dims = set()
    for d in state.get("plan", {}).get("dimensions", []):
        if isinstance(d, dict):
            plan_dims.add(d.get("name", d.get("dimension", "")))
        elif isinstance(d, str):
            plan_dims.add(d)

    # from gates (dim  dimension  scorer )
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
            "Dimension '{}' is used in iterations.scores but missing from plan.dimensions/gates".format(dim)
        )

    unused = plan_dims - used_dims
    if unused and state.get("iterations"):
        for dim in sorted(unused):
            if non_exempt_gate_dims and dim not in non_exempt_gate_dims:
                continue
            warnings.append(
                "Dimension '{}' is defined but never appears in iteration scores".format(dim)
            )


# Raw gate-manifest dimension names differ from scorer internal keys. Using the raw
# names directly in plan.gates can create split verdicts.
_MANIFEST_RAW_SCORER_DIMS = frozenset({
    "syntax_errors", "p1_count", "security", "reliability", "maintainability",
})


def _check_plan_gates_contract(state, warnings, errors, strict):
    """Validate the plan.gates contract against scorer expectations."""
    gates = state.get("plan", {}).get("gates", [])
    if not gates:
        return
    for i, g in enumerate(gates):
        if plan_gate_is_exempt(g):
            continue
        dim = g.get("dim") or g.get("dimension", "")
        if "manifest_dimension" not in g:
            msg = (
                "plan.gates[{}] is missing manifest_dimension (recommended by init and references/loop-data-schema.md)".format(i)
            )
            (errors if strict else warnings).append(msg)
        if g.get("dimension") and not g.get("dim"):
            msg = (
                "plan.gates[{}] uses legacy field 'dimension' but is missing canonical field 'dim'".format(i)
            )
            (errors if strict else warnings).append(msg)
        if dim in _MANIFEST_RAW_SCORER_DIMS:
            msg = (
                "plan.gates[{}].dim='{}' uses a raw gate-manifest name that does not match autoloop-score internal keys; this may cause split judgments".format(i, dim)
            )
            (errors if strict else warnings).append(msg)


def _side_effect_text_covers_dimension(side_effect_lower, dim):
    """Return True when a row side_effect string clearly covers the target dimension."""
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
    """P-03: validate cross-dimensional handoff declarations against TSV side_effect text."""
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
    if se in ("None", "—", "-", "", "none", "n/a"):
        msg = (
            "Row results_tsv.side_effect '{}' does not cover plan.decide_act_handoff impacted_dimensions/"
            "target_dimensions; fill in the actual cross-dimensional impact or remove the handoff declaration".format(
                last.get("side_effect") or "empty"
            )
        )
        (errors if strict else warnings).append(msg)
        return

    dims = impacted if isinstance(impacted, list) else [impacted]
    missing = [d for d in dims if not _side_effect_text_covers_dimension(se, d)]
    if missing:
        msg = (
            "Row side_effect does not cover the handoff-declared dimensions (each dimension name or an underscore-separated token of length >=3 must appear): {}".format(
                ", ".join(str(x) for x in missing)
            )
        )
        (errors if strict else warnings).append(msg)


def _check_phase_artifacts(work_dir, state, errors, warnings, strict):
    """Check minimum required phase artifacts for the latest iteration."""
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

    # ACT: require a canonical strategy_id in decide_act_handoff or the current iteration.
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
                "phase={} but lacks an effective strategy_id (expected in plan.decide_act_handoff.strategy_id "
                "or iterations[-1].strategy.strategy_id; accepted formats: SNN-... or multi:{{SNN+SNN}})".format(
                    phase
                )
            )

    # VERIFY :  scores(Prevent idling in later stages)
    verify_idx = PHASES.index("VERIFY")
    late_post_verify = {"SYNTHESIZE", "EVOLVE", "REFLECT"}
    if phase in late_post_verify and phase_idx > verify_idx and not last.get("scores"):
        _emit(
            " phase={}  iterations[-1].scores empty(Completed VERIFY )".format(phase)
        )

    # REFLECT: It is recommended to have a structured reflect( experience write); strict  strategy_id + effect(E-01)
    if phase == "REFLECT":
        ref = last.get("reflect")
        if strict:
            if not isinstance(ref, dict):
                errors.append(
                    " phase=REFLECT  iterations[-1].reflect  JSON (strict  dict)"
                )
            else:
                sid = (ref.get("strategy_id") or "").strip()
                eff = (ref.get("effect") or "").strip()
                if not sid or not eff:
                    errors.append(
                        " phase=REFLECT  strict  iterations[-1].reflect empty "
                        "strategy_id  effect( write)"
                    )
                else:
                    dval = ref.get("delta", None)
                    has_delta = dval is not None and dval != ""
                    has_likert = ref.get("rating_1_to_5") not in (None, "")
                    sc = ref.get("score")
                    leg_likert = isinstance(sc, int) and 1 <= sc <= 5
                    if not (has_delta or has_likert or leg_likert):
                        errors.append(
                            "REFLECT strict requires reflect to include delta, "
                            "rating_1_to_5, or legacy Likert (score 1-5)"
                        )
        elif not isinstance(ref, dict) or not any(
            (ref.get(k) not in (None, "", [], {}))
            for k in ("strategy_id", "effect", "lesson_learned", "score", "dimension", "context")
        ):
            _emit(
                " phase=REFLECT  iterations[-1].reflect Empty or unstructured(recommended JSON: strategy_id/effect/...)"
            )

    # checkpoint.json  SSOT  phase Prompt when inconsistent(Commonly used in manual modification state Unsynchronized breakpoints)
    ck_path = os.path.join(work_dir, "checkpoint.json")
    if os.path.isfile(ck_path):
        try:
            with open(ck_path, "r", encoding="utf-8") as f:
                ck = json.load(f)
            ck_phase = (ck.get("current_phase") or "").strip()
            if ck_phase and ck_phase in PHASES and ck_phase != phase:
                msg = (
                    "checkpoint.current_phase={}  iterations[-1].phase={} inconsistent( checkpoint  state)".format(
                        ck_phase, phase
                    )
                )
                (errors if strict else warnings).append(msg)
        except (OSError, ValueError, TypeError):
            pass


def _check_findings_canonical_fields(state, warnings):
    """Warn when findings skip canonical fields or duplicate summary/content text."""
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
                    "findings.rounds[{}].findings[{}] has no summary/content/description; "
                    "rendering and scoring may skip this entry".format(ri, fi)
                )
            elif has_s and has_c:
                warnings.append(
                    "findings.rounds[{}].findings[{}] includes both summary and content; "
                    "prefer canonical field order summary -> content -> description".format(ri, fi)
                )


def _check_tsv_completeness(state, errors):
    """TSV Row: Each line must have all 15 columns, iteration numbering"""
    tsv_rows = state.get("results_tsv", [])
    seen_iterations = set()

    for row_idx, row in enumerate(tsv_rows, start=1):
        # Check required columns
        missing_cols = [col for col in TSV_COLUMNS if col not in row]
        if missing_cols:
            errors.append(
                "TSV Row {}: missingcolumns {}".format(row_idx, ", ".join(missing_cols))
            )

        #  iteration numbering
        it_val = row.get("iteration", "")
        if isinstance(it_val, int):
            seen_iterations.add(it_val)
        elif isinstance(it_val, str) and it_val.isdigit():
            seen_iterations.add(int(it_val))

    #  iteration number continuity
    if seen_iterations:
        max_it = max(seen_iterations)
        for expected in range(1, max_it + 1):
            if expected not in seen_iterations:
                errors.append(
                    "TSV iteration Numbering is not consecutive: missing {} ".format(expected)
                )


def _check_iteration_sequence(state, errors):
    """Iteration round number continuity"""
    iterations = state.get("iterations", [])
    for i, it in enumerate(iterations, start=1):
        actual_round = it.get("round", None)
        if actual_round is not None and actual_round != i:
            errors.append(
                "iterations[{}].round = {},  {}".format(i - 1, actual_round, i)
            )


def _check_phase_sequence(state, errors, warnings):
    """columns:  iteration The stages of history must be followed PHASES order"""
    for i, it in enumerate(state.get("iterations", []), start=1):
        current_phase = it.get("phase", "")
        status = it.get("status", "")

        if not current_phase:
            continue

        if current_phase not in PHASES:
            errors.append(
                "Round {}: unknown '{}'(valid values: {})".format(i, current_phase, ", ".join(PHASES))
            )
            continue

        # for completed rounds, phase  REFLECT
        if status in ("Completed",) and current_phase != "REFLECT":
            warnings.append(
                "Round {}:  '{}' But the stage remains at '{}'( REFLECT)".format(i, status, current_phase)
            )

        # Check phase data filling: The stages that have passed should have data
        phase_idx = PHASES.index(current_phase)
        for j in range(phase_idx + 1):
            phase_key = PHASES[j].lower()
            phase_data = it.get(phase_key, {})
            if isinstance(phase_data, dict) and not any(
                v for v in phase_data.values()
                if v and v != 0 and v != "None" and v != "To Validate"
            ):
                # Empty stage data is just a warning, errors
                pass


def _check_gate_status(state, errors, warnings):
    """Check whether plan.gates[].current matches the latest iteration scores."""
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
            # Tolerate type differences when comparing(str vs int/float)
            try:
                if float(gate_current) != float(score_val):
                    warnings.append(
                        "Gate '{}': plan.gates.current={} is inconsistent with iterations[-1].scores.{}={}".format(
                            dim, gate_current, dim, score_val
                        )
                    )
            except (ValueError, TypeError):
                if str(gate_current) != str(score_val):
                    warnings.append(
                        "Gate '{}': plan.gates.current={} is inconsistent with iterations[-1].scores.{}={}".format(
                            dim, gate_current, dim, score_val
                        )
                    )


def _check_budget(state, errors, warnings):
    """Check that iteration count does not exceed plan.budget.max_rounds."""
    budget = state.get("plan", {}).get("budget", {})
    max_rounds = budget.get("max_rounds", 0)
    current_round = budget.get("current_round", 0)
    iters = state.get("iterations") or []
    n_iterations = len(iters)

    if max_rounds and max_rounds > 0:
        if n_iterations > max_rounds:
            errors.append(
                ": Row {} ,  {} ".format(n_iterations, max_rounds)
            )

    # OODA Round:  iteration.round ( ±1: add-iteration  round, controller  budget)
    if n_iterations > 0:
        last_r = iters[-1].get("round")
        if last_r is not None and abs(last_r - current_round) >= 2:
            warnings.append(
                "budget.current_round={}  iterations[-1].round={} (≥2)".format(
                    current_round, last_r
                )
            )


def _check_version_consistency(state, errors):
    """version consistency: metadata.protocol_version  TSV Row"""
    meta_version = state.get("metadata", {}).get("protocol_version", "")
    if not meta_version:
        errors.append("metadata.protocol_version not set")
        return

    for row_idx, row in enumerate(state.get("results_tsv", []), start=1):
        row_version = row.get("protocol_version", "")
        if row_version and row_version not in ("—", "") and row_version != meta_version:
            errors.append(
                "TSV Row {}: protocol_version='{}'  metadata.protocol_version='{}' inconsistent".format(
                    row_idx, row_version, meta_version
                )
            )


# ============================================================
# Markdown fallback(Keep original logic, )
# ============================================================

def validate_markdown(work_dir):
    """from markdown File performs cross-file primary key verification, return (errors, warnings) list"""
    errors = []
    warnings = []

    # Check required documents
    missing = []
    for key, fname in MD_FILES.items():
        if not os.path.exists(os.path.join(work_dir, fname)):
            missing.append(fname)
    if missing:
        return ["missing: {}".format(", ".join(missing))], []

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

        # strategy_id (P3-06 multi:  ≥2  SNN-)
        if sid and sid not in ("—", "baseline"):
            if STRATEGY_RE.match(sid):
                if sid not in f_strategies:
                    errors.append(
                        "Row{}: strategy_id '{}'  findings.md in".format(ln, sid)
                    )
            elif is_multi_strategy_id(sid):
                ok_m, msg = validate_multi_strategy_id(sid)
                if not ok_m:
                    errors.append("Row{}: {}".format(ln, msg))
                else:
                    for comp in parse_multi_strategy_components(sid):
                        if comp not in f_strategies:
                            errors.append(
                                "Row{}: multi  '{}'  findings.md in".format(
                                    ln, comp
                                )
                            )
                    sef = row.get("side_effect", "").strip()
                    if "" not in sef and "" not in sef:
                        warnings.append(
                            "Row{}: multi: recommended side_effect Indicate mixed attribution(loop-protocol)".format(ln)
                        )
            else:
                errors.append(
                    "Row{}: strategy_id errors: '{}' ( SNN-  multi:{{...}})".format(
                        ln, sid
                    )
                )

        # evidence_ref -> problem_id 
        if evi and evi != "—":
            for pid in re.findall(r"[A-Z]\d{3}", evi):
                if pid not in f_problems:
                    errors.append(
                        "Row{}: evidence_ref  '{}'  findings.md in".format(ln, pid)
                    )

        # iteration 
        if it and it.isdigit() and p_iterations and it not in p_iterations:
            errors.append(
                "Row{}: iteration {}  progress.md There is no corresponding round record in the title".format(ln, it)
            )

        # dimension 
        if dim and dim not in ("—", "score") and known_dims and dim not in known_dims:
            errors.append(
                "Row{}: dimension '{}' Not in the set of known dimensions ({})".format(
                    ln, dim, ", ".join(sorted(known_dims))
                )
            )

    return errors, warnings


def _parse_tsv(path):
    """ results.tsv, Return list of rows(dict)"""
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for i, row in enumerate(reader, start=2):
            row["_line"] = i
            rows.append(row)
    return rows


def _extract_ids_from_findings(path):
    """from findings.md  problem_id  strategy_id """
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    problem_ids = set(re.findall(r"\b([A-Z]\d{3})\b", text))
    strategy_ids = set(re.findall(r"\b(S\d{2}-[\w-]+)", text))
    return problem_ids, strategy_ids


def _extract_iterations_from_progress(path):
    """from progress.md Extract from title iteration numbering"""
    iterations = set()
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("#"):
                nums = re.findall(r"(?:iteration|Round|)\s*(\d+)", line, re.IGNORECASE)
                iterations.update(nums)
    return iterations


def _extract_dimensions_from_gates(work_dir):
    """from plan.md  quality-gates.md Extract dimension name"""
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
                    if dim and dim != "Dimension":
                        dims.add(dim)
    return dims


# ============================================================
# P2-17: OODA output Schema 
# ============================================================

PHASE_SCHEMAS = {
    "observe": {"required": ["current_scores", "target_scores", "remaining_budget_pct", "focus_dimensions"]},
    "decide": {"required": ["strategy_id", "action_plan", "fallback", "impacted_dimensions"]},
    "act": {"required": ["subagent_results", "completion_ratio"]},
    "verify": {"required": ["scores", "regression_detected"]},
}


def validate_phase_output(work_dir, phase, strict=False):
    """ OODA Whether the stage's output contains required fields.return (errors, warnings)."""
    phase = phase.lower()
    if phase not in PHASE_SCHEMAS:
        return ["unknown: '{}' (valid values: {})".format(phase, ", ".join(sorted(PHASE_SCHEMAS)))], []

    path = os.path.join(work_dir, STATE_FILE)
    if not os.path.isfile(path):
        return ["not found {}".format(STATE_FILE)], []

    with open(path, "r", encoding="utf-8") as f:
        state = json.load(f)

    iterations = state.get("iterations", [])
    if not iterations:
        return ["No iteration data, Unable to verify stage output"], []

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
        # DECIDE  plan.decide_act_handoff  iterations[-1].strategy
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
        msg = " {} The output is missing a required field: {}".format(phase.upper(), ", ".join(missing))
        if strict:
            errors.append(msg)
        else:
            warnings.append(msg)

    return errors, warnings


# ============================================================
# entry
# ============================================================

def validate(work_dir, strict=False):
    """Automatically select validation mode and return (errors, warnings, mode)."""
    json_path = os.path.join(work_dir, STATE_FILE)

    if os.path.exists(json_path):
        errors, warnings = validate_json(work_dir, strict=strict)
        return errors, warnings, "json"
    else:
        errors, warnings = validate_markdown(work_dir)
        return errors, warnings, "markdown"


def format_text(errors, warnings, mode):
    """Format results as human-readable text."""
    lines = []
    lines.append("Mode: {} ({})".format(
        "SSOT JSON" if mode == "json" else "Markdown fallback",
        STATE_FILE if mode == "json" else "4 markdown files",
    ))

    if errors:
        lines.append("FAIL: {} errors".format(len(errors)))
        for e in errors:
            lines.append("  [ERROR] {}".format(e))
    else:
        lines.append("PASS: no errors")

    if warnings:
        lines.append("WARN: {} warnings".format(len(warnings)))
        for w in warnings:
            lines.append("  [WARN] {}".format(w))

    return "\n".join(lines)


def format_json_output(errors, warnings, mode):
    """Format results as JSON."""
    return json.dumps({
        "mode": mode,
        "pass": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "error_count": len(errors),
        "warning_count": len(warnings),
    }, ensure_ascii=False, indent=2)


# ============================================================
# CLI entry
# ============================================================

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: autoloop-validate.py <work_dir> [--json] [--strict] [--phase-output <phase>]")
        print("  Validate autoloop data consistency (SSOT JSON preferred, markdown fallback)")
        print("  --strict  Treat contract and stage-artifact issues as errors; AUTOLOOP_VALIDATE_STRICT=1 also enables this")
        print("  --phase-output <phase>  Validate OODA output schema (observe/decide/act/verify)")
        sys.exit(1)

    work_dir = sys.argv[1]
    use_json_output = "--json" in sys.argv
    strict_cli = "--strict" in sys.argv
    strict = strict_cli or _validation_strict_default()

    if not os.path.isdir(work_dir):
        print("ERROR: Directory does not exist: {}".format(work_dir))
        sys.exit(1)

    # P2-17: --phase-output 
    phase_output = None
    if "--phase-output" in sys.argv:
        po_idx = sys.argv.index("--phase-output")
        if po_idx + 1 < len(sys.argv):
            phase_output = sys.argv[po_idx + 1]
        else:
            print("ERROR: --phase-output requires a stage name (observe/decide/act/verify)")
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
