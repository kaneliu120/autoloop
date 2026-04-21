"""Shared T5 / user-defined KPI row logic (plan.gates rows with threshold null).

Used by autoloop-score (kpi_target gate) and autoloop-controller (check_gates_passed).
"""

from __future__ import annotations

_KPI_PASS_STATUS = frozenset({"met", "exempt", "pass", "passed"})


def plan_gate_is_exempt(gate_row):
    """When a plan.gates row has status=exempt, roll it up as if the gate were removed (quality-gates.md)."""
    if not isinstance(gate_row, dict):
        return False
    s = (gate_row.get("status") or "").strip()
    return s.lower() == "exempt"


def results_tsv_last_row_fail_closed(state):
    """Aligned with autoloop-variance / controller EVOLVE: the last TSV row is fail-closed if variance≥2 or 0<confidence<50%.

    Returns (is_fail_closed, reason_or_none).
    """
    rows = state.get("results_tsv") or []
    if not rows:
        return False, None
    last = rows[-1]
    sv = str(last.get("score_variance", "0")).strip()
    conf = str(last.get("confidence", "100")).replace("%", "").strip()
    try:
        var = float(sv) if sv and sv != "—" else 0.0
    except ValueError:
        return True, "score_variance is not numeric"
    try:
        c = float(conf) if conf and conf != "—" else 100.0
    except ValueError:
        return True, "confidence is not numeric"
    if var >= 2.0:
        return True, "score_variance≥2.0"
    if c < 50 and c != 0:
        return True, "confidence<50%"
    return False, None


def kpi_row_satisfied(gate_row, current_override=None):
    """Return True if this KPI row is satisfied.

    current_override: when set, use as current value (e.g. iterations[-1].scores[dim])
    instead of plan.gates[].current.
    """
    if not isinstance(gate_row, dict):
        return False
    status = (gate_row.get("status") or "").strip().lower()
    if status in _KPI_PASS_STATUS:
        return True
    target = gate_row.get("target")
    current = gate_row.get("current")
    if current_override is not None:
        current = current_override
    if current is not None and target is not None:
        try:
            c, t = float(current), float(target)
            comparator = gate_row.get("comparator", ">=")
            if comparator == ">=":
                return c >= t
            elif comparator == "<=":
                return c <= t
            elif comparator == "==":
                return c == t
            elif comparator == "<":
                return c < t
            elif comparator == ">":
                return c > t
            else:
                return c >= t  # default fallback
        except (ValueError, TypeError):
            return False
    return False
