#!/usr/bin/env python3
"""P3-06: multi: parallel strategy strategy_id constraints (shared by experience write and validate)."""

import re

# Matches autoloop-validate STRATEGY_RE: S{NN}-description
STRATEGY_ID_BASE_RE = re.compile(r"^S\d{2}-.+$")

# multi:{...}, capturing the sub-strategy list inside braces (loop-protocol recommends + or , separators)
_MULTI_BODY_RE = re.compile(r"^multi:\{(.+)\}\s*$", re.IGNORECASE)


def is_multi_strategy_id(strategy_id):
    if not strategy_id or not isinstance(strategy_id, str):
        return False
    return strategy_id.strip().lower().startswith("multi:")


def parse_multi_strategy_components(strategy_id):
    """Parse multi:{A,B} / multi:{A+B} -> sub strategy_id list; return None for invalid formats."""
    if not strategy_id:
        return None
    s = strategy_id.strip()
    m = _MULTI_BODY_RE.match(s)
    if not m:
        return None
    inner = m.group(1).strip()
    if not inner:
        return None
    parts = re.split(r"[+,]", inner)
    out = [p.strip() for p in parts if p.strip()]
    return out if out else None


def validate_multi_strategy_id(strategy_id):
    """Return (True, None) or (False, error_message)."""
    parts = parse_multi_strategy_components(strategy_id)
    if parts is None:
        return (
            False,
            "multi: must be multi:{SNN-description,SNN-description} or multi:{SNN-description+SNN-description} (at least 2 child strategies)",
        )
    if len(parts) < 2:
        return False, "multi: must contain at least 2 child strategies (SNN-description)"
    for p in parts:
        if not STRATEGY_ID_BASE_RE.match(p):
            return (
                False,
                "multi: child strategy '{}' must match SNN-description (e.g. S01-parallel-scan)".format(p),
            )
    if len(set(parts)) != len(parts):
        return False, "multi: duplicate child strategies are not allowed"
    return True, None
