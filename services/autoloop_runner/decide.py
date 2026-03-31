"""DECIDE：校验并序列化 plan.decide_act_handoff。"""

from __future__ import annotations

import json
from typing import Any


REQUIRED_KEYS = ("strategy_id", "hypothesis", "planned_commands")


def validate_handoff(obj: dict[str, Any]) -> tuple[bool, str]:
    if not isinstance(obj, dict):
        return False, "handoff_not_object"
    for k in REQUIRED_KEYS:
        if k not in obj or obj[k] in (None, ""):
            return False, f"missing_{k}"
    sid = str(obj["strategy_id"]).strip()
    if not sid or not sid[0].upper().startswith("S"):
        return False, "strategy_id_format"
    cmds = obj["planned_commands"]
    if not isinstance(cmds, list) or not all(isinstance(x, str) for x in cmds):
        return False, "planned_commands_not_string_list"
    imp = obj.get("impacted_dimensions")
    if imp is not None and not isinstance(imp, list):
        return False, "impacted_dimensions_not_list"
    if imp is not None:
        for x in imp:
            if not isinstance(x, str):
                return False, "impacted_dimensions_item_not_str"
    return True, ""


def handoff_to_state_json(obj: dict[str, Any]) -> str:
    """单行 JSON 供 autoloop-state.py update 使用。"""
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
