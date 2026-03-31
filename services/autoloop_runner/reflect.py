"""P1-2：REFLECT JSON 校验（与 experience write / validate strict 对齐）。"""

from __future__ import annotations

from typing import Any

_VALID_EFFECTS = frozenset({"保持", "避免", "待验证"})


def validate_reflect(obj: dict[str, Any]) -> tuple[bool, str]:
    if not isinstance(obj, dict):
        return False, "reflect_not_object"
    sid = str(obj.get("strategy_id", "")).strip()
    if not sid:
        return False, "missing_strategy_id"
    eff = str(obj.get("effect", "")).strip()
    if eff not in _VALID_EFFECTS:
        return False, "invalid_effect"
    if obj.get("score") is None and obj.get("delta") is None:
        return False, "missing_score_or_delta"
    dim = str(obj.get("dimension", "")).strip()
    if not dim:
        return False, "missing_dimension"
    return True, ""


def normalize_reflect(obj: dict[str, Any]) -> dict[str, Any]:
    """统一 score 键供 state / experience 使用。"""
    out = dict(obj)
    if "score" not in out and "delta" in out:
        out["score"] = out["delta"]
    if "score" in out and not isinstance(out["score"], str):
        out["score"] = str(out["score"])
    out.setdefault("context", "")
    return out
