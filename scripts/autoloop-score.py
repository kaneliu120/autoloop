#!/usr/bin/env python3
"""AutoLoop multi-template scorer — supports dual SSOT JSON + markdown modes

Usage:
  autoloop-score.py <Work Directory>              Score from SSOT JSON()or markdown 
  autoloop-score.py <file>              Pattern,  findings.md
  autoloop-score.py <Work Directory> --json       JSON 
"""

import json
import os
import re
import sys
import urllib.parse

_score_dir = os.path.dirname(os.path.abspath(__file__))
if _score_dir not in sys.path:
    sys.path.insert(0, _score_dir)

from autoloop_kpi import (
    kpi_row_satisfied,
    plan_gate_is_exempt,
    results_tsv_last_row_fail_closed,
)

# ---------------------------------------------------------------------------
# Gate Definitions —  gate-manifest.json(SSOT)
# ---------------------------------------------------------------------------

# manifest dimension → scorer internal dim (handling naming differences)
_MANIFEST_DIM_MAP = {
    "security": "security_score",
    "reliability": "reliability_score",
    "maintainability": "maintainability_score",
    "p1_count": "p1_all",
    "syntax_errors": "syntax",
}

# manifest dimension → English label
_MANIFEST_LABEL_MAP = {
    "coverage": "Coverage",
    "credibility": "Credibility",
    "consistency": "Consistency",
    "completeness": "Completeness",
    "bias_check": "Bias Check",
    "sensitivity": "Sensitivity Analysis",
    "kpi_target": "KPI Met",
    "pass_rate": "Pass Rate",
    "avg_score": "Average Score",
    "syntax_errors": "Syntax Validation",
    "p1_p2_issues": "P1/P2 Issues",
    "service_health": "Service Health",
    "user_acceptance": "Manual Acceptance",
    "security": "Security",
    "reliability": "Reliability",
    "maintainability": "Maintainability",
    "p1_count": "P1Issues(Dimension)",
    "security_p2": "Security P2 Issues",
    "reliability_p2": "ReliabilityP2Issues",
    "maintainability_p2": "MaintainabilityP2Issues",
    "architecture": "Architecture",
    "performance": "Performance",
    "stability": "Stability",
    # T3 
    "design_completeness": "Design Completeness",
    "feasibility_score": "Technical Feasibility",
    "requirement_coverage": "Requirement Coverage",
    "scope_precision": "Scope Precision",
    "validation_evidence": "Validation Evidence",
}

# manifest unit → scorer unit 
_MANIFEST_UNIT_MAP = {
    "%": "%",
    "/10": "/10",
    "bool": "bool",
    "count": "count",
    "user_defined": "user_defined",
}


def _load_gate_manifest():
    """Load gate definitions from canonical manifest (SSOT)."""
    manifest_path = os.path.join(os.path.dirname(__file__), "..", "references", "gate-manifest.json")
    with open(manifest_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _manifest_to_scorer_gates(manifest):
    """Convert manifest templates to scorer's internal TEMPLATE_GATES format."""
    result = {}
    for tkey, tdef in manifest["templates"].items():
        gates = []
        for g in tdef["gates"]:
            dim_raw = g["dimension"]
            dim = _MANIFEST_DIM_MAP.get(dim_raw, dim_raw)
            unit = _MANIFEST_UNIT_MAP.get(g["unit"], g["unit"])
            gate_type = g["type"]  # hard/soft
            threshold = g["threshold"]
            label = _MANIFEST_LABEL_MAP.get(dim_raw, dim_raw)
            entry = {
                "dim": dim,
                "manifest_dimension": dim_raw,
                "threshold": threshold,
                "unit": unit,
                "gate": gate_type,
                "label": label,
                "comparator": g.get("comparator", ">="),
            }
            if "llm_grader" in g:
                entry["llm_grader"] = g["llm_grader"]
            gates.append(entry)
        result[tkey] = gates
    return result


_MANIFEST = _load_gate_manifest()
TEMPLATE_GATES = _manifest_to_scorer_gates(_MANIFEST)

# Template(Users may write "T1 Research" instead of "T1")
_TEMPLATE_ALIAS = {}
for _k in TEMPLATE_GATES:
    _TEMPLATE_ALIAS[_k] = _k
    _TEMPLATE_ALIAS[_k.lower()] = _k
_TEMPLATE_ALIAS.update({
    "t1 research": "T1", "t1-research": "T1", "research": "T1",
    "t2 compare": "T2", "t2-compare": "T2", "compare": "T2",
    "t3 design": "T3", "t3-design": "T3", "t3 product design": "T3", "t3-product-design": "T3",
    "t4 deliver": "T4", "t4-deliver": "T4", "deliver": "T4",
    "t5 iterate": "T5", "t5-iterate": "T5", "iterate": "T5",
    "t6 generate": "T6", "t6-generate": "T6", "generate": "T6",
    "t7 quality": "T7", "t7-quality": "T7", "quality": "T7",
    "t8 optimize": "T8", "t8-optimize": "T8", "optimize": "T8",
})


def resolve_template(raw):
    """Template T1-T8 """
    if not raw:
        return None
    key = raw.strip().lower()
    return _TEMPLATE_ALIAS.get(key)


def plan_gates_for_ssot_init(template_raw):
    """Generate plan.gates from the manifest, aligning dim with scorer JSON dimensions / iterations.scores keys.

    Each row includes manifest_dimension so the controller can look up the manifest comparator.
    """
    tkey = resolve_template(template_raw)
    if not tkey:
        tr = (template_raw or "").strip()
        if tr in TEMPLATE_GATES:
            tkey = tr
    tmpl = _MANIFEST.get("templates", {})
    if not tkey or tkey not in tmpl:
        return []
    out = []
    for g in tmpl[tkey]["gates"]:
        dim_raw = g["dimension"]
        dim = _MANIFEST_DIM_MAP.get(dim_raw, dim_raw)
        unit = _MANIFEST_UNIT_MAP.get(g["unit"], g["unit"])
        row = {
            "dim": dim,
            "dimension": dim,
            "manifest_dimension": dim_raw,
            "label": _MANIFEST_LABEL_MAP.get(dim_raw, dim_raw),
            "threshold": g["threshold"],
            "unit": unit,
            "gate": g["type"],
            "comparator": g.get("comparator", ">="),
            "current": None,
            "status": "Fail",
        }
        if g["threshold"] is None:
            row["target"] = None
        out.append(row)
    return out


# =====================================================================
# Mode Detection
# =====================================================================

def detect_mode(path):
    """Determine the scoring mode for an input path.

    Returns ("ssot", state_dict, work_dir)
         ("markdown", content_str, findings_path)
         ("error", message, None)
    """
    if os.path.isdir(path):
        state_path = os.path.join(path, "autoloop-state.json")
        if os.path.exists(state_path):
            with open(state_path, "r", encoding="utf-8") as f:
                state = json.load(f)
            return "ssot", state, path
        # None state.json —  findings.md 
        findings_path = os.path.join(path, "autoloop-findings.md")
        if os.path.exists(findings_path):
            with open(findings_path, "r", encoding="utf-8") as f:
                content = f.read()
            return "markdown", content, findings_path
        return "error", "Medium: autoloop-state.json or autoloop-findings.md not found: {}".format(path), None

    if os.path.isfile(path):
        if path.endswith(".json"):
            with open(path, "r", encoding="utf-8") as f:
                state = json.load(f)
            return "ssot", state, os.path.dirname(path)
        abspath = os.path.abspath(path)
        dir_ = os.path.dirname(abspath) or "."
        state_sidecar = os.path.join(dir_, "autoloop-state.json")
        if os.path.isfile(state_sidecar):
            with open(state_sidecar, "r", encoding="utf-8") as f:
                state = json.load(f)
            return "ssot", state, dir_
        # None SSOT  markdown findings
        with open(abspath, "r", encoding="utf-8") as f:
            content = f.read()
        return "markdown", content, path

    return "error", "path does not exist: {}".format(path), None


# =====================================================================
# SSOT Scoring Engine (primary path)
# =====================================================================

def _get_latest_scores(state):
    """Get the latest score dict from iterations[-1].scores"""
    iterations = state.get("iterations", [])
    if not iterations:
        return {}
    return iterations[-1].get("scores", {})


def _finding_body_text(finding):
    """Return finding text using canonical field priority: summary -> content -> description."""
    if not isinstance(finding, dict):
        return ""
    for k in ("summary", "content", "description"):
        v = finding.get(k)
        if v not in (None, ""):
            return str(v).strip()
    return ""


def _finding_substantive_info_count(finding):
    """Substantive information count per finding (used for strict coverage / completeness rules)."""
    body = _finding_body_text(finding) or ""
    lines = body.split("\n")
    bullets = sum(
        1 for line in lines
        if line.strip().startswith("- ") and len(line.strip()) > 10
    )
    if bullets >= 2:
        return bullets
    paras = sum(
        1 for line in lines
        if line.strip() and len(line.strip()) > 10
        and not line.strip().startswith("#")
        and not line.strip().startswith("|")
    )
    return max(bullets, paras)


def _find_plan_gate_row(plan_gates, dim, manifest_dimension=None):
    """Find the matching plan.gates row by canonical dim or manifest_dimension."""
    if not plan_gates:
        return None
    md = manifest_dimension or dim
    for pg in plan_gates:
        pd = pg.get("dim") or pg.get("dimension", "")
        if pd == dim:
            return pg
        if manifest_dimension and pg.get("manifest_dimension") == md:
            return pg
    return None


def _get_plan_gates(state):
    """Return user-defined gate targets from plan.gates."""
    return state.get("plan", {}).get("gates", [])


def _count_issues_by_severity(state, category=None):
    """Count engineering issues from findings.engineering_issues.

    category: "security" / "reliability" / "maintainability" / "architecture"
              / "performance" / "stability" / None(all)
    Returns {"P1": n, "P2": n, "P3": n}
    """
    eng = state.get("findings", {}).get("engineering_issues", {})
    counts = {"P1": 0, "P2": 0, "P3": 0}

    categories = [category] if category else list(eng.keys())
    for cat in categories:
        issues = eng.get(cat, [])
        for issue in issues:
            sev = issue.get("severity", "P3") if isinstance(issue, dict) else "P3"
            if sev in counts:
                counts[sev] += 1
    return counts


def _count_findings_coverage(state):
    """Count dimensions in findings.rounds that have at least two substantive entries."""
    plan_dims = state.get("plan", {}).get("dimensions", [])
    rounds = state.get("findings", {}).get("rounds", [])
    dim_best = {}
    for rnd in rounds:
        for finding in rnd.get("findings", []):
            dim = finding.get("dimension", "")
            if not dim:
                continue
            n = _finding_substantive_info_count(finding)
            dim_best[dim] = max(dim_best.get(dim, 0), n)
    # Detect: if plan.dimensions are gate dimension names (not research scope),
    # fall back to counting all unique finding dimensions
    template_raw = state.get("plan", {}).get("template", "")
    tkey = resolve_template(template_raw)
    if tkey and tkey in TEMPLATE_GATES and plan_dims:
        gate_dim_names = set()
        for g in TEMPLATE_GATES[tkey]:
            gate_dim_names.add(g["dim"])
            md = g.get("manifest_dimension")
            if md:
                gate_dim_names.add(md)
        # If plan.dimensions are all gate dimension names → not research scope → use fallback
        if set(plan_dims) <= gate_dim_names:
            plan_dims = []

    if plan_dims:
        total = len(plan_dims)
        covered = sum(1 for d in plan_dims if dim_best.get(d, 0) >= 2)
    else:
        if not dim_best:
            return 0, 0
        total = len(dim_best)
        covered = sum(1 for _, n in dim_best.items() if n >= 2)
    return covered, total


def _count_findings_credibility(state):
    """Compute the proportion of findings supported by multiple sources( URL, or/Source)."""
    rounds = state.get("findings", {}).get("rounds", [])
    total = 0
    multi_source = 0
    for rnd in rounds:
        for finding in rnd.get("findings", []):
            total += 1
            source = finding.get("source", "") or ""
            blob = source + " " + _finding_body_text(finding)
            if not blob.strip():
                continue
            urls = re.findall(r"https?://[^\s)\]>]+", blob)
            domains = set()
            for u in urls:
                try:
                    domains.add(urllib.parse.urlparse(u).netloc.lower())
                except Exception:
                    pass
            if (
                len(urls) >= 2
                or len(domains) >= 2
                or ";" in source
                or "," in source
            ):
                multi_source += 1
    return multi_source, total


def _count_findings_consistency(state):
    """NoneDimension"""
    rounds = state.get("findings", {}).get("rounds", [])
    all_dims = set()
    for rnd in rounds:
        for finding in rnd.get("findings", []):
            dim = finding.get("dimension", "")
            if dim:
                all_dims.add(dim)

    contradictions = state.get("findings", {}).get("disputes", [])
    contradiction_dims = set()
    for c in contradictions:
        dim = c.get("dimension", "") if isinstance(c, dict) else ""
        if dim:
            contradiction_dims.add(dim)

    total = len(all_dims)
    consistent = total - len(contradiction_dims & all_dims)
    return consistent, total


def _count_findings_completeness(state):
    """Sourceat least 1 finding."""
    rounds = state.get("findings", {}).get("rounds", [])
    total = 0
    sourced = 0
    for rnd in rounds:
        for finding in rnd.get("findings", []):
            total += 1
            source = (finding.get("source") or "").strip()
            body = _finding_body_text(finding)
            has_ref = bool(
                source or (body and re.search(r"https?://|Source|Source|arXiv", body, re.I))
            )
            if has_ref and _finding_substantive_info_count(finding) >= 1:
                sourced += 1
    return sourced, total


def _confidence_for_dim(dim):
    """DimensionSource, Returns (confidence, margin).

    Three-tier confidence: 
    - empirical (margin ≤ 0.3): based on actual tool output(syntax_check_cmd, TestPass Rate, lint )
    - heuristic (margin ≤ 1.5): ContentanalysisPattern(Source, keyCoverage, Pattern)
    - binary (margin = None): can only determine pass/fail(None)
    """
    # Empirical dimensions: T4/T7/T8
    _EMPIRICAL_DIMS = {
        "syntax",              # T4: syntax_check_cmd 
        "p1_p2_issues",        # T4: Issue List
        "service_health",      # T4: check URL should
        "p1_all",              # T7: Dimension P1 
        "security_p2",         # T7:  P2 
        "reliability_p2",      # T7: Reliability P2 
        "maintainability_p2",  # T7: Maintainability P2 
    }
    # Heuristic dimensions: T1/T2/T3/T5/T6 depend mainly on content analysis; T7/T8 can also fall back here.
    _HEURISTIC_DIMS = {
        "coverage",            # T1/T2: Source / DimensionCoverage
        "credibility",         # T1/T2: 
        "consistency",         # T1/T2: NoneDimension
        "completeness",        # T1/T2: Source
        "sensitivity",         # T2: Sensitivity Analysis
        "kpi_target",          # T5: KPI Pass()
        "pass_rate",           # T6: Pass Rate
        "avg_score",           # T6: Average Score
        "security_score",      # T7: Security
        "reliability_score",   # T7: Reliability
        "maintainability_score",  # T7: Maintainability
        "architecture",        # T8: Architecture
        "performance",         # T8: Performance
        "stability",           # T8: Stability
        "design_completeness",      # T3: Design Completeness
        "feasibility_score",        # T3: Technical Feasibility
        "requirement_coverage",     # T3: Requirement Coverage
        "scope_precision",          # T3: Scope Precision
        "validation_evidence",      # T3: Validation Evidence
    }
    # binary:  pass/fail
    _BINARY_DIMS = {
        "bias_check",          # T2: Bias Check(bool Gate)
        "user_acceptance",     # T4: Manual Acceptance(bool Gate)
    }

    if dim in _EMPIRICAL_DIMS:
        return "empirical", 0.3
    if dim in _HEURISTIC_DIMS:
        return "heuristic", 1.5
    if dim in _BINARY_DIMS:
        return "binary", None
    # UnknownDimension heuristic
    return "heuristic", 1.5


def _eval_gate(gate_def, value, evidence=""):
    """Gate, ReturnsResult dict.

    value: Value( / score /  / bool)
    """
    dim = gate_def["dim"]
    manifest_dimension = gate_def.get("manifest_dimension", dim)
    threshold = gate_def["threshold"]
    unit = gate_def["unit"]
    gate_type = gate_def["gate"]
    label = gate_def["label"]
    confidence, margin = _confidence_for_dim(dim)

    # threshold=None indicates T5 KPI gates.
    # T5 KPI values come from score_from_ssot() after plan_gates is finalized.
    # controller.py check_gates_passed() reads the target from plan.gates[].target.
    if threshold is None:
        passed = value is not None and bool(value)
        return {
            "dimension": dim,
            "manifest_dimension": manifest_dimension,
            "label": label,
            "value": value,
            "threshold": "User Defined",
            "unit": unit,
            "gate_type": gate_type,
            "pass": passed,
            "evidence": evidence,
            "confidence": confidence,
            "margin": margin,
        }

    # Use the manifest comparator field for comparison(SSOT), unit 
    comparator = gate_def.get("comparator", ">=")
    if unit == "bool":
        # bool + ==: and threshold (avoid misclassifying float bias scores as True via bool())
        if comparator == "==":
            passed = value == threshold
        else:
            passed = bool(value)
    elif comparator == ">=":
        passed = value >= threshold
    elif comparator == "<=":
        passed = value <= threshold
    elif comparator == "==":
        passed = value == threshold
    elif comparator == "<":
        passed = value < threshold
    elif comparator == ">":
        passed = value > threshold
    else:
        passed = value >= threshold

    #  threshold 
    if unit == "%":
        thr_display = "{}%".format(threshold)
        val_display = "{:.1f}%".format(value)
    elif unit == "/10":
        thr_display = "{}/10".format(threshold)
        val_display = "{:.1f}/10".format(value)
    elif unit == "score":
        comparator_display = gate_def.get("comparator", ">=")
        thr_display = "{} {}".format(comparator_display, threshold)
        val_display = "{:.1f}".format(float(value) if isinstance(value, (int, float)) else 0.0)
    elif unit in ("errors", "count"):
        thr_display = "{} {}".format(comparator, threshold)
        val_display = str(int(value))
    elif unit == "bool":
        thr_display = "True"
        val_display = str(bool(value))
    else:
        thr_display = str(threshold)
        val_display = str(value)

    return {
        "dimension": dim,
        "manifest_dimension": manifest_dimension,
        "label": label,
        "value": value,
        "value_display": val_display,
        "threshold": threshold,
        "threshold_display": thr_display,
        "unit": unit,
        "gate_type": gate_type,
        "pass": passed,
        "evidence": evidence,
        "confidence": confidence,
        "margin": margin,
    }


LLM_GRADER_WEIGHT = 0.7
HEURISTIC_WEIGHT = 1.0 - LLM_GRADER_WEIGHT  # 0.3


def _prepare_llm_grader(gate_def, result, state, work_dir):
    """Prepare an LLM-grader handoff when a heuristic-scored dimension needs review.

    For gates with llm_grader.enabled=true and heuristic confidence:
    1. Read the grader prompt file
    2. Build evaluation context from findings for the current dimension
    3. Write the grader prompt + evaluation context to state.json metadata.pending_llm_grader
    4. Print a prompt so the controller can delegate scoring to a subagent during VERIFY

    Returns the pending entry dict to write into state, otherwise None.
    """
    grader_cfg = gate_def.get("llm_grader")
    if not grader_cfg or not grader_cfg.get("enabled", False):
        return None

    trigger = grader_cfg.get("trigger", "when_confidence_is_heuristic")
    confidence = result.get("confidence", "")

    # Apply the configured trigger to heuristic-confidence results.
    if trigger == "when_confidence_is_heuristic" and confidence != "heuristic":
        return None

    dim = result.get("dimension", gate_def.get("dim", "unknown"))
    prompt_file = grader_cfg.get("prompt_file", "")

    # Read the grader prompt file
    prompt_content = ""
    if prompt_file:
        assets_dir = os.path.join(os.path.dirname(__file__), "..", "assets")
        prompt_path = os.path.join(assets_dir, prompt_file)
        if os.path.exists(prompt_path):
            with open(prompt_path, "r", encoding="utf-8") as f:
                prompt_content = f.read()

    # extractCurrentDimension findings 
    context_lines = []
    rounds = state.get("findings", {}).get("rounds", [])
    for rnd in rounds:
        for finding in rnd.get("findings", []):
            dim_tag = finding.get("dimension", "")
            body = finding.get("body", finding.get("content", ""))
            if isinstance(body, list):
                body = "\n".join(str(b) for b in body)
            if dim in dim_tag or gate_def.get("manifest_dimension", "") in dim_tag:
                context_lines.append(str(body)[:500])
    # if, roundall findings 
    if not context_lines and rounds:
        last_round = rounds[-1]
        for finding in last_round.get("findings", []):
            body = finding.get("body", finding.get("content", ""))
            if isinstance(body, list):
                body = "\n".join(str(b) for b in body)
            context_lines.append(str(body)[:500])

    context_text = "\n---\n".join(context_lines[:10])  # 10, Avoid

    print("[LLM Grader] Evaluating dimension '{}' with grader: {}".format(dim, prompt_file))
    print("[LLM Grader] → Controller should delegate a subagent in VERIFY phase.")
    print("[LLM Grader] → Fusion formula: final = heuristic * {:.1f} + llm * {:.1f}".format(
        HEURISTIC_WEIGHT, LLM_GRADER_WEIGHT))

    return {
        "dimension": dim,
        "prompt_file": prompt_file,
        "prompt_content": prompt_content,
        "context": context_text,
        "heuristic_score": result.get("value"),
        "fusion_weights": {"heuristic": HEURISTIC_WEIGHT, "llm": LLM_GRADER_WEIGHT},
    }


def score_from_ssot(state):
    """Score from SSOT JSON, Returns (template, results_list).

    results_list: [{dimension, label, value, threshold, gate_type, pass, evidence, confidence, margin}, ...]
    """
    template_raw = state.get("plan", {}).get("template", "")
    template = resolve_template(template_raw)

    if not template:
        return None, [{"error": "Unknown template type: '{}'".format(template_raw)}]

    gates = TEMPLATE_GATES[template]
    scores = _get_latest_scores(state)
    plan_gates = _get_plan_gates(state)
    results = []

    for gate_def in gates:
        dim = gate_def["dim"]
        pg = _find_plan_gate_row(plan_gates, dim, gate_def.get("manifest_dimension"))
        if pg and plan_gate_is_exempt(pg):
            conf, marg = _confidence_for_dim(dim)
            results.append(
                {
                    "dimension": dim,
                    "manifest_dimension": gate_def.get("manifest_dimension", dim),
                    "label": gate_def["label"],
                    "value": None,
                    "threshold": gate_def["threshold"],
                    "unit": gate_def["unit"],
                    "gate_type": gate_def["gate"],
                    "pass": True,
                    "evidence": "plan.gates.status=Exempt (rolled up)",
                    "confidence": conf,
                    "margin": marg,
                }
            )
            continue

        value = None
        evidence = ""

        # --- T1/T2 :  findings  ---
        if dim == "coverage":
            covered, total = _count_findings_coverage(state)
            value = (covered / total * 100) if total > 0 else 0.0
            evidence = "{}/{} dimensions covered by findings".format(covered, total)

        elif dim == "credibility":
            multi, total = _count_findings_credibility(state)
            value = (multi / total * 100) if total > 0 else 0.0
            evidence = "{}/{} findings include multi-source support".format(multi, total)

        elif dim == "consistency":
            consistent, total = _count_findings_consistency(state)
            value = (consistent / total * 100) if total > 0 else 0.0
            evidence = "{}/{} dimensions remain internally consistent".format(consistent, total)

        elif dim == "completeness":
            sourced, total = _count_findings_completeness(state)
            value = (sourced / total * 100) if total > 0 else 0.0
            evidence = "{}/{} findings include supporting sources".format(sourced, total)

        # --- T2  ---
        elif dim == "bias_check":
            # Bool gate with ==1 semantics: values below 0.15 are treated as passing.
            raw = scores.get("bias_check", scores.get("bias_score", 0.0))
            if isinstance(raw, bool):
                value = raw
                evidence = "Bias Check={}".format(value)
            elif isinstance(raw, (int, float)):
                value = raw < 0.15
                evidence = "Bias score={:.3f} -> {}".format(raw, value)
            else:
                value = False
                evidence = "No bias-check evidence available"

        elif dim == "sensitivity":
            value = scores.get("sensitivity", scores.get("sensitivity_pass", False))
            if isinstance(value, bool):
                evidence = "Sensitivity Analysis={}".format(value)
            else:
                value = bool(value)
                evidence = "Sensitivity Analysis={}".format(value)

        # --- T5 KPI ---
        elif dim == "kpi_target":
            kpi_rows = [pg for pg in plan_gates if pg.get("threshold") is None]
            if not kpi_rows:
                value = False
                evidence = "No KPI gates found (plan.gates with threshold=null)"
            else:
                kpi_pass = True
                kpi_details = []
                for pg in kpi_rows:
                    pg_dim = pg.get("dimension", pg.get("dim", ""))
                    override = scores.get(pg_dim)
                    met = kpi_row_satisfied(pg, override)
                    if not met:
                        kpi_pass = False
                    cur = (
                        override if override is not None else pg.get("current")
                    )
                    tgt = pg.get("target")
                    kpi_details.append("{}:{}→{}({})".format(
                        pg_dim, cur, tgt, "✓" if met else "✗"))
                value = kpi_pass
                evidence = "; ".join(kpi_details)

        # --- T6  ---
        elif dim == "pass_rate":
            value = scores.get("pass_rate", 0.0)
            if isinstance(value, (int, float)):
                evidence = "Pass Rate={:.1f}%".format(value)
            else:
                value = 0.0
                evidence = "NonePass Rate"

        elif dim == "avg_score":
            value = scores.get("avg_score", scores.get("average_score", 0.0))
            if isinstance(value, (int, float)):
                evidence = "Average Score={:.1f}/10".format(value)
            else:
                value = 0.0
                evidence = "NoneAverage Score"

        # --- T4  ---
        elif dim == "syntax":
            value = scores.get("syntax_errors", scores.get("syntax", 0))
            if isinstance(value, (int, float)):
                value = int(value)
                evidence = "={}".format(value)
            else:
                value = 0
                evidence = "Nonecheck"

        elif dim == "p1_p2_issues":
            counts = _count_issues_by_severity(state)
            value = counts["P1"] + counts["P2"]
            evidence = "P1={}, P2={}".format(counts["P1"], counts["P2"])

        elif dim == "service_health":
            value = scores.get("service_health", scores.get("services_healthy", False))
            if isinstance(value, bool):
                evidence = "Status={}".format("" if value else "")
            else:
                value = bool(value)
                evidence = "Status={}".format(value)

        elif dim == "user_acceptance":
            value = scores.get("user_acceptance", scores.get("user_confirmed", False))
            if isinstance(value, bool):
                evidence = "={}".format("" if value else "")
            else:
                value = bool(value)
                evidence = "={}".format(value)

        # --- T7  ---
        elif dim == "security_score":
            value = scores.get("security_score", scores.get("security", 0.0))
            value = float(value) if isinstance(value, (int, float)) else 0.0
            evidence = "SecurityScores={:.1f}/10".format(value)

        elif dim == "reliability_score":
            value = scores.get("reliability_score", scores.get("reliability", 0.0))
            value = float(value) if isinstance(value, (int, float)) else 0.0
            evidence = "ReliabilityScores={:.1f}/10".format(value)

        elif dim == "maintainability_score":
            value = scores.get("maintainability_score", scores.get("maintainability", 0.0))
            value = float(value) if isinstance(value, (int, float)) else 0.0
            evidence = "MaintainabilityScores={:.1f}/10".format(value)

        elif dim == "p1_all":
            counts = _count_issues_by_severity(state)
            value = counts["P1"]
            evidence = "DimensionP1Issues={}".format(value)

        elif dim == "security_p2":
            counts = _count_issues_by_severity(state, "security")
            value = counts["P2"]
            evidence = "Security P2 Issues={}".format(value)

        elif dim == "reliability_p2":
            counts = _count_issues_by_severity(state, "reliability")
            value = counts["P2"]
            evidence = "ReliabilityP2Issues={}".format(value)

        elif dim == "maintainability_p2":
            counts = _count_issues_by_severity(state, "maintainability")
            value = counts["P2"]
            evidence = "MaintainabilityP2Issues={}".format(value)

        # --- T8  ---
        elif dim == "architecture":
            raw = scores.get("architecture", scores.get("architecture_score", None))
            if raw is not None and isinstance(raw, (int, float)) and float(raw) > 0:
                value = float(raw)
                evidence = "Architecture Score={:.1f}/10 (from scores)".format(value)
            else:
                rounds = state.get("findings", {}).get("rounds", [])
                issues = {"P1": 0, "P2": 0, "P3": 0}
                for rnd in rounds:
                    for finding in rnd.get("findings", []):
                        dim_tag = finding.get("dimension", "")
                        body = _finding_body_text(finding)
                        if "architect" in dim_tag.lower() or any(kw in body.lower() for kw in
                                ("Architecture", "architecture", "", "module", "", "coupling",
                                 "", "dependency", "", "layer")):
                            for sev in ("P1", "P1:", "P1 ", "P1: "):
                                issues["P1"] += body.count(sev)
                            for sev in ("P2", "P2:", "P2 ", "P2: "):
                                issues["P2"] += body.count(sev)
                            for sev in ("P3", "P3:", "P3 ", "P3: "):
                                issues["P3"] += body.count(sev)
                deduction = issues["P1"] * 1.5 + issues["P2"] * 0.8 + issues["P3"] * 0.3
                value = max(0.0, min(10.0, 10.0 - deduction))
                evidence = "Architecture (findings): P1={} P2={} P3={} -> {:.1f}/10".format(
                    issues["P1"], issues["P2"], issues["P3"], value)

        elif dim == "performance":
            raw = scores.get("performance", scores.get("performance_score", None))
            if raw is not None and isinstance(raw, (int, float)) and float(raw) > 0:
                value = float(raw)
                evidence = "Performance Score={:.1f}/10 (from scores)".format(value)
            else:
                rounds = state.get("findings", {}).get("rounds", [])
                issues = {"P1": 0, "P2": 0, "P3": 0}
                for rnd in rounds:
                    for finding in rnd.get("findings", []):
                        dim_tag = finding.get("dimension", "")
                        body = _finding_body_text(finding)
                        if "performance" in dim_tag.lower() or any(kw in body.lower() for kw in
                                ("Performance", "performance", "", "pagination", "", "index",
                                 "", "cache", "n+1", "", "query")):
                            for sev in ("P1", "P1:", "P1 ", "P1: "):
                                issues["P1"] += body.count(sev)
                            for sev in ("P2", "P2:", "P2 ", "P2: "):
                                issues["P2"] += body.count(sev)
                            for sev in ("P3", "P3:", "P3 ", "P3: "):
                                issues["P3"] += body.count(sev)
                deduction = issues["P1"] * 1.5 + issues["P2"] * 0.8 + issues["P3"] * 0.3
                value = max(0.0, min(10.0, 10.0 - deduction))
                evidence = "Performance (findings): P1={} P2={} P3={} -> {:.1f}/10".format(
                    issues["P1"], issues["P2"], issues["P3"], value)

        elif dim == "stability":
            raw = scores.get("stability", scores.get("stability_score", None))
            if raw is not None and isinstance(raw, (int, float)) and float(raw) > 0:
                value = float(raw)
                evidence = "Stability Score={:.1f}/10 (from scores)".format(value)
            else:
                rounds = state.get("findings", {}).get("rounds", [])
                issues = {"P1": 0, "P2": 0, "P3": 0}
                for rnd in rounds:
                    for finding in rnd.get("findings", []):
                        dim_tag = finding.get("dimension", "")
                        body = _finding_body_text(finding)
                        if "stabilit" in dim_tag.lower() or any(kw in body.lower() for kw in
                                ("", "stability", "", "error", "", "logging",
                                 "check", "health", "shutdown", "", "rate limit")):
                            for sev in ("P1", "P1:", "P1 ", "P1: "):
                                issues["P1"] += body.count(sev)
                            for sev in ("P2", "P2:", "P2 ", "P2: "):
                                issues["P2"] += body.count(sev)
                            for sev in ("P3", "P3:", "P3 ", "P3: "):
                                issues["P3"] += body.count(sev)
                deduction = issues["P1"] * 1.5 + issues["P2"] * 0.8 + issues["P3"] * 0.3
                value = max(0.0, min(10.0, 10.0 - deduction))
                evidence = "Stability (findings): P1={} P2={} P3={} -> {:.1f}/10".format(
                    issues["P1"], issues["P2"], issues["P3"], value)

        # --- T3  ---
        elif dim == "design_completeness":
            # Estimate design completeness from requirement and design detail coverage in findings.
            raw = scores.get("design_completeness", scores.get("design_complete", None))
            if raw is not None and isinstance(raw, (int, float)):
                value = float(raw)
                evidence = "Design Completeness={:.1f}/10 (from scores)".format(value)
            else:
                rounds = state.get("findings", {}).get("rounds", [])
                req_entries = 0
                design_entries = 0
                for rnd in rounds:
                    for finding in rnd.get("findings", []):
                        body = _finding_body_text(finding)
                        dim_tag = finding.get("dimension", "")
                        if any(kw in dim_tag or kw in body for kw in
                               ("", "requirement", "", "feature", "user story")):
                            req_entries += 1
                            if any(kw in body for kw in
                                   ("", "", "design", "spec", "", "Architecture", "approach")):
                                design_entries += 1
                if req_entries > 0:
                    value = min(10.0, (design_entries / req_entries) * 10.0)
                    evidence = "{}/{} requirement entries include design detail -> {:.1f}/10".format(
                        design_entries, req_entries, value)
                else:
                    value = 0.0
                    evidence = "No requirement-linked design evidence found in findings"

        elif dim == "feasibility_score":
            # Estimate technical feasibility from findings that mention constraints, risks, or dependencies.
            raw = scores.get("feasibility_score", scores.get("feasibility", None))
            if raw is not None and isinstance(raw, (int, float)):
                value = float(raw)
                evidence = "Technical Feasibility={:.1f}/10 (from scores)".format(value)
            else:
                rounds = state.get("findings", {}).get("rounds", [])
                feasibility_signals = 0
                for rnd in rounds:
                    for finding in rnd.get("findings", []):
                        body = _finding_body_text(finding)
                        dim_tag = finding.get("dimension", "")
                        if any(kw in dim_tag or kw in body for kw in
                               ("", "feasibility", "Risk", "risk", "",
                                "constraint", "", "dependency", "Architecture", "architecture")):
                            feasibility_signals += _finding_substantive_info_count(finding)
                if feasibility_signals >= 6:
                    value = 9.0
                elif feasibility_signals >= 4:
                    value = 7.5
                elif feasibility_signals >= 2:
                    value = 6.0
                elif feasibility_signals >= 1:
                    value = 4.0
                else:
                    value = 0.0
                evidence = "{} feasibility signals in findings -> {:.1f}/10".format(feasibility_signals, value)

        elif dim == "requirement_coverage":
            # Estimate requirement coverage from finding coverage counts.
            raw = scores.get("requirement_coverage", scores.get("req_coverage", None))
            if raw is not None and isinstance(raw, (int, float)):
                value = float(raw)
                evidence = "Requirement Coverage={:.1f}/10 (from scores)".format(value)
            else:
                covered, total = _count_findings_coverage(state)
                value = (covered / total * 10.0) if total > 0 else 0.0
                evidence = "{}/{} dimensions covered in findings -> {:.1f}/10".format(covered, total, value)

        elif dim == "scope_precision":
            # check IN/OUT 
            raw = scores.get("scope_precision", scores.get("scope", None))
            if raw is not None and isinstance(raw, (int, float)):
                value = float(raw)
                evidence = "Scope Precision={:.1f}/10 (from scores)".format(value)
            else:
                rounds = state.get("findings", {}).get("rounds", [])
                scope_signals = 0
                for rnd in rounds:
                    for finding in rnd.get("findings", []):
                        body = _finding_body_text(finding)
                        dim_tag = finding.get("dimension", "")
                        if any(kw in dim_tag or kw in body for kw in
                               ("", "scope", "IN scope", "OUT scope", "", "boundary",
                                "", "", "exclude", "")):
                            scope_signals += _finding_substantive_info_count(finding)
                if scope_signals >= 4:
                    value = 9.0
                elif scope_signals >= 2:
                    value = 7.0
                elif scope_signals >= 1:
                    value = 5.0
                else:
                    value = 0.0
                evidence = "{} scope signals in findings -> {:.1f}/10".format(scope_signals, value)

        elif dim == "validation_evidence":
            # Estimate validation evidence from review, check, and risk-assessment signals.
            raw = scores.get("validation_evidence", scores.get("validation", None))
            if raw is not None and isinstance(raw, (int, float)):
                value = float(raw)
                evidence = "Validation Evidence={:.1f}/10 (from scores)".format(value)
            else:
                rounds = state.get("findings", {}).get("rounds", [])
                validation_signals = 0
                for rnd in rounds:
                    for finding in rnd.get("findings", []):
                        body = _finding_body_text(finding)
                        dim_tag = finding.get("dimension", "")
                        if any(kw in dim_tag or kw in body for kw in
                               ("", "review", "validation", "validation", "check", "check",
                                "Risk", "risk assessment", "check", "feasibility check")):
                            validation_signals += _finding_substantive_info_count(finding)
                if validation_signals >= 4:
                    value = 9.0
                elif validation_signals >= 2:
                    value = 7.0
                elif validation_signals >= 1:
                    value = 5.0
                else:
                    value = 0.0
                evidence = "{} validation signals in findings -> {:.1f}/10".format(validation_signals, value)

        else:
            # Unknown dimension: read directly from scores as a fallback.
            value = scores.get(dim, 0)
            evidence = "Scores fallback: {}={}".format(dim, value)

        results.append(_eval_gate(gate_def, value, evidence))

    # --- LLM Grader Phase ---
    #  gates,  llm_grader  confidence=heuristic Dimension
    #  grader prompt + , write state.metadata.pending_llm_grader
    work_dir = state.get("_work_dir", "")
    pending_graders = []
    for gate_def, result in zip(gates, results):
        entry = _prepare_llm_grader(gate_def, result, state, work_dir)
        if entry:
            pending_graders.append(entry)

    if pending_graders:
        if "metadata" not in state:
            state["metadata"] = {}
        state["metadata"]["pending_llm_grader"] = pending_graders

    return template, results


# =====================================================================
# Markdown (Pattern)
# =====================================================================

# Dimensionkey
_SKIP_KEYWORDS = [
    "Executive Summary", "Source", "Strategy", "", "", "direction",
    "Issue List", "record", "Pattern Recognition", "Lessons Learned", "Problem Tracking",
]
_ROUND_HEADER_RE = re.compile(r'^\s*\d+\s*round')


def _split_all_sections(content):
    """ markdown Content ##  ###  (level, heading, body) """
    pattern = re.compile(r'^(#{2,3})\s+(.+)$', re.MULTILINE)
    sections = []
    matches = list(pattern.finditer(content))
    for i, m in enumerate(matches):
        heading_level = len(m.group(1))
        heading_text = m.group(2).strip()
        body_start = m.end()
        body_end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        body = content[body_start:body_end].strip()
        sections.append((heading_level, heading_text, body))
    return sections


def _is_dimension_section(level, heading, body):
    """Dimension"""
    if any(skip in heading for skip in _SKIP_KEYWORDS):
        return False
    if _ROUND_HEADER_RE.match(heading):
        return False
    if level == 3 and re.search(r'\[.+\]', heading):
        return True
    if "Dimension" in heading or "Dimension" in heading or "keyfinding" in heading:
        return True
    if level == 2 and len(body) > 20:
        return True
    return False


def _count_info_points(body):
    """Count substantive information points in a markdown section body."""
    lines = body.split("\n")
    bullet_count = sum(1 for line in lines
                       if line.strip().startswith("- ") and len(line.strip()) > 10)
    if bullet_count >= 2:
        return bullet_count
    para_count = sum(1 for line in lines
                     if line.strip()
                     and not line.strip().startswith("Source:")
                     and not line.strip().startswith("Source: ")
                     and not line.strip().startswith("Strategy:")
                     and not line.strip().startswith("Strategy: ")
                     and not line.strip().startswith("ID:")
                     and not line.strip().startswith("ID: ")
                     and not line.strip().startswith("|")
                     and not line.strip().startswith("#")
                     and len(line.strip()) > 10)
    return max(bullet_count, para_count)


def score_from_markdown(content):
    """ markdown Content(legacy-mode fallback), Returns ("T1", results_list).

    Markdown Pattern T1  4 Dimension(Coverage/Credibility/Consistency/Completeness).
    """
    sections = _split_all_sections(content)

    # --- Coverage ---
    total_dims = 0
    covered_dims = 0
    for level, heading, body in sections:
        if not _is_dimension_section(level, heading, body):
            continue
        total_dims += 1
        if _count_info_points(body) >= 2:
            covered_dims += 1

    cov_pct = (covered_dims / total_dims * 100) if total_dims > 0 else 0.0

    # --- Credibility ---
    source_markers = ["http", "Source", "Source", "arXiv", "GitHub"]
    inline_findings = re.findall(r'- .+(?:Source|Source|http|arXiv|GitHub).+', content)
    ssot_findings = []
    for level, heading, body in sections:
        if not _is_dimension_section(level, heading, body):
            continue
        has_source = bool(re.search(
            r'(?:^Source[:: ]|^Source[:: ]|https?://)', body, re.MULTILINE))
        if has_source:
            ssot_findings.append(body)

    total_findings = max(len(inline_findings), len(ssot_findings))
    multi_source = 0
    for f_text in inline_findings:
        if (f_text.count("http") >= 2 or "" in f_text or "multiple" in f_text.lower()
                or f_text.count("Source") >= 2 or f_text.count("Source") >= 2):
            multi_source += 1
    ssot_multi = 0
    for body in ssot_findings:
        url_count = len(re.findall(r'https?://', body))
        source_line_count = len(re.findall(r'^Source[:: ]', body, re.MULTILINE))
        if (url_count >= 2 or source_line_count >= 2
                or "" in body or "multiple" in body.lower()):
            ssot_multi += 1
    multi_source = max(multi_source, ssot_multi)
    cred_pct = (multi_source / total_findings * 100) if total_findings > 0 else 0.0

    # --- Consistency ---
    contradictions = len(re.findall(
        r'|||contradictory|conflict', content, re.IGNORECASE))
    consistent_dims = max(0, total_dims - contradictions)
    cons_pct = (consistent_dims / total_dims * 100) if total_dims > 0 else 0.0

    # --- Completeness ---
    bullet_statements = re.findall(r'- .{20,}', content)
    bullet_total = len(bullet_statements)
    bullet_sourced = sum(1 for s in bullet_statements
                         if any(marker in s for marker in source_markers))
    ssot_total = 0
    ssot_sourced = 0
    for level, heading, body in sections:
        if not _is_dimension_section(level, heading, body):
            continue
        if _count_info_points(body) < 1:
            continue
        ssot_total += 1
        if any(marker in body for marker in source_markers):
            ssot_sourced += 1
    if ssot_total >= bullet_total:
        comp_sourced, comp_total = ssot_sourced, ssot_total
    else:
        comp_sourced, comp_total = bullet_sourced, bullet_total
    comp_pct = (comp_sourced / comp_total * 100) if comp_total > 0 else 0.0

    # T1 gate results
    gates = TEMPLATE_GATES["T1"]
    values = {
        "coverage": (cov_pct, "{}/{} dimensions covered".format(covered_dims, total_dims)),
        "credibility": (cred_pct, "{}/{} findings are multi-sourced".format(multi_source, total_findings)),
        "consistency": (cons_pct, "{}/{} dimensions are internally consistent".format(consistent_dims, total_dims)),
        "completeness": (comp_pct, "{}/{} findings include sources".format(comp_sourced, comp_total)),
    }

    results = []
    for gate_def in gates:
        val, ev = values[gate_def["dim"]]
        results.append(_eval_gate(gate_def, val, ev))

    return "T1", results


# =====================================================================
# Output Formatting
# =====================================================================

def _overall_pass(results):
    """: Gates Passed"""
    for r in results:
        if isinstance(r, dict) and r.get("gate_type") == "hard" and not r.get("pass", False):
            return False
    return True


def print_results(template, results, mode="ssot", state=None):
    """GateResult"""
    payload = results_to_json(template, results, mode=mode, state=state)
    overall = payload["overall_pass"]
    mode_label = "SSOT" if mode == "ssot" else "Markdown()"

    print("Template: {} | Pattern: {} | Overall Verdict: {}".format(
        template or "Unknown", mode_label, "PASS" if overall else "FAIL"))
    if mode == "ssot" and state is not None and payload.get("tsv_fail_closed"):
        print(
            "TSV fail-closed: {}(and EVOLVE Termination rollup ; Gate alone )".format(
                payload.get("fail_closed_reason") or "variance/confidence"
            )
        )
    print()
    print("{:<16} {:>10} {:>10} {:>6} {:>6} {:>10} {:>6}  {}".format(
        "Dimension", "Scores", "threshold", "Type", "Status", "Confidence", "Margin", ""))
    print("-" * 110)

    for r in results:
        if "error" in r:
            print("ERROR: {}".format(r["error"]))
            continue

        label = r.get("label", r.get("dimension", "?"))
        val_display = r.get("value_display", str(r.get("value", "?")))
        thr_display = r.get("threshold_display", str(r.get("threshold", "?")))
        gate_type = r.get("gate_type", "?")
        status = "✅" if r.get("pass") else "❌"
        evidence = r.get("evidence", "")
        confidence = r.get("confidence", "?")
        margin = r.get("margin")
        margin_display = "±{:.1f}".format(margin) if margin is not None else "N/A"

        print("{:<16} {:>10} {:>10} {:>6} {:>6} {:>10} {:>6}  {}".format(
            label, val_display, thr_display, gate_type, status, confidence, margin_display, evidence))

    # Notice for failed soft gates
    soft_fails = [r for r in results
                  if isinstance(r, dict) and r.get("gate_type") == "soft" and not r.get("pass", False)]
    if soft_fails and payload.get("gates_pass"):
        print()
        print("Note: {} soft gates did not pass (recorded, but do not block termination):".format(len(soft_fails)))
        for r in soft_fails:
            print("  - {}: {}".format(r.get("label", r.get("dimension")), r.get("evidence", "")))

    print()


def results_to_json(template, results, mode="ssot", state=None):
    """Result JSON  dict.

    SSOT Pattern results_tsv  fail-closed,  overall_pass  false(and controller phase_evolve ).
    """
    gate_pass = _overall_pass(results)
    tsv_fc, tsv_reason = False, None
    if mode == "ssot" and state is not None:
        tsv_fc, tsv_reason = results_tsv_last_row_fail_closed(state)
    overall = gate_pass and not tsv_fc
    return {
        "template": template,
        "mode": mode,
        "gates_pass": gate_pass,
        "tsv_fail_closed": tsv_fc,
        "fail_closed_reason": tsv_reason if tsv_fc else None,
        "overall_pass": overall,
        "gates": results,
    }


# =====================================================================
# CLI Entry
# =====================================================================

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    target_path = sys.argv[1]
    json_output = "--json" in sys.argv

    mode, data, context = detect_mode(target_path)

    if mode == "error":
        print("ERROR: {}".format(data))
        sys.exit(1)

    if mode == "ssot":
        print("INFO: SSOT pattern: reading {} for scoring.".format(
            os.path.join(context, "autoloop-state.json")), file=sys.stderr)
        template, results = score_from_ssot(data)
    else:
        template, results = score_from_markdown(data)

    ssot_state = data if mode == "ssot" else None
    if json_output:
        output = results_to_json(template, results, mode, state=ssot_state)
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        print_results(template, results, mode, state=ssot_state)
        #  JSON ()
        output = results_to_json(template, results, mode, state=ssot_state)
        print("---JSON---")
        print(json.dumps(output, ensure_ascii=False))

    sys.exit(0 if results_to_json(template, results, mode, state=ssot_state)["overall_pass"] else 1)


if __name__ == "__main__":
    main()
